# Phase 8K 最终验收

**LLVM headed 功能验收为 CONDITIONAL PASS。** 设备为 Tizen Unified Toolchain 20261120.082536、Raspberry Pi 4 ARMv7l。基础四项经正式 Adapter 各执行三次，12/12 达到冻结契约。专项 19 项实际执行，12 正例成功、6 预期失败、1 项私有 DSO 的 dlopen 契约受设备 Loader 策略阻断。另有 1 项 libc++ 跳过。

LLVM headed 上实际验证了 SDK 构建、冻结与白名单、非特权设备准入、SDB 部署、执行、行为比较、实际 Loader/Provider/版本与指定绑定、受控失败、超时和独立清理。统一报告保留 31 份最终实机观察与 21 项编译链接记录。独立清理复核覆盖本轮 44 个尝试目录和 scope，包括 2 个在 grant 前停止的尝试。原始证据仅保留在工作区 `.local-backups/phase8k-llvm-full-validation/`。

发布范围为可复用的静态分析和授权 LLVM headed 验证工作流。正式 headless 仍为 0/8，GCC/LLVM 双镜像结论 UNKNOWN，正式 cleanup 仍为 NOT_VERIFIED。目标设备原生参考与跨镜像兼容性继续保留独立状态。SQLite 验收是独立子任务。

- [完整功能矩阵](FEATURE_MATRIX.md)
- [基础实测](BASIC_RUNTIME_RESULTS.md)
- [专项实测](SPECIALIZED_RUNTIME_RESULTS.md)
- [动态链接证据](DYNAMIC_BINDING_EVIDENCE.md)
- [Adapter 复用](ADAPTER_GENERALIZATION.md)
- [端到端复现](END_TO_END_VALIDATION.md)
- [统一报告](REPORT_INTEGRATION.md)
- [安全与清理](SECURITY_AND_CLEANUP.md)
- [自动化回归](REGRESSION_RESULTS.md)
- [全量 SQLite](SQLITE_ACCEPTANCE.md)
- [剩余限制](REMAINING_GAPS.md)
- [使用指南](USER_GUIDE.md)
