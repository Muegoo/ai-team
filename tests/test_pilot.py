import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.pilot import InputError, summarize, validate_records


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pilot.py"


def row(task_id="task-a", mode="team-2", status="accepted", elapsed=10, rework=0, cost=None, tokens=None):
    return {
        "task_id": task_id,
        "mode": mode,
        "status": status,
        "elapsed_seconds": elapsed,
        "rework_count": rework,
        "cost_usd": cost,
        "tokens": tokens,
    }


class PilotTests(unittest.TestCase):
    def test_aggregation_includes_rejected_and_blocked_effort(self):
        data = validate_records([
            row(status="accepted", elapsed=10, rework=0, cost=2, tokens=100),
            row("task-b", status="rejected", elapsed=20, rework=1, cost=3, tokens=150),
            row("task-c", status="blocked", elapsed=30, rework=2, cost=5, tokens=250),
        ])
        summary = summarize(data)["modes"]["team-2"]
        self.assertEqual(summary["counts"], {"accepted": 1, "rejected": 1, "blocked": 1})
        self.assertEqual(summary["total_elapsed_seconds"], 60)
        self.assertEqual(summary["seconds_per_accepted"], 60)
        self.assertEqual(summary["first_pass_rate"], 1 / 3)
        self.assertEqual(summary["cost_usd"]["per_accepted"], 10)
        self.assertEqual(summary["tokens"]["per_accepted"], 500)

    def test_missing_usage_is_unknown_but_measured_zero_is_known(self):
        result = summarize(validate_records([
            row(cost=0, tokens=0),
            row("task-b", cost=None, tokens=0),
        ]))["modes"]["team-2"]
        self.assertEqual(result["cost_usd"], {"measured_count": 1, "total": None, "per_accepted": None})
        self.assertEqual(result["tokens"], {"measured_count": 2, "total": 0, "per_accepted": 0})

    def test_no_accepted_results_has_null_per_accepted_metrics(self):
        result = summarize(validate_records([row(status="blocked", elapsed=7, cost=1, tokens=4)]))["modes"]["team-2"]
        self.assertIsNone(result["seconds_per_accepted"])
        self.assertIsNone(result["cost_usd"]["per_accepted"])
        self.assertIsNone(result["tokens"]["per_accepted"])

    def test_duplicate_task_and_mode_is_rejected(self):
        with self.assertRaisesRegex(InputError, "duplicate"):
            validate_records([row(), row()])

    def test_rejects_invalid_types_booleans_and_nonfinite_values(self):
        cases = [
            row(elapsed=True),
            row(rework=False),
            row(cost=float("nan")),
            row(tokens=True),
            row(elapsed=math.inf),
            row(status="unknown"),
            row(mode="baseline", task_id=" "),
        ]
        for invalid in cases:
            with self.subTest(invalid=invalid), self.assertRaises(InputError):
                validate_records([invalid])

    def test_rejects_empty_input(self):
        with self.assertRaisesRegex(InputError, "no measurements"):
            validate_records([])

    def test_cli_summarize_success_and_clean_error(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "records.json"
            fixture.write_text(json.dumps([row(cost=0, tokens=0)]), encoding="utf-8")
            good = subprocess.run([sys.executable, str(SCRIPT), "summarize", str(fixture)], capture_output=True, text=True)
            self.assertEqual(good.returncode, 0)
            self.assertEqual(json.loads(good.stdout)["modes"]["team-2"]["cost_usd"]["per_accepted"], 0)
            fixture.write_text("{}", encoding="utf-8")
            bad = subprocess.run([sys.executable, str(SCRIPT), "summarize", str(fixture)], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)
            self.assertEqual(bad.stdout, "")
            self.assertIn("error:", bad.stderr)
            self.assertNotIn("Traceback", bad.stderr)

    def test_cli_aggregate_overflow_fails_before_writing_json(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "overflow.json"
            fixture.write_text(json.dumps([
                row(task_id="task-a", elapsed=1e308),
                row(task_id="task-b", elapsed=1e308),
            ]), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), "summarize", str(fixture)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("error: aggregated elapsed_seconds is not finite", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_cli_mixed_huge_integer_and_float_overflow_is_clean_error(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "mixed-overflow.json"
            fixture.write_text(json.dumps([
                row(task_id="task-a", elapsed=10**400),
                row(task_id="task-b", elapsed=0.5),
            ]), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), "summarize", str(fixture)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("error: aggregated elapsed_seconds is outside the representable range", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
