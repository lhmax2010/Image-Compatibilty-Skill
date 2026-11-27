# Codex Work Package WP-2
## VD readiness: repository-wide library tracking, requirement satisfiability, instrumentation confound detection

You are the implementation engineer for the Tizen Image Compatibility Skill. Claude is the technical PM and independently reviews your commits, tests and evidence. Communicate in English. Do not invent product requirements. If something here is ambiguous, or a demonstrably smaller and safer solution exists, implement the safe interpretation and disclose the deviation.

**Input files** (the owner placed them in `$DOWNLOADS`, i.e. `$DOWNLOADS`; copy them yourself and do not delete anything there):

| File in Downloads | Put it at |
|---|---|
| `WP-2_CODEX_PROMPT.md` (this file) | `docs/pm/work-packages/WP-2/PROMPT.md` |
| `CLINESR_VD-1_PROMPT.md` (revision 2) | **replace** `docs/pm/clinesr/VD-1_PROMPT.md` |

---

### 1. Task title

WP-2: Close repository-mode blind spots and the ASan confound before the real VD acceptance.
Register items: F-04, F-05, F-07, F-11, F-12, OPS-3. Housekeeping: WP-1 verification record, version naming, ClineSR prompt revision 2.

### 2. Background

The real VD comparison has these properties:
- It can only be done through RPM repository payloads, because EROFS extraction failed.
- It compares a GCC baseline with an **LLVM ASan** candidate.
- There are about 5,880 RPMs per side.

In repository mode, v1.5.2 still has three gaps, so it cannot yet support that comparison:
- It pairs ELF objects only inside the same package name.
- It never checks whether baseline consumers' needed libraries and versioned symbols exist in the candidate.
- It does not detect that the two sides were built with different instrumentation.

### 3. Starting commit

`ae4d269e9ff822f7479d51b800cc8b964910e2b3` on `main`. This is the WP-1 result. Verify that local `main` and `origin/main` both point to it before you change anything. If they do not, or if there is uncommitted work that is not yours, report and stop.

### 4. PM verification of WP-1 (record this; do not re-test)

The PM independently re-ran the following on `ae4d269` (x86-64 host, binutils 2.42, Python 3.13):

- **Hex-size fixtures.**
  - The 200,000→100-byte case: `bar@@V1` is INCOMPATIBLE, the size change is `DATA_SIZE_DECREASED`, and there is no `V1` finding.
  - The 100→150,000-byte case: `bar@@V1` is INCOMPATIBLE, the size change is `DATA_SIZE_INCREASED`, and the CLI exits 1.
- **FUNC→IFUNC:** UNKNOWN LOW `IFUNC_TRANSITION`.
- **libLLVM.so.20.1:** complete export inventory with 55,959 exports.
- **All-zero inputs:** exit 2 with an input error.
- **`compat_workflow.py run` on the hex-size fixture:** exit 1, `objective_completion=COMPLETE`, and `run-summary.json` is 5.3 KB.
- **Full suite:** 355 run, OK, 21 skipped (the host has no rpm or erofs tools).
- **Code review:** the changes for F-20, K-06 and K-09 were read and found consistent with the prompt.

**Set the status of these items to `Verified (PM, 2026-11-27, ae4d269)`:** F-01, F-02, F-03, F-20, K-01, K-03, K-06, K-09, OPS-1, OPS-2. Record two notes:
1. With `max_readelf_bytes`, `readelf` output is held in memory up to the cap (512 MiB by default). The VD-1 data will show whether that matters.
2. The bubblewrap EROFS integration test stayed BLOCKED (see §11 clarification).

### 5. Recorded PM decisions (add them to `docs/pm/DECISIONS.md`)

1. **Pre-handover commit `6991426`** ("release: harden Tizen compatibility production workflow"). It was created before the PM handover and is now on `main`. It contains the workflow controller (`compat_workflow.py`), `run_summary.py`, the 29-line SKILL.md and demo materials. The PM accepts the controller and run summary **provisionally**, which means WP-5 is no longer a "build a controller" task; it becomes a review-and-gap-closing task. The full PM review of `6991426` is ongoing. **Rule from now on:** any work started outside an assigned work package must be reported in `CODEX_STATE.md` before it is committed.
2. **Version naming.** The local tag `v1.5.2` points to `6991426`. It must never be moved, overwritten or pushed. The next deliverable is **v1.5.3**. In this package, set `VERSION` to `1.5.3-dev` so manifests from post-tag `main` cannot be confused with the tag. Update the version header in SKILL.md to match.
3. **Owner rules (unchanged):** no GitHub Releases; only `git push`/`git pull`; backups go to GitHub `main`.

