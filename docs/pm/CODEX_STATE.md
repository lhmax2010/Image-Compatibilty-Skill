# Codex checkpoint

WP-4 RC1 was independently accepted. Addendum B packages v1.5.3-rc2.
[PM verification](work-packages/WP-4/PM_REVIEW.md) · [RC2 report](work-packages/WP-4/ADDENDUM_B_REPORT.md)

- Kit revision 7 is published at `068df39ee3ec05511fdaad144c5505512859f281`.
  Published SHA-256
  `4a8b6ae5d4442604a36cb2362690d0f344c186ec8a635f58980b9583a84cfb78`.
  A follow-up documentation commit records both digests.
- REV-HEAD and the COPY-REL base-name fix passed. The full local suite
  ran 392 tests with 386 passed, six existing skips and zero failures.
- ClineSR passed the RC1 suite on Python 3.10.22 with 391 run, 13 skipped,
  zero failures, and zero errors. PORT-310 and the Python 3.10 gate are closed.
- The reconciled synthetic MEM-SCALE slope fell 71.24%. The PM lowered
  MEM-SCALE to P2 after confirming 72 GB available on the VD-2 server
  against a 14 GB projection. Native RSS is a measurement and native
  report sizing remains open. No Addendum B local jobs remain.
- Backups and raw benchmark evidence remain workspace-local.
  The final verified backup is selected by `.local-backups/LATEST`.
