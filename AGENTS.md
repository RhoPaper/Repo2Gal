# Repo2Gal Agent Handoff Guide

本文件是未来 AI Agent 和贡献者进入仓库后的第一入口。它描述当前真实状态、不可破坏的边界和工作方式。

## 1. 项目目标

Repo2Gal 把 GitHub 仓库转换为基于 WebGAL 的“可游玩开源项目文档”。

当前实现三种剧本模式：Chronicle（编年，默认）使用真实源码、README、Issue、PR、
Discussion、wiki 和 Release 生成项目历史视觉小说；Overview（仓库概览）使用源码、
README、目录树、根级项目文件、Release 与 wiki 生成面向新手的“项目导览”视觉小说；
Quick Start（贡献者上手）使用源码、README、目录树、贡献者入口文件（CONTRIBUTING、
构建/测试入口、CI 工作流）与新人友好 Issue 生成“从跑起来到第一个改动”的上手视觉小说。
不要擅自把 MVP 扩成通用 Galgame、RPG 或可视化 IDE。

当前稳定基线为 `v0.9.0`：v0.1.0 主流程已于 2026-07-31 通过真实仓库、真实 LLM
和 WebGAL 产物的端到端实测；v0.3.0 重构流程架构（显式管线 + 统一错误域 + 薄 CLI）；
v0.4.0 实现 Asset Pack v1 本地单包闭环与内置 CC0 Chronicle 示例包；v0.5.0 实现显式
Performance Plan v1 动态演出闭环；v0.6.0 实现仓库概览（Overview）模式；v0.6.1 修复
WebGAL 4.6.2 旁白继承上一句 speaker 的问题（validator 统一补 `-clear`）；v0.6.2 明确
Overview 模式不使用旁白，向导台词全部由角色亲口说出；v0.7.0 把剧本生成重构为三轮 LLM
（自由创作草稿 → 自然语言演出批注 → Director Plan JSON）+ 确定性编译 + 有界重试，
合并原 `--performance` 通道并删除插入式合并；v0.8.0 新增 Quick Start（贡献者上手）模式，
按模式选择 Issue 采集范围并确定性提取起步任务，并与 Overview 统一为“带路角色全程说话、
不使用旁白”的剧本形态（config 的 `NARRATION_FREE_MODES` 是唯一来源）；v0.9.0 加入
LLM 模型降级链与瞬时故障重试、`REPO2GAL_MODE` 环境变量与增量备份跳过未变更子资源，
并把 GitHub Pages 部署流水线参数化为跨仓库可复用（本仓库生产演示仍是 Vercel）。

项目版本严格遵循 SemVer 2.0.0。`0.y.z` 阶段兼容修复提升 PATCH，向后兼容新功能或公开
不兼容变更提升 MINOR；`1.0.0` 后不兼容变更提升 MAJOR。发版必须同步 `pyproject.toml`、
`repo2gal/__init__.py`、README、CHANGELOG、AGENTS 和架构文档，规则以 `CONTRIBUTING.md`
“版本管理”为准。

在线演示（dogfooding 产物）：https://repo2gal.rhopaper.top/demo ，
部署与更新方式见 `docs/dev/deployment.md`。

GitHub Actions 的 `CI` 对 push/PR 运行离线测试。部署有两条**分开配置、互不影响**的路径：
`Deploy Demo`（Vercel）只在本仓库 `main` 的 CI 成功后使用仓库 secrets 生成并部署生产演示；
`Deploy Demo to GitHub Pages` 是面向其它项目开发者的推荐路径，`main` 上手动触发、只用
`REPO2GAL_API_KEY`、不读 Vercel 凭据。本仓库的演示站保持 Vercel 不变。PR 不得接触
LLM/Vercel secrets，自动部署规则以 `docs/dev/deployment.md` 为准。

开始工作前必读：

1. `README.md`
2. `docs/dev/architecture.md`
3. `docs/dev/webgal-script-reference.md`
4. 涉及素材时读 `docs/dev/asset-pack-spec.md`
5. `CONTRIBUTING.md`（开发规约与提交流程）

`docs/dev/early/` 仅为历史决策轨迹，其中含已知技术错误。不得把它当当前规范。

## 2. 最高优先级：禁止重复造轮子

**在已有可用、维护活跃、许可证兼容的开源项目时，绝对不允许自己重新实现同类基础能力。**

尤其禁止自行实现：

- 通用 GitHub REST/GraphQL 客户端；
- API 认证、分页、限流、重试和增量 checkpoint；
- Git clone/wiki clone；
- 通用归档下载器、包管理器、媒体转码器；
- 已有成熟库覆盖的 JSON Schema、SPDX、SemVer、MIME 检测等基础能力。

