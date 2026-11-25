# 自动化回归

Phase 8J 参考为 288 项（283 PASS、5 SKIP）。Phase 8K 新增 8 项工作流用例，覆盖外置摘要和文件表、替换与 symlink、跨路径与 PCS、授权绑定、报告 Profile/HTML、输出与历史源隔离、版本检查与绑定分离、构建归档与精确预期链接失败。原 SDB 对照继续覆盖身份和部署摘要拒绝、非法输出、观察陈旧或遗漏、超时、断链与参与进程残留。超时用例增加受控空 stdout 的采集证据。

```bash
python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v
git diff --check
```

五项可选测试保留原门槛。两项需要显式设置经认可的 libabigail / Clang 工具；另外三项分别需要可直接由对应测试调用的 GCC/Clang、Clang ARM 和真实 Clang PCS 工具。Phase 8K 单独受审的 Tizen SDK 实机工作流不用于替代这些可选宿主集成。

全量结果为 **296 项，291 PASS、5 SKIP、0 FAIL**。unittest 用时 28.301 秒，含隔离入口耗时 30.93 秒，峰值 RSS 102,612 KiB。测试临时路径使用工作区内的私有 tmpfs，宿主 RPM 数据库测试仍执行真实 rpmbuild、RPM 查询和文件对账。先前将整个宿主挂为只读的诊断运行在 RPM 虚拟安装计量中失败；最终复验保留宿主文件系统真实余量语义，全部可执行项通过。未为通过测试调整生产判定或磁盘门槛。

测试名称为 `test_probe_workflow.WorkflowTests`，SDB 边界见 `test_sdb_runtime.SdbRuntimeTests`，正式 cleanup 与原生参考见 `test_frozen_runtime`。完整输出本地保存在 `full-tests-managed.log` 和 `full-tests-managed.time`。
