# SDB Adapter 协议与调用方式

默认只验证本地计划，`--admit` 仅作设备只读准入，`--execute` 还要求独立受信来源提供以下身份钉住值、授权布尔值和该产物完整 SHA256。运行时只使用已有设备连接，每次调用显式选择同一个 SDB endpoint。配置保存在项目本地忽略目录，可信来源由设备操作者确认。

| 配置键 | 值及约束 |
| --- | --- |
| `sdb_serial` | 已授权的 IPv4:port。 |
| `scope` | headed 为 `SR_HEADED_RUNTIME`，原 headless 为 `SR_RUNTIME`。新入口在 headless 仅提供计划和只读准入。 |
| `image_family` 与 `build_id` | `llvm` 或 `vd`，及含准确 profile 的完整发布 ID。两个实际发布文件需匹配。 |
| `cpu_serial_sha256` | 已知目标的 `/proc/cpuinfo` Serial 字段去掉空白后的 SHA256，事先由设备身份记录固定。 |
| `provider_sha256` | 精确映射 `ld-linux.so.3`、`libc.so.6`、`libgcc_s.so.1`、`libstdc++.so.6`、`libm.so.6` 的可信摘要。 |
| `authorization` | 包含 JSON 布尔值 `execute` 和 `artifact_sha256` 映射。执行要求 `true` 及所选产物的匹配摘要。 |

在仓库根目录运行。每次指定新的 workspace 输出目录。以下命令默认不会连接设备。经过授权后可分别追加 `--admit` 或 `--execute`。

```bash
python3 .agents/skills/tizen-image-compatibility/scripts/sdb_runtime.py \
  --manifest docs/reviews/phase8e/ARTIFACT_MANIFEST.json \
  --bundle "$LOCAL_FROZEN_BUNDLE" --enrollment "$LOCAL_ENROLLMENT" \
  --output "$NEW_OUTPUT" --artifact llvm-A-C
```

Adapter 只接受已钉住的 Phase 8E 清单四个基础产物 ID。临时基目录取自核验后的目标账号缓存，临时目录、Attempt ID、scope、PID 及 boot ID 均按本次运行生成或观测。单次用户 scope 上限 10 秒，停止宽限 1 秒，宿主 SDB 请求各有独立期限及 640 KiB 合计捕获上限。每份远端输出与 Loader 文件的接收上限为 128 KiB，复制时再次核对大小和摘要。SDB stdout/stderr、原始字节、结构化运行记录及命令收据在输出目录保存。

退出 0 表示目标观察匹配且本次清理已验证，或所请求的计划/只读准入成功。请通过 `execution_status` 区分。退出 3 表示冻结观察不完整、执行授权拒绝或实测行为不同；退出 2 是 CLI 输入错误。报告的观察状态不改变正式 Runtime 门禁。 [退出验证规则](TARGET_EXIT_VERIFICATION.md)
