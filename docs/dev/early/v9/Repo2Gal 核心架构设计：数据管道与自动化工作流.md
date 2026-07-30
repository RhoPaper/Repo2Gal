# **Repo2Gal 核心架构设计：数据管道与自动化工作流**

本文档聚焦于 Repo2Gal 的后端核心工程架构，剥离了 Prompt 层面，专注于如何高效、稳定地将原始 GitHub 仓库数据流转为可在浏览器中运行的 WebGAL 游戏。

## **一、 系统总体架构图 (Data Flow)**

整个系统表现为一个标准的**有向无环图 (DAG)**，由 PocketFlow 负责全局调度。架构严格遵循“引擎与资源完全解耦”的设计理念，所有 Prompt 与媒体素材均从外部注入。  
\[输入数据\] GitHub URL / Local Path  
\[外部资源\] 自定义 Prompts / BGM / 立绘 / 背景 (Config & Assets)  
       │  
       ▼  
┌─────────────────────────────────────────────────────────┐  
│                   PocketFlow Engine                     │  
│                                                         │  
│  \[Node 1: Config\] 验证输入，加载外部 Prompt 与资源映射表│  
│       │                                                 │  
│       ├──► \[Node 2: Code Fetcher\] 调用 \`repo2txt\`       │  
│       │    输出: 目录树 \+ 核心代码文本                  │  
│       │                                                 │  
│       ├──► \[Node 3: Lore Fetcher\] 调用 \`gh2md\`          │  
│       │    输出: Issue/PR 历史剧情文本                  │  
│       │                                                 │  
│  \[Node 4: Context Merger\] 合并文本，执行 Token 截断     │  
│       │                                                 │  
│  \[Node 5: LLM Caller\] 注入外部 Prompt，调用 API 生成剧本 │  
│       │                                                 │  
│  \[Node 6: Builder\] 拦截 .wg 输出，注入 WebGAL 模板与素材│  
└───────┼─────────────────────────────────────────────────┘  
        ▼  
\[输出\] 包含完整 HTML/JS/CSS、.wg 脚本及自定义媒体资源的游戏目录

## **二、 PocketFlow 工作流节点详细设计**

我们使用 Pydantic 定义整个工作流的共享状态（State），并在 PocketFlow 中定义 6 个核心节点。

### **1\. 共享状态定义 (Shared State)**

from pydantic import BaseModel  
from typing import Optional, Dict

class Repo2GalState(BaseModel):  
    \# 输入参数  
    repo\_url: str  
    game\_mode: str \# "Explorer", "Architect", "Chronicle"  
      
    \# 外部解耦资源配置路径  
    prompt\_config\_path: Optional\[str\] \= None  
    media\_assets\_dir: Optional\[str\] \= None  
      
    \# 提取的上下文  
    code\_context: Optional\[str\] \= None  
    lore\_context: Optional\[str\] \= None  
    merged\_context: Optional\[str\] \= None  
      
    \# 生成的剧本  
    webgal\_script: Optional\[str\] \= None  
      
    \# 输出路径  
    output\_dir: Optional\[str\] \= None

### **2\. 节点职责与接口**

> * **Node 1: 初始化与配置加载节点 (InitNode)**  
  * **职责**：解析命令行参数，验证仓库可达性。读取由用户自定义的 prompts.yaml 以及外部媒体资源映射表（如 BGM、立绘列表），实现逻辑与资源的初步解耦。  
> * **Node 2: 代码抓取节点 (CodeFetchNode)**  
  * **职责**：基于 subprocess 调用 repo2txt。  
  * **策略**：根据 game\_mode 动态调整过滤参数。例如 Explorer 模式仅保留 README.md 和配置文件；Architect 模式扫描 src 或 lib 目录。  
> * **Node 3: 剧情挖掘节点 (LoreFetchNode)**  
  * **职责**：调用 gh2md 抓取 Issues 和 PRs。  
> * **Node 4: 上下文组装与截断节点 (ContextMergerNode)**  
  * **职责**：将 Node 2 和 Node 3 的输出合并。使用 tiktoken 快速估算 Token，执行预算截断。  
> * **Node 5: LLM 调度节点 (LLMGenerationNode)**  
  * **职责**：加载纯文本上下文和**外部注入的 Prompt 模板**，发起对 LLM 的 API 请求。确保输出纯净的 .wg 格式文本。  
> * **Node 6: 资源注入与编译节点 (WebGALInjectNode)**  
  * **职责**：除了组装 HTML 游戏引擎外，还会根据初始化阶段加载的外部配置，将用户自定义的 BGM、背景、立绘等媒体资源打包进最终产物中。

## **三、 WebGAL 模板注入方案详解 (取代 CLI)**

为了避开“不存在全局 WebGAL CLI”的问题，我们采用**静态模板克隆与覆盖**策略。

### **1\. 预置模板目录结构**

在 Repo2Gal 源码中，硬编码预置一个 assets/webgal\_template/ 目录。该目录是预先从 WebGAL 官方下载好的空白游戏引擎环境：  
repo2gal/  
├── repo2gal/            \# Python 源码包  
├── assets/  
│   └── webgal\_template/ \# WebGAL 静态空项目  
│       ├── index.html  
│       ├── WebGAL.js  
│       └── game/        \# 游戏资源目录  
│           ├── script/  \# 存放 .wg 脚本  
│           ├── bg/      \# 背景图  
│           ├── bgm/     \# 背景音乐  
│           └── figure/  \# 立绘

### **2\. 注入逻辑 (Python 伪代码)**

在 WebGALInjectNode 中执行以下操作：  
import shutil  
import os

def inject\_webgal\_script(state: Repo2GalState, target\_dir: str):  
    \# 1\. 复制纯净引擎模板到用户指定的输出目录  
    shutil.copytree("assets/webgal\_template", target\_dir)  
      
    \# 2\. 写入 AI 生成的 .wg 剧本  
    script\_path \= os.path.join(target\_dir, "game", "script", "main.wg")  
    with open(script\_path, "w", encoding="utf-8") as f:  
        f.write(state.webgal\_script)  
          
    \# 3\. 外部媒体资源挂载 (体现完全解耦)  
    \# 扫描 state.media\_assets\_dir，将用户自定义的 BGM、立绘、背景全部同步至对应目录  
    if state.media\_assets\_dir:  
        sync\_custom\_assets(state.media\_assets\_dir, os.path.join(target\_dir, "game"))

### **3\. 本地预览机制**

注入完成后，系统直接在终端提示用户运行 python \-m http.server \-d ./dist/my\_repo\_game 8000，玩家打开浏览器访问即可游玩。

## **四、 极致解耦与高度自定义 (Complete Decoupling)**

Repo2Gal 架构设计的核心原则之一是**引擎逻辑与资源内容的完全隔离**。系统本身只负责“数据流转、Token 管理与 WebGAL 模板组装”的管道工作，所有的表现层均开放给用户自定义：

> 1. **Prompt 外部化配置**  
   * 系统代码内不硬编码任何角色设定或系统 Prompt。  
   * 允许开发者通过 \--prompt-profile \<path\> 动态注入不同的 Prompt 配置文件。提取的 Context (Repo结构 \+ 历史记录) 只会被安全地送入配置模板的 {{CONTEXT}} 占位符中。  
> 2. **媒体资源 (Media Assets) 全量自定义**  
   * **立绘 (Figure) 与角色**：无论是赛博朋克风的 AI 助手，还是二次元萌娘，用户只需将自己的 PNG 放入配置目录，通过配置文件映射角色名即可在剧情中调用。  
   * **背景 (Background)**：允许配置 IDE 截图、科幻机房或奇幻场景等自定义背景图片。  
   * **背景音乐与音效 (BGM & SE)**：解耦了音频绑定，用户可挂载自定义音频包，LLM 会根据提取到的剧情氛围（如 Issue 中的激烈争吵、代码重构时的史诗感）在脚本中触发调用相应的自定义外部音频资源。