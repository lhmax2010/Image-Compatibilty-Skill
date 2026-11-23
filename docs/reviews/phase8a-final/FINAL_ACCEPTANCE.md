# Phase 8A 最终代码验收

两项 P1 代码遗留项关闭。Phase 8A 的真实验证仍为 **CONDITIONAL PASS**。原始 SR 结论依然为 INCOMPATIBLE，完整真实 SQLite、SDK 和目标 Runtime 验证仍待证据。

- [采集执行完整性](COLLECTOR_EXECUTION_REVIEW.md)。必需回执缺项无法得到整体 COMPLETE。真实故障退出 3 的兼容范围保持生效。
- [DWARF Finding ID](FINDING_ID_STABILITY.md)。临时宿主路径退出逻辑身份。相同证据跨不同目录生成同一 ID。History 对有足够证据的迁移记录保持同一观察。
- [真实 SR 复验](SR_REVALIDATION.md)。903,383 条 Finding 的状态分布未变。单独核对 7 条 DWARF ID 迁移与相关包、接口和消费者引用。
- [未完成项](REMAINING_GAPS.md)。磁盘预检继续阻断全量 SQLite。真实 SDK、运行行为与完整动态链接仍缺源证据。

基线是 `8f3dc4493c0e811974b698741f506fe8a74cc5cf`。修改范围为 `collect.py`、`core.py`、`report.py`、`debuginfo.py`、`history.py`、新增的定向测试和本目录验收说明。ABI/API/Linking 检测规则保持本轮基线。 [回归测试源码](../../../.agents/skills/tizen-image-compatibility/tests/test_phase8a_final.py)

```bash
python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v
git diff --check
```

全量共 **245 项，240 PASS、5 SKIP、0 FAIL**，耗时 104.435 秒。新增的 8 项回归全部通过。5 项可选跳过与 Phase 8A 一致，原因分别为未配置真实 libabigail、未配置 Clang AST/ARM、缺成对的 GCC/Clang 工具、缺 Clang ARMv6/v7/VFP 和缺 ARM PCS 的 Clang 编译测试。现场临时文件与 RPM 临时目录留在 workspace。 [基线跳过清单](../phase8a/REGRESSION_SUMMARY.md)
