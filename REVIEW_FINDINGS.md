# Correctness review findings

Reviewed revision: `386a284c37b0fdf105948bef35d1bacdc7a9c389` (collector 1.0.0). Review date: 2026-11-16. Scope: existing offline-first framework, not a rewrite. All reproduced ELFs and adapter results below are **synthetic**, not Tizen TV results. No source image was supplied from the other workstation.

Original independent reproduction is retained in [before.txt](.agents/skills/tizen-image-compatibility/tests/review/before.txt). The script [reproduce.py](.agents/skills/tizen-image-compatibility/tests/review/reproduce.py) accepts `COMPAT_SCRIPTS` to inspect an older checkout. The original 36 tests passed in an isolated `git archive HEAD` checkout before evaluating the new regression suite.

## F1 — P0 / CRITICAL: inventory mistaken for loader resolution

- **Location:** original `scripts/compat/compare.py::dependency_checks()`; corrected implementation delegates to `compat/linker.py`.
- **Root cause:** a union of all ELF basenames/SONAMEs and symlink basenames suppressed missing-dependency findings regardless of search paths. No imported-symbol, dependency closure or version-requirement checks existed.
- **Minimal reproduction:** compile a versioned `x.so` with GCC/readelf, place its manifest path in `/opt/hidden`, and make `/bin/client` need `x.so` with no RPATH/RUNPATH. Also require an absent symbol. Original output was `[]`, silently suppressing both defects. A provider anywhere is not proof the loader can find it.
- **Correction:** explicit glibc search environment, RPATH ancestry, direct RUNPATH, ORIGIN, ordered cache/default/library paths, virtual aliases, closure and scoped symbol/version matching. Distinct machine-readable resolution states. Complete inventory and search context are required for definitive failure/success conclusions. Baseline consumers are checked against candidate providers separately from candidate's own dependencies.
- **Verification:** `LoaderTests` positive/negative path, cache, symlink, unknown-token, weak/plugin scope, TLS, IFUNC, loader absence, cycles and version-provider tests; `RealELFTests.test_real_elf_hidden_provider_and_import_failure` compiles actual ELF dependencies. Making the hidden directory reachable verifies resolution; removing the required export causes failure.
- **Remaining limits:** this is a declared, bounded glibc model. Binary cache decoding, arbitrary loader config includes, hwcaps, caller namespaces, interposition and dlopen behavior are not fully implemented. Unknown context is preserved. A supplied cache must reflect actual target choices; it is not inferred from all SONAMEs.

## F2 — P0 / HIGH: version relationships and lookup roles lost

- **Location:** `compat/elf.py::parse_readelf()`, `compat/compare.py::exports()/compare_elf()`.
- **Root cause:** `.gnu.version_d` and `.gnu.version_r` names were flattened into one list; provider filenames, definition parents, flags and indexes were lost. `exports()` transformed `@@` to `@` and inserted a synthetic bare-name alias. The original raw symbol name did remain inside each record; not every existing version comparison was wrong.
- **Minimal reproduction:** a real DSO containing `foo@V1` and `foo@@V2`, with `V2` inheriting `V1`, produced no definition/requirement records and lookup keys `foo@V2`, `foo`, `foo@V1`. A linked consumer's required provider/version relationship was unavailable.
- **Correction:** retain lossless raw export keys and structured base/version/default/index/provider fields. Parse definition parents and per-provider requirements. Separate explicit version lookup from default lookup; an existing `foo@V2` satisfies the explicit version but does not prove default lookup survived. Binding, visibility and type remain explicit.
- **Verification:** actual dual-version ELF and linked-consumer fixtures; default removal negative and unchanged positive controls; bare/wrong-version provider negatives; definition-on-wrong-provider negative. Raw `@` and `@@` are distinct in reports.
- **Remaining limits:** symbol-level compatibility does not establish function signatures/layouts or runtime interposition. Legacy schema 1.0 relationships cannot be reconstructed; recollect them. The original implementation already detected many missing versioned exports and default removals; those protections are retained.

## F3 — P0 / CRITICAL: compiler role conflation and invalid native reference

- **Location:** `compat/testing.py::run_matrix()/run_target()`, `compat/elf.py` target metadata.
- **Root cause:** `gcc → baseline` and `clang → candidate` were hardcoded, but every runtime result used the baseline image as behavioral reference. Adapter process success was treated as target execution; machine/class/endian alone ignored ARM EABI/float PCS. Header probes combined runtime-image headers with SDK configuration.
- **Minimal reproduction:** configure the `clang` slot with an explicitly chosen synthetic GCC compiler (family-role label under test), build its artifact on candidate, and use a Python adapter that returns 0 on baseline and 1 on candidate without executing the ELF. Old results: baseline `COMPATIBLE`, candidate `INCOMPATIBLE`, even though the artifact failed its own native environment. This is a harness simulation, not execution evidence.
- **Correction:** explicit compiler → SDK/reference-image/provenance mapping; no mapping means no inferred runtime build. Record ARM attributes/EABI/float PCS and compiler macros. SDK headers are collected independently. Stage-specific compile/deployment/execution/behavior results require identity/hash-bound adapter JSON receipts; direct target invocation is rejected. An artifact must pass its own reference image before either destination receives behavioral compatibility credit.
- **Verification:** swapped GCC/candidate mapping with actual compiled minimal artifact and simulated adapters, own-reference failure/success controls, invalid hash/identity/deployment/absent receipt negatives, no-authorization/no-runtime exclusions, real Clang ARM hard/soft object generation, SDK-only header compilation. No target artifact is executed by these matrix tests.
- **Remaining limits:** an operator adapter is a trusted boundary, not cryptographic attestation of device isolation. SDK origin metadata is operator-supplied; no GBS server integration or full compiler-internal search attestation is implemented. ARM CPU features and every ABI attribute are not exhaustively validated. Real Tizen SDK/devices remain required.

