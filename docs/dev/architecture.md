# Repo2Gal 当前架构

> 本文描述**当前实现和已锁定的边界**。历史设想放在 `docs/dev/early/`，不得把早期规划当成现状。

当前基线：`v0.4.0`。Chronicle 主流程已于 2026-07-31 在真实 GitHub 仓库和真实 LLM
环境中端到端实测通过。v0.3.0 完成显式管线与统一错误域重构；v0.4.0 落地 Asset Pack v1
Schema、Local Provider、WebGAL Adapter、第三方声明聚合和内置 CC0 示例包。

## 1. 产品定位

Repo2Gal 是“可游玩的开源项目文档生成器”，不是通用 Galgame 生成器。

当前 MVP 只实现 Chronicle（编年）模式：从真实源码、README、Issue、PR、Discussion、
wiki 与 Release 中提炼项目历史，生成 WebGAL 静态站点。

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
       │    完整源码与社区原始备份
       │
       └──► GitHub official REST     单次仓库概览：description / Star / topics 等
                       │
                       ▼
.repo2gal/backups/<owner>/           可审计、可增量、可复用的原始数据
       │
       ▼
fetcher.context_from_backup()        确定性归一化与热门素材筛选
       │
       ▼
RepoContext
       │
       ▼
generator.build_cast()               确定性选角（角色表白名单）
       │
       ▼
generator.build_prompt()             确定性 prompt 组装（只暴露逻辑素材 ID）
       │
       ▼
OpenAI-compatible LLM                唯一非确定性步骤：写剧本（llm.LLMClient）
       │
       ▼
validator.sanitize()                 命令/角色/逻辑素材 ID 校验与死跳转修复（硬边界）
       │
       ▼
packager.package()                   WebGAL 模板 + 素材适配 + notices，staging 内完成
       │
       ▼
output/<repo>/                       可由任意静态服务器托管
```

整条直线由 `pipeline.py` 编排（四模式矩阵，见 README「模式矩阵」），`cli.py` 只负责
参数映射与结果渲染。阶段依赖（fetch/LLM/package）可注入，流水线可离线端到端测试。

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
- LLM 只负责叙事创作，不负责 GitHub 抓取、角色白名单、流程校验和资源打包

### 3.5 Asset Pack 标准校验依赖

Asset Pack 基础标准不自行实现：Draft 2020-12 使用 `jsonschema`，SemVer 使用 `semver`，
SPDX expression 使用 `packaging.licenses`，BCP 47 使用 `langcodes`，CSS Color 使用
`coloraide`，magic MIME 使用 `python-magic` + 系统 `libmagic`。完整调研、维护状态、采用度、
许可证和安全风险见 `docs/dev/asset-pack-dependencies.md`。

`libmagic` 仅在实际加载素材包时延迟导入；未使用 `--asset-pack` 的原有流程不依赖系统库。

## 4. 模块职责

| 文件 | 职责 | 不应承担 |
|---|---|---|
| `fetcher.py` | 调上游备份工具；调用受控官方 REST 补充；构建 `RepoContext` | HTML 爬虫、通用 API 客户端 |
| `generator.py` | 确定性选角、上下文渲染、prompt 组装 | GitHub 抓取、WebGAL 打包、网络调用 |
| `llm.py` | LLM transport 薄客户端：请求、错误包装、脱敏 | prompt 策略、重试框架 |
| `validator.py` | WebGAL 安全子集、流程完整性、静默错误降级 | 改写剧情内容 |
| `webgal.py` | 经源码核实的命令常量与转义 | 猜测引擎语法 |
| `packager.py` | 获取发行版、原子替换、最小 flowchart、输出静态站点 | 修改 WebGAL 引擎 |
| `asset_pack.py` | Schema、本地路径/授权/MIME/SHA/Profile 校验与本地包初始化 | 下载素材、执行包内脚本 |
| `webgal_assets.py` | 逻辑 ID 映射、素材复制、脚本重写、第三方声明聚合 | 转码、多包覆盖、许可证猜测 |
| `pipeline.py` | 流程编排唯一持有者：四模式矩阵、阶段产物传递 | 参数解析、终端渲染 |
| `config.py` | 默认值、环境解析、路径常量、密钥脱敏显示 | 业务逻辑 |
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
确定性映射为 `game/background/background-archive.png` 等目标。当前 Chronicle MVP 支持
`background`、`character`、`bgm` 三类素材；不指定包时继续使用 WebGAL 默认文件名，指定包时
默认背景/BGM 也会合并进 prompt 与 validator catalog，并由 Adapter 原样放行。
逻辑 ID 强制以素材类型和点号开头，不能与 WebGAL 默认裸文件名形成歧义或遮蔽。

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

- Chronicle 单模式通路
- python-github-backup 采集适配层
- 源码、README、Issue、PR、Discussion、wiki、Release 上下文归一化
- 原始备份复用与上游增量备份
- LLM prompt 与确定性角色表
- WebGAL validator
- 固定版本、SHA-256 校验的官方 WebGAL 发行版模板注入
- CLI 与离线测试
- 真实仓库 + 真实 LLM + WebGAL 产物端到端验证
- `github-backup` 实时采集进度与 WebGAL 下载百分比
- 官方 GitHub REST 仓库概览及离线落盘
- v0.3.0：显式管线（pipeline.py）、统一错误域（errors.py）、配置集中（config.py）、
  LLM 薄客户端（llm.py）、原子打包与最小 flowchart、`--dry-run` 模式矩阵语义修正
- v0.4.0：Asset Pack v1 Schema、Local Provider、素材逻辑 ID validator、WebGAL Adapter、
  `THIRD_PARTY_NOTICES.md` 和 CC0 Chronicle 示例包

`v0.4.0` 结论：Chronicle MVP 与单本地素材包闭环均已实现；Git/AI Provider 仍是计划，
不得写成现有能力。

推荐下一步：

1. 给备份解析器增加真实 `python-github-backup` fixture 回归样本。
2. 用真实 LLM 和 CC0 示例包评估 Chronicle prompt，建立固定仓库 golden cases。
3. 再考虑多场景拆分和 Git Asset Provider；实现 Git Provider 前必须重新调研成熟 Git/归档依赖。
4. AI Provider 继续后置，先明确服务条款快照、Prompt/seed 与 `LicenseRef-AI-*` 策略。
