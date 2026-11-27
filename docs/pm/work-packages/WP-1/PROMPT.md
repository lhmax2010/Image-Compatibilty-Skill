# Codex Work Package WP-1 (revision 2, 2026-11-26)
## Workspace state report, PM continuity backup, and ELF/input correctness fixes

You are the implementation engineer for the Tizen Image Compatibility Skill. Claude is the technical PM and will independently review your commits, tests and evidence. Communicate in English. Do not invent product requirements. If something here is ambiguous, or a demonstrably smaller and safer solution exists, implement the safe interpretation and disclose the deviation in your report.

**Input files** (the project owner placed them in `$DOWNLOADS`; copy them into the workspace yourself, then treat the workspace copies as authoritative):

| File in Downloads | Put it at (inside the repository) |
|---|---|
| `WP-1_CODEX_PROMPT.md` (this file) | `docs/pm/work-packages/WP-1/PROMPT.md` |
| `ISSUE_REGISTER_SEED.md` | content becomes `docs/pm/ISSUE_REGISTER.md` |
| `CLINESR_VD-1_PROMPT.md` | `docs/pm/clinesr/VD-1_PROMPT.md` |
| any `*KIMI*` or `*review*` file the owner added (optional) | `docs/pm/reviews/` (keep the original file name) |

If a listed file is missing from Downloads, continue with the others and say so in your report. Do not delete anything from Downloads.

---

### 1. Task title

WP-1: State report + PM backup bootstrap + ELF export-inventory and input-handling correctness.
Register items: F-01, F-02, F-03, F-20, K-01, K-03, K-06, K-09, OPS-1, OPS-2.

### 2. Background

The Skill compares a GCC baseline and an LLVM candidate Tizen image or RPM repository, in the direction "baseline consumers on candidate". v1.5.1 added RPM payload analysis. Two independent reviews of commit `2d43c58` (Claude and Kimi) found defects in the ELF export-inventory parser, in input-format detection, and in resource handling. They are release blockers for v1.5.2. The runtime/SDB layer is out of scope for this package.

### 3. Starting commit

`2d43c58b8753c53f58fae906cc4c821bd6227397` on `main`. Verify your local `main` first (Step 0). If local `main` differs from that commit and the difference is not yours, report it and stop before changing code.

### 4. Problem statement

- **F-01 (P0).** GNU readelf prints `st_size` values above 99,999 as `0x`-prefixed hex (binutils `DEC_5` formatting). `parse_readelf` (`elf.py` L135) and the completeness regex in `collect_elf` (`elf.py` L201) accept decimal only. The symbol is dropped and `export_inventory_complete` becomes False for the whole library. The GNU version-node marker filter is then disabled, data-size changes on large objects are missed, and real removals are downgraded to UNKNOWN.
- **F-02 (P0).** `collect_elf` passes `-r` in the same `readelf` call as `--dyn-syms`. Relocations print before dynsym. `Tools.run` parses only the first 16 MiB (`core.py` L341-343), and the bounded RPM path caps capture at 16 MiB. Large libraries get `complete=False` and zero exports. Example: libLLVM (137 MB) produces 42.7 MB of output; libQt5WebKit (45 MB) is also affected.
- **F-03 (P1).** `compare.py` L138-142 marks any symbol `type` change INCOMPATIBLE HIGH, including `FUNC↔IFUNC`, which is transparent to PLT/GOT callers.
- **F-20 (P3).** `core.py` L20 `VERSION='1.3.1-phase8a'` is written as `collector_version` in v1.5.1 manifests and is part of the ELF cache key.
- **K-01 (P2, from Kimi).** `compare.exports()` builds `{name: symbol}`. Duplicate dynsym rows with the same decorated name (`name`, `name@V`, `name@@V`) silently overwrite each other, so the result depends on row order. Reproduced: `[foo/8, foo/4]` gives INCOMPATIBLE, while `[foo/4, foo/8]` gives IDENTICAL. The same pattern exists in `repository.symbols()`.
- **K-03 (P1, from Kimi).** `preparation.is_tar_container` (L31-38) accepts a file whose first block is all zeros as an empty TAR. Reproduced: two 1 KiB all-zero files as baseline/candidate give 38 findings, overall UNKNOWN, quality gate PASS and exit 0.
- **K-06 (P1, from Kimi).** `Tools.run` without `max_capture_bytes` writes child stdout/stderr to disk without any limit (`core.py` L305-318). Only parsing is bounded.
- **K-09 (P1, from Kimi).** `report_io.ResourceGuard` reads `/proc/pressure/memory` unconditionally (L111). On kernels without PSI, enhance/impact/history fail and two tests error.
- **OPS-1.** The project owner requires that important project state is backed up, so work survives if the PM or the Codex session is lost.
- **OPS-2.** The PM could not verify the local workspace state (local tags, uncommitted work, release archive hash, any in-progress work).

