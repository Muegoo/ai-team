import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.workflow import InputError, plan, usage, wait_for_messages


def task(task_id, path, *, deps=None, worktree=None):
    return {"task_id": task_id, "goal": f"Do {task_id}", "writable_paths": [path],
            "worktree_id": worktree or f"wt-{task_id}", "depends_on": deps or [],
            "acceptance": ["accepted"]}


def usage_event(timestamp, input_tokens, output_tokens, *, cached=None, reasoning=None):
    counters = {"input_tokens": input_tokens, "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens}
    if cached is not None:
        counters["cached_input_tokens"] = cached
    if reasoning is not None:
        counters["reasoning_output_tokens"] = reasoning
    return {"type": "event_msg", "timestamp": timestamp,
            "payload": {"type": "token_count", "info": {"total_token_usage": counters, "last_token_usage": counters}}}


def task_event(kind, timestamp):
    return {"type": "event_msg", "timestamp": timestamp, "payload": {"type": kind}}


def write_log(directory, session_id, events, name=None):
    path = Path(directory) / (name or f"{session_id}.jsonl")
    records = [{"type": "session_meta", "payload": {"id": session_id}},
               {"type": "turn_context", "payload": {"model": "codex-luna"}}, *events]
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    return path


class WorkflowTests(unittest.TestCase):
    def test_default_one_and_two_ready_tasks(self):
        data = {"tasks": [task("a", "src/a.py"), task("b", "src/b.py")]}
        self.assertEqual([item["task_id"] for item in plan(data)["selected"]], ["a"])
        self.assertEqual([item["task_id"] for item in plan(data, workers=2)["selected"]], ["a", "b"])

    def test_dependency_release_and_conflicts(self):
        data = {"tasks": [task("a", "src/a"), task("b", "src/b", deps=["a"]),
                          task("c", "pkg/child"), task("d", "pkg", worktree="wt-d")]}
        result = plan(data, workers=3, completed=["a"])
        self.assertEqual([item["task_id"] for item in result["selected"]], ["b", "c"])
        self.assertEqual(result["deferred"], [{"task_id": "d", "reason": "conflicts with c"}])
        same_tree = {"tasks": [task("x", "one", worktree="shared"), task("y", "two", worktree="shared")]}
        self.assertEqual(plan(same_tree, workers=2)["selected"][0]["task_id"], "x")
        self.assertIn("conflicts", plan(same_tree, workers=2)["deferred"][0]["reason"])

    def test_plan_rejects_invalid_graph_state_and_oversized_brief(self):
        for data in (
            {"tasks": [task("a", "src/../x")]},
            {"tasks": [task("a", "a", deps=["missing"]) ]},
            {"tasks": [task("a", "a", deps=["b"]), task("b", "b", deps=["a"]) ]},
        ):
            with self.subTest(data=data), self.assertRaises(InputError):
                plan(data)
        data = {"tasks": [task("a", "src/a")]}
        with self.assertRaisesRegex(InputError, "task a"):
            plan(data, max_brief_chars=20)
        with self.assertRaises(InputError):
            plan(data, completed=["a"], active=["a"])

    def test_wait_empty_then_actionable_without_ack(self):
        now = [0.0]
        calls = []

        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            if len(calls) == 1:
                now[0] += 0.2
                receipt = {"ok": True, "result": {"runId": "run-1", "messages": [], "timedOut": True}}
            else:
                receipt = {"ok": True, "result": {"runId": "run-1", "deliveryId": "delivery-1",
                           "messages": [{"id": "m1", "type": "worker_done", "subject": "done", "body": "x" * 1100,
                               "payload": json.dumps({"taskId": "t", "dispatchId": "d", "reportPath": "result.json", "outcome": "succeeded"})},
                               {"id": "m2", "type": "future_event", "subject": "future", "body": "preserve", "payload": "{}"}]}}
            return subprocess.CompletedProcess(argv, 0, json.dumps(receipt), "")

        result = wait_for_messages("run-1", 3, runner=runner, clock=lambda: now[0])
        self.assertEqual(result["event"], "messages")
        self.assertFalse(result["acknowledged"])
        self.assertTrue(result["review_before_ack"])
        self.assertEqual(len(result["messages"][0]["body_preview"]), 1000)
        self.assertTrue(result["messages"][0]["body_truncated"])
        self.assertEqual(result["messages"][0]["task_id"], "t")
        self.assertEqual(result["messages"][0]["dispatch_id"], "d")
        self.assertEqual(result["messages"][0]["report_path"], "result.json")
        self.assertEqual(result["messages"][1]["type"], "future_event")
        self.assertTrue(all(call[0][-1] == "--json" and call[1]["shell"] is False for call in calls))
        self.assertTrue(all("--ack" not in call[0] for call in calls))

    def test_wait_runtime_error_and_deadline(self):
        def failed(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 1, "", "offline")
        with self.assertRaisesRegex(InputError, "offline"):
            wait_for_messages("run", 1, runner=failed, clock=lambda: 0)
        now = [0.0]

        def empty(argv, **kwargs):
            now[0] += 0.5
            return subprocess.CompletedProcess(argv, 0, json.dumps({"ok": True, "result": {"runId": "run", "messages": [], "timedOut": True}}), "")
        self.assertEqual(wait_for_messages("run", 1, runner=empty, clock=lambda: now[0])["event"], "timeout")

    def test_wait_rejects_connection_and_invalid_message_schema(self):
        def invoke(receipt):
            def runner(argv, **kwargs):
                return subprocess.CompletedProcess(argv, 0, json.dumps(receipt), "")
            return runner
        with self.assertRaisesRegex(InputError, "connection was lost"):
            wait_for_messages("run", 1, runner=invoke({"ok": True, "result": {"runId": "run", "messages": [], "connectionLost": True}}), clock=lambda: 0)
        invalid = {"ok": True, "result": {"runId": "run", "deliveryId": "d", "messages": [{"type": "worker_done", "subject": "x", "body": "y"}]}}
        with self.assertRaisesRegex(InputError, "id"):
            wait_for_messages("run", 1, runner=invoke(invalid), clock=lambda: 0)

    def test_wait_validates_receipt_metadata_for_all_message_types(self):
        def invoke(message):
            receipt = {"ok": True, "result": {"runId": "run", "deliveryId": "d", "messages": [message]}}
            def runner(argv, **kwargs):
                self.assertNotIn("--ack", argv)
                return subprocess.CompletedProcess(argv, 0, json.dumps(receipt), "")
            return runner

        message = {"id": "m", "type": "future_type", "payload": json.dumps({
            "taskId": "t", "dispatchId": "d", "outcome": "failed", "reportPath": "../opaque path",
            "ignored": {"secret": "value"}})}
        result = wait_for_messages("run", 1, runner=invoke(message), clock=lambda: 0)
        self.assertEqual(result["messages"][0], {"id": "m", "type": "future_type", "subject": "",
            "body_preview": "", "body_truncated": False, "task_id": "t", "dispatch_id": "d",
            "outcome": "failed", "report_path": "../opaque path"})
        for metadata in ({"outcome": "succeeded"}, {"reportPath": None}, {}):
            valid = {"id": "m", "type": "future", "subject": "  ", "body": "  ", "payload": metadata}
            self.assertEqual(wait_for_messages("run", 1, runner=invoke(valid), clock=lambda: 0)["event"], "messages")

    def test_wait_rejects_each_invalid_receipt_metadata_field_atomically(self):
        def invoke(messages, delivery_id="d"):
            receipt = {"ok": True, "result": {"runId": "run", "deliveryId": delivery_id, "messages": messages}}
            calls = []
            def runner(argv, **kwargs):
                calls.append(argv)
                return subprocess.CompletedProcess(argv, 0, json.dumps(receipt), "")
            return runner, calls

        valid = {"id": "ok", "type": "future"}
        invalid_messages = [
            ({**valid, "id": " "}, "id"), ({**valid, "id": 4}, "id"),
            ({**valid, "type": " x "}, "type"), ({**valid, "type": None}, "type"),
            ({**valid, "subject": None}, "subject"), ({**valid, "body": 12}, "body"),
            ({**valid, "payload": []}, "payload"), ({**valid, "payload": "[]"}, "payload"),
            ({**valid, "payload": "null"}, "payload"),
            ({**valid, "payload": {"taskId": " t "}}, "taskId"),
            ({**valid, "payload": {"dispatchId": None}}, "dispatchId"),
            ({**valid, "payload": {"outcome": "done"}}, "outcome"),
            ({**valid, "payload": {"outcome": True}}, "outcome"),
            ({**valid, "payload": {"reportPath": " x "}}, "reportPath"),
            ({**valid, "payload": {"reportPath": False}}, "reportPath"),
        ]
        for message, field in invalid_messages:
            with self.subTest(field=field, message=message):
                runner, calls = invoke([valid, message])
                with self.assertRaisesRegex(InputError, field) as caught:
                    wait_for_messages("run", 1, runner=runner, clock=lambda: 0)
                self.assertNotIn("raw", str(caught.exception))
                self.assertEqual(len(calls), 1)
                self.assertFalse(any("--ack" in argv for argv in calls))
        runner, _ = invoke([valid], delivery_id=" d ")
        with self.assertRaisesRegex(InputError, "deliveryId"):
            wait_for_messages("run", 1, runner=runner, clock=lambda: 0)

    def test_usage_deduplicates_checkpoints_and_copied_logs(self):
        with tempfile.TemporaryDirectory() as temp:
            first = usage_event("2026-10-20T10:00:00Z", 10, 4, cached=3, reasoning=1)
            duplicate = usage_event("2026-10-20T10:00:01Z", 10, 4, cached=3, reasoning=1)
            duplicate["payload"]["info"]["last_token_usage"] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 24098}
            advancing_a = usage_event("2026-10-20T10:01:00Z", 20, 8, cached=6, reasoning=2)
            advancing_a["payload"]["info"]["last_token_usage"] = {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14, "cached_input_tokens": 3, "reasoning_output_tokens": 1}
            advancing_b = usage_event("2026-10-20T10:02:00Z", 30, 12, cached=9, reasoning=3)
            advancing_b["payload"]["info"]["last_token_usage"] = dict(advancing_a["payload"]["info"]["last_token_usage"])
            events = [first, duplicate, advancing_a, advancing_b]
            first = write_log(temp, "s1", events, "one.jsonl")
            second = write_log(temp, "s1", events, "copy.jsonl")
            result = usage({"sessions": [{"path": first.name, "session_id": "s1", "role": "worker"},
                                          {"path": second.name, "session_id": "s1", "role": "worker"}]}, Path(temp) / "manifest.json")
            self.assertEqual(result["duplicates_removed"], 1)
            self.assertEqual(result["duplicate_checkpoint_count"], 1)
            self.assertEqual(result["duplicate_checkpoint_validation_count"], 1)
            self.assertEqual(result["worker"]["metrics"]["total_tokens"]["total"], 42)
            self.assertEqual(result["worker"]["metrics"]["uncached_input_tokens"]["total"], 21)

    def test_advancing_checkpoint_with_bad_last_usage_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            advancing = usage_event("2026-10-20T10:01:00Z", 20, 8)
            advancing["payload"]["info"]["last_token_usage"] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            path = write_log(temp, "s", [usage_event("2026-10-20T10:00:00Z", 10, 4), advancing])
            with self.assertRaisesRegex(InputError, "delta does not match"):
                usage({"sessions": [{"path": path.name, "session_id": "s", "role": "worker"}]}, Path(temp) / "manifest.json")

    def test_usage_windows_roles_subsets_and_unknown_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            controller = write_log(temp, "c", [
                usage_event("2026-10-20T10:00:00Z", 10, 4, cached=3, reasoning=1),
                task_event("task_started", "2026-10-20T10:45:00Z"),
                {"type": "turn_context", "payload": {"model": "codex-sol"}},
                {"type": "event_msg", "timestamp": "2026-10-20T11:00:00Z", "payload": {"type": "token_count", "info": {
                    "total_token_usage": {"input_tokens": 18, "output_tokens": 7, "total_tokens": 25},
                    "last_token_usage": {"input_tokens": 8, "output_tokens": 3, "total_tokens": 11}}}},
                task_event("task_complete", "2026-10-20T11:01:00Z")], name="controller.jsonl")
            worker = write_log(temp, "w", [usage_event("2026-10-20T10:30:00Z", 5, 2, cached=2, reasoning=1)], name="worker.jsonl")
            result = usage({"sessions": [
                {"path": controller.name, "session_id": "c", "role": "controller", "start": "2026-10-20T10:30:00+00:00", "end": "2026-10-20T11:30:00+00:00"},
                {"path": worker.name, "session_id": "w", "role": "worker"}]}, Path(temp) / "manifest.json")
            self.assertEqual(result["controller"]["metrics"]["total_tokens"]["total"], 11)
            self.assertEqual(result["controller"]["models"], ["codex-luna", "codex-sol"])
            self.assertEqual(result["sessions"][0]["previous_boundary"], "2026-10-20T10:00:00+00:00")
            self.assertEqual(result["sessions"][0]["usage"]["cached_input_tokens"], None)
            self.assertEqual(result["sessions"][0]["task_started"], 1)
            self.assertEqual(result["sessions"][0]["task_complete"], 1)
            self.assertEqual(result["worker"]["metrics"]["reasoning_output_tokens"]["total"], 1)
            self.assertEqual(result["worker"]["metrics"]["cached_input_tokens"]["total"], 2)
            self.assertEqual(result["combined"]["metrics"]["total_tokens"]["total"], 18)
            empty_worker = write_log(temp, "empty", [], name="empty.jsonl")
            unknown = usage({"sessions": [{"path": empty_worker.name, "session_id": "empty", "role": "worker"}]}, Path(temp) / "manifest.json")
            self.assertIsNone(unknown["worker"]["metrics"]["total_tokens"]["total"])

    def test_usage_rejects_reset_invalid_data_and_overlapping_windows(self):
        with tempfile.TemporaryDirectory() as temp:
            reset = write_log(temp, "s", [usage_event("2026-10-20T10:00:00Z", 10, 4),
                usage_event("2026-10-20T11:00:00Z", 1, 1)])
            spec = {"path": reset.name, "session_id": "s", "role": "worker"}
            with self.assertRaisesRegex(InputError, "reset"):
                usage({"sessions": [spec]}, Path(temp) / "manifest.json")
            reset.write_text("{broken\n", encoding="utf-8")
            with self.assertRaisesRegex(InputError, "malformed JSON"):
                usage({"sessions": [spec]}, Path(temp) / "manifest.json")
            reset = write_log(temp, "s", [usage_event("2026-10-20T10:00:00Z", 10, 4)])
            base = {"path": reset.name, "session_id": "s", "role": "worker"}
            a = {**base, "start": "2026-10-20T09:00:00Z", "end": "2026-10-20T11:00:00Z"}
            b = {**base, "start": "2026-10-20T10:00:00Z", "end": "2026-10-20T12:00:00Z"}
            with self.assertRaisesRegex(InputError, "overlapping"):
                usage({"sessions": [a, b]}, Path(temp) / "manifest.json")

    def test_usage_rejects_conflicting_roles_on_disjoint_windows(self):
        with tempfile.TemporaryDirectory() as temp:
            advancing = usage_event("2026-10-20T12:00:00Z", 20, 8)
            advancing["payload"]["info"]["last_token_usage"] = {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14}
            path = write_log(temp, "s", [usage_event("2026-10-20T10:00:00Z", 10, 4), advancing])
            common = {"path": path.name, "session_id": "s", "start": "2026-10-20T09:00:00Z"}
            sessions = [
                {**common, "role": "controller", "end": "2026-10-20T11:00:00Z"},
                {**common, "role": "worker", "start": "2026-10-20T11:00:00Z", "end": "2026-10-20T13:00:00Z"},
            ]
            with self.assertRaisesRegex(InputError, "conflicting roles"):
                usage({"sessions": sessions}, Path(temp) / "manifest.json")

    def test_windowed_usage_cli_emits_json(self):
        with tempfile.TemporaryDirectory() as temp:
            write_log(temp, "s", [usage_event("2026-10-20T10:00:00Z", 10, 4)], "session.jsonl")
            manifest = Path(temp) / "manifest.json"
            manifest.write_text(json.dumps({"sessions": [{"path": "session.jsonl", "session_id": "s", "role": "worker",
                "start": "2026-10-20T09:00:00Z", "end": "2026-10-20T11:00:00Z"}]}), encoding="utf-8")
            script = Path(__file__).resolve().parents[1] / "scripts" / "workflow.py"
            result = subprocess.run([sys.executable, str(script), "usage", str(manifest)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["worker"]["metrics"]["total_tokens"]["total"], 14)
            self.assertIsInstance(payload["sessions"][0]["next_boundary"], (str, type(None)))


if __name__ == "__main__":
    unittest.main()
