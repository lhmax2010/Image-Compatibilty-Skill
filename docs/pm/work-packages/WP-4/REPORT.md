# WP-4 implementation and release candidate verification

## 1. Step 0 state

Local and remote `main` matched `26336721a13dc3e08e964a5fc8bd3e15218e6493` with a clean worktree. Step 0 copied the assigned prompt, recorded the accepted WP-3b checks, VD-1b measurements and both policy decisions, then backed up and pushed `4bebed633420b758356c8384d32ddbc144ca2d5f`. [PM evidence](../WP-3b/PM_REVIEW.md)

## 2. Changes and commit identities

| Item | Implementation |
| --- | --- |
| COPY-REL | `compat/elf.py` recognizes defined version requirements corroborated by COPY relocations in static mode. Provider checks in `requirements.py` and `linker.py` require the exact version and data size. ELF inventory revision 7 invalidates older cached inventories. |
| POL-BINDING | `compat/symbol_rules.py` applies D-POL-BINDING in the active loader context. |
| POL-WEAK | `compat/weak_review.py`, comparison and report paths apply D-POL-WEAK, export the review table, and restrict decisions to eligible matching review IDs. |
| DT-AGG | `compat/linker.py`, `linking_details.py` and `coverage.py` aggregate non-breaking dependency findings and keep exact checks and their anchor IDs in the detail CSV. |
| RPT-SIZE-3 | `compat/report_io.py`, report readers and writers, and RPM export paths use gzip manifests and raw-byte evidence identities, resolve symbol references, and retain counts for filtered rows. |
| F-08 / K-05 | `compat/erofs.py` probes Bubblewrap, confines the fallback directory and checks free space. `make_erofs_fixture.sh` prepares standard test images on an equipped host. |
| SUITE-ARM | `6434bdf07a3e4a9396297dcdbfcbcf599282bfd4` published the tested ClineSR runner. |
| Packaging | `VERSION` is `1.5.3-rc1`. The implementation commit is `8b948dd0fa98bf74fbae6dbda04a922b8696d1d5`. It includes the six code items above, the focused and updated tests, CHANGELOG and Skill settings. |

## 3. Deviations and measurement controls

- The CLI now accepts `--reuse REPORT_DIR` alongside the existing paired manifest flags. The archived WP-3b and compressed WP-4 reports both replayed.
- The first SR run was stopped after its invocation was found to omit the historical `--exclude performance` flag. The measured run used the original configuration, explicit exclusion, the same TARs and a fresh output directory. The abandoned attempt remains local.
- The older VD-1 kit revision 5 remains pinned. Its archived `rerun` command can launch the RC. Its original detail reader expects plain manifests, so for the RC use the new report's summary counters and total bytes, or inspect the gzip manifests locally. Keep RPM names, symbol names, paths and raw logs local.

## 4. Test results

| Requirement | Outcome | Evidence |
| --- | --- | --- |
| T-COPY and T-VERNORM | PASS | Real x86-64 non-PIE `optind` and build-only ARMv7 `R_ARM_COPY` fixtures reached COMPLETE. Missing verneed, missing corroboration, wrong version, wrong size and unproven rootfs scope tested. Raw readelf keeps the index suffix. |
| T-BIND, T-WEAK and T-REVIEW | PASS | Defined weak/global rules, UNIQUE and loader exception, removal controls, CSV/HTML/Markdown, exact decision matching and immutable reviewed CSV. |
| T-DTAGG | PASS | Synthetic details match the pre-aggregation checks. A confirmed missing provider stays individual. Real SR totals are below. |
| T-SIZE3 | PARTIAL | Per-file and row reconciliation below. Tested the compact symbol resolver in the enhanced index and a 54-finding legacy report. |
| T-EROFS | PASS / BLOCKED | Synthetic old-Bubblewrap rejection, success/failure cleanup and storage-gate trials passed. A confined host extractor fixture passed with Bubblewrap 0.9.0. Standard filesystem extraction requires `mkfs.erofs` and `fsck.erofs`, absent here. The generator stopped at admission with exit 3. |
| T-SUITE | PASS / BLOCKED | A copy of the repository ran the archived WP-3b suite with 381 tests, six skips and zero failures or errors. Outside WORK was rejected before creation. A deliberately failing archive tests failure and error IDs without leaking fixture stderr. Native Python 3.10 execution awaits ClineSR. |
| Full regression | PASS | Python 3.12.3, 391 tests, 385 passed, 6 skipped, 0 failures and 0 errors. Compileall, shell syntax and Git diff check passed. |

The full regression used `python3 -B -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v` with `COMPAT_RELEASE_CI=1` and the existing admitted SR SDK wrappers. The six existing skips cover optional libabigail, the explicit Clang integration, GCC/Clang probe tooling, Clang ARM ISA, Clang ARM PCS, and standard EROFS. The ARM copy fixture uses GCC 14.2.0 and GNU binutils 2.43 from the preserved SR SDK. Its ELF32 executable evidence includes SHA-256 `e84d12f110a53461456961d78f7a130d812dad17c131c0a724e90f064e50b630`.

