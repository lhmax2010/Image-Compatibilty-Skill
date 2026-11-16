---
name: tizen-image-compatibility
description: Compare GCC and LLVM Tizen images or SDKs for external-interface compatibility, audit ABI/API and missing libraries or symbols, investigate compatibility regressions, run cross-compiler probes, and generate evidence-based reports. Supports offline rootfs analysis and explicitly configured target environments.
---

# Tizen Image Compatibility

Use the executable Python framework in this directory. Compare **baseline consumers on the candidate**; reverse the inputs for the other direction. Never describe a synthetic fixture report as a real Tizen result.

## Workflow

1. Identify the baseline, candidate and intended direction from the request. Ask only for missing image locations. Inspect their formats and architectures through collection; do not assume the filenames prove GCC/LLVM provenance or a shared architecture.
2. Choose `static` by default, `quick` for a first inventory, `full` for static plus available SDK/target checks, or `runtime` for target-focused work (also collects static context). Missing optional tools or runtime environments become `UNKNOWN`, not success.
3. Run the CLI below. The output must be a new/empty directory outside both images and SDKs. It creates independent manifests, raw evidence and reports. Use an external `--cache` for incremental ELF collection.
4. Review `results.json`, `summary.md` and `index.html`. Explain confirmed incompatible interfaces first, then high-severity unknowns and coverage gaps. A zero CLI exit code means the configured CI threshold was not hit, **not** that all dimensions passed.
5. For compilation/runtime work, read [execution.md](references/execution.md). Require actual SDK sysroots and compiler paths. For target execution, use an explicitly provided and authorized isolated device/QEMU/VM adapter. Never substitute direct execution of image binaries on the host. Existing user authorization may be recorded in configuration; do not ask again unnecessarily.
6. For classification details use [severity_rules.md](references/severity_rules.md); for coverage use [compatibility_dimensions.md](references/compatibility_dimensions.md). Do not turn an unsupported check into a pass or attribute all differences to compiler choice.

## Commands

Run from the repository root; elsewhere replace `SKILL` with this skill's absolute directory.

```bash
SKILL=.agents/skills/tizen-image-compatibility
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline ./images/tizen-gcc --candidate ./images/tizen-llvm \
  --mode static --output ./reports/gcc-vs-llvm
```

TAR/TAR.GZ and SquashFS are accepted. An exported, merged OCI rootfs is a normal rootfs input. EXT4 and layered OCI layouts require prior offline extraction; the CLI gives instructions. RPM collections support package metadata analysis without installation or payload execution.

```bash
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline ./images/gcc.tar.gz --candidate ./images/llvm.tar.gz \
  --config "$SKILL/config.yaml" --cache ./compat-cache \
  --mode full --fail-on HIGH --output ./reports/full

python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline-manifest ./reports/full/baseline-manifest.json \
  --candidate-manifest ./reports/full/candidate-manifest.json \
  --output ./reports/reused

python3 "$SKILL/scripts/tizen_compat.py" --list-tools --output ./reports/tools
```

Use `--exclude abi,runtime,performance` to omit dimensions from classification, `--strict` to fail on any unknown, and `--fail-on CRITICAL|HIGH|MEDIUM|LOW|INFO`. Exit codes: **0** threshold not hit; **1** compatibility/strict failure; **2** invalid input/configuration; **3** infrastructure failure. Optional collector failures remain visible unknown findings so other analyses can complete.

## Validation and synthetic example

```bash
python3 -m unittest discover -s "$SKILL/tests" -v
python3 -m compileall -q "$SKILL/scripts" "$SKILL/tests"
python3 "$SKILL/scripts/make_synthetic_fixture.py" ./synthetic-images
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline ./synthetic-images/baseline --candidate ./synthetic-images/candidate \
  --output ./synthetic-report
```

The last command deliberately returns **1** because the fixture removes a versioned export, changes a data symbol and removes a command. A pre-generated example is in [examples/synthetic-report/index.html](examples/synthetic-report/index.html).

For supported tools/dependencies read [tool_requirements.md](references/tool_requirements.md). For implementation, raw evidence, caching and normalization read [detection_methods.md](references/detection_methods.md). For consumers of JSON/CSV read [report_schema.md](references/report_schema.md). The detailed delivery/validation record is [implementation.md](references/implementation.md).
