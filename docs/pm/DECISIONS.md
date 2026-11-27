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

## WP-2 independent evidence

The PM verified `323e0e1` on x86-64 with binutils 2.42 and Python 3.13 (365 run, 28 skipped). The tests confirmed repository library loss and relocation with a missing symbol, AVAILABLE_SET emitted two VERSIONED_SYMBOL_UNAVAILABLE findings and VERSION_NODE_UNAVAILABLE. Missing libc on both sides was only ALSO_UNSATISFIED_IN_BASELINE (UNKNOWN LOW). Plain GCC versus Clang ASan produced CONFOUNDED, an UNKNOWN MEDIUM size observation and an INCOMPATIBLE removed function. Rootfs instrumentation and repository requirement volume remain WP-3 items.

ClineSR independently ran the WP-2 checks on a second Linux host. Python 3.11.18 ran 365 tests (354 passed, 10 skipped, one error) because Bubblewrap 0.6.1 rejects the EROFS `--size` option. Python 3.10 had 15 errors traced to `hashlib.file_digest` in ARM smoke admission. With 1,001 RPMs and 1,501 ELF objects per side, wall time was 148.21 s, peak RSS 504 MB and report size 390.8 MB. OPS-3 passed 200/200 iterations. The two local ClineSR documentation commits were left on that workstation.

## WP-3 Addendum A acceptance

The PM reviewed and accepted `d9aa0803a3465f83b5d93cd2c15706c329b6cf4c`, including the delegated changes to VD-1 revision 4.2. The accepted script SHA256 is `ee9b0b6c109f67b9dd27bb70bce053b542364cc7a8f27017382be9a6cdb49a1a`. WP-3 starts from that documentation-only child of `323e0e1`.

## WP-3 acceptance and VD-1 measurement

The technical PM accepted WP-3 at `853cadc` and `0c40d40`. [Independent PM checks](work-packages/WP-3/PM_REVIEW.md)

ClineSR ran revision 4.2 on 150 common ARM ELF32 package names per side. Baseline GCC was 214 MB, candidate LLVM 191 MB. Both sides contained 243 ELF objects and ran static payload analysis.

| Measurement | v1.5.1 2d43c58 | WP-2 323e0e1 |
| --- | --- | --- |
| Wall time and peak RSS | 54.4 s / 360 MB | 54.3 s / 380 MB |
| Report size | 467.8 MB | 535.6 MB |
| ELF complete, baseline / candidate | 242 / 242 | 243 / 243 |
| Export inventories complete | 228 / 240 | 230 / 242 |
| Unknown exports without reason | 14 / 2 | 13 / 1 |
| Findings / INCOMPATIBLE / UNKNOWN | 13,605 / 4,849 / 7,739 | 14,657 / 4,924 / 8,609 |
| SYMBOL_BINDING_CHANGED, UNKNOWN HIGH | — | 6,939 |
| EXPORT MISSING / CHANGED / ADDED | — | 4,828 / 29,218 / 826 |
| Candidate failures among baseline-satisfied requirements | — | 0 / 14,668 |
| Baseline-unsatisfied requirements | — | 26,198 |
| Comparison validity and ASan counts | — | COMPARABLE, 0 / 0 |

1. **D-WP3b-1** keeps F-10 after the release candidate, subject to the full-repository projection from VD-1 detail.
2. **D-WP3b-2** prioritizes report size. VD data reached about 3.6 MB per sampled RPM. SR reports reached 1.24 GB without a profile and 5.5 GB with partial profiles, with 6.5 GB peak RSS.
3. **D-WP3b-3** freezes removal and binding statuses and severities for WP-3b. All 4,924 confirmed findings lacked a reason code in VD-1, nearly all were removed exports, and none of 14,668 baseline-satisfied sampled requirements broke. WP-4 policy review depends on the ClineSR detail breakdown.
4. **D-WP3b-4** records COMPARABLE and zero observed ASan objects. The two import totals were 40,616 and 40,427. VD-2 owns real ASan positive validation.

## WP-3b acceptance and WP-4 decisions (2026-11-27)

The PM accepted WP-3b at `2633672`, including all 381 tests on the PM host, the published kit revision 5 privacy changes and end-to-end retest, zero missing reason codes and the removal context. The 10,000 Linking target conflicted with retaining individual DT_NEEDED checks. PERF-LINK is P2.

VD-1b measured 324.9 MB at WP-3b on 150 ARM packages per side. The PM projects about 40 minutes and 15.5 GB for 5,693 RPMs per side (about 10.2 GB of inputs each), making RPT-SIZE-3 a VD-2 blocker. The owner confirmed the candidate QuickBuild name contains ASAN but the build uses no ASan. VD-ASAN closes with fixture-only detection evidence.

D-POL-WEAK sends qualifying unreferenced weak C++ removals to UNKNOWN LOW owner review. D-POL-BINDING treats defined GLOBAL and WEAK exports as equivalent under default glibc lookup, with an exception for LD_DYNAMIC_WEAK. UNIQUE to WEAK retains the GNU unique loss risk. [Full VD-1b counts and PM evidence](work-packages/WP-3b/PM_REVIEW.md)

## WP-4 recorded outcomes

The RC implementation at `8b948dd0fa98bf74fbae6dbda04a922b8696d1d5` passed
391 tests on this host with six existing skips. The scale report reached
39.76% of its WP-3b size. The SR run reached 82,992 Linking findings and
59.31% of the original report size. Both SR targets remain open. The
SR output contains 10,011 owner-review rows under D-POL-WEAK. Two other
previously reported export removals are versioned copy relocations.
[WP-4 verification and unresolved gates](work-packages/WP-4/REPORT.md)
