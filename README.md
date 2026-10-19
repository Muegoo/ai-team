# Personal AI Agent Team

Research and a proposed AI team design, now accompanied by active repository routing instructions and a small pilot measurement CLI.

Research date: **18 October 2026**. The repository does not install tools, configure accounts, or launch agents. Active routing rules are in [AGENTS.md](AGENTS.md) and [the `ai-team-routing` skill](.agents/skills/ai-team-routing/SKILL.md); older research remains background material.

## Documents

- [Full design in Thai](README.th.md): roles, model selection, parallel tasks, account boundaries, skills, and evaluation.
- [Leader policy draft](leader-policy.draft.md): a policy to adapt to your installed runtime.
- [Task templates](task-templates.md): briefs, worker assignments, results, and checkpoints.
- [Pilot protocol](task-templates.md#controlled-pilot): paired-task procedure and `scripts/pilot.py` measurement schema.
- [Tool preflight and summary CLI](scripts/pilot.py): executable presence check and result aggregation; it does not access accounts or providers.
- [Token tool comparison in Thai](token-tools-comparison.th.md): RTK, Headroom, Serena, Ponytail, and Caveman.
- [Windows Orca capability notes](orca-capabilities.md): observations from the original research machine, not a compatibility guarantee for macOS.

## Fresh clone setup

1. Clone this repository and open the clone in Orca on branch `ai/docs/setup-benchmark`. Start a fresh agent session in that clone so it discovers this repository's [AGENTS.md](AGENTS.md) and routing skill. Follow [AGENTS.md](AGENTS.md); do not assume a global skill installation or company team wrappers.
2. Use an authorized installed Orca runtime, Codex Astra or Sol as controller, and Codex Terra or Luna as executor. Check the installed runtime's guide before lifecycle work. Do not install tools or edit global configuration as part of setup.
3. For the local scripts, require Python 3.10 or newer. They use only the Python standard library; no pip or npm install is needed. Run `python3 --version`, `python3 scripts/pilot.py preflight`, and `python3 -m unittest discover -s tests -p 'test_*.py'`. Prefix commands with `rtk` when it is already available; RTK itself is optional and is not a bootstrap requirement.
4. Treat local setup as ready when the Python CLI runs and its tests pass. Preflight reports executable presence only; optional tools being present does not establish authentication, entitlement, or routing. After local setup, run a separate small authorized task and complete the Orca lifecycle smoke test in the [pilot protocol](task-templates.md#lifecycle-smoke-test).

For a private repository, authenticate Git or GitHub CLI with an account that has access before cloning. For later updates, run `git pull --ff-only` from the clone when your local work is ready to update. Git does not transfer logged-in sessions or subscription credentials.

## Repository scope

Keep credentials and machine-local state outside this repository. Review the actual tool versions and source links before installing anything. The suggested worker limits and budgets are starting points to evaluate, not enforced runtime settings.
