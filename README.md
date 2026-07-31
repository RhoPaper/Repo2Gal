# Repo2Gal

把 GitHub 仓库变成可游玩的 WebGAL 视觉小说。

输入一个仓库地址，输出一个静态网站——用视觉小说的形式讲述这个项目的编年史：
它为何诞生、经历过哪些争论、社区如何演变。素材全部来自仓库的真实 Issue/PR 讨论。

> 状态：MVP 可跑通。当前仅实现 Chronicle（编年）模式。

## 快速开始

```bash
python3 -m venv .venv && .venv/bin/pip install -e .

export GITHUB_TOKEN=ghp_xxx        # 可选，但强烈建议（匿名仅 60 次/小时）
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
```

## 工作原理

```
GitHub API  ──►  RepoContext  ──►  LLM  ──►  validator  ──►  WebGAL 产物
  抓取讨论        结构化素材        写剧本      收敛降级        静态站点
```

| 模块 | 职责 |
|---|---|
| `fetcher.py` | 抓仓库元信息、README、贡献者、Release、热门 Issue/PR 讨论 |
| `generator.py` | 定角色表（确定性）、拼 prompt、调 LLM |
| `validator.py` | 把脚本收敛到安全语法子集 |
| `packager.py` | 克隆 WebGAL 发行版模板，注入脚本 |
| `cli.py` | 串联流程 |

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

## 已知限制

- **素材匮乏是当前最大短板。** WebGAL 发行版只自带 3 张背景 + 1 首 BGM，
  产物观感受限。这是决定项目传播力的关键问题，尚未解决。
- 仅 Chronicle 一种模式。
- 剧情为单场景线性叙事 + 少量分支，未做多场景切分。
- 讨论抓取依赖 GitHub Search API，冷门仓库素材可能不足。

## 开发

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests/ -q
```

## 文档

- [`docs/dev/webgal-script-reference.md`](docs/dev/webgal-script-reference.md) —
  WebGAL 语法速查表，对照解析器源码核实过，**写代码前先读这个**
- [`docs/dev/early/`](docs/dev/early/) — 早期规划文档（v1–v9）及其勘误

## 许可

产物基于 WebGAL 引擎（MPL-2.0）。
