# 真实端到端验收

| 阶段 | 实际入口与结果 |
| --- | --- |
| 静态输入 | 复用 Phase 8C 同一原始 headless 报告。CSV 对账 903,377 条 Finding，其中 11,490 INCOMPATIBLE、868,069 UNKNOWN，Linking UNKNOWN 860,294。VD 719 / LLVM 736 安装 RPM |
| 构建与冻结 | `runtime_workflow.py build --config build-config.json --output build-reviewed`，20 项真实编译链接成功，9.61 秒。补充 resident-provider 使用独立配置和冻结清单 |
| 审查授权 | 复用可信 enrollment 的硬件、镜像、标准库身份。对新清单及部署摘要单独固定授权，未复用原始四项的授权来自动放行新产物 |
| 四项基础复验 | `sdb_runtime.py --execute` 使用 Phase 8E 原始产物，12/12 观察成功 |
| 专项部署与运行 | `runtime_workflow.py run --execute` 负责每一项的准入、部署检查、释放、执行、证据和清理。审查初版、其余病例、补充验收阶段耗时分别为 233.14、132.04、45.70 秒，含执行边界停机、SDB 及报告处理 |
| 最终统一报告 | `runtime_workflow.py report --config final-report-config.json --output integrated-final` 聚合 31 份最终实机回执、21 项编译链接记录与原始静态对账，生成 JSON/Markdown/HTML |

命令中的私有配置文件在本轮本地目录内。分批实测保留了初轮安全停止和失败证据。最终报告选定每个专项用例的最终回执，基础四项保留全部三个重复。新用户仍需审核 SDK、配置测试契约、固定清单、登记和授权设备，并维持 SDB 的已有连接。构建、部署、执行、收集和生成报告由脚本完成。见 [使用指南](USER_GUIDE.md)。
