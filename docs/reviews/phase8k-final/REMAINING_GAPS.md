# 剩余验证边界

- 正式 GCC/LLVM 双镜像兼容性为 UNKNOWN，VD headed 尚未准入。正式 headless 矩阵 0/8。
- 单信任域 SDB 的独立观测确认了本次目标清理。更高信任要求下的正式目标监督仍为 NOT_VERIFIED。
- 当前 LLVM Loader 拒绝私有 DSO 的 dlopen，历史原失败及成功预期原样冻结。已观察到的常驻库动态查找证据语义保持原样。
- libc++ 和 libc++abi 运行依赖缺失，设备执行保持 SKIP。
- 未触发的 Lazy Binding、其他 Loader 命名空间和产品全量行为仍缺少真实绑定证明。
- 全量 SQLite 尚待现有任务成功完成及独立核对。该任务与已完成的设备功能验收独立。

见 [正式环境与 VD 计划](VD_VALIDATION_PLAN.md) 和 [SQLite 状态](REPORT_AND_SQLITE_ACCEPTANCE.md)。
