# 镜像身份核验

**PARTIAL_IDENTITY_MATCH。** 设备的 `/etc/os-release` 和 `/etc/tizen-release` 同时自报 `tizen-unified-toolchain_20261120.082536_tizen-headed-armv7l`。冻结 LLVM 参考归档和本地已提取根文件系统均指向同一构建的 `tizen-headless-armv7l`。VD 冻结参考则是 `tizen-unified-dev_20261119.012448_tizen-headless-armv7l`。当前设备的 Variant 与两份参考均不同。 [冻结身份及归档摘要](../phase8e/ARTIFACT_MANIFEST.json)

| 证明层 | 证据 |
| --- | --- |
| 发布声明 | 两个系统发布文件相同，观察到 LLVM 同构建的 headed 变体。 |
| 已选文件身份 | 远端解析到真实路径后运行 `sha256sum`。5 个关键文件均与本地冻结 LLVM headless 文件逐字节摘要相符，逐项与 VD 不同。 |
| RPM 安装事实 | 只读选包查询返回 `glibc 2.40-1.8`、`libgcc 14.2.0-1.7`、`libstdc++ 14.2.0-1.7`、`tizen-release 11.0.0-0`、`filesystem 3.1-1.1`，均为 `armv7l`。 |
| 完整快照身份 | 未建立。已安装系统的完整归档身份仍无法由上述几份文件证实，且发布变体明确不同。 |
| 运行时绑定 | 尚未观测冻结程序实际加载的解释器、Provider 或符号版本。 |

对账时对本地 VD、LLVM 两侧 Rootfs 也重新解析并计算五个文件的 SHA256。原始发行与 Provider 证据、对账 JSON 和哈希在 `.local-backups/real-sr-runtime/`。附件中的 VD Loader 摘要缺一位，以冻结历史与本地实物的完整值 `0b1fe895ab844a3dfb04a2ab034a6fca9aeadb570abd49b36bf4be16a676f4df` 为准。 [Provider 对账](LOADER_BINDING_EVIDENCE.md) · [既有完整 VD Loader 摘要](../phase8h/QEMU_SMOKE_RESULTS.md)
