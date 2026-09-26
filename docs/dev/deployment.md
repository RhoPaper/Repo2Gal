# 在线演示部署

Repo2Gal 吃自己的狗粮：在线演示就是**用当前版本代码生成的本项目编年史**，
对外地址：

- 游戏入口：`https://repo2gal.rhopaper.top/demo`（根路径自动 307 到 `/demo`）
- 托管：Vercel（项目 `repo2gal-demo`，静态部署）
- 域名：`repo2gal.rhopaper.top`（Cloudflare 托管 DNS，CNAME 指向 Vercel）

## 架构

```text
output/Repo2Gal/（本地产物，gitignored）
       │  vercel deploy --prod
       ▼
Vercel 项目 repo2gal-demo ── 域名 repo2gal.rhopaper.top（已验证）
       ▲
Cloudflare DNS：repo2gal.rhopaper.top CNAME cname-china.vercel-dns.com（仅 DNS）
```

## 部署方式选择

两条部署路径**分开配置、互不影响**，可以只启用其中一条：

| 方式 | 适合谁 | 触发方式 | 额外依赖 |
|---|---|---|---|
| **GitHub Pages（推荐）** | 其它项目开发者：把自己仓库的演示挂出去 | `deploy-pages.yml`，`workflow_dispatch` 手动 | 只需 `REPO2GAL_API_KEY`；把仓库 `Settings -> Pages` 的 Source 设为 GitHub Actions |
| Vercel | 本仓库当前的生产演示（`repo2gal.rhopaper.top/demo`） | `deploy-demo.yml`，`main` 的 CI 成功后自动 | 另需 `VERCEL_TOKEN`、Vercel 项目与自定义域名 |

本仓库的演示站保持 Vercel 不变：`deploy-pages.yml` 在这里默认只手动触发，不会自动发布，
也不读取 Vercel 凭据。给自己项目部署时推荐 GitHub Pages——不需要 Vercel 项目或自定义
域名，站点地址就是 `https://<owner>.github.io/<repo>/`。

## 自动部署

仓库通过三条 GitHub Actions workflow 运行：

| Workflow | 触发条件 | 职责 |
|---|---|---|
| `.github/workflows/ci.yml` | 所有 push 和 PR | 离线测试、内置 Asset Pack 校验、release wheel 构建 |
| `.github/workflows/deploy-demo.yml` | `main` 的 CI 成功后；或在 `main` 手动触发 | 真实数据/LLM 生成、严格校验、审计上传、Vercel production 部署和线上校验 |
| `.github/workflows/deploy-pages.yml` | 在 `main` 手动触发（想持续部署再打开 `workflow_run` 触发器） | 同一套生成与校验流程，发布到 GitHub Pages（推荐给其它项目开发者的托管路径，不依赖 Vercel，见文末附录） |

标准路径是每次 push 到 `main` 部署一次最终 commit。一次 push 包含多个 commit 时不会逐个
重复调用 LLM；快速连续 push 会由 concurrency 取消旧部署，只保留最新 commit。

PR 不会获得生产 secrets，也不会部署。Deploy job 使用 GitHub `production` environment，
可以在仓库 Settings 中为该 environment 增加 required reviewers。

`deploy-pages.yml` 与 Vercel 完全分开：只用 `REPO2GAL_API_KEY`，发布到 GitHub Pages，
不读 `VERCEL_TOKEN`；启用方式和可选参数见文末「GitHub Pages 部署」。

### 必需 Secrets

在 GitHub 仓库 `Settings -> Secrets and variables -> Actions` 中配置 repository secret，
或在 `production` environment 中配置同名 environment secret：

| Secret | 用途 |
|---|---|
| `REPO2GAL_API_KEY` | 三轮 LLM（创作草稿、演出批注、导演 JSON） |
| `VERCEL_TOKEN` | 链接并部署 `rhopapers-projects/repo2gal-demo` |

GitHub 数据访问使用 Actions 自动提供的 `github.token`，不要另建长期 GitHub PAT。Workflow
只授予 `contents/issues/pull-requests/discussions: read`。该 `ghs_` installation token 会通过
`python-github-backup` 的公开 `--as-app` 模式使用，不需要第三个 secret。

### 可选 Variables

