# WebGAL 脚本语法速查表

> **权威性说明**：本文档所有结论均对照 `OpenWebGAL/WebGAL` 解析器源码与官方 demo 场景核实，
> 而非来自 LLM 记忆。核对源：
> - `packages/parser/src/config/scriptConfig.ts`（命令全集）
> - `packages/parser/src/scriptParser/{scriptParser,commandParser,contentParser}.ts`（解析规则）
> - `packages/webgal/public/game/scene/*.txt`（官方 demo）
>
> ⚠️ `OpenWebGAL/script-specification` 仓库目前只有流程说明，**没有实际规范内容**，不要指望它。

---

## 0. 三条最容易搞错的事实

| 常见错误说法 | 真相 |
|---|---|
| 场景文件是 `.wg` | ❌ 是 **`.txt`**，放在 `game/scene/` |
| 对话写 `say:角色:文本` | ❌ 对话是 **`角色名:文本;`**；`say:文本;` 是**旁白**（无 speaker） |
| 有 `webgal build` / `webgal serve` CLI | ❌ 不存在。npm `webgal` 是 0.0.0 占位包，`WebGAL-Server` 2022 年已 archived。<br>正确做法是**静态模板克隆 + 文件覆盖**，然后任意静态服务器托管 |

---

## 1. 语句结构

```
命令:内容 -参数=值 -布尔参数;  // 分号之后是行内注释
```

- **一行一条语句**，按 `\n` 切分。
- `;` **终结语句**，其后同行内容全部是注释。
- 空行安全（解析为 comment 类型，跳过）。

### ⚠️ 注释的坑

裸的 `// 注释` 行会被**当成对话渲染出来**。因为解析器先按 `;` 切，`//注释` 前面没有 `;`，
整行就成了语句内容。

```
;这是安全的注释          ← 以分号开头，前段为空 → 识别为注释
changeBg:bg.webp;  // 这也安全   ← 跟在分号之后
// 这行会显示在游戏里！   ← 错误
```

### 转义

`\:` `\,` `\.` `\;` 分别转义冒号、逗号、句点、分号。`choose` 内还需 `\|`。

```
WebGAL:我会显示出来：\:\,\.\;不信你看看;
```

`\.` 尤其重要——`choose` 的跳转目标若含 `.` 会被当成**场景文件名**而非 label。

---

## 2. 🔥 最关键的解析规则：未知命令静默降级

```ts
// commandParser.ts
function getCommandType(command) {
  return SCRIPT_CONFIG_MAP.get(command)?.scriptType ?? commandType.say;  // 默认 say
}
if (type === commandType.say && commandRaw !== 'say') {
  additionalArgs.push({ key: 'speaker', value: commandRaw });  // 命令名 → 角色名
}
```

**WebGAL 遇到不认识的命令不会报错，而是把它当成角色名，把参数当成台词渲染出来。**

| 输入 | 实际渲染 |
|---|---|
| `WebGAL:你好;` | 角色「WebGAL」说「你好」✅ |
| `say:你好;` | 旁白「你好」（无角色名）✅ |
| `:你好;` | 旁白「你好」✅ |
| `showCode:print(1);` | ❌ 角色「showCode」说「print(1)」——**LLM 幻觉命令的典型下场** |
| `say:小明:你好;` | ❌ 旁白显示字面文本「小明:你好」 |

> **这是 Repo2Gal 必须做 validator 的根本原因**：产物永远"能跑"，但会静默错渲染。
> 靠肉眼看游戏发现问题的成本极高，必须在生成后、打包前用白名单校验。

---

## 3. 命令全集（35 个，源自 `scriptConfig.ts`）

### 常用

| 命令 | 示例 | 说明 |
|---|---|---|
| `say` | `say:文本;` | 旁白。等价于 `:文本;` |
| *(角色名)* | `WebGAL:文本 -v1.wav -left;` | 对话。任何非命令词都作为 speaker |
| `changeBg` | `changeBg:bg.webp -next;` | 切背景 → `game/background/` |
| `changeFigure` | `changeFigure:stand.webp -left;` | 切立绘 → `game/figure/` |
| `bgm` | `bgm:s_Title.mp3 -volume=80 -enter=3000;` | BGM → `game/bgm/` |
| `playEffect` | `playEffect:se.mp3;` | 音效 → `game/vocal/` |
| `intro` | `intro:第一行\|第二行 -hold;` | 黑屏文字演出，`\|` 分行 |
| `changeScene` | `changeScene:next.txt;` | 切场景（不返回） |
| `callScene` | `callScene:sub.txt;` | 调用子场景（会返回） |
| `end` | `end;` | 结束游戏 |
| `miniAvatar` | `miniAvatar:avatar.webp;` | 小头像 |

### 流程控制

| 命令 | 示例 |
|---|---|
| `label` | `label:chapter2;` |
| `jumpLabel` | `jumpLabel:chapter2;` |
| `jumpLabel` + 条件 | `jumpLabel:high_score -when=varScore>1;` |
| `choose` | `choose:选项A:label_a\|选项B:label_b;` |
| `setVar` | `setVar:a=3;` / `setVar:a=a + 3;` |
| `setVar` + 条件 | `setVar:bg=x.webp -when=a>2;` |
| `if` | `if:条件;`（条件跳转，实际更常用 `jumpLabel -when=`） |
| `showVars` | 调试用，打印所有变量 |

### 演出 / 其他

