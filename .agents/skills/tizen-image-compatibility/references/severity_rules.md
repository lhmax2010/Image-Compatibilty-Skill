# Status, severity and CI policy

Statuses and severity are separate. Different does not imply incompatible.

| Status | Meaning |
|---|---|
| IDENTICAL | Measured interface surface equals the baseline; no conclusion about unmeasured dimensions |
| COMPATIBLE | Evidence supports the specific change/test, such as an added export, release-only metadata or successful deterministic probe |
| INCOMPATIBLE | Confirmed missing/changed exposed contract or observed regression against a valid baseline |
| UNKNOWN | Missing tools/debug info/SDK/environment, incomplete input, ambiguous semantic change or unexecuted check |
| NOT_APPLICABLE | No detected userspace subsystem for a scoped check; does not infer physical hardware absence |

Default CRITICAL findings: ELF class/endian/machine mismatch; missing required dynamic loader when collection is complete. HIGH: missing export/version, changed data/TLS size/type, removed public header/unconditional prototype, missing command, missing DT_NEEDED provider, incompatible D-Bus contract, confirmed header/behavior regression. MEDIUM: ambiguous configuration/SDK/interface differences. LOW: environment provenance and optional binary-size budget. INFO: additions, normalization and explicit coverage limitations. File metadata or policy changes remain unknown without effective access-control evidence.

`severity_overrides: {abi: CRITICAL, performance: MEDIUM}` changes severity by dimension. `ci.fail_on: HIGH` fails only INCOMPATIBLE findings at HIGH or CRITICAL. `--strict` additionally fails **every UNKNOWN**, regardless of severity; offline runs normally have unknowns. Excluded dimensions do not contribute severity failures, but a configured minimum-coverage threshold on an excluded dimension fails. Global report status remains UNKNOWN when coverage is incomplete, even if CLI exit is 0. Performance size-budget failures remain their own dimension, never ABI/API failures.

The finding confidence is high for direct complete symbol/contract evidence, medium for static contextual changes, low where tool/type coverage is insufficient. Explain evidence and recommended verification instead of treating confidence as a probability.
