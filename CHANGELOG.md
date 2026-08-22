# 更新日志

本文件记录面向用户可感知的变化。内部重构细节见各版本提交历史。版本号遵循
[Semantic Versioning 2.0.0](https://semver.org/)；`0.y.z` 阶段的新功能提升 `MINOR`，
兼容缺陷修复提升 `PATCH`，公开不兼容变更至少提升 `MINOR`。

## v0.5.0 — 2026-08-22

**Performance Plan v1 动态演出**：

- 新增显式 `--performance`，默认 profile 为 `chronicle-subtle`；
- 剧情校验后确定性生成 Beat Manifest，第二次 LLM 只输出结构化演出意图 JSON；
- 新增 `figure.enter`、`figure.exit`、`figure.move`、`figure.shake`、`figure.animate`、
  `screen.transition` 和场景生命周期 `screen.effect`；
- Python 负责角色状态机、演出预算、WebGAL 4.6.2 能力表、坐标、时长、runtime ID 和时序编译；
- 演出计划无效或返回空 cues 时，普通模式保留剧情并加入最低确定性演出，
  `--strict-performance` 沿用退出码 5；
- 新增 `--save-beat-manifest`、`--save-performance-plan`、`--save-performance-report`，
  仅在指定时写出调试审计 JSON；
- 新增离线 Performance Plan Schema、状态机和 WebGAL golden tests，离线测试扩充至 165 项。
- 修复真实模型遗漏 `screen.transition.phase` 导致整份计划 fallback 的问题，无歧义时默认补
  `enter`；模型复制错误的运行元数据由 Python 绑定；
- 新增角色归一化 framing，内置全身角色图非破坏性编译为居中半身 WebGAL transform，
  动态移动、摇晃和缩放保持该基础构图。
- 新增 Pillow 图片结构/真实尺寸校验；所有 Asset Pack 角色（含未声明 framing 的包）统一使用
  中心基准并覆盖不可信原始 transform；分支汇合状态不一致时拒绝角色演出。
- `screen.transition` 直接补入对应 `changeBg` 的 `-enter/-exit` 参数，使 shockwave 与背景切换
  同时发生，不再在新背景已经显示后播放。

## v0.4.0 — 2026-08-21

**Asset Pack v1 本地单包闭环**：

- 新增随 wheel 分发的 Draft 2020-12 Schema，以及 SemVer、SPDX expression、BCP 47、
  CSS Color、magic MIME、SHA-256、Profile 和公开授权策略校验；
- 新增 `repo2gal assets init/validate` Local Provider 命令，以及生成命令的 `--asset-pack`
  和 `--public-assets`；原有 `repo2gal owner/repo` 命令形态保持兼容；
- 剧本使用引擎无关逻辑 ID，validator 新增素材存在性/类型校验并安全放行 `changeFigure`；
- 新增 WebGAL Adapter，在原子 staging 中复制 background/character/bgm、重写裸文件名，
  打包前二次检查 SHA-256，拒绝符号链接、路径穿越和模板覆盖；
- 所有产物生成 `THIRD_PARTY_NOTICES.md` 并附 MPL-2.0 正文；使用素材包时另保留原始
  manifest、LICENSE、NOTICE 和 evidence；
- 加入 RhoPaper 制作并以 CC0-1.0 提供的 Chronicle 示例包；BGM 转为 OGG 后整包约 7.7 MiB，
  不传素材包时仍保留 WebGAL 默认素材；
- 依赖调研与实现边界落盘，离线测试从 85 项扩充到 119 项。
## v0.3.0 — 2026-08-14

**流程架构重构**（产品功能与 v0.2.0 一致，行为修正与内部优化）：

- 新增显式流水线 `pipeline.py`：抓取 → 选角 → prompt → 剧本 → 校验 → 打包，
  阶段产物显式传递、依赖可注入、全流程可离线端到端测试；
- 新增统一错误体系 `errors.py`：每个错误类型对应固定退出码（2 用法 / 3 采集 /
  4 生成 / 5 严格校验 / 6 打包），错误正文集中脱敏；
- 新增 `config.py`（默认值与路径单一来源）与 `llm.py`（LLM 薄客户端，
  网络/HTTP/结构错误包装并脱敏）；`cli.py` 重写为薄表现层，新增 `--timeout`；
- 打包原子化：staging + 原子替换，失败保留旧产物；
- 修复流程图缺陷：生成只含 `start.txt` 的最小 `flowchart.json`；
- 修正 `--dry-run` 语义：与 `--script` 组合时校验剧本并打印报告（此前静默忽略）；
- 离线测试从 36 项扩充到 85 项；
- 修复包版本入口 `repo2gal.__version__` 仍停留在 0.2.0 的问题，并新增版本一致性测试；
- 许可证：根目录加入 GPL-3.0 `LICENSE`，README/文档同步。

## v0.2.0 — 2026-08-01

- 实时显示 `python-github-backup` 采集阶段（仓库、Issue、PR、Discussion、wiki 等）；
- WebGAL 官方发行版下载显示百分比与已下载体积；
- 通过官方 GitHub REST API 补齐 description、language、Star、topics、创建时间，
  并落盘到原始备份供 `--reuse-backup` 离线复用。

## v0.1.0 — 2026-07-31

- Chronicle 主流程端到端跑通（真实仓库 + 真实 LLM + WebGAL 产物实测）：
  python-github-backup 采集 → RepoContext → LLM 写剧本 → validator 收敛降级 →
  WebGAL 静态站点打包；
- 确定性角色表白名单、`--script` / `--dry-run` / `--reuse-backup` 等基础 CLI。
