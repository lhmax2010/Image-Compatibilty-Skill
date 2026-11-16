# Tizen Image Compatibility Skill

用于比较 **GCC 与 LLVM/Clang 构建的 Tizen OS 镜像**的 Codex Skill，以及可独立运行的 Python 兼容性检测框架。

默认执行离线分析，比较二进制、开发接口和系统接口，并生成带证据的兼容性报告。检查方向是：**依赖 baseline 接口的应用，能否在 candidate 环境继续工作**。需要验证反向兼容时，交换两个输入再运行一次。

> 当前版本提供可运行的离线分析、SDK 编译探针和可配置的目标运行适配器。无法完成或证据不足的检查标为 `UNKNOWN`。仓库中的示例全部为合成数据，不代表任何真实 Tizen 版本的兼容性结论。

## 快速开始

推荐在 Linux 上使用 Python 3.10 或更新版本。

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

## 作为 Codex Skill 使用

Skill 入口是 [SKILL.md](.agents/skills/tizen-image-compatibility/SKILL.md)。在此仓库的 Codex 会话中可以显式调用：

```text
$tizen-image-compatibility
比较以下两个 Tizen 镜像，执行离线兼容性检测并生成报告：
baseline=/path/to/tizen-gcc-rootfs
candidate=/path/to/tizen-llvm-rootfs
output=./reports/gcc-vs-llvm
```

也可以把完整技能目录复制到另一个项目中，保留内部目录结构：

```bash
mkdir -p /path/to/project/.agents/skills
cp -R .agents/skills/tizen-image-compatibility /path/to/project/.agents/skills/
```

Python CLI 可独立使用，不依赖 Codex 或在线服务。

## 检测能力

| 范围 | 当前能力 | 主要边界 |
|---|---|---|
| ELF / ABI | ELF 架构和类型、导入/导出符号、符号版本、数据/TLS 符号大小、C++ RTTI/vtable 符号；可选 libabigail | 完整类型布局需要可用调试信息；相同符号不等于完整 ABI 相同 |
| 公共 API / 头文件 | 安装路径、声明、宏、包含依赖、条件编译信息、注释/空白归一化 | 保守词法分析，不是完整 C/C++ AST 或类型解析器 |
| 动态链接 | SONAME、DT_NEEDED、加载器、RPATH/RUNPATH、库提供者、依赖环 | 不完整模拟实际加载器的搜索顺序、命名空间和符号解析 |
| RPM / SDK | 名称、版本、架构、Provides/Requires/Conflicts/Obsoletes、文件列表、pkg-config/CMake 配置 | 不安装 RPM，不执行脚本，不实现包依赖求解器 |
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

头文件矩阵覆盖 GCC 镜像/LLVM 镜像分别使用 GCC 和 Clang 编译。运行矩阵把同一个 GCC 产物和同一个 Clang 产物分别送入两个目标环境执行，避免把“重新编译成功”误当作二进制兼容。

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

严重性分为 `CRITICAL`、`HIGH`、`MEDIUM`、`LOW`、`INFO`。差异不会自动被判为不兼容，例如 RPM release 变化和仅有注释/空白的头文件变化。

```bash
python3 "$SKILL/scripts/tizen_compat.py" \
  --baseline ./images/gcc-rootfs --candidate ./images/llvm-rootfs \
  --fail-on HIGH --exclude performance \
  --output ./reports/ci
```

| 退出码 | 含义 |
|---|---|
| `0` | 没有命中所配置失败阈值，不代表所有检查通过 |
| `1` | 不兼容项达到阈值，或 `--strict` 检测到 UNKNOWN |
| `2` | 输入或配置无效 |
| `3` | 执行基础设施错误 |

默认 `--fail-on HIGH` 包含 HIGH 和 CRITICAL。`--strict` 对任何 UNKNOWN 也返回失败；离线运行通常存在 UNKNOWN。`--exclude abi,runtime,performance` 可排除维度。详见 [分类规则](.agents/skills/tizen-image-compatibility/references/severity_rules.md)。

## 合成示例与验证

预生成示例位于 [examples/synthetic-report](.agents/skills/tizen-image-compatibility/examples/synthetic-report)。GitHub 文件视图不会直接执行 HTML 报告，可克隆后在浏览器中打开 `index.html`，或本地查看：

```bash
python3 -m http.server 8000 --bind 127.0.0.1 \
  --directory "$SKILL/examples/synthetic-report"
```

访问 `http://127.0.0.1:8000/`。示例故意移除符号、修改数据大小和 D-Bus 签名等，报告包含 **7 条不兼容 finding**。其运行时矩阵全部为 UNKNOWN，两个镜像夹具均由宿主编译器生成，不能作为真实 GCC/LLVM Tizen 对比结果。

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

已验证的套件包含 36 项测试，覆盖实际 ELF/RPM 采集、语义归一化、源文件不变性、归档路径安全、缺失工具、缓存、manifest 复用、报告、CI 阈值、GCC 头文件编译和合成运行适配器。依赖宿主工具的测试在工具缺失时可能跳过。当前测试环境没有完成真实 Tizen、Clang SDK、libabigail 或设备/QEMU 集成验证。

## 目录与进一步阅读

```text
.agents/skills/tizen-image-compatibility/
├── SKILL.md
├── agents/openai.yaml
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
