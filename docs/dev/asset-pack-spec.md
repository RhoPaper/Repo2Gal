# Repo2Gal Asset Pack v1 规范

> 状态：**v0.4.0 已实现本地单包闭环。** JSON Schema、Local Provider、Validator、
> WebGAL Adapter 与 `THIRD_PARTY_NOTICES.md` 已可用；Git/AI Provider、多包组合以及字体/UI
> Adapter 仍是计划，不能写成现有能力。

当前机器可读 Schema 随 Python 包分发：`repo2gal/schemas/asset-pack-v1.schema.json`。

## 1. 目标

外部媒体资源完全插件化，支持三种获取渠道：

1. 用户自行整理后本地导入；
2. 从 GitHub 开源素材仓库下载；
3. AI 生成，包括 UI 配色、立绘、背景和音乐。

三种渠道是 **Provider**，不是三种包格式。每个 Provider 最终必须输出同一种
Repo2Gal Asset Pack，核心流水线不关心素材从哪里来。

## 2. 设计原则

### 2.1 引擎无关

素材包不得直接使用 WebGAL 的 `game/background/`、`game/figure/` 目录语义。
包内使用逻辑 ID：

```text
background.archive
character.guide.normal
character.guide.happy
bgm.peaceful
se.click
font.code
palette.primary
```

由 WebGAL Adapter 在打包阶段转成真实目录。这样未来支持其他视觉小说引擎时，
素材生态无需重做。

### 2.2 采用成熟基础标准

不存在一个同时覆盖立绘、背景、BGM、UI、字体、AI 来源和许可证的通用视觉小说包规范，
因此容器格式由 Repo2Gal 定义，但基础字段必须复用成熟标准：

| 内容 | 标准 |
|---|---|
| 包版本 | Semantic Versioning 2.0.0 |
| 许可证 | SPDX License Identifier |
| Schema | JSON Schema Draft 2020-12 |
| 语言 | BCP 47，如 `zh-CN` |
| 颜色 | CSS Color，如 `#7C3AED`、`oklch(...)` |
| 文件类型 | IANA MIME Type |
| 时间 | ISO 8601 |
| 完整性 | SHA-256 |
| 地址 | URI |

禁止自行发明数字许可证枚举、非标准版本号或私有 MIME 名称。

### 2.3 授权可追溯

每个包必须包含包级默认许可证；单个文件可以覆盖许可证。缺失许可证的包不得发布到
公共素材索引。

GitHub 托管、AI 生成和“免费下载”均不等于无版权风险。

## 3. 固定目录结构

```text
my-asset-pack/
├── repo2gal-pack.json       # 必需：机器索引
├── LICENSE                  # 必需：包级默认许可证全文
├── NOTICE.md                # 必需：署名和第三方声明，可为空但必须存在
├── README.md                # 推荐：人类说明
├── backgrounds/
├── characters/
├── audio/
├── fonts/
├── ui/
├── generation/              # 可选：Prompt、seed、MIDI、生成脚本
└── licenses/                # 可选：逐文件许可证与来源快照
```

索引文件固定命名为 `repo2gal-pack.json`，不使用 `package.json`，避免与包内 Node 项目冲突。

## 4. Manifest 示例

```json
{
  "$schema": "https://repo2gal.dev/schemas/asset-pack/v1.json",
  "manifestVersion": 1,
  "name": "@repo2gal/example-cyber-pack",
  "version": "1.0.0",
  "displayName": "Repo2Gal Cyber Archive",
  "description": "适用于编年模式的赛博档案馆素材包",
  "authors": [
    {
      "name": "Example Artist",
      "url": "https://github.com/example"
    }
  ],
  "license": {
    "spdx": "CC0-1.0",
    "file": "LICENSE"
  },
  "homepage": "https://github.com/repo2gal/assets-cyber",
  "repository": {
    "type": "git",
    "url": "https://github.com/repo2gal/assets-cyber.git"
  },
  "keywords": ["cyber", "developer", "chronicle"],
  "locale": "zh-CN",
  "profiles": ["repo2gal.theme", "repo2gal.chronicle"],
  "theme": {
    "palette": {
      "primary": "#7C3AED",
      "secondary": "#22D3EE",
      "background": "#09090B",
      "surface": "#18181B",
      "text": "#FAFAFA",
      "mutedText": "#A1A1AA",
      "success": "#22C55E",
      "warning": "#F59E0B",
      "danger": "#EF4444"
    },
    "typography": {
      "body": "font.body",
      "heading": "font.heading",
      "code": "font.code"
    }
  },
  "assets": {
    "background.archive": {
      "type": "background",
      "file": "backgrounds/archive.webp",
      "mimeType": "image/webp",
      "width": 1920,
      "height": 1080,
      "sha256": "..."
    },
    "character.guide.normal": {
      "type": "character",
      "file": "characters/guide/normal.webp",
      "mimeType": "image/webp",
      "character": "guide",
      "emotion": "normal",
      "sha256": "..."
    },
    "bgm.archive": {
      "type": "bgm",
      "file": "audio/archive.ogg",
      "mimeType": "audio/ogg",
      "loop": true,
      "sha256": "..."
    }
  },
  "provenance": {
    "sourceType": "manual",
    "createdAt": "2026-07-31T08:00:00Z"
  }
}
```

