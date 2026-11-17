# v1.2 release-candidate readiness

**READY FOR REAL TIZEN STATIC ACCEPTANCE**

This is readiness to begin product-specific static testing, **not proof of GCC/LLVM image compatibility**. All five PR #1 findings pass local regression acceptance. The frozen local candidate is collector `1.2.0-rc.1`, schema 1.2, based on reviewed commit `d5085a5`. It has not been committed, pushed or merged. Final evidence and exact changed files are in [V1_2_FINAL_REVIEW.md](V1_2_FINAL_REVIEW.md).

| Gate | Assessment |
|---|---|
| ARM ABI versus ISA/hardware distinction | PASS |
| Explicit C/C++ probe scheduling and exact expected IDs | PASS |
| Explicit collected symbol-resolution metadata | PASS |
| Candidate inventory addition versus compatibility | PASS |
| Missing-interfaces filtered preview and complete machine data | PASS |
| Complete existing + new regression suite | PASS — 131/131, no skips |
| Package ownership, counts, dependency attribution, coverage/ID gates | PASS — existing regression suite and independent stress verifier |
| JSON/CSV/HTML consistency and source immutability | PASS — exact records/previews and source hashes tested |
| Actual Tizen images / SDK / target hardware | NOT TESTED — product inputs are still required |

## Proposed real-product static acceptance input

Fill [V1_2_STATIC_ACCEPTANCE_INPUT.json](V1_2_STATIC_ACCEPTANCE_INPUT.json) before running the product comparison. It is an operator input/provenance record, **not** a CLI config or an executable request. Its `static_config` object is a supported CLI configuration subset; export that object to a separate JSON file for `--config`.

Required product information:

1. Baseline and candidate extracted rootfs paths; immutable source archive/hash records; exact build IDs, compiler provenance and sanitizer/instrumentation settings. Confirm the baseline-consumer → candidate direction. Filenames alone do not establish compiler provenance.
2. Actual installed RPM database locations and independent package/NEVRA/file-list exports, including expected source counts. A missing DB remains unknown; archives are not installed packages. Source snapshots must be stable during analysis.
3. Matching available debuginfo paths and build provenance for type/layout analysis. Missing data stays UNKNOWN. Supply explicit SDK provenance and installed development-package manifests if claiming SDK ownership; runtime-only images cannot establish full API semantics.
4. Intended ARM EABI, base/VFP PCS, CPU/ISA profile and product hardware evidence. A CPU architecture tag on a runtime object is not proof of the hardware's full capabilities. For this static-only acceptance no hardware execution is claimed.
5. Actual loader search/cache/namespace evidence if asserting a complete supported startup environment. Otherwise keep the loader environment unknown and review the resulting gaps. Do not manually set ELF completeness flags to obtain a pass.
6. Product-owner-approved required contracts, severity/coverage thresholds and documented exclusions/unknowns. The template deliberately does not invent acceptable coverage percentages; an empty threshold map is not approval.

## Static-only execution proposal

After input review, export `static_config`, supply actual loader/debuginfo/tool configuration as appropriate, and run:

```bash
python3 .agents/skills/tizen-image-compatibility/scripts/tizen_compat.py \
  --baseline /approved/baseline-rootfs --candidate /approved/candidate-rootfs \
  --mode static --config /approved/static-config.json \
  --cache /outside-images/compat-cache --output /outside-images/new-static-report
```

Paths above are placeholders, not directories validated by this task. The template disables runtime and compilation and excludes header-compilation/runtime/performance dimensions from the static scope. Offline API/header inventory remains included. No target execution, flashing, sudo, source-image writes or adapter implementation is implied. Supply a fresh/empty output directory outside images/SDKs. Current schema 1.2 manifests lacking resolution markers need recollection; earlier ELF cache keys are invalidated by the RC collector version.

Acceptance review of that **future** product run must reconcile actual installed package counts, retain every unowned/unverified record, trace confirmed failures to consumers/providers, inspect full JSON/CSV rather than only capped HTML, check coverage denominators and source hashes, and independently review every critical unknown. An exit 0 only means configured gates were not triggered.

## Remaining limitations and freeze

The checker remains conservative for differing/missing ARM ISA tags, unavailable hardware capability, incomplete or warned readelf output, unsupported loader scope/interposition/IFUNC, absent debug types, source API semantics, renamed/split packages and runtime/system behavior. These limits do not block beginning static product testing; they block unsupported compatibility claims.

Source/test hashes are recorded in `tests/review/rc-source-sha256.json`. Further functional changes would require a new review/test record. The current local tree is ready for review and later publication only after authorization. Main, remote branches and PR state remain unchanged by this stabilization task.
