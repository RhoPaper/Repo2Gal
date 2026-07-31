"""GitHub 数据抓取（Chronicle 模式）。

**为何不用 gh2md**：gh2md 导出的是仓库全量 Issue/PR 的 Markdown，
而 Chronicle 模式只需要「评论最多的 Top N 条」——用 GitHub Search API 一次就能拿到，
不必导出上万条再回头解析 Markdown。少一个外部二进制依赖、少一层文本往返。
等将来要做全量归档时再引入 gh2md 不迟。

未提供 token 时走匿名请求（60 次/小时），够跑通一次；
设置 GITHUB_TOKEN 后升到 5000 次/小时。
"""

from __future__ import annotations

import dataclasses
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

import requests

API = "https://api.github.com"
_UA = "repo2gal"


class FetchError(RuntimeError):
    """抓取失败，且无法降级继续。"""


@dataclass
class Comment:
    author: str
    body: str


@dataclass
class Thread:
    """一条 Issue 或 PR，连同它的讨论。"""

    number: int
    title: str
    kind: str  # "issue" | "pr"
    state: str
    author: str
    created_at: str
    comment_count: int
    body: str
    comments: list[Comment] = field(default_factory=list)


@dataclass
class Release:
    tag: str
    name: str
    published_at: str
    body: str


@dataclass
class Contributor:
    login: str
    contributions: int


@dataclass
class RepoContext:
    """喂给 LLM 的结构化上下文。"""

    owner: str
    name: str
    description: str
    language: str
    stars: int
    created_at: str
    topics: list[str] = field(default_factory=list)
    readme_excerpt: str = ""
    contributors: list[Contributor] = field(default_factory=list)
    releases: list[Release] = field(default_factory=list)
    threads: list[Thread] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def parse_repo(url: str) -> tuple[str, str]:
    """从 URL 或 owner/repo 里解出 (owner, repo)。"""
    text = url.strip().removesuffix(".git")
    m = re.search(r"github\.com[/:]([^/]+)/([^/]+)", text)
    if m:
        return m.group(1), m.group(2)
    parts = text.split("/")
    if len(parts) == 2 and all(parts):
        return parts[0], parts[1]
    raise FetchError(f"无法解析仓库标识：{url!r}（期望 owner/repo 或 GitHub URL）")


class GitHubClient:
    def __init__(self, token: str | None = None, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        headers = {"Accept": "application/vnd.github+json", "User-Agent": _UA}
        token = token or os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.session.headers.update(headers)
        self.authenticated = bool(token)

    def get(self, path: str, **params: Any) -> Any:
        url = path if path.startswith("http") else f"{API}{path}"
        for attempt in range(3):
            resp = self.session.get(url, params=params or None, timeout=self.timeout)

            # 触发速率限制：等待重置或直接放弃
            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                reset = resp.headers.get("X-RateLimit-Reset")
                wait = max(0, int(reset) - int(time.time())) if reset else 60
                if wait > 90 or attempt == 2:
                    hint = "" if self.authenticated else "，建议设置 GITHUB_TOKEN 提高配额"
                    raise FetchError(f"GitHub 速率限制，需等待 {wait}s{hint}")
                time.sleep(wait + 1)
                continue

            if resp.status_code == 404:
                raise FetchError(f"资源不存在：{url}")
            if resp.status_code >= 500:
                time.sleep(2 * (attempt + 1))
                continue
            if not resp.ok:
                raise FetchError(f"GitHub 返回 {resp.status_code}：{resp.text[:200]}")
            return resp.json()
        raise FetchError(f"多次重试后仍失败：{url}")

    def get_optional(self, path: str, **params: Any) -> Any | None:
        """用于非关键数据：失败就返回 None，不中断整条流水线。"""
        try:
            return self.get(path, **params)
        except FetchError:
            return None


def _clean_body(text: str | None, limit: int) -> str:
    """压掉 Markdown 噪声，控制长度，省 token。"""
    if not text:
        return ""
    text = re.sub(r"```.*?```", "[代码块]", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)  # 裸 HTML 标签（README 里的徽章区常见）
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)  # 图片
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # 链接：保留文字，丢掉 URL
    text = re.sub(r"https?://\S+", "", text)  # 裸 URL
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text[:limit] + "…" if len(text) > limit else text