## 5. 许可证模型

### 5.1 包级默认许可证

```json
{
  "license": {
    "spdx": "CC-BY-4.0",
    "file": "LICENSE"
  }
}
```

必须使用精确 SPDX 表达式，例如 `CC-BY-4.0`、`OFL-1.1`、`MIT`。
不得只写 `GPL`、`Creative Commons` 或 `free`。

### 5.2 单文件覆盖

```json
{
  "bgm.archive": {
    "type": "bgm",
    "file": "audio/archive.ogg",
    "license": {
      "spdx": "CC-BY-4.0",
      "copyright": "Copyright 2026 Example Artist",
      "source": "https://example.org/music/archive",
      "attribution": "Archive by Example Artist",
      "retrievedAt": "2026-07-31T08:00:00Z",
      "evidence": "licenses/archive-license.html"
    }
  }
}
```

打包器必须汇总所有 `attribution` 和许可证，生成 `THIRD_PARTY_NOTICES.md`；v0.4.0 已实现。

### 5.3 本地私有素材

允许本地包使用 `LicenseRef-Proprietary`，但这类包不得上传到公共素材索引。
“用户拥有文件”不等于“用户拥有再分发权”，CLI 必须区分本地使用与公开发布校验。

## 6. Provider 规范

Provider 的职责只有两个：获取素材、产出合规 Asset Pack。核心系统只读取包，不读取 Provider 私有状态。

### 6.1 Local Provider

已实现命令：

```bash
repo2gal assets init ./my-pack
repo2gal assets validate ./my-pack
repo2gal assets validate ./my-pack --public
repo2gal owner/repo --asset-pack ./my-pack --public-assets
```

`init` 生成最小目录、manifest、LICENSE 和 NOTICE 模板，且绝不覆盖非空目录；`validate`
执行 Schema、文件和授权检查。默认按本地使用校验，允许 `LicenseRef-Proprietary`；`--public`
和生成命令的 `--public-assets` 会拒绝全部 `LicenseRef-*`。

### 6.2 Git Provider

GitHub 只是传输渠道，不是信任来源。provenance 必须记录：

```json
{
  "sourceType": "git",
  "repository": "https://github.com/example/asset-pack",
  "revision": "完整 commit SHA",
  "retrievedAt": "2026-07-31T08:00:00Z"
}
```

必须锁定 release tag 对应的 commit SHA，不能只记录 `main`。下载后校验：

- JSON Schema；
- SHA-256；
- manifest 声明 MIME 与 magic bytes；
- 路径穿越与 Zip Slip；
- 软链接；
- 单文件和整包大小；
- LICENSE/NOTICE；
- 逐文件来源与授权。

实现 Git 下载与缓存时，应优先评估成熟包管理、Git 和归档库，不自行实现传输协议。

### 6.3 AI Provider

必须记录可复现信息和提供商条款：

```json
{
  "sourceType": "ai-generated",
  "provider": "example-provider",
  "model": "example-model-v2",
  "generatedAt": "2026-07-31T08:00:00Z",
  "promptFile": "generation/prompts.json",
  "seed": 123456,
  "providerTerms": "https://example.com/terms",
  "termsRetrievedAt": "2026-07-31T08:00:00Z"
}
```

AI 生成不自动等于 CC0。商业使用权可能依赖账户套餐、生成时间、输入参考素材和司法辖区。
无法映射 SPDX 时使用明确的 `LicenseRef-AI-*`，并在 `licenses/` 保存条款快照。

