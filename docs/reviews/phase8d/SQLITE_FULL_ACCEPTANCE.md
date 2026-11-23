# SR SQLite 全量验收 — NOT VERIFIED

本轮使用既有 Phase 8C 报告做只读预检。要求的基准记录为 903,377 条 Finding，其中 INCOMPATIBLE 11,490，Linking UNKNOWN 860,294，VD/LLVM 安装包 719/736。历史报告和上轮失败导入均保留。 [源报告对账](../phase8c/COVERAGE_BEFORE_AFTER.md) · [上轮停止记录](../phase8c/SQLITE_ACCEPTANCE.md)

| 输入方案 | 新建前最低可用空间（B） |
| --- | ---: |
| 直接使用同阶段未压缩的 Phase 8C 报告，五个必需文件共 5,521,133,297 B | 13,189,750,242 |
| 使用最后一次 Phase 8C gzip 原始输出，先在授权卷物化五个必需文件，共 5,521,144,235 B | 物化后仍需 13,189,772,118 |
| 最新 gzip 输出的物化与建库均写在同一卷 | 18,710,916,353，另计复制其余资料时的额外空间 |
| 本轮唯一获准卷启动时 | 8,407,785,472 |
| SDK 验证后测量 | 5,211,840,512 |

计算沿用增强构建器的 `2 × 索引输入字节 + 1 GiB` 工作预算和额外 `1 GiB` 空闲余量。最终报告的 gzip 输入长度来自各单流文件的 ISIZE（每个文件均小于 4 GiB）。最接近可行的未压缩输入方案在本轮启动时仍短缺 4,781,964,770 B，且同一共享卷曾在实际导入中跌破动态门槛。本轮没有启动 SQLite 构建，因而没有当轮墙钟时间、峰值内存、SQLite 大小或成功的 run.json/validation.json。上一轮的部分索引仅供失败诊断。 [资源保护源码](../../../.agents/skills/tizen-image-compatibility/scripts/compat/report_io.py) · [构建器](../../../.agents/skills/tizen-image-compatibility/scripts/compat/report_enhance.py)

获准使用稳定卷后，在新目录重新构建。可从当轮解压报告启动，或先把最终 gzip 报告物化到新输入目录，核对压缩前后的字节和源 Evidence，然后执行：

```bash
python3 .agents/skills/tizen-image-compatibility/scripts/enhance_report.py build \
  --input "$VERIFIED_RAW_REPORT" --output "$NEW_INDEX_DIR"
```

验收必须同时匹配 run.json 和 validation.json 的 PASS。独立逐行比对 Finding ID、状态、原始载荷和哈希，检查 Package/Consumer/Provider、Linking Group 成员和无悬空边。以只读 SQLite 执行 integrity_check 及逻辑关联检查，核对每个 Evidence 的内容哈希，并在 loopback 查询 API 验证分页、排序、搜索和去重。记录输入前后 SHA256、墙钟、峰值 RSS 和输出实际分配空间。现有合成测试覆盖这些路径中的工具行为，未给真实数据记完成。
