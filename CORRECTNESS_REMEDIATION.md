# Correctness remediation

The existing collector → manifest → comparison → optional tests → report architecture is retained. Collector version is **1.1.0**, manifest/report schema **1.1**. This document records the local remediation before publication. Publishing a review branch is a separate step and does not merge main.

## Implementation map

| Review item | Implementation | Observable change |
|---|---|---|
| F1 loader | `compat/linker.py`; collector loader environment/config evidence | Explicit modeled search/closure/import outcomes instead of rootfs-wide SONAME presence |
| F2 versions | `compat/elf.py`, `compat/compare.py` | Lossless raw versions, definition inheritance and provider requirements; separate default/explicit lookup |
| F3 matrix | `compat/testing.py`, config validation | Explicit SDK/native reference/build provenance, ARM PCS/EABI validation, SDK headers, per-stage receipts |
| F4 DWARF | `compat/debuginfo.py` | Build-ID-verified split files/extracted RPM roots; per-object UNKNOWN; staged read-only analysis |
| F5 API | `compat/semantic.py`, lexer comparator | Optional Clang AST/context evidence; token equality no longer semantic pass |
| F6 coverage | `compat/coverage.py`, report/CLI | Contract denominator/counts/percentages, configurable quality gate, conservative old-manifest import |

The old comparison entry points `dependency_checks` and `advanced_abi` remain importable from `compare.py`. New modules isolate the larger algorithms without replacing unrelated collectors, adapters or packaging logic.

## Intentional classification changes

1. Provider presence outside the known search paths now fails the scoped dependency check. An unspecified search environment stays UNKNOWN rather than silently accepting a SONAME.
2. `foo@VER` and `foo@@VER` stay distinct raw records. Explicit version imports may use either definition role; bare/default lookup is a separate obligation. Removed exports are not dismissed based on ASAN, C++ or generated names.
3. A successful adapter process without a validated receipt is UNKNOWN. Failed native-reference behavior invalidates compatibility credit on both destinations.
4. No per-library DWARF/tool coverage means a visible UNKNOWN layout obligation. An ABI difference bit without a confirmed incompatible bit remains UNKNOWN.
5. Identical normalized headers remain semantic UNKNOWN. Compile success is explicitly limited to that compiler/SDK/probe, and AST equality is not claimed as complete API compatibility.
6. New coverage thresholds can fail a run that previously returned 0. Strict mode also checks unverified coverage units. Existing severity thresholds retain their meaning.
7. Schema 1.0 still loads, but successful old test/matrix observations are downgraded to UNKNOWN pending revalidation. Old failures remain failures. ELF cache keys change with collector version.

## Configuration and operation

See the updated [config.yaml](.agents/skills/tizen-image-compatibility/config.yaml), [correctness contract](.agents/skills/tizen-image-compatibility/references/correctness.md), [execution adapter contract](.agents/skills/tizen-image-compatibility/references/execution.md), and [schema](.agents/skills/tizen-image-compatibility/references/report_schema.md).

Minimal gate fragment:

```yaml
ci:
  fail_on: HIGH
  strict: false
  minimum_coverage: {abi: 90, linking: 95, runtime: 100}
cross_compilation:
  builds:
    gcc: {sdk: baseline, reference_image: baseline, provenance: actual-gbs-gcc-build}
    clang: {sdk: candidate, reference_image: candidate, provenance: actual-gbs-clang-build}
```

These are examples, not verified Tizen parameters. Supply actual compiler paths, SDKs, target loader settings, debug roots and authorized runtime adapters. The SDK/reference-image mapping is configurable in either direction. ARMv7l target triples/float flags must come from the product toolchain; aarch64 remains supported at the existing machine/class/endian level. Runtime-library family differences require interface/behavior evidence, not compiler branding.

Coverage uses **baseline component contracts**, not emitted findings. Each baseline ELF gets separate export-surface and reachable-type-layout obligations. Other inventories are generally counted per component; header probes include SDK headers; runtime uses matrix cells/custom probes. Both coverage and compatibility percentages divide by applicable contracts. See the schema for treatment of unknown inventory/excluded dimensions.

Source images and SDKs remain read-only; generated compiler and libabigail staging lives under the report. Output/cache paths are also checked against debug roots. No image tools are installed, and no target binary is run directly on the host. Raw evidence and source guards remain in place.

## Validation and limits

See [VALIDATION_RESULTS.md](VALIDATION_RESULTS.md) for commands, actual results and tool provenance; [REVIEW_FINDINGS.md](REVIEW_FINDINGS.md) maps every confirmed defect to reproduction and regression tests.

Completed: all six scoped defects have implementations and positive/negative regression coverage. Actual versioned ELF, ARM object, Clang AST, RPM metadata and embedded/split libabigail tests were run.

Not completed / requirements for production acceptance:

- Real Tizen TV GCC/LLVM rootfs, matching ARMv7l SDK/GBS provenance, full debuginfo and device/QEMU environments were not supplied. No real migration pass is claimed.
- Automatic binary loader-cache decoding and the full glibc namespace/hwcaps/secure/preload/dlopen model are not implemented. Effective target snapshots or authorized runtime validation are required for those cases.
- Direct debuginfo RPM extraction, CRC-only debuglink/DWZ/.dwo/.dwp are not implemented. Existing safe image extraction does not support CPIO payloads; supply safely extracted debug roots rather than adding an unvalidated extractor to this change.
- A complete C/C++ semantic compatibility engine and GBS service integration are outside this implementation; AST signatures and supplied build identifiers are evidence only.
- Runtime isolation/transport is operator-provided. Receipts verify the harness contract but do not establish independent attestation.

The stored `examples/synthetic-report` remains the clearly identified historical schema 1.0 example. Current regeneration uses schema 1.1 and intentionally produces different findings/coverage. Existing examples are not silently relabeled as new validation.
