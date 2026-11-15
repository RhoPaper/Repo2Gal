# Repo2Gal 当前架构

> 本文描述**当前实现和已锁定的边界**。历史设想放在 `docs/dev/early/`，不得把早期规划当成现状。

当前基线：`v0.9.0`。Chronicle 主流程已于 2026-07-31 在真实 GitHub 仓库和真实 LLM
环境中端到端实测通过。v0.4.0 落地 Asset Pack v1；v0.5.0 增加显式 Performance Plan
动态演出；v0.6.0 新增仓库概览（Overview）模式；v0.6.1 修复旁白继承上一句 speaker 的问题；
v0.6.2 明确 Overview 不使用旁白；v0.7.0 把剧本生成重构为三轮 LLM（自由创作草稿 →
自然语言演出批注 → Director Plan JSON）+ 确定性编译 + 有界重试，合并原 Performance
通道并删除插入式合并；v0.8.0 新增 Quick Start（贡献者上手）模式，按模式选择 Issue
采集范围并确定性提取起步任务，同时把“不使用旁白”收敛为 config 的
`NARRATION_FREE_MODES`；v0.9.0 增加 LLM 模型降级链与瞬时故障重试、`REPO2GAL_MODE`
环境变量与增量采集优化，并把 GitHub Pages 部署流水线参数化为跨仓库可复用。

版本号采用 SemVer 2.0.0；v0.7.0 删除 `--performance` 系列 CLI 参数并以三轮生成取代，
属于公开不兼容变更；v0.8.0 新增 Quick Start 模式属于向后兼容的新功能；v0.9.0 新增
LLM 模型降级链与 `REPO2GAL_MODE`，并把 `RunOptions.model` 改为 `models`，按 0.y.z 规则
都提升 MINOR。
完整升级与多文件同步规则见 `CONTRIBUTING.md`「版本管理」。

## 1. 产品定位

Repo2Gal 是“可游玩的开源项目文档生成器”，不是通用 Galgame 生成器。

当前实现三种剧本模式：

| `--mode` | 目标玩家 | 素材重点 | 剧情体验 |
|---|---|---|---|
| `chronicle`（默认） | 想了解项目历史、社区演变的人 | Issue/PR/Discussion、Release、README、wiki | 史诗编年史 |
| `overview` | 第一次接触项目的人 | README、目录树、根级项目文件、Release、wiki | 新手村向导导览 |
| `quickstart` | 想交出第一个改动的贡献者 | CONTRIBUTING、构建/测试入口与 CI 定义、目录树、README、新人友好 Issue | 老维护者带上手 |

Overview 与 Quick Start 都不使用旁白：带路角色全程说话，规则由
`config.NARRATION_FREE_MODES` 单一持有。RP 圆桌模式（`--rp`）仍依赖外部 KiMo 引擎，
属于计划项。不要擅自把 MVP 扩成通用 Galgame、RPG 或可视化 IDE。

## 2. 数据流

