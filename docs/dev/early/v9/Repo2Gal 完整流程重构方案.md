# **Repo2Gal 核心系统流程重构方案**

为了彻底解决线性脚本带来的工程脆弱性、Token 爆炸风险以及资源强耦合问题，我们将 Repo2Gal 的核心引擎重构为基于 **PocketFlow** 的有向无环图 (DAG) 架构。

## **一、 系统总体数据流转图 (DAG)**

系统不再是简单的 A -> B -> C 脚本调用，而是通过全局状态机共享数据，并通过图节点进行路由调度。  
[用户输入] 仓库 URL / 本地路径 / Game Mode  
[外部资源] 自定义 prompt.yaml / media_assets (立绘、BGM)  
       │  
       ▼  
┌──────────────────────────────────────────────────────────────┐  
│                    PocketFlow 流程引擎                       │  
│                                                              │  
│  (1) [Init Node] 验证参数，加载外部 Prompt 与资源映射表      │  
│       │                                                      │  
│       ├──► (2) [Code Fetch Node] 调用 `repo2txt`             │  
│       │    输出: 核心代码与目录树                            │  
│       │                                                      │  
│       ├──► (3) [Lore Fetch Node] 调用 `gh2md`                │  
│       │    输出: Issue/PR 历史辩论与剧情背景                 │  
│       │                                                      │  
│  (4) [Context Merger Node] ★ 核心防御：组装与 Token 预算截断 │  
│       │                                                      │  
│  (5) [LLM Node] 注入外部 Prompt 模板，调用大模型生成剧情     │  
│       │                                                      │  
│  (6) [Builder Node] 静态模板克隆，注入 WebGAL 脚本与媒体素材 │  
└───────┼──────────────────────────────────────────────────────┘  
        ▼  
[最终产物] 包含完整 HTML/JS、.wg 脚本及自定义媒体的 WebGAL 游戏目录

## **二、 六大核心 Node 节点详解**

整个工作流共享一个 Repo2GalState 状态对象，各个节点各司其职，保证工程弹性：

> 1. **InitNode (初始化与配置加载)**  
   * **职责**：系统“启动加载界面”。负责解析命令行参数，并读取用户传入的外部 prompt.yaml 和多媒体资源目录（media_assets）。  
   * **解耦体现**：系统内部不包含任何“二次元”或“赛博朋克”等特定风格数据，所有风格由该节点在运行时动态挂载。  
> 2. **CodeFetchNode (代码上下文提取)**  
   * **职责**：包装 repo2txt 工具。  
   * **动态路由**：根据用户选择的游戏模式（如探索模式 vs 架构模式），向 repo2txt 传递不同的 --exclude-dir 参数，精准控制代码提取范围。  
> 3. **LoreFetchNode (剧情背景挖掘)**  
   * **职责**：包装 gh2md 工具，通过 GitHub API 抓取该仓库中评论数最多的 Top 20 Issues 和 PRs，作为游戏内 NPC 互动与剧情冲突的天然语料。  
> 4. **ContextMergerNode (组装与 Token 预算控制)**  
   * **职责**：系统“防御装甲”。接收 Node 2 和 Node 3 的纯文本输出进行合并。  
   * **Token 预算机制**：引入 tiktoken。设定安全阈值（例如 ![][image1] Tokens）。如果合并后的文本超载，按以下优先级进行**截断 (Pruning)**：  
     1. 优先丢弃旧的、已关闭的次要 Issue 对话。  
     2. 丢弃非核心目录的代码实现（仅保留目录树和函数签名）。  
     3. 抛出警告但不中断流程。  
> 5. **LLMNode (大模型剧情生成)**  
   * **职责**：真正的“大脑思考”环节。将 Node 4 截断后的安全上下文，填入 Node 1 加载的 prompt.yaml 模板中。  
   * **输出约束**：强制要求 LLM 返回严格遵循 WebGAL .wg 语法的纯文本数据（或使用 Structured Output 转换为 .wg）。若格式错误，PocketFlow 可通过自循环机制触发重试。  
> 6. **BuilderNode (资源编译与组装)**  
   * **职责**：将生成的 .wg 文件与所有外部资源进行物理合并。  
   * **操作流程**：  
     1. 复制一份空白的 WebGAL 静态引擎模板。  
     2. 将 LLM 生成的剧本写入 game/script/main.wg。  
     3. 将 Node 1 挂载的 media_assets 中的背景图片、立绘、BGM 复制到 game/ 对应的资源目录下，完成最后的游戏打包。

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEcAAAAZCAYAAABjNDOYAAADhUlEQVR4Xu2YaahOURSGlylDZJ5FJBkz5Y+UWzKl5JchbiI/DElIUcpHGUp+kYgSIUOSmVL3yjyEUiIkQ5mnRMj0vnftc779re6+344fdDtPvbX3e9Zdzlln7/2tQyQjIyPj39PJGo5aUA66AZ2HjkPd/ABHP6gMOgddhxZCNQoi4pgAXYXOQhehUYWXK2gB7RSNuwZthhoVRCgxuYI0gAZDh6Gj5lrCOugm1NDNZ0LPoJZphEhH6C1U6ubNoNvQ0jQijrHQJ8kXvz/0ERqaRujLugJtFS0+57ug014MickVZBb0EjoGfZfKi9MB+gZN8jzeEIuz0vM2Qne8OWEReXONjV8VLChXgc8e0RWbMB76BbXzvO7OG+55Mbmi+CKVF2eO6D/ax/jlov84YbFeQAfSq0qJ6N/yYWLoJRo/1/g557d28/3Qm/SqwtXzQ/QlkdhcUYSKw6XLZPY8OgT9hOqLri7GbCuI0GVMf7XxQ0wRjZ9q/PnOH+nm96GH+cspH0TPFRKbK4pQcbjlmKyt8fn26HeBBrmxXcLJ29th/BCLROP9LUyS1TvdzblV7+Yvp7yCHrtxbK4oQsUpE03Wxvh7nd9X9IDjeFNBhEgP5x80fohlovETjc+zkf48N+eKtecb4dZ+58axuaIIFadcihenxI3/tjg5Kf5APN84LlacnBTPFQ2Lwy1kCW2rfc7vKuFt1dP57EdiCG2F2c6f4eahbcVf3qduHJsrChbnhDVFH5jJOhufBzJ9HsgsHMfbCyLyB/Ia44fggzB+mvGTQzRp4FiYR/nLKTyQL7lxbK4oWJyT1hTtVZhsoPHZK/hL+zl0xJsT9hz8W7u0QyS9CjtrH/ZT9JOtzV6FzZxPHdGYZGvH5oqCxTllTdFGiw3iZM/jjbyGVnke+4t73pwsgD5DTTxvnOg5FYK90xbjsXu/4M2TJrC95w1w3gjPi8lVlNrQV+iMveDg5wO/q5KHXCzaITdNI7TXeS/5voKfFk+gJWmErj4+AA/Nep7vw5af26O3m/PThh36kDRCpKbkPx845v3zx8S+3JhcQcZAD0RvljdNcXuwyfIfnN3nCuiW6Eccb8SeQYRvr1z0xllM2522Em3euCWqWj3chvxwvSz6locVXq6gObRb9JuP2iD6nWiJyfVfsVb0Zz6jEvhL9yf/lVHtGQ0tt2aGsh6qa82MjIxqzW+mGwXCA8w4QwAAAABJRU5ErkJggg==>