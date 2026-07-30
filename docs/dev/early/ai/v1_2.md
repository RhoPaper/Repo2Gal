# **Repo2Gal - AI Agent Development Specification (V1.1)**

## **1. 项目愿景 (Project Vision)**

**Repo2Gal** 是一个将开源 GitHub 仓库转换为可交互式视觉小说（Galgame）的工具流。  
本项目旨在通过 LLM 技术，将枯燥的代码结构、复杂的提交历史和文档，转化为带有剧情、角色互动的沉浸式阅读体验，从而极大地降低开源项目的理解门槛。

## **2. 核心架构约束 (CRITICAL CONSTRAINTS - 必读)**

为保证项目的高可维护性和未来扩展性，所有参与开发的 AI Agent 及开发者必须严格遵守以下原则：

> 1. **确定性脚本与 AI 职责分离 (Pipeline Separation)：**  
>
* **数据拉取与清洗必须是由程序脚本执行**，直接接收一个或多个仓库 URL 进行自动化拉取，**不依赖 LLM 的 Agent Skill/Tool Calling 过程**。  
* **LLM 仅参与：** 仓库结构与文本分析、人设萃取、三维世界观映射、剧情/对话生成。  
>
> 1. **绝对解耦 (Strict Decoupling)：**  
>
* **禁止硬编码 (No Hardcoding)：** 所有的剧情文本、角色立绘路径 (Sprites URLs)、背景音乐/图片路径 (BGM/BG URLs) **必须**与代码逻辑和核心引擎完全解耦。  
* **缺省资源策略：** 第一版 (V1) 开发中，立绘和背景资源统一使用“缺省占位符 (Placeholders)”（如 default_bg.png, char_a_smile.png 等）。系统支持通过统一配置文件（assets_config.json）映射真实 URL。  
>
> 1. **WebGAL 引擎黑盒原则 (Black-box Engine)：**  
>
* **禁止修改源码：** 必须直接使用 [OpenWebGAL/WebGAL] 引擎的标准发行版，**绝对禁止**修改引擎本身的源代码。  
* **适配器/编译器模式：** 本项目的核心工作是“生成 WebGAL 可识别的脚本文件（如 .txt 剧本和配置文件）”，通过本地格式化编译器生成打包产物。  
>
> 1. **V1 世界观锁定 (V1 Worldview)：**  
>
* 为了保证初版生成质量的可控性，当前版本世界观统一限制为 **“简单西幻世界观 (Western Fantasy)”**。  
* 代码库的模块被隐喻为不同“魔法阵”、编程语言为“魔法”流派、仓库为“城堡”、社区为“公会”等这类西幻元素类比。

## **3. 系统架构与模块职责 (System Architecture)**

整体系统划分为 **自动化数据流水线 (Data Pipeline Script)**、**AI 处理中枢 (Core LLM Processor)** 和 **表现层 (Presentation Engine)** 三层。  
[ 用户输入: 1~N 个 GitHub Repo URLs ]  
              │  
              ▼  
┌─────────────────────────────────────────────────────────────┐  
│ 1. 自动化数据流水线脚本 (Deterministic CLI / Script)        │  
│  - 执行 `repo2txt` -> 提取代码树 & 关键源码文本             │  
│  - 执行 `github_analyzer` -> 获取 Commits/Issues 数据       │  
│  - 数据清洗器 (Data Cleaner) -> 过滤冗余，提炼 Core Context │  
└─────────────────────────────┬───────────────────────────────┘  
                              │ 清洗后的 Context JSON  
                              ▼  
┌─────────────────────────────────────────────────────────────┐  
│ 2. AI 处理中枢 (LLM Processor)                              │  
│  - Prompt 引擎 -> 注入西幻世界观与模式模板                  │  
│  - 剧情与人设生成 -> 输出中间态 `story_data.json`           │  
└─────────────────────────────┬───────────────────────────────┘  
                              │ story_data.json  
                              ▼  
┌─────────────────────────────────────────────────────────────┐  
│ 3. WebGAL 剧本编译器 (WebGAL Compiler Script)               │  
│  - 将 `story_data.json` 编译翻译为 WebGAL 标准 `.txt` 剧本  │  
│  - 结合 `assets_config.json` 导出 WebGAL 资源包             │  
└─────────────────────────────┬───────────────────────────────┘  
                              │  
                              ▼  
                [ OpenWebGAL 引擎直接加载渲染 ]

### **3.1 Fetcher & Data Pipeline (自动化脚本层)**

直接由本地命令行脚本或后端服务调用现成工具拉取，无需 AI 介入决策：

> * **仓库结构与代码内容提取：** 调用 donoceidon/repo2txt
>
* **职责：** 输入 GitHub URL，输出仓库文本化结构与核心文件内容。  
>
> * **历史与社区数据提取：** 调用 Oltrematica/github_analyzer  
>
* **职责：** 获取 Commits、Issues、PRs 及核心贡献者列表。  
>
> * **数据清洗脚本 (Data Cleaner Rules)：**  
>
* 过滤 .git、二进制文件、大型 Lock 文件（如 package-lock.json）。  
* 抽取全量 Commit 中影响文件范围广、包含重大修改记录（如 feat!, breaking change, release）的事件，精简 Tokens 消耗。

### **3.2 Core LLM Processor (AI 处理中枢)**

负责吸收清洗后的 Context，输出纯粹的结构化剧情数据：

