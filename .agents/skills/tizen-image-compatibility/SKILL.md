---
name: tizen-image-compatibility
description: Compare GCC and LLVM Tizen images or SDKs for external-interface compatibility, audit ABI/API and missing libraries or symbols, identify potentially affected applications and packages from existing reports, and run explicitly configured cross-compiler probes.
---

# Tizen Image Compatibility v1.5.1

Start with the bundled [Quick Start](references/QUICK_START.md). Resolve every script and reference relative to this SKILL.md.

Use the executable Python framework in this directory. Compare **baseline consumers on the candidate**; reverse the inputs for the other direction. Never describe a synthetic fixture report as a real Tizen result.

## Workflow

1. Identify the baseline, candidate and intended direction from the request. Ask only for missing image locations. Inspect their formats and architectures through collection; do not assume the filenames prove GCC/LLVM provenance or a shared architecture.
2. Choose `static` by default, `quick` for a first inventory, `full` for static plus available SDK/target checks, or `runtime` for target-focused work (also collects static context). Missing optional tools or runtime environments become `UNKNOWN`, not success.
3. Run the CLI below. The output must be a new/empty directory outside both images and SDKs. It creates independent manifests, raw evidence and reports. Use an external `--cache` for incremental ELF collection.
4. Review `results.json`, `summary.md` and `index.html`. Explain confirmed incompatible interfaces first, then high-severity unknowns and coverage gaps. A zero CLI exit code means the configured CI threshold was not hit, **not** that all dimensions passed.
5. For compilation/runtime work, read [execution.md](references/execution.md). Require actual SDK sysroots and compiler paths. For target execution, use an explicitly provided and authorized isolated device/QEMU/VM adapter. Never substitute direct execution of image binaries on the host. Existing user authorization may be recorded in configuration; do not ask again unnecessarily.
6. For classification details use [severity_rules.md](references/severity_rules.md); for coverage use [compatibility_dimensions.md](references/compatibility_dimensions.md). Do not turn an unsupported check into a pass or attribute all differences to compiler choice.

## Commands

Set `SKILL` to the absolute directory containing this SKILL.md. Run the command from any working directory and resolve input and output paths there.

```bash
SKILL=/path/to/tizen-image-compatibility
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline ./images/tizen-gcc --candidate ./images/tizen-llvm \
  --mode static --output ./reports/gcc-vs-llvm
```

TAR/TAR.GZ and SquashFS are accepted. An exported, merged OCI rootfs is a normal rootfs input. EXT4 and layered OCI layouts require prior offline extraction; the CLI gives instructions. A single RPM or recursive local RPM repository uses isolated payload ELF analysis by default. Use `--rpm-mode metadata` for archive inventory only. Read the [repository guide](references/rpm_repository.md) for reports and EROFS fallback.

For a Tizen flashing bundle, first run `python3 "$SKILL/scripts/prepare_image.py" IMAGE --inspect --output NEW_DIRECTORY`. Use the recorded TAR members, GPT geometry, XZ integrity and filesystem signature to decide the next step. `VDFS_EXTRACTOR_UNAVAILABLE` means the identified payload needs a trusted adapter. A `READY` preparation can be passed as an image input. Keep `PARTIAL`, `FAILED` and SDK-only outputs out of runtime compatibility judgments. [Image preparation and replacement inputs](references/image_preparation.md)

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

Review the Collector execution section alongside compatibility and coverage. A failed critical collector normally returns exit 3 after writing reports. Partial collection retains per-object gaps. Set `ci.fail_on_collector_failure: false` to reproduce the previous gate behavior. [CI and severity](references/severity_rules.md)

## Optional SR device workflow

Run static analysis with the regular CLI or reuse an existing report. Use `scripts/runtime_workflow.py build` to compile reviewed recipes with pinned SDKs and freeze the output. Review the new manifest and enroll its digest and selected artifact hashes for the exact SDB target. `runtime_workflow.py run` defaults to a local plan, `--admit` reads device identity, and `--execute` requires explicit authorization. The run command emits JSON, HTML and Markdown with per-stage evidence, even when a runtime observation fails. `runtime_workflow.py report` can combine previously collected observations. Existing Phase 8E manifests remain supported by `scripts/sdb_runtime.py`.

