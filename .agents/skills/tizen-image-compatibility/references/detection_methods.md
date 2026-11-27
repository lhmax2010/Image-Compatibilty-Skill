# Collection and comparison methods

## Inputs and immutability

The directory reader uses lstat and does not traverse directory symlinks. Absolute file links are resolved against the virtual image root with a hop bound. `/proc`, `/sys`, `/run` are not traversed; special files are inventoried but never opened. Rootfs regular ELF files are identified by magic, not suffix. Existing absolute-link aliases in `/usr/include` and selected configuration paths can be read through the image resolver. Rootfs directory aliases are considered when comparing removed command/config paths.

TAR/TAR.GZ inputs are streamed to a private temporary workspace. Traversal, duplicate paths and link/file collisions are rejected. Regular files and directories are materialized before links. UID/GID/mode/device metadata is retained separately, without creating device nodes or applying source ownership or setuid bits. Hardlinks to unavailable targets are rejected. Entry quotas include hardlink copies and a scratch-space reserve is checked before materialization. Sparse metadata and xattrs are not fully represented. Security coverage remains unknown. Temporary directories are cleaned on completion or error. Reading may change access timestamps under the host mount policy.

Use a **merged rootfs export** for OCI. Apply whiteouts first with an OCI-aware tool. For EXT4, extract using a read-only userspace tool or isolated VM, then supply the rootfs. Single RPMs and recursively discovered local RPM archives support payload or metadata-only analysis in a separate repository scope. See [RPM repository analysis](rpm_repository.md).

## Evidence and determinism

Every external invocation uses argv, C locale, timeout and process-group cleanup. Full stdout/stderr are streamed to temporary files and retained under content-addressed `evidence/*.txt`. Parsing is limited to 16 MiB per stream; truncation becomes incomplete ELF/RPM coverage. JSON-lines `collection.log` includes normalized argv, return code, errors, evidence paths and truncation flags. Source header/configuration text is also retained. Raw evidence can contain original build paths; normalized findings use portable paths where possible.

Manifests record collector/schema versions, discovered utility versions, source format, user-declared compiler provenance, observed ELF architectures and OS metadata. Lists/findings are sorted and finding IDs derive from content. Timestamps are omitted by default. Stable inputs/tool outputs/config produce stable normalized results; raw evidence retains naturally varying external output rather than falsifying it. Absolute source paths are provenance, not compatibility criteria.

`--cache DIR` reuses complete ELF extraction results by file SHA-256, virtual path, cache and collector revisions, mode and readelf/nm identity and version. Use a directory owned by the executing account with no group or other write permission. Concurrent tasks can share that account's cache while using separate report directories. Evidence is published atomically and its content digest is checked before reuse. Missing or damaged cache entries are recollected. Other collectors run again. Failed or incomplete ELF results are not cached.

Trusted host tools have a 16 MiB default combined stdout/stderr cap and a timeout. Protocol-specific callers can choose tighter limits. A tool that exceeds a limit retains bounded evidence and cannot establish complete inventory. ELF collection has four workers by default and permits at most 32. Existing tool processes in their original local process group are reaped. Static analysis does not supervise arbitrary detached processes, so use only trusted configured tools and private, stable input and output directories. Raw evidence can contain local paths and file contents and belongs in the approved report workspace.

Manifest-only comparison needs no source images. Copy the manifests **and sibling evidence directory** to retain raw evidence. Recorded test failures still contribute to CI failure; no new compile/runtime/abidiff execution is claimed. `--exclude` and `analysis.modes` limit findings/CI; common inventory collection can still occur because dimensions share evidence.

## Normalization and classification

ELF instruction bytes, function symbol sizes, build IDs, debug paths and compiler comments do not establish ABI failure. Data/TLS symbol size and symbol type changes are significant. Default symbol versions expose both versioned and unversioned lookup identities. Optional weak imports are not mistaken for removed exports. Removed exports of a matched complete ELF pair are confirmed interface removal. A relocated library is matched by unique SONAME when possible; ambiguous or missing library paths remain unknown until dependencies/consumer evidence establish impact.

Header lexer preserves string/character literals, multi-character operators, macro kind (`f(x)` vs `f (x)`), macro values and preprocessor conditions. Comment/spacing-only differences can be compatible; lexical function changes stay unknown except unconditionally removed simple declarations. The implementation is **not** a semantic AST parser. Conditional macro hints distinguish possible compiler/architecture/feature/SDK context, but do not prove cause.

Only generated timestamp-comment lines and preprocessor line markers are normalized, not arbitrary configuration values or public string constants. Build-path normalization is deliberately narrow. `ignore_build_ids: false` surfaces build ID changes as informational compatible differences; they remain non-interface data. `ignore_timestamps: false` exposes collected filesystem mtimes as unknown metadata differences (archive extraction time is not original device timing). RPM release changes are compatible metadata; version/provides/dependency changes remain unknown pending solver/consumer checks.

Readelf captures the declared dependency graph, and provider inventory checks every object plus baseline consumers against the candidate. The graph detects cycles, but does not implement the runtime linker's search/cache/namespace/version-resolution semantics. Never report an available filename as a proven successful load. Platform consolidation and compatibility symlinks are inventory evidence, not hardcoded glibc assumptions.

System files are never executed: unit ExecStart, shell scripts, udev rules, package scriptlets and configuration commands are text evidence only. XML parsing does not fetch remote entities. HTML escapes all image-controlled strings; CSV protects formula-leading cells. Reports can contain configuration values and should be handled as image-derived artifacts.

## Correctness changes in 1.1

Read [correctness.md](correctness.md) for loader search/closure, version relationships, ARM ABI checks, split Build-ID DWARF, SDK/AST context and coverage denominators. Lexical equality and rootfs-wide SONAME presence do not establish semantic or loader compatibility.

## WP-1 dynamic symbol evidence

GNU readelf can format a large symbol size in hexadecimal. Parsing and advertised-row reconciliation use the same row grammar for decimal and hexadecimal values. A valid GNU version definition can identify its zero-valued ABS marker in either GNU spelling or LLVM's default-version spelling. Marker evidence remains recorded separately.

The primary ELF metadata call omits relocations. Static ARM analysis reads relocations separately. A failed ARM relocation call leaves relocation coverage UNKNOWN independently of the primary export inventory. Both ordinary and RPM ELF collectors use the complete captured primary stream up to `analysis.max_readelf_bytes`. The default is 512 MiB of combined output per invocation and the maximum is 4 GiB. General host-tool capture has a 64 MiB default. An exceeded capture budget sets `OUTPUT_LIMIT` and the available bytes remain in evidence. A partial stream cannot prove export absence.

Export and import observations are kept by decorated identity. When more than one observed row has the same decorated identity, all rows remain in the manifest and distinct ambiguous observations are available in repository symbol details. The export inventory records `DUPLICATE_DYNSYM_IDENTITY`; the ambiguous identity cannot establish compatibility or identical results. ELF cache keys include the bundled collector VERSION, inventory revision and capture budget. Manifest schema remains 1.2.
