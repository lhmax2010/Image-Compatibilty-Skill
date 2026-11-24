# 仍需补齐的兼容性条件

本轮 Adapter 接受配置化 VD 或 LLVM headed 的发布 ID 和 Provider 钉住值。支持的探针为同一套 Phase 8E 原始冻结 C/C++，可以直接选择同一 SHA256 重复执行。当前 LLVM headed 未切换镜像。

1. 准备获授权的 VD headed 目标，独立固定它的完整发布、硬件身份、实际 Loader 和四个 Provider 摘要。验证对应同 Profile SDK 或明确记录冻结件复用证据。
2. 用相同 GCC C/C++ 字节在 VD headed 得到可用原生参考，再与 LLVM headed 的 GCC 行为对照。用相同 Clang C/C++ 字节在 VD headed 获得另一交叉方向的观测。对比真实 Loader、符号版本、输出、非零及超时行为。
3. 在正式原生与跨镜像结论之前接入满足原信任模型的独立目标监督，验证目标不能操纵退出边界，补齐身份、结果和清理回执。仅有本轮的一条 SDB 通道无法提供该隔离证明。
4. headless 仍需对应的真实设备、发布快照和正式执行证明。原始正式矩阵仍为 **0/8**，headed 跨镜像结论为 **0**。 [实际 headed 结果](LIVE_DEVICE_VALIDATION.md) · [目标退出差距](TARGET_EXIT_VERIFICATION.md)
