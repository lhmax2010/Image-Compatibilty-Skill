# Tizen Image Compatibility Skill v1.5.0

Internal Developer Release for Linux. Compare the public interfaces required by applications built for a baseline Tizen image against a candidate image. The default Python CLI runs offline and records findings, coverage and reviewable evidence. The same directory works as an Agent Skill in Cline.

## Start here

1. Get the approved internal v1.5.0 archive and checksum. Extract the complete `tizen-image-compatibility` directory.
2. Use the [Quick Start](QUICK_START.md) for your first static comparison. Python 3.10+ on Linux is required. Use Linux, WSL or a remote Linux shell with Cline.
3. Use the [User Guide](USER_GUIDE.md) for project/user Cline installation, report navigation, SDKs and authorized Runtime. See the [release notes](RELEASE_NOTES.md) and [verification record](RELEASE_ACCEPTANCE.md).

| Included | What you get |
| --- | --- |
| Images | Rootfs directories, rootfs TAR/TAR.GZ, supported SquashFS, merged OCI rootfs and RPM collections. Read-only flashing-package inspection and configured extraction |
| Static evidence | ELF/ABI, API/headers, symbol versions and dynamic links, RPM ownership, provider/consumer roles, coverage and Findings |
| Reports and automation | JSON, CSV, HTML, Markdown and raw Evidence. Configurable CI gates, Impact Analysis, History and optional bounded SQLite indexing |
| Optional validation | SDK build/links, frozen GCC/Clang probe bundles, authorized SDB observations, exact bindings, expected-test reconciliation and unified reports |

Switch baseline and candidate to test the reverse direction. The default static path requires no SDK, device, SDB, QEMU, root or network. For input coverage, tooling and optional extraction see the [bundled image guide](.agents/skills/tizen-image-compatibility/references/image_preparation.md). An `UNKNOWN` finding reflects insufficient evidence. CI exit 0 only means that the configured gate passed.

The verified SR headless static run produced **903,377 findings**, including **11,490 INCOMPATIBLE** and **860,294 Linking UNKNOWN**. Two real matching ARMv7 SDKs and representative GCC/Clang compile/link operations were verified. On LLVM headed, four frozen basic probes passed **12/12** runs and the exact binding recheck passed **1/1**. These are scoped results. The [known limitations](KNOWN_LIMITATIONS.md) cover the unverified VD/headless Runtime, supervisor, full-size SQLite and product certification boundaries. Historical evidence is retained under [docs](docs/).
