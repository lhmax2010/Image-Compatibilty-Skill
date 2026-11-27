# WP-2 implementation report

WP-2 is implemented and awaiting independent PM review. The source reports 1.5.3-dev. The tests are synthetic ELF/RPM acceptance and prior fixture replay. The actual VD runs remain assigned to ClineSR.

## 1. Step 0 state

```text
$ git status --short --branch
## main...origin/main
$ git rev-parse HEAD origin/main
ae4d269e9ff822f7479d51b800cc8b964910e2b3
ae4d269e9ff822f7479d51b800cc8b964910e2b3
```

The worktree was clean and the origin value was confirmed after fetch. The owner-supplied VD-1 prompt replaced the workspace copy and `cmp` passed. Both copies were byte-identical already. The ten WP-1 items and the PM's evidence and decisions were recorded without rerunning the PM's verification in Step 0. The startup snapshot was checked and `main` was pushed to ce40949 before source edits.

## 2. Changes per register item

| Item | Change | Commit |
| --- | --- | --- |
| WP-1 verification and VD handover | Recorded PM decisions, copied prompts and pushed startup checkpoint | ce4094977784b81c3d73312375b956d8e67c843e |
| Version | VERSION and SKILL.md header are 1.5.3-dev | eba25bc7938c380ad68596e311bb081c00a8caf6 |
| F-04 | Preserve package-local matches, then reconcile uniquely matched cross-package path/SONAME pairs. Carry both package IDs and apply completeness to removals | Same code commit |
| F-05 | Indexed baseline-controlled AVAILABLE_SET obligations, provider ambiguity, bounded examples and full CSV | Same code commit |
| F-07 | Observed instrumentation lists and shares, comparison validity banner, per-pair data-size downgrade and instrumentation export details | Same code commit |
| F-11 | Split debug exports NOT_APPLICABLE and excluded from applicable export coverage | Same code commit |
| F-12 | Keep comparison labels and append baseline lookup satisfaction. Count confirmed unsatisfied identities | Same code commit |
| OPS-3 | Record the approved stress non-reproduction. Runtime code and tests retained | This report commit |

### Changed files

```text
.agents/skills/tizen-image-compatibility/SKILL.md
.agents/skills/tizen-image-compatibility/VERSION
.agents/skills/tizen-image-compatibility/references/QUICK_START.md
.agents/skills/tizen-image-compatibility/references/rpm_repository.md
.agents/skills/tizen-image-compatibility/references/severity_rules.md
.agents/skills/tizen-image-compatibility/references/workflow.md
.agents/skills/tizen-image-compatibility/scripts/compat/compare.py
.agents/skills/tizen-image-compatibility/scripts/compat/coverage.py
.agents/skills/tizen-image-compatibility/scripts/compat/elf.py
.agents/skills/tizen-image-compatibility/scripts/compat/profile.py
.agents/skills/tizen-image-compatibility/scripts/compat/report.py
.agents/skills/tizen-image-compatibility/scripts/compat/repository.py
.agents/skills/tizen-image-compatibility/scripts/compat/repository_pairing.py
.agents/skills/tizen-image-compatibility/scripts/compat/requirements.py
.agents/skills/tizen-image-compatibility/scripts/compat/run_summary.py
.agents/skills/tizen-image-compatibility/scripts/tizen_compat.py
.agents/skills/tizen-image-compatibility/tests/test_rpm_payload.py
.agents/skills/tizen-image-compatibility/tests/test_wp2.py
.agents/skills/tizen-image-compatibility/tests/wp2_scale.py
QUICK_START.md
docs/pm/CODEX_STATE.md
docs/pm/DECISIONS.md
docs/pm/ISSUE_REGISTER.md
docs/pm/PM_STATE.md
docs/pm/work-packages/WP-2/PROMPT.md
docs/pm/work-packages/WP-2/REPORT.md
```

## 3. Deviations and conservative boundaries

