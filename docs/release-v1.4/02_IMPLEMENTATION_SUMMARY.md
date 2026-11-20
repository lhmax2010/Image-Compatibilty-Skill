# 实现、接口与复现

| 代码 | 职责 |
|---|---|
| `scripts/impact_report.py` | `build`、`serve`、`query`、`--version`。接受增强 v1.3 输入、独立输出、可信范围配置和显式 replay roots |
| `compat/impact_source.py` | 检查 v1.3/1.2 schema、已通过对账、稳定文件、SQLite 只读快照与 CSV 结构。配置与解压读取有界 |
| `compat/impact_store.py` | 侧车 schema 1。`source_finding`、`impact_group`、`group_finding`、`association`、`package_group`、`meta`。全量引用、范围、统计、索引、失败及原子发布 |
| `compat/impact_replay.py` | 使用原 resolver 在两侧查同一 baseline 可执行根。匹配精确原 Finding、验证 baseline 满足、限定可确认的失败种类。独立保存重放依据 |
| `compat/linker.py` | 可选 checkpoint，在已有解析循环计工作量并限制重放。默认调用和决策语义保持一致 |
| `compat/impact_browser.py`、`compat/report_browser.py`、`enhance_report.py` | 验证侧车与输入摘要，参数化只读查询。可独立启动或通过原 serve 的 `--impact` 挂载，原路由保留 |
| `assets/impact-report.html`、`assets/impact-report.js` | 在 `/impact` 展示分页组、消费者、包、Finding、原 Evidence 和动作。DOM 使用文本节点，不下载数据库 |
| `tests/test_impact.py` | 可重建的合成源和正反例。验证确定性、双侧门控、来源对账、损坏输入、引用与中断 |

## 数据和查询

- 原 `source_finding.n` 只作紧凑引用，保留原 ID、状态、类别、payload hash 与旧导航组。`group_finding` 复合主键保存多对多，反向索引从 Finding 找组。
- 导航组 ID 来自规范键 `[schema,kind,old_group_id]`。未分组的 ABI/API 观察及重放检查以原 Finding ID 为锚点。重放组限定直接根；同一原 Finding 可同时属于观察、运行库提示和重放组。独立根因不因包或名称相同而合并。组 rank 表示其所含最高关联等级。
- `association` 每条记录至多一个直接检查投影，借稳定源 ID 回到消费者、root、Provider、版本、检查和原 Evidence。历史关系为 INFERRED，未知缺口按原因显式统计，确认静态影响或未见失败须有 DIRECT proof。候选原生检查继续按自身方向显示。
- `package_group` 按 side/package/group/role 去重。确认的包关联只引用完整归属的 baseline 直接消费者组件。保留其余角色，不更改原包状态。
- `run.json` 记录 SHA256 来源、配置摘要、引擎和 schema、投影、发布状态及资源。临时文件在新目录内，先通过引用和计数校验，再同目录重命名 SQLite，最后发布清单。失败留 `failure.json`；无有效清单的目录不可查询。重建使用另一个新输出路径。
- API 前缀 `/api/impact/`，支持 `overview`、`groups`、`group`、`members`、`consumers`、`packages`、`finding`、`finding-groups`、`package-groups`。列表最多 100 项，游标绑定投影，包查询同时指定 side/id。图展开和原始 JSON 下载均不在请求路径。

## 可重复的合成演示

在仓库根目录执行，示例输出目录初次运行时必须不存在。合成模型输入包含真正的静态缺库、缺强符号、版本节点缺失对照，也含加载复用、权限和导出不完整反例。无需下载镜像。

```bash
SKILL=.agents/skills/tizen-image-compatibility
DEMO="$PWD/reports/impact-demo"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SKILL/tests" python3 - "$DEMO" <<'PY'
from pathlib import Path
import sys
from test_impact import synthetic_report
from compat.report_io import ResourceGuard
synthetic_report(Path(sys.argv[1]), ResourceGuard)
PY
python3 "$SKILL/scripts/impact_report.py" build \
  --input "$DEMO/indexed" --output "$DEMO/impact" \
  --replay-root /bin/missing --replay-root /bin/versions \
  --replay-root /bin/symbol --replay-root /bin/alias
python3 "$SKILL/scripts/impact_report.py" query \
  --report "$DEMO/indexed" --impact "$DEMO/impact" groups --param rank=2
python3 "$SKILL/scripts/impact_report.py" serve \
  --report "$DEMO/indexed" --impact "$DEMO/impact"
```

用已经验证的真实 v1.3 目录替换 `--input` 并去掉 replay 参数，即可做历史关联。`--report` 指向同一个增强目录。需要构建原始增强目录时先运行现有 `enhance_report.py build` 命令。示例仅执行报告分析。
