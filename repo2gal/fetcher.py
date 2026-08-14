"""GitHub 采集适配层（Chronicle 模式）。

GitHub 的认证、分页、限流、重试、GraphQL、Discussion、wiki 与增量备份
全部委托给成熟项目 ``josegonzalez/python-github-backup``。本模块只做两件事：

1. 以 subprocess 调用 ``github-backup``；
2. 把其落盘的 Git 仓库和 JSON 归一化成 RepoContext。

项目明确禁止在已有成熟开源实现时自造 GitHub API 客户端。
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import requests

from .errors import FetchError, UsageError


GITHUB_REST_API = "https://api.github.com"


@dataclass
class Comment:
    author: str
    body: str


@dataclass
class Thread:
    """一条 Issue、PR 或 Discussion，连同它的讨论。"""

    number: int
    title: str
    kind: str  # "issue" | "pr" | "discussion"
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
    wiki_excerpt: str = ""
    contributors: list[Contributor] = field(default_factory=list)
    releases: list[Release] = field(default_factory=list)
    threads: list[Thread] = field(default_factory=list)
    backup_dir: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def parse_repo(url: str) -> tuple[str, str]:
    """从 URL 或 owner/repo 里解出 (owner, repo)。"""
    text = url.strip().removesuffix(".git")
    match = re.search(r"github\.com[/:]([^/]+)/([^/]+)", text)
    if match:
        return match.group(1), match.group(2)
    parts = text.split("/")
    if len(parts) == 2 and all(parts):
        return parts[0], parts[1]
    raise UsageError(f"无法解析仓库标识：{url!r}（期望 owner/repo 或 GitHub URL）")


# 不使用 --all：上游的 --all 会额外下载 Release 二进制并读取 hooks，可能需要
# 高权限 token，也可能意外拉取数十 GB。这里显式列出生成叙事真正需要的全量数据。
NARRATIVE_BACKUP_FLAGS = (
    "--repositories",
    "--issues",
    "--issue-comments",
    "--issue-events",
    "--issue-timeline",
    "--pulls",
    "--pull-comments",
    "--pull-reviews",
    "--pull-commits",
    "--pull-details",
    "--discussions",
    "--wikis",
    "--releases",
    "--labels",
    "--milestones",
    "--fork",
)


def run_backup(
    owner: str,
    repo: str,
    backup_root: Path,
    *,
    token: str | None = None,
    organization: bool = False,
    incremental: bool = True,
    log=lambda _msg: None,
    progress=lambda _msg: None,
) -> Path:
    """调用 python-github-backup，返回该仓库的备份目录。

    Token 通过权限为 0600 的临时文件传递，避免出现在进程列表或 shell history。
    Discussion 使用 GraphQL，完整采集必须有 token，因此本适配层直接要求认证。
    """
    if not token:
        raise FetchError(
            "python-github-backup 需要 GitHub Token；请设置 GITHUB_TOKEN，"
            "或用 --reuse-backup 读取已有备份"
        )

    sibling = Path(sys.executable).with_name("github-backup")
    executable = str(sibling) if sibling.is_file() else shutil.which("github-backup")
    if not executable:
        raise FetchError("找不到 github-backup，请执行 pip install github-backup")

    backup_root = Path(backup_root).resolve()
    repo_dir = backup_root / "repositories" / repo
    backup_root.mkdir(parents=True, exist_ok=True)

    command = [
        executable,
        owner,
        "--output-directory",
        str(backup_root),
        "--repository",
        repo,
        *NARRATIVE_BACKUP_FLAGS,
    ]
    if organization:
        command.append("--organization")
    command.append("--private")
    if incremental and repo_dir.exists():
        command.append("--incremental")

    token_file: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
            handle.write(token)
            token_file = handle.name
        os.chmod(token_file, 0o600)
        option = "--token-fine" if token.startswith("github_pat_") else "--token"
        command.extend((option, Path(token_file).as_uri()))

        log(f"调用 python-github-backup 采集 {owner}/{repo}")
        process = subprocess.Popen(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
        output: list[str] = []
        if process.stdout:
            for raw_line in process.stdout:
                line = raw_line.strip()
                if line:
                    output.append(line)
                    progress(line)
        returncode = process.wait()
        if returncode:
            message = output[-1] if output else "无错误详情"
            raise FetchError(f"github-backup 退出码 {returncode}：{message}")
    finally:
        if token_file:
            Path(token_file).unlink(missing_ok=True)

    if not repo_dir.exists():
        raise FetchError(f"github-backup 未产出预期目录：{repo_dir}")
    log(f"原始备份已保存：{repo_dir}")
    return repo_dir


def fetch_repository_metadata(
    owner: str,
    repo: str,
    token: str,
    *,
    log=lambda _msg: None,
) -> dict[str, Any]:
    """通过官方 GitHub REST API 补齐上游不落盘的仓库概览。

    这是仓库数据采集模块唯一允许的直接网络补充。URL 固定为
    ``api.github.com/repos/{owner}/{repo}``；不得改成抓取 GitHub HTML 页面。
    失败时保留 github-backup 主流程，不把非关键元数据升级为致命错误。
    """
    log("通过官方 GitHub REST API 获取仓库概览")
    try:
        response = requests.get(
            f"{GITHUB_REST_API}/repos/{owner}/{repo}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "Repo2Gal",
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        log(f"仓库概览获取失败（{exc}），继续使用备份数据")
        return {}
    if not response.ok:
        log(f"仓库概览获取失败（HTTP {response.status_code}），继续使用备份数据")
        return {}
    try:
        data = response.json()
    except ValueError:
        log("仓库概览响应不是合法 JSON，继续使用备份数据")
        return {}
    return data if isinstance(data, dict) else {}


def _metadata_path(repo_backup_dir: Path) -> Path:
    return repo_backup_dir / "repo2gal-repository.json"


def _read_metadata(repo_backup_dir: Path) -> dict[str, Any]:
    path = _metadata_path(repo_backup_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _clean_body(text: str | None, limit: int) -> str:
    """压掉 Markdown 噪声并限制单段长度。"""
    if not text:
        return ""
    text = re.sub(r"```.*?```", "[代码块]", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:limit] + "…" if len(text) > limit else text


def _load_json_files(directory: Path) -> Iterable[dict[str, Any]]:
    if not directory.is_dir():
        return []
    values: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            values.append(data)
    return values


def _login(actor: Any) -> str:
    if isinstance(actor, dict):
        return actor.get("login") or actor.get("name") or "unknown"
    return "unknown"


def _comments(items: Iterable[dict[str, Any]], limit: int = 20) -> list[Comment]:
    result: list[Comment] = []
    for item in items:
        body = _clean_body(item.get("body") or item.get("bodyText"), 500)
        if body:
            result.append(Comment(author=_login(item.get("user") or item.get("author")), body=body))
        for reply in item.get("reply_data") or []:
            reply_body = _clean_body(reply.get("body") or reply.get("bodyText"), 500)
            if reply_body:
                result.append(Comment(author=_login(reply.get("author")), body=reply_body))
        if len(result) >= limit:
            break
    return result[:limit]


def _thread_from_issue(data: dict[str, Any]) -> Thread:
    comments = _comments(data.get("comment_data") or [])
    return Thread(
        number=data.get("number", 0),
        title=data.get("title") or "（无标题）",
        kind="issue",
        state=data.get("state") or "unknown",
        author=_login(data.get("user")),
        created_at=(data.get("created_at") or "")[:10],
        comment_count=max(data.get("comments", 0), len(comments)),
        body=_clean_body(data.get("body"), 800),
        comments=comments,
    )


def _thread_from_pull(data: dict[str, Any]) -> Thread:
    raw_comments = [
        *(data.get("comment_regular_data") or []),
        *(data.get("comment_data") or []),
        *(data.get("review_data") or []),
    ]
    comments = _comments(raw_comments)
    count = data.get("comments", 0) + data.get("review_comments", 0)
    return Thread(
        number=data.get("number", 0),
        title=data.get("title") or "（无标题）",
        kind="pr",
        state=data.get("state") or "unknown",
        author=_login(data.get("user")),
        created_at=(data.get("created_at") or "")[:10],
        comment_count=max(count, len(comments)),
        body=_clean_body(data.get("body"), 800),
        comments=comments,
    )


def _thread_from_discussion(data: dict[str, Any]) -> Thread:
    comments = _comments(data.get("comment_data") or [])
    return Thread(
        number=data.get("number", 0),
        title=data.get("title") or "（无标题）",
        kind="discussion",
        state="closed" if data.get("closed") else "open",
        author=_login(data.get("author")),
        created_at=(data.get("createdAt") or "")[:10],
        comment_count=max(data.get("comment_count", 0), len(comments)),
        body=_clean_body(data.get("body") or data.get("bodyText"), 800),
        comments=comments,
    )


def _read_text_candidates(directory: Path, names: tuple[str, ...], limit: int) -> str:
    if not directory.is_dir():
        return ""
    lower_names = {name.lower() for name in names}
    reference, files = _git_files(directory)
    for name in files:
        if "/" not in name and name.lower() in lower_names:
            text = _git_output(directory, "show", f"{reference}:{name}")
            if text:
                return _clean_body(text, limit)
    for path in directory.iterdir():
        if path.is_file() and path.name.lower() in lower_names:
            try:
                return _clean_body(path.read_text(encoding="utf-8"), limit)
            except (OSError, UnicodeDecodeError):
                pass
    return ""


def _read_wiki(directory: Path, limit: int = 3000) -> str:
    if not directory.is_dir():
        return ""
    chunks: list[str] = []
    reference, git_paths = _git_files(directory)
    paths = git_paths or [
        str(path.relative_to(directory))
        for path in sorted(directory.rglob("*.md"))
        if ".git" not in path.parts
    ]
    for relative in paths:
        if not relative.lower().endswith(".md"):
            continue
        if reference:
            raw = _git_output(directory, "show", f"{reference}:{relative}")
        else:
            try:
                raw = (directory / relative).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
        text = _clean_body(raw, 1000)
        if text:
            chunks.append(f"### {Path(relative).stem}\n{text}")
        if sum(map(len, chunks)) >= limit:
            break
    return _clean_body("\n\n".join(chunks), limit)


def _git_output(repo_dir: Path, *args: str) -> str:
    if not (repo_dir / ".git").exists():
        return ""
    result = subprocess.run(
        ["git", "-C", str(repo_dir), *args], text=True, capture_output=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_files(repo_dir: Path) -> tuple[str, list[str]]:
    """返回最新远端引用及其文件列表，避免读取增量备份中的陈旧工作树。"""
    if not (repo_dir / ".git").exists():
        return "", []
    reference = _git_output(
        repo_dir, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"
    )
    if not reference:
        remotes = _git_output(
            repo_dir, "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin"
        ).splitlines()
        reference = next(
            (item for preferred in ("origin/main", "origin/master") for item in remotes if item == preferred),
            remotes[0] if remotes else "HEAD",
        )
    files = _git_output(repo_dir, "ls-tree", "-r", "--name-only", reference).splitlines()
    return reference, files


def _detect_language(repo_dir: Path) -> str:
    _, git_paths = _git_files(repo_dir)
    if git_paths:
        extensions = Counter(Path(path).suffix.lower() for path in git_paths)
    else:
        extensions = Counter(
            path.suffix.lower()
            for path in repo_dir.rglob("*")
            if path.is_file() and ".git" not in path.parts
        )
    mapping = {
        ".py": "Python",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".js": "JavaScript",
        ".jsx": "JavaScript",
        ".rs": "Rust",
        ".go": "Go",
        ".java": "Java",
        ".kt": "Kotlin",
        ".cpp": "C++",
        ".c": "C",
        ".rb": "Ruby",
        ".php": "PHP",
    }
    known: Counter[str] = Counter()
    for extension, count in extensions.items():
        if extension in mapping:
            known[mapping[extension]] += count
    return known.most_common(1)[0][0] if known else "未知"


def context_from_backup(
    owner: str,
    repo: str,
    repo_backup_dir: Path,
    *,
    metadata: dict[str, Any] | None = None,
    top_threads: int = 12,
    log=lambda _msg: None,
) -> RepoContext:
    """把 python-github-backup 的落盘结果归一化成 RepoContext。"""
    repo_backup_dir = Path(repo_backup_dir)
    source_dir = repo_backup_dir / "repository"
    metadata = metadata if metadata is not None else _read_metadata(repo_backup_dir)

    threads = [
        *(_thread_from_issue(item) for item in _load_json_files(repo_backup_dir / "issues")),
        *(_thread_from_pull(item) for item in _load_json_files(repo_backup_dir / "pulls")),
        *(
            _thread_from_discussion(item)
            for item in _load_json_files(repo_backup_dir / "discussions")
        ),
    ]
    threads.sort(key=lambda item: (item.comment_count, item.created_at), reverse=True)
    threads = threads[:top_threads]

    activity: Counter[str] = Counter()
    for thread in threads:
        if thread.author != "unknown":
            activity[thread.author] += 1
        activity.update(comment.author for comment in thread.comments if comment.author != "unknown")

    releases = [
        Release(
            tag=item.get("tag_name") or "",
            name=item.get("name") or item.get("tag_name") or "",
            published_at=(item.get("published_at") or item.get("created_at") or "")[:10],
            body=_clean_body(item.get("body"), 500),
        )
        for item in _load_json_files(repo_backup_dir / "releases")
        if not item.get("draft")
    ]
    releases.sort(key=lambda item: item.published_at, reverse=True)

    readme = _read_text_candidates(
        source_dir, ("README.md", "README.rst", "README.txt", "README"), 3000
    )
    readme_description = next(
        (line.lstrip("#= ") for line in readme.splitlines() if line.strip()), ""
    )
    reference, _ = _git_files(source_dir)
    roots = _git_output(
        source_dir, "rev-list", "--max-parents=0", reference or "HEAD"
    ).splitlines()
    first_commit = _git_output(source_dir, "show", "-s", "--format=%cs", roots[0]) if roots else ""

    context = RepoContext(
        owner=(metadata.get("owner") or {}).get("login") or owner,
        name=metadata.get("name") or repo,
        description=metadata.get("description") or readme_description,
        language=metadata.get("language") or _detect_language(source_dir),
        stars=metadata.get("stargazers_count") or 0,
        created_at=(metadata.get("created_at") or first_commit)[:10],
        topics=metadata.get("topics") or [],
        readme_excerpt=readme,
        wiki_excerpt=_read_wiki(repo_backup_dir / "wiki"),
        contributors=[Contributor(login=name, contributions=count) for name, count in activity.most_common(8)],
        releases=releases[:10],
        threads=threads,
        backup_dir=str(repo_backup_dir),
    )
    log(
        f"上下文：{len(context.threads)} 条热门讨论（含 Discussion），"
        f"{len(context.releases)} 个 Release，wiki={'有' if context.wiki_excerpt else '无'}"
    )
    if not context.threads and not context.readme_excerpt and not context.wiki_excerpt:
        raise FetchError("备份中没有 README、wiki 或社区讨论，素材不足以生成剧情")
    return context


def fetch_context(
    owner: str,
    repo: str,
    *,
    backup_root: Path,
    token: str | None = None,
    organization: bool = False,
    top_threads: int = 12,
    reuse_backup: bool = False,
    log=lambda _msg: None,
    progress=lambda _msg: None,
) -> RepoContext:
    """执行备份（或复用已有备份）并构建上下文。"""
    if not reuse_backup and not token:
        raise FetchError(
            "python-github-backup 需要 GitHub Token；请设置 GITHUB_TOKEN，"
            "或用 --reuse-backup 读取已有备份"
        )
    expected = Path(backup_root).resolve() / "repositories" / repo
    if reuse_backup:
        if not expected.exists():
            raise FetchError(f"--reuse-backup 指定的备份不存在：{expected}")
        repo_dir = expected
        log(f"复用原始备份：{repo_dir}")
        metadata = _read_metadata(repo_dir)
    else:
        metadata = fetch_repository_metadata(owner, repo, token or "", log=log)
        repo_dir = run_backup(
            owner,
            repo,
            Path(backup_root),
            token=token,
            organization=organization,
            log=log,
            progress=progress,
        )
        if metadata:
            _metadata_path(repo_dir).write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
    return context_from_backup(
        owner,
        repo,
        repo_dir,
        metadata=metadata,
        top_threads=top_threads,
        log=log,
    )
