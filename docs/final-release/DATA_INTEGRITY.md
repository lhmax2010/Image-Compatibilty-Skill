# 数据完整性

真实历史源 `phase5-report-enhancement-final-924ef9f` 的输入身份保存在每次回执。全量侧车重建和独立脚本逐字段对账 **898342** 条原 Finding，含 **855522** 条 Linking、**11111** 条 Unassigned、**2106110** 条原角色和 **722 / 736** 个包。`COMPATIBLE 25726 / IDENTICAL 311 / INCOMPATIBLE 12195 / UNKNOWN 860110` 原状态分布保持一致。

新旧发布侧车的 SQLite SHA256 均为 `50d437f34d2aaf3d2d318e0ed8e0a565cc7afb40af8dfd3c0c3be5adede67098`。保留 183290 个影响组、984285 个成员引用和 824606 个包角色深链。真实输入的 853881 条潜在影响、44461 条未评估、0 条确认影响不变。

构建先核对源文件内容摘要和版本，再核对覆盖索引和引用，最后原子发布 SQLite 和完成清单。新版按引用键顺序检查外键。独立验收另执行完整 SQLite `foreign_key_check`。实际 HTTP 请求验证旧 Finding 回查、供检查的 Evidence 哈希、分页互斥、穿越 403 和 SQLite 下载 404。

工作区的 `.local-backups/final-development/real-impact/run.json` 和 `gate4-http.json` 提供构建与独立验证回执。历史和合成报告各自记录真数据范围和校验结果。
