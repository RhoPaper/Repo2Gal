# Repo2Gal Agent Handoff Guide

本文件是未来 AI Agent 和贡献者进入仓库后的第一入口。它描述当前真实状态、不可破坏的边界和工作方式。

## 1. 项目目标

Repo2Gal 把 GitHub 仓库转换为基于 WebGAL 的“可游玩开源项目文档”。

当前只实现 Chronicle（编年）模式：使用真实源码、README、Issue、PR、Discussion、wiki
和 Release 生成项目历史视觉小说。不要擅自把 MVP 扩成通用 Galgame、RPG 或可视化 IDE。

当前稳定基线为 `v0.3.0`：v0.1.0 主流程已于 2026-07-31 通过真实仓库、真实 LLM
和 WebGAL 产物的端到端实测；v0.2.0 增加采集/下载进度与官方 REST 元数据补充；
v0.3.0 重构流程架构（显式管线 + 统一错误域 + 薄 CLI），产品功能与 v0.2.0 一致。

在线演示（dogfooding 产物）：https://repo2gal.rhopaper.top/demo ，
部署与更新方式见 `docs/dev/deployment.md`。

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
当前显式 flags 定义在 `fetcher.NARRATIVE_BACKUP_FLAGS`。

### WebGAL

使用 `OpenWebGAL/WebGAL` 官方发行版（MPL-2.0），黑盒集成，不修改引擎源码。
版本和官方资产 SHA-256 固定在 `packager.py`，升级时必须核对 Release 与 parser 变更。

- 场景脚本是 `game/scene/*.txt`，不是 `.wg`
- 对话是 `角色名:文本;`
- `say:文本;` 是旁白，不是 `say:角色:文本`
- 不存在可依赖的 `webgal build` / `webgal serve` npm CLI
- 语法权威来源是 `packages/parser/src/` 和官方 demo

修改脚本生成或 validator 前必须对照 `docs/dev/webgal-script-reference.md`。

### LLM

使用 OpenAI-compatible Chat Completions 协议。LLM 只负责剧本创作。

LLM 不负责：GitHub 抓取、资源路径决策、角色白名单、流程跳转校验、许可证判断和打包。
所有可确定的工作必须由普通代码完成。

## 4. 架构约束

### 确定性与生成式职责分离

```text
python-github-backup -> RepoContext -> LLM -> validator -> WebGAL package
      确定性              确定性      非确定性     确定性        确定性
```

不要引入 Agent tool-calling 循环来替代确定性流水线。当前流程是一条直线，不需要 PocketFlow、
LangChain 或复杂 DAG 框架。只有出现真实的并行分章、map-reduce 或动态路由需求后才重新评估。

### Validator 不可绕过

WebGAL 会把未知命令静默解释为 speaker，不会报错。因此“页面能打开”不代表脚本正确。
所有 LLM 输出打包前必须经过 `validator.sanitize()`。

角色表由确定性代码生成并作为 validator 白名单。不得允许 LLM 无约束创建角色名。

### 原始数据与上下文分离

`python-github-backup` 产物是完整、可审计的原始层；`RepoContext` 是面向 LLM 的有损视图。
不要为了节省 token 删除原始备份。筛选、排序和截断只发生在 Context Builder。

## 5. 素材系统约束

素材获取有三类 Provider：Local、Git、AI。三者必须输出同一种引擎无关 Asset Pack。

每个素材包必须包含：

- `repo2gal-pack.json`
- `LICENSE`
- `NOTICE.md`
- 包名、SemVer、作者、描述、精确 SPDX 许可证
- 每个文件的逻辑 ID、MIME、SHA-256
- 来源 provenance；AI 素材还需模型、Prompt、seed、生成时间和服务条款

素材包不得直接使用 WebGAL 目录语义。先使用 `background.archive` 等逻辑 ID，
再由 WebGAL Adapter 转成 `game/background/archive.webp`。

程序采用 GPL-3.0 不会自动把外部媒体变成 GPL。必须保留各素材许可证，未来打包器应生成
`THIRD_PARTY_NOTICES.md`。项目根目录 `LICENSE` 已锁定 GPL-3.0。

## 6. 当前代码地图

| 路径 | 职责 |
|---|---|
| `repo2gal/fetcher.py` | github-backup 适配；受控官方 REST 元数据；备份 JSON/Git -> RepoContext |
| `repo2gal/generator.py` | 确定性部分：选角（角色表白名单）、上下文渲染、prompt 组装 |
| `repo2gal/llm.py` | LLM transport 薄客户端：错误包装与脱敏，与 prompt 组装分离 |
| `repo2gal/validator.py` | WebGAL 安全子集与静默错误降级（硬边界） |
| `repo2gal/webgal.py` | 从官方 parser 核实的命令常量与转义 |
| `repo2gal/packager.py` | 官方 WebGAL 发行版缓存、原子打包、最小 flowchart 生成 |
| `repo2gal/pipeline.py` | 流程编排唯一持有者：四模式矩阵与阶段产物传递 |
| `repo2gal/config.py` | 默认值、环境解析与路径常量单一来源 |
| `repo2gal/errors.py` | 统一错误类型 -> 退出码契约与集中脱敏 |
| `repo2gal/cli.py` | CLI 参数解析与结果渲染（不含流程逻辑） |
| `repo2gal/prompts/chronicle.md` | Chronicle 生成约束 |
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

## 8. 修改流程

1. 先读相关实现和当前文档，不从早期规划猜。
2. 搜索现有依赖是否已提供功能。
3. 做最小正确修改，不先引入框架或插件系统。
4. 对外部工具用 fixture/mock 测适配逻辑；必要时额外做一次显式网络冒烟测试。
5. 运行完整测试。
6. 同步更新 `README.md`、`docs/dev/architecture.md` 或素材规范。
7. 说明哪些是已实现、哪些只是计划。

## 9. 已知风险与待办

- Asset Pack 只有规范草案，尚未实现。
- WebGAL 默认素材只有 3 张背景和 1 首 BGM。
- `python-github-backup` 不落盘仓库列表元数据，目前由一个受控官方 REST 请求补齐。
- 全量大仓库备份可能很慢、很大；依赖上游增量机制，不自己再写缓存协议。
- 当前只有 Chronicle 模式和单场景产物。

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
