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
