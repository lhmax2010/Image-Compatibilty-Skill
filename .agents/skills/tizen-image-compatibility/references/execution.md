# SDK compilation and target adapters

Normal analysis requires no network. Compilation never silently substitutes host default compilers. Supply explicit compiler executables and actual SDK sysroots for each image. GCC C/C++ may be cross compiler binaries; Clang accepts `target`. `flags` are trusted, user-provided argv elements, not shell strings. Paths are relative to the invocation working directory. Compiler `--version`, target-object ELF machine/class/endian, full argv and diagnostics are recorded. A target mismatch becomes UNKNOWN. This check does not prove SDK version equivalence.

```yaml
cross_compilation:
  enabled: true
  c_tests: true
  cpp_tests: true
  sysroots:
    baseline: /sdk/gcc/sysroot
    candidate: /sdk/llvm/sysroot
  compilers:
    gcc:
      c: /sdk/gcc/bin/aarch64-linux-gnu-gcc
      cpp: /sdk/gcc/bin/aarch64-linux-gnu-g++
      flags: []
    clang:
      c: /sdk/llvm/bin/clang
      cpp: /sdk/llvm/bin/clang++
      target: aarch64-linux-gnu
      flags: []
  include_dirs: [usr/include, usr/include/tizen]
  header_limit: 200
  probes:
    - name: my-tizen-api
      source: /tests/my_tizen_api.c
      language: c
      flags: [-lmy_tizen_library]
```

The GCC application is built once against the baseline SDK; the Clang application is built once against the candidate SDK. Each artifact is then sent to both runtime environments, without rebuilding per destination. Header probes separately compile each image's installed header with each configured compiler and that image's SDK. Runtime probe sources live in `assets/probes/`; additional probes are explicit trusted source files. Header sources that normally need preceding includes can fail standalone; a failure is only classified as a regression when the same compiler's baseline probe passed. Compilation failure is never relabeled as “compiler missing.”

SDKs should be properly relocated, trusted toolchains. A `--sysroot` and target-object check cannot prove every compiler-internal C++ include/library search directory belongs to the intended SDK. Inspect recorded argv/diagnostics and configure SDK flags accordingly. Compiler wrappers must preserve the explicit sysroot. Output artifacts remain in report `build/`; image files are never overwritten.

## Adapter contract

Execution requires `mode=runtime|full`, `runtime.enabled: true`, `runtime.authorized: true`, and explicitly configured environments. Set authorization only when the user has authorized execution in those environments. The adapter, its isolation, credentials and target transport are supplied by the operator; there is no automatic device flashing, mount, deployment or policy change.

```yaml
runtime:
  enabled: true
  authorized: true
  timeout_seconds: 60
  environments:
    baseline:
      id: tizen-gcc-isolated-guest-01
      runner: [/opt/compat/run-in-guest, --guest, gcc-test, --artifact, "{binary}", --rootfs, "{rootfs}"]
    candidate:
      id: tizen-llvm-isolated-guest-02
      runner: [/opt/compat/run-in-guest, --guest, llvm-test, --artifact, "{binary}", --rootfs, "{rootfs}"]
  probes:
    - name: systemctl-version
      dimension: commands
      argv: [/usr/bin/systemctl, --version]
      expected_exit: 0
```

This template references an operator-supplied executable; it is not a built-in adapter. Each argv token substitutes `{binary}`, `{image}` and `{rootfs}` literally. No shell is used. For built-in/compile probes, `{binary}` is a local generated artifact which the adapter must run **inside its guest**. For runtime-only probes it is a target command path, followed by the probe's arguments. The adapter must distinguish these cases, forward target stdout/stderr and exit status without banners, and perform cleanup inside the isolated environment. It must not execute target binaries on the host. Prefer disposable QEMU system guests or a dedicated device test account. QEMU user-mode alone is an emulator, not an isolation boundary.

The harness applies process-group timeouts to the adapter. The adapter must also bound remote execution and clean up remote processes; killing an SSH process alone cannot do that. Reserve exit codes 124 (timeout), 125 (transport/infrastructure), and 126/127 (unavailable execution) for adapter failures, with explanatory stderr. These codes are classified UNKNOWN even if the baseline succeeds. Such errors cannot establish compatibility. Runtime tests without a successful baseline remain UNKNOWN; a candidate nonzero result or different observable stdout/stderr against a passing baseline is INCOMPATIBLE. A local timeout/signal termination is UNKNOWN, not proof of a target crash. For command probes, `expected_exit` and optional exact `expected_stdout` define the successful baseline contract. Select only appropriate read-only commands; configuration never authorizes arbitrary commands found in an image.

Exact output comparison is intentional for deterministic probes. Do not benchmark by printing changing timestamps or addresses. Performance comparison currently implements binary-size budgets only. Use controlled, domain-specific probes and interpret noisy performance results separately from ABI/API.
