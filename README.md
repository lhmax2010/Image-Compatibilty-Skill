# Tizen Image Compatibility Skill

用于在 **Cline** 中比较 **GCC 与 LLVM/Clang 构建的 Tizen OS 镜像**的 Agent Skill，以及可独立运行的 Python 兼容性检测框架。保留兼容 Codex 的元数据，但使用本项目不需要 Codex。

默认执行离线分析，比较二进制、开发接口和系统接口，并生成带证据的兼容性报告。检查方向是：**依赖 baseline 接口的应用，能否在 candidate 环境继续工作**。需要验证反向兼容时，交换两个输入再运行一次。

> 当前版本提供可运行的离线分析、SDK 编译探针和可配置的目标运行适配器。无法完成或证据不足的检查标为 `UNKNOWN`。仓库中的示例全部为合成数据，不代表任何真实 Tizen 版本的兼容性结论。

**当前本地交付**包含离线影响侧车、历史回归、ARM 静态检查和可独立查询的编译／运行阶段。真实报告规模和静态 ARM 样本已复核，真实 SDK 四象限和设备验证仍待执行。旧版本更改与验证记录保留在 [1.2 验证记录](V1_2_VALIDATION.md)。 [最终验收](docs/final-release/FINAL_ACCEPTANCE.md)


## 快速开始

检测程序应在 Linux 环境中使用 Python 3.10 或更新版本。Windows 用户可让 Cline 在 WSL、Linux 容器或远程 Linux 环境中执行；当前实现使用 `os.killpg`、POSIX 进程组及 Linux 扩展属性，未支持原生 Windows 执行。

```bash
git clone https://github.com/lhmax2010/Image-Compatibilty-Skill.git
cd Image-Compatibilty-Skill

SKILL=.agents/skills/tizen-image-compatibility
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline /path/to/tizen-gcc-rootfs \
  --candidate /path/to/tizen-llvm-rootfs \
  --mode static \
  --output ./reports/gcc-vs-llvm
```

默认参数仅依赖 Python 标准库；ELF 和 RPM 的详细分析分别需要 `readelf` 和 `rpm`。缺少可选工具时保留其他分析结果，并报告覆盖缺口。

输出目录必须是新的或空目录，并且位于源镜像和 SDK sysroot 之外。程序不会安装软件到镜像，不执行镜像中的配置命令，也不会自动挂载、刷写或启动设备。

## 在 Cline 中使用

### 当前兼容性结论

**现有代码支持由 Cline 加载并调用，无需修改 Python 检测引擎。** 这里的支持是根据 Cline 官方格式/源码及本地脚本验证得出的结论；已实际将完整技能复制到临时 `.cline/skills/`，从不同工作目录运行 CLI，并复现合成示例的 7 条预设不兼容项及全部报告文件；尚未在真实 Cline UI 会话中做端到端验收。

| 检查项 | 结果 |
|---|---|
| Skill 格式 | `SKILL.md` 包含 `name` 和 `description`；名称与目录 `tizen-image-compatibility` 一致 |
| 辅助资源 | `scripts/`、`references/`、`assets/` 随 skill 一起分发，脚本按自身位置定位资源 |
| Codex 依赖 | Python 程序没有 Codex/OpenAI SDK、API、MCP 或专用工具依赖 |
| `agents/openai.yaml` | Codex 的界面元数据；Cline 加载本技能不依赖此文件，它也不控制 Cline 的启用或权限设置 |
| 执行环境 | 需要 Cline 能读取本地文件、调用 Linux 终端，且该环境安装了所需分析工具 |

