# Phase 7A 交接

本文件供 PM 在仓库迁移后复核 Phase 7A 的修复范围与验证记录。

## 修复范围

修复基线为 `924ef9f5123cf3cbce9df181420f9f716c7ea476`。

1. Header采集不完整时不确认删除；完整清单的真实删除仍可失败。
2. 通过原公共入口的受限包含图核对声明可达性；条件/宏/解析不足保持UNKNOWN。
3. dynsym完整度与ELF头解析分离；部分/旧清单不确认导出不存在，也不获得完整覆盖率或统计信用。
4. 已加载SONAME按root与namespace隔离复用，不以任意同名文件授信；真实闭合上下文缺库仍失败。
5. baseline消费者权限/安全元数据来自baseline，candidate自身检查使用candidate，不混用同路径mode。

对应代码、文档与永久回归随仓库迁移，并已纳入 workspace 内的备份。collector policy 为 `1.3.1-phase7a`，manifest schema 为 1.2。

上一阶段记录：193项测试，188 PASS、5 SKIP、0 FAIL，新增35项。SKIP为未配置/不可用的可选Clang、ARM、libabigail真实集成；另有小型报告链路核对与2000包合成报告基准。没有重新分析真实Tizen镜像，不代表GCC/LLVM镜像兼容认证。

## 尚在workspace外的历史证据

上一阶段七份验收文档、原始日志与小型报告位于：

`/home/linhao/lss/tizen-static-acceptance/20261118/phase7a-static-fixes-924ef9f/`

本轮用户限定所有文件操作在当前workspace内，因此没有读取、复制或修改这些外部文件。它们不在本轮Git bundle或工作树备份中，也不会自动上传到新GitHub。若PM需要其完整内容，须先获得将这些指定证据读取并复制进workspace的特许；仅提交本概要不能替代完整原始验收证据。

迁移的工作区及上传约定见 [GitHub 上传与仓库迁移约定](PUBLICATION_POLICY.md)。
