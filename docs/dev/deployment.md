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

## 自动部署

仓库通过两条 GitHub Actions workflow 持续部署：

| Workflow | 触发条件 | 职责 |
|---|---|---|
| `.github/workflows/ci.yml` | 所有 push 和 PR | 离线测试、内置 Asset Pack 校验、release wheel 构建 |
| `.github/workflows/deploy-demo.yml` | `main` 的 CI 成功后；或在 `main` 手动触发 | 真实数据/LLM 生成、严格校验、审计上传、Vercel production 部署和线上校验 |

标准路径是每次 push 到 `main` 部署一次最终 commit。一次 push 包含多个 commit 时不会逐个
重复调用 LLM；快速连续 push 会由 concurrency 取消旧部署，只保留最新 commit。

PR 不会获得生产 secrets，也不会部署。Deploy job 使用 GitHub `production` environment，
可以在仓库 Settings 中为该 environment 增加 required reviewers。

### 必需 Secrets

在 GitHub 仓库 `Settings -> Secrets and variables -> Actions` 中配置 repository secret，
或在 `production` environment 中配置同名 environment secret：

| Secret | 用途 |
|---|---|
| `REPO2GAL_API_KEY` | LLM 1 剧情生成和 LLM 2 Performance Plan |
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

### 自动生成策略

生产生成使用：

```bash
repo2gal RhoPaper/Repo2Gal \
  --asset-pack builtin:cc0-chronicle --public-assets \
  --performance --strict --strict-performance \
  --save-beat-manifest .repo2gal/audit/beat-manifest.json \
  --save-performance-plan .repo2gal/audit/performance-plan.json \
  --save-performance-report .repo2gal/audit/performance-report.json \
  --output output/Repo2Gal
```

Workflow 缓存固定 WebGAL 模板和 `python-github-backup` 原始层，但不传 `--reuse-backup`：
每次部署仍会让上游增量更新 GitHub 数据。生成或严格校验失败时不会执行 Vercel 部署，已有
生产版本保持不变。

每次成功生成会保留 30 天 GitHub Artifact：Beat Manifest、Performance Plan、Performance
Report、最终 `start.txt` 和第三方声明。

Performance Plan 中 `screen.transition` 的 `phase` 和 `duration` 允许模型省略；普通代码会按
preset 推导 phase，并使用 `medium` 默认时长。这类机械补全只产生 warning，不会让严格部署
失败；未知能力、无目标背景和角色状态冲突仍会阻止生产部署。

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

## 注意事项

- `output/Repo2Gal/vercel.json` 是复制品，重新生成会丢失；权威文件是已跟踪的
  `deploy/vercel.json`。未来可再把复制逻辑纳入 `packager.py`；
- 产物约 93 MB（含 WebGAL 引擎与官方演示 vocal），在 Vercel 静态部署限额内；
- `VERCEL_TOKEN` 属敏感凭据，不要写入任何仓库文件或日志。
