# WP-3b PM acceptance and VD-1b evidence

Accepted at `26336721a13dc3e08e964a5fc8bd3e15218e6493` on 2026-11-27.

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