Inspect `runtime-expected-plan.json` and the report's `expected_runtime` section. Each planned repetition has its own Test ID. Keep missing, blocked and skipped tests visible. Imported receipts require an independent review ledger for observation credit. For exact bindings, use `binding_contracts` with Consumer, Provider, Symbol, Version and Provider SHA256. An observed version check alone cannot verify a binding. [Expected tests and import contract](references/USER_GUIDE.md)

Keep headless static findings separate from `SR_HEADED_RUNTIME` observations. Actual exit, expected behavior, Loader evidence and cleanup are separate fields. The SDB observation cannot satisfy the formal headless or cross-image classification on its own. See the [integrated workflow guide](references/USER_GUIDE.md).

## Validation and synthetic example

```bash
python3 -m unittest discover -s "$SKILL/tests" -v
python3 -m compileall -q "$SKILL/scripts" "$SKILL/tests"
python3 "$SKILL/scripts/make_synthetic_fixture.py" ./synthetic-images
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline ./synthetic-images/baseline --candidate ./synthetic-images/candidate \
  --output ./synthetic-report
```

The last command deliberately returns **1** because the fixture removes a versioned export, changes a data symbol and removes a command. The source-only [examples](examples/README.md) explain how to generate fresh reports.

For supported tools/dependencies read [tool_requirements.md](references/tool_requirements.md). For implementation, raw evidence, caching and normalization read [detection_methods.md](references/detection_methods.md). For consumers of JSON/CSV read [report_schema.md](references/report_schema.md). The detailed delivery/validation record is [implementation.md](references/implementation.md).

## Correctness and migration gates (1.2)

Before claiming GCC-to-LLVM migration compatibility, read [correctness.md](references/correctness.md). Preserve exact versions (`@` / `@@`), actual provider paths and baseline-consumer direction. Do not dismiss C++/ASAN/generated-symbol removals from export counts or naming alone. Same-build-type comparisons reduce confounding but do not establish compatibility themselves.

Require explicit compiler → SDK/native-reference/build-provenance mappings for the four-way matrix. SDK headers and runtime-image headers are separate evidence. Own-reference failure or missing deployment/execution receipts means UNKNOWN. Never execute target artifacts directly on the host.

Report compatibility outcome and verification completeness independently. A confirmed break with missing checks is **INCOMPATIBLE + PARTIAL**, not fully verified. Count only COMPLETE mandatory obligations in coverage; show partial/unexecuted obligations, confirmed failures, and both denominators. Missing tools/DWARF/SDK/devices stay visible. `ci.minimum_coverage` and compatibility failures have separate gate reasons; exit 0 without coverage thresholds is not a full pass.

Inspect `expected-tests.json` (written before execution) and `expected-tests-results.json`. Matrix acceptance requires exact expected IDs, all mandatory stages, matching artifact hashes and a valid native reference. Header limits and unavailable prerequisites leave expected tests incomplete. Loader verification requires a declared complete startup scope/search environment; multiple providers, weak/IFUNC/GNU UNIQUE/protected semantics, namespaces and legacy interposition stay UNKNOWN when unsupported. Never promote first-match lookup evidence to runtime proof.

Use configured SDK ABI and selected runtime objects for ARMv7 probes; unrelated missing attributes do not veto the primary ABI. Report mixed objects separately. Base PCS (`float: soft`) includes softfp code generation; it is distinct from VFP PCS (`float: hard`).

Read [packages.md](references/packages.md) before interpreting package results. Installed RPM database records and available RPM archives are separate. Unreadable/missing databases mean unknown counts, not zero. Ownership uses RPM file lists, retaining multiple owners and usrmerge aliases; consumer, provider and root consumer are separate roles. SDK header findings need an explicitly associated SDK inventory. Runtime-only packages do not establish API compatibility. Review `package_results`, `packages.csv` and unassigned interfaces alongside global findings.

Schema 1.0/1.1 successful observations require 1.2 revalidation. Preserve failures and original evidence; never infer new execution from manifest reuse.

## Acceptance accounting

Check `count_reconciliation`, candidate assessments and unverified package records before reporting package totals. Review `provider_consumers`, `interface_findings`, and global unassigned finding IDs. Shared-file rename/split hints are UNKNOWN, not proof of lineage. Complete data-only applicability yields NOT_APPLICABLE, not an automatic compatibility pass. `finding_integrity` makes exact duplicate occurrences visible; distinct root-consumer failures must remain distinct. A recorded failure without complete test metadata stays incompatible and partial.

