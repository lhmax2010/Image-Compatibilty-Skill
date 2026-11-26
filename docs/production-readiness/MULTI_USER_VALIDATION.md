# Multi-user and path validation

Two packaged Skill installations ran under distinct HOME directories, working directories and private task outputs. Both jobs ran concurrently from a network-isolated Bubblewrap namespace with a read-only host mount and an explicitly writable job boundary. Paths included spaces, Latin Unicode and Chinese characters. Each run used the installed v1.5.2 package and rebuilt its synthetic RPMs. The two runs reconciled identical scope, objective, execution, compatibility, coverage, Finding counts and symbol statistics.

| Test | Result |
| --- | --- |
| Two independent installations, two HOME and cwd values | PASS |
| Two concurrent jobs, distinct outputs and isolated scratch | PASS. Both reported 2 RPMs and 2 ELF objects per side, 16 Findings and 9 symbol rows |
| Two processes given the same output | One owner wrote a complete report and the other returned 2 |
| Shared cache between trusted same-user jobs | Cache concurrency test passed. Both read the complete verified entries; invalid evidence triggers recollection |
| Missing-tool preflight | BLOCKED with the missing tool summary |
| Read-only destination | Refused with infrastructure exit 3 and created no report directory |
| Occupied report port | Local test got exit 2 with the alternate-port hint; the original listener remained alive |
| Different SDK data | Read-only isolated GCC and Clang SR SDK selections compiled genuine ARM ELF into separate fixture RPMs |
| Different device configuration | Existing synthetic enrolled-device tests validate endpoint/identity controls. A second actual target was unavailable |

Both installs ran under the same actual unprivileged UID. Distinct real accounts, shared production storage permissions and another physical device remain NOT VERIFIED. Use per-account home/cache permissions and separate outputs on the deployment host.

The final package's two job receipts, execution logs and reconciliation are in the local release working directory. The upstream [demo command](DEMO_GUIDE.md) reproduces the portable workload.
