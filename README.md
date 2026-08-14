# Repo2Gal

把 GitHub 仓库转换为基于 [WebGAL](https://github.com/OpenWebGAL/WebGAL) 的可游玩开源项目文档。

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

输入一个 GitHub 仓库地址，输出一个静态网站：以视觉小说（编年史）的形式讲述该项目的
真实历史——它为何诞生、经历过哪些争论、社区如何演变。剧情素材全部来自仓库的真实
源码、README、Issue、PR、Discussion、wiki 与 Release。

当前版本：v0.3.0（版本历史见 [CHANGELOG.md](CHANGELOG.md)）。

## 演示

在线演示使用本仓库自身数据生成，部署于 Vercel（部署方式见
[docs/dev/deployment.md](docs/dev/deployment.md)）：

https://repo2gal.rhopaper.top/demo

## 特性

- **忠于事实**：剧情素材全部来自仓库真实数据；角色表由代码从贡献者与技术栈推导，
  不允许 LLM 自行创造角色；
- **确定性流水线**：采集、选角、校验、打包均由普通代码完成，LLM 只负责写剧本；
- **安全校验**：所有剧本打包前强制经过 validator，收敛到 WebGAL 语法白名单，
  未知命令、无效跳转、缺失 `end;` 等自动降级或修复（`--strict` 可拒绝降级产物）；
- **产物即静态站点**：输出可直接托管，无需服务器；
- **省钱与离线模式**：`--dry-run`、`--script`、`--reuse-backup` 覆盖不调用 LLM、
  不联网的完整流程；
- **原始数据可审计**：完整备份保留在 `.repo2gal/backups/`，可复用、可增量更新。

## 安装

要求 Python 3.10+ 与 git：

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

## 快速开始

```bash
export GITHUB_TOKEN=github_pat_xxx # 必填；Discussion 的 GraphQL API 必须认证
export REPO2GAL_API_KEY=sk-xxx     # LLM API Key

.venv/bin/repo2gal owner/repo
python3 -m http.server -d output/<repo> 8000   # 打开 http://localhost:8000 游玩
```

### 使用其他模型

任意 OpenAI 兼容端点均可接入：

```bash
export REPO2GAL_BASE_URL=https://api.deepseek.com/v1
export REPO2GAL_MODEL=deepseek-chat
```

### 不花钱先看看

```bash
repo2gal vuejs/core --dry-run                       # 只抓数据、打印 prompt，不调用 LLM
repo2gal vuejs/core --script my_story.txt           # 用手写剧本走完打包流程
repo2gal vuejs/core --reuse-backup                  # 不联网，复用上次原始备份
repo2gal vuejs/core --dry-run --script my_story.txt # 只校验剧本并打印报告，不打包
```

### 模式

| `--dry-run` | `--script` | 行为 |
|---|---|---|
| ✗ | ✗ | 抓取 → 选角 → prompt → LLM → 校验 → 打包 |
| ✗ | ✓ | 抓取 → 选角 → 读脚本 → 校验 → 打包 |
| ✓ | ✗ | 抓取 → 选角 → prompt → 打印 prompt（不调 LLM） |
| ✓ | ✓ | 抓取 → 选角 → 读脚本 → 校验 → 打印报告（不打包） |

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
python-github-backup ─┐
                      ├─► RepoContext ──► LLM ──► validator ──► WebGAL 产物
GitHub REST metadata ─┘    筛选叙事素材      写剧本    收敛降级       静态站点
```

| 模块 | 职责 |
|---|---|
| `fetcher.py` | 调用 `python-github-backup`；从官方 REST API 补仓库概览；构建 RepoContext |
| `generator.py` | 确定性部分：选角（角色表白名单）、上下文渲染、prompt 组装 |
| `llm.py` | LLM transport 薄客户端：错误包装与脱敏，与 prompt 组装分离 |
| `validator.py` | 把脚本收敛到安全语法子集（不可绕过的硬边界） |
| `packager.py` | WebGAL 发行版缓存、原子打包、最小 flowchart 生成 |
| `pipeline.py` | 流程编排唯一持有者：四模式矩阵与阶段产物传递 |
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

默认采集叙事所需的完整文本数据，但不默认下载 Release 二进制和用户附件（可能高达数十 GB），
二者留作未来的显式选项。原始备份保存在 `.repo2gal/backups/<owner>/repositories/<repo>/`。

### 为什么必须有 validator

WebGAL 的解析器遇到不认识的命令不会报错，而是把命令名当作角色名：

```ts
// packages/parser/src/scriptParser/commandParser.ts
return SCRIPT_CONFIG_MAP.get(command)?.scriptType ?? commandType.say;  // 默认 say
```

因此 LLM 幻觉出的 `showCode:print(1);` 会变成一个叫 `showCode` 的角色在说话。
产物永远"能跑"，却处处错渲染。validator 在打包前对剧本做四件事：

- 未知命令 / 未声明角色 → 降级为旁白；
- 跳转目标不存在 → 注释该行，避免玩家卡死；
- 剥离 Markdown 代码围栏与标题噪声；
- 缺 `end;` 自动补齐。

## 素材系统（规划）

外部媒体资源将采用统一的、引擎无关的 Asset Pack，不直接捆绑进 GPL 程序代码。
素材有三种 Provider：用户本地导入、GitHub 开源素材包下载、AI 生成，最终统一产出
相同格式的 `repo2gal-pack.json`（SPDX 许可证、作者、版本、来源、哈希与生成记录）。
规范见 [docs/dev/asset-pack-spec.md](docs/dev/asset-pack-spec.md)。

## 限制

- Asset Pack 仅有规范草案，尚未实现，当前使用 WebGAL 内置素材（3 张背景、1 首 BGM）；
- 仅 Chronicle 一种模式，剧情为单场景线性叙事加少量分支；
- 全量 Issue/PR/Discussion 备份首次可能较慢，后续运行使用上游增量备份。

## 文档

- [docs/user-guide.md](docs/user-guide.md) — 用户指南：怎么玩、怎么生成自己的作品、FAQ
- [CONTRIBUTING.md](CONTRIBUTING.md) — 开发规约：环境、边界、提交流程
- [AGENTS.md](AGENTS.md) — AI Agent 接手仓库的第一入口
- [CHANGELOG.md](CHANGELOG.md) — 版本历史
- [docs/dev/webgal-script-reference.md](docs/dev/webgal-script-reference.md) —
  WebGAL 语法速查表，对照解析器源码核实过，修改脚本生成前必读
- [docs/dev/architecture.md](docs/dev/architecture.md) — 当前架构、依赖边界和数据流
- [docs/dev/asset-pack-spec.md](docs/dev/asset-pack-spec.md) — Asset Pack v1 规范草案
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
