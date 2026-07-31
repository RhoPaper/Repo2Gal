# Repo2Gal 当前架构

> 本文描述**当前实现和已锁定的边界**。历史设想放在 `docs/dev/early/`，不得把早期规划当成现状。

当前基线：`v0.1.0`。Chronicle 主流程已于 2026-07-31 在真实 GitHub 仓库和真实 LLM
环境中端到端实测通过；本阶段期望功能全部完成。

## 1. 产品定位

Repo2Gal 是“可游玩的开源项目文档生成器”，不是通用 Galgame 生成器。

当前 MVP 只实现 Chronicle（编年）模式：从真实源码、README、Issue、PR、Discussion、
wiki 与 Release 中提炼项目历史，生成 WebGAL 静态站点。

## 2. 数据流

```text
GitHub repository
       │
       ▼
python-github-backup                 成熟外部采集器
       │                             认证 / 分页 / 限流 / 重试 / GraphQL / Git clone
       ▼
.repo2gal/backups/<owner>/           可审计、可增量、可复用的原始备份
       │
       ▼
fetcher.context_from_backup()        确定性归一化与热门素材筛选
       │
       ▼
RepoContext
       │
       ▼
generator.build_prompt()             确定性选角 + prompt 组装
       │
       ▼
OpenAI-compatible LLM                唯一非确定性步骤：写剧本
       │
       ▼
validator.sanitize()                 白名单校验、降级、修复死跳转
       │
       ▼
packager.package()                   WebGAL 官方发行版模板克隆与注入
       │
       ▼
output/<repo>/                       可由任意静态服务器托管
```

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

- GitHub REST/GraphQL 认证
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

### 3.2 渲染：OpenWebGAL/WebGAL

- 许可证：MPL-2.0
- 接入方式：下载固定版本官方 `*-web.zip`，校验 SHA-256，按版本缓存后复制
- 约束：黑盒使用，不修改引擎源码
- 场景入口：`game/scene/start.txt`
- 权威语法来源：WebGAL parser 源码，而非早期规划或模型记忆

详见 `docs/dev/webgal-script-reference.md`。

### 3.3 LLM

- 协议：OpenAI-compatible Chat Completions
- 默认配置：环境变量 `REPO2GAL_BASE_URL`、`REPO2GAL_MODEL`、`REPO2GAL_API_KEY`
- LLM 只负责叙事创作，不负责 GitHub 抓取、角色白名单、流程校验和资源打包

## 4. 模块职责

| 文件 | 职责 | 不应承担 |
|---|---|---|
| `fetcher.py` | 调上游备份工具；把落盘数据转成 `RepoContext` | 自己请求 GitHub API |
| `generator.py` | 确定性选角、上下文渲染、LLM 调用 | GitHub 抓取、WebGAL 打包 |
| `validator.py` | WebGAL 安全子集、流程完整性、静默错误降级 | 改写剧情内容 |
| `webgal.py` | 经源码核实的命令常量与转义 | 猜测引擎语法 |
| `packager.py` | 获取发行版、覆盖 config/scene、输出静态站点 | 修改 WebGAL 引擎 |
| `cli.py` | 参数与阶段编排 | 业务逻辑实现 |

## 5. 原始数据与上下文

原始备份目录：

```text
.repo2gal/backups/<owner>/
└── repositories/<repo>/
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

当前上游不会把仓库列表元数据单独落盘，因此 Star 和 topics 暂不可用。
不要为补这两个字段重新写 API 客户端；应优先请求上游增加 repository metadata 输出，
或找到另一个成熟、兼容的元数据工具。

## 6. 为什么 validator 是硬边界

WebGAL 对未知命令不会报错，而会把命令名当作 speaker：

```ts
return SCRIPT_CONFIG_MAP.get(command)?.scriptType ?? commandType.say;
```

所以 LLM 输出 `showCode:print(1);` 时，游戏会正常启动，但出现一个名叫 `showCode`
的角色。validator 必须在打包前执行，并且不可通过“模型应该不会出错”绕过。

## 7. 素材系统（已决策，未实现）

素材来源插件化，但格式统一：

```text
Local Provider ───┐
Git Provider ─────┼──> Repo2Gal Asset Pack ──> Validator ──> WebGAL Adapter
AI Provider ──────┘
```

素材包必须引擎无关。剧本引用逻辑 ID，例如 `background.archive`，WebGAL Adapter
再映射为 `game/background/archive.webp`。

完整规范见 `docs/dev/asset-pack-spec.md`。

## 8. 许可证边界

计划中的分层：

| 组件 | 许可证 |
|---|---|
| Repo2Gal 程序代码 | 计划 GPL，具体版本待根目录 `LICENSE` 锁定 |
| WebGAL | MPL-2.0，保持原许可证 |
| python-github-backup | MIT |
| Asset Pack | 各自许可证，必须 SPDX 标识并保留 NOTICE |
| 用户生成剧本 | 由用户和所用模型条款决定 |

程序采用 GPL 不意味着外部媒体自动变成 GPL。最终打包器未来必须聚合素材包声明并生成
`THIRD_PARTY_NOTICES.md`。

## 9. 当前状态与下一步

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

`v0.1.0` 结论：当前 Chronicle MVP 已可用，不再处于“仅设计”或“待跑通”状态。

推荐下一步：

1. 进入下一里程碑：落地 Asset Pack v1 JSON Schema 与本地 Provider。
2. 给备份解析器增加真实 `python-github-backup` fixture 回归样本。
3. 用真实 LLM 评估 Chronicle prompt，建立固定仓库 golden cases。
4. 再考虑多场景拆分、Git Asset Provider 和 AI Asset Provider。
