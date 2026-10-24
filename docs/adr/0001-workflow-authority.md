# ADR 0001: Keep workflow authority with the controller and Orca

- Status: accepted
- Decision: local planning and evidence tools validate inputs and produce bounded proposals; the controller owns architecture, acceptance, task state, and review, while Orca owns dispatch and lifecycle delivery/acknowledgement.
- Lessons: project lessons remain proposals until a controller records an approved reviewer and date; selection is exact-project and read-only.
- Consequences: plan output is not dispatch, tests do not imply acceptance, and lesson or worktree labels are supplied evidence rather than authenticated runtime facts.
