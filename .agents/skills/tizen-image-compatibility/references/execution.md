# SDK compilation and target adapters

Normal analysis requires no network. Compilation never silently substitutes host default compilers. Supply explicit compiler executables and actual SDK sysroots for each image. GCC C/C++ may be cross compiler binaries; Clang accepts `target`. `flags` are trusted, user-provided argv elements, not shell strings. Paths are relative to the invocation working directory. Compiler `--version`, target-object ELF machine/class/endian plus ARM EABI/float PCS, full argv and diagnostics are recorded. A target mismatch becomes UNKNOWN. This check does not prove SDK version equivalence.

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
      c: /sdk/gcc/bin/arm-linux-gnueabi-gcc
      cpp: /sdk/gcc/bin/arm-linux-gnueabi-g++
      flags: []
    clang:
      c: /sdk/llvm/bin/clang
      cpp: /sdk/llvm/bin/clang++
      target: armv7-linux-gnueabi
      flags: []
  # Examples only: fill with the actual SDK/native image and GBS build identifiers.
  builds:
    gcc: {sdk: baseline, reference_image: baseline, provenance: gbs-gcc-build-id}
    clang: {sdk: candidate, reference_image: candidate, provenance: gbs-clang-build-id}
  semantic_headers: false
  include_dirs: [usr/include, usr/include/tizen]
  header_limit: 200
  probes:
    - name: my-tizen-api
      source: /tests/my_tizen_api.c
      language: c
      flags: [-lmy_tizen_library]
