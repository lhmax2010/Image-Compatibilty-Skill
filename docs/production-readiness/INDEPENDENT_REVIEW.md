# Independent design and code review

The reviewed baseline was v1.5.1 at `2d43c58b8753c53f58fae906cc4c821bd6227397`. Four separate passes covered architecture and compatibility (A), security and side effects (B), configuration and Agent usability (C), and tests and Demo readiness (D). A, B and D used independently running Codex reviewers. C and reconciliation were performed by the integrating Codex session. The reviewers used the same model family. No independent external model, company Agent, or human sign-off was available.

## Additional findings from integration and release review

| Severity and baseline source | Trigger and minimum proof | Impact and implemented correction | Regression and closure |
| --- | --- | --- | --- |
| P1 • tizen_compat.py:104–107 | Two local processes use the same new report destination while both pass the emptiness check | Results and evidence could interleave. An exclusive output claim is now made before any report writes | `test_simultaneous_same_output_has_one_owner` verifies exactly one writer. CLOSED |
| P1 • SKILL.md:14–24 and compat/report.py:144–193 | A no-ELF image or metadata-only report could look like a completed export job to a generic Agent. The old guide directed the Agent to the full results payload | The offline controller validates an explicit goal and emits independent bounded statuses. HTML and Markdown show them in the overview. The original CLI contract remains available | `test_required_export_without_elf_is_not_success`, metadata test and optional-stage failure test. CLOSED |
| P2 • enhance_report.py:27 and report_browser.py:230 | Start the local report browser on an occupied loopback port | Raw bind exception gave no recovery action. The CLI now reports the occupied port and suggests an available port or port 0 | `test_occupied_report_port_produces_actionable_cli_error` uses a real loopback listener. CLOSED |

P0 defects were not identified. The security pass's seven closed P1s, proofs and operating limits are recorded in [Security and side effects](SECURITY_AND_SIDE_EFFECTS.md). Production readiness includes external gates beyond the closed code findings.

## Design findings and implementation boundaries

The comparison engine, ELF ABI classifiers, Linking resolver, ownership model, exact Runtime binding, expected-plan reconciliation, SQLite, Impact and History remain separate. The controller delegates to these implementations and starts neither a networked stage nor a target. Existing enhanced reporting uses bounded projections. The base report now ships library and symbol CSVs for explicit Rootfs export jobs and all RPM payload jobs.

Config input has a strict small JSON contract, while advanced SDK and target configuration stays in the existing mechanism. Platform-specific build and loader evidence remains explicit. Task D generated real fixture RPMs and ran the actual browser. See [feature matrix](FEATURE_ACCEPTANCE_MATRIX.md) and [demo](DEMO_GUIDE.md).

## Architecture and compatibility evidence

Reviewed baseline 2d43c58. Runtime permissions and external sharing are assessed separately. Repo path names below are relative to the Skill scripts directory at that baseline.

| Severity | Evidence and trigger | Impact | Minimal fix and regression |
| --- | --- | --- | --- |
| P1 | `compat/core.py` 570–581, 635–643 allowed only the readelf/rpm receipts and installed statuses. Native manifests include rpm2cpio, archive-keyed error receipts and an installed inventory of NOT_APPLICABLE. Both published synthetic v1.5.1 manifests independently failed read_manifest. | A required, own-output replay path always failed before comparison. A malformed repository object graph could also raise a traceback. | Scope receipt/status validation to RPM replay, reconcile archive IDs, object references and counts. Real fallback/replay protection verifies identical symbol CSV and findings and a clean exit 2 for a dangling object. The v1.5.1 archives still replay at 30 findings and the expected compatibility exit 1. |
| P1 | `compat/repository.py` 105–152 and 248–268 take a single archive from each group and omit groups of multiple versions. Compare two versions of one RPM against its third version, all carrying ELF at one internal path. | Successfully collected objects and symbols vanished from per-ELF and per-symbol tables, though aggregate counts included them. A failed duplicate could hide a successful equivalent archive. | Emit one-sided observations for all unpaired objects, retain independent archive identities, prefer completed duplicate when choosing the comparison representative, and avoid absence claims. A true three-RPM fixture retains two baseline and one candidate ELF, with 18/9 distinct export observations across the source objects. |
| P1 | `compat/elf.py` 134–145 and 200–208 take the first word of the dynsym name and allow arbitrary trailing text in the completeness parser. Native GNU assembler and readelf demonstrate `space name` becoming `space`. | Distinct, legitimate exported names collapsed while the inventory was marked complete. A real removal could be missed. | Share the row parser and retain the name after Ndx. Parse only applicable GNU import version indices and bump the ELF inventory cache revision. The native two-DSO fixture detects loss of `sample name (4)`, and the GNU marker/provider tests pass unchanged. Earlier reports retain their recorded evidence. Collect the original inputs again for corrected name evidence. |
| P1 | `compat/repository.py` 174–209 inferred an unmatched version relationship even if the inventory was incomplete, labeled a pure default-lookup change as VERSION_CHANGED, and reported known compatible additions as UNKNOWN. | The symbol display conflated observed names with lookup requirements and could contradict the exact Finding report. | Match qualified identities before name-only pairing when both inventories are complete, distinguish default lookup changes, use observation labels for partial residuals, and project the authoritative exact Finding verdict. Reconcile the real fixture CSV with report split by role. |

## Reconciled v1.5.1 fixture

Both inputs observe 18 distinct raw export rows across two ELF files each. Unique export base names across each input are 9 and 10. Each input has 36 lookup identities summed across individual ELF files, since each default export is also eligible for unversioned lookup. This is distinct from comparing those symbols. The 25 combined comparison rows consist of 19 export rows (14 matched, one added, three changed, one missing) and six import rows (two matched, four added). The malformed candidate RPM gives partial archive scope even with complete export inventories on two observed ELF files.

## Additional architecture coverage

- `compat/preparation.py` 194–235 retains GPT partition geometry and distinguishes filesystem headers, XZ expansion, vendor readiness and standard EROFS extraction. EROFS real decoding is unverified without local mkfs.erofs/fsck.erofs. The fixture proves tool orchestration, original inputs stay intact and explicit fallback reaches native RPM analysis. It provides no evidence for Samsung layout support.
- `compat/compare.py` 65–158 makes ELF identity, absence, versions and local type/size observations distinct. This review inherits limitations for debug/type layout and cannot derive ABI compatibility from a count match.
- `compat/linker.py` 34–95, 145–249 uses recorded startup context, provider reachability, version requirements and special symbol handling. Repository analysis has no measured installed Consumer–Provider resolution. It keeps scope UNKNOWN. Phase 8A and the static-fixes suite include real or directed controls for namespace, missing inventory and required version.
- `compat/matrix_manifest.py` 106–178 verifies expected test cardinality and required stages and preserves prior failures. `compat/sdb_runtime.py` 259–341 and 463–541 separates observed bindings, attempt identity, cleanup proof and formal Runtime. No new device execution was performed in this review.
- `compat/history.py` 122–177 requires explicitly comparable architectures and independent output, reconciles linked evidence, uses local SQLite read-only input and exact payload matching. Impact and History limitations for RPM-only scope remain explicit.
