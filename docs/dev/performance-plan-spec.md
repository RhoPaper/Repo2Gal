# Performance Plan v1 设计

> 状态：**v0.5.0 已实现第一版流水线。** Schema、Beat Manifest、Performance Plan 校验、
> 确定性 WebGAL 编译和显式 CLI 开关已落地；仍需继续通过真实模型和 WebGAL 产物调优视觉
> golden cases。
>
> 本文定义 Chronicle 的动态演出规划协议。
> 当前 WebGAL 目标版本固定为 `4.6.2`，实现以该版本发行版中的 parser、
> 官方 demo 和实际产物验证命令语义。

## 1. 目标与原则

Repo2Gal 的动态演出采用“两次 LLM + 确定性编译”模式：

```text
LLM 1 剧情脚本
        │
        ▼
Python sanitize + Beat Manifest
        │
        ▼
LLM 2 Performance Plan JSON
        │
        ▼
Schema Validator + 状态机 Validator
        │
        ▼
WebGAL Performance Compiler
        │
        ▼
按 beat_id 合并到剧情 AST
        │
        ▼
最终 WebGAL Validator + Package
```

### 1.1 必须满足

- LLM 1 只负责真实项目历史和对白；
- LLM 2 只负责演出意图，不直接生成 WebGAL 命令；
- `beat_id`、运行时角色 ID、素材文件名、坐标、时长和时序参数全部由确定性代码负责；
- 演出计划引用不存在的 beat、角色、素材或能力时不得进入产物；
- 演出失败时默认保留可玩的剧情，不把动画错误降级为对白；
- 相同剧情、计划、素材和 WebGAL 版本必须生成字节稳定的演出脚本；
- 编译器只能输出经过固定能力表允许的 WebGAL 命令。

### 1.2 不在 v1 范围内

- LLM 直接输出 `setTransform`、`setTempAnimation` 或 `pixiPerform` 原始语句；
- 任意 JavaScript、CSS、DOM 或 Pixi 配置；
- 多包素材组合和动态下载素材；
- Live2D、视频摄像机、复杂 UI、音效设计；
- 自动学习新的 WebGAL 动画名称；
- 让模型决定 `-next`、`-parallel`、`-continue`、`-keep`；
- 让模型决定绝对坐标、资源路径或 WebGAL 运行时 target ID；
- Agent tool-calling 循环。v1 是有界的两次生成调用和确定性编译。

## 2. WebGAL 4.6.2 目标能力

以下能力来自锁定版本 `4.6.2` 的 parser 与官方 demo，不根据模型记忆放行：

| 语义能力 | WebGAL 编译目标 | v1 状态 |
|---|---|---|
| 立绘进入 | `changeFigure` + `-id` / `-enter` / `-next` | 支持 |
| 立绘退出 | `changeFigure:none -id=...` | 支持 |
| 立绘移动、缩放、透明度 | `setTransform` | 支持，参数由编译器生成 |
| 立绘震动/往返 | `setTempAnimation` | 支持，关键帧由编译器生成 |
| 预设立绘动画 | `setAnimation` | 支持，仅允许能力表中的 preset |
| 背景转场 | 补丁对应 `changeBg` 的 `-enter/-exit` 参数 | 支持，仅允许能力表中的 preset |
| Pixi 场景效果 | `pixiInit` + `pixiPerform` | 支持，仅允许能力表中的 preset |
| 任意滤镜 | `setFilter` | v1 暂缓 |
| 任意 UI/CSS | `applyStyle` / `setTextbox` | v1 暂缓 |
| 音效 | `playEffect` | 等 Asset Pack 支持 `se` 后再设计 |

官方依据：

