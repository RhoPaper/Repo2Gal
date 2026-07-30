我基于你上传的 Repo2Gal 第三版架构文档进行了重构。
主要调整方向：

1. **降低 V1 实现复杂度**：弱化 Agent 作为核心，避免一开始陷入 Tool Calling 调试。
2. **增强 DSL 稳定性**：从“自然 Markdown + 正则匹配”升级为更明确的脚本 DSL。
3. **重新定位产品目标**：从“自动生成完整 Galgame”调整为“生成可玩的开源项目视觉化介绍”。
4. **保留未来 Agent 扩展能力**：不是删除 Agent，而是延后到 V2/V3。
5. **加强传播属性**：加入 Repo 娘人格、GitHub Action、在线 Demo 等方向。

下面是第四版规划。

---

# Repo2Gal v4 架构设计文档

## 1. 项目简介

**Repo2Gal** 是一个基于 Python 的开源项目视觉化生成工具。

它能够读取 GitHub 仓库中的代码结构、文档、依赖关系以及 Git 历史，将一个普通代码仓库转换为具有二次元/幻想风格的**交互式视觉小说介绍作品（Visual Novel Presentation）**。

目标不是替代 README，而是创造一种新的开源项目展示方式：

> 让开发者通过一段可游玩的故事，理解一个项目的理念、架构与成长历史。

输入：

```
GitHub Repository URL
```

输出：

```
WebGAL 游戏包
    |
    ├── 项目介绍
    ├── 架构解析
    ├── 开发历史
    └── Repo 人格化角色
```

---

# 2. 产品定位调整

## 原版本定位

> GitHub 仓库 → 自动生成完整 Galgame

问题：

* 范围过大
* 剧情质量不可控
* 游戏内容价值弱于技术展示价值

---

## v4 定位

> GitHub Repository → Interactive Anime Documentation

即：

**交互式二次元项目文档**

类似：

README:

```
文字介绍项目
```

Repo2Gal:

```
进入世界
认识角色
体验项目故事
理解代码结构
```

---

# 3. 核心模式设计

保留三个模式，但是重新定义。

| 模式             | 目标     | 数据来源            | 输出     |
| -------------- | ------ | --------------- | ------ |
| Explorer 探索模式  | 快速认识项目 | README、配置文件     | 项目介绍剧情 |
| Architect 架构模式 | 学习源码结构 | 文件树、核心代码        | 架构解析剧情 |
| Chronicle 编年模式 | 了解项目成长 | Commit、Issue、PR | 开发史剧情  |

---

# 4. 新增：Repo Persona 系统

每个仓库生成一个人格化角色。

例如：

输入：

```
vuejs/core
```

生成：

```
Vue精灵

职业:
响应式魔法师

属性:
灵活
优雅
追求性能

技能:
Composition API
Virtual DOM
Compiler Magic

弱点:
大型项目调试困难
```

人格来源：

```
README
代码风格
Commit Message
Issue讨论
Star数量
贡献者生态
```

---

# 5. 新架构

整体改为：

```
                 Repo URL
                    |
                    ↓

        ┌───────────────────┐
        │ Data Extraction   │
        └───────────────────┘

                    ↓

        ┌───────────────────┐
        │ Structured Context│
        └───────────────────┘

                    ↓

        ┌───────────────────┐
        │ Story Generator   │
        │       LLM         │
        └───────────────────┘

                    ↓

        ┌───────────────────┐
        │ RepoGal DSL       │
        └───────────────────┘

                    ↓

        ┌───────────────────┐
        │ Compiler          │
        └───────────────────┘

                    ↓

             WebGAL Package
```

---

# 6. 数据层重构

## 原设计

```
repo2txt
github_analyzer
       |
       ↓
LLM
```

问题：

LLM 直接面对大量文本。

---

## v4

新增 Context Builder。

目录：

```
src/
 └── context/
      ├── repo_context.py
      ├── code_summary.py
      └── history_summary.py
```

输出：

