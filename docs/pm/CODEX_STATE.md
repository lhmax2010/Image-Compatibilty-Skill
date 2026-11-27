# Codex checkpoint

WP-3 is implemented and awaiting independent PM review. Start with [REPORT.md](work-packages/WP-3/REPORT.md) and the [issue register](ISSUE_REGISTER.md).

- The PM accepted Addendum A at `d9aa0803a3465f83b5d93cd2c15706c329b6cf4c`. The accepted script SHA256 is `ee9b0b6c109f67b9dd27bb70bce053b542364cc7a8f27017382be9a6cdb49a1a`.
- Startup commit `5d191e1da0a6091ae0aa9848c84b53e0a12422d1` recorded WP-2 review and continuity. Backup `pm/20261127T054422Z` was verified.
- Implementation `853cadcb7107a159a0ca54dbf3dbb6312473c661` passed 375 tests with 369 passed, six existing skips and zero failures.
- The no-profile and partial-profile SR runs are complete. They produced 44,142 and 604,645 findings. Both retain 11,490 confirmed incompatibilities and zero complete linking coverage. The failed first profile attempt is retained locally. JSON/CSV and source SHA256 were checked.
- Raw reports and test logs remain only in workspace-local WP-3 evidence. The verified post-run backup is selected by `.local-backups/LATEST`. There are no WP-3 subprocesses pending.
- WP-4 retains the Python 3.10 execution and Bubblewrap/EROFS portability gates.