## 5. Policy fixture counts

| Status and reason | Before | WP-4 default | After review CSV |
| --- | ---: | ---: | ---: |
| INCOMPATIBLE / EXPORT_REMOVED | 6 | 3 | 3 |
| UNKNOWN LOW / WEAK_CXX_EXPORT_REMOVED_UNREFERENCED | 0 | 3 | 1 |
| COMPATIBLE / WEAK_CXX_EXPORT_REMOVAL_ACCEPTED | 0 | 0 | 1 |
| INCOMPATIBLE / WEAK_CXX_EXPORT_REMOVAL_REJECTED | 0 | 0 | 1 |

The fixture includes a template, vtable, and ordinary weak C++ function with no observed importer. An imported weak C++ symbol, a global and a weak C export remain INCOMPATIBLE. The legacy policy restores all six original removal grades. The decision fixture also reports one unmatched ID.

| Defined binding fixture | Before | After |
| --- | --- | --- |
| GLOBAL to WEAK | UNKNOWN HIGH / SYMBOL_BINDING_CHANGED | COMPATIBLE INFO / SYMBOL_BINDING_WEAKENED |
| WEAK to GLOBAL | UNKNOWN HIGH / SYMBOL_BINDING_CHANGED | COMPATIBLE INFO / SYMBOL_BINDING_STRENGTHENED |
| UNIQUE to WEAK | UNKNOWN HIGH / SYMBOL_BINDING_CHANGED | UNKNOWN MEDIUM / GNU_UNIQUE_DROPPED |
| GLOBAL to WEAK, `ld_dynamic_weak: true` | UNKNOWN HIGH / SYMBOL_BINDING_CHANGED | UNKNOWN MEDIUM / DYNAMIC_WEAK_SEMANTICS |

Each binding row has one observation. The copy fixture produces one proven COPY_RELOC_SIZE_CHANGED when the provider grows and no size failure when the exact version and size match.

## 6. DT-AGG SR partial-profile rerun

| Metric | WP-3b | WP-4 |
| --- | ---: | ---: |
| Total findings | 146,831 | 126,067 |
| Linking findings | 103,753 | 82,992 |
| DT_NEEDED individual checks in the main findings | 34,576 | 0 |
| DT_NEEDED check rows in the detail CSV | 0 | 34,576 |
| Total linking detail rows | 519,784 | 554,304 |
| Verified Linking coverage units | 0 | 0 |
| Wall time | 13:48.02 | 11:42.53 |
| Peak RSS, KiB | 2,124,896 | 2,048,512 |
| Installed RPMs, VD / LLVM | 719 / 736 | 719 / 736 |

The 80,000 Linking target missed by 2,992 findings. The 34,576 DT_NEEDED checks
became 13,871 dependency groups. The 61,914 symbol groups and 7,207 other
Linking observations remain in the main report.
WP-4 keeps distinct search contexts and conservative partial-profile grades.
519,668 of 519,784 earlier detail rows match the original ID, consumer, state, provider, root count and search-context hash.
34,576 of 34,576 formerly individual DT_NEEDED findings retain their exact ID in the new detail CSV.
The 116 earlier detail rows outside that exact match comprise 58 prior import observations
over two symbol identities and 58 surviving IDs whose root counts changed after
the former copy storage stopped contributing an export to the symbol scopes. The
replacement report adds two explicit copy requirements. Each detail anchor resolves to a current finding.
The input TARs and configuration passed their recorded SHA-256 checks before and after the run.
The current results JSON SHA-256 is `aa6153f30b9e94027a53a22e76ddad2fb3c889a3f65b10a860e70d6a2321d214`.

| Status | WP-4 SR findings |
| --- | ---: |
| COMPATIBLE | 23,612 |
| IDENTICAL | 336 |
| INCOMPATIBLE | 1,477 |
| NOT_APPLICABLE | 2 |
| UNKNOWN | 100,640 |

10,011 weak C++ removals await owner review. 1,477 prior confirmed observations preserve their entire original payload.

Confirmed status changes by reason

- `EXPORT_REMOVED` has 10,013 former IDs absent from the confirmed set and 0 new confirmed IDs. The 10,013 comprise 10,011 owner-review rows and two old false exports now identified as versioned copy storage.

| SR policy status and reason | WP-3b | WP-4 |
| --- | ---: | ---: |
| `COMPATIBLE/SYMBOL_BINDING_WEAKENED` | 0 | 125 |
| `INCOMPATIBLE/EXPORT_REMOVED` | 11,490 | 1,477 |
| `UNKNOWN/GNU_UNIQUE_DROPPED` | 0 | 1,481 |
| `UNKNOWN/SYMBOL_BINDING_CHANGED` | 1,606 | 0 |
| `UNKNOWN/WEAK_CXX_EXPORT_REMOVED_UNREFERENCED` | 0 | 10,011 |

## 7. RPT-SIZE-3 file table

Logical bytes sum all output files and exclude temporary scratch from completed reports.
The manifest rows show the original JSON and the replacement gzip files.

