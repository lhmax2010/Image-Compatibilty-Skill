> **FOR CODEX ONLY.** If you are ClineSR or another agent, stop: this is not your task.

# Codex Work Package WP-3b
## Real-data hygiene: reason codes, removal context, linking detail aggregation, report size

You are the implementation engineer for the Tizen Image Compatibility Skill. Claude is the technical PM and independently reviews your commits, tests and evidence. Communicate in English. Do not invent product requirements. If something here is ambiguous, or a demonstrably smaller and safer solution exists, implement the safe interpretation and disclose the deviation.

**Input files** (in `$DOWNLOADS` = `/home/linhao/Downloads`; copy them yourself, do not delete anything there):

| File | Put it at |
|---|---|
| `WP-3b_CODEX_PROMPT.md` (this file) | `docs/pm/work-packages/WP-3b/PROMPT.md` |
| `vd1_measure.sh` (revision 5, SHA-256 `16035e63e8b1197bdfe32d59f376da3ba1f4b62ec9a05ed75640844bc41efcdf`) | `docs/pm/clinesr/vd1_measure.sh` (replaces revision 4.2). See §2. |

Target: report by **Nov 29**. WP-4 starts Dec 1.

---

### 1. Starting commit

`0c40d400433d9f54c9659c598372f07d990095e1` on `main`. Stop if `origin/main` has moved and report what is there.

### 2. Addendum B — publish measurement kit revision 5 FIRST (Step 0)

ClineSR is waiting for this kit. Publish it before any code work.

1. Verify the SHA-256 of `$DOWNLOADS/vd1_measure.sh` is `16035e63e8b1197bdfe32d59f376da3ba1f4b62ec9a05ed75640844bc41efcdf`. If not, stop.
2. Review it against the rules already recorded for ClineSR (writes only under `.local-work/`, read-only Git, counts only, no package/file/symbol names printed, raw diagnostics only in `*.private.*` files). Revision 5 keeps revision 4.2 and adds:
   - `rerun <WORK> <40-hex commit>`: exports another published tool commit (must be an ancestor of `origin/main`) into the same WORK and runs it on the same sample. It refuses to overwrite.
   - `summary <WORK> [tag...]`: optional extra 7-hex tags.
   - `detail <WORK> <tag>`: name-free breakdowns of one report: full-repository counts from `BASE.map`/`CAND.map`, report bytes per top-level entry, UNKNOWN composition, ABI findings by kind/status/reason, removed-export profile (binding, type, versioned, C++ class, whether any sampled object imports it), field-change pairs, and export-incompleteness flags with **sanitized** readelf diagnostic signatures (quoted strings, paths, file names, long tokens and numbers masked).
3. You keep the delegated authority from Addendum A for **same-class** fixes (writes outside `.local-work`, names reaching the terminal). If you change the file, the SHA-256 changes: put the new SHA-256 in the **first line of your Step 0 message to the owner**, because the ClineSR paste prompt checks it. Do not make non-blocking edits.
4. Update `docs/pm/clinesr/VD-1_PROMPT.md`: append a "Revision 5" record with the published SHA-256 and the commands `rerun`, `summary <WORK> 323e0e1 0c40d40`, `detail` (no paste prompt text is needed there; the PM gives it to the owner).
5. Commit, make the verified backup, `git push origin main`, and tell the owner the commit and the kit SHA-256.

### 3. PM verification of WP-3 (record it in `docs/pm/work-packages/WP-3/PM_REVIEW.md` and `DECISIONS.md`; do not re-test)

