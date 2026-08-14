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

打包器暂不生成部署配置（后续待办），部署前在产物根目录放置：

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
npx -y vercel@latest projects add repo2gal-demo --token "$VERCEL_TOKEN"   # 首次
npx -y vercel@latest link --yes --project repo2gal-demo --token "$VERCEL_TOKEN"
npx -y vercel@latest deploy --prod --yes --token "$VERCEL_TOKEN"
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

- `vercel.json` 位于 gitignored 的 `output/` 内，重新生成会丢失；更新 demo 时
  按第二步重新放置。未来把部署配置生成纳入 `packager.py` 是待办项；
- 产物约 93 MB（含 WebGAL 引擎与官方演示 vocal），在 Vercel 静态部署限额内；
- `VERCEL_TOKEN` 属敏感凭据，不要写入任何仓库文件或日志。
