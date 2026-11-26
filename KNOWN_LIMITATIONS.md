# Known Limitations

- ELF and RPM coverage depends on available collectors, debug/public headers and input completeness. Loader environment, application scope and security or kernel behavior can remain UNKNOWN. A matching symbol list is insufficient for complete ABI proof.
- Private filesystems such as VDFS require a trusted external extractor. Some flashing formats and incomplete extraction only support inspection or partial evidence. The Skill does not flash, mount or run input image code.
- Linux Python is the verified platform. Native Windows is outside scope. WSL or remote Linux provides the CLI environment.
- SDK and SDB are optional and require pre-existing trusted SDK inputs, authorized devices and scoped execution. LLVM headed is a functional reference. The original private DSO `dlopen` case was blocked by that Loader, and libc++ lacked runtime dependencies.
- VD headed native/reference and cross-image verification, the formal headless matrix (0/8), and an independent trusted target supervisor are pending. Product compatibility certification remains UNKNOWN.
- Real SR full-size enhanced SQLite acceptance is pending. Small synthetic indexes and read-only queries are within the verified scope.
- RPM reports cover available archives and observed ELF contracts. Installed loader/provider selection, completeness of a product image, and behavior still require matched Rootfs or Runtime evidence. The v1.5.2 real ARMv7 test used synthetic RPMs and matching local SR SDKs. The actual VD RPM repositories remain to be validated on an authorized workstation.
- Standard EROFS execution needs compatible local erofs-utils, Bubblewrap, and tar. Samsung KantSU2e remains unverified and requires a matching trusted vendor adapter with the feature/algorithm attestations and any companion inputs, or a same-build replacement.
- Company Agent execution and separate real user accounts remain rollout gates. The offline controller has been exercised in parallel with two clean installs and two HOME directories under one unprivileged UID. Whole-job production resource ceilings require OS isolation and quotas. [Production readiness](docs/production-readiness/PRODUCTION_READINESS.md)
