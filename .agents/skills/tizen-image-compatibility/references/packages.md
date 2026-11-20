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

Ownership, component coverage and SDK header checks use indexes; complete JSON output streams to disk. Large RPM XML queries stream from full raw evidence rather than the bounded command-output preview; malformed raw XML remains UNKNOWN. JSON still contains the full manifests, exports, checks and evidence associations, so large images require disk and memory proportional to collected records and relationships. The original offline HTML limits previews. For full paginated navigation, use the enhanced SQLite report.

RPM dependency solving, automatic rename/split identification, exhaustive public-API policy and target runtime behavior still need product-specific evidence. Current package ownership does not execute package payloads or install into source images.

- [RPM query options and database interface](https://rpm.org/docs/4.20.x/man/rpm.8)

## Acceptance accounting

Count reconciliation is explicit for runtime and SDK inventories. Every reliable candidate package also appears in `candidate_assessments`; unsupported-provenance records remain in `unverified_package_records`. Provider/consumer edges and interface-path finding indexes make associations inspectable. Replacement hints distinguish possible renames/replacements and splits from unrelated candidate additions; shared paths alone never verify a relationship. Data-only packages with complete N/A evidence have overall NOT_APPLICABLE, not a package compatibility pass.

## Report-only export accounting (v1.3)

Count symbols by `(image, scope, canonical virtual ELF path, exact decorated export name)`. Resolve only symlinks recorded in the manifest; never follow image paths on the host. Identical duplicate export rows count once; conflicting attributes or incomplete ELF metadata prevent complete counts. FUNC and IFUNC/GNU_IFUNC are separate. Version/default-version, binding and visibility remain available in symbol attributes. Hardlink identity is unavailable and is not inferred from SONAME or Build-ID.

Within each package, canonical ELFs count once even if several RPM paths are aliases. Shared file owners stay explicit: package-attributed totals can exceed image-unique totals. Missing file inventory, `collection_complete != true`, ambiguous ownership or incomplete ELF data yields UNKNOWN complete counts with separate observed counts. This includes owned ELF/library/executable counts: a partial manifest with no collected ELF cannot establish a complete zero. Missing SDK/header data yields UNKNOWN header count, not zero or API compatibility. Browser FUNC/missing sorts explicitly use observed counts so partial inventories remain useful without acquiring verification credit.

Report pair matching requires original known package peers, then unique canonical same-path or globally unique canonical SONAME matching. Ambiguous/missing pairs have UNKNOWN comparisons; candidate-only inventory does not imply compatibility or a trusted reverse assessment. Exact decorated symbol names match first; unmatched base names pair for version changes only when unique on both sides. These statistics do not change original package outcomes or detection semantics. A version change or equal export count never supplies new verification credit.
