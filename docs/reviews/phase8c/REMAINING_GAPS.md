# 剩余限制和 Phase 8D 准入

- **运行时授权和设备。** 缺少与两套 SR ARMv7l 匹配的授权设备或模拟环境。Phase 8D 需要目标镜像身份、执行授权和隔离运行边界，才能启动四象限测试。
- **有效加载上下文。** 待取得目标进程入口、实际加载器、凭据和辅助向量、挂载策略、有效路径、插件 Namespace、dlopen 和符号查找次序。 [静态证据边界](STATIC_EVIDENCE_VALIDATION.md)
- **匹配 SDK。** 需验证 Rootstrap 或 Sysroot 的实际包签名、依赖闭包、头文件、crt、softfp ABI，以及两侧真实 C/C++ 编译和链接。 [SDK 路线](SDK_ROOTSTRAP_RESEARCH.md)
- **DWARF 与 API。** Build-ID 和 Evidence 保持可追溯，完整调试信息、匹配 SDK 与 libabigail 验证仍待补充。五项外部工具测试保持 SKIP。
- **ELF 角色。** 依赖完整 GNU readelf 证据。无节头、布局不可判定或工具异常的对象保持 UNKNOWN。历史 manifest 维持原有记录，需要重新采集才能应用分类。 [角色判据](DEBUG_ELF_CLASSIFICATION.md)
- **全量派生索引。** 资源和结果见 [SQLite 验收](SQLITE_ACCEPTANCE.md)。
