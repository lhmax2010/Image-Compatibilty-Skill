# Schema 1.2 (with conservative 1.0/1.1 import)

Each image has an independent JSON manifest:

- `schema_version`, `collector_version`, `collection_mode`, `tools`.
- `image`: name, source, format, user-declared toolchain, observed architecture list, os_version keys, kernel_version configuration-file labels.
- `elf_objects`: path/size/complete, metadata, exports/imports (lossless raw name, base_name, version, default_version, version_index, version_file on imports, size, value, type, binding, visibility, section), needed, SONAME, loader/search paths, version_definitions (index/name/parents/flags), version_requirements (file/name/index/flags), ARM attributes/EABI/PCS, TLS/sections/C++/unwind inventories, evidence. Full raw relocation/version text is external evidence.
- `collection_complete`, `loader_environment`, `loader_configuration`: inventory completeness, explicit effective loader model, collected ld.so.conf evidence.
- `sdk_headers`: SDK path and provenance, distinct from runtime image headers.
- `public_headers`: origin (`runtime_image`), path/hash, tokens, body_tokens, macros (kind/replacement), declarations, includes, conditions, context_hints, evidence.
- `packages`: installed records only, name/epoch/version/release/arch, provides/requires/conflicts/obsoletes (name, raw RPM flags, version), files, collection_status, provenance (kind/source/query/evidence), evidence. Parallel NEVRAs are retained.
- `available_packages`: RPM archive metadata, not installed ownership. `package_inventory`: status, installed_count (null if unavailable), reason and archive counts/status.
- `sdk_package_manifest`: explicitly associated SDK inventory, separate from runtime ownership.
- `expected_tests`: stable ET IDs, compiler/source/SDK identities, build provenance, configured target ABI, expected artifact, reference/destination images, required stages, actual stage results, outcome, verification, evidence/reason. `test_manifest_audit` lists missing/duplicate/unexpected IDs.
- `filesystem`, `configurations`, `services`, `commands`, `ipc`, `security_interfaces`, `kernel`, `hardware`, `network`, `development`, `runtime_libraries`, `capabilities`.
- `limitations`: dimension, component, reason. Missing RPM DB and tool failures are explicit.
- `test_results`: ID, image/compiler/kind/status, compile success/argv/version/diagnostics or runtime output/return code/environment, evidence.
- `cross_matrix`: four compiler/image cells with explicit build_sdk/build_provenance/reference_image, header/runtime status, and compile/deployment/execution/behavior stages; on reuse these are prior observations, never a new execution.

Top-level `results.json` contains `schema_version`, direction, image identities, global status, summary (findings and separately executable test counts), per-dimension statuses, findings, tests, matrix, limitations, excluded dimensions, missing interface IDs, compatible normalized difference IDs and normalization policy. `findings.csv` exposes the same finding records as flat cells; nested values are JSON strings.

Every finding contains:

```json
{
  "id": "TC-content-derived-id",
  "dimension": "abi",
  "component": "/usr/lib/libexample.so.1",
  "interface": "example@VERSION_1",
  "baseline": "exported",
  "candidate": null,
  "status": "INCOMPATIBLE",
  "severity": "HIGH",
  "confidence": "high",
  "evidence": ["evidence/content-hash.txt"],
  "detection_method": "ELF dynamic export/version comparison",
  "potential_impact": "Existing consumers cannot resolve this export.",
  "recommended_action": "Restore the exported interface or validate affected consumers."
}
```

`index.html` is self-contained, with summary, dimension overview, four-way matrix, filterable escaped details limited to first 1000 findings (full JSON/CSV retained), missing interfaces, compatible/normalized differences and limitations. `summary.md` is CI-readable and limits incompatible detail rows to 200; it includes the full coverage table. `baseline-manifest.json`, `candidate-manifest.json` and `collection.log` are always emitted; report format flags control HTML/results JSON/Markdown/CSV. `evidence/` preserves collection outputs; `build/` holds generated compile sources/artifacts if applicable. No timestamps are added to findings just for display. `expected-tests.json` is the pre-execution plan; `expected-tests-results.json` is its reconciled outcome. Manifest reuse does not re-run or regenerate those original artifacts; reconciled expected tests remain in results/manifests.