截至 2026-11-16 核对，Cline 当前主分支的[目录发现代码](https://github.com/cline/cline/blob/main/apps/vscode/src/core/storage/skill-directories.ts)包含 `.agents/skills/`；[官方 Skills 文档](https://docs.cline.bot/customization/skills)推荐项目目录 `.cline/skills/`。源码主分支不等于你已安装的版本，以下提供两种使用路径。

### 方式一：直接在本仓库使用

1. 将仓库克隆到 Linux、WSL 或远程 Linux 环境，并在 Cline 中打开仓库根目录作为工作区。
2. 打开 Cline 的 Skills 列表，检查是否出现并启用了 `tizen-image-compatibility`。支持 `.agents/skills/` 的版本可以直接发现仓库内的技能。
3. 在聊天框输入 `/`，从建议中选择 `/tizen-image-compatibility`，再提供镜像位置；也可以通过下面的自然语言请求触发。

```text
/tizen-image-compatibility
比较以下两个 Tizen 镜像，执行离线兼容性检测并生成报告：
baseline=/path/to/tizen-gcc-rootfs
candidate=/path/to/tizen-llvm-rootfs
output=./reports/gcc-vs-llvm
请使用实际加载的 skill 目录运行 scripts/tizen_compat.py，
保留原始证据，并区分 INCOMPATIBLE 和 UNKNOWN。
```

自然语言请求示例：

```text
请使用 tizen-image-compatibility 技能，比较 /images/tizen-gcc 与
/images/tizen-llvm 的 ABI、公共头文件、RPM 和系统接口，生成离线报告。
```

`$tizen-image-compatibility` 是原 README 中面向 Codex 的写法；在 Cline 中使用其斜杠菜单或自然语言请求，不依赖 `$` 触发。

### 方式二：安装到 Cline 专用目录

如果 Cline 未发现仓库里的 `.agents/skills/`，或需要在另一个项目使用，在仓库根目录执行以下命令。复制的是**完整目录**，不是单独的 `SKILL.md`：

```bash
# 把 /path/to/project 替换成 Cline 实际打开的项目根目录。
# 在本仓库使用时可设为 PROJECT="$PWD"。
PROJECT=/path/to/project
mkdir -p "$PROJECT/.cline/skills"
cp -R .agents/skills/tizen-image-compatibility "$PROJECT/.cline/skills/"
```

此命令用于首次安装；若目标已存在同名目录，先检查是否有自行修改，避免覆盖自定义内容，并保持技能目录名不变。安装后在 Skills 列表中重新检查并启用该技能。日常只维护一份启用的同名技能，避免调用到旧副本。

需要所有项目共用时，也可首次安装到全局目录：

```bash
mkdir -p "$HOME/.cline/skills"
cp -R .agents/skills/tizen-image-compatibility "$HOME/.cline/skills/"
```

全局路径属于 **Cline 实际运行环境**的用户目录；远程/WSL 环境不要复制到另一个宿主用户目录。同名全局技能可能覆盖项目技能，排查时检查实际加载路径。

### 命令路径、权限与排查

以下 README 的 CLI 示例默认从本仓库根目录运行：

```bash
SKILL=.agents/skills/tizen-image-compatibility
```

安装到 Cline 目录后，应按实际位置重新设置变量，例如：

```bash
# 项目安装：替换成实际绝对路径。
SKILL=/path/to/project/.cline/skills/tizen-image-compatibility
# 全局安装时使用：SKILL="$HOME/.cline/skills/tizen-image-compatibility"
python3 "$SKILL/scripts/tizen_compat.py" --help
```

Cline 应使用**实际加载的 `SKILL.md` 所在目录**定位脚本，不应始终套用仓库内的 `.agents/skills/` 示例路径。不同终端调用不保证共享 `SKILL` 变量，需要在同一次命令中设置变量并运行脚本。输入镜像、sysroot 和输出路径也必须是执行环境可访问的路径。

- 找不到技能：检查 Skills 启用状态、目录名与 frontmatter 名称、实际工作区及同名全局副本；必要时按方式二安装。
- 找不到 Python 或分析工具：在 Cline 实际执行命令的 Linux 环境安装依赖，而非修改源镜像。
- 无法执行命令：按照自己的 Cline 终端工具审批设置允许所需命令；技能文件不会绕过这些设置。
- 命令退出 `1`：先查看已生成的报告，这通常表示命中兼容性失败阈值，不代表程序崩溃。
- 没有设备/QEMU：使用 `static`；`full` 下无法执行的运行时检查保持 UNKNOWN，不要据此宣称全部兼容。

“离线分析”指 Python 检测程序不需要联网；Cline 所选模型是否需要网络，取决于模型提供方及部署方式。

## 检测能力

| 范围 | 当前能力 | 主要边界 |
|---|---|---|
| ELF / ABI | ELF 架构和类型、导入/导出符号、符号版本、数据/TLS 符号大小、C++ RTTI/vtable 符号；可选 libabigail | 完整类型布局需要可用调试信息；相同符号不等于完整 ABI 相同 |
| 公共 API / 头文件 | 安装路径、声明、宏、包含依赖、条件编译信息、注释/空白归一化 | 保守词法分析，不是完整 C/C++ AST 或类型解析器 |
| 动态链接 | SONAME、DT_NEEDED、加载器、RPATH/RUNPATH、库提供者、依赖环 | 不完整模拟实际加载器的搜索顺序、命名空间和符号解析 |
| RPM / SDK | 已安装数据库与可用 RPM 档案分开；完整 NEVRA、文件归属；逐包 ABI/API/链接状态及覆盖率 | 缺少数据库时包数为未知；SDK 需明确关联；不实现包依赖求解器 |
| 系统接口 | 文件类型、链接、权限、UID/GID、配置、命令可用性、systemd 单元、D-Bus XML | 静态存在性不证明运行行为 |
| 安全 / 内核 / 网络 / 多媒体 | 策略和可读取扩展属性、UAPI/内核配置、相关库与配置清单 | 有效权限、内核行为、网络协议和硬件能力需要目标测试 |
| 编译与运行 | 四向头文件编译、C/C++ 探针、相同程序跨镜像执行与输出比较 | 需要显式 SDK/编译器，以及获得授权的隔离目标环境 |
| 性能与资源 | 可选二进制大小百分比阈值 | 尚未内置启动时间、CPU/内存和吞吐量基准 |

完整范围及限制见 [兼容性维度说明](.agents/skills/tizen-image-compatibility/references/compatibility_dimensions.md)。

## 输入格式与模式

| 输入 | 支持情况 |
|---|---|
| 已解包 rootfs 目录 | 支持，主要使用方式 |
| TAR / TAR.GZ | 支持，解包到独立临时工作区 |
| SquashFS | 需要 `unsquashfs` |
| 单个 RPM / RPM 集合目录 | 支持包元数据分析；不会安装或展开 payload |
| OCI / 容器 rootfs | 支持已合并、已导出的 rootfs；不直接处理分层布局和 whiteout |
| EXT4 镜像 | 需先用只读用户态工具或隔离环境解包 |

| 模式 | 行为 |
|---|---|
| `quick` | 初步静态比较，省略详细 relocation/note 及 libabigail 检查 |
| `static` | 默认模式，执行可用的静态分析 |
| `runtime` | 采集静态上下文，并执行已配置的 SDK/目标测试 |
| `full` | 静态分析及所有已配置、可执行的编译/运行检查 |

没有运行环境不会阻断静态分析，也不会把未执行测试算作通过。

## 配置与依赖

使用 YAML 配置前，在宿主工具环境中安装可选依赖；离线环境可从本地 wheel 源安装：

```bash
python3 -m pip install -r "$SKILL/requirements.txt"
cp "$SKILL/config.yaml" ./compat-config.yaml
```

修改配置后运行：

```bash
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline ./images/gcc.tar.gz \
  --candidate ./images/llvm.tar.gz \
  --config ./compat-config.yaml \
  --cache ./compat-cache \
  --mode full \
  --output ./reports/full
```

`--cache` 按文件内容、工具版本和采集参数复用完整 ELF 采集结果，其他采集器仍会执行。默认忽略 ELF build ID、文件时间戳等非接口信息；配置可以调整工具路径、分析维度、超时、头文件数量、严重性和大小阈值。

| 工具 | 用途 |
|---|---|
| Python 3.10+ | CLI、采集、比较和报告 |
| PyYAML 6.x | 仅 `--config` 需要 |
| GNU readelf / 可选 nm | ELF 详细采集 / 降级原始符号证据 |
| rpm | RPM 文件或临时复制的 RPM 数据库查询 |
| abidiff | 可选 DWARF 类型与布局 ABI 比较 |
| unsquashfs | 可选 SquashFS 解包 |
| GCC/G++、Clang/Clang++ 与 SDK | 显式配置的编译探针 |
| rpmbuild | 合成 RPM 集成测试 |

工具探测命令：

```bash
python3 "$SKILL/scripts/tizen_compat.py" --list-tools --output ./reports/tools
```

完整配置见 [config.yaml](.agents/skills/tizen-image-compatibility/config.yaml)，依赖与降级行为见 [工具说明](.agents/skills/tizen-image-compatibility/references/tool_requirements.md)。

## SDK 与四向测试

头文件矩阵使用各自 SDK 中的头文件，并分别配置 GCC 和 Clang。运行矩阵把同一个编译产物送入两个目标环境；通过 `cross_compilation.builds` 显式指定每个编译器的 SDK、原生参考镜像和构建来源，不再由编译器名字推断 baseline/candidate。自身参考环境失败时，两侧都不会被算作已验证兼容。适配器须返回带环境 ID、产物哈希、部署/执行状态的 JSON 回执；旧式 stdout/退出码适配器需要升级。

```bash
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline ./images/gcc-rootfs \
  --candidate ./images/llvm-rootfs \
  --mode full \
  --baseline-sysroot /sdk/gcc/sysroot \
  --candidate-sysroot /sdk/llvm/sysroot \
  --gcc /sdk/gcc/bin/aarch64-linux-gnu-gcc \
  --gxx /sdk/gcc/bin/aarch64-linux-gnu-g++ \
  --clang /sdk/llvm/bin/clang \
  --clangxx /sdk/llvm/bin/clang++ \
  --config ./compat-config.yaml \
  --output ./reports/sdk-matrix
```

运行探针还需在配置中提供 `builds: {gcc: {sdk: baseline, reference_image: baseline, provenance: 实际GBS构建标识}, clang: {sdk: candidate, reference_image: candidate, provenance: 实际GBS构建标识}}`；示例角色可调换。

Clang 的目标三元组及 SDK 专用参数应配置在 `cross_compilation.compilers` 中。框架不会用宿主默认编译器替代缺失的 SDK 编译器。

运行测试默认关闭。显式设置 `runtime.enabled: true` 和 `runtime.authorized: true` 后，仅在已配置 runner 的目标环境执行；完整双镜像比较需要两侧环境，缺失侧为 `UNKNOWN`。设备/QEMU/VM 传输与隔离由使用者提供的适配器负责；框架没有内置生产级部署适配器。配置和接口协议见 [编译与目标执行指南](.agents/skills/tizen-image-compatibility/references/execution.md)。

## 报告与结果复用

默认输出：

```text
reports/gcc-vs-llvm/
├── index.html                 # 可筛选的详细报告
├── summary.md                 # 摘要、风险和限制
├── results.json               # 机器可读结果
├── findings.csv               # 差异表
├── baseline-manifest.json     # 独立 baseline 清单
├── candidate-manifest.json    # 独立 candidate 清单
├── collection.log             # JSON Lines 命令记录
└── evidence/                  # 原始采集证据
```

执行编译时另有 `build/` 目录。每条 finding 包含组件、接口、两侧值、状态、严重性、置信度、证据、检测方法、潜在影响和建议操作。

已有清单可以直接重新比较，无需再次访问镜像：

```bash
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline-manifest ./reports/gcc-vs-llvm/baseline-manifest.json \
  --candidate-manifest ./reports/gcc-vs-llvm/candidate-manifest.json \
  --output ./reports/reused
```

移动清单时同时保留旁边的 `evidence/`。复用时保留历史测试结果，但不会声称重新执行过目标测试。

## 状态与 CI

| 状态 | 含义 |
|---|---|
| `IDENTICAL` | 已测量接口表面相同 |
| `COMPATIBLE` | 证据支持该项变化或测试兼容 |
| `INCOMPATIBLE` | 确认的接口缺失、契约变化或行为回归 |
| `UNKNOWN` | 工具、输入或环境缺失，或语义证据不足 |
| `NOT_APPLICABLE` | 该限定检查未检测到适用的用户态子系统 |

严重性分为 `CRITICAL`、`HIGH`、`MEDIUM`、`LOW`、`INFO`。差异不会自动被判为不兼容，例如 RPM release 变化。仅有注释/空白的头文件变化保留词法相等证据，语义兼容结论仍为 UNKNOWN，需 SDK/宏/目标上下文验证。

```bash
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline ./images/gcc-rootfs --candidate ./images/llvm-rootfs \
  --fail-on HIGH --exclude performance \
  --output ./reports/ci
```

| 退出码 | 含义 |
|---|---|
| `0` | 没有命中所配置失败阈值，不代表所有检查通过 |
| `1` | 不兼容项达到阈值、最低覆盖率未达到，或 `--strict` 检测到 UNKNOWN |
| `2` | 输入或配置无效 |
| `3` | 执行基础设施错误 |

默认 `--fail-on HIGH` 包含 HIGH 和 CRITICAL。`--strict` 对任何 UNKNOWN 也返回失败；离线运行通常存在 UNKNOWN。`--exclude abi,runtime,performance` 可排除维度。详见 [分类规则](.agents/skills/tizen-image-compatibility/references/severity_rules.md)。

## 合成示例与验证

预生成示例位于 [examples/synthetic-report](.agents/skills/tizen-image-compatibility/examples/synthetic-report)。GitHub 文件视图不会直接执行 HTML 报告，可克隆后在浏览器中打开 `index.html`，或本地查看：

```bash
python3 -m http.server 8000 --bind 127.0.0.1 \
  --directory "$SKILL/examples/synthetic-report"
```

访问 `http://127.0.0.1:8000/`。仓库保留的历史 schema 1.0 示例故意移除符号、修改数据大小和 D-Bus 签名等，旧报告包含 **7 条不兼容 finding**。其运行时矩阵全部为 UNKNOWN，两个镜像夹具均由宿主编译器生成，不能作为真实 GCC/LLVM Tizen 对比结果。

重新生成自己的合成输入和报告：

```bash
python3 "$SKILL/scripts/make_synthetic_fixture.py" ./synthetic-images
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline ./synthetic-images/baseline \
  --candidate ./synthetic-images/candidate \
  --output ./synthetic-report
# 预期退出码为 1：合成数据包含刻意设置的不兼容项。
```

运行测试：

```bash
python3 -m unittest discover -s "$SKILL/tests" -v
python3 -m compileall -q "$SKILL/scripts" "$SKILL/tests"
```

原有 36 项测试保留，并补充了正确性回归和可选真实 Clang/libabigail 工具测试。1.1 基线 69 项测试全部通过后开始本次修改；1.2 的新增用例、完整命令、工具来源和结果见 [V1_2_VALIDATION.md](V1_2_VALIDATION.md)。测试使用真实构造的 ELF/RPM 和模拟适配器；已验证 Clang AST/ARM 对象及 libabigail 嵌入/拆分 DWARF，尚未完成真实 Tizen SDK、设备/QEMU 集成验收。依赖工具的测试在工具缺失时明确跳过。

## 目录与进一步阅读

```text
.agents/skills/tizen-image-compatibility/
├── SKILL.md
├── agents/openai.yaml        # 可选 Codex 元数据，Cline 不依赖
├── config.yaml
├── requirements.txt
├── scripts/
│   ├── tizen_compat.py
│   ├── make_synthetic_fixture.py
│   └── compat/
├── assets/
│   ├── report_template.html
│   └── probes/
├── tests/
├── examples/
└── references/
```

- [采集、证据、归一化与缓存](.agents/skills/tizen-image-compatibility/references/detection_methods.md)
- [JSON manifest 与报告结构](.agents/skills/tizen-image-compatibility/references/report_schema.md)
- [实现清单、验证记录与已知限制](.agents/skills/tizen-image-compatibility/references/implementation.md)

### 覆盖率质量门禁

```yaml
ci:
  minimum_coverage: {abi: 90, linking: 95, runtime: 100}
```

`results.json.coverage` 每个维度列出 applicable、completely_verified、partially_verified、unexecuted，以及 confirmed_compatible、confirmed_incompatible、unknown。兼容结论和验证完整度独立：一个确认破坏但仍缺 DWARF 的组件可以是 **INCOMPATIBLE + PARTIAL**，不会算作完整验证。`verified` 兼容字段现在只等于 completely_verified，不能再理解为 compatible + incompatible。

覆盖率 = COMPLETE / applicable；兼容率 = confirmed_compatible / applicable。NOT_APPLICABLE 排除在分母外；缺失清单产生 UNKNOWN 义务，不能变成 100%。全部 N/A 或排除的维度百分比为 null。统计单位是组件契约及明确的必需检查，ABI 区分导出表与类型布局；增加 finding 不会提高覆盖率。`quality_gate` 分开报告 compatibility_status、coverage_status 和 strict_status；覆盖率低于门槛返回 1。退出 0 只说明配置的门禁未触发。

加载器环境默认未知，不能仅凭 rootfs 内存在 SONAME 判定可加载。声明完整 loader environment 前，必须核实目标搜索路径及有效缓存；配置样例、尚不支持的 glibc 行为、拆分 debuginfo 输入和 AST 限制见 [正确性边界](.agents/skills/tizen-image-compatibility/references/correctness.md)。

HTML 展示前 1000 条 finding 和前 1000 个包，Markdown 展示前 200 条不兼容详情和前 200 个包；完整数据保存在 JSON/CSV。Schema 1.0/1.1 manifest 可读取，保留已确认失败，但旧成功测试/矩阵结论降为 UNKNOWN，不能作为 1.2 完整覆盖证据。升级会使旧 ELF 缓存失效。

### 逐包 ABI/API 报告

查看 `results.json.package_inventory`、`package_results` 和 `packages.csv`。包级表包括 baseline/candidate 版本、ABI、API、链接、完整覆盖率与总体状态；可展开 ELF/符号/头文件、相关 finding、缺失接口、证据及未验证项。已安装 RPM 与目录里可下载/可安装的 RPM 文件分别统计。数据库不存在或查询失败时 installed_count 为 null，不是 0。

文件归属来自 RPM 文件清单，保留多所有者、usrmerge 别名以及消费者/提供者角色。多版本不被覆盖，改名/拆包不凭名称缺失就判不兼容。只拿到 runtime rootfs 不能宣布某个包 API 兼容；SDK 头文件必须通过 `cross_compilation.sdk_package_manifests` 明确关联到 SDK 的已安装包清单，否则列为未归属。配置与解释见 [包级分析](.agents/skills/tizen-image-compatibility/references/packages.md)。

### 预期测试清单与 ARMv7

`expected-tests.json` 在执行前生成，`expected-tests-results.json` 记录逐阶段结果。稳定 ID 包含编译器、源文件、SDK、构建来源和目标角色。缺失、重复、意外 ID、产物哈希不符、无效回执或原生参考失败都会阻止矩阵通过；`header_limit` 之外的头文件仍是未完成项。静态模式下矩阵保持未执行是正常结果。

ARMv7 可配置 `cross_compilation.target_abis` 和 `runtime_objects`，用真实 SDK ABI 与选定 loader/libc 校验编译器探针；其他 ELF 缺少可选属性不再阻塞全部探针。hard 对应 VFP PCS，soft 对应 base PCS（包含 softfp 代码生成）。明确 ABI 冲突与信息不足分别记录，不能把两者当成成功。示例见 [编译与运行配置](.agents/skills/tizen-image-compatibility/references/execution.md)。

### v1.2 补充验收

新增 [审查发现](V1_2_REVIEW_FINDINGS.md)、[实现范围、能力分类与生产验收前提](V1_2_CORRECTNESS_REMEDIATION.md)，实际命令与结果统一记录在 [V1_2_VALIDATION.md](V1_2_VALIDATION.md)。可直接查看 [小型包级 HTML 示例](.agents/skills/tizen-image-compatibility/examples/package-report/index.html) 与 [示例说明/JSON/CSV](.agents/skills/tizen-image-compatibility/examples/package-report/README.md)；这些都是合成数据，不是 Tizen 产品结果。

包清单现在显式提供数量对账、每个 candidate 包的 assessment、提供者包到消费者包的索引以及未验证来源的包记录。改名/拆包只报告有共享文件证据的候选线索，状态仍为 UNKNOWN。无公开接口且清单完整的包为 NOT_APPLICABLE，不凭元数据相等宣布兼容。`finding_integrity` 记录重复观察次数；不同入口程序的传递失败使用不同 ID。缺少预期测试元数据时不沿用旧矩阵成功，已有失败继续保留。

压力测试会重新读取 JSON/CSV 并核对精确 finding ID、归属、状态、HTML/Markdown 展示及完整记录数，并执行时间/内存预算：

```bash
python3 "$SKILL/tests/review/benchmark_v12.py" \
  --packages 2000 --symbols 10 --max-seconds 30 --max-rss-mib 768 \
  --output /tmp/package-stress-new
# 同一夹具版本、同规模的后续运行可增加：
# --reference /tmp/package-stress-new/benchmark.json --max-regression-factor 2
```

默认预算是合成测试的回归警戒值，不是实际 Tizen 镜像的性能承诺。正式验收仍需匹配的产品 rootfs、RPM 数据库、SDK、debuginfo 和授权隔离运行环境。


### v1.2 release candidate 本地冻结

PR #1 最终审查修复及逐项证据见 [V1_2_FINAL_REVIEW.md](V1_2_FINAL_REVIEW.md)，静态产品测试准备结论见 [V1_2_RELEASE_READINESS.md](V1_2_RELEASE_READINESS.md)。拟用的 [真实 Tizen 静态验收输入记录](V1_2_STATIC_ACCEPTANCE_INPUT.json) 需由产品方填入镜像、来源、RPM 清单和覆盖要求；它不是 CLI 配置文件。

此次 collector 标识为 `1.2.0-rc.1`，报告 schema 仍为 1.2；旧 ELF 缓存会重新采集。修复仅涉及 ARM ABI/ISA 区分、自定义探针调度、解析完整度、candidate 新增包状态及 HTML 缺失接口预览。产品静态测试准备就绪不等于 GCC/LLVM 镜像兼容已获证明。

### v1.3 大型报告浏览（独立报告增强）

使用已生成的 schema 1.2 报告，无需重新采集镜像。Cline 可以直接执行以下命令；Python 标准库即可，不需要安装服务或访问互联网：

```bash
SKILL=.agents/skills/tizen-image-compatibility
python3 "$SKILL/scripts/enhance_report.py" build \
  --input /path/to/existing/skill-report --output /path/to/new/enhanced-report
python3 "$SKILL/scripts/enhance_report.py" serve --report /path/to/new/enhanced-report
# 浏览器打开 http://127.0.0.1:8765/
```

输出目录必须全新且独立。输入包含 `results.json`、双侧 manifest、`findings.csv`、`packages.csv`。增强工具不调用检测器，不执行镜像内容，不改变原始兼容性结论。原始 schema/collector 版本保持不变。

- 按 Image → Package → ELF → Symbol 浏览；Package 支持名称搜索、ABI/API/Linking 过滤及 FUNC、Missing、Finding、UNKNOWN 数量排序。
- 区分 FUNC/IFUNC/OBJECT/TLS、Weak、Versioned exports；按记录的虚拟符号链接去重，保留共享所有权和缺失证据。`observed_*` 是已观察数量；完整计数不足时为 UNKNOWN。
- 完整导出 `package-symbol-summary.csv`、`elf-symbol-summary.csv`、`symbol-differences.csv`、`linking-findings-groups.csv`、`linking-unknown-reasons.csv`。MATCHED 和属性变化是展示分类，不生成新的兼容性判断。
- Linking 分组保留原始状态、原因、方向、需求和提供者；可分页追溯消费者、Root Consumer、全部原始 Finding ID 及证据。缺失原因显示 NOT_RECORDED。
- 原始 Finding 的完整 JSON 载荷以无损压缩形式保存在 `report-index.sqlite`，另提供完整 ID/Group Member/Unassigned CSV。原始 JSON/CSV 字段、Package 状态、符号总量和源文件哈希会自动对账。

直接打开 `index.html`（`file://`）仅支持静态概览和 CSV 链接，**完整交互浏览需要上述本机 HTTP 服务**。服务只绑定 `127.0.0.1`，仅提供只读分页查询。证据仍位于原始报告目录，移动增强报告时请保留或同步原始目录位置；不要删除原始报告。

真实报告处理限制：进程树 RSS 3 GiB、新增报告 15 GiB、磁盘剩余至少 100 GiB；可用内存低于 3 GiB 持续 10 秒停止并写入失败证据。不会通过提高限制自动重试。统计采用动态导出表，不等同于 Public API；相同导出数量不证明 ABI 兼容。详见 [设计](V1_3_REPORT_DESIGN.md)、[验证](V1_3_REPORT_VALIDATION.md)、[性能](V1_3_PERFORMANCE.md)和[限制](V1_3_KNOWN_LIMITATIONS.md)。

### v1.4 RC 离线影响分析

已有 v1.3 增强报告可直接复用。如果只有原始 schema 1.2 报告，先按上一节生成增强报告。下面的命令为独立 SQLite 侧车生成影响组、消费者、软件包角色、原 Finding 引用与验证建议。

```bash
SKILL=.agents/skills/tizen-image-compatibility
python3 "$SKILL/scripts/impact_report.py" build \
  --input ./reports/enhanced --output ./reports/impact-rc1
python3 "$SKILL/scripts/impact_report.py" serve \
  --report ./reports/enhanced --impact ./reports/impact-rc1
# 在浏览器打开终端显示的本机 /impact 地址
```

复用历史数据时，优先核对绑定证据和未知原因。若同源的 Phase 7A manifests 可用，可以重复传入 `--replay-root /bin/app` 以静态解析指定 baseline 根程序。确认直接影响需要基线已满足同一需求、候选原 Finding 明确失败，且重放记录精确吻合。每条结论限定于对应的静态上下文，运行环境和 C++ ABI 行为另需验证。详见 [v1.4 架构与能力](docs/release-v1.4/01_ARCHITECTURE_AND_FEATURES.md)。

## Release 交付

查看 [最终验收](docs/final-release/FINAL_ACCEPTANCE.md) 和 [使用指南](docs/final-release/USER_GUIDE.md)。现有报告可直接生成影响侧车。两个已验证、方向与产品谱系一致的报告可生成历史回归索引。只有显式配置的 GCC/Clang SDK 和已授权的隔离目标才能用于运行矩阵。
