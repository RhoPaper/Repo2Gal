# Repo2Gal

把 GitHub 仓库变成可游玩的 WebGAL 视觉小说。

输入一个仓库地址，输出一个静态网站——用视觉小说的形式讲述这个项目的编年史：
它为何诞生、经历过哪些争论、社区如何演变。素材来自仓库的真实源码、README、
Issue、PR、Discussion、wiki 与 Release。

> **当前版本：v0.2.0 Chronicle MVP。** v0.1.0 主流程已于 2026-07-31 在真实 GitHub
> 仓库和真实 LLM 环境中端到端实测通过；v0.2.0 新增采集/下载进度和官方 REST 元数据补充。

### v0.2.0 新增

- 实时显示 `python-github-backup` 的仓库、Issue、PR、Discussion、wiki 等采集阶段；
- 下载 WebGAL 官方发行版时显示百分比和已下载体积；
- 通过官方 GitHub REST API 补齐 description、language、Star、topics、创建时间等仓库概览；
- 官方 REST 元数据落盘到原始备份，可由 `--reuse-backup` 离线复用。

## 快速开始

```bash
python3 -m venv .venv && .venv/bin/pip install -e .

export GITHUB_TOKEN=github_pat_xxx # 必填；Discussion 的 GraphQL API 必须认证
export REPO2GAL_API_KEY=sk-xxx     # LLM API Key

repo2gal OpenWebGAL/WebGAL
python3 -m http.server -d output/WebGAL 8000
```

打开 http://localhost:8000 即可游玩。

### 换用其他模型

任何 OpenAI 兼容端点都能接：

```bash
export REPO2GAL_BASE_URL=https://api.deepseek.com/v1
export REPO2GAL_MODEL=deepseek-chat
```

### 不花钱先看看

```bash
repo2gal vuejs/core --dry-run              # 只抓数据、打印 prompt
repo2gal vuejs/core --script my_story.txt  # 用手写剧本走完打包流程
repo2gal vuejs/core --reuse-backup         # 不联网，复用上次原始备份
```

## 工作原理

```
python-github-backup ─┐
                      ├─► RepoContext ──► LLM ──► validator ──► WebGAL 产物
GitHub REST metadata ─┘    筛选叙事素材      写剧本    收敛降级       静态站点
```

| 模块 | 职责 |
|---|---|
| `fetcher.py` | 调用 `python-github-backup`；从官方 REST API 补仓库概览；构建 RepoContext |
| `generator.py` | 定角色表（确定性）、拼 prompt、调 LLM |
| `validator.py` | 把脚本收敛到安全语法子集 |
| `packager.py` | 克隆 WebGAL 发行版模板，注入脚本 |
| `cli.py` | 串联流程 |

### 为什么采集依赖 python-github-backup

Repo2Gal 不自行实现 GitHub API 客户端。认证、分页、速率限制、重试、GraphQL、
Discussion 回复、Issue timeline、wiki clone 和增量备份全部交给成熟项目
[`josegonzalez/python-github-backup`](https://github.com/josegonzalez/python-github-backup)（MIT）。

上游未落盘的仓库概览由固定官方端点 `https://api.github.com/repos/{owner}/{repo}` 补齐。
仓库数据模块允许调用 GitHub 官方 REST API，但禁止抓取 `github.com` HTML 页面、使用搜索引擎
爬取、调用非官方接口或自行实现通用 GitHub 客户端。

默认采集叙事所需的完整文本数据，但**不默认下载** Release 二进制和用户附件，
因为这两类文件可能让一次生成意外下载数十 GB。未来将作为显式选项提供。

原始备份保存在 `.repo2gal/backups/<owner>/repositories/<repo>/`，可以审计和复用。

### 为什么必须有 validator

WebGAL 的解析器遇到不认识的命令**不会报错**：

```ts
// packages/parser/src/scriptParser/commandParser.ts
return SCRIPT_CONFIG_MAP.get(command)?.scriptType ?? commandType.say;  // 默认 say
```

所以 LLM 幻觉出的 `showCode:print(1);` 会变成「一个叫 showCode 的角色在说 print(1)」。
产物永远"能跑"，却处处错渲染，靠肉眼玩游戏去发现成本极高。

validator 在打包前做四件事：

- 未知命令 / 未声明角色 → 降级为旁白
- 跳转目标不存在 → 注释掉该行，避免玩家卡死
- 剥离 Markdown 代码围栏与标题噪声
- 缺 `end;` 自动补齐

角色表由代码从贡献者列表推导，**不交给 LLM 决定**——否则无法区分「新角色」和「幻觉命令」。

## 素材系统方向

外部媒体资源将采用统一的、引擎无关的 Asset Pack，不直接捆绑进 GPL 程序代码。
素材有三种 Provider：用户本地导入、GitHub 开源素材包下载、AI 生成。三种来源最终必须
产出相同格式的 `repo2gal-pack.json`，记录 SPDX 许可证、作者、版本、来源、哈希和生成记录。

详见 [`docs/dev/asset-pack-spec.md`](docs/dev/asset-pack-spec.md)。

## 已知限制

- Asset Pack 目前只有规范草案，尚未实现；现在仍使用 WebGAL 内置的 3 张背景和 1 首 BGM。
- 仅 Chronicle 一种模式。
- 剧情为单场景线性叙事 + 少量分支，未做多场景切分。
- 全量 Issue/PR/Discussion 备份可能耗时较长，后续运行会使用上游增量备份。

以上均为下一阶段能力或已知产品边界，不影响 v0.2.0 Chronicle MVP 的完整使用。

## 开发

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests/ -q
```

## 文档

- [`docs/dev/webgal-script-reference.md`](docs/dev/webgal-script-reference.md) —
  WebGAL 语法速查表，对照解析器源码核实过，**写代码前先读这个**
- [`docs/dev/architecture.md`](docs/dev/architecture.md) — 当前真实架构、依赖边界和数据流
- [`docs/dev/asset-pack-spec.md`](docs/dev/asset-pack-spec.md) — Asset Pack v1 规范草案
- [`docs/dev/early/`](docs/dev/early/) — 早期规划文档（v1–v9）及其勘误

## 许可

Repo2Gal 采用 GPL-3.0 开源
WebGAL 引擎保持 MPL-2.0，外部 Asset Pack 保持各自许可证