A static finding is not counted as an executable test. Missing environments leave all runtime cells unknown. Empty evidence or an absent collection section is never evidence of success.

## Coverage and quality gates

`coverage_policy` defines counting units and denominators. Each `coverage.<dimension>` includes:

- `applicable`, `completely_verified`, `partially_verified`, `unexecuted`, `not_applicable`.
- `confirmed_compatible`, `confirmed_incompatible`, `unknown` (outcome counts).
- `complete_verification_coverage_percent` = 100 × completely_verified / applicable.
- `compatibility_percent` = 100 × confirmed_compatible / applicable.
- Compatibility aliases retained: `verified` = completely_verified, `coverage_percent` = complete_verification_coverage_percent; `compatible` / `incompatible` alias their confirmed counts. **Since 1.2, verified is no longer compatible + incompatible.**
- `units`: interface, status/compatibility, verification, required_checks, finding_ids, evidence, confidence, limitations. Each check has a unique local ID, status, verification, evidence, reason.

Outcome is IDENTICAL / COMPATIBLE / INCOMPATIBLE / UNKNOWN / NOT_APPLICABLE. Completeness is COMPLETE / PARTIAL / NOT_EXECUTED / NOT_APPLICABLE. A confirmed break plus unknown checks remains INCOMPATIBLE + PARTIAL and earns no COMPLETE credit. Duplicate finding rows cannot add coverage. Baseline ABI export and type-layout contracts are separate. Header obligations use expected IDs; runtime obligations use matrix cells and declared custom probes. Unsupported/missing inventory creates an unknown discovery obligation. N/A items leave the denominator; excluded/all-N/A ratios are null, never 100%.

`quality_gate` retains PASS/FAIL, thresholds and `failures` (coverage dimension/minimum/actual), adding `coverage_status`, `compatibility_status`, `compatibility_failures` and `strict_status`. A configured coverage shortfall returns CLI 1 independently of severity. Strict also rejects partial/unexecuted/unknown obligations. Compatibility failure preserves the configured severity threshold. Old finding counters under `dimensions` remain separate from coverage.

Loader findings add `resolution`, check_id, consumer_path/image, root_consumer/image, provider_path and ordered lookup-candidate evidence. Deep ABI findings retain coverage_unit and debug_coverage. Package attribution adds `package_ownership` with distinct consumer, candidate provider and root consumer associations, owner IDs, canonical path, target owners, status/reason. Finding CSV retains its original flat columns; structured additions are in JSON. Raw symbol names retain `@` versus `@@`.

## Package reports

`package_inventory` contains both runtime inventory statuses/counts, matched IDs, baseline_only/candidate_only, unresolved_matches, candidate_additions, available_archives, sdk_inventories, unassigned_interfaces and unassigned_finding_ids. Unknown installed counts are null. Candidate additions describe inventory additions only. Matching multiple NEVRAs never silently overwrites identities.

`package_results` retains every baseline installed package, including explicit SDK packages with scope `sdk`. Each row includes ID/name/arch/scope, baseline/candidate versions and full package metadata; availability, metadata, abi, api and linking obligations; overall, verification, confidence, limitations, coverage; owned_interfaces/candidate_interfaces (ELFs and full exports, headers, development files, ambiguous paths); finding IDs, missing interfaces and evidence. Per-package ABI/API/linking obligations expose their own coverage. Renamed/split/replacement candidates remain unresolved unless interface evidence establishes a relationship. Runtime ELF availability alone never verifies API compatibility.

