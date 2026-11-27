# WP-3 acceptance report

## 1. Step 0 state

Local and remote main agreed at clean Addendum A commit `d9aa0803a3465f83b5d93cd2c15706c329b6cf4c`, the direct child of the requested `323e0e1b416494a94eac40182970612b6b96d987` code baseline. The PM accepted the Addendum A script with SHA256 `ee9b0b6c109f67b9dd27bb70bce053b542364cc7a8f27017382be9a6cdb49a1a`. Step 0 recorded the acceptance, copied the WP-3 prompt and pushed the documentation checkpoint `5d191e1da0a6091ae0aa9848c84b53e0a12422d1`. The WP-2 independent evidence and both host constraints were recorded at that checkpoint. [Decisions](../../DECISIONS.md) · [WP-2 report](../WP-2/REPORT.md) · [Prompt](PROMPT.md)

## 2. Changes per item

Implementation commit `853cadcb7107a159a0ca54dbf3dbb6312473c661`.

| Item | Implementation |
| --- | --- |
| F-06 | Cache DT_NEEDED decisions by the needed name, effective search paths, relevant loaded object and proof context. Memoize version/import checks with ordered lookup evidence. A finding records each distinct context and the root relation. |
| F-15 | ELF permission and capability evidence is collected when linking is enabled. Standalone security findings follow their dimension switch. |
| REQ-AGG | Keep each available-set failure or unknown in CSV. Group dependent version obligations at their missing SONAME and aggregate baseline-unsatisfied obligations per consumer and SONAME. |
| F-07b | Reuse the repository build profiles and per-pair instrumentation size rules in rootfs comparison. Keep the rootfs and repository result status separate from comparison validity. |
| F-09 | Add bounded extraction, RPM database and abidiff timeouts. Preserve timeout tool identity and process-group cleanup evidence. |
| F-21 | Add a validated metadata capture cap and per-archive OUTPUT_LIMIT evidence. |
| PORT-310 | Replace Python 3.11-only file hashing in ARM smoke admission and the demo generator. |
| RPT-SIZE | Stream machine JSON in compact form. Keep content-addressed evidence and the CSV payloads. The enhanced index reconciles both CSV layouts. |
| PROC-1 | Record prompt routing and the no-commit, no-push rule for ClineSR. |

### Exact changed-file list

```text
.agents/skills/tizen-image-compatibility/config.yaml
.agents/skills/tizen-image-compatibility/references/correctness.md
.agents/skills/tizen-image-compatibility/references/workflow.md
.agents/skills/tizen-image-compatibility/scripts/arm_smoke_admission/manage.py
.agents/skills/tizen-image-compatibility/scripts/compat/collect.py
.agents/skills/tizen-image-compatibility/scripts/compat/compare.py
.agents/skills/tizen-image-compatibility/scripts/compat/core.py
.agents/skills/tizen-image-compatibility/scripts/compat/coverage.py
.agents/skills/tizen-image-compatibility/scripts/compat/debuginfo.py
.agents/skills/tizen-image-compatibility/scripts/compat/erofs.py
.agents/skills/tizen-image-compatibility/scripts/compat/images.py
.agents/skills/tizen-image-compatibility/scripts/compat/linker.py
.agents/skills/tizen-image-compatibility/scripts/compat/package_analysis.py
.agents/skills/tizen-image-compatibility/scripts/compat/packages.py
.agents/skills/tizen-image-compatibility/scripts/compat/preparation.py
.agents/skills/tizen-image-compatibility/scripts/compat/report.py
.agents/skills/tizen-image-compatibility/scripts/compat/report_groups.py
.agents/skills/tizen-image-compatibility/scripts/compat/report_io.py
.agents/skills/tizen-image-compatibility/scripts/compat/report_store.py
.agents/skills/tizen-image-compatibility/scripts/compat/repository.py
.agents/skills/tizen-image-compatibility/scripts/compat/requirements.py
.agents/skills/tizen-image-compatibility/scripts/compat/rpm_payload.py
.agents/skills/tizen-image-compatibility/scripts/compat/run_summary.py
.agents/skills/tizen-image-compatibility/scripts/tizen_compat.py
.agents/skills/tizen-image-compatibility/tests/test_acceptance.py
.agents/skills/tizen-image-compatibility/tests/test_wp2.py
.agents/skills/tizen-image-compatibility/tests/test_wp3.py
docs/pm/CODEX_STATE.md
docs/pm/DECISIONS.md
docs/pm/HANDOVER.md
docs/pm/ISSUE_REGISTER.md
docs/pm/work-packages/WP-2/REPORT.md
docs/pm/work-packages/WP-3/PROMPT.md
docs/production-readiness/demo/generate_fixture.py
docs/pm/PM_STATE.md
docs/pm/work-packages/WP-3/REPORT.md
```

