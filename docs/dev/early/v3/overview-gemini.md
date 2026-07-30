# Repo2Gal 项目架构设计文档

## 1. 项目简介

**Repo2Gal** 是一个全纯 Python 驱动的自动化工具，旨在将 GitHub 代码仓库转化为二次元/西幻风格的**交互式视觉小说（Visual Novel / Galgame）**。

项目通过数据抓取、大模型（LLM）剧本化演绎以及正则表达式编译器，将枯燥的代码架构与提交历史包装为极具故事性与传播属性的视觉小说，并直接交付为可运行的 WebGAL 游戏包。

---

## 2. 核心模式设计

针对用户的不同诉求，系统预设了三种阅读模式：

| 模式 | 核心目标 | 数据来源 Focus | 西幻世界观隐喻 |
| --- | --- | --- | --- |
| **仓库概览** *(Overview)* | 快速了解仓库基础功能与用法 | `README.md`、`package.json` / 依赖配置、项目根目录树 | 冒险者公会任务看板：向新人展示圣物的威力与使用契约 |
| **快速上手** *(Onboarding)* | 针对二次开发者，解析结构、原理与实现 | `repo2txt` 核心代码切片、架构主干文件、目录结构 | 高塔法师解析室：圣物精灵剖析自身魔力回路与法阵节点 |
| **沉浸历史** *(History)* | 了解历史变动、社区氛围、大事件与人员变迁 | `github_analyzer` 过滤提交日志、Top Issue / PR 讨论 | 篝火战记：史诗战役、魔物（Bug）降临与救世英雄（PR） |

---

## 3. 技术栈与开源依赖

项目完全基于 **Python** 进行开发与解耦整合：

* **智能 Agent 框架**：`pydantic/pydantic-ai` *(MIT)* —— 用于 Tool Calling（按需读取文件/Commit）、类型校验与 LLM 流程管控。
* **代码文本提取**：`donoceidon/repo2txt` *(MIT)* —— 提取结构化代码与目录树。
* **Git 历史分析**：`Oltrematica/github_analyzer` —— 抽取 Commit 历史与社区大事件。
* **渲染引擎（交付目标）**：`OpenWebGAL/WebGAL` *(MPL-2.0)* —— 纯 Web 端视觉小说引擎，作为黑箱依赖，仅接收导出的剧本文件与资源包。

---

## 4. 整体架构与工作流

系统采用单向三层流水线（Data -> Agent -> Compiler -> Delivery）架构，确保各模块强解耦：

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        Repo2Gal CLI (main.py)                          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ 传入: Repo URL/路径 + 模式选择
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 1. 数据抽取与预处理层 (Data Extraction Layer)                           │
│    ├── extractors/txt_extractor.py  --> repo2txt 封装 (结构与代码)      │
│    └── extractors/git_analyzer.py   --> github_analyzer 封装 (日志降噪) │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. Agent 剧本创作层 (pydantic-ai Agent Layer)                            │
│    ├── prompts/                   --> 系统提示词 (西幻世界观 & 模式约束) │
│    ├── tools/                     --> Agent "点菜"工具 (按需查阅文件/Git) │
│    └── Output                     --> 产生纯 Markdown 剧本文本           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3. 剧本编译与解耦映射层 (Compiler Layer)                                 │
│    ├── config/western_fantasy.json --> 角色/背景/音效 占位符 URL 映射    │
│    └── compiler/webgal_compiler.py --> 正则解析 Markdown 为 WebGAL 指令 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 4. 目录包交付层 (Delivery Layer)                                        │
│    └── 纯文件输出至: ./output/<repo_name>_gal/                         │
│        ├── game/scene/start.txt    (WebGAL 编译剧本)                   │
│        ├── game.config.json        (游戏元信息)                         │
│        └── assets/                 (占位/缺省素材库)                    │
└────────────────────────────────────────────────────────────────────────┘

```

---

## 5. 数据解耦与 DSL 交互协议

为了防止 LLM 产生 JSON 语法格式幻觉，AI 仅输出 **Markdown 格式的剧本 DSL**，由 Python 正则编译器将其编译为 WebGAL 脚本。

### AI 输出的 Markdown 剧本规范 (DSL)

```markdown
[场景: 魔法公会大厅]
[BGM: 预备战斗]
[旁白: 三天后，深渊魔物（Issue #404）降临了。]

**骑士** (严肃): 旅行者，这个法阵（仓库）的核心法则不容篡改。
**仓库娘** (哭泣): 呜呜……可是昨天合并那个卷轴（PR）的时候明明还是好好的！

```

### 资源解耦配置文件 (`config/western_fantasy.json`)

```json
{
  "theme": "western_fantasy",
  "backgrounds": {
    "魔法公会大厅": "assets/bg/guild_hall.jpg",
    "高塔解析室": "assets/bg/tower_lab.jpg"
  },
  "characters": {
    "仓库娘": { "name": "圣物精灵", "sprite": "assets/char/repo_chan.png" },
    "骑士": { "name": "守卫骑士", "sprite": "assets/char/knight.png" }
  }
}

```

---

## 6. 项目目录结构规范

```text
repo2gal/
├── config/                     # 配置文件 (解耦立绘、背景与素材映射)
│   └── western_fantasy.json
├── src/
│   ├── __init__.py
│   ├── extractors/             # 仓库与 Git 数据提取器
│   │   ├── txt_extractor.py
│   │   └── git_analyzer.py
│   ├── agent/                  # pydantic-ai 驱动的编剧核心
│   │   ├── prompts.py          # 提示词工程 (三大模式)
│   │   └── script_agent.py     # Agent 实例与 Tool Calling 工具定义
│   ├── compiler/               # Markdown 到 WebGAL 语法转换器
│   │   └── webgal_compiler.py
│   └── delivery/               # 游戏文件打包导出器
│       └── packager.py
├── output/                     # 默认导出生成结果的目录
├── main.py                     # CLI 主入口
├── pyproject.toml              # 依赖与项目配置
└── README.md

```

---

## 7. 开发里程碑 (V1 MVP)

1. **Phase 1 - 数据与编译通路 (1 周)**：
* 实现 `repo2txt` 与 `github_analyzer` 的数据清洗函数。
* 编写 `webgal_compiler.py`，实现正则解析 Markdown 剧本并生成 WebGAL `.txt` 指令。


2. **Phase 2 - pydantic-ai Agent 接入 (1 周)**：
* 配置 `pydantic-ai` Agent，挂载 `read_file` 与 `read_git_log` 工具。
* 调试西幻世界观在三大模式下的提示词工程（Prompt Engineering）。


3. **Phase 3 - 打包交付与 CLI 验证 (3 天)**：
* 集成 `main.py` CLI 入口，实现从仓库输入到一键生成 `./output/` 静态文件夹的全流程闭环。