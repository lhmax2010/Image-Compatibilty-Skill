# WP-3b acceptance report

## 1. Step 0 state

The local and remote main branch started clean at `0c40d400433d9f54c9659c598372f07d990095e1`. The downloaded revision 5 kit matched the PM's SHA-256 `16035e63e8b1197bdfe32d59f376da3ba1f4b62ec9a05ed75640844bc41efcdf`. The delegated fixes made the rerun log exclusive, kept tool streams private, and replaced permissive report entry and diagnostic labels with fixed categories. The 50-RPM-per-side smoke test covered prepare, run, rerun, summary, detail, redaction and overwrite refusal. The published script SHA-256 is `8bf3dc72b7d2a20b5ac1f98fbd4c7aa77cd9b100c512134b7053dd5a8780af66`. GitHub main received `3395992a2f0d5b1d88beebc86366134185aa97d5` before production work. The next commit `0e08fdb5bdf8719b621690b42536ca49582c5535` records WP-3 acceptance and the real VD-1 observations. [Revision 5 record](../../clinesr/VD-1_PROMPT.md) · [Independent PM review](../WP-3/PM_REVIEW.md) · [VD-1 decisions](../../DECISIONS.md)

## 2. Changes per item

Implementation commit `e525a838a847d0a71c9431eb10b0de5c76c73039`.

| Item | Implementation |
| --- | --- |
| RC-INV | Add stable upper-snake reasons, including explicit export and version cases and coverage gaps. Report and test the count of missing or invalid reason codes. |
| EXP-RC | Collect every failed export inventory condition and a primary code. Stderr diagnostics expose fixed classes. The original completeness predicates remain authoritative. |
| EXP-CTX | Compare exact dynamic symbol identities against per-side importer indexes. Each removal records binding, type, version flag, Itanium class and observed importer counts with self excluded. |
| LINK-AGG | Stage per-symbol checks and their root relations in SQLite, stream the detail CSV, and aggregate equivalent contexts into findings. Keep individual failures and DT_NEEDED rows. Carry direct check counts into coverage. |
| RPT-SIZE-2 | Default the symbol CSV to changes. Keep MATCHED counters and the explicit all mode. Refer to manifest symbol inventories from package assessments. |

### Changed implementation and test files

```text
.agents/skills/tizen-image-compatibility/config.yaml
.agents/skills/tizen-image-compatibility/references/correctness.md
.agents/skills/tizen-image-compatibility/references/workflow.md
.agents/skills/tizen-image-compatibility/scripts/compat/compare.py
.agents/skills/tizen-image-compatibility/scripts/compat/core.py
.agents/skills/tizen-image-compatibility/scripts/compat/coverage.py
.agents/skills/tizen-image-compatibility/scripts/compat/elf.py
.agents/skills/tizen-image-compatibility/scripts/compat/linker.py
.agents/skills/tizen-image-compatibility/scripts/compat/linking_details.py
.agents/skills/tizen-image-compatibility/scripts/compat/observation.py
.agents/skills/tizen-image-compatibility/scripts/compat/package_analysis.py
.agents/skills/tizen-image-compatibility/scripts/compat/report.py
.agents/skills/tizen-image-compatibility/scripts/compat/report_enhance.py
.agents/skills/tizen-image-compatibility/scripts/compat/report_store.py
.agents/skills/tizen-image-compatibility/scripts/compat/repository.py
.agents/skills/tizen-image-compatibility/scripts/compat/rootfs_symbols.py
.agents/skills/tizen-image-compatibility/scripts/compat/run_summary.py
.agents/skills/tizen-image-compatibility/scripts/tizen_compat.py
.agents/skills/tizen-image-compatibility/tests/test_rpm_payload.py
.agents/skills/tizen-image-compatibility/tests/test_wp3.py
.agents/skills/tizen-image-compatibility/tests/test_wp3b.py
```

## 3. Deviations and limits

Equivalent anchors use the requiring object, separate comparison direction and image, resolution state, search flags and ordered image-qualified provider scope. The individual detail ID and full search-context hash retain the symbol-specific distinction. Test and data reconciliation compare detail IDs, not just totals. Direct library callers and impact replay still receive individual findings unless they request a detail sink.

The SR target of at most 10,000 linking findings conflicts with keeping all existing DT_NEEDED checks individual. These alone numbered 34,576 in the WP-3 SR reference. The real run retains them and measures the reduction for the detail checks.

## 4. Test table

