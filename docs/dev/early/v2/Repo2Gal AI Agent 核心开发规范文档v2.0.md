# **Repo2Gal - AI Agent Development Specification (V2.0)**

> **版本变更摘要（V1.1 → V2.0）：**
> - 新增 CLI 完整命令规范、退出码定义
> - 新增 `story_data.json` 完整 Schema（含选择肢、变量系统、条件分支）
> - 新增 `assets_config.json` 完整覆盖（BGM / SE / CG / UI 主题）
> - 新增 Data Pipeline → LLM 中间契约（Context JSON Schema）
> - 新增错误处理策略、日志与可观测性规范
> - 新增 Prompt 模板文件覆盖机制
> - 新增 WebGAL 产出目录结构定义
> - 新增开发环境与依赖声明
> - 新增附录：JSON Schema、西幻世界观映射表、WebGAL 指令映射接口
>
> **最近修订（V2.0 深度评估修正）：**
> - 🔧 **剧情线性化策略：** LLM 只输出线性叙事段 + 选择节点声明 + 结局声明，Compiler 负责后编译分支分解（见 §3.2.4、§6.2、§6.5）
> - 🔧 **show_code_board 降级映射：** 定义三层降级策略确保在不修改 WebGAL 源码的前提下渲染代码展示（见 §6.5.2）
> - 🔧 **LLM 结构化输出强化：** 增加 JSON Mode / response_format 约束与 Schema 自动修复重试循环（见 §3.2.3）
> - 🔧 **音频格式统一：** SE/BGM 统一指定为 `.mp3` 或 `.ogg`，不再使用 `.wav`（见 §6.1）

---

## **1. 项目愿景 (Project Vision)**

**Repo2Gal** 是一个将开源 GitHub 仓库转换为可交互式视觉小说（Galgame）的工具流。
本项目旨在通过 LLM 技术，将枯燥的代码结构、复杂的提交历史和文档，转化为带有剧情、角色互动的沉浸式阅读体验，从而极大地降低开源项目的理解门槛。

---

## **2. 核心架构约束 (CRITICAL CONSTRAINTS — 必读)**

为保证项目的高可维护性和未来扩展性，所有参与开发的 AI Agent 及开发者必须严格遵守以下原则：

### 2.1 确定性脚本与 AI 职责分离 (Pipeline Separation)

> * **数据拉取与清洗必须由程序脚本执行**，直接接收一个或多个仓库 URL 进行自动化拉取，**不依赖 LLM 的 Agent Skill/Tool Calling 过程**。
> * **LLM 仅参与：** 仓库结构与文本分析、人设萃取、三维世界观映射、剧情/对话生成。
> * **Pipeline 合约：** Data Pipeline 产出的 Cleaned Context 必须符合 **第 6.3 节 Context JSON Schema**，LLM Processor 产出的 `story_data.json` 必须符合 **第 6.2 节 Story Schema**。任何一方的输出不符合 Schema 即判定为该阶段失败。

### 2.2 绝对解耦 (Strict Decoupling)

> * **禁止硬编码 (No Hardcoding)：** 所有的剧情文本、角色立绘路径、背景音乐/图片路径 **必须**与代码逻辑和核心引擎完全解耦，统一通过 `assets_config.json` 管理（Schema 见 **第 6.1 节**）。
> * **缺省资源策略：** V1 开发中，所有多媒体资源统一使用缺省占位符。占位符文件必须预置在 `assets/` 模板目录中，确保 Compiler 产出物在无外部网络下也能正常加载（黑屏/静音但无报错）。
> * **资源路径解析：** `assets_config.json` 中的所有路径均为 **相对于 WebGAL 项目根目录的相对路径**，由 Compiler 负责在打包时将占位符替换/拷贝至正确位置。

### 2.3 WebGAL 引擎黑盒原则 (Black-box Engine)