- [4.6.2 `scriptConfig.ts`](https://raw.githubusercontent.com/OpenWebGAL/WebGAL/4.6.2/packages/parser/src/config/scriptConfig.ts)
- [4.6.2 `argsParser.ts`](https://raw.githubusercontent.com/OpenWebGAL/WebGAL/4.6.2/packages/parser/src/scriptParser/argsParser.ts)
- [4.6.2 `demo_parallel_animation.txt`](https://raw.githubusercontent.com/OpenWebGAL/WebGAL/4.6.2/packages/webgal/public/game/scene/demo_parallel_animation.txt)
- [4.6.2 `demo_performs.txt`](https://raw.githubusercontent.com/OpenWebGAL/WebGAL/4.6.2/packages/webgal/public/game/scene/demo_performs.txt)
- [4.6.2 `demo_zh_cn.txt`](https://raw.githubusercontent.com/OpenWebGAL/WebGAL/4.6.2/packages/webgal/public/game/scene/demo_zh_cn.txt)

## 3. Beat Manifest

Beat Manifest 是 Python 从**已经 sanitize 的剧情脚本**中确定性生成的中间视图。
LLM 不创建和修改 `beat_id`。

### 3.1 Beat 类型

v1 只允许下列 beat 作为演出锚点：

| 类型 | 是否可作为锚点 | 说明 |
|---|---:|---|
| `dialogue` | 是 | 角色台词 |
| `narration` | 是 | 旁白台词 |
| `scene_command` | 否 | 背景、BGM、立绘等原始剧情命令 |
| `choice` | 否 | 分支选择本身，演出可绑定 choice 前后的 dialogue |
| `label` | 否 | 流程控制节点 |
| `comment` | 否 | 注释和 validator 诊断 |

### 3.2 Beat Manifest 示例

```json
{
  "schemaVersion": 1,
  "sceneId": "start",
  "storyHash": "sha256:...",
  "beats": [
    {
      "id": "b0001",
      "ordinal": 1,
      "sourceLine": 8,
      "kind": "dialogue",
      "speaker": "Repo2Gal",
      "text": "项目第一次进入公共视野。",
      "branchPath": [],
      "stateBefore": {
        "background": "background.archive",
        "bgm": "bgm.archive",
        "figures": {
          "Repo2Gal": {
            "visible": true,
            "slot": "left",
            "asset": "character.guide.normal"
          }
        }
      }
    }
  ]
}
```

### 3.3 Beat 生成规则

- `id` 使用 `b` 加六位十进制序号，例如 `b000001`；序号只由 Python 分配；
- `ordinal` 按规范化脚本中的可演出语句顺序递增；
- `sourceLine` 仅用于诊断，不作为 LLM 合并主键；
- `storyHash` 是 sanitize 后剧情正文的 SHA-256，防止计划被错误复用到另一份剧情；
- `branchPath` 使用已解析的 label 路径，例如 `[]`、`["choose1"]`；
- `stateBefore` 是确定性状态快照，不允许 LLM 修改；
- 台词文本只供 LLM 理解，编译器不使用文本匹配定位；
- 计划必须引用当前 `storyHash`，不匹配时整个计划失效。

## 4. Performance Plan v1

### 4.1 顶层结构

```json
{
  "$schema": "https://repo2gal.dev/schemas/performance-plan/v1.json",
  "schemaVersion": 1,
  "sceneId": "start",
  "storyHash": "sha256:...",
  "profile": "chronicle-subtle",
  "cues": [
    {
      "id": "cue0001",
      "beatId": "b0001",
      "anchor": "during",
      "actions": [
        {
          "kind": "figure.move",
          "character": "Repo2Gal",
          "to": "center",
          "duration": "medium",
          "easing": "easeOut"
        }
      ]
    }
  ]
}
```

顶层字段规则：

| 字段 | 类型 | 规则 |
|---|---|---|
| `$schema` | string | 固定为 Performance Plan v1 URI |
| `schemaVersion` | integer | 固定为 `1` |
| `sceneId` | string | 必须对应当前场景 |
| `storyHash` | string | 必须等于 Beat Manifest 的 hash |
| `profile` | enum | `chronicle-subtle`、`chronicle-cinematic` |
| `cues` | array | 最多 256 个，按 beat ordinal 和 cue id 排序 |

所有对象使用 `additionalProperties: false`。LLM 输出 JSON 失败、重复键或额外字段时，
该计划整体视为无效，不尝试猜测修复。

### 4.2 Cue 字段

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | string | `cue` 加六位序号，必须唯一；由 LLM 提供但由 Python 校验格式 |
| `beatId` | string | 必须引用已有 dialogue/narration beat |
| `anchor` | enum | `before`、`during`、`after` |
| `actions` | array | 每个 cue 最多 3 个动作 |

Anchor 语义由编译器解释：

| anchor | 编译语义 |
|---|---|
| `before` | 在台词执行前完成动作，默认允许阻塞 |
| `during` | 与该台词并行执行，编译器负责 `-parallel` / `-continue` |
| `after` | 在该台词结束后执行，默认允许阻塞 |

LLM 不输出 WebGAL 的同步参数。

## 5. Action 枚举

### 5.1 `figure.enter`

```json
{
  "kind": "figure.enter",
  "character": "Repo2Gal",
  "slot": "left",
  "motion": "from-left",
  "duration": "medium"
}
```

规则：

- `character` 必须来自确定性角色表；
- `slot` 只能是 `left`、`center`、`right`；
- `motion` 只能是 `none`、`from-left`、`from-right`、`fade`；
- 角色当前必须为 hidden；
- 素材由 Python 从角色和 Asset Pack 状态决定；
- runtime `figure_id` 由 Python 生成，不进入 LLM 协议。

### 5.2 `figure.exit`

```json
{
  "kind": "figure.exit",
  "character": "Repo2Gal",
  "motion": "fade",
  "duration": "short"
}
```

规则：

- 角色当前必须 visible；
- v1 编译为 `changeFigure:none -id=<runtime_id>` 或固定退场宏；
- 退场后不能在同一 branchPath 中继续对该角色执行 move/animate，除非重新 enter。

### 5.3 `figure.move`

```json
{
  "kind": "figure.move",
  "character": "Repo2Gal",
  "to": "center",
  "duration": "medium",
  "easing": "easeOut"
}
```

规则：

- `to` 只能使用语义槽位，不接受 `x`、`y`；
- Python 从 WebGAL 4.6.2 校准表获取坐标；
- 角色必须 visible；
- 同一个角色同一 cue 只能有一个 transform 动作；
- `duration` 为 `instant`、`short`、`medium`、`long`；
- `easing` 为 `linear`、`easeIn`、`easeOut`、`easeInOut`。

### 5.4 `figure.shake`

```json
{
  "kind": "figure.shake",
  "character": "Repo2Gal",
  "intensity": "normal",
  "duration": "short"
}
```

规则：

- 只能使用 `subtle`、`normal`、`dramatic`；
- 关键帧由 Python 固定生成，LLM 不传数组；
- `dramatic` 在 `chronicle-subtle` profile 中自动降级为 `normal` 并记录 finding；
- 角色必须 visible；
- 编译器必须保证动画结束后恢复原位置。

### 5.5 `figure.animate`

```json
{
  "kind": "figure.animate",
  "character": "Repo2Gal",
  "preset": "move-front-and-back",
  "duration": "medium"
}
```

规则：

- `preset` 必须存在于 WebGAL 4.6.2 capability registry；
- LLM prompt 只列出当前 registry 中的 preset；
- Python 决定 target、同步方式和是否保留最终状态；
- 未注册 preset 直接拒绝该 cue。

### 5.6 `screen.transition`

```json
{
  "kind": "screen.transition",
  "phase": "enter",
  "preset": "shockwaveIn",
  "duration": "short"
}
```

规则：

- `phase` 只能是 `enter` 或 `exit`；
- `preset` 必须来自背景转场 capability registry；
- v1 默认 target 固定为 `bg-main`，不允许 LLM 指定 DOM target；
- Beat Manifest 记录该 beat 前最近一次确定可达的 `changeBg` 语句；编译器把 preset 和
  duration 补丁直接合并到该命令，使效果与背景进入/退出同步；
- `duration` 映射为 `-enterDuration` 或 `-exitDuration`；
- 分支合并后无法唯一确定 `changeBg` 时拒绝 transition；同一次背景切换只允许一个 transition；
- `shockwaveIn` 必须配 `phase=enter`，`shockwaveOut` 必须配 `phase=exit`。

### 5.7 `screen.effect`

```json
{
  "kind": "screen.effect",
  "preset": "snow",
  "intensity": "subtle"
}
```

规则：

- `preset` 只能来自实际模板已验证的 Pixi preset，例如 `snow`、`rain`、`cherryBlossoms`；
- v1 只支持 scene lifetime，不承诺任意毫秒级停止；
- 同一场景最多一个 active screen effect；
- `pixiInit` 和 `pixiPerform` 的顺序由编译器固定；
- `intensity` 只有在 capability registry 明确支持时才生效，否则忽略并记录 finding。

## 6. Profile 与演出预算

Profile 不由 LLM 自由选择，来自用户配置或 CLI 参数。

### `chronicle-subtle`

- 每 3 个 beat 最多一个 cue；
- 每个 cue 最多 2 个动作；
- 不允许 `dramatic` shake；
- 每场景最多一个 Pixi effect；
- 优先背景转场、轻微移动和淡入淡出；
- 不主动改变玩家阅读节奏。

### `chronicle-cinematic`

- 每 2 个 beat 最多一个 cue；
- 每个 cue 最多 3 个动作；
- 允许 `dramatic` shake；
- 每场景最多两个 Pixi effect，但不能重叠启动；
- 允许少量 `during` 并行动画；
- 仍不允许 LLM 直接提供时间和坐标。

超出预算不是通过删除随机动作解决，而是按固定优先级裁剪：

```text
figure.enter/exit > screen.transition > figure.move > figure.animate
> figure.shake > screen.effect
```

裁剪结果写入 Performance Report。

## 7. Runtime State Machine

编译器维护每个场景的确定性状态：

```text
FigureState {
  character: semantic character name,
  runtimeId: compiler-generated id,
  assetId: selected logical asset id,
  visible: bool,
  slot: left | center | right,
  transform: current normalized transform,
  animationBusy: bool
}
```

状态转移：

| 当前状态 | 动作 | 结果 |
|---|---|---|
| hidden | enter | visible，生成 runtimeId |
| visible | move | visible，更新 slot/transform |
| visible | animate | visible，保留或恢复 transform |
| visible | shake | visible，动画结束恢复原 transform |
| visible | exit | hidden，释放 runtimeId |
| hidden | move/animate/shake/exit | 拒绝 |

编译器不能依赖 LLM 声称的角色状态，必须从剧情命令和已编译动作顺序自行推导。

同一分支中的每次剧情 `changeFigure` 都带确定性 story version，即使资源和槽位文本相同也会
重新同步 Performance 状态。前向 `choose`/`jumpLabel` 的入边状态在 label 处合并；角色在
不同分支的可见性、素材或 framing 不一致时标记为 ambiguous，并拒绝汇合点角色动作。

背景、BGM 和 Pixi effect 也有状态：

- `changeBg` 更新 background state；
- `bgm` 更新 bgm state；
- `screen.effect` 检查 active effect 数量；
- 分支进入时复制 branch checkpoint，不能把一条分支的角色状态泄露到另一条分支。

## 8. WebGAL 编译宏

编译器输入语义动作，输出固定模板。下列示例是实现约束；新增宏或升级 WebGAL 前必须以
本地缓存的 WebGAL 4.6.2 发行版重新进行渲染验收。

### `figure.move`

输入：`character=Repo2Gal, to=center, duration=medium, easing=easeOut`

编译步骤：

1. 查找 `Repo2Gal` 的 runtime ID；
2. 查找 `center` 的固定坐标；
3. 查找 `medium` 的固定毫秒数；
4. 生成 `setTransform` JSON；
5. 由 anchor 决定 `-next` 或 `-parallel/-continue`；
6. 更新 Runtime State。

LLM 永远看不到最终 JSON。

角色存在 Asset Pack framing 时，`figure.move` 只改变语义槽位，编译器会同时保留 framing 的
垂直偏移和缩放。`figure.shake` 使用 framing 后的当前位置作为往返基准；
`move-front-and-back` 编译为相对于 framing scale 的临时缩放，不得重置为全身默认比例。

### `figure.shake`

Python 维护固定关键帧模板：

```text
normal position
→ x - delta
→ x + delta
→ x - half_delta
→ normal position
```

`delta` 由 `intensity` 决定，`duration` 由 duration table 决定。

### `figure.enter`

Python 负责：

- 选择 Asset Pack 中的实际立绘文件；
- 生成唯一 `-id`；
- 把 `left/center/right` 转为固定位置；
- 选择已经注册的进入动画；
- 确定动作是否阻塞当前 beat。

### `screen.effect`

只允许编译器输出经过 registry 验证的 preset：

```text
pixiInit;
pixiPerform:snow;
```

LLM 不可以写 `pixiPerform:some-new-effect;`。

## 9. Python 接口草案

初版可以放在一个 `repo2gal/performance.py` 中，避免过早拆分模块；WebGAL 具体命令
生成可以在 `repo2gal/webgal_performance.py` 中隔离。

```python
def extract_beats(
    script: str,
    *,
    cast: Cast,
    asset_catalog: AssetCatalog,
) -> BeatManifest:
    """从已 sanitize 脚本生成稳定 beat manifest。"""

def validate_plan(
    plan: PerformancePlan,
    *,
    manifest: BeatManifest,
    capabilities: WebGALCapabilities,
    profile: PerformanceProfile,
) -> PerformanceReport:
    """执行 Schema、引用、状态、时序和预算校验。"""

def compile_plan(
    plan: PerformancePlan,
    *,
    manifest: BeatManifest,
    capabilities: WebGALCapabilities,
    profile: PerformanceProfile,
) -> list[PerformanceInsertion]:
    """只生成确定性 WebGAL 演出语句，不修改剧情正文。"""

def merge_insertions(
    script: str,
    insertions: list[PerformanceInsertion],
) -> str:
    """按 AST statement index/beat_id 合并，不按台词文本搜索。"""
```

`PerformanceInsertion` 至少包含：

```python
@dataclass(frozen=True)
class PerformanceInsertion:
    beat_id: str
    anchor: str
    ordinal: int
    lines: tuple[str, ...]
```

合并前按 `(beat_ordinal, anchor_order, cue_id, action_index)` 排序，保证同一输入字节稳定。

## 10. LLM 2 协议

LLM 2 的 system prompt 必须明确：

- 你是舞台导演，不是编剧；
- 不得修改 beat 文本；
- 只能引用输入中已有的 beat、角色和 capability；
- 不得生成 WebGAL 命令；
- 不得生成文件名、坐标、target ID 或任意 JSON transform；
- 无适合演出的 beat 时返回空 `cues`；
- 只输出 JSON，不输出 Markdown 或解释。

输入只包含：

- Beat Manifest；
- 确定性角色状态；
- 角色可用立绘能力；
- WebGAL capability registry；
- profile 和预算；
- 当前场景目标。

不重复发送完整 RepoContext，避免第二次调用重新编造事实。

### 调用策略

- LLM 1 使用当前 Chronicle 配置；
- LLM 2 初始温度建议 `0.2`，偏向结构稳定而不是创意发散；
- 如果兼容端点支持 JSON Schema response format，使用它；
- 即使端点声称返回 Structured Output，也必须本地运行 Schema 和语义校验；
- v1 不做无限修复循环；计划无效时采用最低确定性演出 fallback；
- 对缺失 `screen.transition.phase` 这类无歧义字段，普通模式可按 preset 补齐并标记 degraded；
  `--strict-performance` 仍拒绝该计划；
- 后续若增加一次修复调用，也必须是固定上限的普通重试，不引入 Agent loop。

## 11. 失败策略与报告

### 普通模式

```text
剧情有效 + Performance Plan 有效
→ 合并演出

剧情有效 + Performance Plan 无效
→ 保留原剧情
→ 生成一个最低确定性演出 fallback
→ Performance Report 标记 degraded
```

### 严格模式

新增 `--strict-performance`，与现有 `--strict` 分开：

- `--strict` 控制剧情 WebGAL validator；
- `--strict-performance` 控制演出计划和编译器 finding；
- 严格演出失败使用新的校验失败分支，不能把错误转成角色对白。

报告至少包含：

- plan 是否通过 Schema；
- cue/action 总数；
- 丢弃的 cue/action 及原因；
- 发生 fallback 的 beat；
- 编译出的 WebGAL 命令数量；
- 所用 WebGAL 版本和 capability registry hash；
- story hash 和 performance plan hash。

调试产物建议保存：

```text
repo2gal/
├── beat-manifest.json
├── performance-plan.json
└── performance-report.json
```

这些文件不是 WebGAL 引擎输入，只用于审计和复现。

## 12. 测试设计

所有测试保持离线。

### Schema 测试

- 合法空计划；
- 合法 enter/move/shake/transition/effect 组合；
- 重复 cue id；
- 未知 action kind；
- 多余字段；
- 超过 cue/action 数量上限；
- 非法 duration、slot、anchor、profile；
- 非法 beat id 格式。

### 语义状态测试

- hidden 角色 move 被拒绝；
- visible 角色重复 enter 被拒绝；
- exit 后 move 被拒绝；
- 同一角色冲突 transform 被拒绝；
- 不存在的 preset 被拒绝；
- 分支状态不互相泄露；
- story hash 不匹配时拒绝整个计划。

### 编译 golden tests

- enter from left；
- move left to center；
- normal shake；
- `during` 对话的并行动画；
- background transition；
- snow Pixi effect；
- 默认无演出时剧情字节完全不变；
- 非法计划 fallback 后剧情正文不被改写，仅插入确定性最低演出；
- 相同输入重复编译结果字节完全一致。

### 真实 WebGAL 验收

使用固定 WebGAL `4.6.2` 缓存模板人工检查：

- 动画不会阻塞下一句对白；
- `during` 动画确实与对白并行；
- 立绘移动后位置状态正确；
- shake 结束后角色回到原位置；
- Pixi effect 不重复叠加；
- 分支返回后角色状态正确；
- 存档/读档后动画状态不破坏剧情推进。

## 13. 实施顺序

1. [x] 固定 `WebGALCapabilities` 数据格式和 4.6.2 fixture；
2. [x] 实现 Beat Manifest 提取，不调用 LLM；
3. [x] 落地 Performance Plan v1 JSON Schema；
4. [x] 实现计划 Schema/语义/状态/预算校验；
5. [x] 实现 figure enter/move/shake 三个编译宏；
6. [x] 实现 transition 和 Pixi effect 编译宏；
7. [x] 实现 AST 插入和报告文件；
8. [x] 接入第二次 LLM 调用和显式性能配置；
9. [x] 补齐离线 golden tests；
10. [x] 用真实 WebGAL 4.6.2 做基础产物验收；
11. [ ] 在默认模式稳定后，再考虑是否把动态演出设为默认开启。

## 14. 待确认项

以下项目不影响 Schema 主体，当前决策如下：

1. [x] 动态演出第一版以 `--performance` 显式开启；
2. [x] `chronicle-subtle` 作为默认 profile；
3. [x] `screen.effect` 只支持场景生命周期；
4. [x] 通过三个独立 CLI 参数选择性保存 Beat Manifest、Performance Plan 和 Report JSON；
5. [x] 演出计划失败沿用现有 `ValidationFailed`，由 `--strict-performance` 触发。