### 6. Problem statement and approved design

#### 6.1 F-04 — repository-wide ELF pairing and library removal

Today `compare_repository` pairs objects only inside a `(name, arch)` package group. Unpaired baseline objects become `Repository ELF path availability` with status UNKNOWN and severity INFO. PM reproduction with complete inventories on both sides gave these results:
- a library removed from the candidate repository → INFO;
- a library moved to a renamed package and missing a symbol → INFO, and the symbol is never compared.

**Approved design.** After the existing package-local pairing:

1. Build a candidate-side index over all candidate runtime ELF objects, excluding `DEBUG_ONLY`. Index by `package_path` and by `(soname, class, machine, endianness)`.
2. For each unpaired baseline object, look for a unique candidate match:
   - (a) the same `package_path` with the same class and machine; otherwise
   - (b) the same SONAME with the same class, machine and endianness.

   A candidate object that is already paired cannot be reused.
3. When a match is found, record the pair with `match = CROSS_PACKAGE_PATH` or `CROSS_PACKAGE_SONAME`, keeping **both** package IDs. Run the normal `compare_elf` on it. Neither object may then also appear as an unpaired baseline or added candidate.
4. When there are several possible matches, report one finding with status UNKNOWN, severity MEDIUM and `reason_code=PROVIDER_AMBIGUOUS`. List the candidates.
5. When there is no match, the baseline object is a DSO with a SONAME, and **both** repository inventories are complete (all archives' metadata and extraction COMPLETE and every applicable export inventory complete), report status INCOMPATIBLE, severity HIGH and `reason_code=LIBRARY_REMOVED`, with scope `RPM_REPOSITORY_PAYLOAD`. If either inventory is incomplete, keep status UNKNOWN, raise the severity to MEDIUM, and set `reason_code=LIBRARY_NOT_FOUND_INCOMPLETE_INVENTORY`.
6. An executable with no match is reported as status UNKNOWN, severity LOW, `reason_code=EXECUTABLE_NOT_FOUND`. It is not a provider break.
7. The `objective_completion` rule in `run_summary.py` must keep treating unpaired or ambiguous objects as PARTIAL. A confirmed `LIBRARY_REMOVED` with complete inventories does **not** lower completion, because the objective was achieved.

#### 6.2 F-05 — available-set requirement satisfiability in repository mode

Add a closed-world check, labelled scope `AVAILABLE_SET`. It answers one question: can each baseline consumer's dynamic requirements be satisfied by *some* candidate repository object? It is not an installed-set or runtime proof, and the finding text must say so.

**Approved design**, as a new module (e.g. `scripts/compat/requirements.py`) reused by repository mode:

1. Consumers are baseline runtime ELF objects (DSOs and executables, excluding `DEBUG_ONLY`) with a complete import inventory and resolution metadata.
2. A candidate provider for SONAME `S` is any candidate runtime object with `soname == S` and the same class, machine and endianness as the consumer.
3. Requirement kinds and rules:
   - **DT_NEEDED `S`:** no provider exists → INCOMPATIBLE HIGH, `reason_code=NEEDED_SONAME_UNAVAILABLE`.
   - **verneed `(file S, version V)`:** providers exist but none defines version node `V` → INCOMPATIBLE HIGH, `reason_code=VERSION_NODE_UNAVAILABLE`.
   - **Versioned import `name@V` from file `S` (strong binding):** no provider of `S` exports `name@V` or `name@@V` → INCOMPATIBLE HIGH, `reason_code=VERSIONED_SYMBOL_UNAVAILABLE`.
   - **Weak versioned import:** the same failure is UNKNOWN LOW, `reason_code=WEAK_REFERENCE_UNSATISFIED`.
   - **Unversioned strong import `name`:** search the candidate providers of the consumer's DT_NEEDED closure. The closure is the transitive set of NEEDED SONAMEs resolved by SONAME in the candidate available set, with a hard depth limit of 32. The import is satisfied by any provider exporting `name` unversioned or with a default (`@@`) version. If none does, report UNKNOWN MEDIUM, `reason_code=UNVERSIONED_SYMBOL_NOT_IN_CLOSURE`. This is never INCOMPATIBLE, because preload, `dlopen` and interposition are possible.
   - **A provider object without any version definitions** satisfies a versioned reference by name alone. This is the LSB rule: the reference uses versioning, but the definer specifies none.
4. **Baseline control (mandatory).** Evaluate every requirement against the **baseline** available set first. If the baseline itself does not satisfy a requirement, report it only as UNKNOWN LOW, `reason_code=ALSO_UNSATISFIED_IN_BASELINE`. Never report it as INCOMPATIBLE. This prevents false positives from partial repositories and samples.
5. **Multiple candidate providers for one SONAME** with different contents. If all of them satisfy the requirement, it is satisfied. If some do and some do not, report UNKNOWN MEDIUM, `reason_code=PROVIDER_AMBIGUOUS`.
6. **Output volume.** Emit findings only for failed or unknown requirements, **one finding per (consumer, requirement)**. Never emit one finding per closure member or per root. Do not emit satisfied rows as findings. Count satisfied, failed and unknown requirements per kind in `results.repository.requirements` and in `run-summary.json` statistics. Each finding names the consumer object, its package ID and NEVRA, the SONAME, the version and the symbol. Cap the stored detail at 1,000 example rows per reason code; full rows go to a new `requirement-findings.csv`.
7. **Performance.** Build the export indexes once per side, as dicts keyed by `(soname, base_name, version)`. Each requirement must be an O(1) lookup, plus closure computation memoized per SONAME. Stay within the existing resource guard.

#### 6.3 F-07 — build-profile confound detection

The Clang ASan candidate pads exported globals: the PM measured 40→96 bytes and also saw `__odr_asan_gen_*` exports. Every data-size change then becomes a false INCOMPATIBLE.

**Approved design.**

1. **Per object**, record `instrumentation` as a sorted list derived from DT_NEEDED and imports:
   - `ASAN`: libasan, libclang_rt.asan or `__asan_` imports;
   - `HWASAN`: `__hwasan_`;
   - `UBSAN`: libubsan or `__ubsan_`;
   - `TSAN`: libtsan or `__tsan_`;
   - `COVERAGE`: `__gcov_`, `__llvm_gcov`, `__llvm_profile_` or `__sanitizer_cov`.
2. **Per side**, `build_profile = {kind: share of applicable runtime objects}`. A kind is *dominant* on a side if its share is at least 0.20.
3. **Run level.** If a kind is dominant on one side and has a share of at most 0.02 on the other, set `results.comparison_validity = CONFOUNDED` and record `confounders` with each kind and both shares. Put `comparison_validity` and `confounders` in `run-summary.json`. Add a first-line banner to `summary.md` and `index.html`: "Comparison confounded by instrumentation difference: … Size findings are downgraded." Otherwise use `comparison_validity = COMPARABLE`.
4. **Per pair.** When the two objects' instrumentation lists differ, OBJECT/TLS size findings become UNKNOWN MEDIUM, `reason_code=INSTRUMENTATION_MISMATCH`, and keep the original sizes as evidence. Added exports matching `__odr_asan*`, `___asan_gen*`, `__asan_*` or `__sancov*` become INFO with `reason_code=INSTRUMENTATION_SYMBOL`. Removals, type/kind changes and version changes keep their normal classification.
5. **Never** suppress or drop findings. Downgrades must be visible and counted in `run-summary.json`, as `instrumentation_downgrades` by reason.
6. Fix `QUICK_START.md` and `references/rpm_repository.md`. The example must not present a GCC vs LLVM-ASan comparison as a normal GCC→LLVM comparison; explain the confound.

#### 6.4 F-11 — separate debug files

Objects with `elf_runtime_role == DEBUG_ONLY` currently produce `dynamic export collection coverage` UNKNOWN HIGH even when identical. Make export comparison NOT_APPLICABLE for DEBUG_ONLY objects (one INFO finding per pair at most), and exclude them from export-coverage denominators. They remain available for DWARF/abidiff.

#### 6.5 F-12 — requirement-based symbol counting

In `symbol-differences.csv`, a removed GNU version (e.g. `v@@N1` → `v@@N2` only) is labelled `CHANGED/VERSION_CHANGED`, while the engine's finding correctly says the baseline identity `v@N1` is unavailable. Add a column `baseline_identity_satisfied` (true/false/unknown) to EXPORT rows, derived from the engine's lookup rule. Add `exports_baseline_unsatisfied` to the per-role counts in `results.repository.symbol_differences` and in `run-summary.json`. Keep the existing `change` labels for compatibility. Restate the v1.5.1 acceptance fixture counts with these semantics in `docs/pm/work-packages/WP-2/REPORT.md`.

#### 6.6 OPS-3 — flaky interruption test

Identify the test that failed once in a parallel run. The candidates are the interrupt and reaping tests in `tests/test_frozen_runtime.py` and the interruption test in `tests/test_runtime_release.py`.
1. Reproduce it with repeated runs under parallel load, for example 50 iterations with 4 concurrent copies.
2. Determine whether the cause is production logic, timing, test isolation or host load.
3. Fix the root cause.

No retries, no longer sleeps used only as masking, and no weakened assertions. If you cannot reproduce it after 200 iterations, report that with the exact procedure and leave the test unchanged.

### 7. In scope

§4–§6, the tests in §13–§15, documentation updates (`references/rpm_repository.md`, `references/severity_rules.md`, `references/workflow.md` for the new summary fields, `QUICK_START.md`), and the PM files.

### 8. Out of scope

Linking finding volume (F-06; that is WP-3), EROFS sandbox changes, runtime/SDB, pyelftools, the HTML redesign, finding-ID stability, waivers, and reverse-direction mode. Do not change rootfs-mode classification, except for F-11 where it shares code. List any new issues instead of fixing them.

### 9. Relevant files

- `scripts/compat/repository.py`
- new `scripts/compat/requirements.py` and `scripts/compat/profile.py` (names flexible)
- `scripts/compat/compare.py` (size downgrade hook, DEBUG_ONLY), `scripts/compat/elf.py` (instrumentation fields)
- `scripts/compat/run_summary.py`, `scripts/compat/report.py` (banner), `scripts/compat/coverage.py` (DEBUG_ONLY denominators)
- `VERSION`, `SKILL.md` (version line only)
- `tests/`, `references/`, `QUICK_START.md`, `docs/pm/`

### 10. Steps

**Step 0 — State check and start backup.**
1. Verify the commit (§3).
2. Copy the input files.
3. Record §4 and §5 in `ISSUE_REGISTER.md`, `DECISIONS.md` and `PM_STATE.md`.
4. Commit and make the verified local backup (same procedure as WP-1).
5. **Push `main` immediately**, so ClineSR can pull revision 2 of the VD-1 prompt.

**Step 1 — Version naming** (§5.2).
**Step 2 — F-04** (§6.1).
**Step 3 — F-05** (§6.2).
**Step 4 — F-07** (§6.3).
**Step 5 — F-11 and F-12** (§6.4, §6.5).
**Step 6 — OPS-3** (§6.6).

**Step 7 — Report, PM files, final backup and push.**
1. Set the items' status to `Implemented, awaiting PM review`.
2. Write `docs/pm/work-packages/WP-2/REPORT.md`.
3. Commit, make the verified backup and push `main`.
4. Update `CODEX_STATE.md` before and after any command expected to run longer than 30 minutes.

### 11. Security and side-effect constraints

Never execute analyzed ELF files. No sudo, no host mounts, and no network beyond GitHub push/pull. All writes stay inside the workspace, except reading Downloads. Do not modify historical evidence. Do not change visibility, remotes, branches or tags. **No GitHub Releases.**

**Clarification of the WP-1 "no mounts" rule:** it forbids mounting or remounting *host* filesystems. Unprivileged bubblewrap or user-namespace bind mounts inside a test sandbox are allowed. If `fsck.erofs` and `mkfs.erofs` exist on the host, run the existing EROFS integration test and report the result. If they do not exist, report BLOCKED and name the missing tool.

### 12. Backward compatibility

- New fields (`reason_code` values, `comparison_validity`, `confounders`, `instrumentation`, `requirements`, the new CSV and its columns) are additive.
- Existing CSV column order is unchanged; new columns are appended.
- Former INFO path-availability findings become INCOMPATIBLE or UNKNOWN with reason codes. List these classification changes in the report.
- Exit codes are unchanged. `LIBRARY_REMOVED` and failed requirements are INCOMPATIBLE HIGH, so with the default `fail_on: HIGH` they produce exit 1, which is the intended behavior.

### 13. Required positive tests (with independently written expected results)

Build real ELF fixtures for x86-64. Also build ARMv7l fixtures with the SR SDK if they work as in WP-1. Package them with `rpmbuild` where the test needs repository mode.

- **T-05 Library removed:** package `foo` keeps its name, but `libbar.so.1` is gone and no other package provides it; both inventories are complete. Expected: INCOMPATIBLE HIGH `LIBRARY_REMOVED`. The same scenario with one damaged candidate RPM gives UNKNOWN MEDIUM `LIBRARY_NOT_FOUND_INCOMPLETE_INVENTORY`.
- **T-06 Package split:** `baz` → `baz-libs`, and `libbaz.so.1` loses symbol `b`. Expected: paired as `CROSS_PACKAGE_SONAME`, `b` is INCOMPATIBLE, and neither object is reported as unpaired or added.
- **T-06b Ambiguous provider:** two candidate packages provide `libq.so.1` with different contents. Expected: UNKNOWN MEDIUM `PROVIDER_AMBIGUOUS`.
- **T-07 Requirement satisfiability.** The baseline consumer `app` has DT_NEEDED `libx.so.1` and imports `f@X_1`, `g@X_1` and an unversioned `h`. Candidate cases:
  - (i) `libx.so.1` exports `f@@X_2` only → `f` and `g` are `VERSIONED_SYMBOL_UNAVAILABLE`, and `VERSION_NODE_UNAVAILABLE` for `X_1`;
  - (ii) `libx.so.1` is missing → `NEEDED_SONAME_UNAVAILABLE`;
  - (iii) `h` is missing from the closure → UNKNOWN `UNVERSIONED_SYMBOL_NOT_IN_CLOSURE`;
  - (iv) the baseline repository itself lacks `libx.so.1` → only UNKNOWN LOW `ALSO_UNSATISFIED_IN_BASELINE`;
  - (v) a fully satisfied consumer → zero findings, and the satisfied count is greater than 0.
- **T-08 Confound.** Two DSO builds of the same source: GCC plain (baseline) and Clang `-fsanitize=address` (candidate), plus a second plain control pair.
  - Expected for the ASan pair: `comparison_validity=CONFOUNDED`, the data-size finding is UNKNOWN MEDIUM `INSTRUMENTATION_MISMATCH`, `__odr_asan*` additions are INFO, and a deliberately removed function is still INCOMPATIBLE.
  - Expected for the control pair: `COMPARABLE`, and the size change is still INCOMPATIBLE.
- **T-12 Debug files:** identical `--only-keep-debug` pairs produce no HIGH findings and are excluded from the export-coverage denominator.
- **T-13 Counting:** the v1.5.1 acceptance fixture reports `exports_baseline_unsatisfied = 2` (`removed_symbol` and `version_switch@NEXT_1`). If your independent analysis of the fixture gives a different number, explain why.

### 14. Required negative tests

- Mismatched class or machine is never paired across packages; for example, an armv7l library must not pair with an aarch64 library that has the same SONAME.
- A candidate object already paired locally is not reused for a cross-package match.
- A closure cycle (A needs B, B needs A) terminates and does not crash.
- Instrumentation on one object only, with a COMPARABLE run, still downgrades only that pair.
- A requirement check on a consumer with an incomplete import inventory yields one UNKNOWN finding (`CONSUMER_INVENTORY_INCOMPLETE`), not per-symbol findings.

### 15. Required real integration tests and measurements

- Run `compat_workflow.py run` (objective `EXPORT_SYMBOLS`, `rpm_mode: payload`) end to end on the T-05/T-06/T-07 RPM fixtures. Report the exit code and all `run-summary.json` status fields.
- **Scale check:** generate about 1,000 small RPMs per side by script (about 3,000 ELF objects and about 300k imports). Report wall time, peak RSS, the number of requirement findings, and the report size. Do not commit the generated RPMs.

A test that cannot run because a tool is missing is reported as **BLOCKED with the missing tool**, never as PASS. New tests honour `COMPAT_RELEASE_CI=1`.

### 16. Acceptance criteria

All of the following:
- T-05 to T-08, T-12, T-13 and the negative tests pass (any BLOCKED items listed).
- The full existing suite passes with no new skips.
- The OPS-3 root cause is fixed, or a non-reproduction is documented as described in §6.6.
- The scale check completes and its numbers are recorded.
- `VERSION` is `1.5.3-dev`.
- The PM files are updated, two verified backups exist, `main` is pushed, and no tags or Releases were created.

### 17. Required deliverables

- Commit SHAs (pushed).
- Changed-file list.
- Test commands and outputs.
- Scale-check table.
- Classification changes compared with `ae4d269`.
- OPS-3 analysis.
- `docs/pm/work-packages/WP-2/REPORT.md`.
- Backup verification outputs.
- Deviations from this prompt.
- Newly noticed issues.

### 18. Git and publication rules

`main` only. No branches, no PRs, no force-push, no history rewrite. No tag creation, movement or push. **No GitHub Releases.** Stage exact paths only. Use normal `git push origin main` at Step 0 and Step 7.

### 19. Final report format

1. Step 0 state.
2. Changes per register item, with SHAs.
3. Deviations.
4. Test table (ID, environment, command, PASS/FAIL/BLOCKED).
5. Classification changes.
6. Scale check.
7. OPS-3 result.
8. Backup and push evidence.
9. Open risks and new issues.
10. Recommended next step (one paragraph).
