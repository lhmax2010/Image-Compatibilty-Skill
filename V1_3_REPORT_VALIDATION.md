# v1.3 report enhancement — validation evidence

Report build, independent reconciliation, real-browser verification and input immutability audit: **PASS**. This is report functionality evidence, not image compatibility certification.

## Preservation boundary

- Branch: `review/tizen-compatibility-correctness-1.2`; HEAD: `2d5bacaef2af1a9bd4b793123de02684e5f38128`.
- `main`: `386a284c37b0fdf105948bef35d1bacdc7a9c389`. No checkout/reset/stash/commit/push/merge.
- Before work, 141 repository files were hashed and copied to `headless/work/phase5/code-before/`; original binary Git diff and status are in `BASELINE.json` and `baseline.diff`. Pre-existing RC changes are preserved.
- New production code is isolated in the report enhancer/browser and assets. Existing compatibility detector/collector/test scheduling/package assessment modules are unchanged relative to the local starting snapshot.
- A separate SHA256 snapshot covers 9724 Phase3/4 report files, including evidence (`work/phase5/REPORTS_BEFORE.json`). Original reports and rootfs are read-only inputs.

## Tests before actual report processing

Baseline suite: 131 tests, 5 skipped, no failures. Final suite: **152 tests, 147 passed, 5 skipped, no failures**, in 16.214 seconds. The final run log is `headless/work/phase5/full-tests-accepted.log`, with `/usr/bin/time -v` evidence alongside it. The 21 new tests include regressions added after actual report/browser observations.

The five skips are pre-existing optional real Clang/ARM, GCC/Clang custom-probe matrix, and libabigail integrations whose tools/opt-in settings are unavailable. They are not reported as passing.

| Required case | Regression evidence |
|---|---|
| Single package / multiple ELF | `test_multiple_elf_and_alias_dedup` |
| Symlink aliases | Same test verifies 4 collected rows → 3 canonical ELF identities |
| FUNC / IFUNC / OBJECT / TLS | `test_export_types_and_version_counts` |
| Versioned symbols | Type/count test plus `test_all_difference_categories_and_original_status` |
| Missing / added / changed | All eight known comparison categories, original incompatible ID and conservative MATCHED status |
| Ambiguous ownership | `test_ambiguous_ownership_is_not_complete` |
| Candidate-only package | `test_candidate_only_and_unknown_api_linking` |
| UNKNOWN API/Linking | Same test and original assessment comparison |
| Grouping without loss | `test_grouping_preserves_consumers_and_requirements` retains two roots and separates different requirements |
| Large JSON/CSV | 20000-row Unicode/chunk-boundary test; original 2000-package/22201-finding benchmark plus full serialized reconciliation |
| HTML escaping / read-only access | HTML text-node contract, query injection/filter tests, HTTP traversal/POST rejection, actual Chromium navigation |
| No SDK/debuginfo | `test_no_sdk_debug_information_is_unknown` |
| Incomplete manifests | `test_incomplete_collection_never_supplies_complete_zero` and incomplete symbol/unmatched ELF test |
| Source/record preservation | Exact original payload/ID comparison, original package fields, source SHA256 before/after |
| Resource/output boundaries | Disk-limit failure test; existing/source-contained output refusal |
| Original global result | `test_original_global_outcome_and_verification` reproduces and protects the source `status` mapping |
| Bounded list payloads | `test_list_pages_defer_heavy_metadata_to_exact_details` retains complete details while keeping lists small |
| Indexed group pagination | `test_group_pagination_uses_covering_sort_before_payloads` checks the actual query plan and ordered/filtered results |

`node --check` and `git diff --check` passed. A synthetic browser run exercised Overview → package name search → Package → ELF symbols → Linking group → original Finding with no JavaScript exceptions. A navigation race found during this run was fixed by suppressing stale page continuations.

## Real source and required reconciliation

The source is `headless/reports/phase4-static/skill-report`. Expected source facts are 898342 findings (12195 INCOMPATIBLE, 860110 UNKNOWN, 25726 COMPATIBLE, 311 IDENTICAL), 855522 Linking findings, 11111 unassigned IDs, 722 baseline and 736 candidate package rows, and 2007/2116 collected ELF rows.

The build independently checks every original findings.csv field against the ingested JSON representation and verifies the retained payload hash. It checks original package status/verification fields against packages.csv, retained coverage/confidence/limitations against source assessments, package counts from distinct canonical ELF symbol rows, exact group coverage, every generated CSV row count, and source hashes before/after. A separate readback script checks exact generated ID/member fields against the index and the fixed real Phase4 totals.

Observed package symbol counts remain available. Complete package counts remain UNKNOWN because the real manifests explicitly record incomplete collection. No missing SDK/layout/loader evidence is invented.

