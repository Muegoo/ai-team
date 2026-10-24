import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.lessons import InputError, select_lessons, validate_store


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lessons.py"


def lesson(lesson_id="l1", project="alpha", *, trigger="date validation", status="approved", evidence=None,
          reviewer="Codex Sol", reviewed_at="2026-10-24"):
    return {"lesson_id": lesson_id, "project_id": project, "trigger": trigger,
            "observation": "Observed in an accepted synthetic task.", "action": "Keep one focused check.",
            "evidence": evidence or ["source.py"], "source_task": "task-1", "status": status,
            "reviewed_by": reviewer, "reviewed_at": reviewed_at}


def store(*lessons):
    return {"schema_version": 1, "lessons": list(lessons)}


class LessonsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "source.py").write_text("source\n", encoding="utf-8")
        self.store_path = self.root / "lessons.json"

    def tearDown(self):
        self.temp.cleanup()

    def valid(self, data=None, root=None):
        return validate_store(data or store(lesson()), self.store_path, root)

    def test_selects_only_approved_exact_project_and_ranks_trigger_overlap(self):
        data = store(lesson("a", trigger="date validation"),
                     lesson("b", trigger="date validation import"),
                     lesson("foreign", project="beta"),
                     lesson("proposed", status="proposed", reviewer=None, reviewed_at=None))
        selected = select_lessons(self.valid(data), "alpha", "import validation", limit=5)
        self.assertEqual([item["lesson_id"] for item in selected], ["b", "a"])

    def test_review_requirements_and_strict_types(self):
        for bad in (lesson(reviewer=None), lesson(reviewed_at=None), lesson(reviewed_at="20261024"), lesson(reviewer=[])):
            with self.subTest(bad=bad), self.assertRaises(InputError):
                self.valid(store(bad))
        self.assertEqual(len(self.valid(store(lesson(status="proposed", reviewer=None, reviewed_at=None)))["lessons"]), 1)

    def test_duplicate_ids_and_bad_schema_rejected(self):
        with self.assertRaisesRegex(InputError, "duplicate"):
            self.valid(store(lesson(), lesson()))
        for bad in ({"schema_version": 1, "lessons": {}}, {"schema_version": True, "lessons": []}):
            with self.assertRaises(InputError):
                self.valid(bad)
        with self.assertRaises(InputError):
            self.valid({"schema_version": 1.0, "lessons": []})
        missing = lesson()
        del missing["source_task"]
        with self.assertRaisesRegex(InputError, "missing or unknown"):
            self.valid(store(missing))

    def test_evidence_requires_nonempty_safe_local_or_https_reference(self):
        self.valid(store(lesson(evidence=["https://example.com/evidence", "source.py"])))
        for path in ("../secret", ".env", ".git/config", "/tmp/outside", "bad\\path"):
            with self.subTest(path=path), self.assertRaises(InputError):
                self.valid(store(lesson(evidence=[path])))
        with self.assertRaises(InputError):
            self.valid(store(lesson(evidence=["http://example.com/evidence"])))

    def test_root_override_supports_repo_relative_evidence(self):
        nested = self.root / "knowledge"
        nested.mkdir()
        store_path = nested / "lessons.json"
        valid = validate_store(store(lesson(evidence=["source.py"])), store_path, self.root)
        self.assertEqual(len(valid["lessons"]), 1)

    def test_limit_is_bounded_positive_and_project_required(self):
        valid = self.valid()
        for limit in (0, -1, 101, True):
            with self.subTest(limit=limit), self.assertRaisesRegex(InputError, "limit"):
                select_lessons(valid, "alpha", limit=limit)
        with self.assertRaisesRegex(InputError, "project"):
            select_lessons(valid, " ")

    def test_cli_rejects_duplicate_json_and_emits_no_output(self):
        self.store_path.write_text('{"schema_version":1,"lessons":[],"lessons":[]}', encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), "validate", str(self.store_path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("lessons", result.stderr)

    def test_cli_selects_expected_project(self):
        self.store_path.write_text(json.dumps(store(lesson(), lesson("other", project="beta"))), encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), "select", str(self.store_path), "--project", "alpha"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([row["lesson_id"] for row in json.loads(result.stdout)["lessons"]], ["l1"])


if __name__ == "__main__":
    unittest.main()
