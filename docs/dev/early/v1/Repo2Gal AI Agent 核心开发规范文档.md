# **Repo2Gal \- AI Agent Development Specification (V1)**

## **1\. 项目愿景 (Project Vision)**

**Repo2Gal** 是一个将开源 GitHub 仓库转换为可交互式视觉小说（Galgame）的工具流。  
本项目旨在通过 LLM 技术，将枯燥的代码结构、复杂的提交历史和文档，转化为带有剧情、角色互动的沉浸式阅读体验，从而极大地降低开源项目的理解门槛。

## **2\. 核心架构约束 (CRITICAL CONSTRAINTS \- 必读)**

为保证项目的高可维护性和未来扩展性，所有参与开发的 AI Agent 必须严格遵守以下原则：

> 1. **绝对解耦 (Strict Decoupling)：**  
   * **禁止硬编码 (No Hardcoding)：** 所有的剧情文本、角色立绘路径 (Sprites URLs)、背景音乐/图片路径 (BGM/BG URLs) **必须**与代码逻辑和核心引擎完全解耦。  
   * **缺省资源策略：** 第一版 (V1) 开发中，立绘和背景资源暂时使用“缺省占位符 (Placeholders)”（如 default\_bg.png, char\_a\_smile.png 等）。后期将由人工替换 URL，系统需支持通过配置文件统一映射。  
> 2. **WebGAL 引擎黑盒原则 (Black-box Engine)：**  
   * **禁止修改源码：** 必须直接使用 \[OpenWebGAL/WebGAL\] 引擎的标准发行版，**绝对禁止**修改引擎本身的源代码。  
   * **适配器模式：** 本项目的核心工作是“生成 WebGAL 可识别的脚本文件（如 .txt 剧本和配置文件）”，而不是改造 Galgame 引擎。  
> 3. **V1 世界观锁定 (V1 Worldview)：**  
   * 为了保证初版生成质量的可控性，当前版本世界观统一限制为 **“简单西幻世界观 (Western Fantasy)”**。  
   * 代码库的模块将被隐喻为“魔法阵”、“城堡”、“公会”等西幻元素。

## **3\. 技术栈与模块依赖 (Tech Stack & Dependencies)**

本项目整体分为三大模块：**数据获取 (Fetcher)**、**AI 处理中枢 (Core Processor)**、**表现层 (Presentation Engine)**。

### **3.1 Fetcher (数据获取层)**

AI 需调用以下现成开源工具，不得重复造轮子：

> * **仓库结构与代码内容：** donoceidon/repo2txt (MIT Protocol)  
  * **用途：** 提取仓库的文件树结构和核心代码内容，作为 AI 理解的基础上下文。  
> * **历史与社区数据：** Oltrematica/github\_analyzer (Protocol TBD \- 需预留接口)  
  * **用途：** 获取 Commits、Issues、PRs 等历史数据以及人员变迁记录。  
  * **注意：** 需对该工具的输出进行数据清洗，只提取“核心/重大变动”喂给大模型，避免 Token 溢出。

### **3.2 Core Processor (我们主要实现的部分)**

该部分是本项目的核心业务逻辑（Node.js / Python 均可，需模块化设计）：

> * **Data Aggregation (数据整理)：** 清洗和合并 Fetcher 获取的数据。  
> * **Prompt Engineering (提示词工程)：** 针对三种不同的游玩模式（见第 4 节）设计特化的 Prompt 链。  
> * **WebGAL Script Compiler (格式化与编译)：** 将大模型返回的 JSON/结构化剧情数据，转换为 WebGAL 引擎标准的剧本语法。

### **3.3 Presentation (表现层)**

> * **引擎：** OpenWebGAL/WebGAL (MPL-2.0 Protocol)  
> * **职责：** 仅负责最终的渲染与交互。

## **4\. 核心游玩模式 (Three Core Modes)**

系统必须支持让用户在解析仓库前，选择以下三种剧本生成模式之一。每种模式对应不同的 Prompt 策略和剧情侧重点：

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
> * **依赖数据：** 高度依赖 github\_analyzer 提取的 Commits、重构大事件、核心贡献者变迁。  
> * **AI 侧重点：** 讲述仓库从 V0.1 到 V1.0 的发展历程、社区环境变化、曾经遇到的重大 Bug（可以具象化为“魔物入侵”）及修复过程。

## **5\. 数据结构与解耦规范 (Data Schema & Decoupling Standard)**

为了满足“绝对解耦”的要求，AI 处理中枢在生成内容时，应先生成标准的中间态 JSON，再由格式化器 (Formatter) 转换为 WebGAL 剧本。

### **5.1 资产映射表 (Asset Map \- assets\_config.json)**

此文件管理所有多媒体资源，禁止在剧本中直接写死 URL。  
{  
  "characters": {  
    "guide\_npc": {  
      "name": "艾尔 (Al)",  
      "sprites": {  
        "normal": "assets/chars/al\_normal\_placeholder.png",  
        "happy": "assets/chars/al\_happy\_placeholder.png"  
      }  
    }  
  },  
  "backgrounds": {  
    "guild\_hall": "assets/bgs/guild\_hall\_placeholder.jpg",  
    "code\_dungeon": "assets/bgs/dungeon\_placeholder.jpg"  
  }  
}

### **5.2 结构化剧本中间态 (Story Intermediate Schema \- story\_data.json)**

LLM 输出的剧本数据结构参考如下，随后再将其编译为 WebGAL \*.txt：  
{  
  "mode": "Quick Start",  
  "chapter": "1",  
  "title": "初入架构之城",  
  "scenes": \[  
    {  
      "action": "set\_bg",  
      "target": "guild\_hall"  
    },  
    {  
      "action": "dialogue",  
      "speaker": "guide\_npc",  
      "sprite\_emotion": "happy",  
      "text": "欢迎来到 {repo\_name}！我是你的向导，今天我们将一起拆解这座魔法城堡的核心阵法（架构）！"  
    },  
    {  
      "action": "show\_code\_board",  
      "code\_snippet": "import { core } from './src'",  
      "explanation": "一切的起点都在 src 目录下..."  
    }  
  \]  
}

## **6\. AI Agent 工作流拆解 (Actionable Steps for AI)**

当 AI 接收到“处理特定仓库”的任务时，必须按以下标准流执行：

> 1. **Initialize (初始化):** 确认目标 GitHub URL、用户选择的【模式 (Mode)】。加载西幻世界观 Prompt 模板。  
> 2. **Fetch & Clean (拉取与清洗):**  
   * 调用 repo2txt 获取树结构和关键源码。  
   * 若模式为 Immersive History，额外调用 github\_analyzer 并清洗提交历史。  
> 3. **LLM Generation (剧情生成):**  
   * 结合世界观设定和模式设定，逐步（按章节）生成 story\_data.json。  
   * 确保生成的内容引用的背景和人物都在预设的范围内。  
> 4. **WebGAL Compilation (引擎适配):**  
   * 将 story\_data.json 翻译为 WebGAL 支持的 .txt 语法格式。  
   * 打包为 WebGAL 可直接读取的文件结构。