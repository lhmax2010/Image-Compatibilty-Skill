# Demo fixture acceptance

The generator creates two RPMs on each side. Both contain actual ELF shared objects under payload filenames with no `.so` suffix. The baseline and candidate include the identical consumer bytes and distinct provider bytes. The `demo-client` RPM requires `demo-codec-abi`. Its real ELF imports `legacy_export@DEMO_1` and records the provider SONAME `libdemo-codec.so.1`.

| Observation | Baseline | Candidate | Expected |
| --- | --- | --- | --- |
| Provider package | `demo-codec` 1-1 | `demo-codec` 2-1 | Package version changed |
| Removed symbol | `legacy_export@@DEMO_1` | Absent in that provider | Missing in complete export table, incompatible |
| Added symbol | Absent | `added_export@@DEMO_1` | Added |
| Version contract | `version_contract@@DEMO_2` | `version_contract@@DEMO_3` | Version changed, baseline lookup risk |
| Data size | `data_contract@@DEMO_1`, 4 B | Same identity, 8 B | Data size changed, incompatible |
| Code size | `stable_code@@DEMO_1` | Same identity, larger function | Code size observation |
| C++ control | `_Z8demo_cppi@@DEMO_1` | Same identity | Matched |
| Consumer requirement | `legacy_export@DEMO_1` | Same import | Requirement preserved, installed runtime UNKNOWN |

Expected local measurements per side are two RPMs discovered and extracted, two ELF objects collected, two complete export inventories, seven export observations and one import observation. On this fixture the seven unique export names represent thirteen lookup identities per side (a version identity and an unversioned default alias for each of six versioned exports, plus one unversioned export). The fixture run on the x86-64 GNU environment gave nine symbol detail rows (four matched, three changed, one added and one missing). The run produced 16 findings across all enabled checks (five incompatible, six unknown, four compatible and one identical). These totals depend on the fixture/compiler and report policy. The one-click demo independently checks the six core symbol facts, input and evidence digests, JSON/CSV Finding IDs and installed loader UNKNOWN.

Open `report/elf-symbol-summary.csv` for the SONAME and DT_NEEDED evidence, `report/symbol-differences.csv` for the before/after payloads and `report/findings.csv` for original Finding IDs. `report/extraction-errors.csv` is empty apart from its header for this fixture. `demo-receipt.json` records independent demo checks.
