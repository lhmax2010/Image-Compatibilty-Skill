# 可撤销设计和撤销验证

本轮实际运行 `cleanup.sh --dry-run`，退出 0，列出的专用账号、组、独立 Slice、Service 和输入目录均为空。dry-run 日志 SHA256 为 `1ac33df57f54e4dfc2626347cc695dde69f044a44c15c1e32e82faed0a7e024c`。没有创建外部资源，未执行 `--apply`。完整真实撤销仍为 **NOT_VERIFIED**。

撤销脚本默认只检查并打印。真实撤销只能由用户明确执行，或单独授权后执行。使用前先检查资源登记和 dry-run 输出。

```bash
.agents/skills/tizen-image-compatibility/scripts/arm_smoke_admission/cleanup.sh --dry-run
# 仅在明确授权撤销后
.agents/skills/tizen-image-compatibility/scripts/arm_smoke_admission/cleanup.sh --apply
```

身份检查覆盖主机和 workspace、账号及组、创建标记、瞬态服务 InvocationID、cgroup inode、受控目录与文件 inode/所有权/摘要。实际操作先停止登记的测试服务，独立观察 Slice 为空及 UID 无活进程，最后停止锚服务和 Slice。文件按固定登记逐个删除，目录使用 `rmdir`，快照、资源登记、证据以及历史研发资产保留。

部分失败时先检查 `pending`。可证对应对象不存在时，dry-run 会报告可撤销的已登记资源。发现未归属对象、目录替换、符号链接、挂载、身份偏差或剩余进程时停止。保留准确中间态供管理员审查，不按名称猜测。成功撤销后，如需新建，先由操作者把已清理的本地状态目录归档到另一个未占用的 workspace 路径，再用无 `--resume` 的 setup 开新登记。 [撤销脚本](../../../.agents/skills/tizen-image-compatibility/scripts/arm_smoke_admission/cleanup.sh) · [测试](../../../.agents/skills/tizen-image-compatibility/tests/test_arm_smoke_admission.py)