Reproduce with workspace-local scratch, the same WP-1 fixture tool paths as WP-3 and `COMPAT_RELEASE_CI=1`.

```sh
python3 -B -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -p 'test_wp3*.py' -v
python3 -B -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v
python3 -m compileall -q .agents/skills/tizen-image-compatibility
git diff --check
```

| Check | Result |
| --- | --- |
| Full regression | PASS. 381 run, 375 passed, six existing skips, zero failures. 394.786 s. |
| T-RC | Rootfs, ASan, loader/no loader, repository and bounded timeout reports have zero missing codes. The mutation control detects absent and malformed reason codes. |
| T-EXP-RC | All five primary incomplete-export reasons, timeout, output limit and combined conditions pass with name-free diagnostic classes. |
| T-CTX | Self references and different versions are excluded, repeated imports are counted by distinct object, and C, vtable and typeinfo classes match the fixture. |
| T-LINK-AGG | Complete native glibc fixture retains exact detail IDs and root counts. A confirmed missing symbol keeps an individual finding and detail anchor. |
| Negative grouping | State, consumer, image and provider search-context differences remain separate. |
| T-SIZE | Default changes CSV matches the prior non-MATCHED rows exactly, explicit all retains historical rows, summaries agree. |
| Legacy reader | The new SQLite index reconciled a real 54-finding report generated by the archived `0c40d40` source. |
| Compile and whitespace checks | PASS. Python compileall, Bash syntax for the kit, and Git diff checks. |
| Python 3.10 | BLOCKED. No local interpreter. The WP-4 CI gate is still open. |

## 5. Reason-code vocabulary

