> Historical 1.0 delivery record. For current 1.1 behavior, see [correctness.md](correctness.md), [report_schema.md](report_schema.md), and repository-root VALIDATION_RESULTS.md. Counts and missing-tool statements below describe the original delivery, not the current remediation.

# Implementation delivery record

Implemented on 2026-11-15 in `.agents/skills/tizen-image-compatibility/`. Existing `require.md` and `design.md` were left unchanged. The starting directory contained only these documents and no Git repository, AGENTS.md, build system or reusable image tooling.

## Files delivered

- `SKILL.md`, `agents/openai.yaml`: discoverable `$tizen-image-compatibility` skill and execution instructions.
- `scripts/tizen_compat.py`: CLI, modes, input/config validation, exit codes, manifest reuse and report orchestration.
- `scripts/compat/core.py`: schema/config defaults, validation, finding model, tool discovery, bounded parsing, raw evidence/logging and timeout handling.
- `scripts/compat/images.py`: rootfs/TAR/SquashFS/RPM input handling, virtual-root symlink resolution, safe extraction and metadata inventory.
- `scripts/compat/elf.py`, `source.py`, `packages.py`, `collect.py`: modular binary/API/RPM/system collectors.
- `scripts/compat/compare.py`: directional comparisons, semantic classifications, dependency inventory/cycles, optional libabigail and size budgets.
- `scripts/compat/testing.py`: SDK header/application compilation, four-way matrix and opt-in runtime adapter harness.
- `scripts/compat/report.py`, `assets/report_template.html`: escaped HTML, Markdown, JSON, CSV, independent image manifests.
- `assets/probes/behavior.c`, `behavior.cpp`: actual representative C/C++ applications, assertions and deterministic observable output.
- `config.yaml`, `requirements.txt`: validated YAML template and optional YAML dependency.
- `tests/test_framework.py`, `test_execution.py`, `tests/fixtures/*`: unit/integration tests and synthetic shared-library sources/version script.
- `scripts/make_synthetic_fixture.py`: repeatable synthetic rootfs generator.
- `examples/synthetic-config.yaml`, `examples/synthetic-images/*`, `examples/synthetic-report/*`: labeled synthetic inputs and sample HTML/JSON/CSV/Markdown/manifests/raw evidence/logs. Both fixture libraries use the available host compiler; they are not real GCC/LLVM Tizen builds.
- `references/compatibility_dimensions.md`, `detection_methods.md`, `execution.md`, `severity_rules.md`, `tool_requirements.md`, `report_schema.md`, this file: maintained capability, limitation and usage documentation.

## Delivered behavior

The offline end-to-end workflow detects removed versioned exports and data-symbol ABI changes, API/header removals, SONAME/DT_NEEDED/loader differences, package metadata, D-Bus contracts, commands, service/configuration/security/filesystem changes. It distinguishes compatible metadata/additions from confirmed removals and semantic unknowns. Tool failures retain raw evidence and incomplete coverage. ELF collection runs concurrently and can reuse a content/tool-version cache. Manifest-only comparisons preserve recorded tests without rerunning targets.

The four modes are operational. `quick` avoids detailed relocation/note and libabigail work. `static` performs static comparisons. `runtime` and `full` additionally use configured SDKs/adapters; they still produce static context when targets are absent. Threshold policy and exclusions work independently of the overall report status.

## Validation

Commands from repository root:

```bash
SKILL=.agents/skills/tizen-image-compatibility
python3 -m unittest discover -s "$SKILL/tests" -v
python3 -m compileall -q "$SKILL/scripts" "$SKILL/tests"
python3 /opt/nvme-home/linhao/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$SKILL"
```

**36 tests passed**; Python compileall, skill validation and artifact/link validation also passed. The final validation run is recorded in `examples/validation.txt`. Tests include real ELF/versioned-symbol extraction using GCC/readelf, actual RPM building/querying, source immutability snapshots, cache reuse, missing tools, malicious TAR paths/links, unsupported formats, header token semantics, D-Bus signature normalization, SDK header compilation, authorized/unauthorized synthetic target adapters, runtime exclusion, report escaping/CSV safety, manifest reuse and strict/severity CI exits. Own trusted C/C++ probe sources are compiled with `-Wall -Wextra -Werror` and executed on the host strictly as **probe self-tests**, not image compatibility tests.

The synthetic report contains **53 findings: 7 INCOMPATIBLE, 42 UNKNOWN, 2 COMPATIBLE, 2 NOT_APPLICABLE**. It deliberately exits 1. No real target tests ran in that sample: all four execution cells are UNKNOWN and executable-test count is 0. This is evidence that the framework detects deliberately inserted regressions and preserves coverage gaps, not evidence about actual Tizen.

## Dependencies and unverified environments

Python 3.10+ is required; PyYAML is only required for YAML configuration. readelf and rpm provide normal binary/package detail; abidiff adds optional DWARF type checks; unsquashfs enables SquashFS extraction. Tool paths are configurable and tools are not installed into source images. No normal analysis requires network access.

This machine validated GCC/G++/readelf/rpm/rpmbuild. Clang and abidiff were not available, so genuine Clang SDK compilation and libabigail execution remain unverified in this environment. No real Tizen rootfs, SDK, native device, QEMU guest, GPU or multimedia hardware was supplied. The adapter harness was verified with explicitly synthetic adapters; there is no bundled production transport/isolation implementation.

EXT4 and layered OCI require prior extraction; RPM payload extraction is not implemented. C/C++ public API comparison is conservative lexical analysis plus optional SDK probes, not a full AST/type resolver. Exact loader symbol/search behavior, split-debug discovery, kernel/boot/security enforcement and hardware/network semantics remain unknown without appropriate tooling/targets/custom probes. Performance implements binary-size thresholds only. These limitations are surfaced in reports and described dimension by dimension.

## Exact usage

```bash
SKILL=.agents/skills/tizen-image-compatibility
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline /path/to/tizen-gcc-rootfs \
  --candidate /path/to/tizen-llvm-rootfs \
  --config "$SKILL/config.yaml" --mode static \
  --output ./reports/tizen-gcc-vs-llvm
```

For SDK/target configuration and CLI compiler overrides see `SKILL.md` and `references/execution.md`. Explicit Codex invocation: `$tizen-image-compatibility 比较这两个 Tizen 镜像：baseline=...，candidate=...，生成兼容性报告。`
