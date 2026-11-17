# Installed package compatibility (1.2)

Package analysis answers which installed baseline package owns an affected interface, what candidate package can be matched, and which required checks remain unresolved. It does not infer installed packages from every RPM file found on disk, or prove source API compatibility from runtime binaries.

## Inventory and ownership

The collector queries a temporary copy of an actual RPM database; source images remain unchanged. RPMs found as archives are queried independently into `available_packages` with `rpm_archive` provenance. Installed records use `installed_rpmdb` provenance and retain epoch, name/version/release/architecture, dependency capabilities, complete file lists, collection status and evidence. A missing, unreadable or unsupported database produces UNKNOWN with `installed_count: null`. An empty directory is not a successful empty database query. An actual successfully queried empty database can have count zero. RPM collection inputs provide archive availability, not installed package ownership.

Matching groups by name/architecture/scope and requires a unique identity on each side. All parallel NEVRAs and duplicate identities remain visible. Multiple matches are unresolved; absent candidate metadata does not prove removal. Renames/splits/replacements remain UNKNOWN; compare provided interfaces separately. Candidate-only packages are inventory additions, not compatibility failures.

Indexed ownership uses RPM file lists and virtual-root canonical paths, including usrmerge aliases. A symlink's package and its target implementation package remain distinct. Missing/multiple/incomplete owners stay unknown. Linking evidence records the immediate consumer, candidate provider and affected root consumer. A transitive dependency failure reaches the affected executable package without assigning its consumer contract to an unrelated provider package. Files absent from ownership inventories stay in `unassigned_interfaces`; findings without reliable associations remain available globally.

## SDK headers and development packages

Collect SDK rootfs metadata separately and explicitly associate its manifest:

```bash
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline /sdk/gcc/sysroot --candidate /sdk/llvm/sysroot \
  --mode static --output ./reports/sdk-inventory
```

```yaml
cross_compilation:
  sysroots:
    baseline: /sdk/gcc/sysroot
    candidate: /sdk/llvm/sysroot
  sdk_package_manifests:
    baseline: ./reports/sdk-inventory/baseline-manifest.json
    candidate: ./reports/sdk-inventory/candidate-manifest.json
```

The manifest's `image.source` must resolve to the configured SDK root. It must contain reliable installed package provenance and file lists. An SDK with no RPM database cannot acquire installed ownership by naming a similarly named runtime package or scanning archive filenames. Such headers stay unassigned. SDK ELF objects do not borrow runtime ELF coverage at the same virtual path; assess the SDK separately for its ABI/linking contracts. Reusing a relocated manifest needs a fresh collection/explicit source identity; paths alone cannot attest SDK contents.

## Interpreting rows

Each baseline package has separate availability, metadata, ABI, API and dynamic-linking obligations. Known breaks remain INCOMPATIBLE even when type/layout, headers, ownership or runtime checks are incomplete. Completeness is reported independently; partial failures do not earn full coverage. Version equality alone never verifies ABI/API. Runtime libraries without a development inventory have UNKNOWN API coverage. Header compilation and AST observations do not establish every macro/template/inline/semantic contract.

NOT_APPLICABLE requires complete installed/file inventory evidence, no owned relevant ELF/header/development interfaces, no unsupported interface-like files and no ownership ambiguity. It is not a fallback for absent tooling. Per-package coverage is the COMPLETE share of applicable availability/metadata/ABI/API/linking obligations; each interface dimension exposes its own sub-check coverage.

Reports include all baseline rows in `package_results` and `packages.csv`. JSON includes owned ELF objects, full public symbols, headers, related findings, missing interfaces, coverage gaps and evidence. HTML shows searchable expandable previews for 1000 packages; Markdown shows 200. Both identify their caps; machine reports remain complete. IDs can be joined to global `findings` for full details. Available archives and candidate additions are separate inventory sections.

## Scale and boundaries

Ownership, component coverage and SDK header checks use indexes; complete JSON output streams to disk. Large RPM XML queries stream from full raw evidence rather than the bounded command-output preview; malformed raw XML remains UNKNOWN. JSON still contains the full manifests, exports, checks and evidence associations, so large images require disk and memory proportional to collected records and relationships. Reports are not a database-backed browser; HTML search only covers its displayed subset. The synthetic benchmark at `tests/review/benchmark_v12.py` checks 2000 package pairs and 20000 findings, including full CSV rows and a partial incompatible result. It is metadata stress evidence, not measured performance on a real Tizen image. See repository-root `V1_2_VALIDATION.md` for measured time/RSS and remaining limitations.

RPM dependency solving, automatic rename/split identification, exhaustive public-API policy and target runtime behavior still need product-specific evidence. Current package ownership does not execute package payloads or install into source images.

- [RPM query options and database interface](https://rpm.org/docs/4.20.x/man/rpm.8)

## Acceptance accounting and regression budgets

Count reconciliation is explicit for runtime and SDK inventories. Every reliable candidate package also appears in `candidate_assessments`; unsupported-provenance records remain in `unverified_package_records`. Provider/consumer edges and interface-path finding indexes make associations inspectable. Replacement hints distinguish possible renames/replacements and splits from unrelated candidate additions; shared paths alone never verify a relationship. Data-only packages with complete N/A evidence have overall NOT_APPLICABLE, not a package compatibility pass.

The version-2 stress fixture includes 2000 package pairs, 20000 export-removal findings, 2000 cross-package linking findings, 200 API gaps and one unowned finding (22201 total). Its verifier reads JSON/CSV back and compares exact ID multisets, statuses, ownership and dependency edges, plus exact HTML previews and Markdown package rows. It checks no finding is lost between package associations and global unassigned records. Default budgets are 30 seconds and 768 MiB including serialization/readback; configure these for the runner. `--reference previous/benchmark.json --max-regression-factor 2` rejects significant measured regression at the same fixture version/scale. Reference validation is not a proof of asymptotic complexity or actual Tizen performance.

A small generated report is available in [examples/package-report](../examples/package-report/README.md). Full regression mapping, measured results and production prerequisites are linked from the repository README.
