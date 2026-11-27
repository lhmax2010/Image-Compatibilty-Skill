# WP-4 Addendum B and v1.5.3-rc2

## 1. Published kit and starting state

Published revision 7 SHA-256 `4a8b6ae5d4442604a36cb2362690d0f344c186ec8a635f58980b9583a84cfb78`.
Local and remote main started clean at `da3792506c99e2b437957cf883c04480f65a5ace`.
The downloaded source matched `3effc6819b0b35d1f44c8e0f360e8707a2c61fcb74396df55000f1f4fc846abb`.
B1 published the tested script first at `068df39ee3ec05511fdaad144c5505512859f281`.

## 2. Changes per item

| Item | Result |
| --- | --- |
| B0 and B2 | Recorded the PM's RC1 acceptance, the 600-package VD-1c projection, the unexplained export-incomplete group, extraction diagnostics, and ClineSR Python 3.10.22. |
| B1 | Published revision 7 without an intermediate revision 6. Its readers accept WP-3b and RC1 reports and use fixed category labels in shared output. |
| B3 REV-HEAD | Added the console, Markdown and HTML notice, the independent `review_gate` field, and small C++ class count tables. |
| B0 COPY-REL minor | New records store the symbol base name separately from the version. Both spellings resolve to the same version-qualified requirement in offline linking and coverage. ELF inventory revision 8 invalidates stale collector records. |
| B4 MEM-SCALE | Repository collection retains packed export/import arrays and C++ name lists per object. Comparisons unpack arrays as needed. The manifest writer emits the original arrays. |
| B5 packaging | `1.5.3-rc2` and CHANGELOG entry in the final normal main commit. |

[PM review](PM_REVIEW.md) · [VD-1c and server facts](../../DECISIONS.md)

## 3. Deviations and limits

The kit hash differs from the downloaded source because the delegated privacy
review restricted report categories and bounded decompressed evidence reads.
The initial publication note lost the digest strings due to shell quoting.
`e09d79eadf058ce440c1130e3c07dfccfc799d3f` corrected the two strings without
changing the script bytes.

The memory benchmark uses linked fixture objects with 24 consumer variants
and two versioned providers. Its RPM archives are much smaller than VD-1c,
so the extrapolation below is specific to the fixture workload.

## 4. Validation

| Check | Result |
| --- | --- |
| Revision 7 reporting | PASS on the saved WP-3b and RC1 scale reports. The synthetic canary covered compressed evidence, inventory and extraction buckets, and review fields. No canary name appeared in shared output. |
| REV-HEAD | PASS. Pending review appeared near the top of stdout, Markdown and HTML. The C++ class table rendered. NONE and COMPLETE suppressed the pending notice. The ordinary CI gate remained PASS with exit 0. |
| COPY-REL | PASS. The real x86-64 non-PIE fixture collected `optind` with its separate version. The existing decorated fixture still exercised rootfs provider-size checks. |
| MEM-SCALE | PASS on the synthetic slope target and output reconciliation at both sizes. |
| Full suite | PASS. Python 3.12.3 ran 392 tests in 237.584 seconds. 386 passed, six existing optional skips, zero failures and zero errors. Compileall, shell syntax and diff checks passed. |
| Native Python 3.10.22 gate | CLOSED. PM-supplied ClineSR evidence for RC1 `da37925` records `run=391 failures=0 errors=0 skips=13` and `SUITE OK`. RC2's suite result above is from the local Python 3.12.3 run. |
| Real standard EROFS | BLOCKED locally by the existing missing tools. |

## 5. Policy and evidence reconciliation

The memory change preserves the two sizes' finding counts of 614 and 1,222,
including exact IDs, statuses and full payloads. For each size all nine CSVs,
the Markdown report and the HTML report were byte-identical. The results and
run-summary JSON match after excluding the new `review_gate: NONE` field.
Decompressed manifests differ only in `collector_version`. Their recorded
RPM SHA-256 values reconcile with the actual inputs. All 840 and 1,640
evidence files, respectively, match across versions and after raw-hash
verification.

## 6. MEM-SCALE phase RSS

Peak sampled process RSS in KiB. GNU/Linux process RSS was sampled every 20 ms
and at phase boundaries. The high-water row uses `ru_maxrss` from the
untraced runs. Counts are per image side.

| Phase | RC1 · 201 RPMs / 302 ELFs | RC2 · 201 RPMs / 302 ELFs | RC1 · 401 RPMs / 602 ELFs | RC2 · 401 RPMs / 602 ELFs |
| --- | ---: | ---: | ---: | ---: |
| Collection | 192,548 | 38,644 | 358,804 | 51,096 |
| Pairing | 193,268 | 39,092 | 360,276 | 52,428 |
| Requirements | 197,276 | 43,600 | 372,212 | 64,728 |
| Comparison | 197,280 | 43,600 | 372,216 | 64,728 |
| Report assembly | 234,168 | 80,636 | 445,204 | 138,016 |
| Process high-water | **236,404** | **83,920** | **452,308** | **146,020** |
| Wall seconds | 43.60 | 29.49 | 54.69 | 57.86 |