`packages.csv` exports all baseline rows with identities/versions, ABI/API/linking/overall/completeness, coverage, finding IDs and limitations. Markdown shows the first 200 packages. HTML filters the first 1000 packages with expandable ELF/symbol/header/finding/gap/evidence previews (up to 100 items per field). Machine JSON/CSV remain complete. Candidate-only packages are represented in inventory additions, not misreported as baseline contracts. See [packages.md](packages.md).

## Migration

Importing schema 1.0/1.1 preserves confirmed failures, but prior successful tests and matrix cells become UNKNOWN with recorded_status on tests and migration_notes. Legacy ELF lookup completeness is untrusted. No old completeness credit or absent expected-test IDs are inferred. Recollect for 1.2 lookup, provenance and ownership metadata. Collector version 1.2.0-rc.1 invalidates earlier ELF cache entries. A reused manifest contains historical observations, not a new execution. Compare percentages only after aligning schema/denominators and required checks.

## Acceptance supplement (additive 1.2 fields)

- `package_inventory.count_reconciliation`: runtime/SDK declared installed count, discovered/assessed/unverified records and tri-state consistency. Inconsistent complete inputs are rejected on manifest read; direct aggregation downgrades them and reports null installed count.
- `candidate_assessments`: every reliable candidate installed identity, its match_status, baseline_assessment_id (if any), owned interfaces and finding IDs. This complements directional baseline `package_results`; it does not claim reverse compatibility. `unverified_package_records` retains records lacking installed provenance.
- `provider_consumers`: candidate provider package → consumer image/package, ownership status and finding IDs; root consumers are included. `interface_findings`: image/scope/path → dimension/finding IDs. Underlying RPM package file arrays remain the package → owned-path index.
- `replacement_hints`: possible rename/replacement or split based on shared owned file paths. Always UNKNOWN; never confirmed package lineage or automatic matching. Package rows add `match_status` and `replacement_hint`. `baseline_only` means no same-identity match, not proven interface removal.
- Complete interface N/A evidence yields overall NOT_APPLICABLE for data-only packages rather than manufacturing compatibility from metadata equality. Inventory/metadata coverage still has its documented denominator.
- `finding_integrity`: unique_findings, source_occurrences and deduplicated ID/occurrence counts. Exact duplicates are combined visibly. Conflicting ID payloads or unfinalized duplicate IDs are rejected instead of silently overwriting. CSV exports one row per unique finding; occurrence accounting is in JSON. Linker IDs include consumer/root/provider context so distinct affected roots are not duplicates.
- `quality_gate.compatibility_obligation_failures`: confirmed failing obligations without associated finding rows, treated as HIGH severity subject to fail_on. Global status includes confirmed obligation/test/package failures. Missing expected metadata invalidates prior successful matrix checks; recorded failures remain PARTIAL.
- HTML package/finding elements carry escaped data IDs/statuses for consistency auditing. Preview limits do not remove machine records. Candidate-only inventory is displayed separately.

## Final review / release candidate

Schema stays 1.2; collector is 1.2.0-rc.1. `elf_objects.resolution_metadata_complete` must be a boolean when supplied; absence is not a pass. Successful dynamic readelf collection records `resolution_metadata_evidence`. Old/incomplete manifests need recollection for lookup verification; do not manually add true to obtain coverage.

Compile target diagnostics separate `abi_status`, `isa_assessment` (probe/reference CPU tags) and `hardware_assessment`. ABI conflicts can remain INCOMPATIBLE while ISA evidence is UNKNOWN. CPU tag inequality alone is UNKNOWN; tag equality is not hardware capability proof.

`candidate_additions[].inventory_status` is ADDED; its compatibility `status` is UNKNOWN. Candidate assessment records likewise do not claim an untested package compatible. Missing-interfaces and normalized-differences HTML sections now filter first, then display up to 1000 matching records, with total/shown/hidden counts. JSON/CSV remain complete.
