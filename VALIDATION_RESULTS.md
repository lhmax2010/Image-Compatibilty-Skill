# Validation results

Date: 2026-11-16. These results validate checker behavior with **synthetic inputs**. They do not establish compatibility of any Tizen TV release, the other workstation's ONEMAIN/ASAN comparison, or an actual GCC-to-LLVM migration.

## Results

| Check | Observed result |
|---|---|
| Original revision `386a284` suite, isolated archive | 36 tests passed |
| Original defect reproducer | Confirmed outputs recorded in `tests/review/before.txt` |
| Updated complete suite with explicit optional tools | **69 tests passed, no skips**, 2.167 seconds in recorded run |
| Actual ELF / symbol versions | GCC-built DSOs and linked consumers parsed by readelf; positive and negative resolution/version cases passed |
| ARM target ABI | Real Clang ARM hard/soft object generation plus EABI/PCS/conflict fixtures passed; no ARM binary execution |
| Actual Clang semantic evidence | Clang 14 AST extraction passed; no whole-API compatibility claim |
| Actual libabigail | 2.4 embedded DWARF equality/break cases and Build-ID-matched split-DWARF break case passed |
| RPM metadata | Existing rpmbuild/rpm archive fixture passed; no package installation or payload execution |
| Matrix | Swapped compiler/SDK/native reference; own-reference failure; absent/invalid receipt; authorization/exclusion controls passed using simulated adapters |
| Coverage/CLI | Duplicate finding rows cannot inflate coverage; missing data stays unknown; actual runtime=100 threshold returned 1, runtime=0 returned 0 |
| Source immutability/security | Image hashes unchanged through gate runs; existing TAR/symlink/output guards and direct target-runner rejection passed |
| Manifest/cache | Schema 1.1 read/reuse and 1.0 successful-result invalidation passed; new collector version invalidates old cache keys |
| Python compileall | Passed |
| Skill validator | `Skill is valid!` |
| `git diff --check` | Passed |

Full test output: [validation.txt](.agents/skills/tizen-image-compatibility/tests/review/validation.txt). Original suite output: [original-tests.txt](.agents/skills/tizen-image-compatibility/tests/review/original-tests.txt). Original defect observations: [before.txt](.agents/skills/tizen-image-compatibility/tests/review/before.txt). Regressions: [test_correctness.py](.agents/skills/tizen-image-compatibility/tests/test_correctness.py).

## Commands

Run from repository root:

```bash
SKILL=.agents/skills/tizen-image-compatibility
python3 -m unittest discover -s "$SKILL/tests" -v
python3 -m compileall -q "$SKILL/scripts" "$SKILL/tests"
```

The default suite explicitly skips two optional integration tests if their tool paths are not supplied. The fully executed validation used:

```bash
COMPAT_TEST_ABIDIFF=/tmp/tizen-correctness-tools/abidiff \
COMPAT_TEST_CLANG=/tmp/tizen-correctness-tools/clang \
python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v
```

Set these variables to suitable host tool executables in a different environment. They are test dependencies, not Tizen compiler/SDK configuration and not commands to run target binaries.

Original reproduction can be repeated against an isolated checkout of revision `386a284c37b0fdf105948bef35d1bacdc7a9c389`:

```bash
COMPAT_SCRIPTS=/path/to/old-checkout/.agents/skills/tizen-image-compatibility/scripts \
python3 .agents/skills/tizen-image-compatibility/tests/review/reproduce.py
```

The reproduction script builds its own synthetic ELF and uses a simulated adapter; no generated target ELF is executed. Original incorrect outputs include hidden-provider/import checks returning `[]`, missing version relationships, candidate-built/native-failing artifact reported compatible on baseline, a single generic DWARF omission, lexical equality reported COMPATIBLE, and absent coverage/gate fields.

## Optional tool provenance

Clang and abidiff were initially absent. For actual integration validation, distribution packages were **downloaded and extracted under `/tmp/tizen-correctness-tools/`**, without sudo, system installation or changes to source images:

- Ubuntu Noble `abigail-tools` / `libabigail0t64`, package `2.4-3build1`, executable reports 2.4.0.
- Ubuntu Noble `clang-14`, `libclang-cpp14t64`, `libllvm14t64`, `libclang1-14t64`, `libclang-common-14-dev`, package `1:14.0.6-19build4`, executable reports Clang 14.0.6.
- Packages came from the machine's configured Ubuntu distribution mirror via `apt-get download`; extraction used `dpkg-deb -x`. Local wrappers set only the extracted host libraries' search path. No downloaded tool is committed to the repository.

The baseline suite's existing trusted C/C++ probe-source self-test compiles and executes **repository-owned host test programs**, not input-image/ARM/Tizen binaries. Matrix target runs are simulations or remain UNKNOWN. No device, QEMU guest, target command, flash or image-installed tool was executed.

## Compatibility with previous tests

All original 36 test cases remain in the suite. Five assertions/fixtures were intentionally migrated rather than deleted:

- Comment-only equality now expects semantic UNKNOWN.
- Missing versioned export checks its lossless raw `@@` name.
- Definitive missing-provider fixture declares complete inventory and loader context.
- Header compile fixture supplies actual SDK headers and explicit build provenance.
- Simulated adapter fixture supplies identity/hash/deployment/execution receipts.

These are disclosed classification changes, not exemptions that suppress failures. Existing security, timeout, cache, RPM, data-size, D-Bus, source-output guard and authorization tests continue to pass. Additional default-version positive/negative tests prevent the new lossless handling from falsely rejecting an unversioned export that gains a default version.

## Remaining acceptance blockers

No real Tizen rootfs/SDK/debug package set/native execution environment was provided here. Therefore this session cannot validate real target loader search choices, GBS build provenance, architecture-specific runtime behavior, C++ exception/unwind/TLS interoperability, service/kernel/security/hardware/network behavior, or performance budgets. The optional integration tools validate the checker with synthetic fixtures only.

Full glibc cache/namespace/hwcaps/secure-execution modeling, automatic debug RPM extraction/DWZ/.dwo support, complete C++ semantic equivalence and a production isolation/transport adapter remain unimplemented or operator-provided. Their bounds are documented in [CORRECTNESS_REMEDIATION.md](CORRECTNESS_REMEDIATION.md) and the skill's [correctness contract](.agents/skills/tizen-image-compatibility/references/correctness.md). Reports retain UNKNOWN where evidence is missing; no migration pass is inferred.

No commit, push or merge was performed during the validation phase. Original untracked `require.md` and `design.md` were not modified.
