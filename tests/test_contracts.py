import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.contracts import InputError, plan_input, task_brief, validate_contract
from scripts.workflow import plan


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "contracts.py"


def sample():
    return {
        "schema_version": 1,
        "spec": {"spec_id": "spec-x", "problem": "bad dates are accepted", "outcome": "reject invalid dates",
                 "acceptance": [{"id": "AC-1", "description": "invalid dates fail", "verification": ["run unit test"]},
                                {"id": "AC-2", "description": "valid dates pass", "verification": ["run integration test"]}],
                 "out_of_scope": ["date format changes"], "glossary": "glossary.md", "decisions": ["decision.md"]},
        "tickets": [
            {"task_id": "validate", "goal": "Reject invalid dates and preserve valid date handling.", "acceptance_ids": ["AC-1"],
             "worktree_id": "opaque-1", "writable_paths": ["src/validate.py"], "depends_on": [], "constraints": [], "review": "lead"},
            {"task_id": "integrate", "goal": "Apply date validation in the import flow.", "acceptance_ids": ["AC-2"],
             "worktree_id": "opaque-2", "writable_paths": ["src/flow.py"], "depends_on": ["validate"], "constraints": [], "review": "independent"},
        ],
    }


class ContractsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "glossary.md").write_text("terms\n", encoding="utf-8")
        (self.root / "decision.md").write_text("decision\n", encoding="utf-8")
        self.contract_path = self.root / "contract.json"

    def tearDown(self):
        self.temp.cleanup()

    def valid(self, data=None):
        return validate_contract(data or sample(), self.contract_path)

    def test_contract_renders_workflow_compatible_plan_and_brief(self):
        contract = self.valid()
        planned = plan(plan_input(contract), workers=2)
        self.assertEqual([item["task_id"] for item in planned["selected"]], ["validate"])
        self.assertIn("AC-1: invalid dates fail", planned["selected"][0]["brief"])
        brief = task_brief(contract, "integrate")
        self.assertEqual(brief["acceptance"][0]["verification"], ["run integration test"])
        self.assertEqual(brief["depends_on"], ["validate"])
        self.assertEqual(brief["glossary"], "glossary.md")
        self.assertFalse(brief["worktree_identity_verified"])

    def test_rejects_unassigned_or_unknown_acceptance_and_cycles(self):
        data = sample()
        data["tickets"][1]["acceptance_ids"] = ["missing"]
        with self.assertRaisesRegex(InputError, "unknown acceptance"):
            self.valid(data)
        data = sample()
        data["tickets"][1]["depends_on"] = ["validate"]
        data["tickets"][0]["depends_on"] = ["integrate"]
        with self.assertRaisesRegex(InputError, "cycle"):
            self.valid(data)
        data = sample()
        data["tickets"].pop()
        with self.assertRaisesRegex(InputError, "unassigned"):
            self.valid(data)

    def test_rejects_invalid_ids_verification_and_paths(self):
        data = sample()
        data["spec"]["acceptance"][0]["verification"] = []
        with self.assertRaisesRegex(InputError, "verification"):
            self.valid(data)
        data = sample()
        data["tickets"][0]["writable_paths"] = ["../outside.py"]
        with self.assertRaisesRegex(InputError, "canonical relative"):
            self.valid(data)
        data = sample()
        data["spec"]["glossary"] = "../outside.md"
        with self.assertRaisesRegex(InputError, "canonical relative"):
            self.valid(data)

    def test_root_override_allows_project_docs_and_enforces_containment(self):
        examples = self.root / "examples"
        examples.mkdir()
        contract_path = examples / "contract.json"
        contract_path.write_text("{}", encoding="utf-8")
        result = validate_contract(sample(), contract_path, self.root)
        self.assertEqual(result["spec"]["spec_id"], "spec-x")
        bad = sample()
        bad["spec"]["decisions"] = [".env.local"]
        with self.assertRaisesRegex(InputError, "protected path"):
            validate_contract(bad, contract_path, self.root)

    def test_schema_version_and_required_fields_are_strict(self):
        for version in (True, 1.0):
            data = sample()
            data["schema_version"] = version
            with self.subTest(version=version), self.assertRaises(InputError):
                self.valid(data)
        data = sample()
        del data["tickets"][0]["constraints"]
        with self.assertRaisesRegex(InputError, "missing or unknown"):
            self.valid(data)

    def test_duplicate_and_malformed_json_clean_cli_errors(self):
        self.contract_path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), "validate", str(self.contract_path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("schema_version", result.stderr)

    def test_cli_plan_input_and_brief(self):
        self.contract_path.write_text(json.dumps(sample()), encoding="utf-8")
        converted = subprocess.run([sys.executable, str(SCRIPT), "plan-input", str(self.contract_path)], capture_output=True, text=True)
        self.assertEqual(converted.returncode, 0, converted.stderr)
        compatible = plan(json.loads(converted.stdout))
        self.assertEqual(compatible["selected"][0]["task_id"], "validate")
        brief = subprocess.run([sys.executable, str(SCRIPT), "brief", str(self.contract_path), "--task", "integrate"], capture_output=True, text=True)
        self.assertEqual(brief.returncode, 0, brief.stderr)
        self.assertEqual(json.loads(brief.stdout)["acceptance"][0]["id"], "AC-2")


if __name__ == "__main__":
    unittest.main()
