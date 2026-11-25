# VD headed 验证计划

当前 LLVM headed 镜像继续保留。本轮具备测试产物、同一字节和 LLVM 参考的交接条件。VD 切换或部署仍需明确授权、匹配的 VD headed 镜像、对应 SDK 出处和运行库身份、获准目标与非 root 可执行环境、可审核的独立目标监督和回退安排。

1. 校对冻结参考的 SHA256 及归档的镜像、编译器与运行库清单。独立确认 VD 的实际 Build ID、Boot ID、架构、Profile、Loader 和 Provider SHA256。创建只适用于 VD 的 enrollment 与执行计划。
2. 在 VD 原生环境先执行原 GCC C/C++，各三次。用一致的 stdout/stderr、退出、绑定与清理证据冻结原生行为参考。
3. 核实同 Profile 的 LLVM 原生结果满足比较前提，再用相同 SHA256 的 Clang C/C++ 在 VD 上执行。对 GCC 在 LLVM 的历史观察独立看待，按验收要求核对对应 Boot/镜像，必要时取得新的匹配证据。
4. 按冻结清单扩展到 19 项专项。精确版本用原始 executable/DSO 和新目标授权。私有 DSO dlopen 沿用原始成功预期，将 LLVM 的策略拒绝作为对照，不改变 Loader 或安全策略。libc++ 仅在目标依赖闭包可证时纳入，否则保持 SKIP。
5. 分别比较构建、部署、行为、实际 Provider/Binding、异常及清理。只有满足同 Profile 原生参考和独立可信目标监督才可以申请正式双侧结论，headless 矩阵保持独立。

本地机读计划在 `LLVM_REFERENCE/runtime/VD_VALIDATION_TEMPLATE.json`，没有指定可连接设备或任何可执行授权。
