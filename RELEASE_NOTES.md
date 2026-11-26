# Tizen Image Compatibility Skill v1.5.0

**Internal Developer Release**

Use the standalone Skill as a Linux CLI or install its entire directory in Cline. Start with [Quick Start](QUICK_START.md) and see the [User Guide](USER_GUIDE.md) for optional workflows. Verify the downloadable archive with the accompanying `SHA256SUMS`.

The release includes image inspection and preparation, static ELF/ABI/API and dynamic linking analysis, RPM and package relationships, raw evidence and coverage, configurable CI, Impact, History and optional enhanced reporting. Enhanced indexes preserve unknown installed RPM totals and reconcile observed package assessments separately. Authorized users can build frozen SDK probes, plan and reconcile Runtime observations, and inspect actual Loader bindings. The package ships source-only examples.

The real headless SR static comparison retained 903,377 findings, 11,490 INCOMPATIBLE, and 860,294 Linking UNKNOWN. Two real ARMv7 SDKs were exercised, with 21 additional compile/link records in the Phase 8K workflow. LLVM headed verification recorded 12/12 basic successes, 19 specialized executions (12 successes, 6 expected failures, 1 environment policy mismatch), 1 optional libc++ skip and an independent 1/1 exact binding recheck. The original 32 planned slots and 44 historical attempts were reconciled. The LLVM headed functional verdict remains CONDITIONAL PASS.

See the [Release Acceptance](RELEASE_ACCEPTANCE.md) for final clean-package, report and regression results. Real full-size SR SQLite, VD headed, formal headless Runtime, trusted target supervision and product certification remain separate. See [Known Limitations](KNOWN_LIMITATIONS.md).