## 3. Deviations

The PM-approved kit is the documentation-only startup delta over the requested code baseline. The synthetic baseline linking counts below use the same fixture on `323e0e1`. The PM's original figures are retained as a separate reference from a different fixture. Existing `rpm_payload.timeout_seconds` overrides can further limit extraction, and VDFS keeps its separate timeout. The legacy findings CSV columns retain their order. New reports append reason and context fields. The v1.3 enhanced index can read both layouts.

The closure search still visits roots to preserve each process's load sequence and root relations. Requirement results are reused when their effective inputs match. A group view exposes an observed lower bound when root examples are truncated. Package associations are computed from the full in-memory relation before serialization. Strict mode still rejects UNKNOWN checks and unresolved coverage. The absence of thousands of duplicate HIGH rows does not establish linking coverage.

## 4. Tests

```sh
python3 -B -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -p test_wp3.py -v
python3 -B -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v
python3 -m compileall -q .agents/skills/tizen-image-compatibility docs/production-readiness/demo/generate_fixture.py
git diff --check
```

On Python 3.12.3 the full suite ran **375 tests in 190.511 s: 369 PASS, 6 SKIP, 0 FAIL**. The six skips are the existing real abidiff, explicit Clang AST/ARM, two separate Clang ARM/matrix tests, standard EROFS tools and Clang PCS integration.

Fixtures use GNU GCC/readelf, the trusted local SR Clang and RPM tools. The regression set uses `COMPAT_RELEASE_CI=1` and the four existing `WP1_*` tool fixture paths. `WP3_BASELINE_LINKER` points to the archived `323e0e1` linker source for the differential fixture. The production and test processes used workspace-local scratch directories in the recorded acceptance run. An initial targeted regression invocation used the interpreter's default transient directory. That invocation was discarded for sign-off and the tests were rerun with explicit workspace-local scratch.

| Check | Evidence |
| --- | --- |
| T-10 | Real glibc, interpreter and 500 identical ELF executables. The shared libc import checks are evaluated once per effective context. The executable's versioned puts import remains verified. |
| T-10b and cycle | Distinct root RUNPATH and loaded-object evidence produce separate compatible and incompatible observations for the same DSO dependency. The dependency cycle terminates. |
| T-10c | Two LOADER_ENV_MISSING rows. Linking coverage is NOT_EXECUTED and strict mode still fails. Markdown and JSON agree. |
| T-REQ | Both SONAME scenarios preserve all 33 diagnostic rows and retain two findings. The 31 dependent rows point to the SONAME anchor, and the independent SONAME failure remains. |
| T-08r and minority control | Actual GCC plain and Clang ASan ELF input. CONFOUNDED at image scale, UNKNOWN MEDIUM size for the instrumented pair, and INCOMPATIBLE removed function. The minority control retains a COMPARABLE image status. |
| T-TIMEOUT | A synthetic extractor with a child times out at 1 s. The objective is BLOCKED, with TOOL_TIMEOUT and VERIFIED local process-group cleanup. |
| T-META and invalid config | An output-limited archive does not prevent a second archive from completing. Invalid values are rejected. |
| SQLite fixture | Compact JSON and CSV reconcile. Twenty root examples from 21 affected roots are indexed and the exact group-level union remains unknown. |
| Python 3.10 | BLOCKED for runtime. The interpreter is absent. The syntax/API audit and the full host suite exercise the changes. WP-4 CI owns the interpreter run. |

## 5. Before and after counts