### 5. Verified evidence (reproduced by the PM on x86-64, binutils 2.42, Python 3.13)

1. A DSO exporting `char big_table[200000]` plus `foo`, `bar`, `fast` under version node `V1`: `collect_elf` returns `export_inventory_complete=False`. The exports list omits `big_table` and contains the marker `V1`.
2. CLI rootfs run, baseline table 200,000 B → candidate 100 B, and `bar` removed: the result is `INCOMPATIBLE HIGH | V1` (a false positive from the leaked marker), and the size shrink is not reported.
3. CLI rootfs run, baseline table 100 B → candidate 150,000 B, and `bar` removed: `bar@@V1` is `UNKNOWN HIGH`, quality gate PASS, exit 0.
4. `collect_elf` on `/usr/lib/x86_64-linux-gnu/libLLVM.so.20.1`: `complete=False`, 0 exports.
5. `int fast(void)` changed to an `ifunc` with the same name: `fast@@V1:type INCOMPATIBLE HIGH`.
6. `llvm-readelf` prints the version-node marker as `V1@@V1` (GNU readelf prints `V1`). `dynamic_exports()` filters only the GNU form.
7. The K-01 and K-03 reproductions are described in §4.

### 6. Approved architectural decision

Targeted fixes inside the existing modules. Do **not** replace the parser with pyelftools in this package; that migration is planned for v1.6.

- **F-01.** Parse sizes as `0x[0-9a-fA-F]+|\d+` using `int(text, 0)` in **both** regexes. Bump `ELF_INVENTORY_REVISION` (3 → 4) so caches are invalidated.
- **F-02.** Make export-inventory completeness independent of relocation output:
  - Remove `-r` from the primary `readelf` call.
  - If the ARM relocation inventory is needed (`machine == ARM` and mode is not `quick`), get it from a separate bounded call. A failure or truncation of that call may only set `arm_inventory.relocation_status = UNKNOWN`, never affect export completeness.
  - Never decide symbol completeness from a truncated preview. Either stream-parse the full raw evidence file, or add a validated config key (suggested `analysis.max_readelf_bytes`, default 512 MiB, upper bound 4 GiB) used by both the rootfs and RPM paths.
- **Version-node markers.** Recognize both spellings (`V1` and `V1@@V1`) when the row is ABS, OBJECT, size 0, value 0, GLOBAL, DEFAULT, and the name equals a non-BASE version definition.
- **F-03.** Add a small declarative symbol-change rule module (e.g. `scripts/compat/symbol_rules.py`). `compare_elf` uses it and gets `(status, severity, reason_code)` back. Minimum rows:

| Change | Status | Severity | reason_code |
|---|---|---|---|
| FUNC ↔ IFUNC / GNU_IFUNC | UNKNOWN | LOW | IFUNC_TRANSITION |
| NOTYPE ↔ FUNC or OBJECT | UNKNOWN | MEDIUM | NOTYPE_ANNOTATION |
| OBJECT ↔ FUNC/IFUNC | INCOMPATIBLE | HIGH | KIND_CHANGED |
| any ↔ TLS | INCOMPATIBLE | HIGH | TLS_KIND_CHANGED |
| OBJECT/TLS size decrease | INCOMPATIBLE | HIGH | DATA_SIZE_DECREASED |
| OBJECT/TLS size increase | INCOMPATIBLE | HIGH | DATA_SIZE_INCREASED (semantics unchanged in this package) |
| GNU_UNIQUE/UNIQUE → GLOBAL | UNKNOWN | MEDIUM | GNU_UNIQUE_DROPPED (explanation: Clang never emits STB_GNU_UNIQUE; dlclose/RTLD_LOCAL one-definition semantics) |
| other binding/visibility changes | UNKNOWN | HIGH | existing behavior, plus a reason code |

  Add `reason_code` to findings additively. Do not change any other classification.
