# SQLite 空间计量与稳定性

Phase 8E 在创建索引时触发动态磁盘保护。已复现目录计量遗漏仍打开的 SQLite 临时文件。历史差额的精确归因仍为 **UNKNOWN**。 [Phase 8E 失败记录](../phase8e/SQLITE_FULL_ACCEPTANCE.md)

| Phase 8E 观测 | 字节 |
| --- | ---: |
| 外部启动探测可用 | 13,527,703,552 |
| ResourceGuard 第一条采样可用 | 13,527,691,264 |
| 建库启动门槛 | 13,189,750,242 |
| 末次采样可用 | 9,313,439,744 |
| 末次采样目录已分配 | 3,854,589,952 |
| 末次采样动态门槛 | 9,335,160,290 |
| 触发停止的缺口 | 21,720,546 |
| 以外部启动探测计算的未归因差额 | 359,673,856 |
| 以首条内部采样计算的未归因差额 | 359,661,568 |

内部日志有 83 条采样，未归因差额在 0 至 359,661,568 B 之间。两种起点差 12,288 B。末次采样的进程 CPU 时间 142.72 秒，墙钟 1,148.13 秒。历史日志没有同时间的进程打开文件、inode 归属或整卷其他写入记录，无法按来源分摊约 343 MiB。

## 计量范围

- `allocated` 对任务输出下遍历到的常规文件求 `st_blocks × 512`。可见主库、Journal、WAL、SHM 和同目录内仍有名字的中间文件会计入。输出树之外的文件、已取消链接或匿名文件、目录和文件系统元数据超出这个计量范围。符号链接到文件的目标可能被跟随，多个名字指向同一 inode 会重复计入。
- `disk_free` 是同卷 `statvfs.f_bavail × f_frsize`。同卷其他进程写入、仍持有的已删除文件和文件系统本身的分配也影响该数值。两次读取间没有原子快照。
- 动态门槛是 `max(0, disk_budget - allocated) + 1 GiB`。本构建器的 `disk_budget` 是五个输入文件字节合计的两倍加 1 GiB。采样通常间隔至少 2 秒，压缩写日志频率约 10 秒，SQLite progress callback 在构建期间触发检查。可用空间下降时保护仍有效。 [ResourceGuard](../../../.agents/skills/tizen-image-compatibility/scripts/compat/report_io.py) · [输入预算及临时目录](../../../.agents/skills/tizen-image-compatibility/scripts/compat/report_enhance.py)
- 构建器在打开 Store 前设 `SQLITE_TMPDIR` 为输出的 `tmp/`，Store 使用 `PRAGMA temp_store=FILE`。目录选择与可遍历性是两个独立属性。 [Store](../../../.agents/skills/tizen-image-compatibility/scripts/compat/report_store.py) · [SQLite 临时文件](https://sqlite.org/tempfiles.html)

## 小型受控实验

SQLite 3.45.1。输入为新建的 4,096 行随机二进制，每行 2,048 B。在独立目录设置 `SQLITE_TMPDIR`，分阶段取目录 `st_blocks`、卷 `statvfs` 和自身 `/proc/self/fd/*` 的 `st_blocks`。用 `strace -e trace=openat,unlink,unlinkat` 记录文件名生命周期。以 128 KiB 缓存执行更新，再切到 WAL 并关闭自动 checkpoint。随后用 `CREATE TEMP TABLE scratch AS SELECT * FROM objects`，同时打开一个全表 `ORDER BY payload` 游标并读第一行。查询计划包含 `USE TEMP B-TREE FOR ORDER BY`。

| 采样阶段 | 目录已分配（B） | 文件描述符补充证据 |
| --- | ---: | --- |
| DELETE journal 事务打开 | 33,779,712 | 主库 16,822,272，Journal 16,957,440，两者有目录项 |
| WAL 事务提交后 | 33,767,424 | 主库 16,822,272，WAL 16,879,616，SHM 65,536 |
| TEMP 数据库与排序游标同时打开 | 33,767,424 | 已 unlink 但仍打开的两个 `etilqs_*` 分配 16,822,272 和 8,413,184 B |
| 关闭游标后 | 33,767,424 | TEMP 文件仍为 16,822,272 B，排序文件不再持有原占用 |
| 关闭数据库连接 | 16,822,272 | 仅主库，临时描述符已清空 |

`openat`/unlink 证明这两个临时文件均由指定 `SQLITE_TMPDIR` 创建并立即解除目录链接。复现实验确认了遗漏机制，历史任务使用的匿名文件及其峰值仍未知。实验期间卷级可用容量也波动，单凭卷级计量无法分离其他卷负载和采样时序。预算、余量和 Findings 保持原样。

本地复现脚本和日志在 `.local-backups/phase8f/`。计量日志 SHA256 为 `839ed627176a2b66175209ae8a7770bb3d760da54dc4f91433e40cab502e9ac8`，原始系统调用日志 SHA256 为 `432489cba4fbd84deb2f274c575f853c667d9b2329ceeccf61cd6413470d5b0b`。

下次授权建库时可在同一采样点同时记录输出树 inode、数据库进程树的 FD 已分配块和同卷 `statvfs`，用 `(st_dev, st_ino)` 去重关联，并记录 SQLite 阶段和采样时间。使用稳定工作卷可进一步约束外部写入变动。
