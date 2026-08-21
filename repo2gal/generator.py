"""剧本生成的确定性部分：选角、上下文渲染与 prompt 组装。

分两步：
1. 选角（cast）—— 确定性代码完成，不交给 LLM。
   角色名一旦由 LLM 自由发挥，validator 就无法区分「幻觉命令」和「新角色」，
   所以角色表必须在生成之前就固定下来，并作为白名单传给 validator。
2. prompt 组装 —— 依据素材渲染上下文并套用模板；LLM 调用本身在 ``llm.py``。

本模块不做网络、不做打包；LLM 只负责叙事创作。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config import DEFAULT_BACKGROUNDS, DEFAULT_BGM
from .fetcher import RepoContext

PROMPT_DIR = Path(__file__).parent / "prompts"


@dataclass
class Cast:
    """出场角色表。由代码确定，不由 LLM 决定。"""

    entries: list[tuple[str, str]]  # (角色名, 人设说明)

    @property
    def names(self) -> set[str]:
        return {name for name, _ in self.entries}

    def render(self) -> str:
        return "\n".join(f"- {name}：{desc}" for name, desc in self.entries)


def _sanitize_name(login: str) -> str:
    """把 GitHub login 变成安全的角色名。

    角色名会出现在冒号左边，因此不能含 ':' ';' '-' 等解析器敏感字符。
    """
    name = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", login)
    return name or "Dev"


def build_cast(ctx: RepoContext) -> Cast:
    """从仓库数据推导角色表。

    三类角色：旁白者（项目本体拟人）、核心贡献者、技术栈精灵。
    """
    entries: list[tuple[str, str]] = []

    project = _sanitize_name(ctx.name)
    entries.append(
        (project, f"{ctx.full_name} 的项目化身，见证全部历史。{ctx.description or '沉稳的叙述者'}")
    )

    for c in ctx.contributors[:4]:
        name = _sanitize_name(c.login)
        if name in {n for n, _ in entries}:
            continue
        entries.append((name, f"社区参与者，在筛选后的叙事素材中出现 {c.contributions} 次"))

    lang = _sanitize_name(ctx.language)
    if lang and lang.lower() != "未知" and lang not in {n for n, _ in entries}:
        entries.append((lang, f"{ctx.language} 语言的拟人化身，代表这个项目的技术底色"))

    return Cast(entries=entries)


def render_context(ctx: RepoContext, *, max_chars: int = 14000) -> str:
    """把 RepoContext 渲染成给 LLM 读的文本。

    按价值排序后截断：讨论 > Release > README。讨论是 Chronicle 模式的核心素材。
    """
    parts: list[str] = [
        f"## 仓库：{ctx.full_name}",
        f"- 简介：{ctx.description or '（无）'}",
        f"- 主语言：{ctx.language}　创建于：{ctx.created_at or '未知'}",
    ]
    if ctx.stars:
        parts.append(f"- Star：{ctx.stars}")
    if ctx.topics:
        parts.append(f"- 主题标签：{', '.join(ctx.topics[:10])}")

    if ctx.contributors:
        who = "，".join(f"{c.login}（{c.contributions}）" for c in ctx.contributors[:6])
        parts.append(f"- 核心贡献者：{who}")

    if ctx.releases:
        parts.append("\n## 版本里程碑")
        for r in ctx.releases:
            line = f"- {r.tag}（{r.published_at}）{r.name}"
            if r.body:
                line += f"\n  {r.body[:200]}"
            parts.append(line)

    if ctx.threads:
        parts.append("\n## 社区讨论（按热度排序，剧情主要素材）")
        for t in ctx.threads:
            parts.append(
                f"\n### #{t.number} [{t.kind.upper()}/{t.state}] {t.title}"
                f"\n发起人：{t.author}　时间：{t.created_at}　评论数：{t.comment_count}"
            )
            if t.body:
                parts.append(f"正文：{t.body}")
            for c in t.comments:
                parts.append(f"  · {c.author}：{c.body}")

    if ctx.readme_excerpt:
        parts.append(f"\n## README 摘录\n{ctx.readme_excerpt}")

    if ctx.wiki_excerpt:
        parts.append(f"\n## Wiki 摘录\n{ctx.wiki_excerpt}")

    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n…（素材过长，已截断）"
    return text


def build_prompt(
    ctx: RepoContext,
    cast: Cast,
    *,
    backgrounds: list[str] | None = None,
    figures: list[str] | None = None,
    bgm: list[str] | None = None,
) -> str:
    template = (PROMPT_DIR / "chronicle.md").read_text(encoding="utf-8")
    background_names = DEFAULT_BACKGROUNDS if backgrounds is None else backgrounds
    bgm_names = DEFAULT_BGM if bgm is None else bgm
    return (
        template.replace("{characters}", cast.render())
        .replace("{backgrounds}", "、".join(background_names) or "（无）")
        .replace("{figures}", "、".join(figures or []) or "（无）")
        .replace("{bgm}", "、".join(bgm_names) or "（无）")
        .replace("{context}", render_context(ctx))
    )
