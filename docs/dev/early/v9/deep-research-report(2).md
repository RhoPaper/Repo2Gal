**执行摘要**：Repo2Gal MVP 将实现“仓库→交互式文档”流程。输入 GitHub 仓库地址，通过集成 **repo2txt**（导出代码文件）和 **gh2md**（导出 Issues/PR），构建项目上下文；然后调用 LLM 生成符合 WebGAL 脚本格式（如 `say:角色:文本`）的剧情剧本；最后用预置的 WebGAL 静态模板注入该脚本，输出可直接运行的视觉小说包。该方案保留了开源复用、结构清晰、分工明确等特点，可实现 MVP。本文档详细说明目标、架构模块、数据格式、调用示例、部署流程、里程碑等，任何程序员阅读后即可着手开发并交付 MVP。

## 目标与范围

- **目标**：在 MVP 阶段，实现一个基本流程：输入 GitHub 仓库，自动生成一个 WebGAL 视觉小说项目。用户可以运行该项目，在 WebGAL 前端查看仓库故事。
- **范围**：仅依赖现有开源工具，不修改 WebGAL 引擎；不实现完整 Galgame 功能（如 UI 开发、立绘、背景音乐等）；主要产物为生成并注入 WebGAL 脚本文件，搭配现成模板即可运行。 
- **核心设计决策**：  
  1. **使用 WebGAL 引擎**：以其作为游戏运行平台，不需自行开发引擎。  
  2. **去 DSL 化**：LLM 直接输出符合 WebGAL 脚本规范的文本（如 `say:角色:对白` 等），省去中间 DSL 解析步骤。  
  3. **复用开源模块**：集成现有的 [repo2txt](https://github.com/donoceidon/repo2txt)（导出仓库文件）和 [gh2md](https://github.com/mattduck/gh2md)（导出 Issue/PR 内容），避免重复造轮子。  
  4. **模板注入**：准备一个静态的 WebGAL 项目模板，仅替换其中的 `.wg` 脚本文件，快速生成游戏包。

## MVP 功能清单

- **仓库提取**：通过命令行调用 repo2txt，将目标仓库导出为一个 `.txt` 文本，内容包含目录结构和文件内容。  
- **Issue/PR 提取**：通过命令行调用 gh2md，导出目标仓库的 Issues 和 PR 评论为一个或多个 Markdown 文档。  
- **上下文构建**：对 repo2txt 和 gh2md 的输出进行简单处理（如拼接或摘要），形成 LLM 的输入上下文。可选地执行轻量分析（如语言检测、文件统计）。  
- **剧情生成**：调用 LLM（如 GPT-4/GPT-3.5 或开源模型），根据上下文生成 WebGAL 脚本格式的剧情剧本。需指定 prompt 模板，引导 LLM 角色化地描述仓库元素。  
- **脚本输出**：将 LLM 输出的文本保存为 `.wg` 脚本文件，格式满足 WebGAL 要求。  
- **WebGAL 打包**：准备一个基础 WebGAL 项目模板（包含 index.html、场景配置、UI 资源等），替换其中的 `.wg` 脚本，打包为可运行的静态网页应用。  
- **CLI/脚本接口**：实现一个命令行工具或脚本，接受 GitHub 仓库地址，按上述流程执行并输出结果；提供清晰的日志和错误提示。  

## 最小可交付产物（示例输入/输出）

- **输入**：一个 GitHub 仓库地址，如 `https://github.com/exampleuser/sample-repo`。  
- **输出**：一个目录或压缩包，包含 WebGAL 项目文件。主要文件包括：  
  - `project.wg`：由 LLM 生成的剧情脚本（示例片段见下）。  
  - `index.html`、`main.js` 等：WebGAL 前端模板文件（来自官方模板，前端代码不变）。  
- **示例 `.wg` 内容片段**（为演示示例，实际内容根据仓库而异）：

  ```wg
  changeScene:城镇夜晚
  say:旁白:「欢迎来到代码之城，这里每个文件都活着。」
  say:主角:这是示例对白，来自仓库的 README。
  choose:探索仓库结构|查看提交记录
  say:系统:你选择了 %选择%。
  ... 
  end
  ```
- **示例上下文 JSON**（供 LLM 输入参考，实际字段可灵活）：

  ```json
  {
    "project": "sample-repo",
    "description": "一个示例项目，用于演示如何生成互动叙事。",
    "languages": ["JavaScript", "HTML", "CSS"],
    "files": [
      {"path": "src/app.js", "role": "入口组件", "summary": "主程序逻辑和界面渲染"},
      {"path": "README.md", "role": "项目介绍", "summary": "说明项目功能和结构"}
    ],
    "issues": [
      {"id": 5, "title": "修复登录 BUG", "summary": "描述了一个登录验证的错误和解决方案"}
    ],
    "commits": [
      {"hash": "a1b2c3d", "message": "初始化项目", "date": "2026-07-01"}
    ]
  }
  ```

## 系统架构图

```mermaid
graph LR
  A[GitHub 仓库] --> B[仓库提取器 (repo2txt)]
  A --> C[Issue 提取器 (gh2md)]
  B --> D[上下文构建器]
  C --> D
  D --> E[LLM 剧情生成器]
  E --> F[脚本输出 (.wg 文件)]
  F --> G[WebGAL 模板注入]
  G --> H[输出：可运行的 WebGAL 项目]
```

## 模块与接口清单

1. **仓库提取器（RepoExtractor）**  
   - **职责**：调用 [repo2txt](https://github.com/donoceidon/repo2txt) 从指定仓库拉取文件并生成文本。  
   - **输入**：GitHub 仓库地址或本地路径；可选分支/tag。  
   - **输出**：输出文件（如 `repo.txt`），内容为仓库目录树和文件内容。  
   - **关键实现**：可使用 `subprocess` 调用 `python repo2txt.py -r <path> -o <file>`，或通过其 pip 包接口。如果在线拉取，可先 `git clone` 再运行。  
   - **错误处理**：无效地址或权限问题时抛出错误提示；如仓库为空或下载失败需检查网络/API token。  

2. **Issue 提取器（IssueExtractor）**  
   - **职责**：调用 [gh2md](https://github.com/mattduck/gh2md) 导出仓库的 issues 和 PR 评论。  
   - **输入**：GitHub 仓库（owner/repo）；可选 API 令牌。  
   - **输出**：Markdown 文件（如 `issues.md`）或目录，每个 issue/PR 为一段文本。  
   - **关键实现**：使用命令行 `gh2md owner/repo output.md`（或 `gh2md owner/repo issues/`）并设置 `GITHUB_ACCESS_TOKEN` 环境变量。  
   - **错误处理**：若缺失访问令牌，API 限制或仓库不存在，需提示用户获取 Token 或检查权限。  

3. **上下文构建器（ContextBuilder）**  
   - **职责**：整合 repo2txt 和 gh2md 的输出，提取关键信息构成 LLM 上下文。  
   - **输入**：`repo.txt` 文件内容，`issues.md` 内容等。  
   - **输出**：结构化的上下文字符串或 JSON（见数据模型示例）。  
   - **关键实现**：可以进行简单处理，如分段摘要（例如取 README 第一段、列出主要文件及其角色）、提取最近的 commit/issue 标题等；或者仅将文本拼接为 prompt 附加说明文字。确保去除无关内容（如代码注释、镜像文件）。  
   - **示例 LLM 提示模板**：  
     ```
     仓库名: {project}
     描述: {description}
     主要文件:
     {path1} - {role1}
     {path2} - {role2}
     ...
     最近 Issues:
     - [{id}] {title}：{summary}
     生成一个 WebGAL 剧本，将以上信息拟人化，角色对话方式呈现仓库故事。
     ```  
   - **错误处理**：若输入文件过大，可截断或分批处理；注意对中文字符进行正确编码；如果出现格式解析错误需记录日志便于排查。

4. **剧情生成器（StoryGenerator）**  
   - **职责**：调用 LLM，根据上下文生成 WebGAL 脚本。  
   - **输入**：上下文字符串或 JSON；包括仓库信息、说明文字、生成要求（如风格、角色设定等）。  
   - **输出**：符合 WebGAL 脚本语法的纯文本（.wg）剧本。  
   - **关键算法 / LLM Prompt**：使用 ChatGPT/GPT-4/本地 LLM，通过精心设计的 Prompt 引导输出。比如提示模型“输出格式必须为 WebGAL 脚本命令，如 `say:角色:对话`、`choose:选项1|选项2` 等”。可在 prompt 中加入指令如：  
     ```
     请扮演一个讲故事的人，根据下面的仓库信息生成一段 WebGAL 视觉小说脚本。请用 say:角色:对白 或 choose:选项1|选项2 等命令格式输出，不要输出其他解释文字。
     仓库名: {project}
     描述: {description}
     主要文件:
     {file summaries...}
     ```
   - **错误处理**：监测 LLM 返回格式是否符合预期（是否包含非法字符、缺少命令等）。必要时可预先校验，如检测输出是否包含 `say:`、`end` 等关键命令，否则认为生成失败。若失败，可重新调用或输出错误。  

5. **模板注入器（TemplateInjector）**  
   - **职责**：将生成的 `.wg` 剧本注入到预置的 WebGAL 前端模板中，生成最终项目。  
   - **输入**：基础 WebGAL 模板文件夹（包含 HTML/CSS/资源），生成的 `script.wg` 或类似文件。  
   - **输出**：修改过 `.wg` 脚本的完整 WebGAL 项目目录。  
   - **关键实现**：可采用文件复制或模版引擎方式：  
     - 准备一个包含空白剧本的模板工程（如从官方示例项目复制），将该剧本文件替换为 `story.wg`。  
     - 更新 manifest 或配置文件引用，以包含新剧本。  
   - **示例 `script.wg`**：  
     ```wg
     changeBg:街道 白天
     say:叙述者:欢迎来到项目的故事。
     say:模块A:我是核心模块，我负责主要逻辑。
     choose:探索更多|结束故事
     say:系统:你选择了 %选择%。
     end
     ```
   - **错误处理**：验证替换后项目能正常打开。若脚本语法错误导致 WebGAL 无法运行，可在开发时用命令行 `yarn dev` 测试（见 [21†L153-L161]）。确保模板路径正确，脚本文件编码无误。

## 数据模型 / Context JSON 示例

以下为参考的 Context JSON 结构示例，可根据实际需求调整（例如是否只用纯文本拼接而不使用 JSON）。示例中包含项目基本信息、文件概览、Issues 和提交历史摘要等字段，用于丰富剧情背景。

```json
{
  "project": "demo-repo",
  "description": "这是一个示例仓库，用于演示 Repo2Gal 的效果。",
  "languages": ["JavaScript", "Node.js"],
  "files": [
    {"path": "src/index.js", "role": "程序入口", "summary": "启动应用并设置路由"},
    {"path": "src/auth.js", "role": "身份验证模块", "summary": "处理用户登录和注册逻辑"}
  ],
  "issues": [
    {"id": 42, "title": "修复登录错误", "summary": "在身份验证模块中修复了一个登录失败的 bug。"}
  ],
  "commits": [
    {"hash": "abc123", "message": "项目初始化", "date": "2026-07-01"}
  ]
}
```

这份 JSON 可在调用 LLM 时先序列化为字符串并附加到提示中，帮助模型理解仓库背景。**注意**：若直接提供 JSON，请确保 LLM 识别能力，否则可将内容人类可读化如上文提示模板所示。

## repo2txt 与 gh2md 接入说明

- **repo2txt**：  
  - 安装：`pip install repo2txt` 或从源码运行。  
  - 示例调用：  
    ```bash
    python repo2txt.py -r https://github.com/exampleuser/demo-repo -o repo.txt
    ```  
    这会在当前目录生成 `repo.txt`，包含仓库结构和文件内容。若仓库私有，需要先 `git clone` 再指定本地路径。  
- **gh2md**：  
  - 安装：使用 pip `pip install gh2md` 或下载其可执行脚本。  
  - 前提：设置环境变量 `GITHUB_ACCESS_TOKEN` 为一个拥有 repo 访问权限的个人访问令牌。  
  - 示例调用：  
    ```bash
    export GITHUB_ACCESS_TOKEN=你的Token
    gh2md exampleuser/demo-repo demo-issues.md --no-closed-prs
    ```  
    该命令将仓库中所有开放的 PR 导出到 `demo-issues.md`。也可用 `--no-issues`、`--multiple-files` 等选项定制输出。  
  - 说明：默认 `gh2md owner/repo output.md` 会导出所有 issues 和 PR。请根据需要调整筛选条件。

## WebGAL 模板注入流程与示例

1. **准备 WebGAL 模板**：从 WebGAL 官方示例或源码仓库获取一个基础项目。比如，可 `git clone https://github.com/OpenWebGAL/WebGAL-Example.git`（假设存在）并切换到 `vue2` 或 `vue3` 版本。或者从 [WebGAL Terre](https://docs.openwebgal.com/getting-started.html) 创建一个新项目后复制其 `src` 文件。  
2. **替换剧本文件**：在模板的资源目录中找到默认剧本文件（通常是 `scene.wg` 或 `script.wg`），用自动生成的 `story.wg` 覆盖它。  
3. **更新引用**：若模板使用配置文件指向剧本，确保已正确指向 `story.wg`。通常无需改动前端逻辑。  
4. **示例 `.wg` 文件片段**（位于模板中）：
   ```wg
   changeScene:城堡大门
   say:旁白:「在这座由代码编织的城堡中，每个文件都有自己的故事。」
   say:英雄:我们开始探索吧！
   ```
5. **打包输出**：将整个项目目录（含 `index.html`、`dist/`、资源等）打包或直接部署至静态服务器，即可在浏览器中运行。用户点击 `index.html` 会看到生成的视觉小说界面。

## 开发与部署步骤

1. **环境准备**：确保安装 Python3、Node.js、Yarn（或 npm）。  
2. **依赖安装**：  
   - Python：`pip install repo2txt gh2md openai`（若使用 OpenAI API）。  
   - 若使用本地 LLM：安装相关库（如 `pip install transformers accelerate`）。  
3. **代码库结构**（示例）：
   ```
   repo2gal-mvp/
   ├── extractor/        # 调用 repo2txt, gh2md 的脚本
   ├── context/          # 上下文构建逻辑
   ├── generator/        # LLM 剧本生成模块
   ├── template/         # WebGAL 模板文件夹
   ├── output/           # 生成结果（WebGAL 项目输出）
   ├── main.py           # 主执行脚本（CLI）
   ├── requirements.txt  
   └── README.md
   ```
4. **本地运行**：例如：
   ```bash
   # 导出仓库文本和 Issue
   python extractor/repo_extractor.py --repo https://github.com/example/repo --output repo.txt
   python extractor/issue_extractor.py --repo example/repo --output issues.md

   # 生成上下文并调用 LLM
   python context/context_builder.py --repo-file repo.txt --issues-file issues.md --output context.json
   python generator/story_generator.py --context context.json --output story.wg

   # 注入 WebGAL 模板
   python template/injector.py --template template/ --script story.wg --output output/
   ```
   用户也可编写一个简单的 shell 脚本或 Python 主程序，将上述步骤串联。  
5. **CI/CD（可选）**：可编写 GitHub Actions 脚本，在推送时自动测试该流程。测试包括给定公开仓库 URL，检查脚本生成是否成功运行（如检查是否生成 `.wg`，可自动启动 WebGAL dev server 验证无语法错误）。  
6. **测试用例**：  
   - 使用不同规模仓库测试：小型示例仓库（几行代码），大型实际项目（上百文件）。  
   - 验证生成脚本的基本正确性：是否包含 `say:`，以及无明显的乱码或不连贯。  
   - 检查 WebGAL 项目能正常启动。  
   - 如采用外部模型，测试网络断连时的表现，确认失败提示。

## 时间估算与里程碑

| 里程碑             | 任务内容                     | 工时（人天） | 说明           |
|------------------|----------------------------|------------|--------------|
| 需求分析及设计         | 确认最终架构、接口规范             | 1          | 完成本文档         |
| 依赖集成           | 集成 repo2txt、gh2md 并测试       | 2          | 主要完成脚本调用示例   |
| 上下文构建逻辑开发       | 编写 ContextBuilder，包括文件摘要      | 3          | 可基于正则/简单算法提取信息 |
| LLM 剧本生成模块开发     | 调用 LLM 接口，设计 Prompt 模板      | 5          | 包括 Prompt 调优，错误检测 |
| WebGAL 模板准备        | 获取并配置静态 WebGAL 项目         | 2          | 确保模板可正常显示   |
| 集成与打包          | 串联所有模块，生成最终输出         | 2          | 开发自动化脚本       |
| 测试与优化          | 功能测试，修复流程中发现的问题      | 3          | 包括生成脚本审校   |
| 文档完善与发布        | 编写 README、示例，发布 MVP 版本   | 1          | 撰写快速上手指南     |

总计约 **19 人天**。考虑迭代和意外情况，可预留 1-2 周的缓冲。里程碑可并行推进，如部署与测试可与后续开发交替进行。

## 风险与缓解措施

- **LLM 输出不稳定**：可能出现格式错误或与上下文不符的内容。*缓解*：设计严格的 Prompt，引导输出格式（只返回脚本）；对输出进行简单校验（如检测是否含有 `say:` 等关键字）；若格式错误则重试或加入后处理校正逻辑。  
- **调用成本与速度**：使用 OpenAI API 会产生成本（约\$0.002–0.06/消息），响应速度取决于网络；本地 LLM 则需要 GPU 资源（如 Llama 70B 大约 \$200–500/月，否则响应慢）。*缓解*：初期可用 OpenAI API 以快速验证功能；后期如需大量生成，可评估使用本地模型（如使用中文 ChatGLM/英文学习模型）以控制成本。  
- **GitHub 接口限制**：若仓库特别大或项目私有，repo2txt/gh2md 可能耗时或失败。*缓解*：要求用户提供 Access Token；对大型项目，可先进行 `git clone` 并分部分调用；对超大文件（如视频、模型文件）自动忽略。  
- **WebGAL 兼容性**：生成的 `.wg` 脚本可能与特定 WebGAL 版本不兼容。*缓解*：选择稳定的 WebGAL 版本（如官方推荐的最新版），并在模板注入前进行语法验证。  
- **项目规模与维护**：当前为 MVP，后续需求可能膨胀。*缓解*：本实施方案明确在单脚本层面完成，如果未来添加分支剧情、角色定义等，可作为后续扩展（见下节）。  

## 后续扩展建议

- **引入知识图谱分析**：如同 [CodeGraph](https://gitcode.csdn.net/6a169e7310ee7a33f27595f3.html) 的思路，可预先解析仓库结构和依赖关系，构建代码元素知识图谱。这可帮助生成更准确的角色与事件描述。（例如，分析依赖关系生成“守护者”“入侵者”故事情节。）  
- **插件系统设计**：参考 v7/v8 文档可分离功能模块，如 `github_history` (将 commit 历史转为剧情)、`contributor_story` (根据贡献者数据生成人物形象)、`code_tagging` (自动标注文件类型并故事化)。未来可让社区编写新的“故事生成插件”，丰富素材。  
- **多轮交互与分支剧情**：当前 MVP 输出单线剧情。后续可根据用户选择（使用 WebGAL `choose` 命令）设计分支故事，或允许用户提出问题，生成新的剧情分支。  
- **多语言与本地化**：支持根据仓库语言自动选用生成脚本语言（中/英文），或翻译功能。  
- **Web 界面**：除命令行外，可开发简单的网页界面，用户输入仓库地址后展示生成的故事，甚至在页面中直接运行 WebGAL。  
- **性能优化**：对于大型仓库，可使用增量更新或缓存机制（如只针对最新提交生成故事）。  

本实施方案聚焦于核心流程，可作为后续功能扩展的坚实基础。通过清晰的模块划分和文档说明，任何开发者都能根据此计划快速上手，逐步完善 Repo2Gal 项目。  

**参考资料**：仓库提取使用 [repo2txt](https://github.com/donoceidon/repo2txt)；Issue 导出使用 [gh2md](https://github.com/mattduck/gh2md)；本地知识图谱加速示例见 CodeGraph；OpenAI API 与本地 LLM 性能成本对比参考。