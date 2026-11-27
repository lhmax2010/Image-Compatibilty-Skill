# Offline workflow controller

Set `SKILL` to the directory containing `SKILL.md`. Run `python3 "$SKILL/scripts/compat_workflow.py doctor` to inspect available tools without launching them. Copy [workflow.json](../examples/workflow.json) and edit its paths. Run `plan --config job.json`, then `run --config job.json`. Read `summary --output reports/job`; `status` returns only its scope and status fields.

| Field | Meaning |
| --- | --- |
| `baseline`, `candidate` | Two supported local inputs. Baseline consumers are evaluated on the candidate |
| `baseline_manifest`, `candidate_manifest` | Alternative pair of prior manifests. Reuse credits original recorded evidence and performs no new collection |
| `output` | New/empty directory outside source inputs. A run retains its exclusive reservation and evidence |
| `objective` | `EXPORT_SYMBOLS` (default), `PACKAGE_INVENTORY`, or `STATIC_REPORT` |
| `rpm_mode` | `payload` (default) or `metadata`. Export objectives require Payload |
| `mode` | `static` (default) or `quick`. Explicit SDK and Runtime operations use their existing CLIs |
| `baseline_rpm_fallback`, `candidate_rpm_fallback` | Both matching local RPM inputs, used only after an EROFS preparation blockage |
| `same_build_confirmed` | Operator declaration required with both fallback paths. The controller does not infer upstream provenance |
| `engine_config` | Optional trusted engine YAML. Relative legacy engine paths used by this workflow are interpreted from that YAML directory |
| `cache` | Dedicated private local ELF cache, optional and disposable. Reuse within a trusted account only |
| `index_output` | Optional separate enhanced report destination. Basic outputs remain available if this stage fails |

The workflow JSON uses only these fields and rejects duplicate keys. The directory containing it anchors relative paths. Explicit workflow inputs and mode take precedence over engine defaults. Legacy CLI relative paths continue to resolve from its invocation directory. Report, cache and index destinations must be separate. Use filesystem ownership to isolate unrelated users and do not share a writable cache across untrusted accounts.

For advanced stages configure SDK and target identities through [execution.md](execution.md). Keep credentials in company-approved credential stores or preauthenticated adapters. YAML and workflow JSON are trusted operator input. They can select host tools and are not a mechanism for running untrusted configurations.

Status dimensions are independent. An `INCOMPATIBLE` result can accompany a `COMPLETE` export objective and overall `PARTIAL` coverage. A metadata-only objective can complete while export collection is intentionally unexecuted. Rootfs detail CSVs match exact paths and emit unmatched paths as observations. Existing ABI Findings retain the engine's verified or unresolved replacement semantics.

A workflow exit 0 requires both the requested objective and configured CI gate to complete. Exit 1 indicates the engine's compatibility or strict/coverage gate failed with a completed objective. Exit 2 is input/configuration failure. Exit 3 is an incomplete required objective or infrastructure failure. Exit 130 denotes interruption of the main collection. The compact summary records optional-index failures independently. The original CLI retains its existing CI gate behavior.

## RPM payload status additions

`comparison_validity` describes observed instrumentation comparability, and `confounders` lists the qualifying kinds and their baseline/candidate shares. Compatibility, coverage, and objective status remain independent. The statistics include instrumentation adjustments, available-set requirement counts, and unsatisfied baseline export identity counts.

A confirmed missing library under complete inventories can finish the export objective with incompatibility and exit 1. An ambiguous or incompletely inventoried match can leave the objective partial and produce the controller's existing exit 3. A defect in a pre-existing baseline requirement remains UNKNOWN. The full available-set failure and uncertainty rows are in requirement-findings.csv with CSV reporting enabled.

## WP-3 report fields and collector limits

Rootfs linking requires the actual side profiles under `loader.environments`
(or profiles recorded in reused manifests). Missing profiles produce one
`LOADER_ENV_MISSING` per absent side and a NOT_EXECUTED linking obligation.
Static SONAME and DT_NEEDED deltas can still appear. A configured but partial
profile yields conditional observations and cannot establish a complete scope.

`results.json` and `run-summary.json` contain `linking_summary` with UNKNOWN
finding counts, up to 20 example IDs per reason and the next action.
Linking findings retain the consumer, provider and representative root.
`roots` holds the total and up to 20 examples. `search_context` records the
relevant paths, loaded SONAME evidence or projected symbol lookup scope.
Finding IDs for linking can change from older reports. Strict mode continues
to fail when a required linking obligation is UNKNOWN or unexecuted.

Repository `requirement-findings.csv` preserves the failed and unknown detail
rows. A suppressed row points to the leading row by `suppressed_by`.
`suppressed_dependents` is the number of represented detail rows.
`by_kind`, `by_reason` and the legacy `finding_count` count individual
requirements. `emitted_count` counts aggregate findings before the existing
per-reason JSON preview limit. An anchor beyond that limit is still in CSV.

The `analysis.timeout_seconds` short-tool default stays at 60 seconds.
`extract_timeout_seconds` defaults to 3600 for SquashFS, RPM payloads and EROFS.
`rpmdb_timeout_seconds` defaults to 900 for installed RPM queries.
`abi_timeout_seconds` defaults to 1800 for abidiff. All three accept integer
seconds from 1 to 86400. A legacy RPM-specific timeout ceiling can still
limit payload extraction. The VDFS adapter keeps its separate setting.
`rpm_payload.max_metadata_bytes` defaults to 128 MiB per archive with a
1 GiB maximum. A timeout records `TOOL_TIMEOUT` and an exceeded capture cap
records `OUTPUT_LIMIT`. The collector log retains bounded output evidence.
The three large JSON files use compact serialization with the same data types.

## WP-3b linking details and symbol reports

The main rootfs CLI stages individual import and GNU version checks in a
workspace-local SQLite scratch database. It streams `linking-details.csv` when
CSV reports are enabled. Each row records the detail ID, its anchor finding ID,
consumer image and path, check ID, state, observed provider path, root count,
and SHA-256 over the full lookup context. The anchor includes a check count and
up to 20 example check IDs. Anchors share requiring object, direction, state,
search flags and the ordered image-qualified provider scope. The hash on each
detail retains the per-symbol evidence distinction. DT_NEEDED observations
stay individual. Confirmed failures also stay individual and link to their
own finding. Coverage uses direct check counts and transitive root relations.
`linking_detail_counts` reports detail totals by state, status and kind.
`linking_summary.count` counts findings and `check_count` counts the represented
checks and remaining individual observations. CSV-disabled runs keep the
counters and omit the detail file.

`report.symbol_differences` defaults to `changes`. Set it to `all` for MATCHED
rows in the CSV. The per-role and global summary retain the MATCHED counts in
both modes. Package assessments link to the manifest symbol inventory using
`symbol_inventory_ref` with image, scope and virtual path. Manifest symbols
and content-addressed evidence are still available to the enhanced index.
It also recognizes the embedded symbol inventories in older reports.

`finding_integrity.missing_reason_codes` audits UNKNOWN and INCOMPATIBLE
findings. `export_incomplete_by_reason` separates incomplete export inventories
from ABI conclusions. `removed_exports` counts removal observations by reason,
binding, type and C++ class. Importer counts cover distinct sampled objects
with exact name and version identities, excluding the provider itself.