| Identical executables | PM v1.5.1 fixture | 323e0e1, same WP-3 fixture | WP-3 |
| ---: | ---: | ---: | ---: |
| 5 | 434 | 135 | 43 |
| 20 | 1,574 | 540 | 103 |
| 80 | 6,134 | 2,160 | 343 |
| 500 | — | 13,500 | 2,023 |

The same-fixture test evaluates the executable roots, the real interpreter and libc. Each extra root adds only its four own observations. Root-linked libc checks remain in the 23 shared observations. Without profiles the normal CLI reports one missing-profile finding per side. Static SONAME and DT_NEEDED deltas remain independent.

| Available-set case | Old findings | WP-3 emitted | CSV rows | Suppressed dependents |
| --- | ---: | ---: | ---: | ---: |
| Missing candidate SONAME with independent second SONAME failure | 33 | 2 | 33 | 31 |
| Also unsatisfied in baseline with independent second SONAME failure | 33 | 2 | 33 | 31 |
| Scale fixture, provider remains and a single versioned export is missing | 1,500 | 1,500 | 1,500 | 0 |

## 6. RPT-SIZE

Both synthetic generation runs use 1,001 RPMs and 1,501 ELF objects per side. Sizes are bytes. Reproduce with `python3 -B .agents/skills/tizen-image-compatibility/tests/wp2_scale.py "$WORK/scale"` in workspace-local scratch.

| File | WP-2 | WP-3 |
| --- | ---: | ---: |
| results.json | 68,667,296 | 42,368,812 |
| baseline-manifest.json | 70,938,455 | 43,003,390 |
| candidate-manifest.json | 70,938,102 | 43,003,187 |
| symbol-differences.csv | 152,978,830 | 152,978,830 |
| elf-symbol-summary.csv | 1,342,557 | 1,342,557 |
| package-symbol-summary.csv | 158,662 | 158,662 |
| requirement-findings.csv | 900,644 | 914,180 |
| extraction-errors.csv | 41 | 58 |
| findings.csv | 2,637,533 | 2,677,578 |
| packages.csv | 925,192 | 925,192 |
| test-results.csv | 176 | 176 |
| index.html | 3,884,020 | 3,945,917 |
| summary.md | 78,128 | 78,340 |
| run-summary.json | 7,878 | 8,432 |
| rpm-repository.json | 1,779 | 1,779 |
| collection.log | 2,626,719 | 2,626,719 |
| .compat-run | 46 | 46 |
| evidence/ (4,016 files in both runs) | 14,704,828 | 14,692,816 |
| Complete report | 390,790,886 | 308,726,671 |

The regeneration took 144.66 s with peak RSS 410,608 KiB. The three JSON files account for most of the 21.0% reduction. Future format work could replace repeated symbol attributes in the largest CSV with stable keys while retaining a full detail export. Per-package copies of symbol inventories in results.json and repeated symbol attributes in manifests could become resolvable references after a reader compatibility review. Preserve the existing SHA256 evidence references and raw bytes. Offer separate compressed transport for archives. The measured evidence byte difference comes from regeneration, independent of the compact JSON change.

## 7. Optional SR rerun

The optional profile uses the saved per-side on-disk cache observations and declares completeness false. The recorded target namespace, launch credentials and actual startup scope are still unavailable. Both analyses used fresh outputs and the original normalized headless TARs. [Historical Phase 8C configuration and source SHA256](../../../reviews/phase8c/COVERAGE_BEFORE_AFTER.md)

Reproduction uses the archived Phase 8C config plus the observed cache map for each side. Specify `model: glibc`, `environment_complete: false` and `cache_complete: false` for the partial-profile run. Preserve the original two-worker analysis and incomplete metadata declarations.

```sh
python3 -B .agents/skills/tizen-image-compatibility/scripts/tizen_compat.py \
  --baseline "$BASELINE_TAR" --candidate "$CANDIDATE_TAR" \
  --mode static --exclude performance --config "$CONFIG" --output "$NEW_REPORT"
```

The older Phase 8C run used a pre-WP-1 collector. The non-linking delta is five fewer observations in the new no-profile report. The confirmed count remains 11,490. Two confirmed export observations use the newer displayed GNU version-index suffix; the status and underlying interfaces agree. Other differences include complete export-inventory matches and two split-debug applicability observations. Finding IDs are tied to the current evidence and are compared by semantic observation across these collector generations.

