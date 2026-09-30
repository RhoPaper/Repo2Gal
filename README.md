# Repo2Gal

把 GitHub 仓库转换为基于 [WebGAL](https://github.com/OpenWebGAL/WebGAL) 的可游玩开源项目文档。

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

输入一个 GitHub 仓库地址，输出一个静态网站：默认以视觉小说（编年史）的形式讲述
该项目的真实历史——它为何诞生、经历过哪些争论、社区如何演变；也可以切换到
**仓库概览（Overview）** 模式，生成给第一次接触项目的人看的“新手村向导”剧情，
或用 **Quick Start（贡献者上手）** 模式生成带新人交第一个改动上手的剧本。
剧情素材全部来自仓库的真实源码、README、Issue、PR、Discussion、wiki 与 Release。

当前版本：v0.8.0（版本历史见 [CHANGELOG.md](CHANGELOG.md)）。项目版本严格遵循
[Semantic Versioning 2.0.0](https://semver.org/)，具体升级和同步规则见
[CONTRIBUTING.md](CONTRIBUTING.md#版本管理)。

## 演示

在线演示使用本仓库自身数据生成，部署于 Vercel（部署方式见
[docs/dev/deployment.md](docs/dev/deployment.md)）：

https://repo2gal.rhopaper.top/demo

给自己仓库部署演示推荐 **GitHub Pages**：只需要一个 LLM API Key，不需要 Vercel 项目或
自定义域名。目标仓库、剧本模式与是否定时自动更新都在仓库 variables 里配置，
不需要改 workflow 文件；步骤见同一篇文档。

## 特性

`[x]` 已实现，`[ ]` 规划中。规划项的顺序与依据见
[docs/dev/architecture.md](docs/dev/architecture.md)「当前状态与下一步」。

### 数据采集

- [x] 全量仓库数据采集：源码、Issue、PR、Discussion、wiki、Release、label、milestone
- [x] Overview 轻量采集：源码、Release、wiki，不拉取 Issue/PR/Discussion
- [x] Quick Start 轻量采集：源码、Issue 与评论、wiki，不拉取 PR/Discussion/Release
- [x] 官方 GitHub REST 仓库概览补充（Star、topics、语言、创建时间等），落盘可离线复用
- [x] 上游增量备份与 `--reuse-backup` 离线复用
- [x] 采集进度实时显示
- [x] 叙事素材筛选与上下文构建：热门讨论、README/wiki 摘录、语言检测、贡献者统计
- [x] Overview 上下文构建：过滤后的目录树与根级项目文件（依赖/构建配置）摘录
- [ ] Release 资产与附件下载（显式选项）

### 剧本生成

- [x] Chronicle 模式剧本生成（单场景线性叙事 + 少量分支）
- [x] Overview 模式剧本生成（新手村向导：定位、特性、安装用法与目录地图，全程由角色亲口讲述）
- [x] Quick Start 模式剧本生成（贡献者上手：开发环境、测试与 CI、代码地图、提交流程
      与真实起步任务，同样全程由角色亲口讲述）
- [x] 三轮 LLM 协作生成：自由创作草稿 → 自然语言演出批注 → 导演 JSON 确定性编译
- [x] 动态演出默认内建（立绘出入场/移动/摇晃/预设动画、背景转场、Pixi 特效），
      profile 控制风格与预算
- [x] 确定性角色表白名单（Chronicle：项目化身 / 核心贡献者 / 技术栈精灵；
      Overview：项目向导 / 技术栈精灵；Quick Start：项目化身 / 维护者 / 技术栈精灵）
- [x] 任意 OpenAI 兼容端点（`--base-url` / `--model` / 环境变量）
- [x] `--dry-run` / `--script` / `--save-prompt` 省钱与离线路径
- [x] 导演 JSON 校验失败有界重试（默认 2 次）+ 草稿确定性兜底
- [ ] RP 圆桌模式（`--rp`）：多角色独立上下文、以角色自身视角互动生成剧本，
      依赖外部 KiMo 引擎（独立包 + 薄适配，KiMo 首个可用版本发布后接入）
- [ ] 多场景 / 多章节剧情切分

### 校验与安全

- [x] WebGAL 语法白名单校验与静默降级（validator，不可绕过）
- [x] 死跳转修复、Markdown 噪声剥离、缺 `end;` 自动补齐
- [x] `--strict` 严格模式：存在降级即拒绝打包（退出码 5）
- [x] Director Plan 独立 Schema/能力表/角色状态机/预算校验，错误结构化回喂重试

### 打包与产物

- [x] 固定版本 WebGAL 官方发行版缓存（SHA-256 校验 + 下载进度）
- [x] 原子打包：staging + 替换，失败保留旧产物
- [x] 最小 flowchart 生成（当前单场景，仅入口节点）
- [ ] 多场景流程图生成器
- [x] `THIRD_PARTY_NOTICES.md` 引擎/素材声明、MPL-2.0 正文与原始授权材料保留
- [ ] 部署配置（vercel.json）随产物生成

### 素材系统

- [x] Asset Pack v1 Schema 与安全校验（SemVer、SPDX、BCP 47、MIME、SHA-256）
- [x] 演出由导演 JSON 确定性编译（无需额外开关，`--profile` 控制风格与预算）
- [x] Local Provider（`assets init/validate`、单包 WebGAL Adapter）
- [x] 内置 CC0 示例包（Chronicle/Overview 均可使用，与 WebGAL 默认素材并存）
- [x] 角色 framing 元数据：全身原图非破坏性编译为 WebGAL 居中半身构图
- [ ] Git Provider（开源素材包下载）
- [ ] AI Provider（AI 生成素材）

### 工程质量

- [x] 统一错误体系与退出码契约、错误信息脱敏
- [x] 显式管线（pipeline）与可注入依赖，全流程可离线端到端测试
- [x] 离线测试套件（232 项）
- [x] 文档体系：用户指南、开发规约、Agent 指南、部署文档
- [x] GitHub Actions 离线 CI 与 `main` 成功后自动生成/部署演示（需仓库 secrets）
- [ ] python-github-backup 真实 fixture 回归样本
- [ ] 真实 LLM golden cases 评测集

## 安装

要求 Python 3.10+、git 与 `libmagic`（Debian/Ubuntu 包名 `libmagic1`；仅 Asset Pack
MIME 校验需要）。安全加载素材包还要求系统支持 `openat`/`O_NOFOLLOW`；不满足时只有
Asset Pack 路径被拒绝，默认 WebGAL 素材流程仍可用：

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

### 支持平台

支持 Linux、macOS 与 WSL2，CI 在 `ubuntu-latest` 上运行离线测试。**原生 Windows 不在
支持范围内**：Asset Pack 的安全加载依赖 `openat`/`O_NOFOLLOW`，原生 Windows 上没有这些
能力（默认 WebGAL 素材流程仍可用，但会拒绝 `--asset-pack`）。Windows 用户请在 WSL2 里
安装与运行；平台相关兼容补丁需要同时把该平台纳入 CI 才会被接受。

## 快速开始

```bash
export GITHUB_TOKEN=github_pat_xxx # 必填；Discussion 的 GraphQL API 必须认证
export REPO2GAL_API_KEY=sk-xxx     # LLM API Key

.venv/bin/repo2gal owner/repo
python3 -m http.server -d output/<repo> 8000   # 打开 http://localhost:8000 游玩
```

生成「仓库概览」模式：默认是 `chronicle`（编年史），传 `--mode overview` 切换：

```bash
.venv/bin/repo2gal owner/repo --mode overview
python3 -m http.server -d output/<repo>-overview 8000   # Overview 默认输出目录
```

生成「贡献者上手」模式，传 `--mode quickstart`：

```bash
.venv/bin/repo2gal owner/repo --mode quickstart
python3 -m http.server -d output/<repo>-quickstart 8000   # Quick Start 默认输出目录
```

三种模式共用抓取、validator、Asset Pack 与打包流程，差异在采集范围、上下文构建、
角色表和 prompt。Overview 只采集源码、Release 与 wiki，适合给第一次接触项目的玩家
快速介绍“是什么、怎么用、代码怎么组织”；Quick Start 只采集源码、Issue 与评论、wiki，
把开放的新人友好 Issue 当作起步任务，带玩家走完“跑起来 → 改一处 → 提交”的上手路径。

使用仓库内置的 CC0 Chronicle 素材包：

```bash
.venv/bin/repo2gal assets validate builtin:cc0-chronicle --public
.venv/bin/repo2gal owner/repo \
  --asset-pack builtin:cc0-chronicle --public-assets
```

三轮生成默认开启：第一轮自由创作草稿，第二轮自然语言演出批注，第三轮输出导演 JSON。
默认 profile 是 `chronicle-subtle`，Python 把导演 JSON 编译为 WebGAL 4.6.2 命令：

```bash
.venv/bin/repo2gal owner/repo \
  --asset-pack builtin:cc0-chronicle --public-assets \
  --profile chronicle-subtle
```

第三轮校验失败会自动打回重试（默认 2 次，可用 `--format-retries` 调整）；重试耗尽后
使用草稿确定性兜底，产物仍可游玩。调试阶段产物可整体保存：

```bash
.venv/bin/repo2gal owner/repo \
  --save-stage-outputs debug/stages   # 草稿、批注、导演 JSON 各次尝试、反馈与校验报告
```

不传 `--asset-pack` 时继续使用 WebGAL 发行版默认素材；传入素材包后，默认背景/BGM 仍会
与包内逻辑 ID 一起出现在场景可用清单中。当前一次只接受一个本地包，不做多包覆盖或隐式下载。

### 使用其他模型

任意 OpenAI 兼容端点均可接入：

```bash
export REPO2GAL_BASE_URL=https://api.deepseek.com/v1
export REPO2GAL_MODEL=deepseek-chat
```

### 不花钱先看看

```bash
repo2gal vuejs/core --dry-run                       # 只抓数据、打印 prompt，不调用 LLM
repo2gal vuejs/core --mode overview --dry-run       # 查看 Overview 模式 prompt
repo2gal vuejs/core --script my_story.txt           # 用手写剧本走完打包流程
repo2gal vuejs/core --reuse-backup                  # 不联网，复用上次原始备份
repo2gal vuejs/core --dry-run --script my_story.txt # 只校验剧本并打印报告，不打包
```

### 执行矩阵（`--dry-run` × `--script`）

| `--dry-run` | `--script` | 行为 |
|---|---|---|
| ✗ | ✗ | 抓取 → 选角 → prompt → LLM → 校验 → 打包 |
| ✗ | ✓ | 抓取 → 选角 → 读脚本 → 校验 → 打包 |
| ✓ | ✗ | 抓取 → 选角 → prompt → 打印 prompt（不调 LLM） |
| ✓ | ✓ | 抓取 → 选角 → 读脚本 → 校验 → 打印报告（不打包） |

剧本模式由 `--mode` 独立控制：

| `--mode` | 内容 | 采集范围 | 默认产物目录 |
|---|---|---|---|
| `chronicle`（默认） | 项目编年史：诞生、争论、社区演变 | 源码 + Issue/PR/Discussion + wiki + Release | `output/<repo>` |
| `overview` | 仓库概览：定位、特性、安装用法、目录地图 | 源码 + wiki + Release | `output/<repo>-overview` |

`--strict` 在所有执行校验的路径生效：validator 存在任何降级即以退出码 5 结束。

### 退出码

| 类型 | 退出码 | 场景 |
|---|---|---|
| 用法错误 | 2 | 参数/模式冲突、仓库标识或 `--script` 无法读取 |
| 抓取失败 | 3 | `python-github-backup` 采集或备份不可用 |
| 生成失败 | 4 | LLM 网络/HTTP/格式错误（错误信息已脱敏） |
| 校验失败 | 5 | `--strict` 下 validator 存在降级 |
| 打包失败 | 6 | 模板下载、产物构建或替换失败 |
| 内部错误 | 1 | 未预期异常（附完整 traceback） |

## 工作原理

```
Asset Pack ──► Schema/授权/完整性校验 ───────────────────────────┐
python-github-backup ─┐                                         │
                      ├─► RepoContext ──► 三轮 LLM ──► 编译 ─────┼─► WebGAL 产物
GitHub REST metadata ─┘    筛选叙事素材   创作/批注/导演JSON   确定性    静态站点
逻辑素材 ID ──────────────────────────────────────────────────────┘
```

| 模块 | 职责 |
|---|---|
| `fetcher.py` | 调用 `python-github-backup`（按剧本模式选择 flags）；官方 REST 补仓库概览；构建 RepoContext（Overview 含目录树与根级项目文件） |
| `generator.py` | 确定性部分：按模式选角（角色表白名单）、上下文渲染、第一轮创作 prompt 组装 |
| `director.py` | 草稿规范化、演出批注/导演 JSON prompt、Director Plan 校验与确定性 WebGAL 编译、重试反馈与草稿兜底 |
| `llm.py` | LLM transport 薄客户端：错误包装与脱敏，与 prompt 组装分离 |
| `validator.py` | 把脚本收敛到安全语法子集并给旁白补 `-clear`（不可绕过的硬边界） |
| `packager.py` | WebGAL 发行版缓存、原子打包、最小 flowchart 生成 |
| `asset_pack.py` | Asset Pack Schema、本地路径/授权/MIME/SHA/Profile 校验 |
| `webgal_assets.py` | 逻辑 ID 映射、素材复制、脚本重写与第三方声明聚合 |
| `performance.py` | 演出编译内核：能力表、profile、动作级 WebGAL 编译 |
| `pipeline.py` | 流程编排唯一持有者：四模式矩阵、三轮生成与有界重试、阶段产物传递 |
| `config.py` | 默认值、环境解析与路径常量单一来源 |
| `errors.py` | 统一错误类型 → 退出码契约与集中脱敏 |
| `cli.py` | 参数解析与结果渲染（不含流程逻辑） |

### 为什么采集依赖 python-github-backup

Repo2Gal 不自行实现 GitHub API 客户端。认证、分页、速率限制、重试、GraphQL、
Discussion 回复、Issue timeline、wiki clone 和增量备份全部交给成熟项目
[josegonzalez/python-github-backup](https://github.com/josegonzalez/python-github-backup)（MIT）。

上游未落盘的仓库概览由固定官方端点 `https://api.github.com/repos/{owner}/{repo}` 补齐。
仓库数据模块允许调用 GitHub 官方 REST API，但禁止抓取 `github.com` HTML 页面、使用
搜索引擎爬取、调用非官方接口或自行实现通用 GitHub 客户端。

默认 Chronicle 采集叙事所需的完整文本数据；`--mode overview` 只采集源码、Release
与 wiki，`--mode quickstart` 只采集源码、Issue 与评论、wiki。三种模式都不默认下载
Release 二进制和用户附件（可能高达数十 GB），后者留作未来的显式选项。原始备份保存在
`.repo2gal/backups/<owner>/repositories/<repo>/`。

### 为什么必须有 validator

WebGAL 的解析器遇到不认识的命令不会报错，而是把命令名当作角色名：

```ts
// packages/parser/src/scriptParser/commandParser.ts
return SCRIPT_CONFIG_MAP.get(command)?.scriptType ?? commandType.say;  // 默认 say
```

因此 LLM 幻觉出的 `showCode:print(1);` 会变成一个叫 `showCode` 的角色在说话。
产物永远"能跑"，却处处错渲染。validator 在打包前对剧本做五件事：

- 未知命令 / 未声明角色 → 降级为旁白；
- 所有旁白补 `-clear`：WebGAL 4.6.2 的 `say` 会继承上一句说话人，
  漏掉 `-clear` 旁白就会顶着上一个角色的名字显示；无冒号的纯文本行也会被引擎
  当成 speaker，validator 一并改为旁白；
- 跳转目标不存在 → 注释该行，避免玩家卡死；
- 剥离 Markdown 代码围栏与标题噪声；
- 缺 `end;` 自动补齐。

## 素材系统

v0.4.0 已实现 Asset Pack v1 Schema、Local Provider、安全校验、WebGAL Adapter 和
`THIRD_PARTY_NOTICES.md`。剧本只引用 `background.archive` 等逻辑 ID，确定性 Adapter
再映射到 WebGAL 裸文件名；LLM 不决定路径、许可证或复制行为。

动态演出内建于三轮生成：第一轮自由创作草稿，第二轮自然语言批注演出，第三轮输出
Director Plan JSON；`director.py` 用 beat 一对一锚点、角色状态机、能力表和固定编译宏
生成演出命令，校验失败时把结构化错误回喂第三轮重试（默认 2 次），重试耗尽用草稿确定性
兜底。`--profile` 控制演出风格与预算（`chronicle-subtle` / `chronicle-cinematic`）。

角色素材可以保留完整全身透明图，并通过 Asset Pack 的归一化 `framing` 标注默认头顶、
上半身底线和视觉中心。WebGAL Adapter 会生成确定性 `changeFigure -transform`，把角色放在
画面中间并让腿部位于屏幕下方；演出移动、摇晃和缩放会保留这套基础构图。

三种 Provider 最终使用同一个 `repo2gal-pack.json` 格式。当前只实现本地目录包；Git 下载
和 AI 生成仍是后续计划。内置 CC0 示例随 wheel 分发，可用 `builtin:cc0-chronicle` 引用；
源码位于 `repo2gal/examples/cc0-chronicle-pack/`。外部媒体保持自己的许可证，不捆进 GPL
程序许可证。规范见
[docs/dev/asset-pack-spec.md](docs/dev/asset-pack-spec.md)。

## 限制

- 不传 `--asset-pack` 时只有 WebGAL 内置的 3 张背景和 1 首 BGM；
- 当前只支持一个本地素材包（内置示例主题为 Chronicle，三种模式都可使用），
  不支持多包覆盖、Git 下载或 AI 生成；
- Chronicle 的全量 Issue/PR/Discussion 备份首次可能较慢；Overview 与 Quick Start
  的采集范围更小，通常快得多；
- Quick Start 的起步任务依赖仓库真的使用 `good first issue` 一类标签，没有这类标签时
  只能讲解如何自己筛选任务；
- 三种模式都只生成单场景产物，多场景 / 多章节切分仍在计划中。

## 文档

- [docs/user-guide.md](docs/user-guide.md) — 用户指南：怎么玩、怎么生成自己的作品、FAQ
- [CONTRIBUTING.md](CONTRIBUTING.md) — 开发规约：环境、边界、提交流程
- [AGENTS.md](AGENTS.md) — AI Agent 接手仓库的第一入口
- [CHANGELOG.md](CHANGELOG.md) — 版本历史
- [docs/dev/webgal-script-reference.md](docs/dev/webgal-script-reference.md) —
  WebGAL 语法速查表，对照解析器源码核实过，修改脚本生成前必读
- [docs/dev/architecture.md](docs/dev/architecture.md) — 当前架构、依赖边界和数据流
- [docs/dev/asset-pack-spec.md](docs/dev/asset-pack-spec.md) — Asset Pack v1 规范与实现范围
- [docs/dev/asset-pack-dependencies.md](docs/dev/asset-pack-dependencies.md) —
  Asset Pack 标准校验依赖调研与安全边界
- [docs/dev/director-plan-spec.md](docs/dev/director-plan-spec.md) — Director Plan v1
  三轮生成协议、状态机、预算和 WebGAL 编译边界
- [docs/dev/deployment.md](docs/dev/deployment.md) — 在线演示的部署与更新方式
- [docs/dev/early/](docs/dev/early/) — 早期规划文档（v1–v9）及其勘误，仅历史参考

## 开发

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests/ -q
```

测试必须离线（不访问 GitHub 与 LLM 网络）。贡献方式见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可

- Repo2Gal 程序代码：[GPL-3.0](LICENSE)；
- WebGAL 引擎：MPL-2.0，保持原许可证；
- 外部 Asset Pack 保持各自许可证，不因打包而自动变为 GPL。
