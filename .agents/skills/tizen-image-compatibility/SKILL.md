---
name: tizen-image-compatibility
description: Compare GCC and LLVM Tizen images or SDKs for external-interface compatibility, audit ABI/API and missing libraries or symbols, identify potentially affected applications and packages, and run explicitly configured cross-compiler probes.
---

# Tizen Image Compatibility

Compare baseline consumers on the candidate. Reverse inputs for the other direction. Use the included Python CLI and preserve its recorded findings, evidence and coverage.

## Analyze images or reuse reports

1. Identify baseline, candidate and direction. Treat compiler labels and filenames as user-provided context, then inspect architecture and collection evidence.
2. Use `static` by default, `quick` for initial inventory, and `full` or `runtime` for configured SDK and target checks. Use a new or empty output directory outside both images and SDKs.
3. Reuse compatible manifests for static comparisons. For impact or historical reporting, prefer an existing validated enhanced report and retain the original evidence directory.
4. Review `summary.md`, `results.json`, `findings.csv` and `index.html`. Present confirmed incompatibilities, possible impacts and unknown coverage separately. Exit 0 means the configured CI threshold was not hit.

Run from the repository root or assign `SKILL` to the installed Skill directory.

```bash
SKILL=.agents/skills/tizen-image-compatibility
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline ./images/gcc --candidate ./images/llvm \
  --mode static --output ./reports/comparison

python3 "$SKILL/scripts/enhance_report.py" build \
  --input ./reports/comparison --output ./reports/indexed
python3 "$SKILL/scripts/impact_report.py" build \
  --input ./reports/indexed --output ./reports/impact
python3 "$SKILL/scripts/enhance_report.py" serve \
  --report ./reports/indexed --impact ./reports/impact
```

The local `/impact` view links an impact group to its consumers, package roles, original Findings and available Evidence. An affected component does not establish package-wide failure. Historical input without verified baseline bindings yields inferred or unknown associations. Targeted `--replay-root /exact/baseline/executable` checks require the matching manifests and recorded loader context, and run entirely offline.

For historical regression, use `history_report.py build --before OLD_INDEX --after NEW_INDEX --scope SCOPE --output NEW_DIRECTORY`. Compare reports with the same recorded direction and product lineage. Treat unpaired or disappeared observations as unresolved unless a verified match supports the conclusion. Use `--history` with the local report server to browse `/history`. [Usage and examples](references/user_guide.md)

## Interpret compatibility and coverage

- Treat UNKNOWN, partial evidence and unexecuted checks as coverage gaps. Preserve exact symbol versions, loader context, and consumer/provider roles. Incomplete collections cannot prove absence. Equal export counts cannot establish ABI compatibility.
- Keep package inventory separate from package compatibility. Installed RPM records, available archives, runtime ELF, SDK headers and package ownership have separate evidence boundaries. [Package analysis](references/packages.md)
- Require explicit compiler, SDK, target ABI and native reference mappings for the four-way matrix. For target execution, require an authorized isolated adapter. Use the expected-test manifest and verify separate compile, link, deployment, execution and behavior records. [Execution protocol](references/execution.md)
- A confirmed break can coexist with incomplete coverage. Use `--fail-on`, `--strict` and `ci.minimum_coverage` to express separate thresholds. Review the [status rules](references/severity_rules.md), [coverage boundaries](references/compatibility_dimensions.md) and [correctness contract](references/correctness.md) before reporting product readiness.
