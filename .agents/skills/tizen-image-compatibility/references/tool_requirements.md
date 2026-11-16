# Dependencies and capability detection

- Python **3.10+**, standard library for default execution and tests. No package download or network access is needed for normal analysis.
- **PyYAML 6.x** only for `--config`; without it the default CLI works and YAML requests return a clear input error. The environment used for validation has PyYAML 6.0.1.
- **GNU readelf**: normal ELF collection. If absent, basic ELF header fields are read and optional `nm -D -P` output is retained as raw evidence. Symbol/ABI coverage is UNKNOWN. `nm` output is not falsely treated as complete readelf parity.
- **rpm**: package archives and copied installed RPM databases, via XML queries. No source image DB is opened for writing or installation. Unsupported database backend/query errors are recorded as unknown.
- **abidiff / libabigail**: optional type/layout comparison for matched files with embedded `.debug_info`. Return codes are bitmasks; 4 alone is ambiguous change, 8 indicates the tool's incompatible-change classification, 1/2 are errors. Default user/system suppression files are disabled; unavailable options degrade to UNKNOWN. [Official abidiff manual](https://sourceware.org/libabigail/manual/abidiff.html).
- **unsquashfs**: optional unprivileged SquashFS extraction with timeout. Use a patched host tool; xattrs are not extracted. Failure is infrastructure error with raw evidence. Size/count quotas apply to TAR, not to the external SquashFS extractor: use a quota-limited workspace for large untrusted SquashFS inputs.
- **GCC/G++ or Clang/Clang++**: explicit SDK executables for header/application probes. Host GCC is only used automatically by the **synthetic fixture generator/tests**, never substituted for a real image SDK.
- **rpmbuild**: optional integration-test dependency for generating a synthetic RPM.
- `objdump`, `abi-dumper`, `abi-compliance-checker`, `pahole` and `debugfs` are discovered/reported for operator visibility but are not invoked as semantic backends in this release.

Configure utility paths under `tools`, e.g. `readelf: /sdk/bin/readelf`, or `false` to exercise missing-tool behavior. Compiler paths/targets live under `cross_compilation.compilers`. Runtime isolation/transport is an explicitly supplied adapter, not an implicit dependency.

RPM XML output/tag definitions follow the [RPM query-format documentation](https://rpm.org/docs/4.20.x/manual/queryformat.html). Archive extraction is implemented as bounded streaming regular-file extraction with deferred links rather than unrestricted `extractall`; see Python's [TAR extraction security guidance](https://docs.python.org/3/library/tarfile.html#extraction-filters).
