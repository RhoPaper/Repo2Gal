"""打包与上下文构建的测试（不联网）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from repo2gal.fetcher import Contributor, RepoContext, Thread, parse_repo  # noqa: E402
from repo2gal.generator import build_cast, render_context  # noqa: E402
from repo2gal.packager import build_config, package  # noqa: E402


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


def test_render_context_truncates():
    ctx = make_ctx()
    ctx.readme_excerpt = "x" * 50000
    assert len(render_context(ctx, max_chars=1000)) < 1200


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


def test_package_overwrites_existing(tmp_path):
    template = tmp_path / "tpl"
    (template / "game" / "scene").mkdir(parents=True)
    (template / "index.html").write_text("<html></html>")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "stale.txt").write_text("旧产物")

    out = package("end;\n", out_dir, game_name="T", game_key="k", template=template)
    assert not (out / "stale.txt").exists()