```text
Local Asset Pack (optional)
       │
       ▼
asset_pack.load_asset_pack()       Schema / SPDX / path / MIME / SHA / Profile
       │
       ├──────────────────────────────────────────────────────────┐
       │                                                          │
GitHub repository                                                 │
       │
       ├──► python-github-backup     认证 / 分页 / 限流 / 重试 / GraphQL / Git clone
       │               │
       │               ▼
       │    按模式落盘的原始备份
       │    Chronicle：源码 + Issue/PR/Discussion + wiki + Release + label + milestone
       │    Overview：源码 + wiki + Release（轻量，不拉社区讨论）
       │
       └──► GitHub official REST     单次仓库概览：description / Star / topics 等
                       │
                       ▼
.repo2gal/backups/<owner>/           可审计、可增量、可复用的原始数据
       │
       ▼
fetcher.context_from_backup()        确定性归一化与热门素材筛选；
       │                             Overview 另提取目录树 + 根级项目文件摘录
       ▼
RepoContext
       │
       ▼
generator.build_cast()               确定性按模式选角（角色表白名单）
       │
       ▼
generator.build_prompt()             确定性组装第一轮创作 prompt（只暴露逻辑素材 ID）
       │
       ▼
OpenAI-compatible LLM                director 三轮（llm.LLMClient 薄传输）：
       │                             1) 自由创作草稿（[B] 锚点，无语法负担）
       ├── director.canonicalize_draft()
       │                             2) 自然语言演出批注（按 beat 锚定，禁止命令）
       │                             3) Director Plan v1 JSON（受限语义）
       ▼                             └─ 校验失败 -> 结构化反馈 -> 有界重试（默认 2）
director.validate_director()         Schema / 能力表 / 角色状态机 / 预算
       │
       ▼
director.compile_director()          确定性生成 WebGAL（label=beat id、转场并入 changeBg）
       │                             重试耗尽 -> compile_draft_fallback() 草稿兜底
       ▼
validator.sanitize()                 命令/角色/逻辑素材 ID 校验与死跳转修复（硬边界）
        │                            编译产物用 COMPILE_COMMANDS，--script 用 SAFE_COMMANDS
        ▼
packager.package()                   WebGAL 模板 + 素材/演出适配 + notices，staging 内完成
       │
       ▼
output/<repo>/ 或 output/<repo>-<mode>/  可由任意静态服务器托管
```

整条流程由 `pipeline.py` 编排（`--dry-run` × `--script` 四模式矩阵，再叠加
`--mode` 剧本模式）：主线是直线，唯一环路是第三轮导演 JSON 的有界重试，不存在
agent 工具调用循环。`cli.py` 只负责参数映射与结果渲染。阶段依赖（fetch/LLM/package）
可注入，流水线可离线端到端测试。

## 3. 外部依赖边界

### 3.1 GitHub 数据：python-github-backup

