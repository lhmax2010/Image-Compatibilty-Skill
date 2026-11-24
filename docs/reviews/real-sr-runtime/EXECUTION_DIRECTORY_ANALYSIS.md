# 非特权执行目录

**VERIFIED。** 在当前非 root 测试身份自己的缓存目录内，使用唯一的 `mktemp -d` 子目录作为执行位置。候选目录、所有者、实际挂载和原始测试命令保存在本地。仅创建本次私有子目录，目录和探针权限均为 `0700`。

| 候选 | 只读检查与处置 |
| --- | --- |
| 系统根、模块和 HAL | 允许执行的只读文件系统，本轮未作为测试位置。 |
| `/tmp`、`/run` 下用户运行目录 | 当前身份可写，其所在挂载有 `noexec`。 |
| `/opt`、`/var/tmp` 解析位置及候选管理目录 | `/opt` 是读写 ext4 并允许执行；检查过的管理目录对当前身份不可写。 |
| 当前账号的缓存目录 | 位于 `/opt/usr` 对应的读写 F2FS 挂载，无 `noexec`，当前账号所有，且通过写入和遍历检查。 |
| 当前账号的共享和媒体目录 | 权限检查显示另有可写候选，本轮使用账号缓存下的私有子目录。 |
| 开发沙箱 | 检测到包管理和应用启动器，未验证已有专用测试 App 或可供本轮使用的已授权应用沙箱。执行走现有 SDB 及用户级 scope。 |

在该私有目录内，先复制设备只读系统里的 `true` 可执行文件。核对 ELF magic 与源和副本的 SHA256，以设备当前非 root 身份直接执行，退出 0。文件和目录随后删除，另一个 SDB 调用复核路径不存在。四个冻结产物后来也分别在同一缓存目录下的独立私有子目录直接执行。无需管理员新增目录、权限或挂载配置。 [SDB 工具](https://samsungtizenos.com/docs/sdk-tools/dotnet/vscode/baseline-sdk/common-tools/smart-development-bridge) · [退出和删除复核](TARGET_SUPERVISOR_ADMISSION.md)

本地定向盘点日志 `directory-probe.stdout` SHA256 为 `fc68e1f5466d7243dd5e9669f676bf5ebff65d8079fca95e0fb489ea6ab7770e`。直接执行控制结果 `directory-exec-proof.stdout` SHA256 为 `b04cc3859fc4b2cac206c8e79e9003bd8b7c60b1cca2fb4698ac3ac8d6f4b46f`。
