# Issue Register — Tizen Image Compatibility Skill

Owner: technical PM (Claude). Maintained by Codex from PM decisions. Baseline commit for all review findings: `2d43c58b8753c53f58fae906cc4c821bd6227397` (v1.5.1).

- **Sources:** "Claude review" means the PM's independent production-readiness review (2026-11-26). "Kimi review" means Kimi's adversarial source review of the same commit (labelled "v1.1" in that report), stored in `docs/pm/reviews/` if the owner provided it.
- **Evidence levels:** CONFIRMED-exec (reproduced by running the code), CONFIRMED-static (source reading), LIKELY, NEEDS_VERIFICATION, DESIGN_GAP.
- **Status values:** Open, In progress, Implemented (awaiting PM review), Verified, Closed, Deferred, Rejected, Merged.

## Release blockers and v1.5.2 scope

| Issue | Source | Sev | Evidence | Module / location | Root cause (short) | PM decision | Selected solution | WP | Status |
|---|---|---|---|---|---|---|---|---|---|
| F-01 | Claude | P0 | CONFIRMED-exec | elf.py L135, L201 | readelf prints st_size > 99,999 as 0x hex; regex accepts decimal only, so the inventory is incomplete and the marker leaks | Accept | Parse hex or decimal; marker handling; revision bump | WP-1 | Verified (PM, 2026-11-27, ae4d269) |
| F-02 | Claude | P0 | CONFIRMED-exec | elf.py L190-196, core.py L341-343 | `-r` output pushes dynsym past the 16 MiB parse window | Accept | Separate relocation call; full-output parse | WP-1 | Verified (PM, 2026-11-27, ae4d269) |
| F-03 | Claude | P1 | CONFIRMED-exec | compare.py L138-142 | Any type change is INCOMPATIBLE, including FUNC↔IFUNC | Accept | Declarative symbol rule table | WP-1 | Verified (PM, 2026-11-27, ae4d269) |
| F-04 | Claude | P1 (blocker) | CONFIRMED-exec | repository.py L55-81, L146-149 | ELF pairing is package-local; library loss across packages is reported as INFO | Accept | Repository-wide SONAME/path index; LIBRARY_REMOVED | WP-2 | Verified (PM, 2026-11-27, 323e0e1) |
| F-05 | Claude | P1 (blocker) | CONFIRMED-static | repository.py L158-163 | No DT_NEEDED or versioned-import satisfiability check in repository mode | Accept | Closed-world AVAILABLE_SET requirement check | WP-2 | Verified (PM, 2026-11-27, 323e0e1) |
| F-06 | Claude | P1 (blocker) | CONFIRMED-exec | linker.py L64, L207-249 | One finding per root × closure × import; mostly UNKNOWN HIGH by default | Accept | Memoize per (object, requirement); aggregate; NOT_EXECUTED without loader profile | WP-4 | Open |
| F-07 | Claude | P1 (blocker for VD) | CONFIRMED-exec | repository.py L258; QUICK_START | No ASan/instrumentation confound detection (Clang ASan: global st_size 40→96 B) | Accept | Build-profile detector; CONFOUNDED run status | WP-2 | Verified (PM, 2026-11-27, 323e0e1) |
| OBJ-1 | PM + Kimi K-F02 | P0 | CONFIRMED-exec | tizen_compat.py L214-221; config.yaml ci | Exit 0 means only "threshold not hit"; no objective-completion status | Accept (K-F02 merged) | run-summary.json objective block; compat_run.py exit 4 = OBJECTIVE_NOT_MET; legacy CLI exits unchanged | WP-5 | Open |
| AGT-1 | PM | P0 | CONFIRMED-static | 9 CLIs; SKILL.md 16 KB | No bounded summary or single entry point for weak agents | Accept | run-summary.json + compat_run.py doctor/run; SKILL.md ~60 lines | WP-5 | Open |
| AGT-2 | Handover | P0 | NOT_EXECUTED | — | Real internal-agent validation missing | Accept | Drill with ClineSR after WP-5 | WP-5+ | Open |
| OPS-1 | Owner | P0 | — | — | PM/Codex continuity backup | Accept | docs/pm/ + verified local backup + push to main | WP-1 | Verified (PM, 2026-11-27, ae4d269) |
| OPS-2 | PM | P0 | NOT_VERIFIED | workspace | Local state unknown to the PM | Accept | WP-1 Step 0 report | WP-1 | Verified (PM, 2026-11-27, ae4d269) |
| OPS-4 | Claude | P0 | CONFIRMED (16 skips) | tests | Release suite passes while skipping all real RPM, EROFS and ARM tests | Accept | Real-tool CI image; skips fail under COMPAT_RELEASE_CI=1 | WP-6 | Open |
| K-01 | Kimi K-F01 | P2 | CONFIRMED-exec | compare.py L36-37; repository.py L169-171 | Duplicate decorated dynsym names collapse in a dict; order-dependent result | Accept | Multimap; duplicates make the inventory incomplete | WP-1 | Verified (PM, 2026-11-27, ae4d269) |
| K-03 | Kimi K-F03 | P1 | CONFIRMED-exec | preparation.py L31-38 | All-zero file accepted as an empty TAR; UNKNOWN with gate PASS, exit 0 | Accept | Reject zero-member TAR without a recognized payload; exit 2 | WP-1 | Verified (PM, 2026-11-27, ae4d269) |
| K-06 | Kimi K-F06 | P1 | CONFIRMED-static | core.py L305-318 | Unbounded stdout/stderr written to disk | Accept | Bounded capture for all tools; OUTPUT_LIMIT reason | WP-1 | Verified (PM, 2026-11-27, ae4d269) |
| K-09 | Kimi K-F09 | P1 | CONFIRMED-static | report_io.py L111 | /proc/pressure/memory read unconditionally | Accept | NOT_AVAILABLE + meminfo/cgroup fallback | WP-1 | Verified (PM, 2026-11-27, ae4d269) |
| VD-1 | Handover | P0 | NOT_EXECUTED | VD workstation | Real VD sample measurement (v1.5.1) | Accept | ClineSR prompt docs/pm/clinesr/VD-1_PROMPT.md | VD-1 | Open |
| VD-2 | Handover | P0 | NOT_EXECUTED | VD workstation | Real VD full acceptance | Accept | With v1.5.2-rc1 and the confound flag | VD-2 | Blocked on WP-1..WP-3 |

