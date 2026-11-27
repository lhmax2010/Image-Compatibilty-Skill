# Quick Start

Install the complete `tizen-image-compatibility` directory from the internal v1.5.2 archive. Keep its name and set `SKILL` to its absolute path. Run Python 3.10+ on Linux, including WSL or a remote Linux terminal. Use `readelf` (GNU binutils) for ELF analysis and `rpm` when RPM inventory matters. The default static CLI needs no Python packages, network, SDK, SDB, QEMU or root. A host C compiler is only needed to generate the synthetic example.

## Run a configured job

Copy `examples/workflow.json` from the Skill, then edit the input and output paths. All paths in that file are relative to the config file.

```bash
SKILL=/path/to/tizen-image-compatibility
cp "$SKILL/examples/workflow.json" ./job.json
# Edit job.json with your actual paths before running.
python3 "$SKILL/scripts/compat_workflow.py" plan --config ./job.json
python3 "$SKILL/scripts/compat_workflow.py" run --config ./job.json
python3 "$SKILL/scripts/compat_workflow.py" summary --output ./reports/job
```

Read the compact summary first. A completed export comparison can find an incompatibility and return 1. See the [workflow guide](workflow.md) for required objectives, fallback and status fields.

## Compare two images

Run these commands from a writable analysis directory. Set `SKILL` after installing the directory.

```bash
SKILL=/path/to/tizen-image-compatibility
python3 "$SKILL/scripts/tizen_compat.py" --list-tools --output ./tools-check
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline /path/to/baseline-rootfs --candidate /path/to/candidate-rootfs \
  --mode static --output ./comparison
```

Use a new or empty output location outside your input images. Baseline is the old consumer contract and candidate is the replacement environment. Open `comparison/index.html` or `summary.md`. Keep `results.json`, `findings.csv`, any package CSV and the `evidence/` directory together for review.

The static CLI returns 0 when the configured gate passes, 1 when compatibility or a strict gate fails, 2 for invalid input/configuration and 3 for critical collection/infrastructure failure. Inspect the report on exit 1 or 3. An `UNKNOWN` row has insufficient evidence. Coverage measures verification completeness independently of reported compatibility.

## Try it without product images

```bash
python3 "$SKILL/scripts/make_synthetic_fixture.py" ./synthetic-images
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline ./synthetic-images/baseline --candidate ./synthetic-images/candidate \
  --mode static --output ./synthetic-report
```

Exit 1 is expected. The reports show an intentionally removed symbol, header and command differences, and missing evidence for checks the fixture cannot establish. Do not run the fixture's target files.

See the [User Guide](USER_GUIDE.md) for Cline installation, image preparation, report queries, SDK and Runtime.

## Compare two local RPM inputs

```bash
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline /path/to/vd-gcc-rpms --candidate /path/to/vd-llvm-rpms \
  --rpm-mode payload --output ./rpm-comparison
```

This needs host `rpm`, `rpm2cpio` and `readelf`. Inputs can be individual RPMs or recursive directories. View `index.html`, `elf-symbol-summary.csv`, `symbol-differences.csv` and `extraction-errors.csv`. The scope is `RPM_REPOSITORY_PAYLOAD`. Use `--rpm-mode metadata` for an inventory-only run.

Match instrumentation for a GCC-to-LLVM compatibility decision. A GCC plain to LLVM ASan run can still report missing libraries and symbols. It displays instrumentation confounds and downgrades affected data-size findings. Treat the run as an instrumentation-mismatched comparison in review.
