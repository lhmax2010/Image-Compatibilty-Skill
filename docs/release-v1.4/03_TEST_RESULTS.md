# 自动化与端到端验证

基线 `f72a246fbce64b6e9ee2341464cbc067b5981c37` 在实现前完成 193 项测试，188 通过、5 跳过、0 失败，unittest 51.438 秒。最终代码完成 210 项测试，205 通过、5 跳过、0 失败，unittest 220.609 秒，`time -v` 记录的峰值 RSS 为 104376 KiB。新增 17 项影响分析回归，包含 v1.3 空导航导出的 `no_records` 正反用例。最终套件与历史报告只读 I/O 并行，测试耗时仅作本次运行记录。

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s .agents/skills/tizen-image-compatibility/tests -v
node --check .agents/skills/tizen-image-compatibility/assets/impact-report.js
git diff --check
```

验证时为上述命令设置了 workspace 内的 `TMPDIR`、XDG 临时目录和指向该目录的 RPM `_tmppath`。基线、最终全量和定向日志分别为 `.local-backups/v14-rc/baseline.log`、`.local-backups/v14-rc/reconcile-final-tests.log` 与 `.local-backups/v14-rc/reconcile-sequential-tests.log`。

| 范围 | 测试证据 |
|---|---|
| 真静态破坏 | 缺库、缺强符号和版本节点缺失在合成 ELF 元数据下走正常解析器，原 INCOMPATIBLE 与确认 DIRECT 都成立 |
| 正常与不确定 | 同 root SONAME 复用保持满足原契约。多个 Provider、缺 dynsym、baseline setuid/候选普通、原 baseline 已失败和 candidate-native 不获得迁移确认 |
| 历史语义 | 无基线绑定时确认数为零，INFERRED 与 UNKNOWN 分开。原状态与各计数仍可核对 |
| 稳定 ID 与角色 | 乱序输入 root 列表得到相同侧车内容 SHA256。一条 Finding 可由多个组引用，重复键、悬空引用被拒绝，包的确认只与直接消费者角色相关 |
| Phase 7A 与历史回归 | 已有全部 193 项继续运行，包含全部五项修复的回归。checkpoint 开/关的实际 resolver 记录逐字段相等 |
| 异常与输入安全 | 损坏库、错误 schema、源变化、CSV 原状态变化、重复构建、部分写入、中断、压缩超限、过长请求、缺失 Evidence、越界路径均有测试 |
| 可用性 | 合成演示执行正式 CLI，检查 /impact、列表、第二页、客户端脚本、原 Finding 回跳、证据 200/403 和 SQLite 禁止下载。核查覆盖索引实际被采用 |

最终全量测试的 5 个 SKIP 与基线一致。`test_real_abidiff_embedded_and_split_layout_break` 缺显式 libabigail。`test_real_clang_ast_and_arm`、`test_real_arm_v6_v7_and_vfp_fixtures`、`test_real_hard_softfp_and_soft_pcs` 缺明确的 Clang/ARM 环境，`test_explicit_probes_exact_matrix_ids_with_simulated_receipts` 缺实际 GCC 及 Clang 探针组合。未把 SKIP 计为通过。

合成演示创建了 37 条原 Finding、44 个组、49 个组内引用。4 条静态直接影响确认，6 条已对照未见破坏，16 条潜在影响，11 条未评估。20 条/页的真实本机 HTTP 查询完成了正反向关联检查。该数据是合成元数据模型，并未运行 ARM/Tizen ELF。测试运行中的本机 HTTP/HTML 访问有证据，Chromium 交互不列为本次实测。

另外以 GCC 构建两侧 x86_64 ELF 和一个引用 `api` 的可执行文件。在候选库移除该导出，经真实 `readelf` 采集、对照解析、原报告生成和侧车查询，Finding `TC-3e98bbe29b0d38e5` 得到 `INCOMPATIBLE / missing_symbol` 和 `CONFIRMED_CONTRACT_IMPACT`。该验收未执行生成的 ELF，包为明确标注的合成归属。回执在 `.local-backups/v14-rc/native-fixture-reconciled/native-verification.json`。