```

The `builds` mapping explicitly chooses each compiler's SDK, successful native reference image, and build provenance. The example maps GCC to baseline and Clang to candidate; reversing either mapping is supported. Without this mapping no runtime artifact is inferred. Each artifact is sent unchanged to both runtime environments. Header probes compile SDK headers with each configured compiler and that SDK; runtime-image header availability is recorded separately. Runtime probe sources live in `assets/probes/`; additional probes are explicit trusted source files. Header sources that normally need preceding includes can fail standalone; a failure is only classified as a regression when the same compiler's baseline probe passed. Compilation failure is never relabeled as “compiler missing.”

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

This template references an operator-supplied executable; it is not a built-in adapter. Each argv token substitutes `{binary}`, `{image}` and `{rootfs}` literally. No shell is used. For built-in/compile probes, `{binary}` is a local generated artifact which the adapter must run **inside its guest**. For runtime-only probes it is a target command path, followed by the probe's arguments. The adapter must distinguish these cases, return the JSON receipt below on stdout without banners, and perform cleanup inside the isolated environment. It must not execute target binaries on the host. Prefer disposable QEMU system guests or a dedicated device test account. QEMU user-mode alone is an emulator, not an isolation boundary.

The harness applies process-group timeouts to the adapter. The adapter must also bound remote execution and clean up remote processes; killing an SSH process alone cannot do that. Reserve exit codes 124 (timeout), 125 (transport/infrastructure), and 126/127 (unavailable execution) for adapter failures, with explanatory stderr. These codes are classified UNKNOWN even if the baseline succeeds. Such errors cannot establish compatibility. Runtime tests without a successful **own reference_image** remain UNKNOWN on both destinations; this applies equally to candidate-built artifacts. The adapter's process exit code is infrastructure status; target exit code is inside the receipt. A zero adapter exit alone is never proof of successful deployment/execution. Runtime tests without a valid receipt remain UNKNOWN; a candidate nonzero result or different observable stdout/stderr against a passing baseline is INCOMPATIBLE. A local timeout/signal termination is UNKNOWN, not proof of a target crash. For command probes, `expected_exit` and optional exact `expected_stdout` define the successful baseline contract. Select only appropriate read-only commands; configuration never authorizes arbitrary commands found in an image.

Exact output comparison is intentional for deterministic probes. Do not benchmark by printing changing timestamps or addresses. Performance comparison currently implements binary-size budgets only. Use controlled, domain-specific probes and interpret noisy performance results separately from ABI/API.

## Receipt version 1

The trusted operator adapter emits one JSON object (outer process exit 0):

```json
{
  "schema": "tizen-compat-runner/v1",
  "environment_id": "tizen-llvm-isolated-guest-02",
  "binary_sha256": "actual-sha256-of-the-deployed-artifact",
  "deployment": "ok",
  "execution": "ok",
  "returncode": 0,
  "stdout": "observable target output\n",
  "stderr": ""
}
```

`environment_id` must equal configuration. For compile probes the digest must match the local generated artifact; for custom commands it must match the command resolved inside the image. Report the actual deployed/observed bytes, not a guessed digest. A transport cannot claim deployment/execution success before observing it. The harness validates identity, hash and schema but cannot independently attest the adapter's honesty or isolation. Use an audited production adapter. Test suite simulated receipts validate the harness only.

Reports separately expose `compile_status`, `deployment_status`, `execution_status`, `behavior_status`, `build_sdk`, `build_provenance`, and `reference_image`. Runtime behavior is COMPATIBLE only after a valid own-reference run and matching output/exit status. Missing compiler, incomplete target ABI, failed native probe, invalid receipt, unsupported environment or absent deployment evidence stays UNKNOWN. Direct runner invocation of a target artifact/image path is rejected. Operator adapters remain trusted and must never execute the target on the host.

ARM example triples/float flags must match your product's SDK; do not assume all Tizen ARMv7 builds use the same PCS. Read [correctness.md](correctness.md) for exact analysis boundaries.

## Expected tests and complete verification (1.2)

The harness inventories SDK headers and writes `expected-tests.json` before invoking compilers or adapters. Stable IDs bind compiler family/binary hash/configuration, source path/hash, SDK label/path, build provenance, configured target ABI, native reference and destination. Missing prerequisites remain planned. `header_limit` controls execution only; it does not remove mandatory expected headers. A baseline SDK header absent from the candidate is still planned for both. Missing header inventories create an unknown discovery test.

Build tests require target ABI, compilation and linking. Header tests require target ABI, compilation and the same compiler's baseline reference. Runtime tests require successful compilation/linking, the frozen artifact hash, valid deployment/execution receipts, a valid native reference and behavior comparison. Custom command probes require artifact/deployment/execution/reference/behavior stages. Unconfigured identities are explicit null/unknown fields, not invented provenance. Observed target ABI and artifact hash are attached to reconciled results.

`expected-tests-results.json`, image manifests and `results.json.expected_tests` retain each planned ID, required checks, stage results, completeness and diagnostic reasons. Exact reconciliation lists missing, duplicate and unexpected IDs. Duplicates cannot satisfy missing tests; unexpected positive records are downgraded. No compiler/image cell is COMPATIBLE while a required ID/stage is unknown. Confirmed failures survive incomplete stages. A static run normally leaves matrix obligations NOT_EXECUTED; this is expected and visible.

## ARMv7 primary ABI and supporting runtime objects

Configure the actual SDK ABI with provenance. The following values are examples, **not defaults for all Tizen products**:

```yaml
cross_compilation:
  target_abis:
    baseline:
      machine: ARM
      class: ELF32
      endianness: "2's complement, little endian"
      eabi: 5
      float: soft
      cpu_arch: v7
      provenance: product-SDK-toolchain-manifest-id
    candidate:
      machine: ARM
      class: ELF32
      endianness: "2's complement, little endian"
      eabi: 5
      float: soft
      cpu_arch: v7
      provenance: candidate-SDK-toolchain-manifest-id
  runtime_objects:
    baseline: [/lib/ld-linux.so.3, /lib/libc.so.6]
    candidate: [/lib/ld-linux.so.3, /lib/libc.so.6]
```

`float: hard` means VFP calling convention; `float: soft` means base PCS, which includes softfp code generation. Recorded `float_codegen` and ARM macros distinguish softfp from software-only arithmetic without conflating them with calling convention. Object metadata uses readelf field spelling. Compiler probes must be ET_REL; selected runtime objects must be complete DYN/EXEC records. Configured target ABI is primary. Without it the verifier tries selected loader/libc evidence; incomplete ARM evidence yields UNKNOWN. Unrelated ELF attributes no longer veto every compiler probe. Explicit conflicts with authoritative objects prevent acceptance; mixed/missing other objects receive separate findings. CPU attribute equality is conservative, not full ISA feature compatibility proof. AArch64 retains machine/class/endian checks.

SDK package attribution can additionally use `sdk_package_manifests`; see [packages.md](packages.md). Compilation success does not imply whole-package API semantic compatibility.
