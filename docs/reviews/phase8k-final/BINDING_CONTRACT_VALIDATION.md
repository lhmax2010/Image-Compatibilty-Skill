# 精确动态符号绑定

基线能够仅凭 `sr_contract` 名称将错误版本、错误 Provider 和错误 Consumer 的一条日志视为已观察。结构化 `binding_contracts` 现在要求同时匹配这四项，并要求实际 Provider 对应 Loader 装载记录及已核验 SHA256。系统 DSO 以实际装载绝对路径或其已核验别名识别，私有文件以 `bundle:<leaf>` 识别。后者只接受本次部署目录下已钉住的同一文件。

```json
{
  "consumer": "bundle:probe",
  "provider": "bundle:libsr_probe.so",
  "symbol": "sr_contract",
  "version": "SR_PROBE_1",
  "provider_sha256": "5b219a8695c9613b99e31f11d3d9878f326b33b1b851721545d8e465fc3f0753"
}
```

`version: null` 要求实际日志中无版本。当前精确观察仅对目标使用的 glibc 基础加载命名空间给予验证。相同 Consumer、Symbol 和 Version 出现竞争 Provider 或跨命名空间证据时保留 `NOT_VERIFIED`。不同 Consumer 独立验证。版本检查、名称级观察和精确绑定分别保存。旧 `binding_symbols` 仍按名称观察，且不会生成精确验证信用。尚未发生的 Lazy Binding 保留 `NOT_VERIFIED`。

先从旧运行的原始 Loader 文件重新计算 SHA256，与旧回执比对，再重放同一正例和错误版本、Provider、Consumer、缺失事件及竞争 Provider 对照。随后只在现有 LLVM headed 板上执行一次 `version-present`。原始 executable SHA256 为 `70da754484b813fd60089eadcd0550ec36c23dd1db09b0fa8666474627a7957b`，DSO 摘要如上。本次 Manifest SHA256 为 `ec9683cdab0e436880216916e5cfb66f735a73b5d0aebd938a696acfd7526c8f`，使用重新授权的清单和设备环境。设备退出 0，精确绑定、预期输出和观测清理通过，正式目标清理仍为 `NOT_VERIFIED`。独立 SDB 检查确认同一 Boot 中 PID、cgroup 和临时目录均已消失。

复现入口为 `runtime_workflow.py run --execute`，本地记录为 `binding-offline-audit.log`、`exact-device/` 和 `exact-cleanup-recheck.log`。源码见 [Verifier](../../../.agents/skills/tizen-image-compatibility/scripts/compat/runtime_binding.py) 和 [定向回归](../../../.agents/skills/tizen-image-compatibility/tests/test_runtime_release.py)。
