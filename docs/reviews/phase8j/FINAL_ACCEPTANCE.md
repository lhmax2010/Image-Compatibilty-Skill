# Phase 8J 验收

**可复用 SDB 观察 Adapter 已实现并通过实际设备单项复验。正式跨镜像兼容性保持 UNKNOWN。**

| 验收层 | 结果 |
| --- | --- |
| 入口、授权和身份 | 本地计划、现场只读准入以及显式授权的单产物执行均验证。Phase 8E 四件原始 SHA256 保持。 [设计](DESIGN_IMPLEMENTATION.md) · [协议](ADAPTER_PROTOCOL.md) |
| 实际设备 | 新 Adapter 只复跑 LLVM headed 上的 Clang C。部署 SHA256 复核通过，实际退出 0，stdout 匹配，stderr 空，确认三个实际加载文件和八条版本检查。 [实际验证](LIVE_DEVICE_VALIDATION.md) |
| 当前业务清理 | 另一路 SDB 核对本次 PID/starttime、scope 与 cgroup，退出观察通过，私有目录消失。 |
| 正式退出证明 | NOT_VERIFIED。实际文字材料是同一 SDB 信任域内的独立观察，用户级 cgroup 接口对同 UID 可写。未提升既有正式门禁。 [目标退出](TARGET_EXIT_VERIFICATION.md) |
| 兼容性 | 正式原生参考未认证，headed 跨镜像结论 0，headless 正式矩阵 0/8。 [剩余条件](REMAINING_COMPATIBILITY.md) |
| 自动化 | 288 项，283 PASS、5 SKIP、0 FAIL。一共 10 项新测试通过。 [回归](AUTOMATED_TESTS.md) |

基线为 `475c0a7243737d6a8eb0cb9783c83cee2ab8bb6e`。仅增加 scoped SDB 入口、支持模块、测试和文档。既有 Finding、Expected Test、正式 Runtime 与静态 ABI/Linking 分类不变。原始记录、冻结件副本、设备身份及日志保留在本地 `.local-backups/phase8j/`。