For a small reproducible report see [examples](examples/README.md). The stress tool in `tests/review/benchmark_v12.py` validates serialized IDs/relationships and enforces time/memory budgets; do not describe a successful process exit without those checks as scale validation. Before product acceptance, require actual RPM inventories, matching SDK/debuginfo/ABI evidence, declared loader context, a complete expected probe list, and an authorized isolated adapter. See the [correctness guide](references/correctness.md) for prerequisites and capability boundaries.

For the v1.2 release candidate, distinguish ARM calling-convention conflicts from unequal CPU architecture tags; differing tags require ISA/hardware evidence and stay UNKNOWN. Missing symbol-resolution completeness must never be assumed true. Explicit source probes are independent of built-in language toggles, but still require all normal compiler/SDK/authorization prerequisites. Candidate-only packages are inventory additions with unverified compatibility.

## Large existing reports (report enhancement v1.3)

For report usability work, reuse an existing schema-1.2 report rather than rerunning Static. Run `python3 scripts/enhance_report.py build --input EXISTING_REPORT --output NEW_DIRECTORY` from this skill directory. It streams manifests/results into a disk index, retains all original finding payloads/IDs/statuses, and reconciles original CSV fields, package assessments, group membership and symbol counts. Output must be separate and new; a failed run is retained for inspection, never overwritten automatically.

Run `python3 scripts/enhance_report.py serve --report NEW_DIRECTORY` for the local, read-only browser at `http://127.0.0.1:8765/`. No Internet is required. Explain explicitly that `file://` only provides the static overview/CSV links; interactive package, ELF, symbol and Linking navigation needs the loopback server. Retain the original report/evidence directory. See [report_schema.md](references/report_schema.md) and [packages.md](references/packages.md) for counting contracts. Never interpret display differences, navigation groups or export counts as new compatibility proof. Resource failures stop processing and preserve `run.json`; do not raise limits or retry indefinitely.

## Offline impact analysis (v1.4 RC)

When asked which applications or packages may be affected, use the impact engine. If a validated v1.3 enhanced report already exists, reuse it. For an original schema 1.2 report, first run `enhance_report.py build` into a separate directory. If there is no report, run the authorized static workflow; retain its report and Evidence.

```bash
SKILL=/path/to/tizen-image-compatibility
python3 "$SKILL/scripts/impact_report.py" build \
  --input ./reports/enhanced --output ./reports/impact-rc1
python3 "$SKILL/scripts/impact_report.py" serve \
  --report ./reports/enhanced --impact ./reports/impact-rc1
# Open the /impact URL printed by the loopback server.
```

Start with confirmed static contract impacts, then report possible impacts and unassessed observations with their reason counts. Follow each group through the recorded consumer, package role, original Finding and Evidence. Preserve the original Finding status. A Provider or root package role does not establish that package's compatibility or that all its components are affected.

Historical input without a baseline binding supports inferred associations only. With the corresponding Phase 7A manifests and recorded loader settings, repeat `--replay-root /exact/baseline/executable` for targeted checks. The engine uses both manifests through the existing resolver and requires a matching original candidate Finding. This mode performs no target execution. Evidence or runtime gaps lead to proposed verification, not agent-generated verdicts. An incomplete or changed source needs a new bounded build in a separate directory. See the [user guide](references/USER_GUIDE.md).

## Historical regression and final validation

Use `python3 scripts/history_report.py build --before OLDER_INDEX --after NEWER_INDEX --scope 'RECORDED PRODUCT LINEAGE AND DIRECTION' --output NEW_DIRECTORY` for two comparable, validated reports. `query` reads the result in bounded pages. Mount it through `enhance_report.py serve --report NEWER_INDEX --history NEW_DIRECTORY` at `/history`. An unpaired or disappeared observation is unresolved. A changed original ID requires a unique matching startup Linking context plus the same original requirement and detector before assigning a fixed or introduced risk. Keep before/after Finding IDs and coverage visible.

For target work, provide both SDKs and compiler paths, native references and an authorized adapter. `cross_compilation.extended_runtime_probes: true` adds C++ cross-DSO and cancellation checks. `runtime.repetitions` checks reproducibility and runtime probe `requires` records capability gaps. Use the built-in rootless Podman backend with two preloaded, digest-pinned local images for userspace experiments, or a trusted adapter for a disposable VM/device. Container results do not establish Tizen kernel or hardware equivalence. Details and sample configuration are in [execution.md](references/execution.md) and the [final user guide](references/USER_GUIDE.md).
