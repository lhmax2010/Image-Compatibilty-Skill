# WP-1 implementation report

**Implemented, awaiting PM review.** The ELF and input fixes, both original CLI reproductions, the actual ARM RPM path and the host shared-library scan passed. The mount-dependent EROFS test was outside the permitted execution boundary for this task.

## 1. Step 0

```text
$ git status --short
$ git rev-parse HEAD
69914261a7d4913230ac5a3c29734c78aa64ff8b
$ git log --oneline -5
6991426 release: harden Tizen compatibility production workflow
2d43c58 fix: release native RPM payload analysis and EROFS preparation
feb3fd9 release: prepare Tizen Image Compatibility Skill v1.5.0
0a18964 docs: record final static input integrity recheck
658a136 fix: freeze exact ARM runtime evidence and reconcile expected tests
$ git rev-parse origin/main
2d43c58b8753c53f58fae906cc4c821bd6227397
$ git show-ref --tags
16ee5786590f7c9e5bc238eeb47e4c70b6c01d4e refs/tags/v1.5.0
6015ef58e7ac2f70930b23c0a23dee171315fdce refs/tags/v1.5.1
fdb7b9247d2b8d33725292372301df4b9cc7c6e3 refs/tags/v1.5.2
```

Both tracked diffs and the untracked file list were empty. The one local commit was prior Codex work. No earlier job was running in the workspace. Local tag commit targets were feb3fd9, 2d43c58 and 6991426 respectively.

```text
.local-backups/20261119T052928Z-github-migration: 18/18 checksums verified
.local-backups/20261119T052928Z-github-migration/refs-after-fetch.bundle is okay
tizen-image-compatibility-v1.5.1.tar.gz: OK
PACKAGE_FILES.txt: OK
3ab302cba18ecf8533b4415f7ce63d1a61d91a135e109da79c8c6998920654de
```

The trusted SR sysroots are present. Compiler logs report Tizen GCC 14.2.0 20240801 1.1 and Clang 22.1.8 for armv7l-tizen-linux-gnueabi. Both were used in Step 6 acceptance with real target code generation and file-only ELF inspection.

## 2. Register items and commits

| Register item | Change | Commit |
| --- | --- | --- |
| OPS-1 / OPS-2 | Handover, checkpoint, issue register, decisions, prompts and verified start/end continuity snapshots | `b2482c9823dd23dfe6bf8e22a525371e7a3bf38c` plus the final report commit |
| F-01 | Shared hexadecimal and decimal dynsym grammar and GNU/LLVM version marker evidence | `0f6e045483729ede0aec614103fc1f6d8950f65e` |
| F-02 | Complete bounded primary output for both ELF paths, separate ARM relocation receipt | Same implementation commit |
| F-03 | Small declarative rule table and additive reason codes | Same implementation commit |
| F-20 | Bundled VERSION used in the manifest and cache identity | Same implementation commit |
| K-01 | Multimaps, explicit ambiguous observations and order-independent UNKNOWN findings | Same implementation commit |
| K-03 | Required TAR member, signature fall-through and extracted rootfs content check | Same implementation commit |
| K-06 | 64 MiB general capture default and explicit OUTPUT_LIMIT, with existing verified group cleanup | Same implementation commit |
| K-09 | NOT_AVAILABLE for unavailable PSI and optional current cgroup memory headroom | Same implementation commit |

Changed files

```text
.agents/skills/tizen-image-compatibility/config.yaml
.agents/skills/tizen-image-compatibility/references/detection_methods.md
.agents/skills/tizen-image-compatibility/references/severity_rules.md
.agents/skills/tizen-image-compatibility/scripts/compat/collect.py
.agents/skills/tizen-image-compatibility/scripts/compat/compare.py
.agents/skills/tizen-image-compatibility/scripts/compat/core.py
.agents/skills/tizen-image-compatibility/scripts/compat/elf.py
.agents/skills/tizen-image-compatibility/scripts/compat/images.py
.agents/skills/tizen-image-compatibility/scripts/compat/preparation.py
.agents/skills/tizen-image-compatibility/scripts/compat/report_io.py
.agents/skills/tizen-image-compatibility/scripts/compat/repository.py
.agents/skills/tizen-image-compatibility/scripts/compat/symbol_rules.py
.agents/skills/tizen-image-compatibility/tests/test_wp1.py
.agents/skills/tizen-image-compatibility/tests/wp1-sdk-tool.sh
.agents/skills/tizen-image-compatibility/tests/wp1_host_scan.py
docs/pm/CODEX_STATE.md
docs/pm/DECISIONS.md
docs/pm/HANDOVER.md
docs/pm/ISSUE_REGISTER.md
docs/pm/PM_STATE.md
docs/pm/clinesr/VD-1_PROMPT.md
docs/pm/work-packages/WP-1/PROMPT.md
docs/pm/work-packages/WP-1/RELEASE_NOTES_DRAFT.md
docs/pm/work-packages/WP-1/REPORT.md
```

