# 后续 headed 兼容性准入

当前 LLVM headed 设备完成了本轮全部受控运行，已具备可写可执行位置和实际回收路径。此目标无需管理员开通目录、放开 cgroup、修改挂载或启动服务。

| 尚缺项 | 补齐标准 |
| --- | --- |
| VD headed | 提供获授权且已运行匹配 profile 的目标，固定精确发布归档、build ID 和真实系统属性。用户或设备管理员负责镜像切换。 |
| 同 Profile SDK/产物 | 为 VD 和 LLVM headed 记录对应 SDK/构建和链接证据。若沿用之前源自 headless SDK 的冻结件，明确证明可复用的范围、绑定相同 SHA256 和观察契约，保留两套 Profile 的来源。 |
| VD 原生参考 | 在已核实的 VD headed 身份和安全边界中，使用 GCC 冻结原字节依次执行 C 和 C++，取得目标退出、输出、实际 Provider 与独立清理。完成后才可对照本次 LLVM headed 上的 GCC 行为观察。 |
| 剩余 headed 交叉方向 | 对同一 Clang 冻结字节在 VD headed 上取得观测，并使用相同契约与本轮 LLVM headed 的已观测结果对照。 |
| 可复用 Adapter | 对每个授权目标预注册用户 scope 和独立观察能力，验证成功、非零、超时和失联路径。将目标身份、计划、产物、目标回收及传输证据绑定后，才接入正式 Runtime 门禁。 |

headless 需要其自己的真实匹配设备与观测，继续保持 0/8。本轮范围止于普通 C/C++ 探针。 [范围](HEADED_RUNTIME_SCOPE.md) · [实测](HEADED_RUNTIME_RESULTS.md)
