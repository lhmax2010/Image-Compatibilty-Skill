# Tizen Image Compatibility Skill v1.5.1

**Internal Developer Release — native RPM payload and EROFS**

Compare two local recursive RPM repositories with the normal `tizen_compat.py` entry. The default RPM payload mode detects real ELF via magic and reuses the existing ABI, symbol version and ARM collectors. Package identity, archive SHA256 and package paths stay distinct from installed product inventory. The full package, ELF, symbol and extraction CSVs do not require SQLite. Metadata-only mode remains available.

EROFS preparation now records the superblock, feature bits, compression, extra devices, extractor version and stderr. Standard extraction uses a trusted host `fsck.erofs` inside bounded read-only isolation. A vendor adapter must account for detected feature bits and bind input and output digests. When EROFS is blocked, supply two opted-in RPM inputs or a verified same-build rootfs replacement.

Synthetic RPMs built with real ELF verify symbol add/remove, GNU versions, TLS/IFUNC, C++ mangling, code/data size and ASAN observations. Repository tests cover independent package paths, multiple versions and architectures, a damaged archive, and controlled unsafe CPIO. Standard EROFS and Samsung KantSU2e extraction still require real tool and input validation. No internal VD data was accessed.

Start with [Quick Start](QUICK_START.md), see the [RPM repository guide](.agents/skills/tizen-image-compatibility/references/rpm_repository.md), and verify [SHA256SUMS](SHA256SUMS). The v1.5.0 archive, commit and tag are retained. Prior image Runtime and certification limits are unchanged.
