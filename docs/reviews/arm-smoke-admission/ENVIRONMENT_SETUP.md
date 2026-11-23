# 临时 ARM 测试环境搭建

**BLOCKED。** 我们在基线 `97fa3e30e63831cd8cdc0279670f4a568da3c476` 上实际运行了 setup。冻结输入检查通过，系统原生 `sudo -n -- /usr/bin/true` 需要密码。setup 退出 3，状态保存在 workspace。本机没有新增系统账号、组、单元、cgroup 或正式投影目录。

创建前快照来自本机命令。主机是 x86-64，系统管理器为 systemd 255，cgroup v2 提供 CPU、内存和 pids 控制器。当前身份是非 root 工作账号。候选用户和组不存在。候选 Slice 只有 systemd 的未启动占位，Fragment、Drop-in、ControlGroup 均为空。候选 Service 均不存在。获准 ext4 卷在快照时可用 32,749,264,896 B（约 30.5 GiB），可用 inode 93,364,226，进程可见 20 个逻辑 CPU。完整主机身份和路径仅留本地。

setup 逐项在 workspace 写入只读输入身份与资源登记，随后才申请最少的提权命令。原始 SDK、镜像、冻结输入和 Phase 8G 投影保留。服务由 systemd 私有挂载命名空间把新的 root 所有投影只读绑定到私有 tmpfs 里的路径，专用账号无需进入工作账号的 home。实际专用账号还必须核对 UID/GID、组、nologin 和 sudo 拒绝策略。 [系统挂载选项](https://www.freedesktop.org/software/systemd/man/255/systemd.exec.html) · [setup](../../../.agents/skills/tizen-image-compatibility/scripts/arm_smoke_admission/setup.sh)

## 从本机原生终端续接

在仓库根目录以原工作账号运行以下命令。密码输入只交给本机 sudo 提示。

```bash
sudo -v
.agents/skills/tizen-image-compatibility/scripts/arm_smoke_admission/setup.sh --resume
.agents/skills/tizen-image-compatibility/scripts/arm_smoke_admission/cleanup.sh --dry-run
```

当前登记没有部分创建对象，允许这一续接。脚本以自身非 root 身份启动，仅对限定操作使用 `sudo -n`。若 sudo 凭据仍不可用或策略限制某个命令，脚本停止并保留责任边界。如果登记存在部分系统资源，则先走身份受控的撤销流程，已出现但未确证归属的对象需要管理员独立核对。 [撤销流程](ROLLBACK_VALIDATION.md)

本地位置 `.local-backups/arm-smoke-admission/`。初始快照 `pre_setup_snapshot.json` SHA256 为 `1f7f7bf845404c957d2e1c4f8e6f69f4c07fc04ad2a7d0efd2f1ff565071a5ab`。当前 `resource-manifest.json` 为随续接更新的登记。原始日志、快照、登记和编译验证产物均留在本地。