## 7. AI 音乐与 MIDI

MIDI 只包含音符和控制信息，最终音频还依赖 SoundFont、采样库或合成器。生成记录必须包含：

```json
{
  "method": "midi",
  "source": "generation/archive.mid",
  "renderer": "FluidSynth 2.x",
  "soundfont": {
    "name": "Example SoundFont",
    "license": "CC0-1.0",
    "source": "https://example.org/soundfont"
  }
}
```

优先选择明确开放授权的 SoundFont，保存 MIDI 与渲染脚本，并统一导出 Web 友好的 OGG。

## 8. Profile

不同素材包可以只提供一种能力。使用 Profile 表达最低完整度：

| Profile | 最低要求 |
|---|---|
| `repo2gal.palette` | 配色 |
| `repo2gal.ui` | 配色、字体、文本框或等价 UI 配置 |
| `repo2gal.character` | 至少一个角色及 `normal` 表情 |
| `repo2gal.audio` | 至少一首 BGM |
| `repo2gal.chronicle` | 编年模式所需背景、BGM、角色 |
| `repo2gal.complete` | 可独立生成完整游戏 |

MVP 只支持一个完整目录包，不实现依赖解析和多包覆盖。多包组合应在有真实需求后再设计。

v0.4.0 WebGAL Adapter 接受 `background`、`character`、`bgm`，分别映射到
`game/background/`、`game/figure/`、`game/bgm/`。逻辑 ID 全量进入目标文件名，例如
`character.guide.normal` 映射为 `character-guide-normal.png`；这避免末段同名和模板覆盖。
每个逻辑 ID 必须以自身素材类型和点号开头（例如 `background.*`），从语义上隔离 WebGAL
默认裸文件名，禁止素材包静默遮蔽 `bg.webp`、`s_Title.mp3` 等默认资源。
字体、UI、音效与视频的容器语义保留在路线图中，当前 Schema 不接受这些尚无 Adapter 的类型。

## 9. Validator 最低要求

Asset Pack v1 实现不得缺少以下校验：

1. `repo2gal-pack.json` 符合 Draft 2020-12 Schema；
2. 包名、SemVer、BCP 47、SPDX、MIME 合法；
3. 所有逻辑 ID 唯一；
4. 文件存在且路径不能逃出包根目录；
5. SHA-256 与实际文件一致；
6. 声明 MIME 与文件 magic bytes 一致；
7. `LICENSE` 和 `NOTICE.md` 存在；
8. Profile 必需素材齐全；
9. 公共发布模式下拒绝许可证不明确和 `LicenseRef-Proprietary`；
10. 不执行包内脚本，生成脚本只作为可审计源码保存。

当前额外资源上限：manifest 1 MiB、最多 256 个素材、媒体单文件 128 MiB、授权/审计材料
单文件 8 MiB 且最多 512 个、全部声明文件总计 512 MiB。JSON loader 在 Schema 前拒绝
重复键；路径必须为 POSIX 相对路径，包根、素材、LICENSE、NOTICE、evidence 与 AI
`promptFile` 均不能是符号链接。MIME 使用 `libmagic` 检查内容而不是按扩展名猜测。

读取与复制使用逐级 `openat` + `O_NOFOLLOW`；打包时从同一个已打开源文件描述符一边计算
SHA-256 一边写入以 `O_EXCL` 创建的目标，避免“先检查再复制”的竞态。缺少上述 OS 能力的
平台会拒绝 Asset Pack，但不影响不使用素材包的默认流程。

## 10. 实现顺序

1. [x] `repo2gal/schemas/asset-pack-v1.schema.json`；
2. [x] Local Provider 的 `assets init` / `assets validate`；
3. [x] Schema、路径、MIME、SHA、Profile 与授权 Validator；
4. [x] background / character / bgm WebGAL Adapter；
5. [x] 自动生成 `THIRD_PARTY_NOTICES.md` 并保留原始授权材料；
6. [ ] Git Provider；
7. [ ] AI Provider；
8. [ ] 字体、UI、音效、视频 Adapter；
9. [ ] 有真实需求后再设计多包组合。

Local Provider + Validator 已跑通；在 Git Provider 也出现真实多包需求之前，不做在线素材市场
或复杂依赖解析。