The 602-object baseline inventory contains 60,150 exports and 90,000
imports. The median decorated C++ name is 117 characters. The peak-RSS
slope is **1,079.52 → 310.50 KiB per package per side**, a **71.24%**
reduction. Linear extrapolation from the RC2 fixture to 5,693 packages per
side is **1.71 GiB**. The historical VD-1c projection of about 14 GB uses
different data. The PM reports 94 GB total RAM, 72 GB available RAM, 32 cores,
and 146 GB free disk on the VD-2 server. The 14 GB projection fits that
capacity, so the PM lowered MEM-SCALE to P2 and removed it from the RC2 gates.
The actual native peak RSS remains to be measured.

### Allocation attribution

Separate tracemalloc runs used 302 ELF objects per side. The normal RSS
measurements above exclude tracing overhead.

| Snapshot | RC1 top live allocations | RC2 top live allocations |
| --- | --- | --- |
| End of collection | Symbol record dictionaries 57.56 MiB, dynsym group strings 33.12 MiB, symbol identity strings 28.38 MiB, version-index suffix strings 13.56 MiB, value and size fields 11.28 MiB | Packed symbol arrays 1.90 MiB, XML records 0.92 MiB, parsed package capability records 0.92 MiB, archive path records 0.88 MiB |
| End of requirements | Same five symbol sites as collection. The importer index contributes 2.41 MiB. | Importer index 2.41 MiB, packed arrays 1.90 MiB, package capability and XML records 0.92 MiB each |
| Report assembly before release | The same five symbol sites still dominate. Coverage check dictionaries add 10.14 MiB and import check IDs add 7.08 MiB. | Coverage check dictionaries 10.11 MiB, import check IDs 7.08 MiB, coverage units 4.77 MiB, check evidence lists 4.16 MiB, transient symbol identity strings 3.35 MiB |

The largest RC1 allocation sites are in `compat/elf.py` at the dynsym
groups, suffix parsing, symbol construction and identity split. Retaining
those arrays in `compat/packed_rows.py` removes the dominant persistent
symbol allocation. The availability requirement index was smaller on
these fixtures. Coverage becomes the largest traced report allocation site.

The generator and phase sampler are `tests/wp4_mem_scale.py` and
`tests/wp4_profile.py` in the skill directory. Run from the repository root
with fresh workspace-local destinations. Archive RC1 with `git archive`
and pass its exported scripts directory as the sampler's first argument.

```sh
python3 -B "$SKILL/tests/wp4_mem_scale.py" "$FIXTURES"
python3 -B "$SKILL/tests/wp4_profile.py" "$SCRIPTS" "$FIXTURES" "$REPORT_200" 200 sampled
python3 -B "$SKILL/tests/wp4_profile.py" "$SCRIPTS" "$FIXTURES" "$REPORT_400" 400 sampled
python3 -B "$SKILL/tests/wp4_profile.py" "$SCRIPTS" "$FIXTURES" "$TRACE_REPORT" 200 trace
```

## 7. Report size and remaining VD evidence

Addendum B retains report content and the RC1 compression behavior.
The PM accepted the RC1 SR findings and size deviations for the RC.
RPT-SIZE-3 still depends on the native VD output size. The symmetric
export-incomplete group and extraction failures from VD-1c retain their
current classification.

## 8. Runner and kit identities

The suite runner remains `99d5a0115c1c6e190f4a27e60d2894796481dc6e675ba6cb3f1dde7954cd091f`.
The revision 7 measurement kit is `4a8b6ae5d4442604a36cb2362690d0f344c186ec8a635f58980b9583a84cfb78`.

## 9. Backups and push

The B1 publication and digest correction backups are
`pm/20261127T104042Z` and `pm/20261127T104056Z`. Both passed bundle and
checksum verification. The final workspace-local backup is selected by
`.local-backups/LATEST`. Repository publication uses normal pushes of main.

## 10. Open risks

The synthetic fixtures reuse provider shapes and have fewer distinct
requirements. Native peak RSS is a P2 measurement. The reconciled packed-array
change already shipped in RC2. Larger changes go to the backlog. If native
profiling shows that coverage assembly dominates memory, evaluate streaming
coverage rows and require exact reconciliation of JSON, CSV, finding IDs,
and evidence before adopting it. Native report sizing remains open.

## 11. Recommended next step

Repeat the 600-package VD-1c sample on ClineSR at the RC2 commit. Use
revision 7 to report output size, aggregate RSS, and the unexplained
diagnostic shapes. Use the native report-size measurement for the
full 5,693-RPM-per-side run decision.