`pixiInit` `pixiPerform` `playVideo` `setAnimation` `setTempAnimation` `setComplexAnimation`
`setFilter` `setTransform` `setTransition` `setTextbox` `filmMode` `applyStyle` `wait`
`unlockCg` `unlockBgm` `getUserInput` `chooseLabel` `callSteam`

---

## 4. choose 详解

```
choose:选项文本:跳转目标|选项文本:跳转目标 -defaultChoose=1;
```

跳转目标含 `.` → 视为场景文件；否则视为 label。

### 带条件的选项

```
choose:(varHasTicket==true)->可见路径:var_ticket_ok|[varDoorPower>1]->能量路径:var_power_path;
```

| 语法 | 含义 |
|---|---|
| `(条件)->选项:目标` | **显示条件**，不满足则选项不出现 |
| `[条件]->选项:目标` | **启用条件**，不满足则灰显不可选 |
| `-defaultChoose=N` | 快速预览时默认选第 N 项 |

---

## 5. 变量与富文本

```
setVar:speaker=WebGAL;
{speaker}:背景现在是 {bg}。;          ← {var} 插值
{speaker}:\{bg\} 不会插值。;          ← 转义花括号
```

### 富文本（`show_code_board` 的正解）

```
WebGAL:这是[彩色文本](style=color:#B5495B\;)，还支持[注](zhù)[音](yīn)。
WebGAL:[整段富文本](style-alltext=font-style:italic\; style=color:#66327C\;)
```

- `[文本](style=CSS)` — 局部样式，CSS 内的 `;` 要写成 `\;`
- `[文本](style-alltext=CSS)` — 作用于整条语句
- `[汉字](拼音)` — 注音

> 引擎原生支持富文本，配 `game/userStyleSheet.css` 可做等宽代码块。
> 早期 v2 文档里那套「三层降级策略」是在解决一个不存在的问题。

---

## 6. 目录结构与资源解析

```
game/
├── config.txt          # 游戏配置
├── scene/              # 场景脚本 *.txt   ← changeScene / callScene
├── background/         # 背景            ← changeBg / unlockCg
├── figure/             # 立绘            ← changeFigure / miniAvatar
├── bgm/                # 背景音乐        ← bgm / unlockBgm
├── vocal/              # 语音与音效      ← playEffect / 对话的 -v1.wav
├── video/              # 视频            ← playVideo
├── animation/          # 动画预设
├── template/           # UI 模板
├── userStyleSheet.css  # 自定义 CSS
└── flowchart.json
```

**脚本里只写文件名，不写路径**——引擎按命令类型自动补目录：

```
changeBg:bg.webp;        →  game/background/bg.webp     ✅
changeBg:assets/bg/x.jpg;→  game/background/assets/bg/x.jpg  ❌ 早期文档的错误写法
```

入口场景固定为 `game/scene/start.txt`。

### config.txt

```
Game_name:游戏标题;
Game_key:唯一存档键;
Title_img:标题背景图.webp;
Title_bgm:标题音乐.mp3;
Game_Logo:logo.webp;
Enable_Appreciation:true;
Enable_Continue:true;
Enable_flowchart:true;
```

---

## 7. 给 LLM 的最小安全子集

生成剧本时把模型限制在这几条内，配合 validator 白名单，出错面最小：

```
;=== 允许使用的全部语法 ===
changeBg:文件名.webp -next;
changeFigure:立绘文件名.webp -left;
bgm:文件名.mp3;
角色名:台词;
say:旁白;
intro:黑屏文字|第二行;
label:标签名;
jumpLabel:标签名;
choose:选项一:标签一|选项二:标签二;
end;
```

不在此列的一律由 validator 降级为旁白，绝不放行到产物里。

使用 Asset Pack 时，LLM 与 validator 阶段的三个资源参数是逻辑 ID（例如
`changeBg:background.archive;`），打包阶段再由 `webgal_assets.py` 改写成上述裸文件名。
未声明 ID 或素材类型错配会被 validator 注释降级，不会进入 WebGAL 产物。

动态演出使用 `--performance` 时，第二次 LLM 不直接生成本文件中的 WebGAL 命令，而是输出
`Performance Plan v1` 语义 JSON。`repo2gal/performance.py` 再根据固定的 WebGAL `4.6.2`
能力表生成 `setTransform`、`setTempAnimation`、
`pixiInit` 和 `pixiPerform`。模型不能提供坐标、关键帧、runtime target 或 `-next`、
`-parallel`、`-continue` 参数。设计和动作 Schema 见 `docs/dev/performance-plan-spec.md`。
`screen.transition` 是例外：编译器不在台词前追加独立动画，而是修改对应的背景命令，例如
`changeBg:bg.webp -enter=shockwaveIn -enterDuration=1200;`，保证切换和效果同时发生。

Asset Pack 角色声明 `framing.mode=upper-body` 时，WebGAL Adapter 会在最终脚本中确定性追加：

```text
changeFigure:character.png -transform={"position":{"x":-9,"y":326},"scale":{"x":1.538,"y":1.538}};
```

WebGAL 4.6.2 使用 2560×1440 Pixi 设计舞台；`position` 是相对默认槽位的设计坐标偏移，
`scale` 作用于已经按完整纹理 contain 适配后的立绘。正 `y` 向下移动，超出 1440 的腿部由
舞台裁切。不得用 `userStyleSheet.css` 尝试选择单个 Pixi sprite。
