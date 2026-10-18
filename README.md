# Personal AI Agent Team

Research and a proposed Orca team design using existing Codex/Claude subscriptions: one Sol/Opus Leader with scoped workers and on-demand skills.

Research date: **18 October 2026**. This repository contains design documents and prompt templates. It does not install tools, configure accounts, or launch agents.

## Documents

- [Full design in Thai](README.th.md): roles, model selection, parallel tasks, account boundaries, skills, and evaluation.
- [Leader policy draft](leader-policy.draft.md): a policy to adapt to your installed runtime.
- [Task templates](task-templates.md): briefs, worker assignments, results, and checkpoints.
- [Token tool comparison in Thai](token-tools-comparison.th.md): RTK, Headroom, Serena, Ponytail, and Caveman.
- [Windows Orca capability notes](orca-capabilities.md): observations from the original research machine, not a compatibility guarantee for macOS.

## Use on a Mac

Clone this repository using its GitHub HTTPS or SSH URL, then open the cloned folder in Orca. For a private repository, authenticate Git or GitHub CLI with an account that has access first. With GitHub CLI, use the repository's `gh repo clone OWNER/REPOSITORY` command.

Start with [the Thai design](README.th.md). Apply the Leader policy only after adapting it to the client's instruction-loading mechanism. Documents in this repository are not automatically active agent instructions.

Verify the Mac's installed Orca guide and launch options before applying Windows observations:

```sh
orca skills get orchestration
orca orchestration worker-start --help
```

Model access, authentication, installed tools, and account routing must be checked on each machine. Git does not transfer logged-in sessions or subscription credentials.

For later updates, run `git pull --ff-only` from the clone when your local work is ready to update.

## Repository scope

Keep credentials and machine-local state outside this repository. Review the actual tool versions and source links before installing anything. The suggested worker limits and budgets are starting points to evaluate, not enforced runtime settings.
