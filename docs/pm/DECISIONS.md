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

## ClineSR owner rules

1. ClineSR is the Native Server AI. It may download from GitHub but must **never** push, commit or upload anything to GitHub. No prompt may ask it to.
2. ClineSR receives prompts only by the owner's copy-and-paste. Any script or file it needs must be committed to `main` by Codex; ClineSR then downloads it from GitHub.
3. ClineSR's workspace is `/home/liushanshan/Toolchain/Tools/Image-Compatibilty-Skill`, an existing clone of this repository. It must not create any file outside that workspace. Its scratch area is `<workspace>/.local-work/`.
4. `/home/linhao/Downloads` exists only on Codex's PC.
5. The owner relays ClineSR results to the PM.
6. ClineSR's clone currently holds two unpushed local documentation commits made by mistake. Nobody should push or replay them. ClineSR uses `git fetch` plus `git show`/`git archive` only, never `pull` or `merge`.

The published VD-1 revision 4.2 incorporates the delegated Addendum A fixes. It requires the canonical WORK path, creates private scratch files and fresh run logs, disables inherited Python bytecode output, and keeps raw selection and tool output local. The downloaded and published hashes are recorded below.

- Downloaded script SHA256 `b851c0937e044009da961257fe3c1a2b78668eeb3d370fb91fccad78a49f9068`
- Published script SHA256 `ee9b0b6c109f67b9dd27bb70bce053b542364cc7a8f27017382be9a6cdb49a1a`
