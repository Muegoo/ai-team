# Local engineering practices

These standard-library CLIs validate declared inputs and render bounded proposals. They do not install or discover skills, dispatch workers, accept tickets, run verification commands from a contract, fetch lesson evidence, or establish benchmark outcomes. Codex Astra/Sol owns decisions, review, and lesson approval; Luna/Terra executes approved briefs; Gemini may search and record only controller-approved facts. A role label or reviewer name is supplied metadata, not runtime identity or authorization proof.

## Quickstart

```sh
mkdir -p .build/practices
python3 scripts/skills.py audit skills-registry.json > .build/practices/skills-inventory.json
python3 scripts/skills.py audit skills-registry.json --previous .build/practices/skills-inventory.json
python3 scripts/contracts.py validate examples/practices/contract.json --root .
python3 scripts/contracts.py plan-input examples/practices/contract.json --root . > .build/practices/contract-plan.json
python3 scripts/workflow.py plan .build/practices/contract-plan.json --workers 2
python3 scripts/contracts.py brief examples/practices/contract.json --root . --task date-validation
python3 scripts/pilot.py summarize examples/practices/pilot-complete.synthetic.json --compare baseline team-2
python3 scripts/lessons.py select knowledge/lessons.json --root . --project ai-team --trigger routing
python3 scripts/checks.py --profile minimal
sh .githooks/pre-commit
```

The contract chain preserves spec acceptance IDs and verification descriptions in workflow task strings and detailed briefs. `workflow.py plan` remains a bounded proposal; a controller supplies truthful worktree IDs and completion state. Verification entries describe checks but neither `contracts.py` nor `workflow.py` executes them. The complete and incomplete pilot fixtures are synthetic; the incomplete fixture should fail comparison before stdout. Functional checks and examples are not a paired coding benchmark.

## Schemas and boundaries

- `skills-registry.json` declares active local `SKILL.md` entries and remote candidates. `scripts/skills.py audit REGISTRY [--previous SNAPSHOT]` hashes local bytes and registry metadata, reports advisory overlap/freshness findings, and compares a prior CLI inventory snapshot. It does not parse skill YAML, install skills, scan home directories, or verify remote revisions. Only a full 40/64-character hexadecimal revision is treated as a claimed pin; source freshness remains `not_checked`.
- Contracts use schema version 1 with a spec, acceptance IDs, verification descriptions, doc references, and tickets. Every acceptance criterion must map to a ticket; ticket dependencies must be acyclic. `--root .` permits repo-root glossary/ADR references while enforcing containment. Worktree IDs remain controller-supplied opaque labels.
- Pilot records are JSON arrays with one task/mode row, valid status, elapsed seconds, rework count, and nullable usage. `--compare` requires complete coverage for every task ID and selected mode. It does not certify matching inputs, models, base revisions, acceptance, or causal effects; controllers must keep those conditions comparable and review outcomes. Extra unselected modes remain in the ordinary aggregate output.
- `knowledge/lessons.json` starts empty. Approved entries require a `Codex Astra` or `Codex Sol` reviewer label and ISO date; these labels are not authenticated runtime evidence. Selection is exact-project and read-only, and local evidence paths are contained without opening their contents. Lessons must be reviewed before approval; tools never promote lessons or edit rules automatically.
- `checks.py` has fixed `minimal`, `standard`, and `strict` profiles. `--staged` reads staged Git blob objects, validates changed registry/lesson/contract JSON, and scans a limited set of high-confidence secret patterns. Protected and generated paths are skipped. Symlinks, submodules, binary blobs, and oversized blobs are skipped for general files with coverage counts; for the three required JSON artifacts, those conditions fail closed as invalid staged JSON. It is not exhaustive and is not a security assurance. Explicitly named JSON inputs and snapshots may live under ignored `.build/`; referenced skills, docs, and lesson evidence still reject generated/cache paths. Standard captures the full unittest result but emits only check status, exit code, and test count; strict reports only validated Git diff locations.

Upstream work is inspiration only; no upstream code is vendored: [Matt Pocock to-tickets](https://github.com/mattpocock/skills/blob/main/skills/engineering/to-tickets/SKILL.md), [Matt Pocock domain-modeling](https://github.com/mattpocock/skills/blob/main/skills/engineering/domain-modeling/SKILL.md), and [ECC skill-stocktake](https://github.com/affaan-m/ECC/blob/main/skills/skill-stocktake/SKILL.md), [eval-harness](https://github.com/affaan-m/ECC/blob/main/skills/eval-harness/SKILL.md), and [continuous-learning-v2](https://github.com/affaan-m/ECC/blob/main/skills/continuous-learning-v2/SKILL.md). Registry candidates remain unreviewed and unpinned until a controller reviews them.

## Optional local Git hook

The executable `.githooks/pre-commit` runs `python3 scripts/checks.py --profile minimal --staged`. It is opt-in and never changes Git configuration itself. First inspect the current value with `git config --get core.hooksPath`; if one is already configured, decide whether replacing it is appropriate before enabling this hook.

```sh
git config core.hooksPath .githooks
git config --get core.hooksPath
git config --unset core.hooksPath
```

The last command disables this repository hook only when `.githooks` is the configured value; restore any previous value you chose to replace. A clean hook run is a local accidental-secret and input-validity check, not acceptance of a change.
