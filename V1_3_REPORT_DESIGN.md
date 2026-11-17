# v1.3 Report Enhancement — design before implementation

Scope: an additive, offline report renderer for existing schema-1.2 reports. The detector, collector, finding IDs, source statuses, package assessments, coverage and original reports remain unchanged. No new Static/Full/Runtime run is needed. Current branch is `review/tizen-compatibility-correctness-1.2`, HEAD `2d5baca`; pre-existing local RC changes are retained. A file snapshot and original Git diff are saved outside the repository in `headless/work/phase5/`.

## Existing data and limits

- `baseline-manifest.json` / `candidate-manifest.json`: `elf_objects[].exports` retains decorated names, versions/default versions, type, binding, visibility, size/value and evidence. These are dynamic exports, not a public API policy. `filesystem` retains virtual symlink resolution. There is no reliable inode/content identity for hardlinks.
- `package_results[].owned_interfaces` and `package_inventory.candidate_assessments[].owned_interfaces` retain the original package-to-ELF/header associations, including ambiguity. The baseline result owns the directional ABI/API/Linking/Overall/Verification/Coverage/Confidence/Limitations assessment. Candidate inventory alone has no reverse compatibility proof.
- Existing ELF comparison uses the same path, then a unique SONAME fallback. For display statistics we additionally require a unique existing package match and canonical ELF match; ambiguous matches become UNKNOWN. No report-only match changes a detector result.
- Findings retain `package_ownership.consumer`, `candidate_provider`, optional `root_consumer`, image labels, `check_id`, `resolution`, interface, evidence and original ID. Missing reason or environment fields cannot be reconstructed as facts.
- Current HTML previews 1000 findings/packages; Markdown previews 200. Both retain full machine outputs, but the HTML search only covers the preview.
- Phase4: 898342 findings, 855522 Linking, 39744 ABI, 11111 unassigned, 722 baseline / 736 candidate packages. The raw `results.json` is 3928044612 bytes. Phase4's independent distribution reports show 405549 transitive-consumer observations and no exact duplicate payloads. Known resolution states are reused as labels, never promoted to diagnoses.

## Storage and browsing

Add `scripts/enhance_report.py` and report-only modules. Stream the two manifests and results through bounded record decoding into a disk SQLite index. Never load all results or all findings into memory. Preserve every finding, including unassigned records, as a losslessly compressed JSON payload in SQLite with its original ID/status and payload hash. Do not copy the full original report or evidence tree. Record source hashes and relative links to original evidence.

Generate the five requested CSVs, an overview, package/ELF/symbol views and Linking reason/group indexes. A small HTML/JS application uses a standard-library, loopback-only read-only server for indexed pagination/search/sorting, including all findings. This avoids embedding hundreds of thousands of groups or duplicate package indexes in HTML. Tables use text nodes; all API queries are parameterized and bounded. Direct `file://` supports the static overview and CSV/source links, **not** the interactive browser; the page and documentation must explicitly show the local server command. No Internet or package installation is needed. Finding ID lookup returns the exact original payload. No endpoint executes analysis, modifies data, or exposes arbitrary filesystem paths.

## Counting and matching contracts

Canonical identity is `(image, scope, virtual path after recorded symlink resolution)`. Do not merge unrelated objects merely because their SONAME or Build-ID matches. Preserve aliases, original owners and evidence. Hardlink/content identity not recorded by the collector remains a documented limitation. For each package count each canonical ELF once; shared ownership remains explicit. Image totals use distinct canonical ELFs, while package attribution totals can overlap and must expose that overlap.

Symbol identity is the exact decorated export name (base/version/default-version preserved) within one canonical ELF. Identical duplicate rows count once; conflicting duplicate attributes are ambiguous. FUNC and IFUNC are separate; OBJECT/TLS/WEAK/versioned counts are explicit. Report observed counts separately from complete counts. Missing/incomplete inventory, unresolved ownership/matching or missing SDK/header evidence produces null/UNKNOWN, not an invented zero.

Complete package counts additionally require the source manifest's `collection_complete == true`, including complete owned-ELF/library/executable counts. The real manifests record false, so their observed export counts remain useful while their complete package inventory counts stay UNKNOWN. FUNC/missing browser sorts use explicitly labeled observed counts. A stopped first ingestion attempt and its output are retained in `work/phase5/real-attempt1-stopped`; this completeness guard was corrected and tested before the final build. No resource limit was raised.

Display differences use exact symbol identity first, then a unique unmatched base-name pair for version changes. Ambiguous or incomplete comparisons yield UNKNOWN. Emit MISSING, ADDED, TYPE_CHANGED, SIZE_CHANGED, VISIBILITY_CHANGED, BINDING_CHANGED, VERSION_CHANGED, MATCHED and UNKNOWN as observation labels. FUNC code-size changes are not new ABI failures. Existing related ABI findings supply compatibility statuses and IDs; a match without such a finding does not acquire a new COMPATIBLE verdict. MATCHED observations do not create new findings.

Keep candidate-only packages as inventory additions with UNKNOWN comparisons. Keep all original baseline package assessments verbatim in the report index. Candidate rows link to the applicable baseline assessment and retain their original candidate status.

## Linking aggregation

Analyze the actual resolution/status/interface/provider distribution before presenting groups. Group only for navigation using recorded status, resolution (or NOT_RECORDED), interface/check, direction/image labels, provider and required/observed values. Direct/root consumer paths are retained as members rather than discarded. Different recorded requirements or outcomes cannot share a group. A group is not a new compatibility conclusion.

Each group has a deterministic ID, raw count, distinct direct/root consumers and package associations, evidence presence (not proof of completeness), paged original finding references, and a searchable ID index. Affected-package counts distinguish known owners from unknown attribution. Reason totals and group membership must reconcile exactly to every original Linking finding, including records without a resolution field.

## Validation and resource envelope

First test synthetic reports covering multiple ELFs, symlinks, symbol kinds/versions/changes, ambiguous ownership/matches, candidate-only packages, missing SDK/debug data, grouping, large records and HTML/CSV escaping. Run existing tests and preserve the 2000-package/22201-finding benchmark. Then perform one report-only enhancement of Phase4 into `headless/reports/phase5-report-enhancement/`.

Monitor memory, process-tree RSS, CPU, swap and output/disk use. Stop on sustained MemAvailable below 3 GiB, task RSS above 3 GiB, output above 15 GiB, or disk below 100 GiB. Do not raise limits, modify swap, install tools, delete historical data or retry indefinitely.

Acceptance includes exact finding IDs/statuses/payload hashes, unassigned IDs, all baseline/candidate package rows and unchanged assessments, canonical ELF-to-package symbol accounting, complete group membership, source immutability, bounded HTML loading and measured browser behavior where an existing browser is available. All gaps remain explicit. No commit/push/merge is authorized.
