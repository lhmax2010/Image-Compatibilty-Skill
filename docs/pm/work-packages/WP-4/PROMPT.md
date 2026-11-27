> **FOR CODEX ONLY.** If you are ClineSR or another agent, stop: this is not your task.

# Codex Work Package WP-4
## Real-data policy, copy relocations, report size for full repositories, EROFS, Python 3.10, v1.5.3-rc1

You are the implementation engineer for the Tizen Image Compatibility Skill. Claude is the technical PM and independently reviews your commits, tests and evidence. Communicate in English. Do not invent product requirements. If something here is ambiguous, or a demonstrably smaller and safer solution exists, implement the safe interpretation and disclose the deviation.

**Input file** (in `$DOWNLOADS` = `/home/linhao/Downloads`; copy it yourself, do not delete anything there):

| File | Put it at |
|---|---|
| `WP-4_CODEX_PROMPT.md` (this file) | `docs/pm/work-packages/WP-4/PROMPT.md` |

Target: report by **Dec 2**. RC review Dec 3–4. VD-2 (full repositories via ClineSR) Dec 7–9.

---

### 1. Starting commit

`26336721a13dc3e08e964a5fc8bd3e15218e6493` plus your WP-3b acceptance record, if you already pushed it. Stop if `origin/main` holds anything else and report what is there.

### 2. Record first (Step 0, in `DECISIONS.md`, `ISSUE_REGISTER.md` and `docs/pm/work-packages/WP-3b/PM_REVIEW.md`)

**WP-3b accepted.** PM checks:
- 381 tests OK on the PM host.
- Kit revision 5 published as `8bf3dc72…af66`; the PM accepts Codex's privacy changes and retested the kit end to end.
- `missing_reason_codes` is 0 and `removal_context` is present.
- The SR 10,000 target conflicted with the PM's own DT_NEEDED rule, so it was a spec conflict, not an implementation fault.
- PERF-LINK (P2) is recorded.

**VD-1b real-data evidence** (ClineSR, same 150-package ARM sample; full repositories have **5,693 RPMs per side, about 10.2 GB each**):

| Tool | Wall / peak RSS | Report bytes |
|---|---|---:|
| `323e0e1` | 54.3 s / 380 MB | 535.6 MB |
| `0c40d40` | 51.0 s / 418 MB | 454.2 MB |
| `2633672` | 50.0 s / 424 MB | **324.9 MB** |

- **Report-size projection:** a linear projection to the full repositories gives about 40 min wall time and **about 15.5 GB of report**. Breakdown at `2633672`:

  | Entry | Size |
  |---|---:|
  | `evidence/` | 105.5 MB |
  | `results.json` | 55.0 MB |
  | `symbol-differences.csv` | 49.3 MB |
  | manifests | 73.3 MB |
  | `requirement-findings.csv` | 20.7 MB |
  | `findings.csv` | 15.5 MB |

  → **VD-2 blocker RPT-SIZE-3.**
- **Removed exports (4,924, all INCOMPATIBLE `EXPORT_REMOVED`):**

  | By binding and type | Count |
  |---|---:|
  | WEAK FUNC | 4,348 |
  | WEAK OBJECT | 347 |
  | GLOBAL OBJECT | 109 |
  | GLOBAL FUNC | 90 |
  | UNIQUE OBJECT | 30 |

  | By C++ class | Count |
  |---|---:|
  | template | 3,375 |
  | other C++ | 897 |
  | vtable | 350 |
  | thunk | 143 |
  | C | 100 |
  | typeinfo and typeinfo name | 55 |
  | VTT | 4 |

  Imported by some baseline object in the sample: 90, of which 89 are GLOBAL and 1 WEAK. Consumer requirements that fail on the candidate: 0 of 14,668.
- **Binding changes (6,939, UNKNOWN HIGH):** GLOBAL→WEAK 6,472; UNIQUE→WEAK 467.
- **Incomplete export inventories:**
  - 13 baseline (GCC) objects and 1 candidate object, all `VERSION_RECORDS_INCONSISTENT` / `export_version_undefined`.
  - PM root cause, reproduced: **copy relocations** in non-PIE GCC executables. A defined `.dynsym` entry such as `optind@GLIBC_2.2.5 (3)` with `R_*_COPY` carries a version from **verneed**, not verdef.
  - Reproducer: `gcc -no-pie -fno-pic` on a program that reads `optind` gives `UNKNOWN` / `VERSION_RECORDS_INCONSISTENT`, and the export version is kept as `GLIBC_2.2.5 (3)` with the index suffix.
- **ASan:** the candidate QuickBuild is *named* ASAN but is **not** built with ASan (owner, Nov 27). VD-ASAN is closed: ASan detection is validated on fixtures only. Record that the handover's "LLVM ASan candidate" description was a naming artefact.

