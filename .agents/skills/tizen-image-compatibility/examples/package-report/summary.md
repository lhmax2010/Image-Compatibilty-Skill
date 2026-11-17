# Tizen image compatibility

**Result: INCOMPATIBLE** — baseline consumers on candidate.

Baseline: SYNTHETIC metadata baseline; candidate: SYNTHETIC metadata candidate.

Tests: 0; passed: 0; failed: 0; unknown: 0.
Findings: 14; incompatible: 13; unknown: 1.

Static findings are not executable test counts. No runtime execution means no runtime pass.

## Risks

## Coverage

| Dimension | Applicable | Complete | Partial | Unexecuted | Compatible | Incompatible | Unknown | Complete coverage % | Compatible / applicable % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| elf | 0 | 0 | 0 | 0 | 0 | 0 | 0 | None | None |
| abi | 8 | 4 | 0 | 4 | 0 | 4 | 4 | 50.0 | 0.0 |
| api | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0.0 | 0.0 |
| headers | 0 | 0 | 0 | 0 | 0 | 0 | 0 | None | None |
| linking | 4 | 4 | 0 | 0 | 0 | 4 | 0 | 100.0 | 0.0 |
| compiler_runtime | 0 | 0 | 0 | 0 | 0 | 0 | 0 | None | None |
| kernel | 0 | 0 | 0 | 0 | 0 | 0 | 0 | None | None |
| ipc | 0 | 0 | 0 | 0 | 0 | 0 | 0 | None | None |
| commands | 0 | 0 | 0 | 0 | 0 | 0 | 0 | None | None |
| filesystem | 0 | 0 | 0 | 0 | 0 | 0 | 0 | None | None |
| packages | 4 | 0 | 0 | 4 | 0 | 0 | 4 | 0.0 | 0.0 |
| services | 0 | 0 | 0 | 0 | 0 | 0 | 0 | None | None |
| security | 0 | 0 | 0 | 0 | 0 | 0 | 0 | None | None |
| runtime | 0 | 0 | 0 | 0 | 0 | 0 | 0 | None | None |
| hardware | 0 | 0 | 0 | 0 | 0 | 0 | 0 | None | None |
| network | 0 | 0 | 0 | 0 | 0 | 0 | 0 | None | None |
| performance | 0 | 0 | 0 | 0 | 0 | 0 | 0 | None | None |

Quality gate: FAIL; compatibility=FAIL; coverage=FAIL; strict=PASS

## Incompatible interfaces (first 200; full list in JSON/CSV)

- HIGH `/usr/lib/libsynthetic0.so` / `public_0`: Review the observable contract before attributing this difference to a compiler. (TC-5e4ea6d98749c766)
- HIGH `/usr/lib/libsynthetic0.so` / `public_1`: Review the observable contract before attributing this difference to a compiler. (TC-6a1009b7696b460b)
- HIGH `/usr/lib/libsynthetic1.so` / `public_0`: Review the observable contract before attributing this difference to a compiler. (TC-032bc6382407c763)
- HIGH `/usr/lib/libsynthetic1.so` / `public_1`: Review the observable contract before attributing this difference to a compiler. (TC-45ecb1e1d8c63d45)
- HIGH `/usr/lib/libsynthetic2.so` / `public_0`: Review the observable contract before attributing this difference to a compiler. (TC-1b1ccb25204ecd7d)
- HIGH `/usr/lib/libsynthetic2.so` / `public_1`: Review the observable contract before attributing this difference to a compiler. (TC-ee0cb4fbaf603093)
- HIGH `/usr/lib/libsynthetic3.so` / `public_0`: Review the observable contract before attributing this difference to a compiler. (TC-209b428c97fe4497)
- HIGH `/usr/lib/libsynthetic3.so` / `public_1`: Review the observable contract before attributing this difference to a compiler. (TC-342b3e59fe6147b7)
- HIGH `/usr/lib/libsynthetic0.so` / `baseline consumers on candidate:import:public_0`: Review the observable contract before attributing this difference to a compiler. (TC-17c8b44e14ae3489)
- HIGH `/usr/lib/libsynthetic1.so` / `baseline consumers on candidate:import:public_0`: Review the observable contract before attributing this difference to a compiler. (TC-8cf29d936b110194)
- HIGH `/usr/lib/libsynthetic2.so` / `baseline consumers on candidate:import:public_0`: Review the observable contract before attributing this difference to a compiler. (TC-2fec1d74fe7b4dba)
- HIGH `/usr/lib/libsynthetic3.so` / `baseline consumers on candidate:import:public_0`: Review the observable contract before attributing this difference to a compiler. (TC-1296fd79f064dd44)
- MEDIUM `/opt/unowned.so` / `unowned`: Review the observable contract before attributing this difference to a compiler. (TC-92751126ac82c439)

## Package compatibility

Installed package counts: baseline=4; candidate=4. null means UNKNOWN, not zero.

| Package | GCC baseline version | LLVM candidate version | ABI | API | Linking | Complete coverage % | Overall |
|---|---|---|---|---|---|---:|---|
| runtime:synthetic-0 | 0:1-1.x86_64 | 0:1-1.x86_64 | INCOMPATIBLE | UNKNOWN | INCOMPATIBLE | 60.0 | INCOMPATIBLE |
| runtime:synthetic-1 | 0:1-1.x86_64 | 0:1-1.x86_64 | INCOMPATIBLE | UNKNOWN | INCOMPATIBLE | 60.0 | INCOMPATIBLE |
| runtime:synthetic-2 | 0:1-1.x86_64 | 0:1-1.x86_64 | INCOMPATIBLE | UNKNOWN | INCOMPATIBLE | 60.0 | INCOMPATIBLE |
| runtime:synthetic-3 | 0:1-1.x86_64 | 0:1-1.x86_64 | INCOMPATIBLE | UNKNOWN | INCOMPATIBLE | 60.0 | INCOMPATIBLE |

First 200 packages shown; full records, ownership, findings and gaps are in results.json and packages.csv.

## Cross-compatibility matrix

| Compiler | Image | Headers | Runtime | Overall |
|---|---|---|---|---|

## Limitations

- Generated metadata; not queried from RPM or a real Tizen image

Excluded dimensions: commands, compiler_runtime, elf, filesystem, hardware, headers, ipc, kernel, network, performance, runtime, security, services

See index.html, results.json and evidence/ for details.
