# Tizen Image Compatibility v1.5.0 User Guide

## Install for Cline or use the CLI

Download the archive and `SHA256SUMS` from the internal v1.5.0 distribution. Verify the archive digest with `sha256sum` before extracting. Keep the complete extracted directory with its original name. For independent CLI use, follow the [Quick Start](QUICK_START.md) and point `SKILL` to that directory. There is no dependency on an agent API.

For Cline, copy the complete directory into one of these locations in Cline's execution environment.

| Scope | Installed entry |
| --- | --- |
| Project | `<project>/.cline/skills/tizen-image-compatibility/SKILL.md` |
| User | `~/.cline/skills/tizen-image-compatibility/SKILL.md` |

For example, extract to a staging directory then run the following from that directory. Choose one destination.

```bash
dest=/path/to/project/.cline/skills
# For user scope use dest="$HOME/.cline/skills"
mkdir -p "$dest"
test ! -e "$dest/tizen-image-compatibility" &&
  cp -R ./tizen-image-compatibility "$dest/"
```

Open the intended project in Cline, find and enable the Skill in the Skills tab, then select `/tizen-image-compatibility` from chat suggestions or request it by name. Use the installed directory containing the loaded `SKILL.md` when resolving scripts.

> Use tizen-image-compatibility to compare baseline /images/gcc-rootfs with candidate /images/llvm-rootfs in static mode. Write a new report to ./reports/gcc-to-llvm and distinguish incompatibility, UNKNOWN and coverage gaps.

