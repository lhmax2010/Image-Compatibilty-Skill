# Phase 8B 独立验收

基线 `87a6ec4acacfc1575f7957eb2f23e7ae219f4804`。

**结论：定向证据验证通过，完整产品 Linking 仍未验证。** 本轮确认了真实 ARMv7 Consumer 与指定 Provider 的精确版本符号契约，以及候选对象无法满足同一契约的负例。对原盘 xattr、缓存、配置和 ELF 的核查为后续目标验收提供了事实，现有生产门控保持。

| 验收项 | 结果 |
|---|---|
| 真实 UNKNOWN 追溯 | 对全部 860,300 条 Linking UNKNOWN 流式分组，原报告 903,383 条 Finding 和既有内容哈希一致。 [原因分布](LINKING_EVIDENCE_ANALYSIS.md) |
| 真实正反例 | Getconf 与 LLVM libc 局部版本符号契约满足。真实解释器同名版本节点却不提供该符号；另外复核同 SONAME 的导出缺失与 split debug 假缺库线索。 [工具、样本及复现](REAL_SAMPLE_VALIDATION.md) |
| 现有门控与证据充分性 | 六个真实根的部分事实回放生成 2,015 条观察，全部为 UNKNOWN。原报告升级 0 条，Linking 完整覆盖保持 0 / 2,054。 [回放与候选改进](COVERAGE_BEFORE_AFTER.md) |
| 真实全量 SQLite | NOT VERIFIED，完整构建在资源预检前提处受阻。合成索引、证据与分页回归通过。 [空间和核验清单](SQLITE_ACCEPTANCE.md) |
| 下一阶段准入 | 匹配的 SDK、原生参考、目标加载上下文与授权 adapter 尚缺。 [准入清单](SDK_RUNTIME_READINESS.md) |

全量回归 **245 项，240 PASS、5 SKIP、0 FAIL**，耗时 **95.565 秒**。可选跳过原因与 Phase 8A Final 一致，涉及 libabigail、Clang AST/ARM、GCC/Clang 工具组合和 ARMv7 PCS。发布内容是六份评审文档。原始镜像、提取产物、报告及本机运行日志留在 workspace。 [原跳过记录](../phase8a/REGRESSION_SUMMARY.md)

```bash
python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v
git diff --check
```

工具正确性由全量回归和原 ID 回放验证。静态局部结论只适用于已核对的 ELF 文件事实。产品运行时绑定、Secure Execution 与 Namespace 需匹配目标证据。
