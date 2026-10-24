# AI team workflow glossary

- **accepted**: a task outcome the controller has reviewed against its acceptance criteria and approved; passing tests alone is not acceptance.
- **worker_done**: an Orca lifecycle message reporting executor outcome and task/dispatch identity to the controller.
- **spec**: the approved problem, intended outcome, acceptance criteria, boundaries, and decisions for a change.
- **ticket**: a bounded, owned unit of implementation tied to spec acceptance criteria.
- **brief**: the executor-facing rendering of an approved ticket, including ownership, evidence, constraints, and escalation rules.
- **evidence**: a source or verification result that supports a claim; metadata labels do not authenticate identity, authorization, or runtime state.
