> **FOR CODEX ONLY.** If you are ClineSR or another agent, stop: this is not your task.

# Codex Work Package WP-3
## Finding volume control, rootfs confound detection, and portability fixes

You are the implementation engineer for the Tizen Image Compatibility Skill. Claude is the technical PM and independently reviews your commits, tests and evidence. Communicate in English. Do not invent product requirements. If something here is ambiguous, or a demonstrably smaller and safer solution exists, implement the safe interpretation and disclose the deviation.

**Input files** (in `$DOWNLOADS` = `/home/linhao/Downloads`; copy them yourself, do not delete anything there):

| File | Put it at |
|---|---|
| `WP-3_CODEX_PROMPT.md` (this file) | `docs/pm/work-packages/WP-3/PROMPT.md` |
| `WP-3_ADDENDUM_A.md` and `vd1_measure.sh` | Follow Addendum A **first**: it publishes the ClineSR measurement kit and supersedes any `CLINESR_VD-1_PROMPT.md` |

---

### 1. Task title

WP-3: Make reports usable at product scale and close the remaining small correctness and portability gaps before the release candidate.

Register items:
- F-06, F-15 (linking volume and its hidden dependency)
- REQ-AGG (repository requirement volume)
- F-07b (rootfs-mode instrumentation confound)
- F-09 (timeouts)
- F-21 (`rpm -qp --xml` cap)
- PORT-310 (Python 3.10)
- RPT-SIZE (report size measurement)
- PROC-1 (prompt routing)

### 2. Starting commit

`323e0e1b416494a94eac40182970612b6b96d987` on `main`. Verify that local `main` and `origin/main` both point to it and that the worktree is clean. If not, report and stop.

### 3. PM verification of WP-2 (record it; do not re-test)

The PM independently ran the following on `323e0e1` (x86-64, binutils 2.42, Python 3.13):

- **Repository library loss.** With complete inventories, a library removed from the candidate repository was INCOMPATIBLE HIGH. A library moved from `baz` to `baz-libs` that lost symbol `b` gave `b` as INCOMPATIBLE.
- **AVAILABLE_SET check.** A consumer importing `f@X_1`/`g@X_1` against a candidate `libx.so.1` that exports only `f@@X_2` gave `VERSIONED_SYMBOL_UNAVAILABLE` ×2 and `VERSION_NODE_UNAVAILABLE`. Requirements on a libc that was absent from both repositories became only `ALSO_UNSATISFIED_IN_BASELINE` (UNKNOWN LOW).
- **Repository-mode ASan confound.** GCC plain vs Clang ASan gave `comparison_validity=CONFOUNDED`. The size change became UNKNOWN MEDIUM `INSTRUMENTATION_MISMATCH`, and the removed function stayed INCOMPATIBLE.
- **Full suite:** 365 run, OK, 28 skipped (host without rpm or erofs tools).

Set these statuses:
- **F-04, F-05, F-07 (repository mode), F-11, F-12:** `Verified (PM, 2026-11-27, 323e0e1)`.
- **OPS-3:** `Closed — not reproduced in 800 executions (200 × 4 concurrent), assertions unchanged; reopen on recurrence`.

Two gaps found by the PM:
1. **F-07b.** In **rootfs** mode, the same ASan pair still reports `DATA_SIZE_INCREASED` INCOMPATIBLE HIGH, with no `comparison_validity` (WP-2 scope excluded rootfs).
2. **REQ-AGG.** Each `ALSO_UNSATISFIED_IN_BASELINE` and each dependent requirement of a missing SONAME is a separate finding. On partial repositories and samples this becomes a new flood.

### 4. Record this independent-environment evidence (in `DECISIONS.md` and the WP-2 report addendum)

By mistake, ClineSR received the WP-2 prompt on its own host and audited WP-2 there. It made two local documentation commits, which it could not push. **Do not import or replay those commits.** Record their findings as independent evidence from a second Linux host:

- Full suite on Python 3.11.18: 365 run, 354 passed, 10 skipped, **1 error**. Host bubblewrap **0.6.1 rejects `--size`**, which the EROFS extraction command uses (`erofs.py` L90). This confirms F-08 on a realistic company host.
- On Python 3.10, 15 test errors occurred, caused by `hashlib.file_digest`, which is Python 3.11+ only (`arm_smoke_admission/manage.py` L96). The documentation claims Python 3.10+.
- Scale check on that host: 1,001 RPMs and 1,501 ELF objects per side; analysis took 148.21 s, peak RSS was 504 MB, and the report was **390.8 MB**.
- OPS-3: 200/200 iterations passed.

Add these process rules to `HANDOVER.md`:
- Every Codex prompt starts with a `FOR CODEX ONLY` banner, and every ClineSR prompt with `FOR CLINESR ONLY`.
- ClineSR never commits or pushes.

### 5. Problem statement and approved design

#### 5.1 F-06 / F-15 — rootfs linking volume

`linker.dependency_checks` loops over every root and emits a finding for every import of every object in its closure, so libc's imports are re-emitted per root. PM measurements: 434 / 1,574 / 6,134 findings for 5 / 20 / 80 identical executables; 1,530 for 20 executables on `ae4d269`. With the default configuration, nearly all of them are UNKNOWN HIGH, which accounts for the 860k on real SR.

Approved design:

1. **Evaluate once per context.** Evaluate each requirement once per `(requiring object, requirement, search context)`. The search context is the effective search inputs used to resolve that object's DT_NEEDED: inherited RPATH (if the object has no RUNPATH), its own RUNPATH, `$ORIGIN` expansion, loader environment, already-loaded SONAMEs, and symbol scope. Memoize that result. Never emit the same `(object, requirement, context)` result twice.
2. **One finding per object and requirement.** Emit **one finding per (requiring object, requirement)**, carrying a `roots` relation: the count, plus up to 20 example root paths. Results for the same requirement that differ by context stay separate findings, because their evidence differs.
3. **No loader profile.** When `loader.environments` is not configured for a side, linking is `NOT_EXECUTED`. Emit exactly **one** finding per side: UNKNOWN MEDIUM, `reason_code=LOADER_ENV_MISSING`, with the next action ("configure loader.environments"). Do not emit per-import UNKNOWN findings. The `linking` coverage obligation must report NOT_EXECUTED, not PARTIAL, in this case.
4. **Aggregate unknowns.** Aggregate all remaining linking UNKNOWN findings by `reason_code` into `results.linking_summary`: `{reason_code: {count, example_finding_ids[≤20], next_action}}`. Put it in `run-summary.json` and in the first screen of `summary.md`.
5. **F-15.** When the `linking` mode is active, always collect the security/execution metadata it needs (`security_metadata_complete`, file capabilities, set-id), even if the `security` dimension is excluded. The `security` dimension's own findings still follow `--exclude`.
6. **Keep the existing loader semantics.** Search order, NODEFLIB, `$ORIGIN`, IFUNC/UNIQUE handling and version rules do not change. This is a volume and identity change, not a semantic change.

#### 5.2 REQ-AGG — repository requirement volume

In `requirements.py`:

1. **Dependents of a missing SONAME.** When a DT_NEEDED requirement for SONAME `S` fails (`NEEDED_SONAME_UNAVAILABLE`) or is `ALSO_UNSATISFIED_IN_BASELINE`, do not emit separate findings for that consumer's version-node and versioned-import requirements on `S`. Count them as `suppressed_dependents` on the DT_NEEDED finding and list them in `requirement-findings.csv` with `suppressed_by=<finding id>`.
2. **Baseline-unsatisfied requirements.** Report `ALSO_UNSATISFIED_IN_BASELINE` as **one finding per (consumer, SONAME)**, not per symbol. Detail rows go to the CSV.
3. **Counts unchanged.** `results.repository.requirements.by_kind` / `by_reason` counts still count every individual requirement, so totals are unchanged. Only the finding volume drops.

#### 5.3 F-07b — rootfs-mode confound