## Important, scheduled

| Issue | Source | Sev | Evidence | Module / location | Root cause (short) | PM decision | Selected solution | WP | Status |
|---|---|---|---|---|---|---|---|---|---|
| F-08 + K-05 | Claude + Kimi K-F05 | P1 | LIKELY / CONFIRMED-static | erofs.py L54-56, L82-96 | Whole tree must fit a 1 GiB RAM tmpfs; unknown compat bits refused; bwrap ro-binds host `/`, `/dev`, `/proc` | Accept (merged) | Disk scratch; ignore compat bits; minimal bind set | EROFS item (post-RC) | Open |
| F-09 | Claude | P1 | LIKELY | images.py L57; packages.py L199; debuginfo.py L89 | A single 60 s default timeout covers long operations | Accept | Per-operation timeouts | WP-6 | Open |
| F-10 | Claude | P1 | CONFIRMED-static | rpm_payload.py L236-262, L76/L94 | Serial RPM collection; Python byte-sum CRC on all payload bytes | Accept after VD-1 data | Process pool; CRC only for 070702; content-hash cache | post-RC unless VD-1 > 2 h/side | Pending data |
| F-11 | Claude | P2 | CONFIRMED-exec | compare.py L96-100 | Identical debug-only files give UNKNOWN HIGH | Accept | DEBUG_ONLY exports NOT_APPLICABLE | WP-2 | Verified (PM, 2026-11-27, 323e0e1) |
| F-12 | Claude | P2 | CONFIRMED-static | repository.py L184-204 | Version change counted as CHANGED although it is a missing requirement; roles mixed | Accept | Per-role, requirement-based counts; acceptance counts restated | WP-2 | Verified (PM, 2026-11-27, 323e0e1) |
| F-15 | Claude | P2 | CONFIRMED-exec | linker.py L89-94 | Linking verification needs security-dimension metadata | Accept | Always collect execution metadata when linking is active | WP-4 | Open |
| F-16 | Claude | P2 | LIKELY | collect.py L211-230 | Cache trusts stored JSON; no permissions; non-atomic | Accept | 0700 per-user cache; re-derive from evidence; atomic writes | WP-6 | Open |
| F-18 | Claude | P2 | DESIGN_GAP | sdb_runtime.py L71-81; SKILL.md | Agent can self-authorize device execution via config | Accept (doc now) | SKILL.md "always ask"; out-of-band authorization in v1.6 | WP-5 / v1.6 | Open |
| F-20 | Claude | P3 | CONFIRMED-exec | core.py L20 | Stale collector version 1.3.1-phase8a | Accept | Read VERSION | WP-1 | Verified (PM, 2026-11-27, ae4d269) |
| F-21 | Claude | P2 | LIKELY | rpm_payload.py L252 | `rpm -qp --xml` capped at 16 MiB | Accept | `--qf` with the needed tags only | WP-2 | Open |
| F-22 + K-F08 | Claude + Kimi | P2 | DESIGN_GAP | report_browser.py L152-232 | No local access token; fixed port 8765 | Accept (merged) | URL token; `--port 0` default | WP-6 | Open |
| F-23 | Claude | P2 | DESIGN_GAP | results.json / summary.md | Image-controlled strings reach agent-read files | Accept | Agent reads only run-summary.json | WP-5 | Open |
| F-24 | Claude | P3 | CONFIRMED-static | images.py L106-140 | No disk-free preflight for TAR | Accept | doctor preflight | WP-5/6 | Open |
| K-11 | Kimi K-F11 | P3 | CONFIRMED-static | images.py L188 | /proc, /sys, /run silently excluded | Accept | Record as mountpoint metadata + limitation | WP-6 | Open |
| OPS-3 | Handover | P1 | Reported | tests (frozen_runtime / runtime_release interrupt tests) | Flaky interruption test | Accept | Root cause; no retries, no weakened assertions | WP-2 | Closed — not reproduced in 800 executions (200 × 4 concurrent), assertions unchanged; reopen on recurrence |
| PUB-2 | PM | P3 | CONFIRMED-static | references/implementation.md L38; examples/synthetic-report/* | Personal paths in tracked files; packaging regex misses /opt/*/<user>/ | Accept | Sanitize; widen scanner | WP-6 | Open |