> * **禁止修改源码：** 必须直接使用 [OpenWebGAL/WebGAL](https://github.com/OpenWebGAL/WebGAL) 引擎的标准发行版，**绝对禁止**修改引擎本身的源代码。
> * **适配器/编译器模式：** 本项目的核心工作是"生成 WebGAL 可识别的脚本文件"，通过本地格式化编译器生成打包产物（产出目录结构见 **第 6.4 节**）。
> * **接口占位：** WebGAL `.txt` 脚本的具体语法格式由实现者在开发 Compiler 时参考 [OpenWebGAL 官方文档](https://docs.openwebgal.com/) 确定，本文档不硬编码语法细节。所有 Compiler 支持的指令映射关系必须记录在 `compiler/webgal_commands_mapping.json` 中（见 **附录 C**）。

### 2.4 V1 世界观锁定 (V1 Worldview)

> * 当前版本世界观统一限制为 **"简单西幻世界观 (Western Fantasy)"**。
> * 概念映射必须遵守 **附录 B** 中的映射表，禁止自由发挥产生世界观不一致。
> * 后续版本可通过 `worldview_config.json` 切换世界观插件。

---

## **3. 系统架构与模块职责 (System Architecture)**

整体系统划分为 **自动化数据流水线 (Data Pipeline)**、**AI 处理中枢 (Core LLM Processor)** 和 **表现层 (Presentation Engine)** 三层。

```
[ 用户输入: 1~N 个 GitHub Repo URLs ]
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. 自动化数据流水线脚本 (Deterministic CLI / Script)        │
│  - 执行 repo2txt -> 提取代码树 & 关键源码文本               │
│  - 执行 github_analyzer -> 获取 Commits/Issues 数据         │
│  - 数据清洗器 (Data Cleaner) -> 过滤冗余，输出 Context JSON │
│                             │                               │
│             Context JSON (Schema: §6.3)                     │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. AI 处理中枢 (LLM Processor)                              │
│  - Prompt 模板加载与覆盖 (§3.2.1)                          │
│  - 注入西幻世界观映射                                       │
│  - 剧情与人设生成 -> 输出 story_data.json (Schema: §6.2)   │
└─────────────────────────────┬───────────────────────────────┘
                              │ story_data.json + assets_config.json
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. WebGAL 剧本编译器 (WebGAL Compiler)                      │
│  - 将 story_data.json 编译翻译为 WebGAL 标准 .txt 剧本      │
│  - 结合 assets_config.json 拷贝/映射资源文件                 │
│  - 输出可直接被 WebGAL 引擎加载的项目目录                   │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
                [ OpenWebGAL 引擎直接加载渲染 ]
```

### 3.1 Fetcher & Data Pipeline (自动化脚本层)

直接由本地命令行脚本调用现成工具拉取，无需 AI 介入决策。

> **3.1.1 仓库结构与代码内容提取**
> * **工具：** [donoeidon/repo2txt](https://github.com/donoeidon/repo2txt)
> * **职责：** 输入 GitHub URL，输出仓库文本化结构与核心文件内容。
> * **集成方式：** 子进程调用（`subprocess`）。接口契约：CLI 参数与输出格式由实现者查阅 repo2txt 文档确定，产出结果转化为 Context JSON 中 `structure` 和 `source_code` 字段。
>
> **3.1.2 历史与社区数据提取**
> * **工具：** [Oltrematica/github_analyzer](https://github.com/Oltrematica/github_analyzer)
> * **职责：** 获取 Commits、Issues、PRs 及核心贡献者列表。
> * **集成方式：** 子进程调用（`subprocess`）。接口契约同上，产出结果转化为 Context JSON 中 `history` 和 `community` 字段。
>
> **3.1.3 数据清洗器 (Data Cleaner)**
> * **过滤规则：**
>   * 排除 `.git/`、`node_modules/`、`__pycache__/` 等构建/依赖目录
>   * 排除二进制文件（通过文件扩展名 + magic bytes 判断）
>   * 排除大型 Lock 文件（`package-lock.json`、`yarn.lock`、`Cargo.lock`、`poetry.lock`）
>   * 单个源文件超过 **8000 字符**时截断并标记 `"truncated": true`
> * **Commit 提炼规则：**
>   * 保留标记为 `feat!`、`BREAKING CHANGE`、`release`、`major` 的事件
>   * 保留影响文件数 >= 10 个的 Commit
>   * 保留带有 `fix:` 标记且关联已关闭 Issue 的安全/关键 Bug 修复
>   * 若 Commit 总数 > 500，按上述优先级排序后取 Top 200
> * **Token 预算控制：** Cleaner 产出的 Context JSON 序列化后不得超过 **128KB**（约 32K tokens），超出时按 `source_code > history > community` 的优先级逐步截断各字段。

### 3.2 Core LLM Processor (AI 处理中枢)

负责吸收清洗后的 Context JSON，输出纯粹的结构化剧情数据。

> **3.2.1 Prompt 模板覆盖机制 (Template Override)**
> * Pipeline 内置默认 System Prompt 模板文件：`prompts/system_default.txt`
> * 人类开发者可通过 CLI 参数 `--prompt-override <file>` 指定自定义模板文件
> * LLM Processor 启动时检查 override 文件是否存在，存在则**完全替换**默认模板（非合并）
> * 模板中必须包含占位符 `{{CONTEXT_JSON}}` 和 `{{MODE}}`，由 Processor 在运行时注入
> * 模板式样参考：[the-pocket/pocketflow-tutorial-codebase-knowledge](https://github.com/the-pocket/pocketflow-tutorial-codebase-knowledge)
>
> **3.2.2 LLM 调用抽象**
> * **模型选择：** 不锁定具体模型。通过环境变量配置：
>   * `REPO2GAL_LLM_API_KEY` — API Key（必填，缺失则 Pipeline 启动失败）
>   * `REPO2GAL_LLM_BASE_URL` — API Base URL（默认：`https://api.openai.com/v1`）
>   * `REPO2GAL_LLM_MODEL` — 模型标识符（默认：`gpt-4o`）
>   * `REPO2GAL_LLM_TEMPERATURE` — 采样温度（默认：`0.7`）
>   * `REPO2GAL_LLM_MAX_TOKENS` — 输出最大 Token 数（默认：`16384`）
> * **兼容性要求：** LLM 调用接口必须兼容 OpenAI Chat Completions API 格式
> * **速率限制：** 调用间隔 >= 2 秒，由 Processor 内置退避逻辑
>
> **3.2.3 结构化输出与重试（Structured Output & Retry Loop）**
> * **JSON Mode 强制约束：** 调用 LLM 时必须启用 Structured Output / JSON Mode（如 OpenAI 的 `response_format: { type: "json_object" }` 或 `response_format: { type: "json_schema", json_schema: {...} }`），从协议层确保 LLM 返回合法 JSON，减少第一轮失败率。
> * **三级 Schema 校验：** Processor 收到 LLM 输出后执行逐级校验：
>   1. **语法校验：** `json.loads()` — 是否为合法 JSON？
>   2. **结构校验：** `jsonschema.validate()` — 是否符合 §6.2 story_data.json Schema？
>   3. **语义校验：** segment ID 唯一性、choice `next_segment` 可达性、`set_var` key 在 `variables` 中存在
> * **自动修复重试循环（Auto-Repair Retry Loop）：**
>   1. **Round 1（语法错误）：** 追加提示 `Your response was not valid JSON. Please output ONLY raw JSON without markdown code fences.` 重试，保持原 temperature
>   2. **Round 2（结构/Schema 不匹配）：** 将 jsonschema 报错信息注入提示 `Schema validation failed: {errors}. Fix the JSON to match the required structure.` 并降低 temperature 至 0.3 重试
>   3. **Round 3（语义校验失败或残留）：** 将语义错误注入并降低 temperature 至 0.1 重试
>   4. **Round 3 仍失败：** Pipeline 终止，输出 `story_data.json.failed` + 校验错误日志，退出码 `4`
> * **Token 超限处理：** 若 Context JSON 超出模型上下文窗口，按 `source_code > history > community` 优先级裁剪各字段至适配。
>
> **3.2.4 生成策略：剧情线性化与编译器后拆分（Linearize & Decompile）**
>
> **核心原则：LLM 不负责复杂分支逻辑，只生成纯线性叙事。**
>
> 在 V2.0 原设计中，要求 LLM 在单次调用中同时输出 11 种 Action、嵌套条件分支、变量追踪和多结局路由——这在实践层面极易触发 JSON 截断、幻觉跳转死循环或 Schema 校验失败。
>
> V2.0 修正方案将生成职责拆分为两层：
>
> | 层级 | 负责方 | 产出 | 复杂度 |
> |------|--------|------|--------|
> | **叙事层 (Narrative)** | LLM | 线性叙事段 (Segments) + 选择节点声明 (Choices) + 结局声明 (Endings) | 低——纯线性编排 |
> | **分支编译层 (Branching Compilation)** | Compiler 脚本 | WebGAL `.txt` 带 `choose`/`jump`/`setVar`/`if` 指令 | 中——确定性图遍历 |
>
> **LLM 只做三件事：**
> 1. 将故事拆分为独立的线性叙事段（Segment），每个 Segment 是单向的 Action 序列
> 2. 在适当位置声明选择节点（Choice），指明"当前 Segment 之后"弹出哪个选择、每个选项跳转到哪个 Segment、设置什么变量
> 3. 声明结局点（Ending），指明"某个 Segment 之后"游戏结束
>
> **LLM 明确不需要做的事：**
> - 不需要写 `condition`（条件判断）
> - 不需要理解 `gt`/`gte`/`and`/`or` 等逻辑运算
> - 不需要跟踪变量流转
> - 不需要关心 WebGAL `.txt` 底层语法
>
> **Compiler 接管这些：**
> - 读取所有 Segments，生成对应的 WebGAL `.txt` 文件并按顺序或按 Choice 跳转编排场景流
> - 在 Choice 节点后注入 `setVar` 指令
> - 若检测到多个 Choice 路径汇聚到同一 Segment，自动注入 WebGAL `if` 条件守卫（见 §6.5）
> - 将 Ending 声明编译为结局展示 + `end` 指令

### 3.3 Compiler & Presentation (编译器与表现层)

> * **Compiler 职责（扩展）：** 确定性程序脚本，不仅仅是 JSON→`.txt` 的语法转换器，还承担 **分支分解、变量注入、代码板降级** 三项编译时逻辑（详见 **第 6.5 节**）。
> * **输入：** `story_data.json` + `assets_config.json`
> * **产出目录结构：** 见 **第 6.4 节**。
> * **WebGAL 引擎：** [OpenWebGAL/WebGAL](https://github.com/OpenWebGAL/WebGAL) (MPL-2.0)，黑盒调用，加载 Compiler 产出的项目目录。

---

## **4. CLI 命令规范 (CLI Specification)**

### 4.1 命令签名

```bash
repo2gal --repo <URL> [--repo <URL> ...] --mode <MODE> [OPTIONS]
```

### 4.2 参数定义

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--repo` | `string` (可重复) | 是 | — | GitHub 仓库 URL，至少 1 个，支持 `https://` 和 `git@` 格式 |
| `--mode` | `enum` | 是 | — | 生成模式：`overview` / `quick_start` / `immersive_history` |
| `--multi-repo` | `enum` | 否 | `separate` | 多仓库处理策略：`separate`（各自独立故事）/ `merged`（合并为一个故事） |
| `--output-dir` | `string` | 否 | `./output` | WebGAL 项目产出目录 |
| `--temp-dir` | `string` | 否 | `./.tmp` | 临时工作目录（存放 raw_data、中间文件） |
| `--prompt-override` | `string` | 否 | — | 自定义 System Prompt 模板文件路径 |
| `--log-level` | `enum` | 否 | `info` | 日志级别：`debug` / `info` / `warning` / `error` |
| `--log-file` | `string` | 否 | — | 日志文件路径（不指定则仅 stdout） |
| `--dry-run` | `flag` | 否 | `false` | 仅执行 Data Pipeline，输出 Context JSON 到 stdout，不调用 LLM |
| `--version` | `flag` | 否 | — | 输出版本信息后退出 |
| `--help` | `flag` | 否 | — | 输出帮助信息后退出 |

### 4.3 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `REPO2GAL_LLM_API_KEY` | 是 | — | LLM API Key（Pipeline 启动时检查，缺失则拒绝运行） |
| `REPO2GAL_LLM_BASE_URL` | 否 | `https://api.openai.com/v1` | LLM API 端点 |
| `REPO2GAL_LLM_MODEL` | 否 | `gpt-4o` | 模型标识符 |
| `REPO2GAL_LLM_TEMPERATURE` | 否 | `0.7` | 采样温度 (0.0–2.0) |
| `REPO2GAL_LLM_MAX_TOKENS` | 否 | `16384` | 输出最大 Token 数 |
| `REPO2GAL_GITHUB_TOKEN` | 否 | — | GitHub Personal Access Token（用于提升 API 速率限制，缺失则使用未认证请求） |

### 4.4 退出码

| 退出码 | 含义 |
|--------|------|
| `0` | 成功 |
| `1` | 通用错误（未分类的内部异常） |
| `2` | 参数错误（非法参数、缺失必填参数、参数值无效） |
| `3` | 数据拉取失败（repo2txt 或 github_analyzer 执行失败、仓库不存在、网络错误） |
| `4` | LLM 生成失败（三次重试均未产出合法 JSON、Token 超限无法裁剪、API 返回 4xx/5xx） |
| `5` | 编译打包失败（story_data.json Schema 校验失败、Compiler 内部错误） |

### 4.5 使用示例

```bash
# 单仓库 Overview 模式
repo2gal --repo https://github.com/xxx/yyy --mode overview

# 多仓库分离模式
repo2gal --repo https://github.com/xxx/yyy --repo https://github.com/xxx/zzz --mode quick_start --multi-repo separate

# Dry-run：仅拉取和清洗，不调用 LLM
repo2gal --repo https://github.com/xxx/yyy --mode overview --dry-run

# 使用自定义 Prompt 模板
repo2gal --repo https://github.com/xxx/yyy --mode immersive_history --prompt-override ./my_prompts/custom.txt
```

---

## **5. 核心游玩模式 (Three Core Modes)**

系统必须支持在运行 CLI 时，通过 `--mode` 参数指定以下三种剧本生成模式之一。

### Mode 1: 仓库概览 (Repository Overview)

> * **模式标识：** `overview`
> * **目标受众：** 需要快速了解该仓库"是干什么的"、"怎么用"的使用者。
> * **剧情风格：** 新手村向导 / 冒险者公会任务发布。
> * **参考标杆：** the-pocket/pocketflow-tutorial-codebase-knowledge
> * **AI 侧重点：** README 解析、顶层 API 调用说明、核心 Features 展示。
> * **代码详细度约束：** 仅限接口/签名级别说明，不对函数体内部逻辑展开。若 Context JSON 中标记了关键函数（`highlights`），可做一句话摘要，不展示完整实现。
> * **动作类型侧重：** `dialogue` + `set_bg`，少量 `show_code_board`。

### Mode 2: 快速上手 (Quick Start / Contributor Guide)

> * **模式标识：** `quick_start`
> * **目标受众：** 希望参与开源贡献 (PR) 或进行二次开发 (Fork) 的开发者。
> * **剧情风格：** 魔法学院导师指导 / 工坊学徒实战。
> * **参考标杆：** Nova42x/paper2galgame
> * **AI 侧重点：** 详细演绎项目目录结构、底层运行原理、核心算法实现方法、如何配置本地开发环境。
> * **代码详细度约束：** 可深入关键函数体内部，但单次 `show_code_board` 的 `code_snippet` 不超过 40 行。
> * **动作类型侧重：** `dialogue` + `show_code_board` + `choice`（Code Quest 答题环节）。
> * **Code Quest 规范：**
>   * 每章至少 1 个 Code Quest（通过 `choice` action 实现）
>   * 问题内容围绕该仓库的核心概念/API/架构，答案为文本选项
>   * 正确/错误选项走不同分支（`target_scene`），附带解释文本

### Mode 3: 沉浸历史 (Immersive History)

> * **模式标识：** `immersive_history`
> * **目标受众：** 对项目生态、社区演变感兴趣的用户，或纯粹的开源文化体验者。
> * **剧情风格：** 史诗叙事 / 历史纪传体，最具 Galgame 沉浸感。
> * **依赖数据：** 高度依赖 Context JSON 中的 `history.commits`、`history.milestones`、`history.contributors`。
> * **边缘情况处理**：
>   * 若 Commits 总数 < 10：降低期望，生成"创世神话"风格的简短叙事，不少于 3 个场景但不超过 10 个场景
>   * 若 Commits 总数 > 5000（已截断至 Top 200）：在开篇旁白中提示"本故事仅节选关键事件"，避免叙事不连贯
> * **动作类型侧重：** `dialogue` + `set_bg` + `set_bgm` + `transition` + `ending`，适当加入 `choice` 增强叙事体验。

---

## **6. 数据结构与解耦规范 (Data Schema & Decoupling Standard)**

> **Schema 约定：** 本文档中所有 JSON 示例使用 TypeScript 风格的类型注释描述字段类型。附录 A 提供可机器校验的 JSON Schema 定义文件。

### 6.1 资产映射表 (assets_config.json)

配置文件管理所有多媒体资源。Compiler 在编译时读取此文件，将占位符资源拷贝至 WebGAL 项目的 `assets/` 目录下。

```jsonc
{
  // 资产映射表版本号，与 Pipeline 版本联动
  "version": "2.0",

  // --- 角色定义 ---
  // key: 角色标识符 (用于 story_data.json 中 speaker/target 字段引用)
  "characters": {
    "guide_npc": {
      "name": "艾尔 (Al)",            // 角色全名 (含英文标识)
      "display_name": "艾尔",         // 对话中显示的名称
      "description": "冒险者公会的向导，热情耐心，适合 Mode 1 Overview 的新人引导", // 给 LLM 的角色设定（不渲染到前端）
      "sprites": {
        "normal":   "assets/chars/al_normal_placeholder.png",
        "happy":    "assets/chars/al_happy_placeholder.png",
        "surprised":"assets/chars/al_surprised_placeholder.png",
        "serious":  "assets/chars/al_serious_placeholder.png",
        "thinking": "assets/chars/al_thinking_placeholder.png"
      }
    },
    "mage_teacher": {
      "name": "梅林 (Merlin)",
      "display_name": "梅林",
      "description": "魔法学院的导师，严谨博学，适合 Mode 2 Quick Start",
      "sprites": {
        "normal":   "assets/chars/merlin_normal_placeholder.png",
        "serious":  "assets/chars/merlin_serious_placeholder.png",
        "explain":  "assets/chars/merlin_explain_placeholder.png"
      }
    }
    // 更多角色按需追加
  },

  // --- 背景图 ---
  // key 用于 story_data.json 中 set_bg action 的 target 字段
  "backgrounds": {
    "guild_hall":      "assets/bgs/guild_hall_placeholder.jpg",
    "code_dungeon":    "assets/bgs/dungeon_placeholder.jpg",
    "magic_library":   "assets/bgs/magic_library_placeholder.jpg",
    "throne_room":     "assets/bgs/throne_room_placeholder.jpg",
    "black":           "assets/bgs/black_placeholder.jpg"
  },

  // --- 背景音乐 (BGM) ---
  "bgm": {
    "peaceful":   "assets/bgm/peaceful_placeholder.mp3",
    "mysterious": "assets/bgm/mysterious_placeholder.mp3",
    "tense":      "assets/bgm/tense_placeholder.mp3",
    "epic":       "assets/bgm/epic_placeholder.mp3",
    "triumph":    "assets/bgm/triumph_placeholder.mp3"
  },

  // --- 音效 (Sound Effects / SE) ---
  // 格式仅限 .mp3 或 .ogg（Web Audio API 原生友好），禁止使用无压缩 .wav
  "se": {
    "click":  "assets/se/click_placeholder.ogg",
    "magic":  "assets/se/magic_placeholder.ogg",
    "page":   "assets/se/page_turn_placeholder.ogg",
    "error":  "assets/se/error_placeholder.ogg",
    "success":"assets/se/success_placeholder.ogg"
  },

  // --- CG 插图 (全屏大图，用于关键剧情节点) ---
  "cg": {
    "title":        "assets/cg/title_placeholder.png",
    "ending_good":  "assets/cg/ending_good_placeholder.png",
    "ending_true":  "assets/cg/ending_true_placeholder.png",
    "code_reveal":  "assets/cg/code_reveal_placeholder.png"
  },

  // --- UI 主题 ---
  "ui_theme": {
    "textbox":       "assets/ui/textbox_placeholder.png",
    "choice_frame":  "assets/ui/choice_frame_placeholder.png",
    "name_tag":      "assets/ui/name_tag_placeholder.png",
    "font_regular":  "assets/fonts/default_regular.ttf",
    "font_bold":     "assets/fonts/default_bold.ttf",
    "font_code":     "assets/fonts/code_mono.ttf"
  }
}
```

> **占位符要求：**
> - 所有占位符文件必须存在于 `assets/` 模板目录下
> - 图片占位符：单色纯色 PNG/JPG（如 guide_npc 用蓝色 800×1200）
> - 音频占位符：静音文件，时长 >= 2 秒，格式统一为 `.mp3` 或 `.ogg`（Web Audio API 原生支持），禁止 `.wav`
> - 字体占位符：从 Google Fonts / 开源字体库获取

### 6.2 结构化剧本中间态 (story_data.json)

LLM 输出的标准 JSON 结构。**LLM 只负责线性叙事编排，不涉及条件分支逻辑**（由 Compiler 在后编译阶段处理，见 §3.2.4 和 §6.5）。

```jsonc
{
  "version": "2.0",
  "mode": "overview",
  "repo_url": "https://github.com/xxx/yyy",

  // --- 剧本元信息 ---
  "meta": {
    "title": "架构之城的冒险",
    "author": "Repo2Gal",
    "generated_at": "2024-06-15T10:30:00Z",
    "estimated_playtime_minutes": 15,
    "total_segments": 12,
    "description": "一段关于 {repo_name} 的西幻冒险..."
  },

  // --- 线性叙事段 (Segments) ---
  // LLM 生成纯线性流程。每个 segment 是一组顺序 Action 数组。
  // 不含 condition、不含 choice action、不含 ending action —— 这些由顶层声明。
  "segments": [
    {
      "id": "seg_001",
      "chapter": 1,
      "chapter_title": "初入架构之城",

      // Action 序列 (仅限 §6.2.1 表中的 9 种 inline action)
      "actions": [
        { "type": "set_bg", "target": "guild_hall" },
        { "type": "set_bgm", "target": "peaceful", "loop": true, "volume": 0.8 },
        { "type": "show_char", "target": "guide_npc", "emotion": "normal", "position": "center" },
        { "type": "dialogue", "speaker": "guide_npc", "emotion": "happy", "text": "欢迎来到 {repo_name}！我是你的向导，今天我们将一起拆解这座魔法城堡的核心阵法！" },
        { "type": "show_code_board", "title": "核心入口 (src/index.ts)", "code_snippet": "import { App } from './core';\nconst app = new App();\napp.start();", "language": "typescript", "explanation": "一切的起点都在 src/index.ts，App 类的初始化...", "line_highlight": [3] },
        { "type": "transition", "effect": "fade", "duration": 1.0 }
      ]
    },
    {
      "id": "seg_002",
      "chapter": 1,
      "chapter_title": "初入架构之城",
      "actions": [
        { "type": "dialogue", "speaker": null, "text": "穿过公会的长廊，一面巨大的魔法结界映入眼帘……" }
      ]
    }
    // 更多 segment...
  ],

  // --- 选择节点 (Choice Nodes - 顶层声明) ---
  // LLM 声明分支点：在某个 segment 执行完后弹出选择肢，每个选项跳转到不同的 segment
  // Compiler 负责生成 WebGAL choose 指令 + setVar + jump 逻辑（见 §6.5.1）
  "choices": [
    {
      "id": "choice_001",
      "after_segment": "seg_003",
      "prompt": "你想先了解哪个部分？",
      "options": [
        { "text": "探索目录结构", "next_segment": "seg_004", "set_var": { "path": "structure" }, "se": "click" },
        { "text": "查看魔法核心（算法）", "next_segment": "seg_005", "set_var": { "path": "algorithm" } }
      ]
    }
  ],

  // --- 结局声明 (Endings - 顶层声明) ---
  // LLM 声明结局点：在某个 segment 执行完后，展示结局 CG/标题/文本，然后游戏结束
  // Compiler 负责在目标位置生成结局场景 + end 指令（见 §6.5.1）
  "endings": [
    {
      "id": "ending_good",
      "after_segment": "seg_010",
      "ending_type": "good",
      "title": "旅途的开始",
      "text": "你对 {repo_name} 的架构有了初步认识。下一章将带你深入魔法阵的核心..."
    }
  ],

  // --- 全局变量声明 ---
  // 所有 choice 中 set_var 使用的 key 必须在此声明初始值
  // Compiler 在游戏启动时通过 WebGAL setVar 初始化
  "variables": {
    "path": null,
    "quiz_score": 0
  }
}
```

#### 6.2.1 Inline Action 类型完整枚举

以下 9 种 Action 是 LLM 可以在 `segments[].actions[]` 中使用的 **唯一内联动作**。
`choice` 和 `ending` 已从内联动作中移除，改为顶层声明。

| Action 类型 | 必填字段 | 可选字段 | 用途 |
|-------------|----------|----------|------|
| `set_bg` | `type`, `target` | — | 切换背景图片 |
| `set_bgm` | `type`, `target` | `loop`, `volume`, `fade_in_ms` | 切换背景音乐 |
| `set_se` | `type`, `target` | `volume` | 播放一次性音效 |
| `show_char` | `type`, `target`, `emotion`, `position` | — | 显示角色立绘 |
| `hide_char` | `type`, `target` | `transition` | 隐藏角色立绘 |
| `dialogue` | `type`, `speaker`, `text` | `emotion` | 角色对话/旁白（speaker 为 null 或 `"narration"` 时为旁白） |
| `show_code_board` | `type`, `title`, `code_snippet`, `language`, `explanation` | `line_highlight` | 展示代码片段与解释（Compiler 按降级策略渲染，见 §6.5.2） |
| `transition` | `type`, `effect` | `duration` | 场景转场特效（`fade` / `fade_to_black` / `dissolve` / `wipe_left` / `wipe_right` / `none`） |
| `wait` | `type`, `duration` | — | 时间暂停（秒） |

#### 6.2.2 段间流转规则（Compiler 编译时的默认行为）

LLM 输出的 Segments 是**扁平列表**，没有内置跳转逻辑。Compiler 在编译时按以下规则生成场景流转：

1. **默认顺序链接：** 若无 Choice 或 Ending 声明插入，Compiler 在 Segment N 结尾自动跳转到下一个 Segment N+1（按 `segments[]` 数组顺序）
2. **Choice 介入：** 若存在 `after_segment == seg_N` 的 Choice 声明，Compiler 在该 Segment 结尾生成 WebGAL `choose` 指令，选项跳转目标为 `next_segment` 所指向的 label
3. **Ending 介入：** 若存在 `after_segment == seg_N` 的 Ending 声明，Compiler 在该 Segment 结尾生成结局展示序列（CG + title + text），然后 `end`
4. **冲突处理：** 若同一个 `after_segment` 同时有 Choice 和 Ending 声明，Choice 优先（终局 Choice 的场景由 LLM 在叙事中自行处理，如"你要回头看看吗？[是→回忆 Segment] [否→结局 Segment]"）
5. **Chapter 分组：** `chapter` 字段仅用于 Compiler 生成章节显示标题，不影响流程路由。LLM 必须确保跨章节跳转的 `next_segment` 指向有效 Segment

#### 6.2.3 Schema 校验规则

* `segment.id` 在全局必须唯一
* `choices[].after_segment` 必须指向存在的 `segment.id`
* `choices[].options[].next_segment` 必须指向存在的 `segment.id`
* `endings[].after_segment` 必须指向存在的 `segment.id`
* `choices[].options[].set_var` 中的 key 必须在 `variables` 中已声明
* 每个 Segment 的 `actions[]` 必须非空
* `mode` 字段值必须匹配 `overview` / `quick_start` / `immersive_history` 之一
* 任一 Chapter 必须包含至少 1 个 `ending` 声明（否则游戏无退出路径）

### 6.3 上下文数据契约 (Context JSON)

Data Pipeline 产出的标准化中间态，作为 LLM Processor 的唯一输入。**此 Schema 是 Pipeline 与 Processor 之间的硬性合约。**

```jsonc
{
  "version": "2.0",

  // --- 仓库基本信息 ---
  "repo": {
    "url": "https://github.com/xxx/yyy",
    "name": "yyy",
    "owner": "xxx",
    "description": "A cool TypeScript framework for building web apps",
    "topics": ["web", "framework", "typescript"],
    "stars": 1234,
    "forks": 56,
    "language": "TypeScript",
    "license": "MIT",
    "created_at": "2022-03-15T00:00:00Z",
    "updated_at": "2024-06-01T00:00:00Z"
  },

  // --- 目录结构 ---
  "structure": {
    "tree": [
      { "path": "src/", "type": "directory" },
      { "path": "src/index.ts", "type": "file", "size_bytes": 2048, "summary": "Application entry point" },
      { "path": "src/core/", "type": "directory" },
      { "path": "tests/", "type": "directory" }
    ],
    "key_directories": [
      { "path": "src/", "purpose": "核心源码" },
      { "path": "tests/", "purpose": "测试用例" },
      { "path": "docs/", "purpose": "项目文档" }
    ]
  },

  // --- 关键源码内容 ---
  "source_code": [
    {
      "path": "src/index.ts",
      "content": "import { App } from './core/App';\n\nconst app = new App({...});\napp.start();",
      "size_bytes": 2048,
      "highlights": ["应用入口点", "初始化 App 实例", "调用 start() 启动"],
      "truncated": false          // 是否因过长被截断
    }
  ],

  // --- 历史数据 ---
  "history": {
    "total_commits": 450,
    "commits_truncated": false,    // 是否因数量过大被裁减
    "commits": [
      {
        "sha": "abc123def",
        "author": "John Doe",
        "author_email": "john@example.com",
        "date": "2024-01-15T10:30:00Z",
        "message": "feat: add user authentication module",
        "type": "feat",            // feat | fix | docs | refactor | perf | test | chore | ci | release
        "breaking": false,         // 是否为 BREAKING CHANGE
        "files_changed": 15,
        "impact_score": 8          // 内部评分 0–10，用于排序和过滤
      }
    ],
    "milestones": [
      { "version": "v1.0.0", "date": "2023-06-01", "title": "First stable release", "description": "首个稳定版本发布" },
      { "version": "v2.0.0", "date": "2024-03-01", "title": "Major refactor", "description": "核心架构重构" }
    ],
    "contributors": [
      { "name": "John Doe", "email": "john@example.com", "commits": 150, "role": "maintainer" },
      { "name": "Jane Smith", "email": "jane@example.com", "commits": 45, "role": "contributor" }
    ]
  },

  // --- 社区数据 ---
  "community": {
    "issues": {
      "open_count": 23,
      "closed_count": 89,
      "notable_labels": ["bug", "enhancement", "help-wanted", "good-first-issue"],
      "notable_issues": [   // 最多 10 条代表性 Issue
        { "number": 123, "title": "Memory leak in renderer", "state": "closed", "labels": ["bug", "critical"] }
      ]
    },
    "pull_requests": {
      "open_count": 5,
      "merged_count": 120,
      "notable_prs": [      // 最多 10 条代表性 PR
        { "number": 456, "title": "feat: add plugin system", "state": "merged", "author": "jane" }
      ]
    }
  },

  // --- 元数据 ---
  "metadata": {
    "fetched_at": "2024-06-15T10:30:00Z",
    "pipeline_version": "2.0",
    "tool_versions": {
      "repo2txt": "1.2.0",
      "github_analyzer": "0.9.1"
    }
  }
}
```

> **大小限制：** Context JSON 序列化后不得超过 **128KB**。超出时 Cleaner 按 `source_code > history.commits > source_code.highlights > community.notable_*` 优先级逐步截断，并在元数据中标记 `"truncated": true`。

### 6.4 WebGAL 产出目录结构 (Compiler Output)

Compiler 的最终产出为完整的 WebGAL 项目目录，结构如下：

```
output/{repo_name}/
├── index.html                         # WebGAL 加载入口 (由 WebGAL 发行版提供)
├── game/
│   ├── config.txt                     # 游戏配置 (标题、初始 scene、分辨率等)
│   └── scene/
│       ├── start.txt                  # 启动场景 (Compiler 自动生成，跳转到第一个 chapter)
│       ├── chapter_1_scene_001.txt    # 每个 scene 编译为一个 .txt 文件
│       ├── chapter_1_scene_002.txt
│       └── ...
├── assets/
│   ├── chars/                         # 角色立绘 (从 assets_config.json 映射)
│   ├── bgs/                           # 背景图
│   ├── bgm/                           # 背景音乐
│   ├── se/                            # 音效
│   ├── cg/                            # CG 插图
│   ├── ui/                            # UI 组件 (文本框、选项框等)
│   └── fonts/                         # 字体文件
└── assets_config.json                 # 资产映射表副本 (供 WebGAL 运行时读取)
```

> **WebGAL 脚本语法：** Compiler 的 `.txt` 生成规则不在本文档中硬编码，具体语法由实现者查阅 [OpenWebGAL 文档](https://docs.openwebgal.com/) 确定。所有指令映射关系记录在 `compiler/webgal_commands_mapping.json` 中（见 **附录 C**）。

### 6.5 Compiler 后编译逻辑 (Compiler Post-Processing)

Compiler 不仅做语法翻译，还承担 **分支分解** 和 **代码板降级** 两项核心后编译职责。

#### 6.5.1 分支分解与变量注入 (Branching Decomposition)

Compiler 读取 `story_data.json` 中的 `segments[]`、`choices[]`、`endings[]`、`variables`，按以下算法生成 WebGAL 场景：

```
输入: story_data.json
输出: WebGAL .txt 场景文件集

1. WebGAL 启动场景 (start.txt):
   - 声明所有 variables 的初始值 (setVar:path=null ...)
   - jump -> segment_{first_segment.id}

2. 对每个 segment:
   a) 生成 scene 文件，文件名为 segment_{segment.id}.txt
   b) 文件开头: label:segment_{segment.id}
   c) 遍历 segment.actions[]，按附录 C 映射表逐条翻译为 WebGAL 指令
   d) 查找 choices[] 中 after_segment == segment.id 的项:
      - 生成 WebGAL choose 指令
      - 每个 option: text -> label target (segment_{option.next_segment})
      - 选中后在跳转前注入 setVar (将 option.set_var 翻译为 WebGAL setVar)
   e) 查找 endings[] 中 after_segment == segment.id 的项:
      - 显示 ending 的 title 和 text（通过 dialogue action 渲染）
      - 若有 cg 字段，生成 showCG 指令
      - 生成 end 指令
   f) 若既无 choice 也无 ending 在 after_segment:
      - 按 segments[] 数组顺序找到下一个相邻 segment，生成 jump 指令

3. 变量注入时机:
   - 初始化: start.txt 中 setVar 所有 variables 键值
   - Choice 分支: 在 choose 指令内部的选项目标标签之后，第一条指令为 setVar
```

**条件守卫（可选增强）：** 若 Compiler 检测到多个 Choice 路径汇聚到同一 Segment，可自动分析并注入 WebGAL `if` 条件守卫，确保只在正确的路径上下文中进入该 Segment。此功能为 V2.0 可选项，默认关闭。

#### 6.5.2 show_code_board 降级策略 (Code Board Fallback)

`show_code_board` 是 LLM 产出的一个 Action，但 WebGAL 引擎原生**不支持**代码高亮展示板。在不修改 WebGAL 源码（黑盒原则）的前提下，Compiler 采用**三层降级策略**渲染：

| 层级 | 策略 | WebGAL 兼容性 | 视觉质量 |
|------|------|---------------|----------|
| **L1: 样式文本块（首选）** | 利用 WebGAL 文本样式语法渲染：标题用页面标题指令，解释用普通对话，代码块用等宽样式文本块。若 WebGAL 支持自定义 `class` 或 HTML 注入（如 `<div class="code-block">`），则包裹在自定义样式中。 | 高（不修改引擎源码，利用引擎内置的文本/HTML 渲染能力） | 中——有格式化但无语法高亮 |
| **L2: 纯文本降级** | 将 title 渲染为 `<chapter title>`，explanation 渲染为对话，code_snippet 渲染为前缀标注的旁白文本（如 `【代码】\n{code_snippet}\n【/代码】`）。 | 最高（仅使用基础对话/旁白指令） | 低——无格式区分 |
| **L3: 摘要省略** | 若 WebGAL 版本完全不支持任何形式的渲染，将代码展示替换为一句摘要对话："（此处展示 {language} 代码，详见下方解释……）{explanation}"。 | 绝对兼容 | 最低——丢失代码内容 |

Compiler 实现要求：
- 启动时检测 WebGAL 版本能力，自动选择最高可用层级
- 在 `compiler/webgal_commands_mapping.json` 中记录当前版本所使用的层级和具体映射语法
- 日志中 WARNING 级别记录降级触发事件（如 "show_code_board downgraded from L1 to L2: WebGAL version does not support styled text blocks"）

---

## **7. 系统自动化执行流程 (Pipeline Execution Steps)**

当用户执行 `repo2gal --repo <URL> --mode <MODE>` 时，流水线按如下步骤**严格顺序**执行，任一步骤失败即终止后续流程：

### Step 1: 参数校验

* 校验所有 CLI 参数合法性（`--mode` 枚举值、`--repo` URL 格式、环境变量 `REPO2GAL_LLM_API_KEY` 是否存在）
* 校验失败 → 退出码 `2`，打印具体错误信息至 stderr

### Step 2: 数据拉取 (Deterministic Fetching)

* 根据传入的 N 个 Repo URL，**串行/并行**（可配置，默认并行）调用 `repo2txt` 和 `github_analyzer`
* 每个 repo 的数据落盘至 `.tmp/raw_data/{repo_name}/`
* **严格模式：** 任一 repo 拉取失败（工具返回非零退出码 / 网络超时 / 仓库不存在）→ 终止全部任务 → 退出码 `3`
* 超时设置：单个工具调用最长等待 **120 秒**，超时视为失败

### Step 3: 数据清洗 (Preprocessing & Cleaning)

* 脚本读取 `.tmp/raw_data/` 中的原始数据
* 按 **第 3.1.3 节** 定义的过滤规则清洗
* 构建符合 **第 6.3 节** Schema 的 Context JSON
* 若清洗后 Context JSON 为空（仓库无任何有效内容）→ 终止 → 退出码 `3`
* 校验 Context JSON 序列化大小 ≤ 128KB，超出则截断并在 metadata 中标记
* 输出至 `.tmp/context_{repo_name}.json`

### Step 4: 多仓库合并（仅当 `--multi-repo merged`）

* 将多个 Context JSON 合并为一个统一的 Context 对象
* 合并策略：`structure` / `source_code` 字段按 repo 分组嵌套，`history` / `community` 合并数组
* 合并后仍受 128KB 限制，超出时等比例削减各仓库的 `source_code` 内容

### Step 5: LLM 生成 (AI Core Generation)

* 加载 Prompt 模板（默认或 `--prompt-override` 指定的文件）
* 注入 Context JSON + Mode 标识
* 调用 LLM（遵循 **第 3.2.3 节** 的重试策略）
* 解析 LLM 输出为 JSON，校验符合 **第 6.2 节** Schema（见 **第 6.2.3 节** 校验规则）
* 校验失败（三次重试后）→ 输出 `story_data.json.failed` → 退出码 `4`
* 校验通过 → 输出 `.tmp/story_data_{repo_name}.json`

### Step 6: WebGAL 编译打包 (Compilation & Bundling)

* 读取 `story_data.json` + `assets_config.json`
* Compiler 执行 **三段式编译**：
  1. **Schema 校验：** 验证 `story_data.json` 的语义完整性（segment ID 唯一性、`next_segment` 可达性、`set_var` key 在 `variables` 中声明等，见 §6.2.3）
  2. **分支分解：** 按 §6.5.1 算法将 Segments + Choices + Endings 展开为 WebGAL `.txt` 场景文件，注入 `setVar`、`choose`、`jump` 指令
  3. **资源组装：** 按 §6.4 目录结构生成 WebGAL 项目，拷贝占位符资源，`show_code_board` 按 §6.5.2 三层降级策略渲染
* 编译失败 → 退出码 `5`
* 编译成功 → 输出 `output/{repo_name}/` → 退出码 `0`

### Step 7: 清理（无论成功或失败均执行）

* 保留 `.tmp/` 目录中的中间文件用于调试（可通过 `--temp-dir` 自定义路径）
* **注意：** `.tmp/` 在单次运行内累积，多次运行复用同一 `--temp-dir` 时需注意磁盘空间。建议在生产级 wrapper 中添加 `--clean` flag 控制自动清理行为。

---

## **8. 错误处理与日志 (Error Handling & Logging)**

### 8.1 错误处理总则

| 阶段 | 失败类型 | 行为 |
|------|----------|------|
| 参数校验 | 非法参数 / 缺失必填项 | 立即终止，退出码 2，错误信息输出至 stderr |
| 数据拉取 | 工具调用失败 / 超时 / 仓库不存在 | 终止全部，退出码 3，输出失败 repo URL 至 stderr |
| 数据清洗 | Context JSON 为空 / 不符合 Schema | 终止，退出码 3 |
| LLM 生成 | API 错误 (4xx/5xx) | 重试 3 次（间隔 2s/5s/10s），全部失败 → 退出码 4 |
| LLM 生成 | JSON 解析失败 | 三次重试（见 3.2.3），全部失败 → 退出码 4 |
| 编译打包 | Schema 校验失败 / Compiler 内部错误 | 退出码 5，输出具体校验失败明细至 stderr |

### 8.2 日志规范

* **日志级别：**
  * `DEBUG`：函数进入/退出、中间变量、Context JSON 构建细节（仅 `--log-level debug` 时输出）
  * `INFO`：Pipeline 各阶段起止时间、处理 repo 数量、LLM Token 用量
  * `WARNING`：非致命异常（如某个 Commit 被截断、资源占位符缺失但使用了默认值）
  * `ERROR`：导致 Pipeline 终止的错误
* **格式：** JSON Lines (`jsonl`)，每行一条日志记录：

```jsonl
{"ts":"2024-06-15T10:30:01Z","level":"INFO","stage":"fetch","repo":"https://github.com/xxx/yyy","msg":"Fetching repo data"}
{"ts":"2024-06-15T10:30:45Z","level":"WARNING","stage":"clean","repo":"https://github.com/xxx/yyy","msg":"Source file truncated","path":"src/large.ts","size_bytes":12000}
{"ts":"2024-06-15T10:31:00Z","level":"ERROR","stage":"llm","repo":"https://github.com/xxx/yyy","msg":"LLM API returned 500","attempt":3}
```

* **输出目标：**
  * 默认：stdout（INFO 级别及以上）
  * `--log-file` 指定时：文件输出全量日志（含 DEBUG），stdout 保持 INFO+

---

## **9. 开发环境与依赖 (Development Environment)**

### 9.1 运行要求

| 组件 | 最低版本 | 说明 |
|------|----------|------|
| Python | >= 3.10 | Pipeline 和 Compiler 的主语言 |
| Node.js | >= 18 | `github_analyzer` 运行环境 |
| Git | >= 2.30 | `repo2txt` 依赖 Git 命令 |
| WebGAL | 发行版 zip/tar | 黑盒加载，不做修改 |
| 磁盘空间 | >= 2GB 可用 | 临时文件 + 产出物 |

### 9.2 Python 依赖 (requirements.txt 示例)

```
openai>=1.0.0
click>=8.0.0
jsonschema>=4.0.0
python-dotenv>=1.0.0
```

### 9.3 目录结构建议

```
Repo2Gal/
├── main.py                    # CLI 入口
├── pipeline/
│   ├── fetcher.py             # Step 2: 数据拉取
│   ├── cleaner.py             # Step 3: 数据清洗
│   └── merger.py              # Step 4: 多仓库合并
├── llm_processor/
│   ├── engine.py              # Step 5: LLM 调用引擎
│   └── schema_validator.py    # story_data.json Schema 校验
├── compiler/
│   ├── compiler.py            # Step 6: WebGAL 编译器
│   └── webgal_commands_mapping.json  # WebGAL 指令映射表
├── prompts/
│   └── system_default.txt     # 默认 System Prompt 模板
├── schemas/
│   ├── context.schema.json    # Context JSON Schema (附录 A)
│   ├── story.schema.json      # story_data.json Schema (附录 A)
│   └── assets.schema.json     # assets_config.json Schema (附录 A)
├── assets/
│   └── ...                    # 占位符资源模板
├── requirements.txt
└── README.md
```

---

## **10. 测试策略 (Testing Strategy)**

> V1 阶段最低测试要求：

* **Data Pipeline 单元测试：** Cleaner 输入（模拟 raw_data 目录）→ 输出 Context JSON → 断言 Schema 合规且大小 ≤ 128KB
* **LLM 调用 Mock 测试：** 使用 mock API server 返回预置 `story_data.json`，验证 Processor 的重试逻辑和 Schema 校验
* **Compiler 集成测试：** 给定固定的 `story_data.json` + `assets_config.json` → 断言产出目录结构正确、`.txt` 文件数匹配
* **端到端冒烟测试：** 使用一个小型公开仓库（如 `octocat/Hello-World`）运行完整 Pipeline，验证 0 退出码

---

## **附录 A: JSON Schema 定义文件**

以下 Schema 文件应存放于 `schemas/` 目录下，供代码运行时校验使用（通过 `jsonschema` 库）。

> **注意：** 附录 A 的完整 JSON Schema 定义因篇幅关系在此省略，由开发者根据第 6 节中的类型注释和字段描述生成 `schemas/context.schema.json`、`schemas/story.schema.json`、`schemas/assets.schema.json`。校验时必须使用 Draft 2020-12 标准。

---

## **附录 B: 西幻世界观映射表 (Western Fantasy Mapping)**

以下映射表为 V1 权威定义，Prompt 模板和 LLM 生成均须遵守。所有未列入的概念**禁止自由命名**，必须回退到原始技术名词（即不翻译）。

| 编程/开源概念 | 西幻隐喻 | 说明 |
|--------------|----------|------|
| 仓库 (Repository) | 城堡 / 领地 | 整体项目 |
| 模块 (Module) | 魔法阵 | 独立功能单元 |
| 目录 (Directory) | 区域 / 房间 | 组织结构 |
| 文件 (File) | 卷轴 / 符文石 | 承载代码的实体 |
| 编程语言 (Language) | 魔法流派 | 技术栈 |
| 函数 (Function) | 咒语 / 法术 | 可执行的最小逻辑单元 |
| 类 (Class) | 职业 / 角色模板 | 面向对象抽象 |
| 接口 (Interface) | 契约 / 盟约 | 抽象约定 |
| 依赖 (Dependency) | 魔法材料 / 药水配方 | 外部库 |
| 包管理器 (Package Manager) | 炼金工坊 | npm/pip/cargo 等 |
| Commit | 历史记载 / 王国编年史条目 | 单次修改记录 |
| Branch | 平行时空 / 镜像维度 | 分支 |
| Merge | 时空融合 | 合并 |
| Pull Request (PR) | 入城申请 / 魔法论文答辩 | 代码审查 |
| Issue | 悬赏令 / 魔法异常报告 | Bug/功能需求 |
| Release | 王国盛典 / 时代更迭 | 版本发布 |
| CI/CD | 自动魔法阵 / 永动机关 | 自动化流水线 |
| 测试 (Test) | 结界 / 试炼 | 质量保障 |
| Bug | 魔物 / 诅咒 | 缺陷 |
| Breaking Change | 天灾 / 王国崩塌 | 不兼容变更 |
| Refactor | 阵法重构 / 城市改建 | 重构 |
| 文档 (README) | 冒险者指南 / 王国图鉴 | 说明文档 |
| 贡献者 (Contributor) | 冒险者 / 魔法师 | 开发者 |
| Maintainer | 城主 / 大魔法师 | 核心维护者 |
| 社区 (Community) | 冒险者公会 | 开源社区 |
| License | 王国律法 | 开源许可协议 |
| Fork | 分城建国 | 仓库分叉 |
| Star | 声望值 | GitHub Star |

---

## **附录 C: WebGAL 指令映射接口 (Placeholder)**

Compiler 开发者必须创建并维护 `compiler/webgal_commands_mapping.json`，记录 `story_data.json` 中的 action 到 WebGAL `.txt` 语法的映射关系。

```jsonc
// compiler/webgal_commands_mapping.json (示例占位)
{
  "version": "2.0",
  "webgal_version": "4.x",           // 目标 WebGAL 版本
  "mappings": [
    {
      "story_action": "set_bg",
      "webgal_command": "changeBg:{target}",
      "notes": "target 来自 assets_config.json backgrounds key"
    },
    {
      "story_action": "dialogue",
      "webgal_command": "{speaker}:{text}",
      "notes": "speaker 为 narration 时使用旁白语法"
    },
    {
      "story_action": "choice",
      "webgal_command": "choose:{option1_label}:{option1_text}->{target_scene1}|{option2_label}:{option2_text}->{target_scene2}",
      "notes": "变量设置需额外处理，参考 WebGAL setVar 指令"
    }
    // ... 完整映射由实现者调研 WebGAL 文档后填写
  ]
}
```

> 此文件只定义映射关系，不包含实现逻辑。Compiler 代码读取此映射表驱动转换过程。

---

## **11. 版本历史**

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v1.0 | (历史) | 初始版本 |
| v1.1 | (历史) | 细化三段式架构，增加 Schema 示例 |
| v2.0 | 2024-07-30 | 全面重构：完整 Schema 定义、CLI 规范、错误处理、日志、Prompt 模板机制、Context JSON 合约、WebGAL 产出结构、开发环境、西幻映射表、测试策略 |
| v2.0-r1 | 2024-07-30 | 深度评估修正：剧情线性化策略（§3.2.4）、简化 story_data.json（§6.2）、Compiler 分支分解与代码板降级（§6.5）、LLM JSON Mode 强化（§3.2.3）、音频格式统一为 .mp3/.ogg |

---

> **文档维护者：** Repo2Gal 核心团队
> **最后更新：** 2024-07-30