def fetch_context(
    owner: str,
    repo: str,
    *,
    client: GitHubClient | None = None,
    top_threads: int = 12,
    comments_per_thread: int = 8,
    log=lambda _msg: None,
) -> RepoContext:
    """抓取 Chronicle 模式所需的全部数据。

    仓库元信息缺失即失败；其余数据缺失只降级不中断。
    """
    gh = client or GitHubClient()

    log(f"抓取仓库元信息 {owner}/{repo}")
    meta = gh.get(f"/repos/{owner}/{repo}")

    ctx = RepoContext(
        owner=meta["owner"]["login"],
        name=meta["name"],
        description=meta.get("description") or "",
        language=meta.get("language") or "未知",
        stars=meta.get("stargazers_count", 0),
        created_at=(meta.get("created_at") or "")[:10],
        topics=meta.get("topics", []) or [],
    )

    # README：项目自述，人格化的主要依据
    readme = gh.get_optional(f"/repos/{owner}/{repo}/readme")
    if readme:
        import base64

        try:
            decoded = base64.b64decode(readme.get("content", "")).decode("utf-8", "replace")
            ctx.readme_excerpt = _clean_body(decoded, 2500)
            log("已获取 README")
        except Exception:
            log("README 解码失败，跳过")

    # 贡献者：编年史里的「人」
    contributors = gh.get_optional(f"/repos/{owner}/{repo}/contributors", per_page=10)
    if contributors:
        ctx.contributors = [
            Contributor(login=c["login"], contributions=c.get("contributions", 0))
            for c in contributors
            if c.get("type") == "User"
        ][:8]
        log(f"已获取 {len(ctx.contributors)} 位核心贡献者")

    # Release：天然的章节分界
    releases = gh.get_optional(f"/repos/{owner}/{repo}/releases", per_page=10)
    if releases:
        ctx.releases = [
            Release(
                tag=r.get("tag_name", ""),
                name=r.get("name") or r.get("tag_name", ""),
                published_at=(r.get("published_at") or "")[:10],
                body=_clean_body(r.get("body"), 400),
            )
            for r in releases
            if not r.get("draft")
        ][:6]
        log(f"已获取 {len(ctx.releases)} 个 Release")

    # 讨论热度最高的 Issue/PR —— Chronicle 模式的灵魂
    log("检索讨论最热烈的 Issue / PR")
    search = gh.get_optional(
        "/search/issues",
        q=f"repo:{owner}/{repo} sort:comments-desc",
        per_page=top_threads,
    )
    items = (search or {}).get("items", [])
    for item in items:
        is_pr = "pull_request" in item
        thread = Thread(
            number=item["number"],
            title=item["title"],
            kind="pr" if is_pr else "issue",
            state=item.get("state", ""),
            author=(item.get("user") or {}).get("login", "unknown"),
            created_at=(item.get("created_at") or "")[:10],
            comment_count=item.get("comments", 0),
            body=_clean_body(item.get("body"), 600),
        )
        if thread.comment_count and comments_per_thread:
            raw = gh.get_optional(
                f"/repos/{owner}/{repo}/issues/{thread.number}/comments",
                per_page=comments_per_thread,
            )
            for c in raw or []:
                body = _clean_body(c.get("body"), 400)
                if body:
                    thread.comments.append(
                        Comment(author=(c.get("user") or {}).get("login", "unknown"), body=body)
                    )
        ctx.threads.append(thread)

    log(f"已获取 {len(ctx.threads)} 条讨论线索")
    if not ctx.threads and not ctx.readme_excerpt:
        raise FetchError("仓库既无 README 也无讨论记录，素材不足以生成剧情")
    return ctx
