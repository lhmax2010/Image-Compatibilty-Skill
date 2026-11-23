# 剩余事项及 Runtime 准入

- **设备与授权。** 缺少与两套 SR ARMv7l 对应、可隔离且已授权的设备或模拟环境。需要为 VD 和 LLVM 分别固定镜像及加载器身份、启动和访问方式、允许执行和回收的目录。
- **四象限原生参照。** VD GCC 和 LLVM Clang 已分别完成原生 SDK 的构建参考，但两者都缺经过观察的原生执行参考。有效的目标适配器需要返回与产物 SHA256 匹配的部署与运行回执。八条计划运行记录保留 NOT_EXECUTED。 [适配器契约](../../../.agents/skills/tizen-image-compatibility/references/execution.md)
- **实际 Loader 行为。** 目前的固定文件核对不覆盖 AT_SECURE、凭据、Namespace、dlopen、弱符号或 interposition。VD C++ 探针的 Copy Relocation 在指定库上定向复核，Skill 的完整闭包仍保持相应证据门槛。 [C++ 证据](CPP_COMPILE_LINK_RESULTS.md)
- **SDK 范围。** 两套最小 SDK 验证了基础 C/C++ 与代表性 Profile 开发文件。整套 Studio SDK、其他 Profile API、libc++ 作为替代 C++ ABI、开发包的安装脚本及源码级再现仍有各自的验证工作。发包索引与 RPM 没有可验证发布者签名记录。 [SDK 来源](SDK_PROVENANCE.md)
- **SQLite。** 需要获得满足正式预算的稳定工作卷，并在新目录完成真实构建和独立对账。 [资源门槛](SQLITE_FULL_ACCEPTANCE.md)
