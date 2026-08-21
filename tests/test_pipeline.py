"""打包与上下文构建的测试（不联网）。"""

import hashlib
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import repo2gal.fetcher as fetcher  # noqa: E402
import repo2gal.packager as packager_module  # noqa: E402
import repo2gal.webgal_assets as webgal_assets_module  # noqa: E402
from repo2gal.errors import PackageError  # noqa: E402
from repo2gal.fetcher import (  # noqa: E402
    Contributor,
    RepoContext,
    Thread,
    context_from_backup,
    fetch_context,
    fetch_repository_metadata,
    parse_repo,
    run_backup,
)
from repo2gal.generator import build_cast, render_context  # noqa: E402
from repo2gal.packager import build_config, ensure_template, package  # noqa: E402


def make_ctx():
    return RepoContext(
        owner="acme",
        name="widget",
        description="A widget",
        language="Rust",
        stars=42,
        created_at="2020-01-01",
        contributors=[Contributor("alice", 100), Contributor("bob-x", 50)],
        threads=[
            Thread(
                number=1,
                title="内存泄漏",
                kind="issue",
                state="closed",
                author="alice",
                created_at="2021-05-05",
                comment_count=9,
                body="有泄漏",
            )
        ],
    )


# --- parse_repo ---

def test_parse_repo_variants():
    assert parse_repo("https://github.com/vuejs/core") == ("vuejs", "core")
    assert parse_repo("https://github.com/vuejs/core.git") == ("vuejs", "core")
    assert parse_repo("git@github.com:vuejs/core.git") == ("vuejs", "core")
    assert parse_repo("vuejs/core") == ("vuejs", "core")


# --- cast ---

def test_cast_includes_project_and_contributors():
    cast = build_cast(make_ctx())
    assert "widget" in cast.names
    assert "alice" in cast.names
    assert "Rust" in cast.names


def test_cast_names_have_no_parser_hostile_chars():
    """角色名出现在冒号左边，含 '-' ':' ';' 会被解析器切坏。"""
    cast = build_cast(make_ctx())
    for name in cast.names:
        assert not any(c in name for c in ":;-")


def test_cast_has_no_duplicates():
    ctx = make_ctx()
    ctx.contributors = [Contributor("widget", 10), Contributor("alice", 5)]
    cast = build_cast(ctx)
    assert len(cast.names) == len(cast.entries)


# --- context 渲染 ---

def test_render_context_includes_discussion():
    text = render_context(make_ctx())
    assert "内存泄漏" in text
    assert "acme/widget" in text


def test_render_context_includes_wiki():
    ctx = make_ctx()
    ctx.wiki_excerpt = "架构决策记录"
    assert "## Wiki 摘录" in render_context(ctx)


def test_render_context_truncates():
    ctx = make_ctx()
    ctx.readme_excerpt = "x" * 50000
    assert len(render_context(ctx, max_chars=1000)) < 1200


# --- python-github-backup 适配层 ---