**唯一例外：** `repo2gal/fetcher.py` 的仓库数据获取实现可以调用 GitHub 官方 REST API，
但仅限 `https://api.github.com` 的公开 REST endpoint，用于补充现有依赖未落盘的数据。
禁止抓取 GitHub HTML 页面、搜索结果、非官方镜像或其他网页；禁止使用爬虫；禁止直接调用
GitHub GraphQL；禁止借此恢复通用 API 客户端、分页器、限流器或重试框架。

新增基础设施代码前必须先做依赖调研，至少记录：

| 项目 | 必查内容 |
|---|---|
| 功能覆盖 | 是否满足核心需求，缺口是什么 |
| 维护状态 | 最近 release/commit、issue 响应、是否 archived |
| 采用程度 | stars/downloads/使用者，仅作参考而非唯一标准 |
| 许可证 | 是否与计划中的 GPL 代码及分发方式兼容 |
| 接口稳定性 | CLI/API、版本策略、输出格式 |
| 安全性 | 凭据处理、路径安全、供应链风险 |

选择成熟依赖后，Repo2Gal 只写**薄适配层**：调用、输入输出归一化、项目特有策略。
不要复制上游内部实现。上游缺功能时优先顺序为：配置上游 → 升级上游 → 向上游贡献 →
更换成熟依赖 → 最后才讨论自研。自研必须在文档中给出具体、可验证的理由。

## 3. 已锁定依赖与边界

### GitHub 采集

使用 `josegonzalez/python-github-backup`（PyPI 包 `github-backup`，MIT）。

- 当前版本范围：`>=0.65,<0.66`
- 接入：`fetcher.run_backup()` 通过 subprocess 调公开 CLI
- 覆盖：repository、Issue、PR、Discussion、wiki、Release、label、milestone、增量备份
- 原始数据：`.repo2gal/backups/<owner>/repositories/<repo>/`

不得恢复已删除的通用 `GitHubClient`。上游未落盘的 Star/topics 等字段当前通过官方
`GET /repos/{owner}/{repo}` 补齐。新增 REST endpoint 必须有明确字段需求、文档记录和离线测试。

不要默认传上游 `--all`。它会包含 hooks 和 Release assets，可能要求额外权限并下载大量二进制。
当前显式 flags 定义在 `fetcher.NARRATIVE_BACKUP_FLAGS`（Chronicle：全量叙事数据）、
`fetcher.OVERVIEW_BACKUP_FLAGS`（Overview：源码/Release/wiki）与
`fetcher.QUICKSTART_BACKUP_FLAGS`（Quick Start：源码/Issue 与评论/wiki，用于提取起步任务）。

### WebGAL

使用 `OpenWebGAL/WebGAL` 官方发行版（MPL-2.0），黑盒集成，不修改引擎源码。
版本和官方资产 SHA-256 固定在 `packager.py`，升级时必须核对 Release 与 parser 变更。

- 场景脚本是 `game/scene/*.txt`，不是 `.wg`
- 对话是 `角色名:文本;`
- 旁白是 `say:文本 -clear;`，不是 `say:角色:文本`；4.6.2 的 say.ts 先继承上一句 speaker，漏 `-clear` 会显示成上一句话的角色（validator 会确定性补齐）
- `changeFigure:none` 是清空立绘的保留取值，不是素材名；validator 通过 `webgal.RESERVED_ASSET_REFERENCES` 放行（否则每次角色退场都降级，`--strict` 下直接失败）
- 不存在可依赖的 `webgal build` / `webgal serve` npm CLI
- 语法权威来源是 `packages/parser/src/` 和官方 demo

修改脚本生成或 validator 前必须对照 `docs/dev/webgal-script-reference.md`。

### LLM

使用 OpenAI-compatible Chat Completions 协议。LLM 只负责三轮生成式任务：剧情草稿创作
（自由格式，`[B]` 节拍锚点）、自然语言演出批注、受限 Director Plan JSON。

LLM 不负责：GitHub 抓取、资源路径决策、角色白名单、流程跳转校验、许可证判断、WebGAL
原始演出命令、坐标、时序和打包。Director Plan JSON 必须经过独立的 Schema、能力表、
角色状态机和预算校验，之后由普通代码确定性编译为 WebGAL；校验失败只允许有界重试
（`--format-retries`，默认 2 次），重试耗尽走草稿确定性兜底。
所有可确定的工作必须由普通代码完成。

## 4. 架构约束

### 确定性与生成式职责分离

```text
python-github-backup -> RepoContext -> 三轮 LLM -> Director 校验 -> WebGAL 编译 -> validator -> 打包
      确定性              确定性      非确定性        确定性          确定性        确定性      确定性
             创作草稿 / 演出批注 / 导演 JSON（受限语义，重试有界）
```

