> **FOR CODEX ONLY.** If you are ClineSR or another agent, stop: this is not your task.

# WP-4 Addendum B — kit revision 7, memory scaling, review headline → v1.5.3-rc2

Put this file at `docs/pm/work-packages/WP-4/ADDENDUM_B.md`.

**Addendum A was not executed:** it arrived after you had started WP-4. **This addendum replaces it entirely.** Do not publish kit revision 6. Revision 7 includes revision 6.

Starting commit: `da3792506c99e2b437957cf883c04480f65a5ace`. Target: report by **Dec 1**.

## B0. PM verification of WP-4 (record it in `docs/pm/work-packages/WP-4/PM_REVIEW.md` and `DECISIONS.md`)

**v1.5.3-rc1 (`da37925`) is accepted as an RC.** PM checks:

| Check | Result |
|---|---|
| Full suite (PM host) | 391 tests OK, 29 tool-dependent skips |
| COPY-REL | The PM's own non-PIE `optind` reproducer is now `COMPLETE`, and `copy_relocations` records version GLIBC_2.2.5, size 4 and provider `libc.so.6`. |
| POL-WEAK on real g++ output | Hiding a template, a class vtable, typeinfo and inline members in the candidate gives 9 × `UNKNOWN LOW WEAK_CXX_EXPORT_REMOVED_UNREFERENCED`. Their `cxx_class` and demangled names are correct, and `review.pending` is 9. |
| DT-AGG | Linking findings 82,992 against a target of 80,000. Accepted. |
| SR size | 59% against a target of 50%. Accepted, because SR is a linking-profile image case. The VD measurement decides RPT-SIZE-3. |

**Gap REV-HEAD (fix in B3):** with 9 symbols pending review, the console line says `quality gate PASS`, and the summary/HTML headline does not mention the pending review. It only appears in a section further down.

**Minor:** the `copy_relocations[].name` field keeps the `@GLIBC_2.2.5` suffix, while `version` already holds it. Store the base name.

## B1. Publish kit revision 7 now (before any other work)

1. Verify that `$DOWNLOADS/vd1_measure.sh` has SHA-256 `3effc6819b0b35d1f44c8e0f360e8707a2c61fcb74396df55000f1f4fc846abb`. If not, stop.
2. Revision 7 = revision 5 + the revision 6 and revision 7 changes below. All of them are read-only reporting, and no names are printed.
   - **From revision 6:**
     - `summary` skips tags that were not run in the WORK.
     - `detail` adds object counts by role, ELF type and path class; the shape of export-incomplete objects; extraction-error counts by side, stage, code and tool; and more fixed readelf diagnostic classes.
   - **New in revision 7:** it reads v1.5.3-rc1 reports.
     - It accepts gzip manifests and `.txt` evidence references stored as `.txt.gz`.
     - It classifies removed exports by `reason_code`/`removal_context`. Findings now carry `{"$symbol": …}` references instead of symbol dictionaries.
     - It counts `reason_by_status`, compatible reasons, the run-summary `review` block, the number of rows in `weak-export-review.csv` by `cxx_class`, and copy-relocation counts.
3. The PM tested it on a v1.5.3-rc1 report and on a WP-3b report. Your same-class privacy-fix authority still applies. If you change the file, put the new SHA-256 in the first line of your message to the owner.
4. Publish it at `docs/pm/clinesr/vd1_measure.sh`. Append a "Revision 7" record to `VD-1_PROMPT.md`. Then commit, make the verified backup, and `git push origin main`.

## B2. Record VD-1c and the server facts (in `DECISIONS.md`)

The ClineSR server runs **Python 3.10.22**.

VD-1c covers 600 packages per side (1.8 GB each) with tool `2633672`:

| Metric | 150 packages | 600 packages | Linear projection to 5,693 |
|---|---:|---:|---:|
| Wall time | 50 s | 223 s | ≈ 35 min |
| Peak RSS | 424 MB | 1,535 MB | **≈ 14 GB** |
| Report | 325 MB | 1,315 MB | **≈ 12.5 GB** |

- **600-package report breakdown:** evidence 318 MB, `symbol-differences.csv` 281 MB, `results.json` 254 MB, manifests 318 MB, `findings.csv` 78 MB, `requirement-findings.csv` 51 MB.
- **Removed exports and binding changes:** 23,251 removed exports, of which 21,380 are weak (92%). 958 are imported somewhere: 658 GLOBAL and 300 WEAK. Binding changes: GLOBAL→WEAK 25,512, UNIQUE→WEAK 729. Also 6 `DEFAULT_VERSION_LOOKUP_LOST`.
- **Export-incomplete objects:** 463 in the baseline and 365 in the candidate.
  - 341 per side are `DUPLICATE_DYNSYM_IDENTITY`. 352 per side are `object_incomplete` with about 12,200 readelf warnings each side.
  - This symmetric group is **unexplained**. It is not split debug files in the PM's x86 reproduction. Kit revision 7 will classify its shape. Do not change classification for it yet.
- **Extraction errors:** `extraction-errors.csv` is 2.3 MB, cause unknown. Revision 7 counts it.

## B3. REV-HEAD — pending review must be visible at the top

- When `review.status` is `PENDING`, add `Owner review: N weak C++ export removals pending (see weak-export-review.csv).` in three places:
  - the console result line;
  - the `summary.md` headline block;
  - the HTML headline.
- Add `review_gate: PENDING | COMPLETE | NONE` to `run-summary.json`. Existing gate fields keep their meaning; no exit code changes.
- Print the "Counts by C++ class" line as a small table, not raw JSON.
- Tests: assert all three places, plus the `NONE` and `COMPLETE` cases.

## B4. MEM-SCALE (P1)

The projected peak RSS of about 14 GB for the full repositories is a VD-2 risk; the server's RAM is being measured now.

1. **Attribute.** Use `tracemalloc` snapshots, or sampled RSS per phase, on a repository run large enough to show growth. Use a synthetic generator with real-like symbol counts: about 100 exports and 150 imports per object, and C++-length mangled names. Use about 300 to 600 objects per side, and run at least two sizes to get the slope.
   - Report RSS per phase: collection, pairing, requirements, comparison, report assembly.
   - Report the top allocation sites.
2. **Reduce** where the attribution points. Candidates:
   - Release per-object symbol inventories after each pair is compared and written.
   - Keep the requirement index as compact tuples or in SQLite staging.
   - Stream findings to writers instead of materializing the full results structure.
3. **Target:** RSS growth per package at most half of today's. Today it is about 2.5 MB per package on real data. Projected full-repository peak ≤ 7 GB. If you cannot reach it, report the measured slope and the blocker.
4. **Proof:** reconciliation shows the outputs are unchanged.

## B5. Packaging

- `VERSION` becomes `1.5.3-rc2`, with a CHANGELOG entry.
- **No tag and no Release.**

## B6. Report

Use the WP-4 section 10 format with these sections:
1. the published kit SHA-256;
2. REV-HEAD tests;
3. a MEM-SCALE table: RSS per phase before and after, slope before and after, top allocation sites;
4. backups and push.

`main` only. No tags, no Releases.