**Owner decision D-POL-WEAK (Nov 27, verbatim intent):** "List the weak APIs with a table and introduce why this is unknown low risk. Then mark it as unknown low risk level and waiting the final personal reviewing."

**PM decision D-POL-BINDING (technical):**
- glibc's dynamic linker treats a WEAK *definition* like a GLOBAL one unless `LD_DYNAMIC_WEAK` is set.
- Therefore GLOBAL↔WEAK on a defined dynamic export is COMPATIBLE.
- UNIQUE→WEAK loses the process-wide single-instance guarantee for `dlopen(RTLD_LOCAL)` users. It is the same risk class as the existing UNIQUE→GLOBAL rule.

New issues to register: POL-WEAK, POL-BINDING, COPY-REL, DT-AGG, RPT-SIZE-3 (all P1, WP-4); SUITE-ARM (P1, WP-4); VD-ASAN (closed, N/A).

### 3. Approved design

#### 3.1 POL-WEAK — weak C++ export removals go to owner review

- **Qualifying finding.** All of the following:
  - `EXPORT_REMOVED` with both export inventories COMPLETE;
  - baseline binding `WEAK`;
  - `removal_context.cxx_class` other than `c`;
  - `observed_importers.baseline == 0` and `observed_importers.candidate == 0`.

  Everything else keeps today's grading: GLOBAL, UNIQUE, C symbols and anything imported stay INCOMPATIBLE `EXPORT_REMOVED`.
- **Grading.** Status `UNKNOWN`, severity `LOW`, reason `WEAK_CXX_EXPORT_REMOVED_UNREFERENCED`, `review_state: PENDING_OWNER_REVIEW`.
- **Config.** `policy.weak_cxx_export_removal: review | incompatible`, default `review`. The value `incompatible` restores the old grading exactly.
- **Review table.**
  - `weak-export-review.csv` columns:
    - `review_id`: a stable hash of (package name, SONAME or path, symbol identity);
    - `package, soname, path, symbol, demangled, cxx_class, binding, type, size, version`;
    - `observed_importers_baseline, observed_importers_candidate, rationale_code`;
    - `review_decision, reviewer, review_note`, left empty.
  - Demangle with `c++filt` in one batched call when it is available. If it is not, leave `demangled` empty and record the tool's absence once in the collection log.
  - The HTML report and `summary.md` get a section **"Weak C++ symbols no longer exported — pending owner review"** containing:
    - the rationale paragraph below;
    - counts by library and by `cxx_class`;
    - per-library groups. The HTML may collapse groups; `summary.md` shows the top 20 libraries and points to the CSV.
- **Rationale text** (put it in the report and in `references/correctness.md`):

  > C++ template instantiations, inline functions, and the vtables, typeinfo and thunks of classes without a key function have *vague linkage*. Every object file that uses one emits its own weak copy, and the dynamic linker binds all users to one of the available copies. A program compiled against the same headers therefore normally carries its own copy and does not need this library to export it. Clang and GCC make different inlining, instantiation and visibility decisions, so a library built with Clang often exports fewer of these copies. No analyzed program or library imports any of the listed symbols. The remaining risk is a consumer outside the analyzed set that was built to import the library's copy instead of emitting its own, for example through `extern template` declarations or explicit instantiation in the library. That cannot be checked statically here, so each entry waits for owner review.
- **Review loop.** Add `--review-decisions <csv>`, which reads the same CSV.
  - `ACCEPT` → `COMPATIBLE`, reason `WEAK_CXX_EXPORT_REMOVAL_ACCEPTED`, reviewer and note copied.
  - `REJECT` → `INCOMPATIBLE`, reason `WEAK_CXX_EXPORT_REMOVAL_REJECTED`.
  - An empty decision stays pending.
  - Rows that match nothing are reported as `review_unmatched` and never change any finding.
  - The input file is never modified. Its SHA-256 is recorded.
- **Run summary.** Add `review: {required, accepted, rejected, pending, unmatched, status: NONE | PENDING | COMPLETE}`. Existing gate fields keep their meaning.

#### 3.2 POL-BINDING

- **GLOBAL↔WEAK** on a defined dynamic export: `COMPATIBLE`, severity `INFO`, reason `SYMBOL_BINDING_WEAKENED` or `SYMBOL_BINDING_STRENGTHENED`. Exception: when the active loader profile declares `LD_DYNAMIC_WEAK`, it is `UNKNOWN MEDIUM` with reason `DYNAMIC_WEAK_SEMANTICS`.
- **UNIQUE→WEAK:** `UNKNOWN MEDIUM`, reason `GNU_UNIQUE_DROPPED`, the same as UNIQUE→GLOBAL.
- Any other binding pair keeps today's rule.
- Document each rule with its loader rationale.