- The committed WP-2 prompt replaces the owner-specific Downloads path with `$DOWNLOADS`. The owner-provided VD-1 file was copied byte for byte.
- Cross-package pairing also checks for two baseline objects claiming one candidate. A class or machine mismatch, conflicting path evidence or an already-used candidate cannot prove a new pair. The existing package-local choice stays authoritative.
- Closure results are memoized by ABI and initial required SONAME set. Missing version-node providers get an UNKNOWN VERSION_PROVIDER_UNAVAILABLE rather than a claim about a node's contents. An incomplete candidate inventory cannot prove absence. Provider compatibility here is available-set evidence only.
- Full requirement failure rows are emitted when CSV reports are enabled. Regular JSON/HTML Findings retain at most 1,000 examples per reason; the requirement counters always contain the full result.
- The mount-dependent synthetic EROFS case was allowed and passed. The real filesystem test is BLOCKED by missing mkfs.erofs and fsck.erofs. No host mounts, sudo, target ELF execution or software installation occurred.

## 4. Test results

The fixture tests use host GCC/binutils, RPM tools, the local SR Clang and ARMv7 wrappers used in WP-1, and Python 3.12.3. The commands below ran with `COMPAT_RELEASE_CI=1`, the four `WP1_*` fixture executable paths, and a workspace-local TMPDIR. The full suite used Bubblewrap with a private tmpfs and a network namespace. For the historical differential run, `WP2_BASELINE_CLI` pointed to a local extraction of ae4d269 and `WP2_ACCEPTANCE_OUTPUT` recorded both results.

```bash
python3 -B -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -p test_wp2.py -v
python3 -B -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v
python3 -B .agents/skills/tizen-image-compatibility/tests/wp2_scale.py "$WORK/scale-final"
git diff --check
```

| ID | Environment and case | Result |
| --- | --- | --- |
| T-05 | Real x86-64 RPMs, intact and damaged inventories | PASS. Known SONAME removal INCOMPATIBLE HIGH; damaged inventory UNKNOWN MEDIUM |
| T-06 | Real x86-64 and SR ARMv7 RPMs | PASS. Cross-package SONAME and path match; actual export removal retained |
| T-06b | Two actual different x86-64 libraries sharing SONAME | PASS. UNKNOWN MEDIUM PROVIDER_AMBIGUOUS, objective PARTIAL |
| T-07 | Linked f/g versioned and h unversioned imports, real RPMs | PASS. All five required cases, baseline control and exact CSV reconciliation |
| T-08 | GCC plain, actual Clang ASan and plain control | PASS. ASan data size UNKNOWN, instrument export INFO, actual removal still INCOMPATIBLE; plain size change remains INCOMPATIBLE |
| T-12 | GNU objcopy split debug ELF RPM | PASS. Exports NOT_APPLICABLE and exempt from applicable coverage |
| T-13 | Actual archived v1.5.1 synthetic repository and regression fixture | PASS. Exactly two unsatisfied baseline export identities |
| Negative | Mismatched ABI, consumed candidate, dependency cycle, scoped ASan change, incomplete consumer, weak reference | PASS |
| Focused | Release fixture flags enabled | PASS. Ran 10 tests in 9.472s, OK |
| Full regression | Existing suite plus WP-2 | PASS. Ran 365 tests in 42.340s, OK (skipped=6). 359 passed, no new skips |
| Standard EROFS real-image test | Existing integration | BLOCKED. Missing mkfs.erofs and fsck.erofs |

### Workflow status reconciliation

All rows use objective EXPORT_SYMBOLS, source evidence COLLECTED, actual input scope RPM_REPOSITORY_PAYLOAD and comparison validity COMPARABLE. Status columns are values read from run-summary.json. The coverage column describes the broader coverage model independently of export objective completion.

