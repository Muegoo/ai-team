import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import checks


ROOT = Path(__file__).resolve().parents[1]
SECRET = "AKIA" + "1234567890" + "ABCDEF"


class ChecksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True, check=True)

    def test_staged_scan_reads_index_blob_not_worktree_bytes(self):
        file = self.root / "source.py"
        file.write_text("value = 'safe'\n", encoding="utf-8")
        self.git("add", "source.py")
        file.write_text(f"value = '{SECRET}'\n", encoding="utf-8")
        safe = checks.scan_staged(self.root)
        self.assertEqual(safe["status"], "passed")
        self.assertEqual(safe["diagnostics"], [])
        self.assertTrue(safe["scope_limited"])
        file.write_text(f"value = '{SECRET}'\n", encoding="utf-8")
        self.git("add", "source.py")
        found = checks.scan_staged(self.root)
        self.assertEqual(found["status"], "failed")
        self.assertEqual(found["diagnostics"], [{"path": "source.py", "line": 1, "rule_id": "AWS_ACCESS_KEY_ID"}])
        self.assertNotIn(SECRET, json.dumps(found))

    def test_all_fixed_secret_rule_families_emit_only_rule_ids(self):
        file = self.root / "patterns.txt"
        key = b"AKIA" + b"1234567890" + b"ABCDEF"
        github = b"ghp_" + b"x" * 35
        openai = b"sk-" + b"y" * 40
        header = b"-----BEGIN " + b"OPENSSH " + b"PRIVATE KEY-----"
        file.write_bytes(header + b"\n" + key + b"\n" + github + b"\n" + openai + b"\n")
        self.git("add", "patterns.txt")
        result = checks.scan_staged(self.root)
        self.assertEqual([item["rule_id"] for item in result["diagnostics"]],
                         ["PRIVATE_KEY_HEADER", "AWS_ACCESS_KEY_ID", "GITHUB_TOKEN", "OPENAI_STYLE_KEY"])
        self.assertNotIn(key.decode(), json.dumps(result))
        self.assertNotIn(github.decode(), json.dumps(result))
        self.assertNotIn(openai.decode(), json.dumps(result))

    def test_protected_files_are_skipped_without_reading_index_content(self):
        (self.root / ".env.local").write_text(SECRET, encoding="utf-8")
        self.git("add", ".env.local")
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            return subprocess.run(command, **kwargs)

        result = checks.scan_staged(self.root, runner=runner)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["skipped"]["protected"], 1)
        self.assertFalse(any("cat-file" in command for command in calls))

    def test_symlink_binary_and_generated_coverage_is_reported(self):
        target = self.root / "target.txt"
        target.write_text("ordinary", encoding="utf-8")
        (self.root / "link.txt").symlink_to(target)
        (self.root / ".build").mkdir()
        (self.root / ".build/cache.txt").write_text("ordinary", encoding="utf-8")
        (self.root / "image.bin").write_bytes(b"\0binary")
        self.git("add", "target.txt", "link.txt", ".build/cache.txt", "image.bin")
        result = checks.scan_staged(self.root)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["skipped"]["symlink_or_submodule"], 1)
        self.assertEqual(result["skipped"]["generated"], 1)
        self.assertEqual(result["skipped"]["binary"], 1)

    def test_git_failure_is_generic_and_does_not_expose_output(self):
        other = tempfile.TemporaryDirectory()
        try:
            non_repo = Path(other.name)
            result = checks.scan_staged(non_repo)
        finally:
            other.cleanup()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"], "git index read failed")
        self.assertNotIn("fatal:", json.dumps(result))

    def test_staged_json_validation_uses_index_bytes_not_valid_worktree_copy(self):
        file = self.root / "skills-registry.json"
        file.write_text('{"schema_version":1.0,"skills":[]}', encoding="utf-8")
        self.git("add", "skills-registry.json")
        file.write_text('{"schema_version":1,"skills":[]}', encoding="utf-8")
        result = checks.scan_staged(self.root)
        self.assertEqual(result["status"], "failed")
        self.assertIn({"path": "skills-registry.json", "line": 1, "rule_id": "INVALID_STAGED_JSON"}, result["diagnostics"])

    def test_nul_staged_required_json_fails_even_with_valid_worktree_copy(self):
        file = self.root / "skills-registry.json"
        file.write_bytes(b'{"schema_version":1,"skills":[]}\0')
        self.git("add", "skills-registry.json")
        file.write_text('{"schema_version":1,"skills":[]}', encoding="utf-8")

        result = checks.scan_staged(self.root)
        self.assertEqual(result["status"], "failed")
        self.assertIn({"path": "skills-registry.json", "line": 1, "rule_id": "INVALID_STAGED_JSON"}, result["diagnostics"])
        self.assertEqual(result["skipped"]["binary"], 0)

    def test_oversized_staged_required_json_fails_without_reading_content(self):
        file = self.root / "skills-registry.json"
        file.write_bytes(b'{"schema_version":1,"skills":[]}' + b" " * (checks.MAX_STAGED_BYTES + 1))
        self.git("add", "skills-registry.json")
        file.write_text('{"schema_version":1,"skills":[]}', encoding="utf-8")

        result = checks.scan_staged(self.root)
        self.assertEqual(result["status"], "failed")
        self.assertIn({"path": "skills-registry.json", "line": 1, "rule_id": "INVALID_STAGED_JSON"}, result["diagnostics"])
        self.assertEqual(result["skipped"]["oversized"], 0)

    def test_required_json_symlink_and_missing_index_entry_fail_closed(self):
        file = self.root / "skills-registry.json"
        target = self.root / "target.json"
        target.write_text('{"schema_version":1,"skills":[]}', encoding="utf-8")
        file.symlink_to(target.name)
        self.git("add", "skills-registry.json")
        file.unlink()
        file.write_text('{"schema_version":1,"skills":[]}', encoding="utf-8")

        symlink_result = checks.scan_staged(self.root)
        self.assertEqual(symlink_result["status"], "failed")
        self.assertIn({"path": "skills-registry.json", "line": 1, "rule_id": "INVALID_STAGED_JSON"}, symlink_result["diagnostics"])
        self.assertEqual(symlink_result["skipped"]["symlink_or_submodule"], 0)

        def missing_index(command, **kwargs):
            if command[:4] == ["git", "diff", "--cached", "--name-only"]:
                return subprocess.CompletedProcess(command, 0, b"skills-registry.json\0", b"")
            if command[:3] == ["git", "ls-files", "--stage"]:
                return subprocess.CompletedProcess(command, 0, b"", b"")
            return subprocess.run(command, **kwargs)

        missing_result = checks.scan_staged(self.root, runner=missing_index)
        self.assertEqual(missing_result["status"], "failed")
        self.assertIn({"path": "skills-registry.json", "line": 1, "rule_id": "INVALID_STAGED_JSON"}, missing_result["diagnostics"])

    def test_ordinary_missing_or_non_stage_zero_index_entry_fails_scan(self):
        file = self.root / "source.py"
        file.write_text("value = 1\n", encoding="utf-8")

        for index_output in (b"", b"100644 " + b"a" * 40 + b" 1\tsource.py\0"):
            def incomplete_index(command, **kwargs):
                if command[:4] == ["git", "diff", "--cached", "--name-only"]:
                    return subprocess.CompletedProcess(command, 0, b"source.py\0", b"")
                if command[:3] == ["git", "ls-files", "--stage"]:
                    return subprocess.CompletedProcess(command, 0, index_output, b"")
                return subprocess.run(command, **kwargs)

            result = checks.scan_staged(self.root, runner=incomplete_index)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error"], "staged blob read failed")
            self.assertEqual(result["exit_code"], 1)

    def test_staged_blob_read_failure_fails_the_gate(self):
        file = self.root / "source.py"
        file.write_text("plain text\n", encoding="utf-8")
        self.git("add", "source.py")

        def runner(command, **kwargs):
            if "cat-file" in command:
                return subprocess.CompletedProcess(command, 1, b"sensitive git error", b"secret output")
            return subprocess.run(command, **kwargs)

        result = checks.scan_staged(self.root, runner=runner)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"], "staged blob read failed")
        self.assertNotIn("secret output", json.dumps(result))

    def test_minimal_profile_checks_shipped_artifacts(self):
        report, code = checks.run_profile("minimal", ROOT)
        self.assertEqual(code, 0, report)
        self.assertEqual([item["name"] for item in report["checks"]], ["skills_registry", "lesson_store", "example_contract"])
        self.assertFalse(report["acceptance_claimed"])

    def test_registry_gate_rejects_oversized_active_skill_file(self):
        registry_path = self.root / "skills-registry.json"
        registry_path.write_bytes((ROOT / "skills-registry.json").read_bytes())
        data = checks.read_json(registry_path)
        data["skills"][0]["path"] = "local/SKILL.md"
        (self.root / "local").mkdir()
        (self.root / "local/SKILL.md").write_bytes(b"x" * (1_048_576 + 1))

        with self.assertRaises(checks.InputError):
            checks._validate_registry_state(data, registry_path)

    def test_standard_uses_fixed_unittest_argv_timeout_and_hides_output(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 7, "Ran 17 tests", f"secret {SECRET}")

        with patch.object(checks, "_minimal_checks", return_value=[]):
            report, code = checks.run_profile("standard", ROOT, runner=runner)
        self.assertEqual(code, 7)
        self.assertEqual(calls[0][0], [checks.sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])
        self.assertEqual(calls[0][1]["timeout"], checks.TIMEOUT_SECONDS)
        self.assertEqual(report["checks"][0]["test_count"], 17)
        self.assertNotIn(SECRET, json.dumps(report))

    def test_strict_diff_check_reports_only_locations(self):
        def runner(command, **kwargs):
            if "--name-only" in command:
                return subprocess.CompletedProcess(command, 0, b"src/file.py\0", b"")
            fake_token = b"ghp_" + b"x" * 35
            return subprocess.CompletedProcess(command, 2,
                                              b"src/file.py:9: trailing whitespace.\n+" + fake_token + b":123: source text\n", b"")

        result = checks._diff_check(self.root, runner)
        self.assertEqual(result["exit_code"], 2)
        self.assertEqual(result["locations"], [{"path": "src/file.py", "line": 9}])
        self.assertNotIn("x" * 35, json.dumps(result))

    def test_executable_hook_runs_through_git_in_owned_repository(self):
        paths = ["scripts/checks.py", "scripts/practice_common.py", "scripts/skills.py",
                 "scripts/lessons.py", "scripts/contracts.py", "skills-registry.json", "knowledge/lessons.json",
                 "examples/practices/contract.json", "examples/practices/glossary.md",
                 "examples/practices/decision.md", ".agents/skills/ai-team-routing/SKILL.md",
                 ".githooks/pre-commit"]
        for relative in paths:
            source = ROOT / relative
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        self.assertTrue(os.access(self.root / ".githooks/pre-commit", os.X_OK))
        self.git("add", "-A")
        self.git("config", "core.hooksPath", str(self.root / ".githooks"))
        result = subprocess.run(["git", "-c", "user.name=Temporary Test", "-c", "user.email=temporary@example.invalid",
                                 "commit", "--allow-empty", "-m", "hook test"],
                                cwd=self.root, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"profile": "minimal"', result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
