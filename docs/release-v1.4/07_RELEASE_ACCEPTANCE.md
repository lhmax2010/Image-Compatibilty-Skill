# v1.4-offline-compatibility-rc1 交付验收

本版本交付独立 SQLite 影响侧车、可复用的静态解析对照、包和原证据关联、本机分页 HTML、CLI 与 Skill 操作说明。用户可使用原 v1.3 报告获得潜在影响与未评估项，也可用同源 Phase 7A 清单检查指定根的确认影响。

**RC CONDITIONAL PASS**。离线核心功能、数据对账、安全和回归门槛通过。历史真实报告构建完成，用时 14 分 08.382 秒，超出 12 分钟设计目标。参考 SSD 上的重复端到端预算、冷查询尾延迟和 ARMv7 运行时未验证。恢复仍需使用新目录重建。

离线兼容性分析工具通过验收，不代表两套真实 Tizen 镜像已通过全面兼容性认证。

## 核心验收

| 门槛 | 结果 |
|---|---|
| 兼容性和证据 | 原 ID、原状态、旧组和 Evidence 引用保持可追溯。历史模式的低强度证据无确认资格 |
| 静态正例 | 真实采集的本机 ELF 对照捕获缺导出，Finding `TC-3e98bbe29b0d38e5` 获得确认静态影响 |
| 回归测试 | 最终 210 项，205 通过、5 跳过、0 失败，较基线新增 17 项 |
| 只读服务 | 合成和真实报告均完成分页、反查、原 Evidence 内容核对、路径越界拒绝和数据库下载拒绝 |
| 发布和恢复 | 挂载验证输入与输出摘要，未完成构建无可用 `run.json`。合成重建核对 SQLite 内容一致 |
| 真实数据 | 898342 条 Finding 逐字段对账，855522 条 Linking、11111 条 Unassigned、722/736 包保留。853881 条潜在影响，44461 条未评估，确认项为零 |
| 性能 | SQLite 466.59 MiB，峰值进程树 RSS 170.23 MiB。分组和包热查询在预算内，实际构建端到端超出目标 |

## 可复核的交付入口

- [架构与功能](01_ARCHITECTURE_AND_FEATURES.md)、[实施与完整复现命令](02_IMPLEMENTATION_SUMMARY.md)、[自动化测试](03_TEST_RESULTS.md)、[数据完整性](04_DATA_INTEGRITY.md)、[性能](05_PERFORMANCE.md)、[已知边界](06_KNOWN_LIMITATIONS.md)。
- 本地合成演示位于 `.local-backups/v14-rc/synthetic-demo/impact-reconciled/`。本机编译 ELF 正例位于 `.local-backups/v14-rc/native-fixture-reconciled/`。这些演示使用不同于真实输入的合成或本机控制数据。
- 真实派生目录为 `.local-backups/v14-rc/real-reconciled/`。`run.json` 为已完成的构建、来源摘要和资源回执。独立验证记录为 `.local-backups/v14-rc/real-reconciled-http.json`。
- 源版本基线为 `f72a246fbce64b6e9ee2341464cbc067b5981c37`。本次 13 个交付代码、入口说明和测试文件的聚合 SHA256 为 `c8c4ff3a2c3e7f486457de2ec62c66969fa761162b6796fef02cdb6142f84990`，逐文件摘要见 `.local-backups/v14-rc/source-identity.json`。这个身份在基线上绑定本次改动，验收文档另列。历史报告保存在原处，新派生报告写入 workspace 的忽略目录。

## 修改文件清单

以下路径以仓库根为准。除下列代码和本目录七份交付文档，`docs/phase7b/` 的七份未跟踪设计文档在开发前就存在，并予以保留。

| 操作 | 文件 |
|---|---|
| 修改 | `README.md` |
| 修改 | `.agents/skills/tizen-image-compatibility/SKILL.md` |
| 修改 | `.agents/skills/tizen-image-compatibility/scripts/compat/linker.py` |
| 修改 | `.agents/skills/tizen-image-compatibility/scripts/compat/report_browser.py` |
| 修改 | `.agents/skills/tizen-image-compatibility/scripts/enhance_report.py` |
| 新增 | `.agents/skills/tizen-image-compatibility/scripts/compat/impact_source.py` |
| 新增 | `.agents/skills/tizen-image-compatibility/scripts/compat/impact_replay.py` |
| 新增 | `.agents/skills/tizen-image-compatibility/scripts/compat/impact_store.py` |
| 新增 | `.agents/skills/tizen-image-compatibility/scripts/compat/impact_browser.py` |
| 新增 | `.agents/skills/tizen-image-compatibility/scripts/impact_report.py` |
| 新增 | `.agents/skills/tizen-image-compatibility/assets/impact-report.html` |
| 新增 | `.agents/skills/tizen-image-compatibility/assets/impact-report.js` |
| 新增 | `.agents/skills/tizen-image-compatibility/tests/test_impact.py` |
| 新增 | `docs/release-v1.4/01_ARCHITECTURE_AND_FEATURES.md` 至 `07_RELEASE_ACCEPTANCE.md`，共七份 |

工作区保留上述未提交修改，暂存区为空。HEAD 与开发基线一致。操作范围为 workspace 内的代码、文档、临时目录和派生报告。
