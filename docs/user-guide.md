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

1. Python 3.10+ 与 git；使用 Asset Pack 时还需系统 `libmagic`（Debian/Ubuntu：`libmagic1`）
   及 `openat`/`O_NOFOLLOW` 支持；
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

### 使用本地素材包

仓库提供一套可公开发布的 CC0 Chronicle 示例素材：

```bash
.venv/bin/repo2gal assets validate builtin:cc0-chronicle --public
.venv/bin/repo2gal owner/repo \
  --asset-pack builtin:cc0-chronicle --public-assets
```

`--public-assets` 会拒绝 `LicenseRef-Proprietary` 和其他 `LicenseRef-*`；仅在本地使用自有但
不可再分发的素材时，可以不加该选项。最终产物会生成 `THIRD_PARTY_NOTICES.md`，并把原始
manifest、LICENSE、NOTICE 与 evidence 保存到 `third_party/asset-packs/`。

创建自己的包：

```bash
.venv/bin/repo2gal assets init ./my-pack
# 填写 repo2gal-pack.json，加入媒体并更新 SHA-256、LICENSE、NOTICE
.venv/bin/repo2gal assets validate ./my-pack
```

当前一次只支持一个本地包，素材类型限背景、立绘与 BGM；不下载 Git 包、不调用 AI 生成，
也不执行素材包里的脚本。不传 `--asset-pack` 时仍走 WebGAL 默认素材路径；传入包后，默认
背景/BGM 仍可在普通场景中与包内逻辑 ID 一起使用。

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
外部素材保持素材包声明的许可证，不会被改标 GPL。详见仓库根目录 `LICENSE`、产物中的
`THIRD_PARTY_NOTICES.md` 与各上游许可声明。

**Q：只有 3 张背景、1 首 BGM？**
这是不传 `--asset-pack` 时的兼容默认值。v0.4.0 已支持单个本地 Asset Pack，并内置两张
CC0 背景、一张透明立绘和一首 BGM 的示例。Git/AI Provider 仍在路线图中，见
`docs/dev/asset-pack-spec.md`。

**Q：报错了怎么办？**
看退出码：2 用法错误、3 采集失败、4 LLM 失败、5 `--strict` 校验降级、6 打包失败。
错误信息已脱敏，可直接贴到 Issue 里求助。
