# v1.2 remediation, capabilities and production prerequisites

The modular CLI, collectors, loader analysis, SDK/adapter harness and report architecture are preserved. This supplement closes the acceptance gaps listed in [V1_2_REVIEW_FINDINGS.md](V1_2_REVIEW_FINDINGS.md); it does not replace the earlier [M1–M4 implementation record](V1_2_VALIDATION.md).

## Package and finding accounting

Ownership indexes package identities to RPM file lists and paths/canonical aliases to owners. Path/dimension finding indexes, component-coverage indexes and provider-package → consumer-package edges are built once. Aggregation visits each related finding per associated package, not every global finding per package. Deterministic sorting costs O(n log n); work/storage otherwise track records plus relationship cardinality. Many genuine owners or a large dependency fan-out necessarily increase relationships. Closure analysis for many executable roots is not claimed globally linear.

`package_results` assesses every reliable baseline installed identity. `package_inventory.candidate_assessments` represents every reliable candidate identity with its matching baseline assessment ID or candidate-only/unresolved status, owned interfaces and findings. `unverified_package_records` retains records whose installed provenance cannot be established. Archive records remain in `available_archives`. Counts reconcile declared source count, discovered records and assessed records separately for runtime and SDK scopes. Unknown counts stay null. Complete real RPM fixture counts/file lists are independently checked with a separate rpm query.

Same name/architecture/scope uniquely matches an identity. Parallel versions and duplicate identities remain unresolved. Shared files can suggest replacement/rename or split candidates, but package lineage and equivalent provided contracts are **not established**. `replacement_hints` never changes availability to COMPATIBLE or removes baseline findings. A baseline-only name is not definitive interface removal; candidate-only inventory is not proof of package compatibility.

Confirmed ABI breaks remain INCOMPATIBLE while API can remain UNKNOWN and verification PARTIAL. Runtime-only packages cannot prove SDK API compatibility. Same virtual paths do not make SDK ELF and runtime ELF evidence interchangeable; linked SDK inventory alone does not execute a separate SDK ABI analysis. SDK ELF ABI/linking remains UNKNOWN in the runtime report unless separately assessed. Complete data-only applicability yields overall NOT_APPLICABLE, not an automatic compatible result. Consumer, root consumer and candidate provider findings remain distinct. Unattributed findings remain globally visible. Exact duplicate observations are audited as occurrences; conflicting finding IDs are errors rather than last-write-wins data loss.

## Completeness, reuse and gates

COMPLETE credit requires all required checks; outcome and completeness are independent. Absent v1.2 expected metadata cannot reuse earlier success. Unexpected/legacy failures are retained with PARTIAL verification. Global status also considers recorded obligations/tests and package failures. Confirmed obligation failures without associated finding rows use HIGH severity in `compatibility_obligation_failures`; `fail_on: CRITICAL` can intentionally leave the gate passing without changing the incompatible outcome. Finding-level severity overrides continue to apply to findings. Coverage/strict failures remain separate reasons.

Version 1.2 adds accounting fields without removing earlier report fields. See [report schema](.agents/skills/tizen-image-compatibility/references/report_schema.md) for denominators and 1.0/1.1 migration. Existing data consumers must not equate verified with compatible + incompatible.

## Capability categories

Each row classifies the stated scope, not the entire dimension. IMPLEMENTED_AND_TESTED means observed tests of that checker behavior, never universal product validation. IMPLEMENTED_NOT_REAL_TIZEN_VALIDATED means actual code and synthetic integration evidence exist but matching product inputs/targets have not been validated. PARTIALLY_SUPPORTED identifies narrower evidence or conservative UNKNOWN boundaries. UNSUPPORTED means no implementation/proof is claimed.

