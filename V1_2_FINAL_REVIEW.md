# v1.2 final PR review — local release candidate

Date: 2026-11-17 (America/Los_Angeles). Reviewed PR: [#1](https://github.com/lhmax2010/Image-Compatibilty-Skill/pull/1), head `d5085a5ff0cc3231c8f4228aafd338ab6ad2ae50`. Initial tracked tree was clean; `design.md` and `require.md` were pre-existing untracked inputs. Local branch was named 1.1 but already pointed at that reviewed head; local `review/tizen-compatibility-correctness-1.2` was created at the same commit. Main and the remote PR were not changed. These corrective changes remain uncommitted and unpublished.

The existing 120-test suite passed before changes. All five issues were independently reproduced against the reviewed production implementation before any production edit, using [reproduce_final_review.py](.agents/skills/tizen-image-compatibility/tests/review/reproduce_final_review.py). Raw observations are [rc-before.json](.agents/skills/tizen-image-compatibility/tests/review/rc-before.json) and [rc-after.json](.agents/skills/tizen-image-compatibility/tests/review/rc-after.json). The script compiles only its own synthetic source; it does not execute target artifacts.

## Finding disposition

| Finding | Before correction | Minimal correction and observed result | Assessment |
|---|---|---|---|
| Major 1 — ARM architecture | Matching EABI/base PCS, v6 probe versus v7 SDK tag: INCOMPATIBLE solely because cpu_arch differed. | CPU tags are assessed separately from calling conventions. Different/missing tags yield ISA UNKNOWN, not a fabricated ABI conflict. Matching tags establish attribute agreement only; hardware remains unverified. Explicit EABI/PCS/endian conflicts still fail. | **PASS** |
| Major 2 — Explicit probes | Planner declared an explicit C probe with built-ins disabled, but production scheduler compiled zero probes. | Scheduler uses explicit per-language probe requests independently of built-in toggles. Built-ins/header probes stay disabled. Reproducer now builds one explicit probe. Full C/C++ GCC/Clang harness fixture reconciles all 12 expected/actual IDs without duplicates or unexpected IDs. | **PASS** |
| Major 3 — Resolution metadata | Missing completeness marker allowed import:f to be COMPATIBLE. | Explicit boolean true is required on relevant consumer/provider/loader observations. Collector establishes it from successful untruncated dynamic readelf evidence and full dynamic-symbol row counts. Missing marker now gives UNKNOWN; explicit sufficient evidence can still confirm success or missing symbols. | **PASS** |
| Minor 1 — Candidate additions | An untested candidate-only package had status COMPATIBLE despite its explanatory caveat. | Separate inventory_status=ADDED from compatibility status=UNKNOWN. Matched packages do not enter additions. | **PASS** |
| Minor 2 — Missing interfaces preview | A missing-interface finding after the first 1000 global findings was absent from its dedicated preview. | Filter matching findings before the cap, display total/shown/hidden counts. Reproducer now shows the late missing ID; machine record count remains 1001. Dedicated regression checks 1002 missing records after 1000 unrelated findings. | **PASS** |

## Code and proof boundaries

Production patches are limited to `compat/elf.py`, `testing.py`, `linker.py`, `package_analysis.py`, `report.py` and `core.py`. `matrix_manifest.py` was inspected: its explicit-probe planning was already correct, so it was not rewritten. Existing architecture, dimensions and authorization boundaries are preserved.

ARM diagnostics add `abi_status`, `isa_assessment` and `hardware_assessment`. CPU tags describe permitted ISA requirements, with architecture profiles/extensions and nontrivial compatibility relationships. Equality does not validate target hardware; inequality does not automatically imply a calling-convention break. This patch deliberately does not add a CPU capability solver or infer a hardware maximum from another compiled object. Reference: [Arm ABI build attributes](https://github.com/ARM-software/abi-aa/blob/main/addenda32/addenda32.rst#the-target-related-attributes).

The resolution marker attests collected evidence within the existing bounded lookup model, not complete glibc semantics. Readelf warnings, truncation, missing dynamic-section output, inconsistent symbol-row counts and unavailable tools cannot establish the marker. ELF header completeness alone is insufficient. Manifest markers must be boolean; missing markers remain untrusted, and schema 1.0/1.1 migration continues to invalidate old lookup credit. Collector version `1.2.0-rc.1` invalidates earlier cache keys while report schema remains 1.2. Existing export-surface evidence is still reported independently of unknown lookup context.

Two old synthetic fixtures now explicitly declare the complete lookup metadata they model (`test_correctness.obj` and `test_soname_difference_and_needed`). Their success/failure assertions were retained. New negative cases remove the marker or supply false/nonboolean values; production checks were not relaxed to recover test passes.

## Regression evidence

All new cases are in [test_release_review.py](.agents/skills/tizen-image-compatibility/tests/test_release_review.py), class `ReleaseReviewTests`:

| Exact test function | Evidence exercised |
|---|---|
| `test_arm_different_arch_is_unknown_not_calling_convention_break` | Same CPU tag positive; v6/v8/v7E-M/missing tag unknown with ABI still compatible, hardware unverified |
| `test_arm_abi_conflict_survives_isa_uncertainty` | EABI, PCS and endian negatives remain incompatible |
| `test_real_arm_v6_v7_and_vfp_fixtures` | Actual Clang ARMv6/ARMv7 soft and ARMv7 hard objects, readelf and compiler macro evidence; no ARM execution |
| `test_explicit_c_and_cpp_schedule_with_builtin_toggles_disabled` | Actual GCC/G++ compile/link, exact build IDs, no built-ins, unexecuted runtime unknown, source hashes unchanged |
| `test_missing_custom_compiler_and_disabled_execution_keep_expected_ids` | Available C probe executes compilation; unavailable C++ compiler leaves its planned test unknown/missing |
| `test_explicit_probes_exact_matrix_ids_with_simulated_receipts` | Actual GCC/Clang C/C++ compile/link; 12 exact IDs; simulated adapter receipts only, never target execution |
| `test_resolution_marker_required_on_consumer_and_provider` | Missing/false/string/integer marker negatives; explicit true positive; confirmed missing-symbol negative |
| `test_collector_establishes_resolution_evidence_and_rejects_partial_output` | Actual GCC DSO/readelf positive; controlled truncated/warning/missing-section/incomplete-row output negatives and unavailable readelf |
| `test_old_and_incomplete_manifest_never_invents_resolution_marker` | Schema 1.2 missing marker, invalid marker type and 1.1 migration |
| `test_candidate_addition_is_inventory_added_with_unknown_compatibility` | Candidate-only added/unknown versus matched package |
| `test_missing_preview_filters_before_limit_and_keeps_machine_data` | Correct filtered prefix, exact total/shown/hidden, full JSON/CSV IDs with 2002 findings |

## Final execution results

- Baseline: **120 passed, 0 failed, 0 skipped** — [baseline output](.agents/skills/tizen-image-compatibility/tests/review/rc-baseline-tests.txt).
- Final: **131 passed, 0 failed, 0 skipped** — [full output](.agents/skills/tizen-image-compatibility/tests/review/rc-tests.txt). Unittest time 4.470 s; whole command wall 4.55 s, peak RSS 88,196 KiB; exit 0 — [metrics](.agents/skills/tizen-image-compatibility/tests/review/rc-test-metrics.txt).
- Existing tests independently cover package ownership, RPM count reconciliation, linker positives/negatives, stage/coverage gates, manifest reuse, source/rootfs/SDK hash preservation and direct target-runner rejection. Optional actual Clang 14/libabigail 2.4 tests ran, not skipped.
- Existing stress verifier: **2000 package pairs, 22201 findings, 2000 consumer/provider edges**; JSON/CSV exact IDs and status/ownership consistency, complete package rows, HTML/Markdown previews and budgets passed. Wall **3.707 s**, peak **366.2 MiB**, exit 0. [Raw metrics](.agents/skills/tizen-image-compatibility/tests/review/rc-scale.json).
- Static checks, configuration validation, local links and freeze fingerprint are recorded in `tests/review/rc-checks.json` and `rc-source-sha256.json`.

Commands run from the repository root:

```bash
python3 .agents/skills/tizen-image-compatibility/tests/review/reproduce_final_review.py

/usr/bin/time -f 'exit_code=%x\nwall_seconds=%e\npeak_rss_kib=%M' \
  -o /tmp/tizen-rc-final.metrics \
  env COMPAT_TEST_ABIDIFF=/tmp/tizen-correctness-tools/abidiff \
      COMPAT_TEST_CLANG=/tmp/tizen-correctness-tools/clang \
  python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v \
  > /tmp/tizen-rc-final.log 2>&1

python3 .agents/skills/tizen-image-compatibility/tests/review/benchmark_v12.py \
  --packages 2000 --symbols 10 \
  --reference .agents/skills/tizen-image-compatibility/tests/review/v12-acceptance-scale-2000.json \
  --max-regression-factor 2 --output /tmp/tizen-rc-scale-2000
```

The `/tmp/tizen-correctness-tools` wrappers are existing local tools, not bundled dependencies. Substitute equivalent paths elsewhere. Large stress reports are outside the repository. Historical generated examples remain historical artifacts; new generated reports use the corrected preview semantics.

## Frozen scope and limitations

All five findings are closed locally with positive/negative evidence. No new dimensions, runtime adapter, privileged operations or real Tizen execution were added. Full glibc namespace/interposition/IFUNC behavior, exhaustive API semantics, automatic package lineage/solver, hardware capability and production runtime behavior remain limited or unknown as previously documented. Unknown ISA suitability can still block a compiler matrix probe; the static rootfs comparison remains available.

Recommendation and product inputs: [V1_2_RELEASE_READINESS.md](V1_2_RELEASE_READINESS.md), [proposed static input record](V1_2_STATIC_ACCEPTANCE_INPUT.json). Exact files changed relative to reviewed commit d5085a5 are listed in [rc-changed-files.txt](.agents/skills/tizen-image-compatibility/tests/review/rc-changed-files.txt). No publication or merge is authorized by this readiness assessment.
