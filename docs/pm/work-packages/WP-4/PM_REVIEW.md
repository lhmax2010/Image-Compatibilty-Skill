# WP-4 RC1 PM review

**v1.5.3-rc1 (`da37925`) is accepted as an RC.** PM checks:

| Check | Result |
|---|---|
| Full suite (PM host) | 391 tests OK, 29 tool-dependent skips |
| COPY-REL | The PM's own non-PIE `optind` reproducer is now `COMPLETE`, and `copy_relocations` records version GLIBC_2.2.5, size 4 and provider `libc.so.6`. |
| POL-WEAK on real g++ output | Hiding a template, a class vtable, typeinfo and inline members in the candidate gives 9 × `UNKNOWN LOW WEAK_CXX_EXPORT_REMOVED_UNREFERENCED`. Their `cxx_class` and demangled names are correct, and `review.pending` is 9. |
| DT-AGG | Linking findings 82,992 against a target of 80,000. Accepted. |
| SR size | 59% against a target of 50%. Accepted, because SR is a linking-profile image case. The VD measurement decides RPT-SIZE-3. |

**Gap REV-HEAD (fix in B3):** with 9 symbols pending review, the console line says `quality gate PASS`, and the summary/HTML headline does not mention the pending review. It only appears in a section further down.

**Minor:** the `copy_relocations[].name` field keeps the `@GLIBC_2.2.5` suffix, while `version` already holds it. Store the base name.
