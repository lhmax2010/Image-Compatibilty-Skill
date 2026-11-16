# Tizen image compatibility

**Result: INCOMPATIBLE** — baseline consumers on candidate.

Baseline: SYNTHETIC-baseline-NOT-TIZEN; candidate: SYNTHETIC-candidate-NOT-TIZEN.

Tests: 0; passed: 0; failed: 0; unknown: 0.
Findings: 53; incompatible: 7; unknown: 42.

Static findings are not executable test counts. No runtime execution means no runtime pass.

## Risks

- HIGH `/usr/lib/libsynthetic.so.1` / `shared_counter:size`: Review the observable contract before attributing this difference to a compiler. (TC-236fa77325a5d540)
- HIGH `/usr/lib/libsynthetic.so.1` / `shared_counter@TIZEN_SYNTH_1.0:size`: Review the observable contract before attributing this difference to a compiler. (TC-84f33f84ce944d65)
- HIGH `/usr/lib/libsynthetic.so.1` / `public_removed@TIZEN_SYNTH_1.0`: Previously linkable symbol or default symbol version is absent. (TC-9509003be6a52e21)
- HIGH `/usr/lib/libsynthetic.so.1` / `public_removed`: Previously linkable symbol or default symbol version is absent. (TC-d3ccba0f2e85f6af)
- HIGH `/usr/include/synthetic.h` / `public_removed`: Declaration changed; parameter names, typedefs and conditional context require SDK compilation to establish semantic impact. (TC-af0457a94ba018d6)
- HIGH `/usr/bin/synthetic` / `commands availability`: Review the observable contract before attributing this difference to a compiler. (TC-aff180d4c943f709)
- HIGH `/usr/share/dbus-1/interfaces/synthetic.xml` / `/test:org.synthetic.Test:method:Call`: Review the observable contract before attributing this difference to a compiler. (TC-7317ae333d584c87)

## Cross-compatibility matrix

| Compiler | Image | Headers | Runtime | Overall |
|---|---|---|---|---|
| gcc | baseline | UNKNOWN | UNKNOWN | UNKNOWN |
| gcc | candidate | UNKNOWN | UNKNOWN | UNKNOWN |
| clang | baseline | UNKNOWN | UNKNOWN | UNKNOWN |
| clang | candidate | UNKNOWN | UNKNOWN | UNKNOWN |

## Limitations

- Boot/load time, memory/CPU usage, throughput and stability benchmarks are not built in. Optional binary-size budget only.
- Built-in C/C++ probes cover a representative subset. UTF-8 locale conversion, fork/exec, timer APIs, futex/epoll/mmap and target-specific Tizen APIs need configured custom probes.
- Command presence does not prove options, stdout/stderr or exit-code semantics.
- Function/data type layouts, calling convention, padding and member offsets require usable debug info and libabigail; symbol equality alone is not ABI proof.
- Header compilation needs explicit compilers and matching SDK sysroots; lexical API collection is not a compile pass.
- Lexical declarations do not resolve conditional compilation, overloads or typedef-equivalent signatures. Use SDK compile probes for semantic confirmation.
- Loader cache, namespaces, interposition, dlopen paths, weak-symbol behavior and full versioned symbol resolution require target execution.
- Network configuration/certificate inventory does not prove DNS/DHCP/TLS/IPv6 behavior.
- No RPM database or RPM package collection found; package format not assumed.
- Offline D-Bus XML does not prove bus accessibility, Unix socket/RPC semantics or activation.
- Offline files cannot prove syscall, ioctl, /proc, /sys or kernel feature behavior.
- Offline metadata cannot prove effective ACL/LSM/capability enforcement or access permissions.
- Runtime semantics require an explicitly authorized isolated environment.
- Runtime-library inventory and ELF exports do not prove C++ ABI, builtin, sanitizer, atomic or OpenMP behavior.
- Unit files do not prove successful boot or service activation.

Excluded dimensions: 

See index.html, results.json and evidence/ for details.
