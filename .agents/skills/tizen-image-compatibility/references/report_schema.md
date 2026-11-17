# Schema 1.1 (with conservative 1.0 import)

Each image has an independent JSON manifest:

- `schema_version`, `collector_version`, `collection_mode`, `tools`.
- `image`: name, source, format, user-declared toolchain, observed architecture list, os_version keys, kernel_version configuration-file labels.
- `elf_objects`: path/size/complete, metadata, exports/imports (lossless raw name, base_name, version, default_version, version_index, version_file on imports, size, type, binding, visibility, section), needed, SONAME, loader/search paths, version_definitions (index/name/parents/flags), version_requirements (file/name/index/flags), ARM attributes/EABI/PCS, TLS/sections/C++/unwind inventories, evidence. Full raw relocation/version text is external evidence.
- `collection_complete`, `loader_environment`, `loader_configuration`: inventory completeness, explicit effective loader model, collected ld.so.conf evidence.
- `sdk_headers`: SDK path and provenance, distinct from runtime image headers.
- `public_headers`: origin (`runtime_image`), path/hash, tokens, body_tokens, macros (kind/replacement), declarations, includes, conditions, context_hints, evidence.
- `packages`: name/epoch/version/release/arch, provides/requires/conflicts/obsoletes (name, raw RPM flags, version), files, evidence.
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

`index.html` is self-contained, with summary, dimension overview, four-way matrix, filterable escaped details limited to first 1000 findings (full JSON/CSV retained), missing interfaces, compatible/normalized differences and limitations. `summary.md` is CI-readable and limits incompatible detail rows to 200; it includes the full coverage table. `baseline-manifest.json`, `candidate-manifest.json` and `collection.log` are always emitted; report format flags control HTML/results JSON/Markdown/CSV. `evidence/` preserves collection outputs; `build/` holds generated compile sources/artifacts if applicable. No timestamps are added to findings just for display.

A static finding is not counted as an executable test. Missing environments leave all runtime cells unknown. Empty evidence or an absent collection section is never evidence of success.

## Coverage and quality gates

`coverage_policy` defines counting units and denominators. `coverage.<dimension>` has `applicable`, `verified`, `compatible`, `incompatible`, `unknown`, `coverage_percent`, `compatibility_percent`, `excluded`, and `units` (interface/status). Units are baseline component contracts, not finding rows. ABI has separate export and type-layout obligations. A dimension without inventory has one unknown discovery obligation. Both ratios use applicable as denominator; verified = compatible + incompatible. Excluded dimensions have null ratios and zero counts.

`quality_gate` has status PASS/FAIL, configured thresholds and failures (dimension/minimum_percent/actual_percent). Gate failure returns CLI 1 independently of severity. Strict also considers unknown coverage units. Finding status counters under `dimensions` remain available separately for consumers of the old report.

Loader findings add `resolution`; deep ABI findings add `coverage_unit` and `debug_coverage` (source kind/path/build-ID and missing-data reason). CSV retains its original flat columns; additional structured fields are in JSON. Raw symbol names retain `@` versus `@@`; consumers must not normalize them together.

Importing schema 1.0 preserves failures, but prior successful tests and matrix cells are downgraded to UNKNOWN, with `recorded_status` on tests. No new execution is implied by reuse. Recollect for 1.1 version/ABI/search metadata. Cached ELF entries are invalidated by collector version 1.1.0.