## 3. Design deviations

- Bumped the ELF inventory revision from 4 to 5, because the local v1.5.2 ancestor had already consumed revision 4.
- Decimal sizes use explicit base 10 and hexadecimal sizes explicit base 16. This also accepts decimal tokens with leading zeros and avoids Python base-autodetection errors.
- The checked LLVM 22.1.8 reader reported its GNU text format correctly. Its combined JSON output from `--elf-output-style=JSON --dyn-syms -V -d` was malformed, so the differential oracle uses independent GNU text column parsing and never shares the collector's regex.
- For the no-mount constraint, the SDK fixture wrapper invokes the trusted host-side compilers and linkers using the SDK dynamic loader and absolute sysroot arguments. One existing Bubblewrap EROFS integration test was withheld. The existing real EROFS test still requires missing mkfs.erofs and fsck.erofs.
- The working prompt replaces the personal Downloads path with `$DOWNLOADS`. The Seed and VD-1 inputs were present and copied. No matching optional Kimi review was found in Downloads. Filenames resembling Kimi reviews from unrelated projects were excluded. Fetch tag auto-follow was disabled.

## 4. Test evidence

Use the Skill directory as `SKILL` and a fresh local work directory as `WORK`. Set `WP1_SR_SDK` to the parent of the trusted `vd` and `llvm` SDK directories. To reproduce the exact tool selection, install the test wrappers within the work area:

```bash
mkdir -p "$WORK/bin" "$WORK/tmp"
cp "$SKILL/tests/wp1-sdk-tool.sh" "$WORK/bin/sdk-tool"
for tool in clang llvm-readelf arm-gcc arm-clang; do
  ln -s sdk-tool "$WORK/bin/$tool"
done
export TMPDIR="$WORK/tmp" PYTHONDONTWRITEBYTECODE=1 COMPAT_RELEASE_CI=1
export WP1_SR_SDK
export WP1_CLANG="$WORK/bin/clang" WP1_LLVM_READELF="$WORK/bin/llvm-readelf"
export WP1_ARM_GCC="$WORK/bin/arm-gcc" WP1_ARM_CLANG="$WORK/bin/arm-clang"
python3 -m unittest discover -s "$SKILL/tests" -p test_wp1.py -v
python3 -B "$SKILL/tests/wp1_host_scan.py" /usr/lib/x86_64-linux-gnu "$WORK/host-scan"
```

| Test | Environment | Command or selected case | Result |
| --- | --- | --- | --- |
| T-01 / T-03 / two CLI reproductions | x86-64 GCC + Clang 22.1.8 host-target | `test_t01_t03_and_cli_gcc_x86`, `test_t01_t03_and_cli_clang_x86` | PASS. Complete export lists, correct sizes, exact independent diff and CLI exit 1 for shrink and growth with removal |
| T-01 / T-03 ARM | SR GCC 14.2.0 and Clang 22.1.8 | `test_t01_t03_and_cli_sr_arm` | PASS. Both compilers, both size cases |
| T-02 | x86-64 GNU assembler, linker and readelf 2.42 | `test_t02_large_dynamic_table` | PASS. 50,000 independently counted exports, 200,000 relocations, relocation text above 16 MiB |
| T-04 | Synthetic symbol contracts | `test_t04_rules` and real GCC FUNC/IFUNC reproduction | PASS. All rule cases yield the expected status, severity and code. Real FUNC/IFUNC yields UNKNOWN LOW |
| T-K01 | Direct ELF inventory and repository rows | `test_k01_duplicate_orders_and_repository_rows` | PASS. Both orders produce identical UNKNOWN evidence |
| T-K03 | Raw, TAR and GPT files | `test_k03_zero_tar_valid_tar_and_gpt` | PASS. Invalid files exit 2, regular TAR and GPT recognized |
| T-K06 | Bounded host tool | `test_k06_bounded_output_evidence_and_cleanup` | PASS. Combined evidence capped, OUTPUT_LIMIT, group VERIFIED |
| T-K09 | PSI read denied with cgroup-v2 seam | `test_k09_unreadable_psi_uses_memory_fallback` | PASS. NOT_AVAILABLE and bounded fallback |
| Negative ELF cases | Actual GNU and LLVM readelf with targeted fault seams | `test_negative_incomplete_inputs_warning_and_bad_size`, `test_negative_llvm_marker_and_relocation_failure` | PASS. Truncation and warning do not earn compatibility. Malformed size rejected, LLVM marker filtered, failed ARM relocation isolated |
| F-20 | Packaged Skill version | `test_f20_version` | PASS |
| ARM RPM | Two local synthetic armv7l RPMs with actual SR SDK output | `tizen_compat.py --baseline REPO_A --candidate REPO_B --rpm-mode payload --output REPORT` | PASS. ELF32 ARM, EABI5, Base PCS, complete export inventories. Expected exit 1, hashes unchanged |
| Host library inventory | GNU readelf 2.42 on the developer host | `wp1_host_scan.py` above | PASS |
| Full selected regression | Python 3.12, Linux, no mounts, release fixture flags active | unittest discover with the single mount-dependent EROFS case withheld, as recorded below | PASS for selected tests. 354 run, 348 PASS, six existing SKIP, zero FAIL. One mount-dependent case withheld separately |
| Existing mount-dependent EROFS case | Bubblewrap would mount host paths in a new namespace | `test_confined_extractor_command_and_evidence_with_host_tool_fixture` | BLOCKED by the no-mount constraint |