The initial real ingestion was interrupted for this completeness correction; partial output and traceback are retained in `work/phase5/real-attempt1-stopped` and `real-attempt1.*`. It is not counted as a successful run. No resource budget was raised.

## Actual outcome

The real build's `validation.json` passes all 23 checks. A separate `independent-validation.json` passes all 12 checks, including exact fields for every Finding ID, group member and unassigned ID. All 722 baseline / 736 candidate package rows remain present; original package outcomes and partial verification are retained. The original state histogram is unchanged:

| Original state | Retained findings |
|---|---:|
| INCOMPATIBLE | 12195 |
| UNKNOWN | 860110 |
| COMPATIBLE | 25726 |
| IDENTICAL | 311 |
| Total | 898342 |

The 2007/2116 collected ELF records resolve to 1968/2077 canonical objects, with 39 aliases removed from each image's totals. There are 2090 ELF-pair rows and 322036 symbol-detail rows. Observed image-unique FUNC counts are 251312 (baseline) and 273302 (candidate); package-attributed counts are 264662/286651 because shared ownership overlaps. The independent ELF-to-package recount passes. There are 183 baseline and 178 candidate packages with no observed ELF; their complete counts remain UNKNOWN. This is an ELF-only measure, distinct from the source's no-collected-interface measure.

### Linking interpretation

All **855522** original Linking findings remain UNKNOWN. They form **134402 navigation groups**, **75055 distinct recorded interfaces/dependencies**, and **9 recorded-reason categories** (8 actual resolution values plus NOT_RECORDED). **62187** groups have multiple observations and contain **783307** findings; **72215** groups have one observation. These counts expose repeated observations across consumers; they do not collapse the underlying risk or produce a new compatibility verdict.

| Reason category | Raw findings | Groups |
|---|---:|---:|
| unknown_symbol_scope | 443332 | 89766 |
| unknown_symbol_semantics | 312801 | 36894 |
| unknown_version_requirement | 56886 | 5440 |
| unknown_search_environment | 39416 | 1674 |
| unknown_loader_abi | 1444 | 2 |
| NOT_RECORDED | 1035 | 607 |
| unknown_loader_feature | 604 | 15 |
| missing_provider | 2 | 2 |
| unknown_collection | 2 | 2 |

The full member CSV and SQLite lookup preserve direct/root consumers, providers, original IDs and evidence. Interface sets can overlap across reason categories and must not be summed as globally unique interfaces.

### Actual review corrections and retained evidence

1. Incomplete source manifests: stopped the initial ingestion, preserved its partial output, then added the complete-count UNKNOWN guard and a positive/negative regression. The completed build includes this fix.
2. Global overview mapping: a focused regression failed (`None != INCOMPATIBLE`) because the original root key is `status`. Fixed the mapping and refreshed only derived overview/assets. `overview-refresh-evidence.json` records source scalar/Markdown agreement and unchanged Finding DB size/mtime; CSVs were not rewritten.
3. Real package coverage fields reached 3.8 MB. List responses now defer full coverage/limitations and group key/evidence payloads to exact detail endpoints; machine outputs are complete.
4. Actual Linking list pagination timed out. Added `group_navigation` covering sort/filter index, selected page IDs before fetching details, and used the already reconciled overview total for the unfiltered list. `navigation-index-evidence.json` confirms 134402 groups before/after and a covering-index query plan. No data row was modified. The first repair pre-count hit the same large-key-index scan and was stopped; its cause is retained in `work/phase5/navigation-index-count-interruption.json`.
5. The first browser probe selected a building-block package containing “glibc” with no ELF, then timed out waiting for an ELF link. The corrected probe explicitly selects `glibc` and its largest observed-FUNC ELF. The harness failure and the pre-index browser failure remain in `browser-real-first-selection.json` and `browser-real-before-group-index.json`.

Final Chromium verification is **PASS**, with no JavaScript exceptions. It exercises Overview → name search → glibc Package → ELF (50 symbol rows) → Linking groups → group members → the original Finding JSON/evidence. `work/phase5/browser-real.json` records route times; `V1_3_PERFORMANCE.md` reports them without implying cold-cache or cross-browser guarantees.

Input immutability: **PASS**. All 9724 Phase3/4 files have unchanged SHA256/size. Baseline/candidate rootfs path sets, content hashes, modes, UID/GID and symlink targets match the original snapshots (8392/8595 entries; 543945196/552946666 regular-file bytes rehashed). Both original archives and all eight partition images retain their expected hashes. Evidence: `work/phase5/INPUT_IMMUTABILITY_AFTER.json`; errors are empty. Its elapsed time includes the explicitly recorded pause used to serialize disk work.

Final Git/file hashes are recorded in `work/phase5/FINAL_WORKSPACE.json`. See `V1_3_KNOWN_LIMITATIONS.md` for remaining evidence and performance limits. The v1.3 report enhancement is ready for independent review; no compatibility certification is implied.
