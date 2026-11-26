# v1.5.1 release acceptance

**Native RPM payload and repository reporting — PASS on locally built RPMs. Standard EROFS extraction — NOT VERIFIED with a real filesystem. Samsung KantSU2e EROFS and VD repository acceptance — NOT VERIFIED.** This internal developer release covers archive and static analysis.

## Clean install and RPM evidence

A separate checkout and a fresh extraction of the release package were tested offline. The packaged CLI ran from an unrelated directory with spaces. The audit rebuilt both synthetic repositories with `rpmbuild`, read the RPM headers and payloads, compared the extracted ELF objects, and verified the output independently.

| Measurement | Baseline | Candidate |
| --- | ---: | ---: |
| RPM archives discovered | 9 | 9 |
| Metadata parsed and payload extracted | 9 | 8 |
| Payload coverage | 100% | 88.89% |
| ELF objects collected | 2 | 2 |
| Complete export tables among collected ELF objects | 2 | 2 |
| Export observations | 18 | 18 |
| Import observations | 2 | 6 |

The damaged candidate archive failed the metadata query and was recorded in `extraction-errors.csv`. Two packages carrying the same internal path retained distinct object identities. The test covers noarch data packages, ARMv7l and AArch64 package identities, multiple available versions, an unsafe CPIO path, and names resembling security and network components. The compiled test ELF objects are x86-64. The deterministic source archive digests were unchanged across analysis. The case with a package scriptlet confirmed that the scriptlet did not run.

The detailed symbol CSV has 25 rows (16 matched, five added, three changed and one missing). It includes separate observations for one GNU symbol version change, one data symbol size change and one function code size change. Tests also verify C++ mangled names, TLS, IFUNC and ASAN dependency observations. The JSON and Finding CSV ID sets reconcile and the evidence files match their content-addressed references. The package, ELF, symbol and extraction CSVs and the HTML report were generated before optional indexing. Chromium rendered the scope and removed export. The optional loopback browser served multiple distinct pages from the small derived index.

See [test_rpm_payload.py](.agents/skills/tizen-image-compatibility/tests/test_rpm_payload.py), the [RPM guide](.agents/skills/tizen-image-compatibility/references/rpm_repository.md) and the [EROFS preparation guide](.agents/skills/tizen-image-compatibility/references/image_preparation.md).

## Regression and packaging

| Gate | Result |
| --- | --- |
| Full repository tests | 321 total, 315 PASS, six SKIP, zero FAIL |
| Unpacked standalone tests | 306 total, 300 PASS, six SKIP, zero FAIL. The 15 historical host administration tests remain repository-only |
| Python compileall, browser JavaScript syntax and Git whitespace checks | PASS |
| Package reproduction | Two builds from the reviewed tree produced identical archive and file manifest |

The six skips cover explicit libabigail and Clang integrations, a host GCC/Clang matrix, the Clang ARM architecture/VFP case, the Clang PCS case, and real standard EROFS extraction without local `mkfs.erofs` and `fsck.erofs`. An existing Runtime interrupt-output test failed once during a preliminary parallel run and passed on serial re-execution. The Runtime process execution and cleanup implementation was unchanged.

Reproduce the tests with `python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v` and rebuild with `python3 tools/package_skill.py --tree v1.5.1 --output ./release-assets`. See [PACKAGE_FILES.txt](PACKAGE_FILES.txt) and [SHA256SUMS](SHA256SUMS). The v1.5.0 archive, commit and tag remain available locally.

## EROFS and real VD follow-up

Synthetic superblocks verify feature, compression and extra-device identification and refusal for unknown feature bits. A controlled host tool verifies read-only staging, stderr evidence and normalized extraction. A separate end-to-end test verifies that a blocked EROFS input can fall back to both explicitly supplied RPM collections. Real EROFS decoding and Samsung-specific feature interpretation still require matching trusted tools and sample inputs. If a partition uses external devices, a verified same-build replacement or the corresponding RPM repositories can be used.

Large VD repository throughput, actual ARM ELF coverage, product installation state and Runtime compatibility remain unverified by these fixtures. The [Quick Start](QUICK_START.md) provides the direct VD repository command. This package and its supporting evidence are local under the [publication policy](docs/PUBLICATION_POLICY.md).