## F4 — P0 / HIGH: deep ABI omissions invisible per library

- **Location:** original `compat/compare.py::advanced_abi()`, now `compat/debuginfo.py`.
- **Root cause:** only pairs with embedded `.debug_info` were processed. Stripped DSOs with matching split debug files were skipped, and multiple unprocessed libraries collapsed into one generic coverage finding. This prevented an accurate coverage denominator.
- **Minimal reproduction:** two no-DWARF library records with an available mocked abidiff path produced only `('*', 'DWARF coverage')`. An objcopy-stripped, Build-ID-bearing DSO with matching external DWARF was also excluded by the old embedded-only condition.
- **Correction:** per-baseline-runtime-ELF type-layout obligations; embedded or Build-ID-matched split DWARF from read-only image/external roots, including extracted RPM trees. Original ELF/debug files are copied into report staging before libabigail. Missing tool/data/pair emits per-object UNKNOWN. Exit-bit classification is preserved.
- **Verification:** real objcopy split files; correct and incorrect Build-ID tests; real libabigail 2.4 embedded and split-DWARF equal/breaking layout cases; mocked exit 0/4/8/12/1/2/-1 controls; missing-tool coverage cannot increase compatibility.
- **Remaining limits:** automatic RPM extraction, CRC-only debuglink, DWZ alt files, .dwo/.dwp and debuginfod are not implemented. Supply an offline safely extracted debug root. One successful libabigail comparison covers reachable types available to the tool, not a proof of DWARF completeness for every export.

## F5 — P1 / HIGH: lexical equality overstated as semantic API compatibility

- **Location:** `compat/compare.py::compare_api()`, `compat/testing.py`, new `compat/semantic.py`.
- **Root cause:** equal header tokens/macros/conditional text returned IDENTICAL/COMPATIBLE without proving includes, predefined macros, target ABI or SDK semantics. Runtime rootfs headers were treated as development-header inputs.
- **Minimal reproduction:** `int f(void);` versus `/* comment */ int f(void);` returned COMPATIBLE. That proves normalized token equality, not that both SDK contexts expose an equivalent API.
- **Correction:** lexer equality remains evidence with semantic status UNKNOWN. SDK/header origin and compiler macro/target context are recorded. Optional configured Clang AST evidence captures declaration signatures without claiming complete API equivalence.
- **Verification:** updated old lexical-equality assertion; removal tests retained; actual SDK-header compilation positive; missing SDK-header negative; real Clang AST extraction and mocked failure/identical-signature controls. Optional AST comparisons still preserve whole-API UNKNOWN.
- **Remaining limits:** AST signatures are evidence, not a complete template/inline/record-layout/overload/preprocessor semantic comparator. No real Tizen SDK has been validated. Header standalone compilation can legitimately fail because of include-order requirements.

## F6 — P1 / HIGH: no applicable-interface denominator or coverage gate

- **Location:** `compat/report.py::build_results()`, CLI final gate; new `compat/coverage.py`.
- **Root cause:** reports counted finding rows only. Unchanged/unassessed interfaces could disappear from apparent scope; no coverage or compatibility denominator or minimum coverage threshold existed.
- **Minimal reproduction:** even a manifest with ELF/header inventory and no findings emitted neither `coverage` nor `quality_gate`. Repeating findings could change status counts without changing examined interfaces.
- **Correction:** baseline component-contract obligations (ABI export and type-layout obligations separate), all requested counts and explicit applicable denominator. Unassessed inventory remains UNKNOWN; empty inventory creates an unknown discovery obligation. Minimum coverage failures are independent of severity; excluded-but-required dimensions fail. Old successful 1.0 matrix observations are conservatively invalidated on import.
- **Verification:** 100 duplicated findings do not inflate coverage; missing-tool/missing-assessment negatives, covered positive, threshold and excluded-dimension failures, legacy manifest invalidation, actual CLI gate runs.
- **Remaining limits:** applicability is the inventoried baseline contract scope, not an enumeration of every possible third-party consumer or all kernel/device behaviors. Reports state this explicitly. UNKNOWN prevents full coverage rather than inventing an applicability claim.

## Already correct, preserved

- `advanced_abi()` already distinguished libabigail error bits 1/2, change bit 4 and incompatible bit 8; this distinction was not rewritten into a blanket failure.
- `compare_elf()` already avoided treating function code-size changes as ABI failures. Data/TLS sizes remain meaningful contracts.
- `Tools.run()` already used argv (no shell), process-group timeouts and external raw evidence. Image/TAR traversal protections and output/cache separation remain enforced.
- Runtime authorization and exclusion checks already prevented execution when disabled; these regressions remain in the suite.
- Different runtime dependency names were already UNKNOWN rather than automatically INCOMPATIBLE. No blanket GCC-versus-LLVM or ASAN exemption was introduced.

HTML now shows a clearly labeled first 1000 findings and Markdown first 200 incompatible details, while JSON/CSV remain complete. This bounds the reader-facing report without silently dropping machine-readable findings. It is not a claim that the other workstation's 196,199-finding report has been revalidated.