非默认模型时配置 repository/environment variables：

| Variable | 默认值 |
|---|---|
| `REPO2GAL_BASE_URL` | `https://api.deepseek.com/v1` |
| `REPO2GAL_MODEL` | `deepseek-v4-pro` |

`VERCEL_SCOPE=rhopapers-projects` 和 `VERCEL_PROJECT=repo2gal-demo` 是公开项目标识，已固定在
workflow 中，不属于 secret。

Workflow 在任何 GitHub 采集或 LLM 调用前执行 `vercel whoami`。无效、已撤销或无 team
访问权的 token 会立即失败，避免浪费生成时间和模型费用。Token 必须由 Vercel Account
Settings 的 Tokens 页面创建，并能访问 `rhopapers-projects`。

### 自动生成策略

生产生成使用：

```bash
repo2gal RhoPaper/Repo2Gal \
  --asset-pack builtin:cc0-chronicle --public-assets \
  --profile chronicle-subtle --strict \
  --save-stage-outputs .repo2gal/audit/stages \
  --output output/Repo2Gal
```

Workflow 缓存固定 WebGAL 模板和 `python-github-backup` 原始层，但不传 `--reuse-backup`：
每次部署仍会让上游增量更新 GitHub 数据。生成或严格校验失败时不会执行 Vercel 部署，已有
生产版本保持不变。

每次成功生成会保留 30 天 GitHub Artifact：草稿、演出批注、导演 JSON 各次尝试与反馈、
导演校验报告、最终 `start.txt` 和第三方声明。

导演 JSON（第三轮）校验失败时会自动打回重试（默认 2 次），反馈为逐条结构化错误；
重试耗尽后改用第一轮草稿的确定性兜底编译，保证产物仍可游玩。`--strict` 只控制最终
WebGAL validator 的降级是否拒绝产物。

`/demo` 路径由 Vercel 路由配置实现：游戏静态文件部署在站点根目录，
`vercel.json` 把 `/demo` 重写到根文件，因此**产物内部无需改动**。

## 一、生成产物（dogfooding）

用当前版本代码、复用本地原始备份、以现成剧本走完整管线：

```bash
.venv/bin/repo2gal RhoPaper/Repo2Gal \
    --reuse-backup --script <现成剧本.txt> --output output/Repo2Gal
```

或直接用上次产出的剧本作为 `--script` 输入（等于重新打包）：

```bash
.venv/bin/repo2gal RhoPaper/Repo2Gal \
    --reuse-backup --script output/Repo2Gal/game/scene/start.txt \
    --output output/Repo2Gal
```

## 二、写入 vercel.json

打包器暂不生成部署配置。自动部署从已跟踪的 `deploy/vercel.json` 复制；手动部署前在产物
根目录放置同样内容：

```json
{
  "redirects": [
    { "source": "/", "destination": "/demo", "permanent": false }
  ],
  "rewrites": [
    { "source": "/demo", "destination": "/index.html" },
    { "source": "/demo/:path*", "destination": "/:path*" }
  ]
}
```

原理：产物使用相对路径（`./assets/...`、`./game/...`），浏览器以 `/demo/` 为基准
请求资源，rewrite 把 `/demo/<资源>` 映射回站点根路径；`/` 跳转到 `/demo`。

## 三、部署到 Vercel

```bash
cd output/Repo2Gal
pnpm dlx vercel@59.3.0 link --yes \
  --project repo2gal-demo --scope rhopapers-projects --token "$VERCEL_TOKEN"
pnpm dlx vercel@59.3.0 deploy --prod --yes \
  --scope rhopapers-projects --token "$VERCEL_TOKEN"
```

- 部署输出别名为 `https://repo2gal-demo.vercel.app`；
- 本项目本地 `output/` 已被 `.gitignore` 忽略，`.vercel/` 链接目录也不入库。

## 四、绑定自定义域名

Vercel API 添加域名（已 `verified` 的域名无需 TXT 验证）：

```bash
curl -X POST "https://api.vercel.com/v10/projects/repo2gal-demo/domains" \
  -H "Authorization: Bearer $VERCEL_TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"repo2gal.rhopaper.top"}'
```

Cloudflare 侧（`rhopaper.top` 区域）添加：