- **F-20.** Read the tool version from the Skill `VERSION` file, for both `collector_version` and the cache key.
- **K-01.** Index exports and imports as a multimap. If one ELF has more than one dynsym row with the same decorated name (same name, version and default flag), set `export_inventory_complete=False` with reason `DUPLICATE_DYNSYM_IDENTITY`, and emit UNKNOWN rather than any IDENTICAL/COMPATIBLE result. The result must not depend on row order. Apply the same rule in `repository.symbols()`.
- **K-03.** A file is a TAR input only if it has at least one TAR member. A zero-member "TAR" is accepted only when a recognized flash or filesystem signature (GPT/XZ/VDFS/EXT/EROFS/SquashFS) exists at its supported offsets. Otherwise raise `InputError` (exit 2) with a clear message. An extracted tree with no regular files is never a valid rootfs.
- **K-06.** Every external tool call goes through the bounded capture path, with a per-call limit (default 64 MiB for general tools, plus the `readelf` key above). Exceeding it marks the result incomplete, with reason `OUTPUT_LIMIT`.
- **K-09.** If `/proc/pressure/memory` is missing or unreadable, record `memory_pressure: NOT_AVAILABLE` and fall back to `/proc/meminfo` (and cgroup `memory.current`/`memory.max` when present). Never raise.

You may choose a different internal structure if it is smaller and passes the same tests. Disclose any such deviation.

### 7. In scope

Steps 0–7 below, the tests in §13–15, and documentation of the changed semantics in `references/detection_methods.md` and `references/severity_rules.md`.

### 8. Out of scope

- Repository pairing and requirement checks (F-04/F-05).
- ASan confound detection (F-07).
- Linking finding volume (F-06).
- The workflow controller, `run-summary.json` and the exit-code contract (WP-5).
- EROFS sandbox changes, runtime/SDB, report UI, and the pyelftools migration.

Do not fix other findings opportunistically. List anything new you notice in your report.

### 9. Relevant files

- `scripts/compat/elf.py`, `compare.py`, `core.py`, `collect.py` (cache key), `rpm_payload.py` (bounded readelf call), `repository.py` (`symbols()` only), `preparation.py`, `images.py`, `report_io.py`
- New `scripts/compat/symbol_rules.py`
- `tests/`
- `references/detection_methods.md`, `references/severity_rules.md`
- `config.yaml` (only if a new key is added)
- New `docs/pm/` files

### 10. Steps

**Step 0 — State report (read-only, do this first).** Report the following without modifying anything:
- `git status --short`, `git rev-parse HEAD`, `git log --oneline -5`, and `git rev-parse origin/main` after a plain `git fetch` (no merge);
- local tags and their targets (`git show-ref --tags`);
- untracked files and a summary of uncommitted diffs (names and sizes only);
- the target of `.local-backups/LATEST`, and whether its manifest verifies;
- presence and SHA-256 of `tizen-image-compatibility-v1.5.1.tar.gz`, compared with `SHA256SUMS` (`3ab302cba18ecf8533b4415f7ce63d1a61d91a135e109da79c8c6998920654de`);
- whether any other task or long-running process of yours is in progress in this workspace;
- whether a trusted SR ARMv7 SDK (GCC and/or Clang cross compilers with a sysroot) is available in the workspace, and the exact compiler versions. Do not install anything.

If there are uncommitted production changes you did not make in this package, **stop after Step 0 and report**.

