# 实现清单与内部 Gate

| Gate | 交付内容 | 核对证据 |
|---|---|---|
| 0 | 保留基线 `f72a246fbce64b6e9ee2341464cbc067b5981c37` 与已有 v1.4 工作区 | 验证备份 `gate0-worktree.tar.gz` 逐文件 SHA256。基线 210 项，205 PASS、5 SKIP、0 FAIL |
| 1 | ARM 静态拓展、D-Bus 文档完整性、库和系统接口清单 | [静态 ABI](STATIC_ABI_VALIDATION.md) |
| 2 | 分阶段编译与链接、产物和伴随库证据、隔离适配器、重复执行与能力跳过 | [SDK 与 Runtime](SDK_RUNTIME_VALIDATION.md) |
| 3 | 原作用域保守匹配、历史风险、状态和证据对照、CI | [回归验证](REGRESSION_VALIDATION.md) |
| 4 | 索引顺序优化、历史与运行时分页视图、真实数据验证 | [数据完整性](DATA_INTEGRITY.md) · [性能](PERFORMANCE.md) |
| 5 | 全量回归、可复现路径和源码身份 | [最终验收](FINAL_ACCEPTANCE.md) |

主要源码包括 `elf.py`、`collect.py`、`compare.py`，矩阵和执行代码在 `testing.py`、`matrix_manifest.py`、`runtime_adapter.py`，离线历史入口在 `history_report.py` 与 `compat/history.py`。`impact_store.py` 继续创建并核对原侧车 schema。报告和 probe 文件的完整清单见最终验收。
