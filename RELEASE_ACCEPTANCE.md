# v1.5.2 release acceptance

**Local release candidate accepted for a scoped offline pilot and the synthetic headquarters demo. Full company production rollout remains NOT READY.** The [production readiness decision](docs/production-readiness/PRODUCTION_READINESS.md) records separate functional, security, portability, company Agent, demo and distribution gates.

## Evidence

- Two genuine synthetic ARMv7l RPMs built with the authorized local SR GCC 14.2.0 and Clang 22.1.8 SDKs were analyzed by the freshly unpacked candidate. ELF32, EABI5, ARMv7 and Base PCS were observed. The archived CLI detected the versioned removal and addition, with a complete export objective and independently incomplete product coverage. [Reproduction](docs/production-readiness/validate_arm_rpms.py)
- Rootfs directories, TAR/TAR.GZ, single and recursive RPM inputs, metadata-only results, EROFS fallback and manifest replay exercised their real engine paths. A regular unsupported input and a corrupt RPM retained their failure evidence. Native standard EROFS decoding needs local mkfs.erofs and fsck.erofs, which were unavailable. [Feature matrix](docs/production-readiness/FEATURE_ACCEPTANCE_MATRIX.md)
- The packaged workflow ran concurrently from two independently unpacked Skill paths and two HOME/cwd environments, with Unicode and spaces and the same actual UID. Evidence includes successful parallel jobs, a read-only output refusal, exclusive output ownership, atomic cache publication and a real occupied browser port. [Portability](docs/production-readiness/MULTI_USER_VALIDATION.md)
- Live and backup synthetic reports were independently generated. Actual Chromium verified the direct HTML and the optional loopback index, package-filtered detail, Evidence reads and denied off-tree access. The browser recorded zero JavaScript exceptions. Eight presentation slides passed structural checks. [Demo](docs/production-readiness/DEMO_GUIDE.md)

## Regression and versioned package

| Gate | Result |
| --- | --- |
| Clean staged-source suite | 343 total, 337 PASS, 6 SKIP, 0 FAIL, 36.245 s, peak 105,448 KiB |
| Fresh unpacked Skill suite | 328 total, 322 PASS, 6 SKIP, 0 FAIL, 36.495 s, peak 105,164 KiB |
| Python compileall, JavaScript syntax and Git whitespace | PASS |
| Reproducible package | Two byte-identical builds from one reviewed Skill tree. The v1.5.0 and v1.5.1 archive hashes and tag targets were cross-checked |

Five skips are the explicit libabigail integration, explicit Clang integration, host GCC/Clang matrix, Clang ARM ISA/VFP and Clang PCS. These require the opt-in or host tools described in the tests. The sixth skip is real EROFS extraction. The true ARMv7 RPM test is a separate SDK-based end-to-end check. The 15 historical host-admin tests are repository-only.

Rebuild the candidate with `python3 tools/package_skill.py --tree v1.5.2 --output ./release-assets`. Validate the archive and embedded file inventory with [SHA256SUMS](SHA256SUMS) and [PACKAGE_FILES.txt](PACKAGE_FILES.txt).

## Scope requiring follow-up

Current company Agent behavior, two distinct actual accounts, actual VD repositories, secure production resource isolation, standard and Samsung EROFS, full-size SR SQLite and formal cross-image Runtime still need evidence. This candidate was prepared locally. Distribution requires separate authorization for this release. [Known limitations](KNOWN_LIMITATIONS.md)