The first profile run stopped at finalization. Its 137 duplicate IDs came from distinct symbol contexts in which a baseline root and a candidate provider shared the same virtual path and symbol attributes. The semantic cache had kept them distinct, but the serialized context had omitted the image side. The new regression fails before the fix and passes with image-qualified provider identities. The first failure receipt and diagnostic sample remain local.

| Metric | Phase 8C historical | WP-3 no profile | WP-3 partial profiles |
| --- | ---: | ---: | ---: |
| All findings | 903,377 | 44,142 | 604,645 |
| INCOMPATIBLE | 11,490 | 11,490 | 11,490 |
| All UNKNOWN | 868,069 | 8,830 | 569,333 |
| Linking findings and Linking UNKNOWN | 860,294 | 1,064 | 561,567 |
| Confirmed linking coverage | 0 | 0 | 0 |
| Installed RPMs, VD / LLVM | 719 / 736 | 719 / 736 | 719 / 736 |
| Wall time (s) | 261.50 | 152.16 | 352.28 |
| Peak RSS (KiB) | 3,868,380 | 1,311,780 | 6,549,796 |
| Report bytes | 5,863,545,262 | 1,241,020,869 | 5,502,860,561 |

| Linking UNKNOWN reason | Phase 8C | No profile | Partial profiles |
| --- | ---: | ---: | ---: |
| UNKNOWN_SYMBOL_SCOPE | 442,049 | 0 | 16,751 |
| UNKNOWN_SYMBOL_SEMANTICS | 314,185 | 0 | 469,700 |
| UNKNOWN_VERSION_REQUIREMENT | 57,107 | 0 | 33,333 |
| UNKNOWN_SEARCH_ENVIRONMENT | 43,785 | 0 | 38,744 |
| UNKNOWN_LOADER_ABI | 1,486 | 0 | 1,486 |
| LINKING_STATIC_DIFFERENCE | 1,062 | 1,062 | 1,062 |
| UNKNOWN_LOADER_FEATURE | 618 | 0 | 489 |
| UNKNOWN_COLLECTION | 2 | 0 | 2 |
| LOADER_ENV_MISSING | 0 | 2 | 0 |

The no-profile run began before the image-qualified context fix, which is confined to checks with a loader profile. The successful partial-profile rerun used the final implementation. The no-profile run had two unexecuted linking obligations. The partial profiles produced 2,052 partial obligations and zero complete ones. A streamed comparison verified every original JSON/CSV field in both new reports and found all 7,882 and 8,014 referenced evidence files respectively.

The saved cache entries allow the model to observe more candidate providers, shifting observations from missing symbol scope to unknown symbol semantics. Both runs retain zero complete linking coverage. The CLI exited 1 on the confirmed static findings, with no infrastructure failure. Both normalized input TAR SHA256 checks passed after the runs. Configuration SHA256 was `485e8042d09f4a39e14fb13bebde2ca2bb1e4e85265bd65d7094b5e97ad77c45` without profiles and `921a3021a1154c57cc51b2b8eea3cf439c05a05212606e8465c3282167a249d7` with partial profiles. Timings are single-host observations and include the release code's different collection and reporting overhead.

## 8. Backup and push evidence

Step 0 archive `pm/20261127T054422Z` passed SHA256 and bundle verification. The optional SR run has a separate before and after workspace checkpoint. The final verified backup is selected by `.local-backups/LATEST`. The only GitHub update ref is `refs/heads/main`.

## 9. Open risks and new issues

Full Python 3.10 execution requires WP-4 CI. WP-4 also owns the independent Bubblewrap 0.6.1 EROFS failure and real extraction acceptance. RPM and glibc tests use synthetic contracts. The SR profile contains partial cache observations and supplies no runtime clearance. The exact report union across truncated root examples is unavailable in the offline index. The partial-profile SR findings CSV reached 1,285,538,965 bytes with the added context. The complete report is smaller than the historical report, but a partial loader profile still costs time and space.

## 10. Recommended next step

Independently review the WP-3 fixtures and SR deltas, then use the frozen Addendum A kit for VD-1 measurement. Keep the measured linking volume and Python 3.10 plus EROFS results as inputs for WP-4 before any release-candidate decision.