> * **Data Aggregation (数据整理)：** 构建包含项目背景、核心变动、核心贡献者的 Prompt 上下文。  
> * **Prompt Engineering (提示词工程)：** 根据用户选定的【游玩模式】生成符合“西幻世界观”的 Galgame 剧本。  其余基本提示词缺省，解耦交给人类开发者完成
> * **Structured Output：** 严格要求 LLM 输出符合 Schema 的 story_data.json。

### **3.3 Compiler & Presentation (编译器与表现层)**

> * **Compiler Script：** 确定性程序脚本，负责将 JSON 转化为 WebGAL 文本语法（如 changeBg: guild_hall.jpg 等指令）。  
> * **WebGAL 引擎：** OpenWebGAL/WebGAL (MPL-2.0)，黑盒调用，加载编译器产出的文件夹。

## **4. 核心游玩模式 (Three Core Modes)**

系统必须支持在运行 CLI 或脚本时，传入参数指定以下三种剧本生成模式之一：

### **Mode 1: 仓库概览 (Repository Overview)**

> * **目标受众：** 需要快速了解该仓库“是干什么的”、“怎么用”的使用者。  
> * **剧情风格：** 新手村向导 / 冒险者公会任务发布。  
> * **参考标杆：** the-pocket/pocketflow-tutorial-codebase-knowledge  
> * **AI 侧重点：** README 解析、顶层 API 调用说明、核心 Features 展示。无需深入底层代码细节。

### **Mode 2: 快速上手 (Quick Start / Contributor Guide)**

> * **目标受众：** 希望参与开源贡献 (PR) 或进行二次开发 (Fork) 的开发者。  
> * **剧情风格：** 魔法学院导师指导 / 工坊学徒实战。  
> * **参考标杆：** Nova42x/paper2galgame  
> * **AI 侧重点：** 详细演绎项目目录结构、底层运行原理、核心算法实现方法、如何配置本地开发环境。需要穿插“代码解析黑板”或“答题通关 (Code Quest)”。

### **Mode 3: 沉浸历史 (Immersive History)**

> * **目标受众：** 对项目生态、社区演变感兴趣的用户，或纯粹的开源文化体验者。  
> * **剧情风格：** 史诗叙事 / 历史纪传体，最具 Galgame 沉浸感。  
> * **依赖数据：** 高度依赖 github_analyzer 提取的 Commits、重构大事件、核心贡献者变迁。  
> * **AI 侧重点：** 讲述仓库从 V0.1 到 V1.0 再到 Vx.x 的此类发展历程、社区环境变化、曾经遇到的重大 Bug（具象化为“魔物入侵”）及修复过程。

## **5. 数据结构与解耦规范 (Data Schema & Decoupling Standard)**

### **5.1 资产映射表 (Asset Map - assets_config.json)**

配置文件管理所有多媒体资源，禁止在剧本中直接硬编码真实 URL（以下仅为格式示例）。  
{  
  "characters": {  
    "guide_npc": {  
      "name": "艾尔 (Al)",  
      "sprites": {  
        "normal": "assets/chars/al_normal_placeholder.png",  
        "happy": "assets/chars/al_happy_placeholder.png"  
      }  
    }  
  },  
  "backgrounds": {  
    "guild_hall": "assets/bgs/guild_hall_placeholder.jpg",  
    "code_dungeon": "assets/bgs/dungeon_placeholder.jpg"  
  }  
}

### **5.2 结构化剧本中间态 (Story Intermediate Schema - story_data.json)**

LLM 输出的标准 JSON 结构，随后由 Compiler 编译为 WebGAL *.txt 剧本（以下仅为格式示例）：  
{  
  "mode": "Quick Start",  
  "chapter": "1",  
  "title": "初入架构之城",  
  "scenes": [  
    {  
      "action": "set_bg",  
      "target": "guild_hall"  
    },  
    {  
      "action": "dialogue",  
      "speaker": "guide_npc",  
      "sprite_emotion": "happy",  
      "text": "欢迎来到 {repo_name}！我是你的向导，今天我们将一起拆解这座魔法城堡的核心阵法（架构）！"  
    },  
    {  
      "action": "show_code_board",  
      "code_snippet": "import { core } from './src'",  
      "explanation": "一切的起点都在 src 目录下..."  
    }  
  ]  
}

## **6. 系统自动化执行流程 (Pipeline Execution Steps)**

当用户执行命令（例如 python main.py --repo <https://github.com/xxx/yyy> --mode overview）时，流水线按如下步骤严格顺序执行：

> 1. **Step 1: Automated Fetching (确定性脚本拉取)**  
>
* 脚本启动，根据传入的 1 个或多个 Repo URL，并行调用 repo2txt 和 github_analyzer 工具。  
* 数据落盘至本地 .tmp/raw_data/ 目录。  
>
> 1. **Step 2: Preprocessing & Cleaning (确定性数据预处理)**  
>
* 脚本读取原始提取结果，过滤无关文件与庞大 Log。  
* 提炼出核心代码结构摘要、重大 Commit 事件轴与核心作者。构建出干净的 Context 对象。  
>
> 1. **Step 3: LLM Generation (AI 核心分析与剧本创作)**  
>
* 将清洗后的 Context + 指定模式 Prompt 输入给 LLM。  
* LLM 进行项目架构理解、人设映射，并生成结构化的 story_data.json。  
>
> 1. **Step 4: WebGAL Compilation & Asset Bundling (确定性编译打包)**  
>
* 编译脚本读取 story_data.json 和 assets_config.json。  
* 转换为 WebGAL 标准语法格式（生成 game/scene1.txt 等文件），输出可直接被 WebGAL 引擎运行的项目目录。