def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_context_from_backup_reads_issue_pr_discussion_and_wiki(tmp_path):
    backup = tmp_path / "repositories" / "widget"
    source = backup / "repository"
    source.mkdir(parents=True)
    (source / "README.md").write_text("# Widget\n一个小组件", encoding="utf-8")
    (source / "main.py").write_text("print('hi')", encoding="utf-8")
    wiki = backup / "wiki"
    wiki.mkdir()
    (wiki / "Architecture.md").write_text("# 架构\n事件总线", encoding="utf-8")

    _write_json(
        backup / "issues" / "1.json",
        {
            "number": 1,
            "title": "内存泄漏",
            "state": "closed",
            "user": {"login": "alice"},
            "created_at": "2024-01-01T00:00:00Z",
            "comments": 1,
            "body": "发现泄漏",
            "comment_data": [{"user": {"login": "bob"}, "body": "可以复现"}],
        },
    )
    _write_json(
        backup / "pulls" / "2.json",
        {
            "number": 2,
            "title": "修复泄漏",
            "state": "closed",
            "user": {"login": "bob"},
            "created_at": "2024-01-02T00:00:00Z",
            "comments": 1,
            "review_comments": 1,
            "body": "释放资源",
            "comment_regular_data": [{"user": {"login": "alice"}, "body": "同意"}],
            "review_data": [{"user": {"login": "carol"}, "body": "请补测试"}],
        },
    )
    _write_json(
        backup / "discussions" / "3.json",
        {
            "number": 3,
            "title": "未来路线",
            "closed": False,
            "author": {"login": "carol"},
            "createdAt": "2024-01-03T00:00:00Z",
            "comment_count": 1,
            "body": "讨论插件系统",
            "comment_data": [
                {
                    "author": {"login": "alice"},
                    "body": "支持",
                    "reply_data": [{"author": {"login": "bob"}, "body": "先做接口"}],
                }
            ],
        },
    )
    _write_json(
        backup / "releases" / "v1.0.0.json",
        {
            "tag_name": "v1.0.0",
            "name": "First release",
            "published_at": "2024-02-01T00:00:00Z",
            "body": "首个版本",
            "draft": False,
        },
    )

    ctx = context_from_backup(
        "acme",
        "widget",
        backup,
        top_threads=10,
        metadata={
            "owner": {"login": "acme"},
            "name": "widget",
            "description": "Official description",
            "language": "Python",
            "stargazers_count": 123,
            "created_at": "2023-01-01T00:00:00Z",
            "topics": ["demo", "widget"],
        },
    )

    assert {thread.kind for thread in ctx.threads} == {"issue", "pr", "discussion"}
    assert any(thread.title == "未来路线" for thread in ctx.threads)
    assert "事件总线" in ctx.wiki_excerpt
    assert ctx.language == "Python"
    assert ctx.stars == 123
    assert ctx.topics == ["demo", "widget"]
    assert ctx.description == "Official description"
    assert ctx.releases[0].tag == "v1.0.0"
    assert {person.login for person in ctx.contributors} >= {"alice", "bob", "carol"}


def test_context_reads_fetched_remote_ref_not_stale_worktree(tmp_path):
    """上游更新 clone 时只 fetch；Context Builder 必须从 origin/HEAD 读最新内容。"""
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    backup = tmp_path / "repositories" / "widget"
    clone = backup / "repository"

    def git(*args, cwd=None):
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)

    git("init", "--bare", str(origin))
    git("init", str(work))
    git("config", "user.email", "test@example.com", cwd=work)
    git("config", "user.name", "Test", cwd=work)
    (work / "README.md").write_text("# Old title", encoding="utf-8")
    git("add", "README.md", cwd=work)
    git("commit", "-m", "initial", cwd=work)
    git("branch", "-M", "main", cwd=work)
    git("remote", "add", "origin", str(origin), cwd=work)
    git("push", "-u", "origin", "main", cwd=work)
    git("symbolic-ref", "HEAD", "refs/heads/main", cwd=origin)
    clone.parent.mkdir(parents=True)
    git("clone", str(origin), str(clone))

    (work / "README.md").write_text("# New title", encoding="utf-8")
    git("add", "README.md", cwd=work)
    git("commit", "-m", "update", cwd=work)
    git("push", cwd=work)
    git("fetch", "--all", cwd=clone)

    assert "Old title" in (clone / "README.md").read_text(encoding="utf-8")
    ctx = context_from_backup("acme", "widget", backup)
    assert "New title" in ctx.readme_excerpt


def test_run_backup_delegates_all_github_work_to_upstream(tmp_path, monkeypatch):
    captured = {}
    progress = []
    expected = tmp_path / "repositories" / "widget"
    expected.mkdir(parents=True)

    monkeypatch.setattr(fetcher.shutil, "which", lambda _name: "/usr/bin/github-backup")

    class FakeProcess:
        stdout = io.StringIO("Retrieving issues\nSaving discussions\n")

        def wait(self):
            return 0

    def fake_popen(command, **kwargs):
        captured["command"] = command
        return FakeProcess()

    monkeypatch.setattr(fetcher.subprocess, "Popen", fake_popen)
    result = run_backup(
        "acme",
        "widget",
        tmp_path,
        token="ghp_test",
        incremental=False,
        progress=progress.append,
    )

    command = captured["command"]
    assert result == expected
    assert "--issues" in command
    assert "--pulls" in command
    assert "--discussions" in command
    assert "--wikis" in command
    assert "--repositories" in command
    assert "--all" not in command  # 避免隐式下载大型 Release assets / hooks
    assert progress == ["Retrieving issues", "Saving discussions"]
    assert "ghp_test" not in " ".join(command)


