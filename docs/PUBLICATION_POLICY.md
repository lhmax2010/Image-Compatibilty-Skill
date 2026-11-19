# GitHub 上传与仓库迁移约定

所有文件写入仅限当前 workspace，包含临时文件、备份和日志。workspace 外的既有产物本轮不读取、复制、修改或删除；需要纳入时先取得用户特许。

当前目标是私有仓库 `git@github.com:lhmax2010/Image-Compatibilty-Skill.git`。上传统一使用普通 `git push`，不使用 PR 或强推。只推送选中的分支或标签，不使用 `git push --mirror` 上传本机内部 refs，也不默认推送全部旧分支。

## 后续上传范围

| 内容 | 处理 |
|---|---|
| `.agents/skills/tizen-image-compatibility/` 的源码、配置、Skill、说明、测试、必要的小型合成示例 | 上传；保持 Skill 可完整使用与测试复现 |
| `README.md`、`AGENTS.md`、`.gitignore`、`docs/` | 上传；保留使用方式、工作区与迁移约定 |
| 根目录 `V1_*`、审查/整改/验证文档及输入模板 | 上传；属于 PM 和独立审查材料，历史结论须保留原版本语境 |
| 已纳入 Git 的 `reports/preflight/`、`reports/review/` 小型证据 | 保留；本次共42个文件，约2 MB，不是巨型真实报告。后续新增证据逐项选择，不批量强制添加整个 reports |
| Phase 7A 生产修复及新增回归 | 随 Skill 源码和测试一起上传 |
| `.local-backups/`、字节码、虚拟环境、缓存、临时构建 | 仅本地，不上传 |
| `design.md`、`require.md` | 备份并保留本地；它们是未纳入本轮发布审查的原始输入，PM明确需要后再审核纳入 |
| 镜像、Rootfs、分区、RPM DB、副本、SDK/debuginfo、巨型JSON/CSV/SQLite报告 | 不上传；必要时只提交脱敏摘要、输入哈希与复现方法 |
| Token、账号凭据、私钥、真实 `.env` 和个人环境配置 | 不上传；忽略规则不能替代提交前检查 |

`.gitignore` 不会移除已跟踪文件，也不会清除Git历史中的内容。向新仓库推送历史前仍须核查可达历史；不能仅凭忽略规则声称历史已脱敏。当前200个已跟踪文件总量很小，没有发现镜像或巨型报告。

## 本地备份与恢复

备份位置由 `.local-backups/LATEST` 指向，包含工作树归档、逐文件SHA256、未提交patch、Git元数据归档及fetch前后的完整Git bundle。归档保留未提交源码、新增测试和未跟踪需求输入，不需要备份可再生成的Python字节码。

工作树归档逐文件核对；bundle通过 `git bundle verify`。bundle只含Git对象，不包含未提交修改；恢复时必须同时保留工作树归档及状态清单。备份中的Git元数据可能含本机信息，永不上传。

同一磁盘内备份可应对旧GitHub仓库清理和误改，不能应对本机磁盘损坏。用户限定写入范围后，不擅自复制到其他磁盘或服务。

每次上传前核对目标分支、选中文件和可达历史。首次迁移以新仓库的 `main` 作为默认入口，其他历史分支保留在本地备份。
