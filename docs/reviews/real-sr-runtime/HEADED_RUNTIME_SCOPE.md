# SR headed 运行范围

本轮域为 **SR_HEADED_RUNTIME**，继承基线 `ba1dedb1ca88b41e1936ed740a0a964b26ff4a22`。仅对前轮已经连接的授权目标 T1 运行。继续使用现有 SDB 通道和非 root 账号，保留基线的设备盘点。

每次探针执行前重新读取两个系统发布文件，以内部 boot ID 绑定同一次启动，并核对五个 Loader/Provider 文件的 SHA256。四次运行都绑定到 `tizen-unified-toolchain_20261120.082536_tizen-headed-armv7l` 和同一个 boot ID。公开报告省略目标地址、账号、boot ID 和临时路径。已部署文件的源是 Phase 8E 冻结的四个普通用户态产物，源 SDK 原先对应 headless 参考。保留原始 SHA256，无重新编译或链接。 [既有镜像身份](DEVICE_IDENTITY.md) · [原始冻结清单](../phase8e/ARTIFACT_MANIFEST.json)

LLVM headed 上验收了两项使用 Clang 冻结产物的原生执行观察，以及两项 GCC 冻结产物的运行观察。缺少匹配的 VD headed 原生参考，跨镜像兼容性结论为 0。原始 headless 正式四象限仍为 0/8。现有 Finding、Expected Test 和正式 Runtime Adapter 准入规则均沿用原实现。 [本次实测](HEADED_RUNTIME_RESULTS.md) · [原正式矩阵](FOUR_QUADRANT_PROGRESS.md)
