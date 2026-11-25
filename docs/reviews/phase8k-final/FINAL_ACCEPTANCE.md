# Phase 8K Final 验收

**限定范围的 Skill 收尾可结束。** 两项代码问题已关闭。精确绑定与预期测试对账完成了自动化、历史证据和最小实机验证。现有 LLVM headed 功能验收保持 CONDITIONAL PASS，双镜像正式兼容性为 UNKNOWN。

| 项目 | 最终结果 |
| --- | --- |
| 精确绑定 | 原始 `version-present` 产物实机 1/1，准确核对 Consumer、Provider、符号、版本及摘要 |
| 完整预期计划 | 历史 32 个预期槽位，31 个最终观测、1 个 SKIP，44 次尝试的失败与重试完整保留 |
| 旧失败 | 私有 DSO dlopen 保留 BEHAVIOR_MISMATCH，标记目标 Loader 策略阻断 |
| Chromium | 实际浏览器通过，三个页面、详情展开、缺失项、错误转义、Scope 和本地资源边界均已检查 |
| SQLite | NOT VERIFIED，既有真实构建仍执行，等待可验收产物 |
| LLVM 参考冻结 | 原始字节、SDK、构建记录、清单、回执、加载和观测清理证据均已冻结并重放 |
| 回归 | 307 项，302 PASS、5 SKIP、0 FAIL |
| VD 切换准入 | 等待匹配 VD headed 镜像、SDK、授权环境和独立可信目标监督 |

全量回归使用 `python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v`，测试临时目录为工作区内的私有 tmpfs。11 项新增测试。五项原可选 Clang/ARM/libabigail 测试维持原工具门槛。峰值 103,788 KiB，当前完整 unittest 用时 28.199 秒。目标新尝试独立复核未遗留临时资源，正式 headless 矩阵仍为 0/8。用户镜像、运行库和原始材料保持原样。

- [动态绑定](BINDING_CONTRACT_VALIDATION.md)
- [预期测试与回执](EXPECTED_TEST_RECONCILIATION.md)
- [报告与 SQLite](REPORT_AND_SQLITE_ACCEPTANCE.md)
- [冻结参考](LLVM_REFERENCE_FREEZE.md)
- [VD 验证模板](VD_VALIDATION_PLAN.md)
- [剩余限制](REMAINING_GAPS.md)
