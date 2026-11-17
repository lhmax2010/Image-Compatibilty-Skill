# v1.3 report enhancement — known limitations

This release candidate improves navigation of existing observations. It does not establish GCC/LLVM image compatibility, product acceptance, public API stability or runtime behavior.

## Evidence and counting

- The real Phase4 manifests have `collection_complete=false`. Complete package ELF/library/executable/export counts therefore remain UNKNOWN, including packages with no observed ELF. Explicit `observed_*` columns retain useful numeric observations and support sorting. Missing SDK/header evidence remains UNKNOWN. Original ABI/API/Linking outcomes and verification are retained independently.
- Dynamic export counts are not a public API inventory. Equal counts do not establish compatibility. IFUNC is separate from FUNC; a symbol with several changed attributes produces several detail rows but one aggregate changed-symbol observation.
- Canonical identity uses image/scope and recorded virtual symlink resolution. Unrecorded hardlink identity is unavailable. Different objects are not deduplicated solely by SONAME/Build-ID. Shared owners intentionally overlap in per-package totals; use image-unique totals for image totals.
- ELF display matching requires original package peers, unique canonical path or unique SONAME. Candidate-only, unmatched, incomplete or ambiguous comparisons remain UNKNOWN. This does not replace or alter the detector's original matching or outcomes.
- Missing export attributes, conflicting duplicates and incomplete ELF collection prevent complete counts. Observed zero is not a verified zero. The report does not invent SDK, debug-layout, loader-environment, hardware or runtime evidence.

## Linking groups

- A group is a navigation unit, not a new finding or a merged compatibility conclusion. Original IDs, direct/root consumers, providers, ownership, direction, requirements, status and raw payloads remain retrievable. Different recorded requirements/outcomes stay in different groups.
- Reasons are the source `resolution` field. NOT_RECORDED means the original field is absent, not a diagnosis. Reported consumer counts count distinct recorded image/path identities; they do not prove those programs were executed. Package counts distinguish observed associations from complete ownership.
- Evidence existence is a filesystem-presence check, not proof of verification completeness. Original coverage metadata is retained with streamed unit counts; full unit records remain in the unchanged source `results.json`.

## Browser and portability

- Interactive search requires the standard-library, loopback-only HTTP service. Direct `file://` supports only the static overview and complete CSV links. No Internet, external JavaScript/CDN or system installation is needed.
- Browser pages contain 50 rows; the API caps pages at 100. Totals are shown, and JSON payload/CSV access remains complete. Query work has a 20-second SQLite deadline; slow queries fail visibly instead of running indefinitely.
- The derived SQLite index is required for browsing. Original evidence is referenced at its recorded absolute source-report path and is not copied. Moving reports to another machine requires preserving that source location; automatic path migration is not implemented.
- Browser measurements on the available local Chromium are observations for this host, not cross-browser or cold-cache latency guarantees. No real Tizen target program is executed.
- Final measured package detail took about 4.98 seconds and the Linking list 2.41 seconds. Large details can still be slower than the compact lists. Generation was I/O-bound on this host: 38 min 43.5 s plus a 27.8-second navigation-index repair. A single disclosed sequential index pre-read occurred within the measured build interval; this is not an unassisted cold-cache result.

## Resource envelope and retained attempts

- Bounded decoding handles selected arrays record by record and limits the decoder buffer to 64 Mi characters (UTF-8 byte size can be larger). Package/ELF/group calculations retain only their current working records plus metadata indexes; the global resource guard remains authoritative for unusually large inputs.
- The build stops on task RSS above 3 GiB, new output allocation above 15 GiB, free disk below 100 GiB, or available memory below 3 GiB for at least 10 seconds. It logs CPU, memory, swap, pressure and disk samples. No swap/kernel changes or automatic limit increases are made.
- The first real-data attempt was intentionally interrupted to correct incomplete-package counting. At interruption it had reached finding ingestion; the transaction rolled back and no completed statistics were emitted. Its partial manifest index, traceback, metrics and stop reason remain under `headless/work/phase5/real-attempt1-stopped` and adjacent `real-attempt1.*` files. This is disclosed as an interrupted attempt, not a successful performance run.
- Final real-data checks exposed and closed a root-status field mapping bug and a Linking pagination/index performance defect. Display-only refresh and index-only repair evidence are retained; neither changed Finding/Package data. Initial browser selection and pre-index timeouts are preserved alongside the final passing run.
- Five pre-existing optional compiler/libabigail integration tests are skipped on this host. Synthetic report fixtures and actual report reprocessing do not substitute for those integration tests.

No source rootfs, original Phase3/4 report, compatibility detector, existing RC fix, branch reference or remote publication is changed by this report work. Final measured results and any observed blockers are recorded separately in `V1_3_REPORT_VALIDATION.md` and `V1_3_PERFORMANCE.md`.
