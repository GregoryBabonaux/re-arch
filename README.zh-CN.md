# re-arch

[English](README.md) | [Français](README.fr.md) | [Español](README.es.md) | [Deutsch](README.de.md) | [Português](README.pt-BR.md) | [Italiano](README.it.md) | **简体中文** | [日本語](README.ja.md) · **[网站](https://gregorybabonaux.github.io/re-arch/?lang=zh)**

![re-arch 报告：摘要和领域地图](docs/images/banner.png)

一套智能体技能（agent skill），用于审计现有应用的架构，提出按理解成本与实施成本评估的目标架构，规划重构，向管理层论证方案，围绕选定的目标架构约束 AI 编码智能体与 CI，并基于团队自己的代码生成培训材料。适用于任何代码库，尤其适合氛围编程（vibe coding）或 AI 生成的代码库。

支持的技术生态：JavaScript / TypeScript、PHP、.NET (C#)、Java / Kotlin、C / C++、Go、Rust。

## 产出内容

在仓库上运行 `re-arch-audit`，会在 `.re-arch/` 中得到：

- 应用的**领域地图**（业务领域、依赖关系、以 C4 上下文视图呈现的外部系统、模糊地带、各领域的置信度），即使目录结构毫无意义也能生成；
- 一份**诊断报告**，每个问题都引用具体文件和行号，说明其对团队和业务的影响以及修复规模，同时列出应保留的优点、**看起来糟糕但其实没问题的部分**，以及需要向维护者确认的开放问题；
- **2 到 4 个目标方案**（从"定向重构，保持现有结构"到分层架构、垂直切片（vertical slices）、模块化单体、整洁架构 / 六边形架构，在代码确有依据时还包括 CQRS 或事件溯源），每个方案都按**理解成本**和**实施规模**（S、M、L、XL）评估，并对照业务的**质量场景**打分，不同领域可以采用不同方案，同时列出考虑过但被否决的架构风格；
- 一份按 T-shirt 尺码估算、标准明确的**分阶段重构计划**：先用特征测试（characterisation tests）建立安全网，每一步都附带 `verify` 命令，设置阶段出口关卡（exit gate）、回滚方案和停止点，并覆盖所有严重和高优先级问题；
- 一份**面向管理层的提案**：风险、包括"什么都不做"在内的各个选项、以产能区间表示的投入及其推导过程、里程碑、指标，以及需要做出的决策；
- **护栏（guardrails）**：根目录及各领域的 AGENTS.md，一个告诉智能体新代码应该放在哪里的项目技能（skill），一个在智能体自身回合内运行架构检查的**智能体钩子（hook）**，以**冻结基线（baseline）**方式引入 CI 的适应度函数（fitness functions）（每个生态使用原生工具，外加一个与语言无关的检查器），一份 ADR（MADR 4），以及一份代码评审清单；
- 一套**学院课程**：与重构计划对齐的学习路径，课程模块基于仓库中的真实文件（重构前后对比、编程练习（kata）、评审问题），以及精选阅读材料；
- 一份汇总所有内容的**响应式 HTML 报告**，已通过数据契约校验并在手机宽度下检查过渲染效果，可打印为 PDF，另附可放入仓库文档的 Mermaid 图；
- 一个包含架构知识（系统、领域、外部系统、决策、规则、路线图、历史）的 **[Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) (OKF v0.2) 包**，可提交到 `docs/architecture/okf/` 下，供开发者、编码智能体和知识目录使用；信任字段标明哪些内容已经过团队确认，敏感内容不会包含在内；
- **复审**，展示哪些问题已解决、哪些是新出现的，以及各项指标的变化。

## 报告示例

由 re-arch 为 *Factureo* 生成。Factureo 是为评测编写的一个虚构的 vibe coding 发票应用（报告为法语）。[下载完整报告](docs/example/report-factureo.html)，在浏览器中打开。

**领域地图**：业务领域及其依赖关系，相互依赖以橙色显示。

![领域地图](docs/images/domain-map.png)

**方案**：2 到 4 个目标架构，每个都按理解成本和实施规模评估，并对照业务的质量场景打分。

![方案](docs/images/options.png)

**计划**：各阶段的规模、完成标准、回滚方式和可停止点。

![计划](docs/images/plan.png)

**手机端**：每个标签页都在 390 px 宽度下检查。

![手机端](docs/images/mobile.png)

## 技能

| 技能 | 职责 | 脚本 |
|---|---|---|
| `re-arch-audit` | 编排器，设置领域确认和方案选择的检查点，复审模式 | `diff_rearch.py` |
| `re-arch-scan` | 依赖图（尽可能达到编译器级精度）、DI 装配、构建单元、耦合、循环依赖、热点、协同变更、知识分布、重复代码、数据模型、路由、外部系统、依赖健康度、密钥泄露 | `scan.py`, `precise.py`, `di.py`, `insights.py`, `ts_resolve.js`, `php_refs.php` |
| `re-arch-domains` | 基于 import + DI + 协同变更 + 数据模型 + 路由识别业务领域 | `cluster.py` (Louvain) |
| `re-arch-diagnose` | 附带证据、严重程度和修复规模的问题清单；带有"不应标记"列表的坏味道目录 | |
| `re-arch-options` | 目标架构、双维度规模评估、质量场景、决策论证表、架构风格目录、各生态惯用做法 | |
| `re-arch-plan` | 分阶段计划、可验证的步骤、出口关卡、渐进式重构技术 | `plan_to_md.py` |
| `re-arch-pitch` | 面向管理层的论证 | `pitch_to_md.py` |
| `re-arch-guardrails` | 智能体规则、项目技能、智能体钩子、带基线的适应度函数、ADR | `check_architecture.py`（+ 内置的扫描器副本） |
| `re-arch-academy` | 基于团队自有代码的培训材料 | |
| `re-arch-report` | HTML 报告、契约校验、渲染检查、Mermaid 与 OKF 导出 | `render.py`, `validate.py`, `check_render.py`, `to_okf.py` |

每个技能也可以单独使用。它们通过 `.re-arch/` 中的 JSON 文件交换数据；数据契约定义在 `skills/re-arch-audit/references/contract.md` 中，并由 `validate.py` 强制校验。

## 依赖图的精度如何？

扫描在可用时会调用语言自身的工具，并在"Graph sources"部分注明；否则回退到基于正则的解析。

| 生态 | 精确数据源 | 前提条件 |
|---|---|---|
| C/C++ | `compile_commands.json`（真实的 `-I`/`-D`）+ 预处理器 include 树 | 编译数据库（CMake `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`、`bear`）、编译器 |
| Go | `go list`（构建标签、精确的模块路径） | Go 工具链 |
| Rust | `cargo metadata`（crate 依赖图、跨 crate 的 `use`） | Cargo |
| Java/Kotlin | 对已编译 class 运行 `jdeps` | JDK 以及已构建的项目 |
| .NET | `.csproj` ProjectReference 依赖图（剔除不可能存在的边） | 无 |
| JS/TS | TypeScript 自身的模块解析器 | 仓库中有 `typescript`，或使用 `--fetch-tools` |
| PHP | 支持完整名称解析的 PHP tokenizer | `php` 可执行文件 |

依赖注入单独解析（.NET 服务注册、NestJS/Angular providers、Laravel 绑定与 facade、Symfony 服务、Spring `@Bean`、Google Wire、单一实现），生成**运行时边**，与 import 分开存放：分层规则使用 import，耦合与领域划分则同时使用两者。反射和基于约定的扫描仍然无法识别，每份报告都会明确说明这一点。

## 设计原则

- **先证据，后观点**：先运行确定性扫描；每个问题都指向代码，诊断报告也会展示哪些内容被有意判定为无需标记。
- **不预设架构**：始终提供一个轻量方案，每个方案都必须有代码中的信号作为依据，并对照质量场景打分；整洁架构、六边形架构和洋葱架构只是一个选项，而不是质量等级。"保持现有架构"也是合理的结论。
- **成本透明**：理解成本与实施规模并列展示。
- **用尺码，不用天数**：采用标准明确的 T-shirt 尺码；XL 意味着"需要拆分"；管理层得到的是附带推导过程的产能区间。
- **两类受众**：技术团队获得证据和可验证的步骤，管理层获得风险和待决策事项。
- **让重构成果持续有效**：冻结基线的适应度函数、智能体钩子、按领域划分的智能体规则、基于本仓库的培训、定期复审。
- **人不是问题项**：知识集中度以化名（`A1`、`A2`）呈现，映射关系仅保存在本地。

## 环境要求

- Python 3.8+（核心功能仅依赖标准库）。
- 可选，用于精确模式：上述各语言工具链；TypeScript 解析器需要 Node。
- 可选：Playwright + Chromium，用于检查报告渲染（`pip install playwright && python -m playwright install chromium`）。
- 可选：被审计仓库的 git 历史（用于协同变更、热点、知识分布分析；避免使用浅克隆）。

## 安装

**Claude Code**（一步完成，需 Claude Code 2.1.275 或更高版本）：

```
/plugin install re-arch --marketplace GregoryBabonaux/re-arch
```

较早的版本：先运行 `/plugin marketplace add GregoryBabonaux/re-arch`，再运行 `/plugin install re-arch@re-arch`。

**其他任何智能体**（Codex、Cursor、Gemini、Copilot 等）：

```
npx skills add GregoryBabonaux/re-arch
```

加上 `-g` 可为所有项目安装。

然后在要审计的项目中直接提问：*“审计这个仓库的架构”*。

更新：`claude plugin update re-arch@re-arch`（Claude Code）或 `npx skills update`。

## 开发

- `python3 tests/test_suite.py -v`：在各生态的夹具仓库（fixture）上运行 34 个测试。每个夹具都埋设了正则解析层会出错的陷阱（宏计算的 include、include 目录冲突、跨 crate 的 `use`、内联限定名、跨项目的命名空间冲突、构建标签、同命名空间的 PHP 引用），并验证精确解析层和 DI 提取能正确处理；此外还覆盖检查器基线与钩子、契约校验、手机宽度下的渲染、复审差异、OKF 导出（规范符合性、信任字段、日志历史、不含敏感内容）。缺少相应工具链时，依赖该工具链的测试会被跳过。
- 修改扫描器后运行 `python3 tools/sync.py`（guardrails 技能内置了一份副本）；在 CI 中使用 `--check`。
- `evals/`：端到端评测（`evals.json`，由 `evals/grade.py` 评分），其中包括一个健康的仓库，正确答案是"不要迁移到六边形架构"；以及用于测试技能描述触发效果的查询（`triggers.json`）。
- `.github/workflows/tests.yml` 会运行以上全部内容。