## Deferred / owner-decided

| Issue | Source | Sev | Decision | Target |
|---|---|---|---|---|
| F-13 | Claude | P2 | Unstable finding IDs: defer (identity key vs payload hash) | v1.6 |
| F-14 | Claude | P2 | IDENTICAL surface compares addresses: fix with the rule table if trivial, else defer | WP-1 optional / v1.6 |
| F-17 | Claude | P2 | debuginfo creates a new Image() per object | v1.6 |
| F-19 | Claude | P2 | Runtime hard-coded product identity (build-ID regex, IPv4, RPi serial) | v1.6 (runtime experimental) |
| K-04 | Kimi K-F04 | P1 | Frozen Runtime stops after the first case (fail-safe) | v1.6 (runtime experimental; documented) |
| K-07 | Kimi K-F07 | P3 | killpg misses setsid children; rename the field | v1.6 |
| K-10 | Kimi K-F10 | P3 | COMPLETE without evidence; add evidence_complete | v1.6 |
| K-12 | Kimi K-F12 | P3 | Stamp vs re-hash; document "inputs must be frozen" | docs |
| K-13 | Kimi K-F13 | P3 | SDB admission sleep/env | v1.6 |
| PUB-1 | PM | — | Owner: temporary public repo, private after the task; no Releases; push/pull only | Closed (decided 2026-11-26) |
| PUB-3 | PM | P3 | No remote tags; two old review/* branches remain; keep, do not push tags | Closed (keep) |