Reuse the WP-2 build-profile logic in `compare_static`, for the side-level profile, `comparison_validity`, `confounders`, the banner and the per-pair downgrade. Record `comparison_validity` at the top level of `results.json` for both modes. Keep the existing `results.repository` copy for compatibility. Classification rules are identical to WP-2 §6.3.

#### 5.4 F-09 — per-operation timeouts

Add validated config keys:
- `analysis.extract_timeout_seconds` (default 3600): `unsquashfs`, `rpm2cpio`, EROFS adapter and standard extractor;
- `analysis.rpmdb_timeout_seconds` (default 900): `rpm --dbpath … -qa`;
- `analysis.abi_timeout_seconds` (default 1800): `abidiff`.

`analysis.timeout_seconds` stays the default for short tools. A timeout records a distinct reason code `TOOL_TIMEOUT`, with the tool name.

#### 5.5 F-21 — RPM metadata capture

`rpm -qp --xml` is capped at 16 MiB (`rpm_payload.py` L252). Make the cap a validated config key `rpm_payload.max_metadata_bytes` (default 128 MiB, maximum 1 GiB). An exceeded cap gives `OUTPUT_LIMIT` on that archive's metadata, recorded as an extraction error. Do not change the parser.

#### 5.6 PORT-310 — Python 3.10

Replace `hashlib.file_digest` in `arm_smoke_admission/manage.py` with a chunked read. Search the repository for any other Python 3.11+ API used by production code or tests, and fix it or report it. If `python3.10` exists on the host, run the full suite with it and report the result. If it does not, report BLOCKED and say where Python 3.10 coverage will come from (CI in WP-4).

#### 5.7 RPT-SIZE — report size

The 1,001-RPM synthetic run produced a report of about 390 MB. On the regenerated scale fixture, measure the size of each output: `results.json`, each manifest, each CSV, `evidence/` (file count and total), and HTML. Report the top contributors and a concrete proposal for each. **Implement only** reductions that change no classification and no evidence identity, such as not writing duplicate copies of the same evidence bytes, or omitting full symbol lists from `results.json` when the manifests already hold them and the reference stays resolvable. Describe anything larger as a proposal.

#### 5.8 Optional real-data check (only if the data already exists in the workspace)

If the real SR image pair behind the 903,377-finding report (`tizen-unified-dev_20261119.012448` vs `tizen-unified-toolchain_20261120.082536`, headless armv7l) is still present **locally and authorized**, rerun the static comparison with the WP-3 code, both without and with a loader profile. Record total findings, INCOMPATIBLE, linking findings, UNKNOWN by reason, wall time, peak RSS and report size, next to the historical numbers. Back up and update `CODEX_STATE.md` before and after, because this is a long run. If the data is not present, report "not available" and do not search other locations.

### 6. In scope / out of scope

**In scope:** §3–§5, the tests below, documentation of new config keys and summary fields (`references/workflow.md`, `references/correctness.md`, `config.yaml` comments), and the PM files.

**Out of scope:**
- EROFS changes: the bubblewrap `--size` compatibility, disk scratch and real EROFS testing go to WP-4.
- The real-tool CI image and v1.5.3 packaging (WP-4).
- Controller redesign, runtime/SDB, pyelftools, finding-ID redesign, waivers.

### 7. Steps

**Step 0.**
1. Verify the commit.
2. Copy the input files.
3. Record §3 and §4.
4. Carry out Addendum A (if not already done), then commit, make the verified backup, and **push immediately**, so ClineSR can download the kit.

**Step 1** — F-06/F-15. **Step 2** — REQ-AGG. **Step 3** — F-07b. **Step 4** — F-09 and F-21. **Step 5** — PORT-310. **Step 6** — RPT-SIZE. **Step 7** — optional §5.8.

**Step 8.**
1. Report, and set statuses to `Implemented, awaiting PM review`.
2. Commit, back up and push.
3. Update `CODEX_STATE.md` before and after any command expected to take longer than 30 minutes.

### 8. Security and side-effect constraints