#### 3.3 COPY-REL — copy relocations

- A defined dynamic symbol whose version index resolves to a **verneed** entry (corroborated by an `R_*_COPY` relocation when relocations are collected) is a copy-relocated import.
- Record it in a new `copy_relocations` list: `{name, version, size, provider_soname if known}`. It is **not** an export and does not make the export inventory incomplete.
- Normalize version strings: strip the displayed ` (n)` index suffix everywhere a version name is compared, and keep the raw text in evidence.
- Requirements (repository AVAILABLE_SET and rootfs): the candidate provider must export the symbol with the same version, and its `st_size` must equal the copied size.
  - Size differs: `INCOMPATIBLE`, reason `COPY_RELOC_SIZE_CHANGED`. The provider's object grew or shrank under an executable that copies a fixed size.
  - Provider export missing: the existing requirement codes apply.
- Bump `ELF_INVENTORY_REVISION`.

#### 3.4 DT-AGG

- Aggregate non-INCOMPATIBLE DT_NEEDED linking checks exactly like LINK-AGG: detail rows go to `linking-details.csv`; one finding per (image, consumer, state, search context).
- INCOMPATIBLE DT_NEEDED stays individual.
- Re-run the WP-3b SR partial-profile case and report linking findings, wall time and RSS. Target: linking findings ≤ 80,000.

#### 3.5 RPT-SIZE-3 — full repositories must produce a usable report

**Goal:** the full VD repositories (5,693 RPMs per side) produce a complete report **≤ 3 GB**, which means about **≤ 85 MB on the 150-package VD sample**, from 325 MB today.

Required:
1. **Evidence compression.** Store evidence files gzip-compressed (`<sha256-of-raw>.txt.gz`). The SHA-256 is still of the raw bytes. Readers and the enhanced index decompress transparently, and a WP-3b report still reads.
2. **`symbol-differences.csv` default `changes`:** write CHANGED rows only when an ABI-relevant field differs:
   - type, binding, visibility, version;
   - `st_size` for OBJECT/TLS/COMMON.

   FUNC size changes and address-only changes are counted, not written. `all` keeps everything.
3. **`results.json`:** findings reference symbol identities rather than embedding full baseline/candidate symbol dicts when the manifest holds them. Keep a reader-compatible resolver.
4. **Manifests:** add `report.compress_manifests: true` (default true) to write `*-manifest.json.gz`, with transparent reading. Reuse and `--reuse` paths must keep working.
5. **`requirement-findings.csv`:** do not write rows for requirements that are satisfied on both sides; count them. A config option restores them.

Acceptance:
- `wp2_scale` ≤ 40% of the WP-3b size (155.6 → ≤ 62 MB).
- The SR partial-profile report ≤ 50% of 1.62 GB.
- Row-level reconciliation of everything still written.
- A per-file table as before.

The VD sample is measured afterwards by ClineSR.

#### 3.6 EROFS (F-08 / K-05)

- Feature-probe bubblewrap: does `--size` with `--tmpfs` work? If not (bwrap 0.6.1), extract to a **disk scratch directory inside the workspace**, with a pre-flight free-space check of 3× the image size and cleanup on exit.
- Unknown EROFS compat bits keep failing closed with a reason code.
- If `mkfs.erofs`/`fsck.erofs` are not available, the standard-EROFS end-to-end test is BLOCKED. Say so. Provide the fixture generator script, so the owner's approved machine can run it later.

#### 3.7 SUITE-ARM — Python 3.10 on the real server

Neither the PM host nor yours has Python 3.10. ClineSR's server runs the tool already. Publish `docs/pm/clinesr/run_suite.sh` (FOR CLINESR ONLY, same rules as the measurement kit). It must:
- export the tool at a given full commit with `git archive` into `.local-work/suite-<tag>/`;
- set `TMPDIR`/`TMP`/`TEMP` to `.local-work/tmp`;
- run `python3 -B -m unittest discover` with stderr going to a private log;
- print only the Python version, the counts run/failures/errors/skips, and failing **test IDs** (test IDs are tool-internal names, not package names);
- end with `SUITE OK` or `SUITE FAILED`.

Before publishing, test it on your host on a copy of the repository and record the SHA-256.

#### 3.8 v1.5.3-rc1 packaging

- `VERSION` becomes `1.5.3-rc1`.
- Add a `CHANGELOG.md` section for 1.5.2 → 1.5.3-rc1 that lists the WP-1 to WP-4 items.
- Update `SKILL.md`/`references/workflow.md` for new options (`--review-decisions`, the policy keys, the compression keys).
- **No tag and no GitHub Release:** the RC is the pushed commit plus a verified backup bundle.

