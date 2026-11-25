# Phase 8K 工作流使用指南

## 独立静态分析

```bash
skill=.agents/skills/tizen-image-compatibility/scripts
python3 "$skill/tizen_compat.py" --baseline /path/to/baseline --candidate /path/to/candidate \
  --mode static --output work/static
```

可以改用 `--baseline-manifest` 与 `--candidate-manifest`。静态入口不依赖 SDB。

## 编译与审核

```bash
python3 "$skill/runtime_workflow.py" build --config work/build-config.json --output work/build
```

构建配置包含 `sources`（源码路径数组）、`sdk`（按 SDK 别名索引）、`steps`（按构建顺序）和 `probes`。每个 SDK 指定 `host`、`sysroot`、`startfiles`、`lock`、`lock_sha256`、`label` 和 `compiler_sha256`（按 driver 路径索引）。Clang 22 的当前布局可设置 `clang_resources: true`。每个 step 使用 `sdk`、`driver`、`flags` 和唯一 `out`，可设置预期非零 `expected_returncode` 及 `stderr_contains`。沙箱内源目录为 `/work/src`，中间产物目录为 `/work/out`，目标 sysroot 为 `/sysroot`。每个 probe 使用 `artifact_id`、`files`（目标文件名到构建输出名）、`runtime_expectation`（`exit_code`、`stdout`、`stderr`，可选 `outcome` 与 `stderr_contains`）和可选 `binding_symbols`。

核对 `build.json`、冻结产物、源码、工具版本和预期行为。独立保存获准的 `probe-manifest.json` SHA256，并在受信 enrollment 中记录授权的每项 executable SHA256、Manifest SHA256 和 `probe_bundle.target_pin` 计算的设备身份指纹。先从可信发布材料/已核验设备记录取得设备和运行库 pin。

## 只读计划、执行与汇总

```bash
python3 "$skill/runtime_workflow.py" run --config work/run-config.json --output work/plan
python3 "$skill/runtime_workflow.py" run --admit --config work/run-config.json --output work/admission
python3 "$skill/runtime_workflow.py" run --execute --config work/run-config.json --output work/run
python3 "$skill/runtime_workflow.py" report --config work/report-config.json --output work/report
```

每个 `runs[]` 提供 `manifest`、`manifest_sha256`、`bundle`、`enrollment` 和按计划排列的 `artifacts`。旧 Phase 8E 清单可沿用原入口和授权。Enrollment 格式见 [Phase 8J 协议](../phase8j/ADAPTER_PROTOCOL.md)。默认失败即止。只有明确配置 `continue_after_verified_cleanup` 且上次已验证观测清理时，另一个预先获准的探针才可继续。所有输出路径应为新的专用目录。

```json
{
  "static_report": {"directory": "work/static", "scope": "SR_HEADLESS_STATIC"},
  "build_reports": ["work/build/build.json"],
  "runs": [{
    "manifest": "work/build/probe-manifest.json",
    "manifest_sha256": "<审核后独立保存的完整 SHA256>",
    "bundle": "work/build/bundle",
    "enrollment": "work/private/enrollment.json",
    "artifacts": ["version-present"]
  }]
}
```

报告配置可提供 `static_report`，其 `directory` 指向原始报告，`scope` 描述原始 Profile。可选 `build_reports` 和 `runtime_reports` 分别是 `build.json`、`runtime.json` 路径数组。配置和原始证据可能包含设备身份和工作路径，仅在获准本地存储保留。SDK 审核、设备 enrollment 和实际执行授权由操作者独立确认。