def test_repository_metadata_uses_only_official_rest_api(monkeypatch):
    captured = {}

    class Response:
        ok = True
        status_code = 200

        def json(self):
            return {"name": "widget", "stargazers_count": 42}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return Response()

    monkeypatch.setattr(fetcher.requests, "get", fake_get)
    data = fetch_repository_metadata("acme", "widget", "secret-token")

    assert captured["url"] == "https://api.github.com/repos/acme/widget"
    assert "github.com/acme/widget" not in captured["url"]
    assert captured["kwargs"]["headers"]["X-GitHub-Api-Version"] == "2022-11-28"
    assert data["stargazers_count"] == 42


def test_fetch_context_persists_rest_metadata_for_offline_reuse(tmp_path, monkeypatch):
    backup = tmp_path / "repositories" / "widget"
    source = backup / "repository"
    source.mkdir(parents=True)
    (source / "README.md").write_text("# Widget", encoding="utf-8")
    metadata = {
        "owner": {"login": "acme"},
        "name": "widget",
        "description": "Persisted description",
        "stargazers_count": 99,
        "topics": ["saved"],
    }

    monkeypatch.setattr(fetcher, "fetch_repository_metadata", lambda *args, **kwargs: metadata)
    monkeypatch.setattr(fetcher, "run_backup", lambda *args, **kwargs: backup)
    online = fetch_context("acme", "widget", backup_root=tmp_path, token="token")

    saved = json.loads((backup / "repo2gal-repository.json").read_text(encoding="utf-8"))
    assert saved == metadata
    assert online.stars == 99

    monkeypatch.setattr(
        fetcher,
        "fetch_repository_metadata",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("offline mode used network")),
    )
    offline = fetch_context("acme", "widget", backup_root=tmp_path, reuse_backup=True)
    assert offline.stars == 99
    assert offline.topics == ["saved"]


# --- config ---

def test_config_escapes_semicolon():
    """游戏名里的分号不转义会把 config.txt 切坏。"""
    cfg = build_config(game_name="a;b", game_key="k")
    assert "a\\;b" in cfg


def test_config_has_required_keys():
    cfg = build_config(game_name="n", game_key="k")
    for key in ("Game_name", "Game_key", "Title_img"):
        assert key in cfg


# --- 打包 ---

