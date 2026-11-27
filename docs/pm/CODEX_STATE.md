# Codex checkpoint

WP-4 produced v1.5.3-rc1. [Full section 10 report](work-packages/WP-4/REPORT.md)

- Step 0 `4bebed633420b758356c8384d32ddbc144ca2d5f` records the accepted
  WP-3b work and the VD-1b measurements.
- Step 7 `6434bdf07a3e4a9396297dcdbfcbcf599282bfd4` publishes the tested
  ClineSR suite runner. Script SHA-256
  `99d5a0115c1c6e190f4a27e60d2894796481dc6e675ba6cb3f1dde7954cd091f`.
- Implementation `8b948dd0fa98bf74fbae6dbda04a922b8696d1d5` passed
  391 regression tests with 385 passed, six existing skips and zero failures.
- Synthetic scale met its size target. SR completed and reconciled with
  82,992 Linking findings and 963,303,190 report bytes. Both SR targets
  remain open. The initial run omitted the performance exclusion, so the
  measured rerun used the historical arguments in a fresh output.
- Real EROFS, native Python 3.10 and VD acceptance remain pending. Raw traces,
  historical reports and immutable hash checks are workspace-local. The
  selected final backup is in `.local-backups/LATEST`. No WP-4 jobs remain.