The full table maps codes to status, interpretation and next action in [correctness.md](../../../../.agents/skills/tizen-image-compatibility/references/correctness.md#wp-3b-reason-code-vocabulary).

| Area | Representative codes |
| --- | --- |
| Export | EXPORT_REMOVED, EXPORT_NOT_OBSERVED, EXPORT_INVENTORY_INCOMPLETE |
| GNU versions | VERSION_DEFINITION_REMOVED, VERSION_DEFINITION_NOT_OBSERVED, DEFAULT_VERSION_LOOKUP_LOST, DEFAULT_VERSION_CHANGED, DEFAULT_SYMBOL_VERSION_CHANGED |
| Coverage and tools | DIMENSION_NOT_EXECUTED, COVERAGE_LIMITATION, DWARF_ABI_UNAVAILABLE, DWARF_ABI_CHANGED, TOOL_TIMEOUT, OUTPUT_LIMIT |
| Export collection | READELF_DIAGNOSTIC, DYNSYM_ROWS_INCONSISTENT, VERSION_RECORDS_INCONSISTENT, HEADER_FIELDS_MISSING, OBJECT_INCOMPLETE |
| Linking | DT_NEEDED_CHANGED, LOADER_ENV_MISSING and the existing offline resolver state codes |

## 6. LINK-AGG before and after

| Executables in the same real glibc fixture | WP-3 findings | WP-3b findings | Detail rows |
| ---: | ---: | ---: | ---: |
| 5 | 43 | 23 | 32 |
| 20 | 103 | 83 | 62 |
| 80 | 343 | 323 | 182 |
| 500 | 2,023 | 2,003 | 1,022 |

The originally supplied PM fixture used different binaries and gives a separate reference. The detail totals above reconcile with the actual WP-3 checks on the same fixture. Scope checks, loader observations and DT_NEEDED entries retain their individual records.

### SR trial and independent replay

The first fresh run reached its 25-minute limit while staging root relations.
An I/O pressure sample showed 75.78% full pressure over ten seconds and the
analyzer was waiting on the filesystem. The shell recorded exit 137 after the
20-second termination grace. The 864 MiB scratch database is retained as
incomplete. The recovery stores sequential integer root relations in a
disposable database and indexes them after staging.

A separate real-data replay streamed the retained WP-3 observations through
the new anchor identity rule. It preserved the 519,784 detail rows, projected
61,970 anchors plus 41,783 individual findings, and retained the historical
11,490 confirmed incompatibilities. The replay checks aggregation against
saved evidence. Fresh analysis and independent reconciliation use separate
receipts.

### Fresh SR validation with the compact staging database

| Metric | WP-3 partial profiles | WP-3b same inputs and config |
| --- | ---: | ---: |
| All findings | 604,645 | 146,831 |
| Linking findings | 561,567 | 103,753 |
| Individual DT_NEEDED findings | 34,576 | 34,576 |
| Import/version rows | 519,784 findings | 519,784 detail rows |
| Aggregated symbol-check anchors | — | 61,970 |
| INCOMPATIBLE | 11,490 | 11,490 |
| Complete linking coverage | 0% | 0% |
| Wall time | 5:52.28 | 13:48.02 |
| Peak RSS | 6,549,796 KiB | 2,124,896 KiB |
| Full report bytes | 5,502,860,561 | 1,624,167,312 |

The fresh run kept 486,451 import rows and 33,333 GNU version rows.
The linking count dropped by 81.5%. The 10,000-finding target remains
unreachable under the mandated individual DT_NEEDED policy, and another
7,207 individual linking observations and 61,970 distinct context anchors
remain. Peak RSS fell by 67.6% to 2.03 GiB (2.18 GB), slightly above the
2 GiB interpretation of the target. Sampling shows about 1.56 GiB during
detail staging and a later high-water mark during coverage, package and
report assembly. Retained ELF inventories plus the growing coverage and
package structures are the main visible contributors. The samples do not
attribute individual Python allocations. The new report is 29.5% of the
WP-3 SR size.

Both normalized TAR hashes and the profile config hash passed verification
after the run. The analysis exit was 1 for the retained confirmed findings.
Independent streaming reconciliation matched every detail ID, check, state,
provider, root count and search-context hash against WP-3. Every detail
resolved to a current anchor, and the anchor counts reconciled exactly.
All 146,831 Finding CSV rows matched JSON. All 8,014 referenced evidence
files were present. The 11,490 confirmed comparison payloads matched the
prior report, and the result reported zero missing reason codes. Installed
RPM counts remained VD 719 and LLVM 736. The result SHA-256 is
`b4fc3a58f52e6118f6b97cc2f0de22d891717f8b5f355e141cc6a718c3566adc`.
Complete linking coverage remains zero.

## 7. RPT-SIZE-2

Same 1,001 RPMs and 1,501 ELF objects per side from the WP-3 scale fixture, reused byte for byte for an exact CSV comparison. Sizes are bytes.

| File | WP-3 | WP-3b |
| --- | ---: | ---: |
| results.json | 42,368,812 | 42,140,035 |
| baseline-manifest.json | 43,003,390 | 43,054,424 |
| candidate-manifest.json | 43,003,187 | 43,054,221 |
| symbol-differences.csv | 152,978,830 | 979 |
| elf-symbol-summary.csv | 1,342,557 | 1,342,557 |
| package-symbol-summary.csv | 158,662 | 158,662 |
| requirement-findings.csv | 914,180 | 914,180 |
| extraction-errors.csv | 58 | 58 |
| findings.csv | 2,677,578 | 2,677,641 |
| packages.csv | 925,192 | 925,192 |
| test-results.csv | 176 | 176 |
| index.html | 3,945,917 | 3,946,504 |
| summary.md | 78,340 | 78,403 |
| run-summary.json | 8,432 | 9,105 |
| rpm-repository.json | 1,779 | 1,857 |
| collection.log | 2,626,719 | 2,626,719 |
| .compat-run | 46 | 46 |
| evidence/ (4,016 files in each) | 14,692,816 | 14,692,816 |
| Complete report | 308,726,671 | 155,623,575 |

This is 50.4% of the WP-3 size, below the 60% gate. Every field of the one non-MATCHED row was equal. Both summaries count 151,599 MATCHED rows and one MISSING row. Final rerun elapsed time was 6:47.59 and peak RSS 418,984 KiB. All 4,016 raw evidence files matched the old report byte for byte by SHA-256.

## 8. Backup and push evidence

The kit and PM state backups `pm/20261127T062845Z` and `pm/20261127T062948Z` passed the checksum and bundle verifiers. The optional SR checkpoint and final implementation backup use the same workspace-local mechanism. `.local-backups/LATEST` identifies the final backup. Only main is pushed.

## 9. Open risks and new issues

Removal and binding policy depends on the real VD-1 detail breakdown. Real ASan positive evidence remains a VD-2 requirement. Python 3.10, Bubblewrap and real EROFS extraction remain WP-4 gates. The SR loader configuration contains offline cache observations with incomplete runtime scope.

## 10. Recommended next step

Have the PM review the detail and summary reconciliation, then use the published revision 5 kit to collect name-free VD-1 measurements from the same sample. Evaluate the removal and binding policy in WP-4 after receiving those measurements.