def test_webgal_download_reports_progress_and_checks_hash(tmp_path, monkeypatch):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("index.html", "<html></html>")
        zf.writestr("game/scene/start.txt", "end;")
    payload = archive.getvalue()

    class Response:
        ok = True
        status_code = 200
        headers = {"Content-Length": str(len(payload))}

        def iter_content(self, chunk_size):
            midpoint = len(payload) // 2
            yield payload[:midpoint]
            yield payload[midpoint:]

    monkeypatch.setattr(packager_module, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(packager_module.requests, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(packager_module, "WEBGAL_SHA256", hashlib.sha256(payload).hexdigest())
    logs = []

    template = ensure_template(log=logs.append)

    assert (template / "index.html").exists()
    assert any("下载进度" in line for line in logs)
    assert any("100%" in line for line in logs)

def test_package_injects_script(tmp_path):
    template = tmp_path / "tpl"
    (template / "game" / "scene").mkdir(parents=True)
    (template / "index.html").write_text("<html></html>")
    (template / "game" / "scene" / "demo_zh_cn.txt").write_text("demo")
    (template / "game" / "scene" / "function_test.txt").write_text("demo")

    out = package(
        "say:hi;\nend;\n",
        tmp_path / "out",
        game_name="Test",
        game_key="k",
        template=template,
    )

    assert (out / "index.html").exists()
    assert (out / "game" / "scene" / "start.txt").read_text() == "say:hi;\nend;\n"
    # 官方 demo 场景不能混进产物
    assert not (out / "game" / "scene" / "demo_zh_cn.txt").exists()
    assert not (out / "game" / "scene" / "function_test.txt").exists()
    assert "MPL-2.0" in (out / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert (out / "third_party" / "WebGAL" / "LICENSE").exists()


def test_default_package_notices_do_not_require_openat(tmp_path, monkeypatch):
    template = tmp_path / "tpl"
    (template / "game" / "scene").mkdir(parents=True)
    (template / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(webgal_assets_module.os, "supports_dir_fd", set())

    out = package("end;\n", tmp_path / "out", game_name="Test", game_key="k", template=template)

    assert (out / "THIRD_PARTY_NOTICES.md").exists()
    assert (out / "third_party" / "WebGAL" / "LICENSE").exists()


def test_package_overwrites_existing(tmp_path):
    template = tmp_path / "tpl"
    (template / "game" / "scene").mkdir(parents=True)
    (template / "index.html").write_text("<html></html>")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "stale.txt").write_text("旧产物")

    out = package("end;\n", out_dir, game_name="T", game_key="k", template=template)
    assert not (out / "stale.txt").exists()


# --- 原子替换与流程图（v0.3.0 重构新增行为） ---

def test_package_writes_minimal_flowchart(tmp_path):
    """模板 flowchart 引用 demo 场景，必须被替换为只含 start.txt 的最小版本。"""
    import json as json_module

    template = tmp_path / "tpl"
    (template / "game" / "scene").mkdir(parents=True)
    (template / "index.html").write_text("<html></html>")
    (template / "game" / "flowchart.json").write_text(
        json_module.dumps(
            {
                "flowcharts": [
                    {
                        "id": "main",
                        "name": "demo",
                        "type": "main",
                        "nodes": [
                            {
                                "id": "x",
                                "type": "chapter",
                                "position": {"x": 0, "y": 0},
                                "data": {"label": "演示", "sceneName": "demo_zh_cn.txt"},
                            }
                        ],
                        "edges": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    out = package("end;\n", tmp_path / "out", game_name="Test", game_key="k", template=template)
    flowchart = json_module.loads((out / "game" / "flowchart.json").read_text(encoding="utf-8"))

    scenes = {
        node["data"]["sceneName"]
        for chart in flowchart["flowcharts"]
        for node in chart["nodes"]
    }
    assert scenes == {"start.txt"}  # 不再引用任何已删除的 demo 场景
    assert (out / "game" / "scene" / "start.txt").exists()


def test_package_failure_keeps_old_output(tmp_path, monkeypatch):
    """staging 阶段失败时，旧产物必须原样保留。"""
    template = tmp_path / "tpl"
    (template / "game" / "scene").mkdir(parents=True)
    (template / "index.html").write_text("<html></html>")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "precious.txt").write_text("旧产物")

    import repo2gal.packager as packager_module

    def broken_copytree(*args, **kwargs):
        raise OSError("disk exploded")

    monkeypatch.setattr(packager_module.shutil, "copytree", broken_copytree)
    with pytest.raises(packager_module.PackageError):
        package("end;\n", out_dir, game_name="T", game_key="k", template=template)

    assert (out_dir / "precious.txt").read_text(encoding="utf-8") == "旧产物"


def test_package_rejects_symlink_output(tmp_path):
    template = tmp_path / "tpl"
    (template / "game" / "scene").mkdir(parents=True)
    (template / "index.html").write_text("<html></html>")

    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "out"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(packager_module.PackageError):
        package("end;\n", link, game_name="T", game_key="k", template=template)


def test_ensure_template_network_failure_wraps_package_error(tmp_path, monkeypatch):
    import requests

    monkeypatch.setattr(packager_module, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(
        packager_module.requests, "get", lambda *a, **kw: (_ for _ in ()).throw(requests.ConnectionError("offline"))
    )
    with pytest.raises(packager_module.PackageError):
        ensure_template()


def test_ensure_template_http_failure_wraps_package_error(tmp_path, monkeypatch):
    class Response:
        ok = False
        status_code = 404

    monkeypatch.setattr(packager_module, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(packager_module.requests, "get", lambda *a, **kw: Response())
    with pytest.raises(packager_module.PackageError):
        ensure_template()


def test_ensure_template_hash_mismatch_wraps_package_error(tmp_path, monkeypatch):
    import io as io_module
    import zipfile as zipfile_module

    archive = io_module.BytesIO()
    with zipfile_module.ZipFile(archive, "w") as zf:
        zf.writestr("index.html", "<html></html>")
    payload = archive.getvalue()

    class Response:
        ok = True
        status_code = 200
        headers = {"Content-Length": str(len(payload))}

        def iter_content(self, chunk_size):
            yield payload

    monkeypatch.setattr(packager_module, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(packager_module.requests, "get", lambda *a, **kw: Response())
    monkeypatch.setattr(packager_module, "WEBGAL_SHA256", "0" * 64)
    with pytest.raises(packager_module.PackageError) as exc:
        ensure_template()
    assert "SHA-256" in str(exc.value)
