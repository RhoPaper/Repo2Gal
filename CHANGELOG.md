# 更新日志

本文件记录面向用户可感知的变化。内部重构细节见各版本提交历史。版本号遵循
[Semantic Versioning 2.0.0](https://semver.org/)；`0.y.z` 阶段的新功能提升 `MINOR`，
兼容缺陷修复提升 `PATCH`，公开不兼容变更至少提升 `MINOR`。

## v0.9.0 — 2026-11-15

**生成韧性、增量采集与跨仓库部署**：

- 新增 LLM 模型降级链：`--model` 与 `REPO2GAL_MODEL` 接受逗号分隔的模型链，首个为主
  模型、其余按顺序降级；同一模型内对 429/5xx 短暂重试（默认 2 次尝试、5 秒退避），
  模型不存在（404）不重试直接切换，其余错误立即抛出；最近成功过的模型会被提到链首，
  降级与重试过程逐条打印，便于确认实际命中了哪个模型。公开 API 相应调整：
  `RunOptions.model` 变为 `models` 元组，`resolve_model` 变为 `resolve_model_chain`；
- `--mode` 支持 `REPO2GAL_MODE` 环境变量：显式参数仍优先，未传时依次读环境变量与默认值
  `chronicle`，CI 或容器里可以只靠环境变量选择剧本模式；
- 增量备份补传 `--incremental-by-files`：已落盘且未变更的 Issue/PR 评论、评审、提交与
  时间线直接沿用本地文件，列表请求仍每次执行以发现新实体；大仓库重复采集显著变短，
  落盘结构不变；
- GitHub Pages 部署流水线参数化：目标仓库、剧本模式、演出 profile、严格校验、超时与
  采集 token 全部从仓库 variables/secrets 读取，workflow 不再包含项目特化信息，换目标
  无需改文件；新增可选每日自动更新（`REPO2GAL_AUTO_UPDATE`，按目标仓库默认分支推进，
  并用缓存记录上次生成的 revision）；
- 新增 GitHub Pages 备选部署流水线并与 Vercel 并存：默认手动触发，只依赖 Actions 自带的
  `github.token`，不读取 `VERCEL_TOKEN`；本仓库生产演示仍是 Vercel，Pages 是推荐给其它
  项目开发者的路径；
- 修复角色退场被 validator 误降级：编译内核用 `changeFigure:none` 实现 `figure.exit`，
  该保留取值此前被判成“引用未声明或类型不匹配的素材”——非 strict 下角色不会退场，
  `--strict` 下整次运行以退出码 5 失败。现在由 `webgal.RESERVED_ASSET_REFERENCES` 放行，
  且只对 `changeFigure` 生效；
- 修复导演环节的三类锚点与形状问题：草稿 `[B]` 锚点与台词同行时也能正确分块；第三轮
  prompt 补齐每个动作 kind 的字段名清单与可照抄示例，并明确 `choices[].target` 与
  `jump` 是裸字符串；`jump`/`target` 被写成 `{"target": "<id>"}` 时机械拆包并按 fix
  记录，目标 id 是否存在仍由校验判定；
- 导演 prompt 逐个标注角色表项是否有立绘，并写死“`figure.*` 只能使用有立绘角色、
  同一角色先 `enter` 再 `move`/`exit`”，避免整份剧本因能力错误被打回；
- 部署门禁：Vercel 线上内容比对改为轮询（最多 10 分钟）后判定、job 超时提到 60 分钟，
  消除自定义域名切换滞后造成的假红；`Deploy Demo` 补 guard 事件条件，只有 main push
  触发的 CI 成功才执行带生产 secrets 的 job；Pages 流水线给缓存保存加守卫，避免保存
  失败拖住已生成的产物；
- CI 与部署流水线升级到 Node.js 24 运行时：`checkout@v7`、`setup-python@v7`、
  `setup-node@v7`、`cache@v6`（含 `restore`/`save`）、`upload-artifact@v7`、
  `pnpm/action-setup@v6`、`configure-pages@v6`、`upload-pages-artifact@v5`、
  `deploy-pages@v5`；runner 固定 `ubuntu-24.04`，避免 `ubuntu-latest` 迁移到
  Ubuntu 26 造成构建漂移；
- 明确支持平台为 Linux/macOS/WSL2，原生 Windows 不受支持；部署文档写明 `VERCEL_TOKEN`
  与 `REPO2GAL_API_KEY` 必须是仓库级 secret（guard 与 Pages 流水线不在 production
  environment 内，environment secret 读不到会让部署静默跳过）；
- 新增 `tests/fixtures/github-backup-sample/` 落盘结构回归样本：字段形状取自真实
  `python-github-backup` 输出（Issue labels 对象数组、`comment_data`/`reply_data`、
  Pull 的 `review_data`、Discussion 的 camelCase 键），内容为合成数据，固定三种模式
  从同一份备份构建 `RepoContext` 的差异；
- 离线测试从 232 项扩充到 261 项，并新增版本同步守卫：`test_version.py` 检查 README、
  CHANGELOG、AGENTS 与架构文档都带当前版本号，防止只改一个版本入口。

## v0.8.0 — 2026-09-13

**Quick Start（贡献者上手）模式**：

- 新增 `--mode quickstart`：为“第一次想给这个项目提交改动的人”生成上手剧本，路线覆盖
  欢迎、拿到代码、跑通测试与本地预览、代码地图、提交与评审规矩、第一个真实任务与
  后续提问渠道；与现有两种模式一样走三轮 LLM + 确定性编译与 validator 硬边界，
  产物标题为「`owner/repo` 贡献者上手」，存档键使用
  `repo2gal_<owner>_<repo>_quickstart` 独立隔离；
- Quick Start 使用独立采集范围（源码、Issue 与评论、wiki），不拉取 PR/Discussion/Release：
  起步任务来自开放且带 `good first issue`、`help wanted`、`beginner` 等标签的真实 Issue，
  按编号倒序排序，数量由 `--threads` 控制；没有匹配标签时 prompt 明确要求不得编造编号；
- 新增确定性贡献者素材提取：CONTRIBUTING、构建/测试入口、PR 模板与 CI 工作流
  （`.github/workflows/*.yml`，最多 3 个）摘录；项目文件匹配改为仓库内相对路径，
  因此 `.github/CONTRIBUTING.md` 这类嵌套路径同样可命中；`RepoContext` 新增
  `contributor_files` 与 `starter_issues` 两个字段，其他模式保持为空；
- Quick Start 与 Overview 一样不使用旁白：导演 JSON 校验与草稿兜底统一按
  `NARRATION_FREE_MODES`（config 为单一来源）拒绝 narration 与无说话人的 choice 文本，
  兜底编译把无说话人文本归给带路角色；
- 离线测试从 204 项扩充到 232 项。

## v0.7.0 — 2026-08-31

**剧本生成重构为三轮 LLM + 确定性编译（Director 流程）**：

- 第一轮只写故事草稿（自由格式，每个节拍一行 `[B]` 锚点），不再要求模型一边创作
  一边记忆 WebGAL 语法；第二轮用自然语言按 beat 写演出批注；第三轮把草稿与批注落成
  受限 Director Plan JSON（与草稿 beat 一一对应），由普通代码确定性编译为 WebGAL；
- 合并原 `--performance` 通道：动态演出默认内建，`--profile` 控制风格与预算
  （`chronicle-subtle` / `chronicle-cinematic`），删除插入式合并与
  `--performance`/`--performance-profile`/`--strict-performance`/
  `--save-beat-manifest`/`--save-performance-plan`/`--save-performance-report` 参数；
- 第三轮校验失败时把结构化错误清单回喂模型重试（`--format-retries`，默认 2 次）；
  重试耗尽后由第一轮草稿确定性兜底编译，产物保证可玩；
- 新增 `--save-stage-outputs`：保存草稿、批注、导演 JSON 各次尝试、重试反馈与校验报告；
- 编译产物经 validator 时使用 `COMPILE_COMMANDS` 白名单，`--script` 用户脚本仍收敛在
  `SAFE_COMMANDS`；validator 对两类输入都是硬边界；
- 协议与编译边界见 `docs/dev/director-plan-spec.md`（取代 performance-plan-spec）；
- 离线测试扩充到 204 项。

## v0.6.2 — 2026-08-28

**修复 Overview 向导台词被生成成旁白**：

- 明确 Overview 模式不使用旁白：向导自我介绍、展区过渡和结束语必须由项目化身
  以 `角色名:台词` 说出，prompt 禁止输出 `say:` 行并给出反例；
- 同时强化 Chronicle prompt 的规则：`say:` 只能用于没有角色说话的客观叙述，
  不得替角色转述台词；
- 离线测试保持 188 项并新增 prompt 约束断言。

## v0.6.1 — 2026-08-28

**修复旁白继承上一句说话人**：

- WebGAL 4.6.2 的 `say` 先继承 `stageState.showName`，只有 `-clear` 才清空说话人；
  无冒号的纯文本行则会被 parser 把整行当成 speaker；
- validator 现在对所有旁白（`say:`、`:文本`、无冒号文本、未知命令降级）确定性输出
  `say:文本 -clear;`，LLM 和 `--script` 输入都不可绕过；
- 两个 prompt 模板改为显式要求 `say:文本 -clear;`，并同步 WebGAL 语法速查表；
- 离线测试扩充到 188 项。

## v0.6.0 — 2026-08-26

**仓库概览（Overview）模式**：

- 新增 `--mode` 选项（`chronicle` 默认 / `overview`），实现长期规划文档中的
  仓库概览模式；Chronicle 的行为、产物存档键与默认参数保持兼容；
- Overview 采用独立 prompt：以“新手村向导”视角覆盖项目定位、核心特性、
  安装与快速开始、目录结构和继续深入入口，不把 Issue/PR 历史争论当主线；
- Overview 使用独立的上游采集范围（源码、Release、wiki），不拉取
  Issue/PR/Discussion；复用已有完整备份时也跳过社区 JSON 解析，首次与复用运行更快；
- 新增确定性概览上下文提取：过滤依赖/构建产物的浅层目录树，以及 pyproject.toml、
  package.json、Cargo.toml、Dockerfile、CONTRIBUTING 等根级项目文件摘录；
- Overview 的确定性角色表只保留项目向导与技术栈精灵；产物标题为
  「`owner/repo` 仓库概览」，存档键使用 `repo2gal_<owner>_<repo>_overview` 独立隔离；
- Overview 同样经过 validator 硬边界，支持 `--script`、`--dry-run`、`--strict`、
  Asset Pack 与 `--performance`；离线测试从 168 项扩充到 183 项。

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
- 新增离线 Performance Plan Schema、状态机和 WebGAL golden tests，离线测试扩充至 168 项。
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
