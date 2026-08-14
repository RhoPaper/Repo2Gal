# Repo2Gal 用户指南

给从宣传视频、搜索引擎或朋友推荐过来的新朋友：这一页告诉你怎么玩、怎么生成自己的作品，
以及常见问题。

## 1. 这是什么

Repo2Gal 把一个 GitHub 仓库变成一部**可游玩的视觉小说**（编年史模式）：

- 剧情素材全部来自仓库真实数据：源码、README、Issue、PR、Discussion、wiki 与 Release；
- 角色由代码从贡献者和技术栈推导（项目化身、核心参与者、技术栈精灵），不由模型胡编；
- 产出一个纯静态网站，双击或任意静态托管即可游玩。

**先玩一局在线演示**（就是本项目自己的编年史，用当前版本代码 dogfooding 生成）：

👉 **https://repo2gal.rhopaper.top/demo**

## 2. 怎么玩

演示与产物都基于 WebGAL 引擎：

- 点击画面 / 空格 / 回车推进对话；按 `Ctrl` 快进；
- 右上角菜单可以**存档、读档、快进、自动播放**，还有**流程图**（当前单章作品只有一个入口节点）与鉴赏；
- 分支选择用鼠标点击选项。

## 3. 生成你自己的作品

### 准备

1. Python 3.10+ 与 git；
2. `GITHUB_TOKEN`：GitHub 个人访问令牌（Discussion 走 GraphQL，必须认证）；
3. `REPO2GAL_API_KEY`：任意 OpenAI 兼容服务的 API Key（DeepSeek、Kimi、本地 vLLM 等）。

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
export GITHUB_TOKEN=github_pat_xxx
export REPO2GAL_API_KEY=sk-xxx

.venv/bin/repo2gal owner/repo          # 全流程：采集 -> 生成 -> 校验 -> 打包
python3 -m http.server -d output/<repo> 8000   # 本地预览
```

### 不花钱 / 离线玩法

```bash
.venv/bin/repo2gal vuejs/core --dry-run        # 只抓数据并打印 prompt，不调用 LLM
.venv/bin/repo2gal vuejs/core --script my_story.txt   # 手写剧本走完打包流程
.venv/bin/repo2gal vuejs/core --reuse-backup   # 复用上次原始备份，不联网
```

全部命令行选项、模式矩阵与退出码见 [`README.md`](../README.md#快速开始)。

### 一次生成要多久、花多少

- 采集耗时取决于仓库大小：全量 Issue/PR/Discussion 第一次可能较慢；重跑走上游增量备份；
- 生成只有一次 LLM 调用（单章剧本），成本取决于所选模型与上下文长度，通常几万 token 以内；
- `--dry-run` 完全不花钱，适合先看 prompt 与素材质量。

## 4. 常见问题

**Q：为什么必须提供 GitHub Token？**
采集依赖成熟的 `python-github-backup`（MIT），Discussion 的 GraphQL 接口必须认证。
Token 只用于调用官方 API，通过 0600 权限的临时文件传给上游，不出现在进程列表与日志。

**Q：生成的剧本靠谱吗？**
所有事实来自仓库真实数据；生成后强制过 validator——WebGAL 对未知命令不报错，
而是把命令名当角色名渲染，因此 validator 是硬边界：白名单外的命令一律降级为旁白，
跳转目标缺失会注释，缺 `end;` 会补齐。`--strict` 下存在任何降级即拒绝打包。

**Q：生成作品的版权归谁？**
Repo2Gal 程序代码为 GPL-3.0；WebGAL 引擎为 MPL-2.0；剧本内容按你所选模型的服务条款。
详见仓库根目录 `LICENSE` 与各上游许可声明。

**Q：只有 3 张背景、1 首 BGM？**
目前使用 WebGAL 发行版内置素材。Asset Pack 规范（本地/Git/AI 三类素材来源）已设计，
实现排在路线图后续，见 `docs/dev/asset-pack-spec.md`。

**Q：报错了怎么办？**
看退出码：2 用法错误、3 采集失败、4 LLM 失败、5 `--strict` 校验降级、6 打包失败。
错误信息已脱敏，可直接贴到 Issue 里求助。