| Scenario | Exit | Objective | Execution | Compatibility | Coverage | CI gate |
| --- | ---: | --- | --- | --- | --- | --- |
| T-05 complete | 1 | COMPLETE | COMPLETE | INCOMPATIBLE | NOT_EXECUTED | FAIL |
| T-05 damaged | 3 | PARTIAL | PARTIAL | UNKNOWN | NOT_EXECUTED | PASS |
| T-06 SONAME, path and SR ARMv7 | 1 | COMPLETE | COMPLETE | INCOMPATIBLE | PARTIAL | FAIL |
| T-06b competing providers | 3 | PARTIAL | COMPLETE | UNKNOWN | NOT_EXECUTED | PASS |
| T-07 version, needed, unversioned | 1 | COMPLETE | COMPLETE | INCOMPATIBLE | PARTIAL | FAIL |
| T-07 baseline unsatisfied, all satisfied | 0 | COMPLETE | COMPLETE | UNKNOWN | PARTIAL | PASS |

The unversioned case's exit 1 also reflects a confirmed removal in a paired provider. The unversioned consumer requirement itself is UNKNOWN. The fully satisfied available-set case produces zero requirement findings. The overall repository result still reflects limits on installed loader evidence.

## 5. Changes compared with ae4d269

The old CLI and current workflow observed the same synthetic RPM bytes in the differential tests.

| Scenario | ae4d269 | WP-2 |
| --- | --- | --- |
| SONAME removed, complete inputs | UNKNOWN INFO, exit 0 | LIBRARY_REMOVED INCOMPATIBLE HIGH, exit 1 |
| SONAME removed, damaged RPM input | UNKNOWN INFO, old CLI exit 0 | LIBRARY_NOT_FOUND_INCOMPLETE_INVENTORY UNKNOWN MEDIUM, workflow exit 3 for unfinished objective |
| Renamed/split package | UNKNOWN INFO, exit 0 | Cross-package pair and confirmed b removal, exit 1 |
| Availability of DT_NEEDED or qualified imports | Available-set check absent | Baseline-controlled classifications and explicit counts |
| ASan-padded data | DATA_SIZE_INCREASED INCOMPATIBLE HIGH | INSTRUMENTATION_MISMATCH UNKNOWN MEDIUM, original sizes retained. Deliberately missing export remains INCOMPATIBLE |
| Actual split debug pair | Export collection UNKNOWN HIGH | Export applicability NOT_APPLICABLE INFO |
| Version changed in detail | CHANGED | CHANGED plus baseline_identity_satisfied=false when the old version no longer exists |

T-13 used the existing archived synthetic RPM inputs. Each side still has 18 raw export observations, 9/10 unique export base names and 36/36 per-object lookup identities. Of the 25 difference rows, 19 are EXPORT and six IMPORT, with 16 MATCHED, five ADDED, three CHANGED and one MISSING. The two false baseline export lookups are removed_symbol@@NEXT_1 and version_switch@@NEXT_1, which correspond to qualified imports of NEXT_1.

## 6. Scale check

| Measurement | Final observed value |
| --- | --- |
| RPMs, baseline / candidate | 1,001 / 1,001 |
| ELF objects, baseline / candidate | 1,501 / 1,501 |
| Imports, baseline / candidate | 150,000 / 150,000 |
| Build and analysis wall time | 128.59 s |
| Analysis wall time | 83.36 s |
| Peak RSS | 401,972 KiB |
| Full report disk bytes | 390,790,886 |
| Requirement rows | 1,500 VERSIONED_SYMBOL_UNAVAILABLE rows in CSV. 1,000 examples in JSON |
| Satisfied requirements | 1,500 DT_NEEDED, 1,500 version nodes, 148,500 versioned imports |
| Objective and exit | COMPLETE, exit 1 for the deliberately missing versioned symbol |

Each build used bulk rpmbuild subpackages and real ELF consumers. Generated RPMs and the report remain in workspace-local evidence.

## 7. OPS-3

The original v1.5.1 log identifies test_cleanup_interrupt_stops_matrix_and_keeps_evidence. It failed its assertion for partial cleanup output. Earlier work addressed the SIGINT race around the read/write evidence boundary, with a dedicated regression.