依赖：[`josegonzalez/python-github-backup`](https://github.com/josegonzalez/python-github-backup)

- 许可证：MIT
- 当前锁定范围：`>=0.65,<0.66`
- Python：3.10+
- 接入方式：subprocess 调用其公开 CLI
- 当前已用能力：repository clone、Issue/评论/event/timeline、PR/评论/review/commit、
  Discussion/回复、wiki、Release、label、milestone、增量备份

Repo2Gal **不负责**：

- 通用 GitHub REST/GraphQL 认证管理
- API 分页
- 速率限制与节流
- 网络重试
- Discussion GraphQL 查询
- wiki/source clone
- Issue/PR 增量 checkpoint

这些能力若出现问题，优先升级、配置或向上游贡献，不得先在本项目复制一套。

默认未启用的上游能力：

| 能力 | 原因 |
|---|---|
| Release assets | 可能包含数 GB 二进制，与文本叙事无直接关系 |
| Issue/PR/Discussion attachments | 可能很大且包含不受信任文件，未来显式开启 |
| hooks | 需要额外权限，且不是叙事素材 |
| security advisories | 权限和公开性不一致，后续单独设计 |
| LFS objects | 体积不可控，默认源码 clone 足够 |

不要把上游的 `--all` 直接作为默认值：它会隐式包含 hooks 与 Release assets。

剧本模式对应三套显式 flags，都定义在 `fetcher.py`：

| 模式 | flags | 说明 |
|---|---|---|
| `chronicle` | `NARRATIVE_BACKUP_FLAGS` | 源码 + Issue/PR/Discussion + wiki + Release + label/milestone + fork |
| `overview` | `OVERVIEW_BACKUP_FLAGS` | 只采源码 + Release + wiki；概览不需要社区讨论，显著降低首次备份时间 |
| `quickstart` | `QUICKSTART_BACKUP_FLAGS` | 只采源码 + Issue/评论 + wiki；贡献者上手需要真实起步任务，但不需要 PR/Discussion/Release |

复用已有备份时不重采数据；Overview 跳过社区 JSON 解析，Quick Start 只解析 Issue JSON，
因此即使复用 Chronicle 的完整备份也保持快速。

### 3.2 官方 GitHub REST API 例外

仓库数据采集模块允许直接调用 GitHub 官方 REST API，但边界严格限制为：

- 只使用 `https://api.github.com` 的公开、版本化 REST endpoint；
- 只补充 `python-github-backup` 未落盘且 RepoContext 确实需要的数据；
- 当前仅调用 `GET /repos/{owner}/{repo}`；
- 使用 GitHub 官方 API 版本头和现有 `GITHUB_TOKEN`；
- REST 补充失败不得破坏完整备份主流程；
- 禁止抓取 `github.com` HTML、搜索结果、非官方镜像或其他网页；
- 禁止自建通用 GitHub API 客户端、GraphQL 客户端、分页器、限流器和重试框架。

新增 endpoint 时必须在本文记录用途和上游缺口，并提供离线 mock 测试。

### 3.3 渲染：OpenWebGAL/WebGAL

- 许可证：MPL-2.0
- 接入方式：下载固定版本官方 `*-web.zip`，校验 SHA-256，按版本缓存后复制
- 约束：黑盒使用，不修改引擎源码
- 场景入口：`game/scene/start.txt`
- 权威语法来源：WebGAL parser 源码，而非早期规划或模型记忆

详见 `docs/dev/webgal-script-reference.md`。

### 3.4 LLM

- 协议：OpenAI-compatible Chat Completions
- 默认配置：环境变量 `REPO2GAL_BASE_URL`、`REPO2GAL_MODEL`、`REPO2GAL_API_KEY`
- LLM 只负责三轮生成式任务：剧情草稿创作、自然语言演出批注、受限 Director Plan JSON。
  不负责 GitHub 抓取、角色白名单、WebGAL 命令、坐标、时序、流程校验和资源打包；
  第三轮失败只允许有界重试（默认 2 次），不允许无界循环
- 三轮温度：创作 0.8、批注 0.3、导演 JSON 0.2

### 3.5 Asset Pack 标准校验依赖

Asset Pack 基础标准不自行实现：Draft 2020-12 使用 `jsonschema`，SemVer 使用 `semver`，
SPDX expression 使用 `packaging.licenses`，BCP 47 使用 `langcodes`，CSS Color 使用
`coloraide`，magic MIME 使用 `python-magic` + 系统 `libmagic`。完整调研、维护状态、采用度、
许可证和安全风险见 `docs/dev/asset-pack-dependencies.md`。

`libmagic` 仅在实际加载素材包时延迟导入；未使用 `--asset-pack` 的原有流程不依赖系统库。

## 4. 模块职责

| 文件 | 职责 | 不应承担 |
|---|---|---|
| `fetcher.py` | 按模式调上游备份工具；受控官方 REST 补充；构建 `RepoContext`；Overview 目录树/项目文件、Quick Start 贡献者入口文件与起步任务提取 | HTML 爬虫、通用 API 客户端 |
| `generator.py` | 确定性按模式选角、上下文渲染、第一轮创作 prompt 组装 | GitHub 抓取、WebGAL 打包、网络调用 |
| `director.py` | 草稿规范化、批注/导演 prompt、Director Plan Schema/语义校验、确定性 WebGAL 编译、重试反馈与草稿兜底 | 网络调用、WebGAL 打包 |
| `llm.py` | LLM transport 薄客户端：请求、错误包装、脱敏 | prompt 策略、重试框架 |
| `validator.py` | WebGAL 安全子集、流程完整性、静默错误降级、旁白 `-clear` 归一化 | 改写剧情内容 |
| `webgal.py` | 经源码核实的命令常量（SAFE/COMPILE 白名单）与转义 | 猜测引擎语法 |
| `packager.py` | 获取发行版、原子替换、最小 flowchart、输出静态站点 | 修改 WebGAL 引擎 |
| `asset_pack.py` | Schema、本地路径/授权/MIME/SHA/Profile 校验与本地包初始化 | 下载素材、执行包内脚本 |
| `webgal_assets.py` | 逻辑 ID 映射、素材复制、脚本重写、第三方声明聚合 | 转码、多包覆盖、许可证猜测 |
| `performance.py` | 演出编译内核：能力表、profile、动作级 WebGAL 编译与共享状态工具 | 直接信任 LLM 命令、任意引擎参数 |
| `pipeline.py` | 流程编排唯一持有者：执行矩阵、三轮生成与有界重试、阶段产物传递 | 参数解析、终端渲染 |
| `config.py` | 默认值（含剧本模式与重试次数）、环境解析、路径常量、密钥脱敏显示 | 业务逻辑 |
| `errors.py` | 统一错误类型与退出码契约、错误正文脱敏 | 业务逻辑 |
| `cli.py` | 参数解析、结果渲染、退出码映射 | 流程逻辑实现 |

## 4.1 错误码契约

每个错误类型固定对应一个 CLI 退出码（`errors.py` 是唯一权威来源）：

| 类型 | 退出码 | 场景 |
|---|---|---|
| `UsageError` | 2 | 参数/模式冲突、仓库标识或 `--script` 无法读取 |
| `AssetPackError` | 2 | 本地素材包 Schema、授权、路径、MIME 或完整性错误 |
| `FetchError` | 3 | 采集或备份不可用 |
| `GenerationError` | 4 | LLM 网络/HTTP/格式错误（已脱敏） |
| `ValidationFailed` | 5 | `--strict` 下 validator 存在降级 |
| `PackageError` | 6 | 模板下载、产物构建或替换失败 |
| 未预期异常 | 1 | cli 兜底，附完整 traceback |

## 5. 原始数据与上下文

原始备份目录：

```text
.repo2gal/backups/<owner>/
└── repositories/<repo>/
    ├── repo2gal-repository.json # 官方 REST 仓库概览
    ├── repository/       # Git clone
    ├── wiki/             # wiki Git clone（存在时）
    ├── issues/*.json
    ├── pulls/*.json
    ├── discussions/*.json
    ├── releases/*.json
    ├── labels/
    └── milestones/
```

`RepoContext` 是面向 LLM 的有损视图，不是备份格式。全量原始数据必须保留，
上下文只选评论最活跃的 Top N 条并做长度控制。

Overview 额外携带两类确定性提取字段，均由 Context Builder 生成：

- `file_tree`：从 Git tree（非 Git 备份回退为文件遍历）渲染的浅层目录树。
  依赖目录、构建产物、缓存目录整体过滤，深度、行数与字符数均有上限。
- `project_files`：根级 `pyproject.toml`、`package.json`、`Cargo.toml`、`Dockerfile`、
  `CONTRIBUTING.md` 等安装/构建/贡献入口文件的摘录；逐文件与总量均有上限。

Overview 模式下不解析 `issues/`、`pulls/`、`discussions/` JSON；这些字段仍然完整保留在
原始备份层，仅不进入 Overview 的 `RepoContext`。

Quick Start 额外携带两类确定性提取字段，同样由 Context Builder 生成：

- `contributor_files`：贡献者入口文件摘录——CONTRIBUTING/DEVELOPMENT/HACKING、
  构建与测试入口（Makefile、tox.ini、pyproject.toml、package.json 等）、PR 模板与
  行为准则，外加按前缀确定性发现的 CI 工作流（`.github/workflows/*.yml`，最多 3 个）；
  候选路径按仓库内相对路径匹配，因此 `.github/CONTRIBUTING.md` 这类嵌套路径也能命中，
  逐文件与总量沿用同一套上限。
- `starter_issues`：开放状态且带 `good first issue`、`help wanted`、`beginner` 等标签的
  Issue，按编号倒序取前 `--threads` 条；仓库没有这类标签时为空，此时 prompt 明确要求
  讲解如何自行筛选任务、不得编造 Issue 编号。

Quick Start 模式下不解析 `pulls/`、`discussions/`、`releases/` JSON；这些数据仍完整保留在
原始备份层。

当前上游不会把仓库列表元数据单独落盘。v0.2.0 通过官方
`GET /repos/{owner}/{repo}` 补齐，并保存为 `repo2gal-repository.json`，供离线复用。

## 6. 进度反馈

- `github-backup` 的 stdout/stderr 逐行转发到 CLI，展示当前资源和保存阶段；
- WebGAL zip 使用流式下载，每约 10% 报告百分比和已下载 MB；
- 进度显示不得输出 token、Authorization header 或带凭据 URL；
- 日志不是数据协议，Context Builder 只读取上游落盘文件。

## 7. 为什么 validator 是硬边界

WebGAL 对未知命令不会报错，而会把命令名当作 speaker：

```ts
return SCRIPT_CONFIG_MAP.get(command)?.scriptType ?? commandType.say;
```

所以 LLM 输出 `showCode:print(1);` 时，游戏会正常启动，但出现一个名叫 `showCode`
的角色。validator 必须在打包前执行，并且不可通过“模型应该不会出错”绕过。

4.6.2 还有一个已实测确认的静默错误：`say` 先继承 `stageState.showName`，只有
`-clear` 参数才清空说话人（`packages/webgal/src/Core/gameScripts/say.ts`），
无冒号的纯文本行则会被 parser 把整行当作 speaker。因此 validator 把 `say:`、
`:文本`、无冒号文本与未知命令降级统一编译为 `say:文本 -clear;`。

v0.7.0 起 LLM 不再直接输出 WebGAL 文本，validator 的输入分两类：

- 确定性编译产物（`director.compile_director`）：使用 `COMPILE_COMMANDS` 白名单
  （`SAFE_COMMANDS` + `pixiInit`/`pixiPerform`/`setTransform`/`setTempAnimation`）；
- `--script` 用户脚本：仍收敛在 `SAFE_COMMANDS`。

两类输入都必须过 sanitize；编译产物理论上永远通过（否则是编译器 bug，属于错误
而非第三轮重试目标）。

## 8. 素材系统（Local Provider 已实现）

素材来源插件化，但格式统一：

```text
Local Provider ───┐
Git Provider ─────┼──> Repo2Gal Asset Pack ──> Validator ──> WebGAL Adapter
AI Provider ──────┘
```

v0.4.0 只实现 Local Provider，Git/AI Provider 仍是计划；核心没有 Provider 插件注册框架。
一次只接受一个目录包，避免在没有真实需求时设计多包覆盖和依赖解析。

素材包必须引擎无关。剧本引用逻辑 ID，例如 `background.archive`，WebGAL Adapter
确定性映射为 `game/background/background-archive.png` 等目标。当前三种剧本模式共用
`background`、`character`、`bgm` 三类素材；不指定包时继续使用 WebGAL 默认文件名，指定包时
默认背景/BGM 也会合并进 prompt 与 validator catalog，并由 Adapter 原样放行。
逻辑 ID 强制以素材类型和点号开头，不能与 WebGAL 默认裸文件名形成歧义或遮蔽。

角色可用归一化 `framing` 标注 `top`、`bottom` 和 `centerX`。WebGAL Adapter 根据
2560×1440 设计舞台计算 `changeFigure -transform`，保留全身原图但默认呈现居中半身构图；
演出编译器在移动、摇晃和缩放时继续保留该 framing。
未声明 framing 的角色也会使用默认 contain transform 和中心基准，避免 WebGAL 原生
`left/right` 基准与演出语义槽位产生双重偏移。剧情重复换图、退场和前向分支汇合
会进入状态版本/合并分析；汇合状态不一致的角色不允许继续生成目标动画。

校验顺序为：1 MiB 有界读取/重复键 → Draft 2020-12 Schema 与标准格式 → 普通文件和路径
边界 → 扩展名与 magic MIME → SHA-256 → Profile → 公开授权策略。媒体单文件上限 128 MiB，
授权材料单文件上限 8 MiB、最多 512 个，全部声明文件总计上限 512 MiB。

包内读取使用逐级 `openat` + `O_NOFOLLOW`，打包时在同一个源文件描述符上完成哈希与复制；
目标使用 `O_EXCL` 创建，避免检查与复制之间重新跟随符号链接。缺少这些 OS 能力的平台会拒绝
Asset Pack，但不影响 WebGAL 默认素材路径。AI provenance 的 `promptFile` 也按授权材料校验、
哈希和保留；Git provenance 仅离线校验 URL/revision 结构，不声称验证远端内容。

打包器保留 WebGAL 默认标题图、标题 BGM 和 Logo，外部包素材使用带完整逻辑 ID 的文件名，
拒绝覆盖模板文件。所有产物根目录生成 `THIRD_PARTY_NOTICES.md`，并补入官方 web zip 未携带
的 MPL-2.0 正文及对应版本源代码 URL；外部包的原始 manifest、LICENSE、NOTICE 和逐文件
evidence 保存在 `third_party/asset-packs/`。

内置 CC0 包属于 `repo2gal` package-data，随 wheel 分发，通过 `builtin:cc0-chronicle` 解析，
不依赖当前工作目录。

完整规范见 `docs/dev/asset-pack-spec.md`。

## 9. 许可证边界

已锁定的分层：

| 组件 | 许可证 |
|---|---|
| Repo2Gal 程序代码 | GPL-3.0（根目录 `LICENSE`） |
| WebGAL | MPL-2.0，保持原许可证 |
| python-github-backup | MIT |
| Asset Pack | 各自许可证，必须 SPDX 标识并保留 NOTICE |
| 用户生成剧本 | 由用户和所用模型条款决定 |

程序采用 GPL-3.0 不意味着外部媒体自动变成 GPL。v0.4.0 打包器会聚合素材包声明并生成
`THIRD_PARTY_NOTICES.md`，同时保留原始许可证材料。

## 10. 当前状态与下一步

已完成：

- Chronicle 模式通路（默认）
- Overview（仓库概览）模式通路：轻量采集、独立 prompt、目录树/项目文件上下文
- python-github-backup 采集适配层（两套显式 flags）
- 源码、README、Issue、PR、Discussion、wiki、Release 上下文归一化
- 原始备份复用与上游增量备份
- LLM prompt 与确定性角色表（按模式生成）
- WebGAL validator
- 固定版本、SHA-256 校验的官方 WebGAL 发行版模板注入
- CLI 与离线测试
- 真实仓库 + 真实 LLM + WebGAL 产物端到端验证（Chronicle）
- `github-backup` 实时采集进度与 WebGAL 下载百分比
- 官方 GitHub REST 仓库概览及离线落盘
- v0.3.0：显式管线（pipeline.py）、统一错误域（errors.py）、配置集中（config.py）、
  LLM 薄客户端（llm.py）、原子打包与最小 flowchart、`--dry-run` 模式矩阵语义修正
- v0.4.0：Asset Pack v1 Schema、Local Provider、素材逻辑 ID validator、WebGAL Adapter、
  `THIRD_PARTY_NOTICES.md` 和 CC0 Chronicle 示例包
- v0.5.0：显式 `--performance`、Beat Manifest、Performance Plan v1、演出状态机与
  WebGAL 4.6.2 确定性编译
- v0.6.0：`--mode overview`、Overview prompt、轻量 flags、目录树/项目文件提取与
  概览专用选角
- v0.6.1：validator 对所有旁白确定性补 `-clear`，无冒号文本统一转旁白，
  修复 WebGAL 4.6.2 旁白继承上一句 speaker 的静默错渲染
- v0.6.2：Overview prompt 明确该模式不使用旁白，向导自我介绍、过渡与收尾
  全部写成项目化身的台词，避免 LLM 把角色台词生成成 `say:`
- v0.7.0：剧本生成重构为三轮 LLM（自由创作草稿 → 自然语言演出批注 → Director Plan
  JSON）+ 确定性编译；合并原 `--performance` 通道（演出默认内建，`--profile` 控制
  风格与预算）；第三轮校验失败结构化回喂、有界重试（`--format-retries`，默认 2），
  重试耗尽走草稿确定性兜底；删除 `--performance`/`--performance-profile`/
  `--strict-performance`/`--save-*` 旧参数，新增 `--save-stage-outputs`
- v0.8.0：新增 Quick Start（贡献者上手）模式——独立采集 flags（源码/Issue 与评论/wiki）、
  贡献者入口文件（CONTRIBUTING、构建/测试入口、CI 工作流，按仓库内相对路径匹配，
  支持 `.github/workflows/*.yml` 这类嵌套路径）与起步任务（开放且带
  `good first issue`/`help wanted`/`beginner` 等标签的 Issue）确定性提取；
  `RepoContext` 增加 `contributor_files` 与 `starter_issues`；Overview 与 Quick Start
  统一按 `NARRATION_FREE_MODES` 拒绝 narration 与无说话人的 choice 文本
- v0.9.0：LLM 模型降级链（`--model`/`REPO2GAL_MODEL` 支持逗号分隔，429/5xx 同模型
  重试、404 直接切换、最近成功模型提到链首；公开 API 改为 `RunOptions.models` 与
  `resolve_model_chain`）；`--mode` 读取 `REPO2GAL_MODE`；增量备份补
  `--incremental-by-files`；GitHub Pages 流水线参数化（仓库 variables/secrets 驱动，
  可选定时更新），Vercel 仍是本仓库生产路径；validator 放行 `changeFigure:none`
  保留取值，修复角色退场被误降级；导演 prompt 与 `jump` 形状修复；新增
  `tests/fixtures/github-backup-sample/` 落盘结构回归样本

`v0.9.0` 结论：Chronicle、Overview、Quick Start、单本地素材包闭环和动态演出均已实现；
多场景拆分、RP 圆桌模式与 Git/AI Provider 仍是计划，不得写成现有能力。

三轮生成默认开启，三种剧本模式通用。第一轮只写故事（`[B]` 锚点），第二轮按 beat
写自然语言演出批注，第三轮输出与草稿一一对应的 Director Plan JSON；`director.py`
执行 Schema/能力表/角色状态机/预算校验并确定性编译 WebGAL（label = beat id，
`screen.transition` 并入同 beat 的 changeBg）。校验失败的错误清单回喂第三轮重试；
重试耗尽后由 `compile_draft_fallback()` 只凭草稿拼出可玩脚本。协议与编译边界见
`docs/dev/director-plan-spec.md`。

推荐下一步：

1. 用真实 LLM 和 CC0 示例包端到端验证三轮流程（创作/批注/导演 JSON 的质量与重试率），
   建立固定仓库 golden cases；Quick Start 另需验证起步任务是否被如实引用、无标签仓库
   是否遵守“不编造编号”。备份解析器的落盘结构回归样本已在 v0.9.0 补齐
   （`tests/fixtures/github-backup-sample/`），后续按上游格式变化滚动更新。
2. 再考虑多场景拆分与 RP 圆桌模式（后者依赖外部 KiMo 引擎）；实现 Git Asset Provider
   前必须重新调研成熟 Git/归档依赖。
3. AI Provider 继续后置，先明确服务条款快照、Prompt/seed 与 `LicenseRef-AI-*` 策略。