Never execute analyzed ELF files. No sudo and no host mounts; unprivileged sandbox namespaces in tests are allowed. No network beyond GitHub push/pull. All writes stay in the workspace, except reading Downloads. Do not change visibility, remotes, branches or tags. **No GitHub Releases.**

### 9. Backward compatibility

- New config keys have defaults.
- New fields are additive.
- Existing CSV columns keep their order; new columns are appended.
- Linking finding IDs and counts change by design. Record before/after counts on the fixtures.
- Exit codes are unchanged, except that runs which previously failed only on per-import linking UNKNOWN HIGH findings under `--strict` may now pass or fail differently. Document any such case.

### 10. Required positive tests

- **T-10 Linking scale.** Rootfs with a real `libc.so.6` and loader, plus 5 / 20 / 80 / 500 identical executables, with a complete loader profile and `security` excluded.
  - Expected: libc's imports are evaluated and emitted once per context, not per root.
  - The total linking findings grow at most linearly with the *number of distinct objects + requirements*, not with roots × closure.
  - Verified resolutions are still reported for the executables' own imports, with `roots` counts.
  - Report all four counts next to the PM's v1.5.1 numbers (434 / 1,574 / 6,134).
- **T-10b Context split.** The same DSO is reached from two executables with different RUNPATH, where one resolves a dependency and the other does not. Expected: two findings with different contexts.
- **T-10c No profile.** No `loader.environments`: exactly one `LOADER_ENV_MISSING` finding per side, and linking coverage is NOT_EXECUTED.
- **T-REQ.** A repository consumer needs `libmissing.so.1` with 30 versioned imports. Expected: one DT_NEEDED finding with `suppressed_dependents=31` (30 imports plus 1 version node), totals unchanged, CSV rows linked by `suppressed_by`. The same holds for the `ALSO_UNSATISFIED_IN_BASELINE` variant.
- **T-08r.** The WP-2 ASan fixture in **rootfs** mode: `CONFOUNDED`, size UNKNOWN MEDIUM `INSTRUMENTATION_MISMATCH`, and the removed function still INCOMPATIBLE.
- **T-TIMEOUT.** A fake extractor exceeding `extract_timeout_seconds` gives `TOOL_TIMEOUT`, process-group cleanup, and an incomplete objective.
- **T-META.** A fake `rpm` emitting more than `max_metadata_bytes` gives `OUTPUT_LIMIT` on that archive only; other archives continue.

### 11. Required negative tests

- Memoization never merges results from different search contexts.
- A dependency cycle in the closure terminates.
- Suppressed dependents never hide a failure on a *different* SONAME.
- A confound on one side's minority of objects (below the 0.20 share) does not set CONFOUNDED, but per-pair downgrades still apply.
- An invalid timeout or cap config value is rejected with a clear message.

### 12. Acceptance criteria

All of the following:
- All tests in §10 and §11 pass (with any BLOCKED items listed).
- The full suite passes with no new skips.
- The Python 3.10 result is reported (or BLOCKED with the reason).
- The RPT-SIZE table and proposals are delivered.
- The PM files are updated, two verified backups exist, `main` is pushed, and no tags or Releases were created.

### 13. Deliverables and git rules

**Deliverables:**
- Commit SHAs (pushed) and the changed-file list.
- Test commands and outputs.
- Before/after linking and requirement counts.
- The RPT-SIZE table.
- The optional SR rerun table.
- Deviations.
- New issues.
- `docs/pm/work-packages/WP-3/REPORT.md`.

**Git rules:** `main` only. No branches, PRs, force-push, history rewrite, or tag creation, movement or push. **No GitHub Releases.** Stage exact paths. Use a normal `git push origin main` at Step 0 and Step 8.

### 14. Final report format

1. Step 0 state.
2. Changes per item, with SHAs.
3. Deviations.
4. Test table (PASS/FAIL/BLOCKED).
5. Before/after counts.
6. RPT-SIZE.
7. Optional SR rerun.
8. Backup and push evidence.
9. Open risks and new issues.
10. Recommended next step (one paragraph).