| Entry | Scale WP-3b | Scale WP-4 | SR WP-3b | SR WP-4 |
| --- | ---: | ---: | ---: | ---: |
| `.compat-run` | 46 | 46 | 46 | 46 |
| `baseline-manifest.json` | 43,054,424 | 1,694,957 | 171,885,577 | 14,513,846 |
| `candidate-manifest.json` | 43,054,221 | 1,694,944 | 183,768,818 | 15,439,809 |
| `collection.log` | 2,626,719 | 2,626,719 | 4,409,858 | 4,410,300 |
| `elf-symbol-summary.csv` | 1,342,557 | 1,342,557 | — | — |
| `evidence` | 14,692,816 | 3,653,788 | 317,712,259 | 53,248,734 |
| `expected-tests-results.json` | — | — | 50,447 | 50,447 |
| `expected-tests.json` | — | — | 19,695 | 19,695 |
| `extraction-errors.csv` | 58 | 58 | — | — |
| `findings.csv` | 2,677,641 | 2,677,641 | 172,420,652 | 149,786,454 |
| `index.html` | 3,946,504 | 3,946,543 | 13,907,239 | 16,850,790 |
| `linking-details.csv` | — | — | 123,502,142 | 131,569,091 |
| `package-symbol-summary.csv` | 158,662 | 158,662 | — | — |
| `packages.csv` | 925,192 | 925,192 | 15,712,774 | 14,871,530 |
| `requirement-findings.csv` | 914,180 | 926,190 | — | — |
| `results.json` | 42,140,035 | 42,140,671 | 620,690,465 | 556,872,387 |
| `rpm-repository.json` | 1,857 | 1,969 | — | — |
| `run-summary.json` | 9,105 | 9,609 | 13,132 | 13,597 |
| `summary.md` | 78,403 | 78,430 | 74,032 | 63,069 |
| `symbol-differences.csv` | 979 | 979 | — | — |
| `test-results.csv` | 176 | 176 | 176 | 176 |
| `weak-export-review.csv` | — | 193 | — | 5,593,219 |
| **Total bytes** | 155,623,575 | 61,879,324 | 1,624,167,312 | 963,303,190 |

The scale output is 39.76% of WP-3b (PASS at 40% and 62 MB).
The SR output is 59.31% of WP-3b (MISS at 50%).
Scale wall time was 3:13.55 and peak RSS was 415,412 KiB. Its results JSON SHA-256 is `eaa852b7702389861fd80d70de1424600b6a1843b9e3add8e5eda35c311152a3`.

- The independent checker restored compact JSON symbols and compared every retained finding field in CSV and JSON. Scale had 4,004 matching rows and SR had 126,067.
- The scale symbol CSV preserved the same one non-matching row. All 1,500 unavailable-requirement records preserved their old columns, and the new copy-size column is appended. The summary counts all 151,500 satisfied requirements. The other seven compared CSVs were byte-identical.
- Decompressing all 4,016 scale and 8,760 SR evidence files recovered every stored raw SHA-256. The scale evidence set preserved all 4,016 original content identities. Every finding evidence reference resolves.
- The VD 150-package sample and the full 5,693-RPM repositories are pending. The synthetic and SR results measure different workloads.

The SR report is 151,219,534 bytes above its 50% budget. Gzip removed most
manifest and evidence bytes. Expanding the dependency detail and owner-review
tables retains information that still contributes to the total. Retained results JSON, finding CSV and linking detail CSV account for 838,227,932 bytes.

## 8. ClineSR runner SHA-256

Published `docs/pm/clinesr/run_suite.sh` SHA-256 `99d5a0115c1c6e190f4a27e60d2894796481dc6e675ba6cb3f1dde7954cd091f`.
Use the assigned full RC commit after the owner instructs ClineSR to fetch main.
The runner archives that commit and keeps raw logs within `.local-work`.
Only the bounded Python version, test counts, failing test IDs and terminal status are for forwarding.

## 9. Backup and publication

Step 0 backup `pm/20261127T095156Z` and Step 7 backup `pm/20261127T100205Z` passed SHA-256 and Git bundle verification.
The final main backup is selected by the workspace-local `.local-backups/LATEST`.
Each publication uses a normal push of main. The RC uses the published commit and the verified local bundle.

## 10. Open risks and issues

- SUITE-ARM remains open for a native Python 3.10 receipt.
- F-08 / K-05 remains open for real standard-EROFS extraction. Unknown EROFS feature bits continue to fail closed.
- VD-2 still needs the RC's native sample measurement, full report size and weak-export owner review. PERF-LINK remains P2. Repository parallelism remains deferred.
- Partial SR loader facts retain incomplete Linking coverage. The report measures static implementation behavior for the recorded scope.

## 11. Recommended next step

Have ClineSR run the published suite on Python 3.10 at the assigned RC commit, then repeat VD-1b using the same sample and report only sanitized counts, size and timing. Use the fixture generator on an equipped host to close the standard-EROFS check. Carry any pending weak-export decisions and the measured full-repository projection into the VD-2 acceptance.