The full no-mount test command is:

```bash
python3 -B - <<'PYTEST'
import unittest

def cases(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from cases(test)
        else:
            yield test

omitted = 'test_rpm_payload.ErofsTests.test_confined_extractor_command_and_evidence_with_host_tool_fixture'
all_tests = unittest.defaultTestLoader.discover('.agents/skills/tizen-image-compatibility/tests')
print('BLOCKED under the no-mount constraint:', omitted, flush=True)
selected = unittest.TestSuite(test for test in cases(all_tests) if test.id() != omitted)
raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(selected).wasSuccessful())
PYTEST
```

The local evidence directory is `.local-backups/pm/wp-1-evidence/`. Exact clean committed-code suite summary:

```text
Ran 354 tests in 121.640s
OK (skipped=6)
```

The focused output was `Ran 12 tests in 2.645s` and `OK`. The final suite's six pre-existing skips cover explicit Clang and libabigail integration, GCC/Clang matrix prerequisites, direct host Clang ARM ISA/VFP and PCS cases, and real EROFS tools. The WP-1 ARM and Clang cases ran separately with the explicit SDK paths and COMPAT_RELEASE_CI gate.

## 5. Classification changes compared with v1.5.1

| Actual fixture | v1.5.1 | WP-1 |
| --- | --- | --- |
| OBJECT 200,000 to 100 bytes, remove bar@@V1 | Exit 1. Bar removal found. False V1 incompatibility and missing size classification | Exit 1. Bar removal INCOMPATIBLE. DATA_SIZE_DECREASED INCOMPATIBLE HIGH. V1 absent from exports/findings |
| OBJECT 100 to 150,000 bytes, remove bar@@V1 | Exit 0. Bar removal UNKNOWN and V1 spuriously listed as a compatible addition | Exit 1. Bar removal INCOMPATIBLE. DATA_SIZE_INCREASED INCOMPATIBLE HIGH. V1 absent |
| Real FUNC to IFUNC | Exit 1, INCOMPATIBLE HIGH | Exit 0, UNKNOWN LOW with IFUNC_TRANSITION |
| Duplicate decorated symbol | Result depended on the last row | UNKNOWN with DUPLICATE_DYNSYM_IDENTITY and stable rows in both orders |

Affected Finding IDs can change when status, attributes or reason code change. No historical artifacts were edited. DWARF remains an independent UNKNOWN check.

## 6. Host library scan

The scan inspected resolved, unique ELF targets from top-level shared-library directory entries under `/usr/lib/x86_64-linux-gnu`. It retained targets reached through symlinks into LLVM tool directories and excluded linker scripts `libc.so` and `libm.so`.

| Unique ELF targets | Complete headers | Complete export inventories | Hexadecimal size rows seen in objects | Incomplete from hex | Output-limit failures | Other incomplete |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,044 | 1,044 | 1,044 | 14 | 0 | 0 | 0 |

The installed libLLVM.so.18.1 was checked independently and its inventory was complete with 50,459 exports. The PM's cited host version 20.1 was unavailable here. No host binaries were added to Git.

## 7. Backup and push evidence

The startup backup is `.local-backups/pm/20261127T010008Z/`. The startup push updated main from 2d43c58 to b2482c9. Each backup verifies the bundle and these six checksum entries:

```text
BUNDLE_VERIFY.log: OK
main-and-tags.bundle: OK
pm-docs.tar: OK
worktree.patch: OK
staged.patch: OK
untracked-inputs.tar: OK
The bundle records a complete history.
```

After the final commit, `.local-backups/LATEST` identifies its verified snapshot. Each bundle contains main and the local tags. The normal Git push transfers only main. The enclosing delivery message records the final commit and final backup directory.

## 8. Open risks

- Full production gates and later packages remain in the register. Actual VD testing is assigned to ClineSR. Runtime, repository-wide pairing/provider validation and the controller were outside WP-1.
- A raised readelf cap still requires sufficient host memory for parsing complete capture. A deliberate cap breach produces UNKNOWN evidence with OUTPUT_LIMIT.
- Older schema 1.2 manifests remain readable. The exact-collector guard for optional direct Impact replay can require recollection.
- A future mount-authorized EROFS test can complete the withheld existing regression. The no-mount run did not supply EROFS acceptance.

## 9. Next step

Claude should verify the final main commit and both continuity snapshots, review the two CLI classification changes and the no-mount test boundary, then mark the accepted WP-1 register items Verified and start WP-2 with the repository-specific findings from the register.
