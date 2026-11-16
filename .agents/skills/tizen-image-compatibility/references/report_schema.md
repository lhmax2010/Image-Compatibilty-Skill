# Schema 1.0

Each image has an independent JSON manifest:

- `schema_version`, `collector_version`, `collection_mode`, `tools`.
- `image`: name, source, format, user-declared toolchain, observed architecture list, os_version keys, kernel_version configuration-file labels.
- `elf_objects`: path/size/complete, metadata, exports/imports (name, size, type, binding, visibility), needed, SONAME, loader/search paths, GNU versions, TLS/sections/C++/unwind inventories, evidence. Full raw relocation/version text is external evidence.
- `public_headers`: path/hash, tokens, body_tokens, macros (kind/replacement), declarations, includes, conditions, context_hints, evidence.
- `packages`: name/epoch/version/release/arch, provides/requires/conflicts/obsoletes (name, raw RPM flags, version), files, evidence.
- `filesystem`, `configurations`, `services`, `commands`, `ipc`, `security_interfaces`, `kernel`, `hardware`, `network`, `development`, `runtime_libraries`, `capabilities`.
- `limitations`: dimension, component, reason. Missing RPM DB and tool failures are explicit.
- `test_results`: ID, image/compiler/kind/status, compile success/argv/version/diagnostics or runtime output/return code/environment, evidence.
- `cross_matrix`: four compiler/image cells with separate header and runtime status; on reuse these are prior observations, never a new execution.

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

`index.html` is self-contained, with summary, dimension overview, four-way matrix, filterable escaped details, missing interfaces, compatible/normalized differences and limitations. `summary.md` is CI-readable. `baseline-manifest.json`, `candidate-manifest.json` and `collection.log` are always emitted; report format flags control HTML/results JSON/Markdown/CSV. `evidence/` preserves collection outputs; `build/` holds generated compile sources/artifacts if applicable. No timestamps are added to findings just for display.

A static finding is not counted as an executable test. Missing environments leave all runtime cells unknown. Empty evidence or an absent collection section is never evidence of success.
