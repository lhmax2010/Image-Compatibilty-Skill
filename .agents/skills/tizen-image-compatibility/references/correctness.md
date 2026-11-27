# Correctness contract (1.2)

Read this before interpreting a migration gate or comparing instrumented builds. Static symbol differences must not be dismissed because names are C++, generated, GCOV or ASAN-related. Equal export counts do not prove equal exports/contracts. Correlate exact baseline imports with candidate providers and retain unresolved type/runtime coverage. Do not invent Tizen validation from synthetic examples.

## Offline loader model

`linker.py` implements a bounded glibc model: absolute DT_NEEDED paths, RPATH with ancestor inheritance, direct-only RUNPATH, `$ORIGIN`, explicit library paths, operator-supplied ordered target-cache entries, default directories, virtual symlinks and transitive dependencies. DT_NEEDED order is preserved. Imported symbols are matched against the dependency scope with their version, binding, visibility and type; version requirements are also checked against the named dependency's definitions. An unversioned export cannot automatically satisfy a versioned import.

Example only — populate from the **actual target configuration** before claiming completeness:

```yaml
loader:
  environments:
    candidate:
      model: glibc
      symbol_scope: startup # Declared executable startup scope only
      namespace: base
      environment_complete: true
      cache_complete: true
      default_dirs: [/lib, /usr/lib]
      library_path: []
      cache:
        libexample.so.1: [/opt/product/lib/libexample.so.1]
```

These assertions mean the supplied search environment is complete, uses the glibc model, and cache entries reflect the **ordered effective choices for the target architecture/hardware**. Empty cache with `cache_complete: true` asserts a disabled/empty cache; it must not be used just to turn unknowns into passes. The host loader, environment, cache and `ldd` are never consulted. `/etc/ld.so.conf` and snippets are inventoried as evidence; glibc uses the generated cache, so config-directory presence alone does not prove resolvability. Binary cache decoding, arbitrary include directives, hwcaps selection, `$LIB`/`$PLATFORM`, relative/CWD paths, audit/filter namespaces, preloads and secure-execution semantics are not fully modeled. Preload/set-ID/unsupported-token cases remain UNKNOWN. Supply a target-specific snapshot or validate through an authorized adapter; do not claim those unsupported cases passed.

`resolution` distinguishes `missing_provider`, `unresolvable_provider`, `unknown_search_environment`, `verified`, `missing_symbol`, `missing_version`, `symbol_type_mismatch` and scope/semantic unknowns. Verified means proven **within the declared offline model**, not executed. Incomplete inventory/search environment prevents definitive missing-provider conclusions. A standalone DSO closure does not prove its process-wide lookup scope and remains UNKNOWN. Multiple eligible providers retain ordered lookup candidates but do not receive verification credit. Unsupported dynamic flags, non-base namespaces, PROTECTED/IFUNC/GNU UNIQUE and weak references require runtime evidence. Versioned imports with unversioned interposition candidates stay UNKNOWN; glibc can support such interposition, so bare-name fallback is not automatically a confirmed missing symbol. Weak absence, IFUNC and GNU unique behavior require runtime evidence. Export-surface removals remain separately reported even when no shipped consumer uses them; external consumers may exist.

Different libgcc_s/compiler-rt/libstdc++/libc++/libc++abi/libunwind implementations are not intrinsically incompatible. Check required versions, ABI, exception/unwind/TLS behavior and actual consumer probes. ARM probe verification uses configured SDK target ABI with provenance, then selected loader/libc objects as supporting evidence. A conflicting authoritative object prevents acceptance; unrelated missing optional attributes do not. It requires an ET_REL compiler probe with matching machine/class/endian, EABI and PCS. CPU architecture tags describe ISA requirements separately; unequal tags are UNKNOWN without suitability evidence, not an automatic ABI break. Mixed/unknown other objects are reported individually. `soft` denotes base PCS, including softfp, not a promise of software-only instructions. Explicit conflict and insufficient evidence have different diagnostic statuses; either prevents an unproven matrix pass. CPU feature support and every ARM attribute are not proven. aarch64 retains machine/class/endian checks; architectural extension support needs target probes.

## DWARF and split debuginfo