```json
{
"name":"WebGAL",

"identity":{
"type":"visual novel engine",
"language":"typescript"
},

"architecture":[
{
"name":"renderer",
"role":"负责画面渲染"
}
],

"history":[
{
"event":"加入Vue3支持",
"type":"feature"
}
]
}
```

LLM 不再分析原始仓库。

只负责：

```
结构化资料
      ↓
故事化表达
```

---

# 7. Agent 调整

## v3

Agent 是核心：

```
Agent
 |
 |-- read_file
 |-- read_git
```

---

## v4

Agent 降级为高级功能。

基础流程：

```
Context JSON

↓

LLM

↓

DSL
```

---

未来：

v5：

增加：

```
Interactive Repo Agent

用户:
“为什么这里不用xxx？”

Agent:
“让我查看这个模块”
```

---

# 8. 新 DSL 设计

放弃：

```markdown
[场景]
[角色]
```

改成：

## RepoGal DSL

示例：

```text
scene guild_hall

background tower

character repo_chan

dialog
欢迎来到我的代码领域。

character knight

dialog
让我看看你的架构魔法。
```

---

语法：

```
scene <name>

background <name>

character <id>

dialog <text>

narration <text>

choice
    option A
    option B
```

优势：

* 易解析
* 易扩展
* LLM 更稳定

---

# 9. Compiler

目录：

```
src/compiler/

├── parser.py

├── validator.py

└── webgal_writer.py
```

流程：

```
DSL

↓

AST

↓

WebGAL Script
```

例如：

输入：

```
character repo_chan

dialog
你好
```

转换：

```
repo_chan:你好;
```

---

# 10. 项目目录 v4

```
repo2gal/

├── src/

│
├── extractor/
│   ├── github.py
│   ├── git.py
│   └── filesystem.py
│
├── context/
│   ├── builder.py
│   └── schema.py
│
├── generator/
│   ├── prompt.py
│   └── llm.py
│
├── dsl/
│   ├── parser.py
│   └── ast.py
│
├── compiler/
│   └── webgal.py
│
├── delivery/
│   └── package.py
│
└── main.py
```

---

# 11. MVP v4 开发路线

## Phase 1：数据通路（5天）

完成：

* GitHub Repo 获取
* README解析
* 文件树分析
* package.json解析
* Context JSON生成

目标：

```
repo
 ↓
context.json
```

---

## Phase 2：故事生成（7天）

完成：

* 三种模式 Prompt
* Repo Persona
* DSL生成

目标：

```
context.json
 ↓
story.dsl
```

---

## Phase 3：Compiler（5天）

完成：

* DSL Parser
* AST
* WebGAL输出

目标：

```
story.dsl
 ↓
game/
```

---

## Phase 4：展示与传播（7天）

新增：

### CLI

```bash
repo2gal https://github.com/vuejs/core
```

生成：

```
vue-gal/
```

---

### GitHub Action

```yaml
- uses: repo2gal/action
```

自动生成项目介绍游戏。

---

### Web Demo

网页：

```
输入 Repo URL

↓

等待30秒

↓

开始游戏
```

---

# 12. 后续版本路线

## v5

Agent 模式：

```
玩家
 |
Repo娘
 |
动态查询源码
```

---

## v6

多人贡献者角色：

```
作者
维护者
贡献者
Issue作者
```

形成：

```
Git Chronicle RPG
```

---

# 最终评价

第四版核心变化：

| 项目       | v3          | v4        |
| -------- | ----------- | --------- |
| 定位       | AI生成Galgame | 交互式项目文档   |
| Agent    | 核心          | 高级功能      |
| 输入       | 原始代码        | Context模型 |
| DSL      | Markdown    | 专用DSL     |
| Compiler | 正则          | AST       |
| MVP难度    | 高           | 中         |
| 开源传播     | 高           | 更高        |

我认为 v4 会比 v3 更像一个**真正可以做出来并且容易火的开源项目**。

v3 像：

> “我要做一个 AI 游戏生成器”

v4 更像：

> “我要重新发明 GitHub README 的展示方式”

后者的目标更清晰，也更容易吸引开发者社区。