**Step 1 — PM continuity backup bootstrap (owner's standing instruction: back up important things so work survives if the PM or Codex goes missing).** Copy the Downloads files to the paths in the table at the top. Then create these files. They must be in English and contain no credentials, device serials, IP addresses, personal absolute paths, internal images or RPMs.

- `docs/pm/HANDOVER.md` — how a new PM or a new Codex session resumes: read order, current HEAD, open work packages, and how to verify the latest backup. Use placeholders such as `$WORKSPACE`, never a path containing a username.
- `docs/pm/PM_STATE.md` — current status:
  - the v1.5.2 track and its scope: static developer tool, runtime optional/experimental;
  - release categories A–I with their current state;
  - blockers: F-01, F-02, F-04, F-05, F-06, F-07, OBJ-1, AGT-1, OPS-4, K-03;
  - owner decisions recorded 2026-11-26 (see the bullets below);
  - open items: Codex in-progress work, SR SDK feasibility, internal-agent drill.
- `docs/pm/DECISIONS.md` — a dated log. Its first entries are the PM handover to Claude, the v1.5.2 scope, the minimal-controller decision (`run-summary.json` plus `compat_run.py doctor/run`, implemented in WP-5), and the five owner decisions below.
- `docs/pm/CODEX_STATE.md` — your live checkpoint: current step, modified files, any running job and how to resume or stop it. Update it before any long command and at the end of the package.

Owner decisions recorded 2026-11-26:
- The repository is a temporary public GitHub repo and will be made private as a backup after the task. Never create GitHub Releases; only use `git push`/`git pull`.
- Backups go to GitHub via a normal push to `main`.
- Local commits on `main` are allowed.
- ClineSR runs the VD work.
- The SR SDK may be used for ARM fixtures if feasible.

Then do the backup:
1. Commit locally on `main`, staging exact paths only.
2. Create a verified local backup under `.local-backups/pm/<UTC-timestamp>/` containing:
   - a `git bundle` of `main` and all local tags, checked with `git bundle verify`;
   - a tar of `docs/pm/`, the `git diff` and `git diff --staged` output, and untracked inputs;
   - a `SHA256SUMS` file checked with `sha256sum -c`.
3. Update `.local-backups/LATEST`.
4. Run `git push origin main`, a normal push with no force, no tags and no `--mirror`.

Keep the last 10 PM backups, and never delete release or historical backups. **Repeat this whole backup-and-push at the end of the package (Step 7), and before and after any command expected to run longer than 30 minutes.**

**Step 2 — F-01 and version-node markers.** Implement as described in §6.
**Step 3 — F-02 and K-06.** Implement as described in §6, for both `collect_elf(..., bounded=False)` and `bounded=True`, and for `Tools.run` in general.
**Step 4 — F-03 and K-01.** Rule table and duplicate-identity handling.
**Step 5 — K-03 and K-09.** Input detection and the PSI fallback.
**Step 6 — F-20.** Version from the `VERSION` file.
**Step 7 — Report, PM file update, final backup.**
1. Update `PM_STATE.md` and `ISSUE_REGISTER.md`: the items in this package become "Implemented, awaiting PM review".
2. Write `docs/pm/work-packages/WP-1/REPORT.md`.
3. Commit locally.
4. Make the end-of-package backup and push `main`.

### 11. Security and side-effect constraints

- Never execute analyzed ELF files. Generated fixtures are compiled but only inspected with `readelf`/`llvm-readelf`.
- No sudo and no mounts. No network beyond GitHub push/pull.
- All writes stay inside the workspace, except reading from `$DOWNLOADS`.
- Do not modify historical evidence or reports.
- Do not change repository visibility, remotes, branches or tags. Do not create GitHub Releases.
- Keep `.local-backups/` out of Git.

### 12. Backward compatibility

- The manifest schema stays readable as 1.2.
- The `ELF_INVENTORY_REVISION` bump invalidates caches by design.
- New fields (`reason_code`, config keys, `memory_pressure: NOT_AVAILABLE`) are additive.
- Findings affected by F-01, F-02, F-03 and K-01 will change ID and status. List the changed classifications in `REPORT.md`.
- `tizen_compat.py` exit-code semantics stay unchanged, except that invalid all-zero/empty inputs now exit 2 (K-03). Document this in the release notes draft.

### 13. Required positive tests

- **T-01 Hex sizes.** Build fixtures that export a 200,000-byte object:
  - for x86-64 with host GCC and Clang;
  - for ARMv7l with the trusted SR SDK compilers (GCC and Clang), if Step 0 found them usable.

  Assert all of the following:
  - the export inventory is complete;
  - the exact size is parsed;
  - a size decrease gives INCOMPATIBLE `DATA_SIZE_DECREASED`;
  - a neighbouring removed function gives INCOMPATIBLE;
  - no version-node marker appears as an export;
  - the CLI exits with code 1.
- **T-02 Large output.** A DSO generated by a script at test time, with at least 50,000 exported functions and at least 200,000 relocations. Do not commit large binaries. Assert that the inventory is complete, and that the export count equals an independent count computed by the test from `llvm-readelf --dyn-syms` (or `readelf`).
- **T-03 Differential check (subset).** For every fixture above, compare exports, imports, versions and needed libraries between the tool and an independent parse of `llvm-readelf --elf-output-style=JSON --dyn-syms -V -d`. If JSON output is not available, use an independent minimal parser written in the test. The two must match exactly.
- **T-04 Rule table.** One fixture per table row in §6, asserting status, severity and reason_code.
- **T-K01 Duplicates.** Duplicate-identity rows in both orders give identical results, the inventory is incomplete, and no IDENTICAL finding is produced.
- **T-K03 Zero file.** All-zero 1 KiB inputs exit 2. A valid TAR rootfs still works. A raw image with a zero prefix and a GPT signature is still identified.
- **T-K06 Output bound.** A fake tool fixture that prints more than the limit gives an incomplete result with `OUTPUT_LIMIT`. Disk usage stays bounded and the process group is cleaned.
- **T-K09 No PSI.** With `/proc/pressure/memory` made unreadable through a test seam (monkeypatched path), `ResourceGuard` works and records `NOT_AVAILABLE`.

### 14. Required negative tests

- A truncated or corrupted ELF still yields an incomplete inventory and UNKNOWN, never COMPATIBLE.
- A `readelf` stderr warning still prevents `export_inventory_complete=True`.
- A malformed size token (e.g. `0xZZ`) makes the inventory incomplete and does not crash.
- With `llvm-readelf` configured as `tools.readelf`, the marker `V1@@V1` is filtered and sizes are parsed.
- A failed relocation call on an ARM fixture leaves exports complete and sets `relocation_status=UNKNOWN`.

### 15. Required real integration tests

- Re-run the PM's two CLI reproductions (§5 items 2 and 3) as end-to-end tests. Expected: `bar@@V1` INCOMPATIBLE, the table size change INCOMPATIBLE, no `V1` finding, exit 1.
- On the dev host, run `collect_elf` over all shared objects in the host's main system library directory. Report the count, the count complete, the count with any hex-size row, and every object still incomplete with its reason. Report only; do not commit host binaries.
- If the SR ARMv7 SDK is usable: build one RPM with `rpmbuild` containing the ARM T-01 fixture, analyze it through the real `--rpm-mode payload` path, and confirm the ELF `machine` is reported as ARM.

A test that cannot run because a tool is missing must be reported as **BLOCKED, with the missing tool**, not as PASS. Gate the new tests behind an environment variable (e.g. `COMPAT_RELEASE_CI=1`) that turns such skips into failures.

### 16. Acceptance criteria

All of the following:
- T-01 to T-04, T-K01, T-K03, T-K06, T-K09 and the negative tests pass, with any BLOCKED items listed.
- The full existing suite still passes, with no new skips.
- The two CLI reproductions now produce the correct classifications.
- The host library scan shows zero objects left incomplete by hex sizes or the output window.
- The `docs/pm/` files exist, are committed and are pushed.
- Two verified PM backups exist (start and end).
- No tags were pushed and no Releases were created.

### 17. Required deliverables

- Commit SHAs on `main`, preferably one per logical change, and confirmation that they were pushed.
- The changed-file list.
- Test commands and their exact outputs.
- The host scan table.
- `docs/pm/work-packages/WP-1/REPORT.md`.
- Backup directory paths, with the `sha256sum -c` and `git bundle verify` outputs.
- A list of deviations from this prompt.
- Newly noticed issues (not fixed).

### 18. Git and publication rules

- `main` only. No new branches, no PRs, no force-push, no history rewrite.
- No tag creation, movement or push. **No GitHub Releases.**
- No visibility or remote changes.
- Stage exact paths only; no `git add -A`.
- Use normal `git push origin main` at the backup points described in Step 1 and Step 7.

### 19. Required final implementation report (format)

1. Step 0 state report (verbatim command outputs, trimmed).
2. Summary of changes per register item, with commit SHAs.
3. Design deviations and why.
4. Test results table: test ID, environment, command, result (PASS / FAIL / BLOCKED + reason).
5. Classification changes compared with v1.5.1 on the fixtures.
6. Host library scan results.
7. Backup and push evidence: paths, verification outputs, pushed commit.
8. Open risks and newly noticed issues.
9. The exact next step you recommend (one paragraph).
