# Analyze local RPM repositories and payloads

Provide two single RPMs or two directories of local archives. Directory discovery is recursive and independent of repodata. RPM identity comes from the parsed header, with full NEVRA and SHA256. Install or configure trusted host `rpm`, `rpm2cpio` and `readelf`; the analyzer does not fetch packages.

```bash
SKILL=/path/to/tizen-image-compatibility
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline /path/to/vd-gcc-rpms \
  --candidate /path/to/vd-llvm-asan-rpms \
  --rpm-mode payload --output ./vd-rpm-report
```

Use `--rpm-mode metadata` to inventory archives and compare NEVRA, Provides and Requires without decompression. Metadata mode still hashes archive bytes. Package relationships include exact versions, unique same-name and same-architecture replacements, missing and added packages when the opposite inventory is complete, and explicit Provides/Obsoletes hints. Conflicting bytes for one NEVRA and multiple unresolved versions remain ambiguous.

The payload parser bounds decompression, archive and ELF output, entry count, scratch space and timeout. Each package is processed serially in a disposable directory. The parser keeps virtual link information without creating physical links, devices or restoring privileges. It writes only the current ELF to scratch for inspection, preserves SHA256 for regular files, and never installs a package, invokes a scriptlet or executes a target binary. See the `rpm_payload` settings in [config.yaml](../config.yaml).

Packages are never merged. ELF file pairing uses package identity and an internal path, with a unique, compatible SONAME identity only as a fallback. Read the GNU version, type, binding, visibility, data size, code size and import/export metadata in the CSVs. Code size is an observation. ASAN entries are dependency or import observations; they are not used to dismiss missing interfaces. Archive metadata and payloads do not establish product installation, runtime binding, Loader policy or a complete type-layout ABI.

Unpaired ELF from ambiguous package versions remains available as individual archive observations. When either object's dynamic symbol inventory is incomplete, unmatched records are labeled `BASELINE_OBSERVED` or `CANDIDATE_OBSERVED`. A pure default lookup change has its own `DEFAULT_LOOKUP_CHANGED` detail.

`rpm-repository.json` separates raw observed export/import entries, unique base names within an input, qualified lookup identities summed per ELF, and comparison rows split by role and change. A default version exports both a qualified version lookup and an unversioned lookup. These totals have different denominators. An import delta does not establish that the installed loader would choose a particular Provider.

| File | Contents |
| --- | --- |
| `index.html`, `summary.md`, `results.json` | Scope, archive counts, ELF and symbol collection coverage, package relationships and Finding evidence |
| `packages.csv`, `package-symbol-summary.csv` | Repository availability comparisons and observed per-package totals |
| `elf-symbol-summary.csv`, `symbol-differences.csv` | Per-library SHA256, SONAME, DT_NEEDED, ARM and ASAN observations, full imports/exports and deltas |
| `extraction-errors.csv`, `evidence/` | Metadata/payload failure and source evidence |
| Both side manifests | Archived NEVRA, archive and payload identities, payload paths and observed object data |

These reports are available before any indexing step. For optional pagination and package filtering:

```bash
python3 "$SKILL/scripts/enhance_report.py" build --input ./vd-rpm-report --output ./vd-rpm-index
python3 "$SKILL/scripts/enhance_report.py" serve --report ./vd-rpm-index
```

## When EROFS extraction is blocked

Use a reviewed same-build replacement with the [preparation receipt](image_preparation.md), compare the RPM snapshots directly, or supply both corresponding RPM directories alongside the images:

```bash
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline ./gcc-flash.tar.gz --candidate ./llvm-flash.tar.gz \
  --baseline-rpm-fallback /path/to/vd-gcc-rpms \
  --candidate-rpm-fallback /path/to/vd-llvm-asan-rpms \
  --output ./vd-report
```

An EROFS preparation error retains the extraction manifest and switches the entire comparison to the supplied RPM inputs. The result scope is `RPM_REPOSITORY_PAYLOAD` (or `RPM_REPOSITORY_METADATA` when selected). The association between the image and manually supplied RPMs is operator-declared. A verified same-build replacement can bind original and replacement hashes explicitly.
