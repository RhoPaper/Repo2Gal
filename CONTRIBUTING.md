# 贡献指南

感谢你对 Repo2Gal 感兴趣。这份指南面向开发者：环境、测试、代码边界与提交流程。

## 快速开始

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests/ -q      # 261 项离线测试，数秒内完成
```

CLI 冒烟（不联网、不花钱）：

```bash
# 需要本地有该仓库的原始备份（.repo2gal/backups/...）与一份手写脚本
.venv/bin/repo2gal RhoPaper/Repo2Gal --reuse-backup --script my_story.txt --dry-run
```

开发平台为 Linux / macOS / WSL2（CI 只跑 `ubuntu-24.04`）。原生 Windows 不受支持：
Asset Pack 依赖的 `openat`/`O_NOFOLLOW` 在原生 Windows 上不存在，离线测试会有数十项
必然失败。Windows 贡献者请在 WSL2 内建 venv、跑测试并提 PR；平台相关兼容补丁
（`os.name == "nt"` 分支、locale 编码兜底、路径分隔符改写等）不合并，除非该平台同时
进了 CI 且有离线测试覆盖对应分支。

> 在线演示：[https://repo2gal.rhopaper.top/demo](https://repo2gal.rhopaper.top/demo)（dogfooding 产物，部署见
> `docs/dev/deployment.md`）。

## 必读文档

| 文档 | 内容 |
|---|---|
| `docs/dev/architecture.md` | 当前真实架构、数据流、依赖边界、错误码契约 |
| `docs/dev/webgal-script-reference.md` | 对照 parser 源码核实的 WebGAL 语法，**改生成/校验前先读** |
| `docs/dev/asset-pack-spec.md` | Asset Pack 规范与当前实现范围 |
| `docs/dev/asset-pack-dependencies.md` | Asset Pack 标准校验依赖调研与安全边界 |
| `docs/dev/director-plan-spec.md` | Director Plan v1、三轮生成、状态机、预算和 WebGAL 编译边界 |
| `AGENTS.md` | 面向 AI Agent 的仓库交接指南（边界与代码地图） |

## 不可破坏的边界（摘录自 AGENTS.md）

1. **禁止重复造轮子**：GitHub 采集用 `python-github-backup`，不自行实现 API 客户端、
   分页、限流、重试；新增基础设施前先做依赖调研。
2. **Validator 不可绕过**：任何剧本（编译产物或 `--script`）打包前必须经过 `validator.sanitize()`；
   Director Plan JSON 必须经过独立 Schema/状态机/能力校验，失败只允许有界重试
   （默认 2 次）与确定性草稿兜底。
3. **确定性与生成式分离**：抓取、选角、资源路径、跳转校验、许可证判断、WebGAL 编译、
   打包全部由普通代码完成；LLM 只负责草稿创作、演出批注与受限导演 JSON。
4. **原始数据与上下文分离**：`python-github-backup` 产物是完整可审计的原始层；
   筛选/排序/截断只发生在 Context Builder，不为省 token 删备份。
5. **不引入框架**：当前是直线流水线（`pipeline.py`），不需要 LangChain / DAG /
   插件系统；出现真实并行需求后再评估。
6. **不做**：HTML 爬虫、非官方 GitHub 接口、Release 二进制默认下载、恢复已删除的
   通用 GitHubClient、给外部素材改标 GPL。

## 代码地图

```
repo2gal/
├── cli.py         参数解析与结果渲染（薄层，不含流程）
├── pipeline.py    流程编排：三模式（chronicle/overview/quickstart）矩阵、三轮生成 + 有界重试、RunOptions/RunArtifacts
├── fetcher.py     github-backup 适配 + 受控官方 REST 元数据 + RepoContext
├── generator.py   确定性选角、上下文渲染、第一轮创作 prompt 组装
├── director.py    草稿规范化、二/三轮 prompt、Director Plan 校验与确定性编译
├── llm.py         LLM transport 薄客户端（错误包装与脱敏）
├── validator.py   WebGAL 安全子集与静默错误降级（硬边界）
├── webgal.py      经 parser 源码核实的命令常量与转义（SAFE/COMPILE 白名单）
├── packager.py    模板缓存（SHA-256）、原子打包、最小 flowchart
├── asset_pack.py  Asset Pack Schema、本地安全/授权/完整性校验与 init
├── webgal_assets.py  逻辑 ID 映射、素材复制、脚本重写与 notices
├── performance.py 演出编译内核：能力表、profile、动作级 WebGAL 编译
├── config.py      默认值、环境解析、路径常量
├── errors.py      错误类型 -> 退出码契约与集中脱敏
└── prompts/       chronicle/overview 草稿、annotations、director 模板
```

## 测试规约

- 单元测试必须**离线**：不访问 GitHub 或 LLM 网络；外部工具用 fake/monkeypatch；
- 网络验证（真实采集、真实 LLM、部署）显式执行，不计入常规套件；
- 涉及 WebGAL 语法改动必须对照 `docs/dev/webgal-script-reference.md` 与官方 parser 源码。
- Asset Pack 测试需要系统 `libmagic`（Debian/Ubuntu 包名 `libmagic1`），不得改为按扩展名猜 MIME；
- 素材测试使用微型 fixture 或 `builtin:cc0-chronicle`，不访问 Git/AI Provider 网络。
- Director 测试必须验证 Schema、beat 一对一锚点、状态机、能力 registry 和 WebGAL golden 输出；
- 三轮生成默认 2 次重试，阶段产物只能通过 `--save-stage-outputs` 写入。

## 提交流程

1. 先读相关实现与当前文档，不从 `docs/dev/early/` 的早期规划猜；
2. 做最小正确修改，不先引入框架或插件系统；
3. 本地跑完整测试；对外部工具适配逻辑用 fixture 覆盖；
4. 同步更新 `README.md` / `docs/dev/architecture.md` 或素材规范；
5. 说明哪些是已实现、哪些只是计划。

提交信息用中文，风格参考 `git log`：首行一句话概述（如「重构流程架构至 v0.3.0」），
正文按要点列改动与动机。

## 版本管理

Repo2Gal 严格采用 [Semantic Versioning 2.0.0](https://semver.org/)：

```text
MAJOR.MINOR.PATCH
```

- `PATCH`：向后兼容的缺陷修复、文档、测试和不改变公开行为的内部优化；
- `MINOR`：向后兼容的新功能、新 CLI 选项、新可选流程或公开能力扩展；
- `MAJOR`：`1.0.0` 之后不向后兼容的 CLI、Python API、持久化格式或行为变更；
- 在 `0.y.z` 阶段，任何公开不兼容变更至少提升 `MINOR`，并将 `PATCH` 归零；
- 预发布版本使用 `0.7.0-alpha.1`、`0.7.0-beta.1`、`0.7.0-rc.1` 格式；
- Python 元数据不带 `v`，Git tag、README 和 CHANGELOG 标题使用 `v0.7.0` 格式；
- Asset Pack 拥有独立 SemVer，不跟随 Repo2Gal 程序版本自动升级。

发布版本时必须同步：

1. `pyproject.toml` 的 `project.version`；
2. `repo2gal/__init__.py` 的 `__version__`；
3. `README.md` 的“当前版本”；
4. `CHANGELOG.md` 的新版本章节；
5. `AGENTS.md` 与 `docs/dev/architecture.md` 的稳定基线。

`tests/test_version.py` 必须保持通过。禁止只修改其中一个版本入口，也禁止为普通修复错误地
提升 `MINOR` 或为新功能只提升 `PATCH`。

## 更新在线演示

demo 部署方式（Vercel + Cloudflare）与重新生成步骤见
[`docs/dev/deployment.md`](dev/deployment.md)。
