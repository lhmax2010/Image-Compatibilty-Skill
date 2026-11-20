# 使用指南

在 Linux 上使用 Python 3.10+、`readelf` 和 `rpm`。缺少可选 libabigail、SDK 或隔离目标时，结果保留 UNKNOWN 和覆盖缺口。Cline 支持项目 Skill 目录的版本可直接发现 `.agents/skills/tizen-image-compatibility/`。如果版本只识别 `.cline/skills/`，按仓库 README 将整个 Skill 目录链接或复制到项目的该路径，调用 `/tizen-image-compatibility`。

## 静态、影响与历史

```bash
SKILL=.agents/skills/tizen-image-compatibility
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline ./images/gcc-rootfs --candidate ./images/llvm-rootfs \
  --cache ./compat-cache --mode static --output ./reports/current
python3 "$SKILL/scripts/enhance_report.py" build \
  --input ./reports/current --output ./reports/current-index
python3 "$SKILL/scripts/impact_report.py" build \
  --input ./reports/current-index --output ./reports/current-impact
python3 "$SKILL/scripts/history_report.py" build \
  --before ./reports/previous-index --after ./reports/current-index \
  --scope 'Same product lineage, baseline consumers on candidate' \
  --output ./reports/history --fail-on introduced
python3 "$SKILL/scripts/history_report.py" query \
  --report ./reports/history entries --change INTRODUCED --limit 25
python3 "$SKILL/scripts/enhance_report.py" serve \
  --report ./reports/current-index --impact ./reports/current-impact --history ./reports/history
```

已有验证通过的增强报告可跳过采集与增强。打开命令输出的 loopback 地址访问 `/impact`、`/history` 和 `/#/tests`。保留原报告目录用于查看完整证据。旧增强索引可以原样打开，新的执行页需要重新增强具有执行记录的原报告。只需 Manifest 静态复用时，传递 `--baseline-manifest` 和 `--candidate-manifest`。

原 CLI `--fail-on HIGH` 应用于确认的原不兼容，`--strict` 纳入 UNKNOWN，`ci.minimum_coverage` 单独控制覆盖分母。静态 CLI 返回 0 表示所选门槛未触发，1 表示兼容性或覆盖门槛失败，2 表示输入错误，3 表示基础设施错误。历史命令 `--fail-on introduced` 以已证实引入为失败门槛，`observed-risk` 还纳入新的未配对风险，发布报告后返回 1。

## 两套真实 SDK 与隔离目标

`full` 模式用指定编译器和 SDK 执行编译与链接阶段。需同时配置 `cross_compilation.sysroots`、两种编译器、各自 native reference 和真实 ARM ABI。建议先保留 `runtime.enabled: false`，核对 `expected-tests.json` 和 `expected-tests-results.json`，再使用经授权的适配器运行。

```yaml
cross_compilation:
  sysroots:
    baseline: /approved/sdk/gcc/sysroot
    candidate: /approved/sdk/llvm/sysroot
  compilers:
    gcc: {c: /approved/sdk/gcc/bin/arm-gcc, cpp: /approved/sdk/gcc/bin/arm-g++}
    clang: {c: /approved/sdk/llvm/bin/clang, cpp: /approved/sdk/llvm/bin/clang++, target: armv7l-tizen-linux-gnueabi}
  builds:
    gcc: {sdk: baseline, reference_image: baseline, provenance: gcc-sdk-receipt-id}
    clang: {sdk: candidate, reference_image: candidate, provenance: llvm-sdk-receipt-id}
  extended_runtime_probes: true
runtime:
  enabled: false
  authorized: false
  repetitions: 2
  environments:
    baseline:
      id: enrolled-baseline-rootless
      backend: podman
      image: sha256:1111111111111111111111111111111111111111111111111111111111111111
      podman: /usr/bin/podman
      storage_root: /approved/workspace/.containers/images
      run_root: /approved/workspace/.containers/state
      capabilities: []
    candidate:
      id: enrolled-candidate-rootless
      backend: podman
      image: sha256:2222222222222222222222222222222222222222222222222222222222222222
      podman: /usr/bin/podman
      storage_root: /approved/workspace/.containers/images
      run_root: /approved/workspace/.containers/state
      capabilities: []
```

示例 ID 和路径需替换为已登记的数据。Podman 只使用已存在的本地镜像，需要本地 rootless 存储、匹配架构、镜像内 `/bin/sh` 和 `sha256sum`。容器模式共享宿主内核。需要完整 Tizen 用户态与内核时，配置已获授权的 VM 或专用设备 `runner`。跨 DSO 适配器需接收 `{companion}` 和可选 `{companion_sha256}`，在回执中带回实际部署的 `companion_sha256`。

自定义运行探针使用明确的绝对目标命令、参数、期望退出码和能力。例如专用 systemd 目标可声明 `systemd` 并只查询指定 unit，D-Bus 使用已授权的只读对象查询，multimedia 可使用只读的版本或插件信息查询。目标缺所声明的能力时不会执行探针。网络、策略和设备测试应另行核对隔离与预期输出。 [执行协议](../../.agents/skills/tizen-image-compatibility/references/execution.md)

## 可复现控制

```bash
python3 -m unittest discover -s "$SKILL/tests" -v
python3 "$SKILL/scripts/make_synthetic_fixture.py" ./synthetic-images
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline ./synthetic-images/baseline --candidate ./synthetic-images/candidate \
  --output ./reports/synthetic
```

最后一条命令预期触发破坏门槛。`tests/test_final_release.py` 提供历史修复及新增破坏、真实 ELF 字节、编译／链接阶段与 C++ 正反例。真实和合成输出的目录及身份见 [最终验收](FINAL_ACCEPTANCE.md)。