| Capability/scope | Category | Exact limitation |
|---|---|---|
| Required-check accounting, ID reconciliation, finding dedup audit, severity/coverage gates | IMPLEMENTED_AND_TESTED | Correct for explicit recorded obligations; does not enumerate every possible product contract |
| Package ownership/aggregation, count reconciliation, multi-owner aliases, consumer/provider indexes | IMPLEMENTED_AND_TESTED | Depends on actual reliable RPM file lists; missing provenance/counts remain unknown; relationships may be many-to-many |
| JSON/CSV completeness and bounded HTML/Markdown package reports | IMPLEMENTED_AND_TESTED | HTML search only covers first 1000 packages/findings; Markdown first 200; full machine data still needs proportional memory/disk |
| Synthetic stress budgets and serialized consistency verifier | IMPLEMENTED_AND_TESTED | Measured fixture scale only; configurable time/RSS budgets and reference comparison are hardware/load sensitive |
| Rootfs, safe TAR, SquashFS and RPM archive/DB collection interfaces | IMPLEMENTED_NOT_REAL_TIZEN_VALIDATED | Real synthetic ELF/RPM/TAR cases tested; product images/DB backends/metadata and optional SquashFS tooling still need acceptance |
| ELF metadata, dynamic symbols/versions, data/TLS export comparisons | IMPLEMENTED_NOT_REAL_TIZEN_VALIDATED | No full behavior proof; unavailable/truncated ELF evidence remains UNKNOWN |
| Embedded/split Build-ID DWARF with libabigail | IMPLEMENTED_NOT_REAL_TIZEN_VALIDATED | Needs matching debug data; only reachable debug types are observed, not exhaustive runtime semantics |
| ARMv7 target ABI and base/VFP PCS; AArch64 basic ABI | IMPLEMENTED_NOT_REAL_TIZEN_VALIDATED | Real Clang object tests; no ARM execution, exhaustive ISA attribute proof, or actual product SDK run |
| Bounded glibc startup dependency/symbol scope | PARTIALLY_SUPPORTED | Complete operator context required; multiple providers, weak/IFUNC/UNIQUE/protected/namespace/interposition cases stay UNKNOWN where unsupported |
| Full glibc namespace/dlopen/audit/hwcaps/IFUNC behavior | UNSUPPORTED | No complete dynamic-loader implementation or runtime proof |
| Public API lexical comparison, configured SDK header probes and Clang AST evidence | PARTIALLY_SUPPORTED | Not exhaustive typedef/template/macro/inline/semantic equivalence; runtime-only inventory cannot prove API |
| SDK package association | IMPLEMENTED_NOT_REAL_TIZEN_VALIDATED | Explicit installed SDK manifest/source association required; filename/package-name guessing prohibited |
| Automatic verified package rename/split/merge lineage and RPM dependency solver | UNSUPPORTED | Shared-path hints remain UNKNOWN; no solver or identity equivalence inferred |
| Compiler runtime libraries | PARTIALLY_SUPPORTED | Inventory and ELF surfaces only; C++ exception/unwind/TLS/atomic behavior needs authorized target tests |
| Four-way compiler matrix and receipt/hash/native-reference harness | IMPLEMENTED_NOT_REAL_TIZEN_VALIDATED | Own compiled fixtures and simulated receipts test harness only; no production adapter or Tizen execution validated |
| Bundled production device/QEMU transport or isolation implementation | UNSUPPORTED | Operator must supply and audit adapter; QEMU user mode alone is not isolation |
| Kernel/syscalls/UAPI | PARTIALLY_SUPPORTED | Config/header inventory; no boot, syscall/ioctl behavior or kernel version verification through execution |
| IPC/D-Bus | PARTIALLY_SUPPORTED | Introspection signatures/config; no full RPC, bus permissions or behavioral proof |
| Commands | PARTIALLY_SUPPORTED | Inventory plus explicit probes only; no automatic target --help/--version execution |
| Filesystem/configuration | PARTIALLY_SUPPORTED | Metadata and selected normalized content; virtual runtime trees and all effective behavior not assessed |
| Services/boot | PARTIALLY_SUPPORTED | Unit metadata; no systemd boot/service availability proof |
| Security/policies | PARTIALLY_SUPPORTED | Observable permissions/xattrs/policy files; effective access/enforcement requires target principals/probes |
| Hardware/multimedia | PARTIALLY_SUPPORTED | Userspace surface inventory; no device/codec/GPU functional validation |
| Network | PARTIALLY_SUPPORTED | Libraries/cert/config inventory; no complete DNS/DHCP/TLS/IPv6/wireless behavior |
| Performance | PARTIALLY_SUPPORTED | Optional ELF-size budget only; no product boot/CPU/memory/throughput/stability benchmark |
| GPT disk image and Samsung-custom EROFS extraction; layered OCI/EXT4 mounting | UNSUPPORTED | Supply safely extracted rootfs; no bundled product extractor, flashing, privileged mounts or payload installation |
| Missing split .dwo/.dwp/DWZ/CRC-only debug-link support | UNSUPPORTED | No invented DWARF completeness; extract supported matching debug data separately |
| Cline skill instructions and portable Python CLI | IMPLEMENTED_NOT_REAL_TIZEN_VALIDATED | CLI tested locally; latest changes were not exercised through Cline against a real product image |

## Production acceptance prerequisites

1. Supply identified baseline/candidate product rootfs snapshots and explicit GCC/LLVM/build/instrumentation provenance. Preserve the direction; compare comparable builds or document confounders. Names, ASAN mangling and symbol totals do not establish compatibility.
2. Provide readable offline installed RPM databases, independently reconcile package counts/NEVRAs/file lists, and preserve unknown/unowned records. Available RPM archives are not installed inventory. Document any package rename/split lineage from authoritative build/package metadata.
3. Supply matching SDK sysroots, actual GCC/Clang C/C++ paths/flags, build IDs and native-reference mappings. Configure ARM EABI/PCS/CPU evidence and selected loader/libc objects. Associate SDK development packages explicitly; missing SDK headers cannot pass API acceptance.
4. Supply matching embedded/split debuginfo and compatible libabigail. Review every required export/type/consumer gap; a complete symbol check is not complete type/layout coverage.
5. Establish actual target loader paths/cache/startup scope and environment. Do not set completeness flags merely to turn UNKNOWN into pass. Unsupported namespaces/interposition/IFUNC need target evidence.
6. Provide an authorized, isolated, audited device/VM/QEMU-system adapter with real deployment/hash/environment/exit/output receipts, deadlines and cleanup. Never execute extracted target binaries directly on the host. No flashing/sudo/host policy changes are implied by this skill.
7. Declare required interface/probe inventory, coverage and severity gates, acceptable N/A scope, and performance budgets before execution. SDK header limits must not silently reduce required test IDs. Confirm own-reference success before cross-image claims.
8. Run the full suite with available optional tools, then the full product analysis with sufficient disk/memory and immutable source snapshots. Independently inspect source hashes, package count reconciliation, exact finding IDs, unknown ownership, package/global failures, coverage gaps and complete JSON/CSV exports. Synthetic stress measurements do not certify product runtime or scale.

Independent code review can proceed with these documented boundaries. Production migration acceptance remains pending actual product inputs and authorized target evidence.