```yaml
debuginfo:
  roots:
    baseline: [/artifacts/gcc-debuginfo-root]
    candidate: [/artifacts/llvm-debuginfo-root]
```

Roots are directories, including already extracted debuginfo RPM trees. Search the image and supplied roots for `usr/lib/debug/.build-id/xx/rest.debug`, `.build-id/xx/rest.debug` and `usr/lib/debug/<binary-path>.debug`. Split files must contain DWARF and exactly match the binary's Build-ID. No match or no abidiff yields a per-binary UNKNOWN, not silent omission. The tool stages copies under report `abi-inputs/` and passes separate `--debug-info-dir1/2`; sources remain read-only. Direct RPM extraction, CRC-only `.gnu_debuglink` matching, debuginfod downloads, DWZ alternate files and split `.dwo/.dwp` are not implemented. Extract RPM payloads offline with an approved safe extractor before supplying a root; never install packages into the images.

abidiff bit 8 is a confirmed breaking change; bit 4 alone is an ABI difference requiring review, and bits 1/2 or truncated/error output are UNKNOWN. Existing implementation already distinguished these exit bits correctly. Coverage applies to externally reachable types available to libabigail, not all code behavior or proof that every exported type had DWARF.

## APIs, matrix and coverage

Runtime-image `public_headers` and SDK `sdk_headers` have separate provenance. Lexer equality is evidence only and now stays UNKNOWN for semantic/API compatibility. `cross_compilation.semantic_headers: true` adds configured Clang AST signatures, preprocessor macro evidence, SDK and target metadata. AST comparison remains UNKNOWN for whole-API equivalence: template/inline behavior, layouts and untested preprocessing configurations are not fully compared. Successful header compilation is a narrowly scoped compile check.

Each compiler needs explicit `cross_compilation.builds` SDK, native reference environment and build provenance. Compiler names do not select image roles. Read [execution.md](execution.md) for deterministic expected IDs, mandatory stages, artifact identity, adapter receipts and own-reference requirements. Count equality never proves completion. Read [packages.md](packages.md) for ownership and package aggregation.

`coverage` counts baseline component contracts, not finding rows or all possible external consumers. ABI has separate export-surface and type-layout obligations for each baseline ELF. Other dimensions generally use one baseline component per inventory entry; runtime uses configured matrix cells/custom probes; headers use the expected SDK header test IDs, including unexecuted IDs. An unassessed component stays UNKNOWN. No inventory creates an UNKNOWN discovery obligation, not an empty 100% score. Compatibility outcome is independent of completeness: an INCOMPATIBLE obligation can be PARTIAL. Each obligation lists mandatory checks, evidence and missing-check reasons. No unknown mandatory check earns complete-verification credit.

- applicable = compatible + incompatible + unknown
- verified = completely_verified = number of COMPLETE obligations
- applicable = completely_verified + partially_verified + unexecuted
- NOT_APPLICABLE obligations are excluded; all-N/A and excluded ratios are null
- coverage_percent = 100 × verified / applicable
- compatibility_percent = 100 × compatible / applicable (UNKNOWN remains in denominator)

Both percentages are null for excluded dimensions. `ci.minimum_coverage: {abi: 90, linking: 95}` fails exit 1 below either threshold; a threshold on an excluded dimension also fails. Empty thresholds mean no coverage gate requested, not full compatibility. Adding finding rows cannot inflate coverage. Runtime checks unavailable means runtime coverage is unverified. Static UNKNOWN is still a normal result.

Manifest schemas 1.0 and 1.1 remain readable. Legacy successful tests/matrix cells are explicitly downgraded to UNKNOWN with recorded original statuses because their completeness/expected-test semantics do not satisfy 1.2. Recollect old manifests to obtain version relationships, loader inventory and ARM attributes; missing fields are not inferred as verified. This change is intentional and must not be hidden when comparing reports across versions.

## Reference specifications

