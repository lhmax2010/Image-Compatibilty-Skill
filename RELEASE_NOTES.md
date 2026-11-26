# Tizen Image Compatibility Skill v1.5.2

**Internal production-readiness candidate**

The offline `compat_workflow.py` entry validates paired local inputs, an explicit objective and report destinations. It produces a bounded handoff with separate execution, objective, compatibility and coverage statuses. The original CLIs and schema 1.2 reports remain supported.

RPM manifests can be reloaded for analysis. Variant inventories retain unpaired ELF evidence and distinguish raw export observations, unique base names, per-library lookup identities and difference rows. Export CSV annotations cite the corresponding original Finding when available. The rootfs export workflow also generates per-library and per-symbol CSVs.

The release includes defensive changes to report output ownership, cache publication and evidence validation, tool capture, interrupt handling, TAR extraction and EROFS confinement. See the [independent review](docs/production-readiness/INDEPENDENT_REVIEW.md) for individual findings.

The bundled [workflow guide](.agents/skills/tizen-image-compatibility/references/workflow.md) and [Quick Start](QUICK_START.md) cover ordinary static runs. The [acceptance record](docs/production-readiness/PRODUCTION_READINESS.md) identifies the remaining external gates. Prior v1.5.0 and v1.5.1 archives and tags are retained.
