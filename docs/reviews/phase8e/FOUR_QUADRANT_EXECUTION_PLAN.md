# 四象限 Runtime 验收计划

8 项计划，0 项实际执行。离线编译、指定库匹配和样例 stdout 推导来自既有证据。真实目标 ID 等待审批和绑定。 [冻结 Artifact Manifest](ARTIFACT_MANIFEST.json)

| 产物 | 原生镜像 | VD Runtime | LLVM Runtime |
| --- | --- | --- | --- |
| GCC C | VD | ET-661c9547b3d25d9433c403f3 · NOT_EXECUTED | ET-2d9d0b7dcf9afab31ddb5520 · NOT_EXECUTED |
| GCC C++ | VD | ET-621f1a87748fb0b0a1bc7149 · NOT_EXECUTED | ET-8cb3fae8d132c378c1ed1539 · NOT_EXECUTED |
| Clang C | LLVM | ET-5df19312e28f731154224fa1 · NOT_EXECUTED | ET-8c71607512d6c68e63d9e99f · NOT_EXECUTED |
| Clang C++ | LLVM | ET-ddd2df0ba0f155674ea66c54 · NOT_EXECUTED | ET-ddd82a5817b01aaa88d83c3c · NOT_EXECUTED |

1. 绑定两侧已授权环境 ID、镜像及加载器哈希。限制为普通测试用户、专用写入目录，无额外 argv，stdin 关闭，使用 C locale，禁用公网连接。
2. 对四个原生组合执行部署后哈希核验与探针，保存退出码、stdout/stderr、证据和目标侧清理结果。原生结果要与静态预期相符，重复观测满足一致。预期偏差先核对输入、依赖和采集。
3. 冻结原生回执、原始输出、实际环境和产物的摘要。任何原生失败、回执不完整或产物变化都阻断该产物的跨侧完成判定。
4. 将同 SHA256 字节部署到另一侧，独立验证后比较退出码和确定性行为。进程异常、部署/传输失败和实际行为变化分阶段记录。重现时使用相同镜像、产物、环境和权限。
5. 初始矩阵完整后，考虑 C ABI 与版本符号、C++ RTTI/对象生命周期、跨 DSO 异常和 Unwind、TLS、指定 Provider 和 dlopen。AT_SECURE、Namespace 和特权加载验证需独立授权和上下文。

当前的八个计划沿用 Phase 8D 的证据标识。未来实际回执同时绑定计划 ID、完整产物摘要及真实目标 ID。 [Adapter 准入](RUNTIME_ADAPTER_READINESS.md)