- [Linux dynamic linker search rules](https://man7.org/linux/man-pages/man8/ld.so.8.html)
- [GNU ld symbol version nodes and default versions](https://sourceware.org/binutils/docs/ld/VERSION.html)
- [ARM ELF ABI specification](https://github.com/ARM-software/abi-aa/blob/main/aaelf32/aaelf32.rst)
- [libabigail abidiff debug directories and exit status](https://sourceware.org/libabigail/manual/abidiff.html)
- [Clang AST introduction](https://clang.llvm.org/docs/IntroductionToTheClangAST.html)

- [glibc symbol lookup implementation](https://github.com/bminor/glibc/blob/master/elf/dl-lookup.c)

Release-candidate lookup credit requires an explicit boolean resolution_metadata_complete on every relevant collected consumer/provider/loader. The collector establishes it from successful untruncated readelf output with complete dynamic-symbol rows and dynamic-section evidence. Missing/false markers, warnings, malformed or unavailable observations remain UNKNOWN. The flag attests collection coverage within the bounded model, not complete glibc semantics.

## Phase 7A static correctness and manifest reuse

Collector policy `1.3.1-phase7a` retains manifest schema 1.2 and invalidates older content caches through their collector-version key. Recollect inputs to establish the following evidence; missing fields are UNKNOWN, including when reusing schema-1.2 manifests.

- `header_inventory_complete` means the installed include-path header inventory was traversed and decoded without collection failures. It does not attest full SDK availability or C/C++ semantics. A missing header can prove removal only with this evidence and no applicable collection limitation.
- `simple_declarations_complete` and literal `include_directives` enable a bounded (256 files, depth 64) include closure. Only unchanged built-in C prototypes in a fully observed unconditional closure prove declaration availability through the original entry. `declaration_reachability` records PROVEN_PRESENT, POSSIBLE_MIGRATION, PROVEN_ABSENT or UNKNOWN. Typedefs, macros, include guards/conditions, C++ constructs, cycles, unresolved includes and parse gaps require compiler evidence. Angle includes need explicitly recorded `header_include_roots`; no roots are guessed. This scoped COMPATIBLE result is not whole-API or ABI equivalence.
- `export_inventory_complete` requires successful untruncated readelf output without warnings, all advertised dynsym rows, supported attributes and reconciled observed symbol versions. ELF-header `complete` alone cannot prove export/default-version absence or earn export inventory coverage. Observed type/data-size breakage remains actionable when both symbol records exist. ET_REL without dynsym is explicitly NOT_APPLICABLE for collection, not verified dynamic ABI equality.
- Loaded requested names and SONAMEs are reused only within the same proven root/base namespace and load order. An unproven first selection cannot become verified on alias reuse. Isolated DSOs lack caller/loaded-object scope and remain UNKNOWN. Preloads, other namespaces and unsupported loader features remain outside the verified model.
- Baseline-consumer checks receive the baseline manifest explicitly; candidate checks use candidate metadata. Per-object `execution_metadata` is refreshed outside the ELF content cache. Missing permissions/capability observations, setuid/setgid, file capabilities or archive metadata loss cannot establish a normal secure-execution context. Actual credentials, mount policy and AT_SECURE still require target evidence.

The v1.3 report schema, APIs, role definitions and raw findings remain unchanged. Its existing symbol completeness gate now requires the new export marker: old/incomplete manifests retain observed counts but complete totals become null. Rebuilding an old report projection never recomputes detector conclusions. To obtain corrected conclusions, recollect/recompare into a new analysis directory and then build a separate enhanced report. New finding payloads/statuses can produce new content-derived IDs; historical IDs/reports are never rewritten and no equal-count guarantee applies across policies.

## Rootfs linking context and instrumentation

DT_NEEDED analysis preserves per-process loading order. Resolution is reused
only for the same requiring object, effective expanded search inputs, observed
loaded-object evidence and completeness. Import checking also includes the
ordered observations for that symbol, the required provider and version
constraints. Findings with different effective contexts retain separate IDs.
A root count is a relation count, independent of compatibility or coverage.
An indexed group can report a lower bound from root examples when its
underlying root relations are truncated. Comparison of install-tree metadata,
including set-ID and file capabilities, does not prove runtime AT_SECURE.
Linking collects this evidence even when standalone security findings are excluded.

Rootfs and repository reports use the same per-side instrumentation profiles.
An instrumentation share of at least 20% on one side and at most 2% on the other
flags a CONFOUNDED comparison. A particular pair with different instrumentation
can downgrade an OBJECT or TLS size change even below the image-wide threshold.
Complete evidence for a removed ordinary export still supports INCOMPATIBLE.
