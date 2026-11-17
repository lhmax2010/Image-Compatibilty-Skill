# v1.3 report enhancement — performance evidence

The real report build and final browser checks completed. Generation and browsing measurements are reported separately; synthetic measurements do not substitute for these results.

## Retained synthetic benchmark

The original `tests/review/benchmark_v12.py` is unchanged. It generated 2000 package pairs / 22201 findings and re-read JSON/CSV/HTML/Markdown, IDs, ownership and provider edges.

- Original benchmark: 3.723 seconds wall time, 366.8 MiB peak RSS; default 30-second / 768-MiB budgets passed unchanged.
- Initial enhanced projection of that benchmark: 15.538 seconds, 190636032 bytes process peak RSS (181.8 MiB); all reconciliation checks passed.
- Evidence: `headless/work/phase5/benchmark-2000-source/benchmark.json`, `benchmark-2000-enhanced/run.json`, `benchmark-legacy.time`, `benchmark-enhanced.time`.
- Subsequent completeness protection was exercised by the full regression suite; synthetic complete manifests retain their complete counts. The report-only changes do not alter the benchmark detector.

Synthetic Chromium navigation was measured on the installed local browser, without installing software. Initial overview rendered in 2593 ms; package name search in 182 ms. These are host-specific, warm/cold-cache-uncontrolled observations. Full route timings and JavaScript exception results are in `work/phase5/browser-synthetic.json`. The browser profile is isolated under this task's work directory.

## Real processing protocol

Input: the unchanged Phase4 report, with 3,928,044,612-byte results.json, 977,771,249-byte findings.csv and 252,842,383 / 270,972,323-byte manifests. No full results.json load or original report copy is performed. The separate index uses losslessly compressed per-finding JSON and disk-backed indexes. Complete CSV exports are written serially.

Limits remain RSS 3 GiB, output 15 GiB, disk free 100 GiB, sustained available memory 3 GiB. Resource checkpoints sample RSS/process high-water RSS, CPU, memory, swap, pressure and disk; stop conditions retain evidence. No swap/system adjustment or budget increase is made.

An initial real ingestion was intentionally interrupted at 81.241 seconds to correct package completeness accounting; its peak sampled resources and partial index are retained in `work/phase5/real-attempt1-stopped/run.json`. That attempt did not produce a completed enhanced report.

## Final actual measurements

Completed build (`run.json`): **2323.513 seconds (38 min 43.5 s)**, **367009792 bytes peak RSS (350.01 MiB)**, **7043948544 allocated bytes (6.560 GiB)** before the final navigation index. CPU time was 378.503 seconds. No configured resource limit was exceeded. The final navigation index added about 18 MiB; its measured creation/verification took **27.758 seconds**, with 168.45 MiB process peak RSS, and left group/data rows unchanged. Final retained allocation after this repair was **7062659072 bytes (6.578 GiB)** before the small final audit records.

| Build stage | Seconds |
|---|---:|
| Baseline manifest | 7.478 |
| Candidate manifest | 8.080 |
| Findings/assessments ingestion and indexes | 1942.416 |
| Canonical ELF matching | 1.284 |
| Symbol observations | 45.337 |
| Linking grouping | 60.894 |
| Package statistics | 38.539 |
| Complete CSV exports | 48.165 |
| Built-in independent reconciliation | 87.608 |

The build total also includes input hashing, assets and final immutability hashes. The separate final serialized readback took **74.313 seconds** and passed. It verifies exact Finding/member/unassigned fields and fixed real Phase4 totals, rather than only counting rows.

The host exhibited sustained disk-page I/O waits. One disclosed, read-only sequential pre-read of the in-progress SQLite file covered 3826196480 bytes in **624.213 seconds**, using 14.35 MiB process peak RSS. It ran within the measured build interval; do not add that time again to the build wall time. It did not write database bytes, raise limits or change system settings. Evidence: `work/phase5/INDEX_PREREAD.json` and `io-observations.jsonl`. The reported speed is therefore **not an unassisted cold-cache benchmark**. Initial browser/group query failures and the index repair are retained, not hidden behind the final PASS.

| Complete CSV | Data rows (header excluded) |
|---|---:|
| package-symbol-summary.csv | 1458 |
| elf-symbol-summary.csv | 2090 |
| symbol-differences.csv | 322036 |
| linking-findings-groups.csv | 134402 |
| linking-unknown-reasons.csv | 9 |
| finding-index.csv | 898342 |
| linking-group-members.csv | 855522 |
| unassigned-findings.csv | 11111 |

The symbol CSV contains 23580 ADDED, 12069 MISSING, 133702 SIZE_CHANGED, 1568 BINDING_CHANGED, 134842 MATCHED and 16275 UNKNOWN rows. No TYPE_CHANGED, VISIBILITY_CHANGED or VERSION_CHANGED observation was produced for this input; those categories have positive synthetic regression fixtures. These are display observations, not additional ABI findings.

### Actual local Chromium, final successful run

| Interaction | Render/query-to-visible time |
|---|---:|
| Initial overview | 529.9 ms |
| Package list | 220.5 ms |
| Name search | 162.4 ms |
| glibc package detail / owned ELF list | 4975.6 ms |
| ELF / first 50 symbol rows | 223.5 ms |
| Linking group list | 2407.6 ms |
| Group → original members | 162.5 ms |
| Original finding payload | 58.8 ms |

No JavaScript exceptions were recorded. The HTML file is about 11 KiB; rendered overview DOM was 21639 characters. Full findings are not embedded in initial HTML. List endpoints defer multi-MiB coverage and group evidence to details. The final browser test used an existing isolated Chromium profile and warm/uncontrolled filesystem caches; it is not a cold-browser or cross-platform guarantee. Larger package details remain materially slower than list/search pages. Exact browser telemetry: `work/phase5/browser-real.json`.

Resource samples, original `/usr/bin/time -v` results, interrupted-attempt records, source hashes, stage timings and validation JSON remain available. The full input hash audit includes a documented pause to serialize disk work; its elapsed time is separate from build/browser performance. No Runtime/Full/image execution or system installation was performed.
