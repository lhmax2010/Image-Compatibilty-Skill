# Tizen Image Compatibility Skill

在 Cline 或 Linux 终端中比较 GCC 与 LLVM/Clang 构建的 Tizen 镜像。默认检查 baseline 应用和库在 candidate 环境中的兼容性，输出 ABI/API、依赖、软件包、影响范围和可追溯证据。

## 安装

有仓库访问权限时，可直接获取发布快照。

```bash
git clone --depth 1 --branch review/tizen-compatibility-report-v1.3 --single-branch \
  git@github.com:lhmax2010/Image-Compatibilty-Skill.git
cd Image-Compatibilty-Skill
```

也可以解压发布源文件 ZIP。使用 Cline 时，在项目工作区启用 `tizen-image-compatibility`。如果当前版本没有发现 `.agents/skills/` 中的 Skill，把完整目录复制到项目的 `.cline/skills/`。

```bash
mkdir -p .cline/skills
cp -R .agents/skills/tizen-image-compatibility .cline/skills/
```

在 Cline 中调用 `/tizen-image-compatibility`，并提供 baseline、candidate 与输出路径。无论通过 Cline 还是 CLI 调用，分析均在本地执行。

## 静态分析

需要 Linux 和 Python 3.10+。推荐安装 GNU `readelf` 和 `rpm`。需要 `--config` 时安装可选的 PyYAML。默认使用 Python 标准库。 [工具依赖](.agents/skills/tizen-image-compatibility/references/tool_requirements.md)

```bash
SKILL=.agents/skills/tizen-image-compatibility
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline /path/to/gcc-rootfs \
  --candidate /path/to/llvm-rootfs \
  --mode static --output ./reports/comparison
```

输出目录必须位于源镜像和 SDK 之外。CLI 支持已提取的 Rootfs、TAR/TAR.GZ、SquashFS，以及用于包清单分析的 RPM 集合。EXT4 或分层 OCI 输入先离线准备 Rootfs。通过 `--baseline-manifest` 与 `--candidate-manifest` 可复用两份已采集的清单。

对于含 `platform.img` 的烧录包，先用 `prepare_image.py --inspect` 核对内层封装。VDFS 需要可信宿主机提取器或同构建替代输入。准备完成后，可将状态为 `READY` 的运行时 Rootfs 准备目录传给分析 CLI。 [烧录包准备与适配器配置](.agents/skills/tizen-image-compatibility/references/image_preparation.md)

先读 `summary.md`，再按需打开 `index.html`、`results.json` 和 `findings.csv`。`--fail-on HIGH` 控制不兼容阈值。`--strict` 纳入 UNKNOWN，`ci.minimum_coverage` 单独控制覆盖率。退出码 0 表示未触发配置的门槛。 [状态与 CI](.agents/skills/tizen-image-compatibility/references/severity_rules.md)

## 影响与历史报告

```bash
python3 "$SKILL/scripts/enhance_report.py" build \
  --input ./reports/comparison --output ./reports/indexed
python3 "$SKILL/scripts/impact_report.py" build \
  --input ./reports/indexed --output ./reports/impact
python3 "$SKILL/scripts/enhance_report.py" serve \
  --report ./reports/indexed --impact ./reports/impact
```

打开终端显示的本地 URL，通过 `/impact` 查看消费者、软件包、Finding 和原证据。已有验证通过的增强报告可直接复用。增强索引需要可对账的两侧已安装 RPM 清单；清单缺失时可继续阅读原始静态报告。`history_report.py` 比较同谱系、同方向的两份报告，区分新增、修复、持续和未确认项。 [完整使用指南](.agents/skills/tizen-image-compatibility/references/user_guide.md)

SDK 和目标验证需要显式配置编译器、sysroot、原生参考与隔离适配器。运行测试默认关闭。缺少证据的结果保留 UNKNOWN。 [执行指南](.agents/skills/tizen-image-compatibility/references/execution.md) · [兼容性维度](.agents/skills/tizen-image-compatibility/references/compatibility_dimensions.md) · [报告结构](.agents/skills/tizen-image-compatibility/references/report_schema.md)
