import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.skills import InputError, audit
from scripts.practice_common import read_json


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "skills.py"


def record(skill_id="local", *, name="Local", path="skills/local/SKILL.md", **changes):
    value = {
        "id": skill_id, "name": name, "path": path, "source_url": None, "source_revision": None,
        "role": "controller", "triggers": ["review task"], "overlap_group": None, "status": "active",
        "review": {"verdict": "unreviewed", "reason": "initial entry", "reviewed_at": None},
    }
    value.update(changes)
    return value


def registry(*records):
    return {"schema_version": 1, "skills": list(records)}


class SkillsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "skills/local").mkdir(parents=True)
        self.skill_file = self.root / "skills/local/SKILL.md"
        self.skill_file.write_text("# Local skill\n", encoding="utf-8")
        self.registry_path = self.root / "skills-registry.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_audit_reports_findings_and_not_checked_freshness(self):
        remote = record("remote", name="Local", path=None, status="candidate",
                        source_url="https://example.com/skill", overlap_group="shared")
        local2 = record("local-copy", path="skills/copy/SKILL.md", overlap_group="shared")
        (self.root / "skills/copy").mkdir()
        (self.root / "skills/copy/SKILL.md").write_text("# Local skill\n", encoding="utf-8")
        result = audit(registry(record(overlap_group="shared"), local2, remote), self.registry_path)
        rules = {item["rule"] for item in result["findings"]}
        self.assertTrue({"duplicate_name", "identical_local_content", "shared_overlap_group", "remote_revision_unpinned"} <= rules)
        self.assertEqual(result["skills"][0]["source_freshness"], "not_checked")
        self.assertFalse(result["metadata_labels_prove_installed_identity_or_authorization"])

    def test_previous_snapshot_tracks_new_removed_metadata_and_content(self):
        original = audit(registry(record()), self.registry_path)
        self.skill_file.write_text("# Changed\n", encoding="utf-8")
        changed = record(name="Renamed")
        result = audit(registry(changed, record("new", path=None, status="candidate")), self.registry_path, original)
        self.assertEqual(result["changes"], {
            "new_ids": ["new"], "removed_ids": [], "metadata_changed_ids": ["local"],
            "content_changed_ids": ["local"],
        })
        removed = audit(registry(), self.registry_path, result)
        self.assertEqual(removed["changes"]["removed_ids"], ["local", "new"])

    def test_duplicate_ids_and_malformed_previous_snapshot_rejected(self):
        with self.assertRaisesRegex(InputError, "duplicate skill id"):
            audit(registry(record(), record()), self.registry_path)
        with self.assertRaisesRegex(InputError, "previous input"):
            audit(registry(record()), self.registry_path, {})

    def test_schema_types_and_remote_url_are_strict(self):
        for bad in (
            record(triggers=[]),
            record(role=[]),
            record(source_url="http://example.com"),
            record(review={"verdict": "unreviewed", "reason": "x", "reviewed_at": "yesterday"}),
            record(status="candidate", path="skills/local/SKILL.md"),
            {key: value for key, value in record().items() if key != "triggers"},
        ):
            with self.subTest(bad=bad), self.assertRaises(InputError):
                audit(registry(bad), self.registry_path)

    def test_missing_or_unreadable_file_is_a_finding(self):
        result = audit(registry(record(path="skills/missing/SKILL.md")), self.registry_path)
        self.assertFalse(result["skills"][0]["exists"])
        self.assertEqual(result["findings"][0]["rule"], "local_file_unavailable")

    def test_traversal_and_symlink_escape_rejected(self):
        with self.assertRaisesRegex(InputError, "canonical relative"):
            audit(registry(record(path="../outside/SKILL.md")), self.registry_path)
        with tempfile.TemporaryDirectory() as separate:
            outside = Path(separate) / "outside-skill"
            outside.mkdir()
            (outside / "SKILL.md").write_text("untrusted text", encoding="utf-8")
            link = self.root / "skills/escape"
            link.symlink_to(outside)
            with self.assertRaisesRegex(InputError, "outside its allowed root"):
                audit(registry(record(path="skills/escape/SKILL.md")), self.registry_path)

    def test_protected_internal_symlink_and_primary_json_symlink_are_rejected_before_read(self):
        protected_dir = self.root / ".env.secret"
        protected_dir.mkdir()
        protected = protected_dir / "SKILL.md"
        protected.write_text("not for the CLI", encoding="utf-8")
        target = self.root / "skills/protected"
        target.symlink_to(protected_dir)
        with self.assertRaisesRegex(InputError, "protected"):
            audit(registry(record(path="skills/protected/SKILL.md")), self.registry_path)
        input_link = self.root / "safe-name.json"
        input_link.symlink_to(protected)
        with self.assertRaisesRegex(InputError, "protected"):
            read_json(input_link)

    def test_schema_versions_and_enum_containers_are_strict(self):
        for version in (True, 1.0):
            with self.subTest(version=version), self.assertRaises(InputError):
                audit({"schema_version": version, "skills": []}, self.registry_path)
        bad = record()
        bad["review"]["verdict"] = {}
        with self.assertRaises(InputError):
            audit(registry(bad), self.registry_path)
        pinned = record("remote", path=None, status="candidate", source_url="https://example.com/skill",
                        source_revision="a" * 40)
        self.assertNotIn("remote_revision_unpinned", {item["rule"] for item in audit(registry(pinned), self.registry_path)["findings"]})
        pinned["source_revision"] = "main"
        self.assertIn("remote_revision_unpinned", {item["rule"] for item in audit(registry(pinned), self.registry_path)["findings"]})

    def test_cli_rejects_duplicate_json_keys_without_raw_input(self):
        self.registry_path.write_text('{"schema_version":1,"schema_version":1,"skills":[]}', encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), "audit", str(self.registry_path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("error:", result.stderr)
        self.assertNotIn("schema_version", result.stderr)
        for raw in ('{"schema_version":NaN,"skills":[]}', '{"schema_version":1e999,"skills":[]}'):
            self.registry_path.write_text(raw, encoding="utf-8")
            invalid = subprocess.run([sys.executable, str(SCRIPT), "audit", str(self.registry_path)], capture_output=True, text=True)
            self.assertEqual(invalid.returncode, 2)
            self.assertEqual(invalid.stdout, "")
            self.assertNotIn("Traceback", invalid.stderr)

    def test_cli_snapshot_output_is_accepted_as_previous(self):
        self.registry_path.write_text(json.dumps(registry(record())), encoding="utf-8")
        first = subprocess.run([sys.executable, str(SCRIPT), "audit", str(self.registry_path)], capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        snapshot_path = self.root / ".build/practices/skills-snapshot.json"
        snapshot_path.parent.mkdir(parents=True)
        snapshot_path.write_text(first.stdout, encoding="utf-8")
        second = subprocess.run([sys.executable, str(SCRIPT), "audit", str(self.registry_path), "--previous", str(snapshot_path)], capture_output=True, text=True)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout)["changes"]["new_ids"], [])


if __name__ == "__main__":
    unittest.main()
