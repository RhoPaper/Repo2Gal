# 早期规划文档索引与勘误

这里是 v1–v9 的规划文档，保留作为决策轨迹。

当前实现已经进入 `v0.2.0` 可用基线：Chronicle MVP 于 2026-07-31 完成真实环境
端到端实测，随后加入采集/下载进度和官方 REST 元数据补充。本目录不再代表项目当前进度，
当前状态以根目录 README 和 `../architecture.md` 为准。

> ⚠️ **动手写代码前请先读 [`../webgal-script-reference.md`](../webgal-script-reference.md)。**
> 本目录多份文档含有错误的 WebGAL 语法，照抄会产出跑不起来或错渲染的产物。

## 版本一览

| 版本 | 作者 | 定位 | 仍然有效的部分 |
|---|---|---|---|
| v1.0 / v1.1 | Gemini | 三层架构雏形 | **「确定性脚本 vs LLM 职责分离」**——贯穿到最后的核心原则 |
| v2.0 | DeepSeek | 企业级 PRD（957 行） | 附录 B 西幻映射表；§3.2.4 剧情线性化策略 |
| v3 | Gemini | 转纯 Python | 放弃「LLM 输出 JSON」，改 Markdown DSL |
| v4 | ChatGPT | **定位重构** | 「Interactive Anime Documentation」而非 Galgame；Context Builder 层 |
| v5 | Gemini | 工程纪律 | No Over-engineering；解析失败降级旁白而非抛异常 |
| v6 | Gemini | 宣传白皮书 | 基本无可用内容 |
| v7 | Gemini | 依赖选型 | 引入 PocketFlow |
| v8 | Gemini | 依赖选型修正 | 认识到 Issue/PR 完整讨论比宏观统计更有叙事价值 |
| v9 | 多份 | DAG 重构 + 深调研 | 静态模板克隆注入策略 |

## 最终采纳

**v4 的定位 + v1.1 的职责分离 + v5 的工程纪律 + v9 的模板注入。**

实现时相对规划做的三处偏离：

1. **不用 PocketFlow。** 六个节点顺序执行本就是一条直线，六个函数依次调用即可。
   等到需要 map-reduce 分章节生成时再引入。
2. **采集统一依赖 `josegonzalez/python-github-backup`。** 早期曾短暂自写 GitHub API
   客户端，后确认成熟项目已经覆盖认证、分页、限流、Issue/PR、Discussion、wiki、
   Release 和增量备份，自写实现已删除。Repo2Gal 只保留 subprocess 适配和数据归一化。
3. **三模式砍成一个，只做 Chronicle。** 三套 prompt = 三倍调试成本。
   且 Explorer 模式本质是「AI 重写 README」，最容易被质疑价值。

## 🔴 勘误：以下写法是错的

| 错误 | 出处 | 正确 |
|---|---|---|
| 脚本扩展名 `.wg` | **v9 全部 5 份** | `.txt`，位于 `game/scene/` |
| `say:角色:文本` | v9 `deep-research-report(2).md` | `角色名:文本;`；`say:文本;` 是旁白 |
| `webgal build` / `webgal serve` CLI | v9 `deep-research-report.md` | **不存在**。npm `webgal` 是 0.0.0 占位包，`WebGAL-Server` 2022 年已归档。用静态模板克隆 |
| `changeBg:assets/bg/tower.jpg` | v3、v5 | `changeBg:bg.webp;`——只写文件名，引擎按命令类型自动补目录 |
| WebGAL 有 `if` 条件块 | v2 §6.5.1 | `if` 是命令不是块；实际常用 `jumpLabel:x -when=a>1;` |
| `github_analyzer` 需要 Node.js ≥18 | v2 §9.1 | 它是 **Python** 项目 |
| `donoeidon/repo2txt` | v2 §3.1.1 | 拼写错误（少个 c），正确是 `donoceidon`，原链接 404 |
| `show_code_board` 需三层降级策略 | v2 §6.5.2 | 引擎原生支持富文本 `[文本](style=color:#B5495B\;)`，问题不存在 |

**v9 自相矛盾**：《核心架构设计》说「为避开不存在的 WebGAL CLI，采用静态模板克隆」，
而同目录的 `deep-research-report.md` 却把 `webgal serve` 写进了验收标准。

### 根因

9 个版本全程没有人查过官方源码，一直在猜语法。
v2 甚至明写「具体语法由实现者查阅文档确定」——然后无人执行。

注意 `OpenWebGAL/script-specification` 仓库**只有流程说明、没有实际规范内容**，
真正的权威源是解析器源码 `packages/parser/src/`。

## `research/script_quality_bench/`

原名 `script_format/`，但内容不是格式调研——是 6 个模型对同一任务
（写《Vue 的诞生》剧本）的输出横评。这是本目录**最被低估的资产**：
既是模型选型依据，也是现成的 few-shot 样例。已改名以正视听。
