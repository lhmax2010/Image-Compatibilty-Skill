# 真实 SR 全量 SQLite 验收

**NOT VERIFIED。** 本轮只执行资源预检，未产生完整真实索引。

| 核对 | 观测值 |
|---|---:|
| 保留的 Phase 8A Final 五个输入流解压总字节 | 5,520,926,167 B |
| 依现有规则估算所需可用空间 | 13,189,335,982 B（约 12.28 GiB） |
| 测量最新输入大小时可用空间 | 772,952,064 B（约 0.72 GiB） |
| 对旧未压缩 SR 报告实际预检需求 | 13,192,235,858 B（约 12.29 GiB） |
| 旧报告预检当时可用空间 | 844,685,312 B（约 0.79 GiB） |

新报告以 gzip 保存在本机。解压大小通过流式读到 `wc -c` 计量，不占额外存储。现有公式是五个输入文件实际总字节的两倍，加 1 GiB 工作预算及 1 GiB 空闲余量。以较早的未压缩 SR 报告调用原始 CLI 实测预检，得到退出 1、`stage=preflight`、`ResourceLimit`、新增分配 0 B，验收目录没有 `report-index.sqlite`。两个历史报告均保持原样。 [空间估算与预检](../../../.agents/skills/tizen-image-compatibility/scripts/compat/report_enhance.py) · [资源守卫](../../../.agents/skills/tizen-image-compatibility/scripts/compat/report_io.py)

```bash
for name in baseline-manifest.json candidate-manifest.json results.json findings.csv packages.csv
do
  gzip -dc "$SRC/$name.gz" | wc -c
done
df -B1 .
# 以下输入是保留的未压缩历史报告。输出使用新目录。
python3 .agents/skills/tizen-image-compatibility/scripts/enhance_report.py build \
  --input "$RAW_REPORT" --output "$NEW_REPORT"
```

真实全量验收在容量足够时，以最新原始报告建库并对照以下项目。本轮这些真实索引检查保持未验证。

1. Findings 按 ID、序号、状态、维度和完整载荷散列与最新 JSON/CSV 对账，总数 903,383，Linking 860,300 条且均 UNKNOWN。
2. RPM 安装清单与 `packages` 分侧核对 719/736。以原 Finding ID 检查包、Provider、Consumer、ELF 与 group 关系和 Evidence，保留无法归属项。
3. 用 `PRAGMA quick_check`、`PRAGMA foreign_key_check` 检查索引；对未声明外键的逻辑引用执行显式缺失关联查询。比较完整 group 件数并核对分页排序、边界、去重、筛选和只读 Evidence 访问。核对源报告哈希以及 `run.json`、`validation.json` 的成功标记；记录实际耗时、RSS 和磁盘占用。

合成 SQLite、分页、载荷及 Evidence 回归随全量测试通过。 [索引校验](../../../.agents/skills/tizen-image-compatibility/scripts/compat/report_enhance.py#L68) · [分页和访问](../../../.agents/skills/tizen-image-compatibility/scripts/compat/report_browser.py) · [报告回归](../../../.agents/skills/tizen-image-compatibility/tests/test_report_enhancement.py)
