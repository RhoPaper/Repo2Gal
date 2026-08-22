# Chronicle Starter 素材包

这是 Repo2Gal 内置的 Asset Pack v1 示例，包含两张背景、一张透明立绘和一首氛围 BGM。
全部媒体由 RhoPaper 制作并通过 CC0-1.0 提供，可用于本地测试和公开发布。

```bash
repo2gal assets validate builtin:cc0-chronicle --public
repo2gal owner/repo --asset-pack builtin:cc0-chronicle --public-assets
```

不传 `--asset-pack` 时，Repo2Gal 仍使用 WebGAL 官方发行版自带的默认素材。素材包不会覆盖
WebGAL 的标题图片、标题音乐或 Logo，两套素材会在最终产物中并存。

## 资源

| 逻辑 ID | 类型 | 文件 |
|---|---|---|
| `background.archive` | 背景 | `backgrounds/archive.png` |
| `background.community` | 背景 | `backgrounds/community.png` |
| `character.guide.normal` | 角色 | `characters/guide/normal.png` |
| `bgm.archive` | BGM | `audio/archive.ogg` |

同目录 `.txt` 文件是素材创作需求描述，不参与游戏打包。BGM 的体积优化过程与原始文件哈希
记录在 `NOTICE.md`。

角色素材保留原始全身透明图，并在 manifest 中使用归一化 `framing` 元数据标注头顶、默认
上半身底线和视觉中心。WebGAL Adapter 会非破坏性地生成居中半身构图，腿部位于屏幕下方；
原图仍可供其他引擎或未来全身镜头使用。
