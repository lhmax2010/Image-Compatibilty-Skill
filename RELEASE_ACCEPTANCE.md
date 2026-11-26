# v1.5.0 Release Acceptance

**Developer Release Acceptance — PASS.** The standalone Linux scope passed local release gates. **LLVM Headed Functional Validation — CONDITIONAL PASS.** **Image Compatibility Certification — UNKNOWN / NOT VERIFIED.**

## Clean install

Tested the tracked release candidate in a separate directory and re-extracted the final archive. Verified all 108 released files against the archive manifest. Used copies in the documented Cline project and simulated user scopes. All four locations ran from a different working directory with spaces, Python site packages disabled for the CLI checks, and networking isolated. All produced the same synthetic outcomes (52 findings: 6 INCOMPATIBLE, 42 UNKNOWN, 2 COMPATIBLE, 2 NOT_APPLICABLE). JSON and CSV IDs matched, the expected removed symbol was reported, and fixture inputs were unchanged. Actual Chromium rendered the fresh static HTML.

The 23 CLI checks included tool discovery, original and reused Manifest comparisons, small enhanced indexes, Impact and History construction and queries, and an offline Runtime schedule. Reuse preserved all shared finding payloads. The direct comparison had an extra DWARF coverage observation and reuse had an extra manifest-only observation, both UNKNOWN. The offline plan had two NOT_EXECUTED slots. An unauthorized execute attempt was rejected before invoking the SDB sentinel, and full mode without SDK inputs did not claim an executed success.

The clean acceptance run reproduced an index failure for an unknown installed RPM total. The final build reconciles observed assessment and export rows separately from the installed runtime count. Tests cover missing and partial inventories, plus rejection of a contradictory known count. The final synthetic index verified all 52 findings and kept the installed counts null.

Cline format, documented project/user discovery layouts and the CLI through both installed paths were validated. No Cline UI was available in the release environment. See the [official Cline Skills documentation](https://docs.cline.bot/customization/skills).

## Regression and packaging

| Gate | Result |
| --- | --- |
| All tracked repository tests | 309 total, 304 PASS, 5 SKIP, 0 FAIL |
| Unpacked Skill tests | 294 total, 289 PASS, 5 SKIP, 0 FAIL. The 15 historical host-administration unit cases are repository-only |
| compileall and git diff --check | PASS |
| Archive reproducibility | Two builds from the same reviewed Git tree produced byte-identical archive, file manifest and checksum file |
| GitHub Actions | Static-only workflow added. No hosted execution observed |

The five skips were the explicit real libabigail integration, the explicit real Clang semantic/ARM integration, the GCC/Clang matrix integration that needs both host compilers, the Clang ARM v6/v7 and VFP integration, and the Clang hard/softfp/soft PCS integration. The frozen Tizen SDK and LLVM headed observations are independent of these optional host tests.

Reproduce the bundle with `python3 tools/package_skill.py --tree v1.5.0 --output ./release-assets`. See [PACKAGE_FILES.txt](PACKAGE_FILES.txt) and [SHA256SUMS](SHA256SUMS). The archive contains text source, configuration, documentation and needed test fixtures. Historical generated examples, repository-bound host-admin tools, actual device artifacts, SDKs, reports and private inputs remain outside the archive. Distribution remains internal under the repository policy. No license was added.

## Real acceptance boundaries

The existing Phase 8K material was reused without another SDK build or device run. [Phase 8K Final](docs/reviews/phase8k-final/FINAL_ACCEPTANCE.md)

Real full-size SR SQLite is NOT VERIFIED. The original builder process is no longer running. The final resource sample came from the original findings and assessments stage after about 6,811 seconds, with 2,496,806,912 bytes allocated and 259,149,824 bytes peak process RSS. There is no successful run/validation receipt or independently accepted index. The stopping cause is unavailable. The existing partial output and original test sources were retained.

## Distribution check

At the distribution preflight, GitHub reported the configured repository as PUBLIC. This task authorizes an Internal Developer Release to a private repository. The release commit, annotated tag, package and checksum are prepared locally. Publish only once the destination is verified private and authorized. The repository source and tag use ordinary Git pushes. Release assets are attached after verifying the pushed tag.
