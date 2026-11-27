# WP-1 release-note draft

Readelf now recognizes hexadecimal dynamic-symbol sizes and distinguishes GNU and LLVM version-node markers from exports. ARM relocation evidence is collected separately, so relocation failures leave the export comparison available. General host-tool capture is bounded and reports OUTPUT_LIMIT. Duplicate decorated identities remain UNKNOWN, with all observations preserved.

Symbol findings provide reason codes for function/IFUNC and NOTYPE transitions, TLS kind changes, binding/visibility changes, and OBJECT/TLS size changes. Existing size increases and decreases remain HIGH incompatibilities when observed.

Zero-byte and all-zero files without a recognized filesystem or image signature now produce CLI exit 2. TAR extraction needs a regular file to form a rootfs. The legacy CLI exit policy otherwise stays the same. Optional enhanced reporting on hosts without PSI records NOT_AVAILABLE and uses memory availability data.

The ELF cache is intentionally invalidated. Schema 1.2 manifests remain readable. The exact-provenance Impact replay guard may require newly collected evidence for older collector versions.