WP-3 (`853cadc`, `0c40d40`) is **accepted**. Independent PM checks on `0c40d40`:
- Full suite: 375 run, OK, 29 skipped (tool-dependent on the PM host) on both Python 3.13 and Python 3.11. Python 3.10 is still unexecuted (WP-4 CI gate).
- Linker diff reviewed: lookup and state rules unchanged; memoization keys include the search context; grouping keys include image, object, interface and context. Accepted.
- Linking scale fixture (PM's own, glibc profile): 238 / 703 / 2,563 total findings at 5 / 20 / 80 executables, `roots` max 6 / 21 / 81, wall 0.6–1.9 s. Growth is per distinct consumer, not roots × closure. Without a profile: exactly 2 `LOADER_ENV_MISSING` linking findings regardless of size.
- Rootfs ASan fixture: `CONFOUNDED` (candidate share 1.0), size change `UNKNOWN`/`INSTRUMENTATION_MISMATCH`, removed function still `INCOMPATIBLE`. F-07b closed.
- Gap found by the PM (now RC-INV below): the removed-function finding has **no `reason_code`**. Two linking coverage findings also have none.

### 4. VD-1 real-data evidence (record in `DECISIONS.md` and add the new issues to `ISSUE_REGISTER.md`)

ClineSR ran kit revision 4.2 on a real ARM ELF32 sample: 150 common package names per side (214 MB baseline GCC, 191 MB candidate LLVM), 243 ELF objects per side, payload mode, static.

| Metric | v1.5.1 `2d43c58` | WP-2 `323e0e1` |
|---|---:|---:|
| Wall time / peak RSS | 54.4 s / 360 MB | 54.3 s / 380 MB |
| Report bytes | 467.8 MB | 535.6 MB (≈3.6 MB per RPM) |
| ELF complete (base / cand) | 242 / 242 | 243 / 243 |
| Export inventories complete (base / cand) | 228 / 240 | 230 / 242 |
| Incomplete exports with no reason code (base / cand) | 14 / 2 | **13 / 1** |
| Findings / INCOMPATIBLE / UNKNOWN | 13,605 / 4,849 / 7,739 | 14,657 / 4,924 / 8,609 |
| `SYMBOL_BINDING_CHANGED` (UNKNOWN HIGH) | — | **6,939** |
| Export diff (EXPORT role): MISSING / CHANGED / ADDED | — | **4,828** / 29,218 / 826 |
| Requirements satisfied in baseline, failed on candidate | — | **0 of 14,668** |
| Requirements unsatisfied in baseline too | — | 26,198 (sample omits most providers) |
| `comparison_validity`, ASan objects | — | COMPARABLE, 0 / 0 |

PM conclusions (decisions D-WP3b-1..4):
1. **Throughput and memory are not RC blockers.** F-10 (parallel RPM collection) stays after the RC unless the full-repository projection from `detail` says otherwise.
2. **Report size is the scaling problem** (3.6 MB per RPM on real data; 1.24 GB for the SR images without a profile and 5.5 GB / 6.5 GB peak RSS with partial profiles). → RPT-SIZE-2 and LINK-AGG.
3. **The headline is misleading on real data.** All 4,924 INCOMPATIBLE findings carry no reason code (they print as `abi/none`), they are almost all removed exports, and 0 of 14,668 checked consumer requirements break. The 6,939 binding changes dominate UNKNOWN. **No classification policy changes in WP-3b**: first add reason codes and removal context (RC-INV, EXP-CTX), then ClineSR's `detail` run gives the breakdown, then the PM decides the policy for WP-4.
4. The candidate sample is not ASan-instrumented (imports 40,616 vs 40,427), so the ASan detector's negative is correct but its positive path is unvalidated on real data. Recorded for VD-2.

New issues: **RC-INV**, **EXP-RC**, **EXP-CTX**, **LINK-AGG**, **RPT-SIZE-2** (all P1, owner Codex, WP-3b); **POL-REMOVED** and **POL-BINDING** (P1, owner PM, WP-4, blocked on ClineSR `detail`); **VD-ASAN** (P2, owner PM, VD-2).

### 5. Approved design

#### 5.1 RC-INV — every non-COMPATIBLE finding has a reason code

- Every finding with status `INCOMPATIBLE` or `UNKNOWN` carries a non-empty, stable, upper-snake `reason_code`. At least:
  - `EXPORT_REMOVED` (absence proven) and `EXPORT_NOT_OBSERVED` (candidate inventory incomplete);
  - `VERSION_DEFINITION_REMOVED` / `VERSION_DEFINITION_NOT_OBSERVED`;
  - `DEFAULT_VERSION_LOOKUP_LOST`, `DEFAULT_VERSION_CHANGED`, `DEFAULT_SYMBOL_VERSION_CHANGED`;
  - `EXPORT_INVENTORY_INCOMPLETE`, `DT_NEEDED_CHANGED`, `DWARF_ABI_UNAVAILABLE`;
  - a code for each dimension-coverage finding (for example `DIMENSION_NOT_EXECUTED`, `COVERAGE_LIMITATION`) and for the linking coverage findings.
- Existing codes keep their spelling.
- `results.json` → `finding_integrity.missing_reason_codes` (an integer). `build_results` computes it for every run. **It must be 0** in every report the suite generates.
- Document the full vocabulary (code, status, meaning, next action) in `references/correctness.md`.

#### 5.2 EXP-RC — export incompleteness always explains itself

- When `export_inventory_status` is `UNKNOWN`, `export_inventory_reason_code` is always set. Codes:
  - `READELF_DIAGNOSTIC`, `DYNSYM_ROWS_INCONSISTENT`, `VERSION_RECORDS_INCONSISTENT`, `HEADER_FIELDS_MISSING`, `OBJECT_INCOMPLETE`;
  - plus the existing `TOOL_TIMEOUT`, `OUTPUT_LIMIT` and `DUPLICATE_DYNSYM_IDENTITY`.
- Also add `export_inventory_diagnostics`: the list of **all** conditions that failed, not only the first.
- Add `readelf_diagnostic_classes` (sanitized classes, no paths or names) where stderr caused it.
- **Do not relax any completeness rule in WP-3b.** Whether some readelf warnings are benign is decided after the `detail` data.
- Add a repository and image summary counter: `export_incomplete_by_reason`.

#### 5.3 EXP-CTX — removal context (data only, no status change)

- Each `EXPORT_REMOVED` / `EXPORT_NOT_OBSERVED` finding gets `removal_context`:
  - `{binding, type, versioned, cxx_class, observed_importers: {baseline: n, candidate: n}}`;
  - `cxx_class` is one of `c`, `vtable`, `typeinfo`, `typeinfo_name`, `vtt`, `guard`, `thunk`, `cxx_template`, `cxx_other`;
  - `observed_importers` counts distinct objects in the analyzed set (rootfs image or repository side), other than the provider itself, that import the same symbol identity and match its version where one is given. Build the index once per comparison.
- Add a summary block `removed_exports` with these counts.
- Statuses and severities stay exactly as today.

#### 5.4 LINK-AGG — findings are decisions; per-import detail goes to CSV

Under partial loader profiles, the SR run produced 561,567 linking UNKNOWN rows and 6.5 GB peak RSS. In the PM's complete-profile fixture, verified imports are one COMPATIBLE INFO finding each. Neither scales.

- **Per-import checks** (`import:*`, `version:*`):
  - Write them as rows of a new streamed `linking-details.csv`. Columns: `id, anchor_finding_id, image, consumer, check_id, state, provider, roots_count, search_context_hash`.
  - Emit **one finding per (image, consumer object, state, search context)** with `aggregated_checks: n` and up to 20 example `check_id`s.
- **Exceptions:**
  - Every `INCOMPATIBLE` linking state (`missing_symbol`, `symbol_type_mismatch`, `missing_version`, `missing_provider`, `unresolvable_provider`) is still emitted individually. It also gets a detail row.
  - `DT_NEEDED` checks stay individual.
- **Memory:** do not hold per-import rows in memory beyond what the streaming writer needs. Detail rows are reconcilable with the findings by `anchor_finding_id`.
- **Coverage and the run summary** count checks from the detail counters, not from the number of findings.
- **SR acceptance** (same data and configs as the WP-3 §7 partial-profile run):
  - linking findings ≤ 10,000;
  - detail rows equal the WP-3 per-import count;
  - INCOMPATIBLE count unchanged at 11,490;
  - peak RSS and report bytes reported. Target ≤ 2 GB RSS; if it is missed, report the top contributors.

#### 5.5 RPT-SIZE-2 — report size

- **`symbol-differences.csv`:** by default it no longer writes `MATCHED` rows. Their counts stay in every summary. Add `report.symbol_differences: changes | all` (default `changes`).
- **`results.json`:** must not duplicate per-package symbol inventories that the manifests already hold. Use references resolvable by the enhanced index. Keep reader compatibility with v1.3 / WP-3 reports, or document a versioned reader change.
- Keep the evidence SHA-256 references and raw bytes.
- **Acceptance on `tests/wp2_scale.py`:** a complete report ≤ 60% of the WP-3 size (308.7 MB → ≤ 185 MB). Row-level reconciliation of every non-MATCHED row against WP-3 output. Give the per-file table as in WP-3 §6.

### 6. In scope / out of scope

**In scope:**
- §2–§5, the tests below and the PM files.
- Documentation of new keys and fields in `references/workflow.md`, `references/correctness.md` and `config.yaml`.

**Out of scope:**
- Any change to the status or severity of export removals or binding changes (POL-REMOVED, POL-BINDING are WP-4 after data).
- EROFS (WP-4).
- Real-tool CI and packaging (WP-4).
- F-10.
- Finding-ID redesign and waivers.

### 7. Steps

- **Step 0:**
  1. Verify the starting commit.
  2. Copy the inputs.
  3. Carry out Addendum B (§2): commit, verified backup, **push immediately**.
  4. Record §3 and §4, then commit and push.
- **Step 1:** RC-INV.
- **Step 2:** EXP-RC.
- **Step 3:** EXP-CTX.
- **Step 4:** LINK-AGG, including the SR rerun.
- **Step 5:** RPT-SIZE-2.
- **Step 6:**
  1. Report and set statuses to `Implemented, awaiting PM review`.
  2. Commit, back up and push.
  3. Update `CODEX_STATE.md` before and after any command expected to take longer than 30 minutes.

### 8. Security and side-effect constraints

- Never execute analyzed ELF files.
- No sudo and no host mounts.
- No network beyond GitHub push/pull.
- All writes stay in the workspace, except reading Downloads.
- Do not change visibility, remotes, branches or tags. **No GitHub Releases.**

### 9. Backward compatibility

- New config keys have defaults; new fields and CSV columns are appended.
- `linking-details.csv` is new.
- Linking finding counts and IDs change by design: record before/after on the WP-3 fixtures and the SR run.
- Exit codes are unchanged. INCOMPATIBLE findings are never aggregated away.

### 10. Required positive tests

- **T-RC:**
  - Generate reports for rootfs, repository, the ASan fixture, linking with and without a profile, a timeout case and an export-incomplete case.
  - In every one, `finding_integrity.missing_reason_codes == 0`.
  - The removed function has `EXPORT_REMOVED`.
- **T-EXP-RC:** each of the five new export codes is produced by a fixture, and `export_inventory_diagnostics` lists multiple failing conditions when several apply.
- **T-CTX:**
  - Removed exports, one imported by another object in the set and one not, give `observed_importers.baseline` 1 and 0.
  - A versioned import of a different version does not count.
  - `cxx_class` is correct for a vtable, a typeinfo and a C symbol.
- **T-LINK-AGG:**
  - The PM-style fixture with 5 / 20 / 80 executables and a complete profile gives one COMPATIBLE finding per consumer and context, with detail rows equal to the WP-3 per-import count.
  - A missing symbol under a complete scope stays an individual INCOMPATIBLE finding and also has a detail row.
- **T-SIZE:** the `wp2_scale` table, reconciliation, and the `symbol_differences: all` path.

### 11. Required negative tests

- Aggregation never merges different states, consumers, images or search contexts.
- A finding with no reason code makes T-RC fail. Prove it by a temporary mutation in the test; do not commit the mutation.
- `observed_importers` never counts the provider itself.
- The enhanced index still reads a WP-3 report.

### 12. Acceptance criteria

- All of §10 and §11 pass, and the full suite passes with no new skips.
- §5.4 SR targets are met, or the misses are explained with data.
- §5.5 size target is met, or the misses are explained.
- PM files are updated, the kit is published first, two verified backups exist, `main` is pushed, and no tags or Releases were created.

### 13. Git rules

- `main` only. No branches, PRs, force-push, history rewrite, or tag creation, movement or push. **No GitHub Releases.**
- Stage exact paths.
- Use a normal `git push origin main` at Step 0 and Step 6.

### 14. Final report format

1. Step 0 state, including the published kit SHA-256.
2. Changes per item, with SHAs.
3. Deviations.
4. Test table (PASS/FAIL/BLOCKED).
5. Reason-code vocabulary table.
6. LINK-AGG before/after (fixtures and SR).
7. RPT-SIZE-2 table.
8. Backup and push evidence.
9. Open risks and new issues.
10. Recommended next step (one paragraph).
