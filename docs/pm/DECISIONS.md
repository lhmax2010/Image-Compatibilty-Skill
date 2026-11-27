# Decisions

All entries below were recorded on 2026-11-26.

| Decision | Effect |
| --- | --- |
| Technical PM handover to Claude | Claude reviews Codex commits and test evidence |
| v1.5.2 delivery scope | Static developer tool. Authorized Runtime remains optional and experimental |
| Minimal controller | WP-5 specifies run-summary.json and compat_run.py doctor/run. Legacy CLI semantics are retained |
| Temporary public GitHub repository | The owner will make it private after the work. Normal Git push and pull only. No GitHub Releases |
| Continuity copies | Push the reviewed main branch at the requested backup points |
| Local Git | Local commits on main are allowed |
| VD workstation | ClineSR runs VD-1 and VD-2 |
| SR SDK | Existing trusted ARMv7 SDKs may be used for fixture compilation if feasible |

## 2026-11-27

- The PM provisionally accepts the workflow controller, run summary, short Skill instructions and demo materials from pre-handover commit 6991426. Full review continues. WP-5 becomes a review and gap-closing package. Record any work started outside an assigned package in CODEX_STATE.md before committing it.
- Local tag v1.5.2 remains on 6991426 and must neither move nor be pushed. The next deliverable is v1.5.3. WP-2 source will identify its collector as 1.5.3-dev.
- Back up through ordinary Git pushes to main. GitHub Releases remain prohibited.
