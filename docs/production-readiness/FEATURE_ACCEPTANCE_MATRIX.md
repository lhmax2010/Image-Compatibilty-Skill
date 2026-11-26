# Feature acceptance matrix

Fresh execution used local inputs. Historical SR and Pi evidence is identified separately.

| Capability | Designed / implemented | Actual execution and evidence | Negative case or limit |
| --- | --- | --- | --- |
| Rootfs directory | Yes / yes | Real GCC fixture through controller, per-library and per-symbol CSV. `test_workflow.py` | No ELF leaves objective NOT_EXECUTED |
| TAR and TAR.GZ | Yes / yes | Plain and compressed archives of real ELF fixtures reached the detector, source hashes unchanged. `test_workflow.py` | Controlled path/link and budget failures exercise the same extractor |
| Single RPM | Yes / yes | Real ARMv7l RPMs built with GCC 14.2 and Clang 22.1.8, read-only SDK mounts, ELF32/EABI5/Base PCS, versioned removal/addition. [Reproduction](validate_arm_rpms.py) | Synthetic libraries. ARM target code unexecuted |
| Recursive RPM | Yes / yes | Reused 9/9 archive fixture and two-package demo. Real ELF, same-path distinct packages, variants/architectures, noarch, ASAN import, IFUNC/TLS, mangling and sizes. `test_rpm_payload.py` | One corrupt archive, 8/9 extracted on candidate, export objective PARTIAL |
| RPM metadata | Yes / yes | Real RPM headers, metadata objective and zero ELF. `test_rpm_payload.py` | EXPORT_SYMBOLS with metadata mode rejected |
| Manifest reuse | Yes / yes | Real rootfs and RPM replay preserve recorded export evidence and detail counts. `test_workflow.py`, `test_rpm_payload.py` | Invalid repository archive/object references rejected |
| Standard EROFS | Yes / yes | Format/parser and controlled extraction receipt exercised. Read-only input and captured stderr. [Image guide](../../.agents/skills/tizen-image-compatibility/references/image_preparation.md) | NOT VERIFIED on actual EROFS. Local mkfs.erofs and fsck.erofs unavailable |
| EROFS RPM fallback | Yes / yes | Unsupported synthetic EROFS and two explicit real RPM inputs exercised end to end. Extraction receipt and actual ELF present. `test_rpm_payload.py` | Unconfirmed input pair rejected. Matching build claim is operator evidence |
| Samsung EROFS and VD repositories | Adapter and workflow available | NOT VERIFIED, requires admitted actual image/decoder or real paired RPM repositories | Internal inputs were unavailable |
| ELF and GNU versions | Yes / yes | Real ELF, exact qualified/default version distinction, ABS filtering, exact space-containing symbol names, real removal and data/code sizes | Missing/truncated inventory cannot prove absence |
| Ownership and Linking | Yes / yes | Synthetic installed package/loader regression, historical SR static analysis. Demo shows consumer import and candidate export evidence | Installed provider, namespace, secure execution and actual target remain separate |
| Reporting, Impact and History | Yes / yes | HTML/CSV/JSON, Chromium, small SQLite pagination and current integration regressions | Full-size real SR SQLite remains NOT VERIFIED |
| SDK and Runtime | Yes / explicit routes | Current ARM SDK build/link and historical Pi observations. Regression checks expected plan, exact binding and cleanup | New device execution absent, formal headless 0/8 |
| Resource and side effects | Yes / bounded stages | Controlled disk refusal, output cap, timeout, interrupt, concurrent output and cache tests | Use OS quotas for whole-job limits. [Audit](SECURITY_AND_SIDE_EFFECTS.md) |

## Independent RPM counting

The audit reads two manifests and the CSV without importing collector or report code.

| Counting unit | Baseline | Candidate |
| --- | ---: | ---: |
| Raw export observations | 18 | 18 |
| Distinct export base names | 9 | 10 |
| Per-ELF lookup identities, including the unversioned alias of a default definition | 36 | 36 |

The 25 difference rows contain 19 EXPORT and 6 IMPORT records. They include 16 matched, 5 added, 3 changed and 1 missing. Only one of the five added rows is an export. The candidate has 88.89% payload coverage and the required Export objective is PARTIAL. [Independent reconciliation](audit_rpm_counts.py)