不要引入 Agent tool-calling 循环来替代确定性流水线。主线是一条直线，唯一环路是第三轮
导演 JSON 的有界重试（`--format-retries`，默认 2 次，无工具调用、无动态路由），不需要
PocketFlow、LangChain 或复杂 DAG 框架。只有出现真实的并行分章、map-reduce 或动态路由
需求后才重新评估。

### Validator 不可绕过

WebGAL 会把未知命令静默解释为 speaker，不会报错。因此“页面能打开”不代表脚本正确。
任何剧本（确定性编译产物或 `--script`）打包前必须经过 `validator.sanitize()`；Director
Plan JSON 必须经过独立的 Schema、能力表、角色状态机和预算校验。编译产物使用
`COMPILE_COMMANDS` 白名单，`--script` 用户脚本仍收敛在 `SAFE_COMMANDS`。

角色表由确定性代码生成并作为 validator 白名单。不得允许 LLM 无约束创建角色名。

### 原始数据与上下文分离

`python-github-backup` 产物是完整、可审计的原始层；`RepoContext` 是面向 LLM 的有损视图。
不要为了节省 token 删除原始备份。筛选、排序和截断只发生在 Context Builder。

## 5. 素材系统约束

素材获取规划有三类 Provider：Local、Git、AI。当前只实现 Local；三者最终必须输出同一种
引擎无关 Asset Pack。

每个素材包必须包含：

- `repo2gal-pack.json`
- `LICENSE`
- `NOTICE.md`
- 包名、SemVer、作者、描述、精确 SPDX 许可证
- 每个文件的逻辑 ID、MIME、SHA-256
- 来源 provenance；AI 素材还需模型、Prompt、seed、生成时间和服务条款

素材包不得直接使用 WebGAL 目录语义。先使用 `background.archive` 等逻辑 ID，
再由 WebGAL Adapter 转成 `game/background/archive.webp`。

角色默认构图使用引擎无关归一化 framing 元数据，不在素材包中硬编码 WebGAL 坐标；
WebGAL Adapter 负责把全身原图编译为居中半身 transform，演出动画必须保留该构图。

程序采用 GPL-3.0 不会自动把外部媒体变成 GPL。必须保留各素材许可证；v0.4.0 打包器会
生成 `THIRD_PARTY_NOTICES.md`、补入 MPL-2.0 正文并保留素材原始授权材料。项目根目录
`LICENSE` 已锁定 GPL-3.0。

## 6. 当前代码地图

| 路径 | 职责 |
|---|---|
| `repo2gal/fetcher.py` | github-backup 适配（按模式选择 flags）；受控官方 REST 元数据；备份 JSON/Git -> RepoContext；Overview 目录树与项目文件提取；Quick Start 贡献者入口文件与起步任务提取 |
| `repo2gal/generator.py` | 确定性部分：按模式选角（角色表白名单）、上下文渲染、第一轮创作 prompt 组装 |
| `repo2gal/director.py` | 草稿规范化、批注/导演 JSON prompt、Director Plan 校验、确定性 WebGAL 编译、重试反馈与草稿兜底 |
| `repo2gal/llm.py` | LLM transport 薄客户端：错误包装与脱敏，与 prompt 组装分离 |
| `repo2gal/validator.py` | WebGAL 安全子集、静默错误降级与旁白 `-clear` 归一化（硬边界） |
| `repo2gal/webgal.py` | 从官方 parser 核实的命令常量（SAFE/COMPILE 白名单）与转义 |
| `repo2gal/packager.py` | 官方 WebGAL 发行版缓存、原子打包、最小 flowchart 生成 |
| `repo2gal/asset_pack.py` | Asset Pack Schema、本地安全/授权/MIME/SHA/Profile 校验与 init |
| `repo2gal/webgal_assets.py` | 逻辑 ID 映射、素材复制、脚本重写与第三方声明聚合 |
| `repo2gal/performance.py` | 演出编译内核：能力表、profile、动作级 WebGAL 编译与共享状态工具 |
| `repo2gal/pipeline.py` | 流程编排唯一持有者：三模式矩阵、三轮生成与有界重试、阶段产物传递 |
| `repo2gal/config.py` | 默认值（含剧本模式与重试次数）、环境解析与路径常量单一来源 |
| `repo2gal/errors.py` | 统一错误类型 -> 退出码契约与集中脱敏 |
| `repo2gal/cli.py` | CLI 参数解析与结果渲染（不含流程逻辑） |
| `repo2gal/prompts/chronicle.md` | Chronicle 第一轮自由创作草稿约束 |
| `repo2gal/prompts/overview.md` | Overview 第一轮自由创作草稿约束 |
| `repo2gal/prompts/quickstart.md` | Quick Start 第一轮自由创作草稿约束 |
| `repo2gal/prompts/annotations.md` | 第二轮自然语言演出批注约束 |
| `repo2gal/prompts/director.md` | 第三轮 Director Plan JSON 约束 |
| `tests/` | 离线测试，不应依赖 GitHub 或 LLM 网络 |

