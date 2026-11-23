# SDK 与 Runtime 准入

## 本机只读盘点

| 项目 | 现场核对 |
|---|---|
| GCC / G++ | 已有 Ubuntu 13.3.0，`-dumpmachine` 仅为 `x86_64-linux-gnu`。 |
| ARMv7 GCC / Clang | PATH 未找到普通 Clang/Clang++ 或常见 GNU EABI、EABIhf、Tizen ARM 交叉编译器。workspace 和 Tizen Studio 的 `tools/`、`platforms/` 定向搜索也未找到本次匹配的 ARMv7 编译器和 sysroot。 |
| Tizen Studio | 观察到 6.0、6.5、7.0、8.0、9.0 的平台目录。没有本次两组 SR 构建方提供的 SDK/Rootstrap、文件身份和运行时匹配声明。 |
| 目标与传输 | 主机有 SDB x86-64 客户端和 GBS 脚本。未执行探测、连接或部署。PATH 未发现 QEMU ARM、Podman、Docker，当前没有配置且明确获授权的目标 adapter。 |
| 类型布局 | PATH 无 `abidiff`，未配置对应可选集成环境。 |

可用以下只读命令复核工具发现。 `STUDIO` 指向本机 Studio 安装。

```bash
gcc -dumpmachine
g++ -dumpmachine
for tool in clang clang++ arm-linux-gnueabi-gcc arm-linux-gnueabihf-gcc \
  arm-tizen-linux-gnueabi-gcc qemu-arm qemu-system-arm podman docker sdb gbs abidiff
do
  command -v "$tool" || true
done
find "$STUDIO/platforms" "$STUDIO/tools" -maxdepth 7 \
  \( -name 'arm*-gcc' -o -name 'arm*-g++' -o -name clang -o -iname '*rootstrap*' -o -name sysroot \) -print
```

## 下一阶段每侧应满足的条件

1. 提供 SR VD 与 SR LLVM 各自的 SDK 或 Rootstrap、编译器路径和 SHA256、准确 Profile/target triple、发布构建 ID、SDK 原始记录及与同侧镜像的绑定。显式填写编译器 → SDK → 原生参考 → 来源映射。普通主机 GCC 和旧 Studio 平台没有获得本次 SDK 信用。
2. 用可信无害的 C/C++ probe 记录实际完整 argv、编译器版本/hash、include 搜索和 link 搜索范围。核对目标 ET_REL、ELF class/endianness、ARM EABI/PCS、ISA 所需条件，并核对真实 loader/libc。现场 libc 样本为 ARM EABI5、Base PCS，这个观察不代替 SDK 证明。SDK 的真实 `crt`、头文件、链接脚本和 runtime 依赖均需要对应身份。
3. 指定匹配 SR 快照的可丢弃设备或完整隔离 guest，提供其镜像摘要、CPU/hwcaps、网络和文件写入边界、目标身份与用户授权。事先确认 adapter、传输、时限、回执、清理和最小权限。SDB 客户端的存在没有提供目标授权。
4. 先在各自原生参考验证并冻结 C/C++ 产物 SHA256，再对四象限运行同一产物。补齐预期测试 ID、编译、链接、部署、执行和行为证据。运行时 Linking 采样需绑定实际解释器、搜索环境、缓存、进程凭据、`AT_SECURE`、Namespace 和启动加载顺序。涉及 dlopen 的场景另外记录调用及实际对象。
5. 缺原生参考、匹配工具链、权限或回执时保留 UNKNOWN。不在宿主直接执行镜像 ELF。完整配置入口和证据格式见 [SDK 和执行协议](../../../.agents/skills/tizen-image-compatibility/references/execution.md) 与 [ARM 控制规则](../../../.agents/skills/tizen-image-compatibility/references/correctness.md)。