WP-2 ran 200 independent iterations across four workers. Each iteration launched a new unittest process, with a fresh test temporary directory in the workspace-local namespace, and ran these four exact cases:

```text
test_frozen_runtime.FrozenRuntimeTests.test_timeout_and_interrupt_preserve_evidence_and_reap_group
test_frozen_runtime.FrozenRuntimeTests.test_cleanup_interrupt_stops_matrix_and_keeps_evidence
test_frozen_runtime.BoundedProcessTests.test_interrupt_between_pipe_read_and_evidence_write_preserves_output
test_runtime_release.ExpectedRuntimeTests.test_missing_repetition_optional_skip_and_interruption
```

The driver submitted `range(200)` once to a `ThreadPoolExecutor(max_workers=4)`. Each call ran `python3 -m unittest -v <the four IDs>` with a 90-second harness timeout and wrote one result log. Exact aggregate output:

```text
iterations 200 cases per iteration 4 failures [] seconds 125.46
```

The failure did not reproduce. Test assertions, sleeps and production Runtime code remain unchanged in WP-2.

## 8. Backup and push evidence

The startup backup was `.local-backups/pm/20261127T021859Z/` and included main at ce40949. Both snapshots preserve the local tags in the bundle and transfer only main to GitHub. The final delivery message records the final commit and final backup directory, which becomes LATEST. Each checkpoint verified:

```text
BUNDLE_VERIFY.log: OK
main-and-tags.bundle: OK
pm-docs.tar: OK
worktree.patch: OK
staged.patch: OK
untracked-inputs.tar: OK
The bundle records a complete history.
```

## 9. Open risks and new issues

- Real VD repositories have more packages and heterogeneous ELF payloads. The synthetic timings are workload-specific. Actual product comparisons and installation/runtime effects remain to be verified.
- The report contains complete CSV requirement rows with CSV enabled. Its ordinary Findings aggregate covers the retained examples. Use the separate available-set counters for full failure volume.
- Existing legacy collector mode and future package work remain in scope for later review. The register lists F-21 under WP-2 and F-06 under WP-4 while this prompt limits WP-2 to its named items and refers to F-06 as WP-3. Their existing code and statuses are preserved pending PM scheduling reconciliation.
- Standard EROFS decoding remains blocked by unavailable tools. The private namespace safety fixture passed.

## 10. Recommended next step

Claude should review the code commit, the real RPM fixture outcomes and the baseline-control classifications, then have ClineSR pull the verified main checkpoint and execute VD-1 on the intended workstation. Use that measurement to validate resource budgets and observed instrumentation shares before any actual VD compatibility decision.

## WP-2 independent evidence

The PM verified `323e0e1` on x86-64 with binutils 2.42 and Python 3.13 (365 run, 28 skipped). The tests confirmed repository library loss and relocation with a missing symbol, AVAILABLE_SET emitted two VERSIONED_SYMBOL_UNAVAILABLE findings and VERSION_NODE_UNAVAILABLE. Missing libc on both sides was only ALSO_UNSATISFIED_IN_BASELINE (UNKNOWN LOW). Plain GCC versus Clang ASan produced CONFOUNDED, an UNKNOWN MEDIUM size observation and an INCOMPATIBLE removed function. Rootfs instrumentation and repository requirement volume remain WP-3 items.

ClineSR independently ran the WP-2 checks on a second Linux host. Python 3.11.18 ran 365 tests (354 passed, 10 skipped, one error) because Bubblewrap 0.6.1 rejects the EROFS `--size` option. Python 3.10 had 15 errors traced to `hashlib.file_digest` in ARM smoke admission. With 1,001 RPMs and 1,501 ELF objects per side, wall time was 148.21 s, peak RSS 504 MB and report size 390.8 MB. OPS-3 passed 200/200 iterations. The two local ClineSR documentation commits were left on that workstation.
