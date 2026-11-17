# Synthetic package-level report

Generated metadata fixture, **not a real Tizen result or a queried RPM inventory**. Four package pairs own four ELF inventories and one public-header inventory. Eight exported symbols are deliberately removed; four synthetic consumer/provider failures and one unowned finding remain visible. API semantics are UNKNOWN, and partial ABI failure does not receive full verification credit. No target binaries are executed.

Open [index.html](index.html), [summary.md](summary.md), [results.json](results.json), [packages.csv](packages.csv) or [findings.csv](findings.csv). All 14 unique findings are retained; each package links to underlying finding IDs. The provider-consumer index has four relationships. Baseline and candidate manifests describe this metadata fixture only.

Regenerate into a new directory from the repository root:

```bash
python3 .agents/skills/tizen-image-compatibility/tests/review/make_package_example.py /tmp/package-example-new
```

The generator calls the production report builder and independently checks serialized JSON/CSV IDs, statuses, ownership, dependencies and HTML/Markdown previews. It exits 0 when generation and consistency checks pass; the generated report itself deliberately has compatibility and coverage gate failures.
