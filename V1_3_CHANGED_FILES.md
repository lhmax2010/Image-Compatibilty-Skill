# Exact v1.3 changed-file list

Comparison base: the local workspace at task start, saved in `headless/work/phase5/BASELINE.json` and `code-before/`, **not** GitHub/main. The existing uncommitted RC fixes remain part of the workspace and are not attributed to v1.3.

## Modified existing files (4)

1. `README.md` — Cline-compatible report-only build/serve workflow, outputs, counting rules and limits.
2. `.agents/skills/tizen-image-compatibility/SKILL.md` — reuse existing reports; local HTTP/file viewing distinction.
3. `.agents/skills/tizen-image-compatibility/references/report_schema.md` — additive report index/CSV/API contract.
4. `.agents/skills/tizen-image-compatibility/references/packages.md` — canonical identities, observed/complete counts and attribution rules.

## New files (16)

1. `.agents/skills/tizen-image-compatibility/scripts/enhance_report.py`
2. `.agents/skills/tizen-image-compatibility/scripts/compat/report_io.py`
3. `.agents/skills/tizen-image-compatibility/scripts/compat/report_store.py`
4. `.agents/skills/tizen-image-compatibility/scripts/compat/report_symbols.py`
5. `.agents/skills/tizen-image-compatibility/scripts/compat/report_groups.py`
6. `.agents/skills/tizen-image-compatibility/scripts/compat/report_enhance.py`
7. `.agents/skills/tizen-image-compatibility/scripts/compat/report_browser.py`
8. `.agents/skills/tizen-image-compatibility/assets/enhanced-report.html`
9. `.agents/skills/tizen-image-compatibility/assets/enhanced-report.js`
10. `.agents/skills/tizen-image-compatibility/assets/enhanced-report.css`
11. `.agents/skills/tizen-image-compatibility/tests/test_report_enhancement.py`
12. `V1_3_REPORT_DESIGN.md`
13. `V1_3_REPORT_VALIDATION.md`
14. `V1_3_PERFORMANCE.md`
15. `V1_3_KNOWN_LIMITATIONS.md`
16. `V1_3_CHANGED_FILES.md`

No existing production Python module is modified by v1.3. In particular `core.py`, `elf.py`, `linker.py`, `package_analysis.py`, `report.py`, `testing.py`, collectors, coverage gates and Expected Test Manifest logic retain their task-start contents, including the prior local RC fixes. Existing tests and `tests/review/benchmark_v12.py` are unchanged. The two tracked synthetic example symlinks are pre-existing, not new files.

## External artifacts

- Final enhanced report: `/home/linhao/lss/tizen-static-acceptance/20261117/headless/reports/phase5-report-enhancement/`.
- Logs, before snapshots, synthetic reports, performance fixtures, browser probes, audit scripts and retained interrupted attempt: `/home/linhao/lss/tizen-static-acceptance/20261117/headless/work/phase5/`.
- Phase3/4 reports, evidence, original rootfs, archives and partitions are inputs and remain unchanged. Exact after-checks and artifact sizes are recorded in the validation/performance documents and machine audit files.

No commit, push, branch switch, reset, stash or merge is performed. Final branch/HEAD/main verification and SHA256 changes are saved in `work/phase5/FINAL_WORKSPACE.json` at handoff.
