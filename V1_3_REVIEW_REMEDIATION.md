# PR #2 独立审查整改

审查基线：`0f2698eb5c8b5604e1730811b16127133339d20d`；交付分支 `review/tizen-compatibility-report-v1.3`。代码整改完成后，PM 已授权以 `fix: address v1.3 report review findings` 提交并正常推送到 Draft PR #2，等待第二轮独立审查。未合并。全部检测器、原始 Finding ID/载荷与证据未修改。

## 独立复现方法

先用现有 fixture 对四个问题建立失败复现，保留工作目录中的 before-tests.log。之后把最终六项回归文件放入 `git archive HEAD` 导出的独立目录，对未经修改的审查 HEAD 重跑，得到 [before-final-tests.log](reports/review/v1.3-remediation/before-final-tests.log)：6 项方法，9 个失败（包括路径 subTest）、3 个错误（新增角色字段/分类函数在旧实现缺失）。尺寸正反例实际返回旧 SIZE_CHANGED；未从旧错误日志推断新逻辑已经存在。随后在当前修改代码上跑完整测试。

## Major 1：Symbol Size 分类 — 代码关闭，真实迁移待授权

复现：相同 FUNC 的 size 4→8 在旧实现被标成 SIZE_CHANGED，与 OBJECT/TLS 不区分。根因是 compare_symbols 对所有类型使用同一 size 差异标签。

`report_symbols.py` 新增 size_difference：FUNC/IFUNC 类型一致→CODE_SIZE_CHANGED；OBJECT/TLS 类型一致→DATA_SIZE_CHANGED；未知类型或两侧类型不同→SIZE_CHANGED_UNKNOWN。每条保留原属性、版本、Finding IDs、证据及原始状态。类型/size/binding/visibility/version 多属性变化仍分别输出；changed 仍是旧的全部变化符号数，新增 code_size_changes/data_size_changes/unknown_size_changes/potential_abi_attribute_changes，按符号计数后聚合至 ELF 和包。代码大小与潜在 ABI 属性可以在同一符号上重叠，不能相加当成独立符号总量。

测试覆盖：FUNC size 变化 UNKNOWN、IFUNC、OBJECT size 原 ABI Finding INCOMPATIBLE、TLS、NOTYPE、缺类型/跨类型，以及同一符号代码大小+binding+visibility 同时改变。断言原始 size、V1 version、Finding ID、证据、状态、ELF/Package 汇总；原 payload 的验证由 build 内置 JSON/CSV 一致性检查同时执行。旧报告测试的分类断言改为 CODE_SIZE_CHANGED，没有删除测试。

对真实旧索引使用 SQLite mode=ro 逐条读取全部 133702 条 SIZE_CHANGED，调用同一分类函数：**133638 CODE_SIZE_CHANGED（FUNC/FUNC，原 UNKNOWN），64 DATA_SIZE_CHANGED（OBJECT/OBJECT，原 INCOMPATIBLE），0 SIZE_CHANGED_UNKNOWN，0 删除**。只读分类耗时 12.935 秒，详见 [real-size-audit.json](reports/review/v1.3-remediation/real-size-audit.json)。这是分类审计，未声称旧报告已更新。

## Major 2：受影响与关联 Package — 代码关闭，真实迁移待授权

复现：一个 Finding 的 baseline consumer/root 共用 package identity `same`，candidate provider 也叫 `same`；旧 affected_package_count=2，但不能解释哪个角色受影响。根因是 group_package_counts 只计算三角色并集。

`report_groups.py` 新增 associated_package_count、affected_consumer_package_count、affected_root_package_count、provider_package_count 及各自 observed_*。按 `(image, package identity)` 去重，原 roles 表与 Finding 关联不变。同包多角色保留，角色数不相加。完整 ownership 不足时完整计数 UNKNOWN，已观察数单列。旧 affected_package_count/observed_affected_package_count 保留并集值，新增定义字段明确其历史含义和废弃状态。

测试同名跨 Image 身份、同包多角色、UNKNOWN ownership；断言 observed/complete 分离、原三条 roles 不变、新 CSV 四列值与 JSON 一致。HTML 分别显示 Associated packages (union)、Consumer packages、Root packages、Provider packages。完整 CSV 由既有统一导出逻辑输出全部字段。

## Minor 1：证据路径校验 — 关闭

复现：`evidence/escape` 符号链接指向报告根目录内、evidence 子树外的 outside.txt，旧 Store.evidence_exists 返回 true，但 HTTP 服务拒绝。根因是两处目录边界不同。

`report_io.py` 新增共享 evidence_path，要求 evidence/ 前缀、resolve 后同时位于 source 与 evidence 子树；Store 与 HTTP handler 共用。Store 对非法路径记为 MISSING_OR_UNSAFE_REFERENCE，HTTP 返回拒绝，原证据引用字符串保留。测试安全文件 positive、`evidence/../outside.txt`、越界 symlink、非 evidence 前缀 negatives；原 HTTP 路径穿越/POST 安全回归继续通过。

## Minor 2：Consumer Path NULL — 关闭

复现：同组 NULL 路径加一个有效路径时，SQL `sum(consumer_path NOT LIKE '/%')` 忽略 NULL，让完整计数错误得到数值；空路径仍可能进入 observed distinct。根因是只判前缀且依赖 SQL 三值逻辑。

`report_groups.py` 用 valid_consumer_path 与已知 Image 校验，SQL CASE 只对规范绝对文件路径计 observed distinct；无效项计入 direct_consumer_not_recorded_count/root_consumer_not_recorded_count，完整计数 UNKNOWN。原路径和载荷不改。NULL、空、相对路径、根目录、双斜线、路径穿越、NUL 都有负例，同组 `/bin/app` 有正例；检查所有 Finding 行保留。它验证记录路径规范，不证明目标执行。

## 交付范围

生产报告层：report_symbols.py、report_groups.py、report_io.py、report_store.py、report_browser.py；展示 enhanced-report.js；测试 test_report_enhancement.py、新增 test_report_review.py；契约 references/report_schema.md；三份本轮整改文档和小型 `reports/review/v1.3-remediation/` 证据。

完整结果见 [V1_3_REVIEW_REGRESSION.md](V1_3_REVIEW_REGRESSION.md)。未重跑真实 Static，未重建 6 GiB 报告；更新原因、预估成本和待授权范围见 [V1_3_REVIEW_REMAINING_RISKS.md](V1_3_REVIEW_REMAINING_RISKS.md)。