## 7. 开发环境与命令

使用仓库内虚拟环境，不向系统 Python 安装包：

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests/ -q
```

CLI：

```bash
export GITHUB_TOKEN=github_pat_xxx
export REPO2GAL_API_KEY=sk_xxx
.venv/bin/repo2gal owner/repo --dry-run
```

网络测试应显式执行，普通单元测试必须离线。不得把真实 token、LLM 响应、完整第三方备份
或生成产物提交到 Git；`.repo2gal/`、`output/`、`.venv/` 已忽略。

**支持平台：Linux / macOS / WSL2。** CI 只有 `ubuntu-latest`，代码按 POSIX 假设编写
（Asset Pack 安全加载依赖 `openat`/`O_NOFOLLOW`）。原生 Windows 不在支持范围内，
Windows 贡献者在 WSL2 内开发与测试。平台相关兼容补丁（`os.name == "nt"` 分支、locale
编码兜底、路径分隔符改写等）不接受，除非同时把该平台纳入 CI 并有离线测试覆盖该分支。

## 8. 修改流程

1. 先读相关实现和当前文档，不从早期规划猜。
2. 搜索现有依赖是否已提供功能。
3. 做最小正确修改，不先引入框架或插件系统。
4. 对外部工具用 fixture/mock 测适配逻辑；必要时额外做一次显式网络冒烟测试。
5. 运行完整测试。
6. 同步更新 `README.md`、`docs/dev/architecture.md` 或素材规范。
7. 说明哪些是已实现、哪些只是计划。

## 9. 已知风险与待办

- Asset Pack 当前只支持一个本地目录包和 background/character/bgm；Git/AI Provider、
  多包组合、字体/UI/音效/视频 Adapter 尚未实现。
- 不传 `--asset-pack` 时 WebGAL 默认素材仍只有 3 张背景和 1 首 BGM。
- `python-github-backup` 不落盘仓库列表元数据，目前由一个受控官方 REST 请求补齐。
- 全量大仓库备份可能很慢、很大；依赖上游增量机制，不自己再写缓存协议。
- 原生 Windows 不受支持（Windows 上的唯一路径是 WSL2）：Asset Pack 的
  `openat`/`O_NOFOLLOW` 检查在原生 Windows 上必然失败，约 43 项离线测试因此为既有失败；
  这是设计取舍而非缺陷，平台兼容补丁不进主干。
- 三种模式都仍是单场景产物；多场景 / 多章节切分尚未实现。
- Overview 与 Quick Start 在线采集使用轻量 flags（Overview：源码/Release/wiki；
  Quick Start：源码/Issue 与评论/wiki），复用完整备份时跳过无关 JSON 解析；
  Quick Start 的起步任务依赖仓库真实使用 `good first issue` 一类标签，没有标签时
  只能讲解如何自行筛选任务。
- 演出随三轮生成默认内建；profile 为 `chronicle-subtle`（`--profile` 可换 cinematic）；
  阶段产物（草稿/批注/导演 JSON 各次尝试/反馈/报告）只有指定 `--save-stage-outputs`
  时才写入。
- 三轮生成单次运行最多 3 + `--format-retries` 次 LLM 调用，token 成本约为旧单轮的
  2.5 倍起；大仓库草稿较长时注意第三轮上下文长度。
- RP 圆桌模式（`--rp`）为计划：多角色独立上下文、角色以自身视角互动生成剧本，
  依赖外部 KiMo 引擎（用户自有独立包，多 AI 角色叙事引擎）。KiMo 修整到首个可用
  版本（LICENSE/git/Linux 测试/稳定 core API）后，Repo2Gal 以可选 extra + 薄适配层
  接入，只复用其 engine core，不在本仓库重写 arbiter/memory/context 那套。

## 10. 不要做的事

- 不要新增第 10 版宏大规划文档来代替代码和验证。
- 不要恢复通用 GitHub API 客户端；受控官方 REST 补充只能放在仓库数据获取模块。
- 不要使用 HTML 爬虫、搜索引擎抓取或非官方 GitHub 数据接口。
- 不要根据 LLM 记忆编造 WebGAL 语法。
- 不要把 `.wg`、`say:角色:文本` 或 `webgal serve` 写回当前文档。
- 不要默认下载 Release assets、附件或 LFS 大文件。
- 不要把外部素材统一改标 GPL。
- 不要在没有实际组合需求时实现复杂素材依赖解析。
- 不要跳过 validator，即使使用 Structured Output。