### 4. Out of scope

- F-10 (parallel RPM collection; VD-1b projects about 40 min for the full run).
- PERF-LINK optimisation (measure only, in §3.4).
- Finding-ID redesign.
- Controller redesign.
- Runtime/SDB.

### 5. Steps

- **Step 0:**
  1. Verify the commit.
  2. Copy the prompt.
  3. Record §2.
  4. Commit, back up and push.
- **Step 1:** COPY-REL. **Step 2:** POL-BINDING. **Step 3:** POL-WEAK. **Step 4:** DT-AGG.
- **Step 5:** RPT-SIZE-3. **Step 6:** EROFS. **Step 7:** SUITE-ARM (publish and push as soon as it is tested, then continue). **Step 8:** packaging.
- **Step 9:**
  1. Report and set statuses.
  2. Commit, back up and push.
  3. Update `CODEX_STATE.md` around long runs.

### 6. Constraints

- Never execute analyzed ELF files.
- No sudo, no host mounts, no network beyond GitHub push/pull.
- All writes stay in the workspace.
- Do not change visibility, remotes, branches or tags. **No GitHub Releases.**
- New config keys have defaults; new fields and columns are appended; readers keep reading WP-3 and WP-3b reports.

### 7. Required tests

- **T-COPY:** a non-PIE GCC executable with a copy relocation (x86-64 here; ARM too if a cross compiler exists):
  - export inventory COMPLETE;
  - `copy_relocations` holds the symbol;
  - a fake candidate libc with a changed `st_size` gives `COPY_RELOC_SIZE_CHANGED`;
  - the same size passes.
- **T-VERNORM:** version names with and without the ` (n)` suffix compare equal; evidence keeps the raw text.
- **T-BIND:** GLOBAL→WEAK COMPATIBLE; WEAK→GLOBAL COMPATIBLE; UNIQUE→WEAK UNKNOWN MEDIUM `GNU_UNIQUE_DROPPED`; with an `LD_DYNAMIC_WEAK` profile, UNKNOWN MEDIUM.
- **T-WEAK:**
  - a weak template function and a weak vtable removed with no importer are UNKNOWN LOW, pending, and listed in the CSV, HTML and Markdown with demangled names when `c++filt` exists;
  - a weak removed symbol that *is* imported stays INCOMPATIBLE;
  - a GLOBAL removal stays INCOMPATIBLE;
  - a weak C symbol stays INCOMPATIBLE;
  - with `policy.weak_cxx_export_removal: incompatible`, the old grading is identical.
- **T-REVIEW:**
  - ACCEPT, REJECT, empty and unmatched rows behave as specified;
  - the input file is unchanged;
  - its SHA-256 is recorded;
  - review counts appear in the run summary.
- **T-DTAGG:** as LINK-AGG, and an INCOMPATIBLE DT_NEEDED stays individual.
- **T-SIZE3:**
  - the `wp2_scale` table and reconciliation;
  - a WP-3b report is still readable;
  - `--reuse` works with compressed manifests;
  - evidence SHA-256 values match the raw bytes.
- **T-EROFS:** the probe path is selected correctly with a fake bwrap that rejects `--size`; disk scratch is cleaned up on success and failure; the free-space pre-flight fails closed.
- **T-SUITE:** `run_suite.sh` on a repository copy prints only the allowed lines and refuses a WORK outside `.local-work`.
- **Negative tests:**
  - a review CSV can never change a finding outside its matched `review_id`;
  - a copy-relocation candidate without a matching verneed entry is not reclassified;
  - compression never changes an evidence SHA-256.
- The full suite passes with no new skips; `compileall`; `git diff --check`.

### 8. Acceptance criteria

- All of §7 passes.
- The size targets are met, or the misses are explained with data.
- The SR rerun table is delivered.
- `run_suite.sh` is published with its SHA-256.
- `VERSION` is `1.5.3-rc1`.
- PM files are updated, two verified backups exist, `main` is pushed, and no tags or Releases were created.

### 9. Git rules

- `main` only. No branches, PRs, force-push, history rewrite, or tag creation, movement or push. **No GitHub Releases.**
- Stage exact paths.
- Use a normal `git push origin main` at Step 0, Step 7 and Step 9.

### 10. Final report format

1. Step 0 state.
2. Changes per item, with SHAs.
3. Deviations.
4. Test table (PASS/FAIL/BLOCKED).
5. Policy before/after on fixtures: counts by status and reason.
6. DT-AGG SR table.
7. RPT-SIZE-3 table.
8. `run_suite.sh` SHA-256.
9. Backup and push evidence.
10. Open risks and new issues.
11. Recommended next step (one paragraph).