```text
类型：CNAME   名称：repo2gal   目标：cname-china.vercel-dns.com   代理：仅 DNS
```

> 目标选用 `cname-china.vercel-dns.com` 是为国内（B 站）观众优化；境外可直接用
> `cname.vercel-dns.com`。

## 五、验证

```bash
curl -sI https://repo2gal.rhopaper.top/demo          # 期望 200
curl -sI https://repo2gal.rhopaper.top/              # 期望 307 -> /demo
curl -sI https://repo2gal.rhopaper.top/demo/game/scene/start.txt   # 期望 200
```

## 附：GitHub Pages 部署（推荐给其它项目开发者）

把自己仓库的演示挂出去时用 `deploy-pages.yml`：不需要 Vercel 项目或自定义域名，
凭据只有 `REPO2GAL_API_KEY`。它复用 `deploy-demo.yml` 的生成参数（内置 CC0 包、
`--strict`、审计 artifact），只替换发布环节，也不读取 `VERCEL_TOKEN`。

这条流水线不含项目特化信息：目标仓库、剧本模式、生成参数、采集凭据都从仓库
variables / secrets 读取。部署自己的项目时在 `Settings -> Secrets and variables
-> Actions` 里配置即可，不需要改动 workflow 文件。

启用步骤：

1. 仓库 `Settings -> Pages` 把 Source 设为 **GitHub Actions**；
2. 至少配置 `REPO2GAL_API_KEY` secret（LLM）；
3. 要生成的是别的仓库时，再配置 `REPO2GAL_TARGET_REPO` 与 `REPO2GAL_SOURCE_TOKEN`
   （一个能读到目标仓库的只读 PAT，`github.token` 只覆盖当前仓库）；
4. 在 `main` 触发一次。

### 可配置项

| 配置 | 类型 | 缺省 | 说明 |
|---|---|---|---|
| `REPO2GAL_TARGET_REPO` | variable | 当前仓库 | 要生成剧本的目标仓库 `owner/repo` |
| `REPO2GAL_MODE` | variable | `chronicle` | `chronicle` / `overview` / `quickstart` |
| `REPO2GAL_PROFILE` | variable | `chronicle-subtle` | 演出 profile（`--profile`） |
| `REPO2GAL_STRICT` | variable | 开启 | 设为 `false` 关闭 `--strict` |
| `REPO2GAL_AUTO_UPDATE` | variable | 关闭 | 设为 `true` 后按目标仓库推进每天自动更新 |
| `REPO2GAL_TIMEOUT_MINUTES` | variable | `60` | 生成超时分钟数 |
| `REPO2GAL_BASE_URL` | variable | `https://api.deepseek.com/v1` | OpenAI 兼容端点 |
| `REPO2GAL_MODEL` | variable | `deepseek-v4-pro` | 模型名 |
| `REPO2GAL_API_KEY` | secret | 必填 | LLM API Key |
| `REPO2GAL_SOURCE_TOKEN` | secret | `github.token` | 跨仓库采集用的只读 PAT |

`workflow_dispatch` 保留 `repo` 与 `mode` 两个一次性参数，用于临时指定别的目标，
优先级高于对应的 variable。

### 自动更新

默认只手动触发。把 `REPO2GAL_AUTO_UPDATE` 设为 `true` 后，流水线每天检查一次目标仓库
默认分支的 head：与上次生成记录的 revision 不同才重新生成，相同则只跑一个几秒的
`plan` job 直接结束。cron 固定为每天一次，GitHub 不支持变量驱动的 cron。

产物以站点根目录发布，站内资源本来就是相对路径，因此不需要 Vercel 那套 `/demo`
路由。站点地址为 `https://<owner>.github.io/<repo>/`。把 `REPO2GAL_TARGET_REPO` 指向
别的仓库后，站点仍发布在当前仓库的 Pages 下。

## 注意事项

- `output/Repo2Gal/vercel.json` 是复制品，重新生成会丢失；权威文件是已跟踪的
  `deploy/vercel.json`。未来可再把复制逻辑纳入 `packager.py`；
- 产物约 93 MB（含 WebGAL 引擎与官方演示 vocal），在 Vercel 静态部署限额内；
- `VERCEL_TOKEN` 属敏感凭据，不要写入任何仓库文件或日志。