To update, verify and extract the new archive to a staging area, then move the old directory out of the discovery path before installing the complete new one. To uninstall, disable the Skill and remove or relocate its directory. Preserve local analysis outputs and operator-managed settings separately. An enabled user-level copy can take precedence over the project copy. Official discovery and invocation details are in [Cline Skills](https://docs.cline.bot/customization/skills).

## Inputs and configuration

Start with a root filesystem directory, a rootfs TAR/TAR.GZ, a supported SquashFS image, an exported merged OCI rootfs or a local RPM archive collection. RPM collections describe available packages, while an image's installed RPM database supplies installed inventory and ownership. Use independently collected same-build SDK/sysroot inputs where required. For a flashing container, inspect before preparing it. Unsupported filesystem or incomplete preparation is an explicit coverage gap. See [image preparation](image_preparation.md) for EXT4, GPT/XZ, VDFS adapters and alternative inputs.

```bash
python3 "$SKILL/scripts/prepare_image.py" /path/to/flash-package.tar.gz \
  --inspect --output ./image-inspection
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline-manifest ./comparison/baseline-manifest.json \
  --candidate-manifest ./comparison/candidate-manifest.json \
  --mode static --output ./reused
```

The default static run uses the Python standard library and read-only image collection. Install the optional dependency in your Python environment if you use `--config` (`python3 -m pip install -r "$SKILL/requirements.txt"`). See [config.yaml](../config.yaml) and [Tool requirements](tool_requirements.md). Use `--fail-on HIGH`, `--strict`, and the YAML `ci.minimum_coverage` / `ci.fail_on_collector_failure` as needed. Preserve the distinction between findings, coverage, and CI exit status. [CI and severity rules](severity_rules.md)

Manifest reuse recomputes findings from collected inputs. It retains recorded executable tests and skips checks that need the original files, such as a new DWARF layout comparison. Reuse can therefore have a different coverage record from a direct scan.

## Reports, Impact and History

Start with the original `index.html`, `summary.md`, full JSON/CSV and original Evidence. Use a separate output when building an optional index. Success requires completed `run.json` and `validation.json`. Keep the original reports where their evidence paths resolve. Resource guards apply to index builds.

```bash
python3 "$SKILL/scripts/enhance_report.py" build --input ./comparison --output ./index
python3 "$SKILL/scripts/impact_report.py" build --input ./index --output ./impact
python3 "$SKILL/scripts/history_report.py" build \
  --before ./older-index --after ./index --scope 'Same product lineage and direction' \
  --output ./history
python3 "$SKILL/scripts/history_report.py" query --report ./history entries --limit 20
python3 "$SKILL/scripts/enhance_report.py" serve \
  --report ./index --impact ./impact --history ./history
```

Open the loopback address printed by the server. Use `/impact` and `/history` after mounting the corresponding sidecars. Impact separates confirmed, inferred and unassessed consumers. Compare like-for-like verified reports in History. A disappearing observation can still be unresolved. [Report schema](report_schema.md)

An unavailable RPM inventory stays UNKNOWN in the enhanced index. The index retains observed assessment rows and keeps their count separate from the installed total.

## Optional SDK and Runtime

The standalone static route can be used without these prerequisites. For optional compile/link choose trusted, matched SDKs and SDK identities. Supply compiler, sysroot, startfiles and source settings yourself. For target tests use an authorized adapter in a supported isolated environment. See [Execution configuration](execution.md) for the general four-quadrant matrix and external or Podman runner.

For the SDB workflow use the documented `runtime_workflow.py` phases. The reviewed build recipe is a local JSON object with `sources` (paths), `sdk` (by alias), `steps` and `probes`. Each SDK includes `host`, `sysroot`, `startfiles`, `lock`, `lock_sha256`, `label` and `compiler_sha256` keyed by driver path. Each build step uses `sdk`, `driver`, `flags`, `out` and optionally `expected_returncode` with `stderr_contains` for a declared link failure. In the build namespace sources are under `/work/src`, outputs under `/work/out` and the target sysroot is `/sysroot`. Each probe uses `artifact_id`, a `files` mapping from local bundle leaf to step output, and `runtime_expectation` with `exit_code`, `stdout` and `stderr`. The executable leaf is `probe`. Optional `outcome` supports `exit`, `loader-error` and `timeout`.

```bash
python3 "$SKILL/scripts/runtime_workflow.py" build --config ./build-config.json --output ./frozen
python3 "$SKILL/scripts/runtime_workflow.py" run --config ./runtime-config.json --output ./runtime-plan
python3 "$SKILL/scripts/runtime_workflow.py" run --admit --config ./runtime-config.json --output ./admission
python3 "$SKILL/scripts/runtime_workflow.py" run --execute --config ./runtime-config.json --output ./runtime
python3 "$SKILL/scripts/runtime_workflow.py" report --config ./report-config.json --output ./unified
```

An [example offline plan](../examples/runtime-workflow.json) shows `runs[].manifest`, independently fixed `manifest_sha256`, `bundle`, `enrollment` and `artifacts`. Repetitions and required/optional policy can be specified per artifact. Before using a reviewed bundle, obtain its digest and the target identities through independent review. Use a pre-existing SDB connection to a specifically authorized non-root device. The enrollment carries `sdb_serial` (explicit IPv4 and port), `scope`, `image_family`, `build_id`, `cpu_serial_sha256` and `provider_sha256`. Provider pins include `ld-linux.so.3`, `libc.so.6`, `libgcc_s.so.1`, `libm.so.6` and `libstdc++.so.6`, plus needed supported optional libraries. For execution, enrollment `authorization` needs `execute: true`, the original artifact SHA256 map under `artifact_sha256`, `manifest_sha256`, and `target_sha256` computed by `compat.probe_bundle.target_pin` against the independently reviewed enrollment. Plan-only and read-only admission can use `execute: false`. A pinned `environment_id` binds the current admission on re-use.

Exact `binding_contracts` entries contain `consumer`, `provider`, `symbol`, `version` (or null) and `provider_sha256`. Use `bundle:probe` for the executable, `bundle:<leaf>` for a companion DSO and an admitted absolute library path for a system endpoint. Legacy `binding_symbols` carries name-only evidence. Loader version checking and actual binding are separate observations.

Every planned attempt slot appears in `runtime-expected-plan.json`. Report configuration may include `static_report` (`directory` and `scope`), `build_reports` and `runtime_reports` (paths), and independently pinned `expected_runtime_plan` and `reviewed_runtime_attempts` (each with `path`, `sha256`). The latter uses schema `tizen-compat-runtime-reviewed-attempts/v1` and maps receipt SHA256 to `test_id` and `review_basis` in its `attempts` object. Optional `legacy` marks reviewed old records and `eligible: false` keeps a historical attempt without final credit. Use `final_attempts` to map a Test ID to its explicitly selected reviewed receipt digest. Unreviewed imports remain visible without verification credit.

Headed observations preserve their own Scope, target identity, behavior and cleanup evidence. Formal product Runtime needs matched image identities, native references and independent trusted cleanup supervision.
