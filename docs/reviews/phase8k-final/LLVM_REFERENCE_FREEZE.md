# LLVM headed 参考冻结

参考包在工作区本地 `.local-backups/phase8k-final/LLVM_REFERENCE/`。清单以单文件 SHA256 和大小验证内容，完成后设置只读权限。该包保留四个基础冻结产物、19 个已执行专项的原始 executable/DSO、独立 libc++ 离线产物、原始源码和实际编译链接参数、SDK 版本和 RPM 锁定依据。新精确 Manifest 的两个文件与原专项 Bundle 逐字节一致，无重新编译。

包还保存 44 条历史尝试及原始 Evidence、1 条本轮独立的精确验证、环境身份、清理证据、离线审核 Ledger、目标策略失败与可复核的完整报告。归档 enrollment 保留身份字段，不附带可执行授权。原始设备身份和大型证据数据留在已认可的工作区。HEADLESS 静态指标在历史报告中标明独立范围，未作为 LLVM headed 参考身份使用。

在 `.local-backups/phase8k-final/` 内使用 `replay-from-reference-config.json` 和 `runtime_workflow.py report` 可离线从只读包重放 Runtime 对账。该重放已验证 44 次尝试、24 项成功及原失败分布。后续授权测试先核对冻结清单、各 Manifest 与 Bundle 字节，再创建新目标的 enrollment。不要沿用本次 Board、Boot 或历史授权作为 VD 入场记录。

详见 [VD 验证计划](VD_VALIDATION_PLAN.md)。

封存清单列出 1228 个文件，合计 8,121,663 B。封存清单 SHA256 为 `f803786e05e5a5b7fe2ff95e1955977364cf281f50c1cd84a8b79d15a068d13b`。
