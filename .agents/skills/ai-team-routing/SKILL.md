---
name: ai-team-routing
description: Route an incoming development task to the smallest suitable set of tools and skills, with evidence of availability and a fallback.
---

# AI team routing

Use this as a controller decision aid for each incoming development task. It does not schedule or launch agents. The controller owns reasoning, planning, architecture, delegation, user communication, and final review. Only Codex Astra or Sol may act as controller. Only Codex Terra or Luna execute code, tests, mechanical refactors, or focused repository inspection. Executors stop and report when a business, architecture, or other judgment decision is needed. Gemini is limited to web search and recording controller-approved work-log facts; it does not implement or review.

Preserve the user's existing authorization and data boundary. Do not send company data to a personal account or external service without explicit authorization. Do not infer account routing, quota pooling, or billing cost from model names, executable presence, or API prices.

For the task, assess capability, risk, and authorized data first. Verify candidate availability from tools offered in this session, installed skills, an existing repository index, or the tool's help. Distinguish a skill/instruction, a plugin package, and an executable tool; distinguish presence from authentication, entitlement, and a successful run. Choose the smallest sufficient capability set and one primary tool per capability. Load only relevant skills and required references, including mandatory tool prerequisites. If an optional capability is absent, use the fallback below and continue when possible. Never claim a skill is active in a session that began before it was available.

Use Orca as this repository's orchestrator. Before supervised lifecycle work, load the Orca guide matching the installed runtime version and use its CLI/tools directly. Do not route tasks through Superset workflows, CLI, plugins, or skills. For browser or desktop work, choose available Orca tools that fit the task and authorization; when unavailable, use a suitable generic native fallback without introducing Superset.

For bounded task planning, deterministic receipt waiting, or usage evidence from explicitly supplied logs, use `scripts/workflow.py` as a local reader only. The controller supplies exact task identities and acceptance state; Orca alone dispatches and owns delivery review/release/ACK. The workflow CLI never launches workers, infers completion from tests, or reads implicit account/config data. See `workflow.md` for schemas and limits.

For repository-local skill inventory, traceable contract-to-ticket briefs, complete comparative pilot data, reviewed project lessons, and fixed checks, see [`practices.md`](../../../practices.md). These tools remain advisory: controllers own decisions and acceptance, and metadata labels do not prove runtime identity or authorization.

Default to Sol/Astra as controller with one Luna/Terra executor. Increase the cap only for ready, independent tasks with disjoint writable ownership and controller-supplied exact worktree IDs. The same executor owns implementation and tests; the lead reviews results, with independent review where project policy requires it. Give executors compact, approved briefs instead of the full conversation. This guidance does not enforce runtime model identity or launch workers automatically.

Record a compact routing receipt with: task capability and risk; chosen tool and relevant skill; availability evidence; reason and expected benefit; fallback. Reassess only when a blocker, scope change, or failure provides new evidence. Do not repeatedly re-plan without new evidence.

| Capability | Primary choice | Fallback and boundary |
|---|---|---|
| Known small edit | Native file edit | Inspect only the target and its direct context. |
| Repository exploration | Existing indexed CodeGraph or Graft, based on actual availability and index freshness | Targeted `rg` and file reads. |
| Semantic refactor | Serena when available | Identify exact callers/references, then make a bounded native edit. |
| Large logs or payloads | Filter at the source with the relevant parser/search | RTK may compact shell output; do not add another compression layer to the same data. |
| Web research | Gemini, under the model policy | If unavailable, report that current web verification was not performed; do not fabricate sources. |
| UI/browser work | One installed browser workflow suited to the task and provider | Use the available workflow's required guide; avoid running overlapping browser stacks. |
| Artifact creation | Matching installed artifact skill | Use the corresponding native format workflow if the skill is unavailable. |
| External service | Purpose-built available connector | Verify authorization and connection before accessing data. |

Use Superpowers for real feature, debugging, refactoring, or test-strategy decisions. Skip the heavyweight workflow for trivial edits. Honor mandatory skill and tool prerequisites. Avoid overlapping skill chains that repeat the same guidance.

Install a plugin only when a genuine capability gap blocks the task, and obtain explicit approval before installing it or connecting an account. Do not choose plugins from stars or popularity alone. Executable detection is not authorization to launch wrappers, agents, or external actions; inspect help and authorization first. Optional team wrappers are reusable dependencies, not templates to copy or hardcode with machine-specific paths. This repository does not implement automatic TeamAI synchronization or agent scheduling.

## Example-based defect coverage

Treat user examples and reproductions as evidence of a potentially wider defect class; treat them as the full scope only when the user explicitly narrows it. The controller names the suspected shared mechanism and bounded related surfaces. The worker inspects that mechanism, its callers, and relevant data variants; finds evidence-backed cases beyond the reported examples and relevant counterexamples or boundaries when present; then reports inspected and uninspected coverage with limitations. The controller presents proposed fixes with their impact and validation. Completion verifies the shared mechanism and relevant data coverage, not just the named examples. Claim exhaustive coverage only when evidence supports it, and never infer that similar outputs or words are interchangeable.
