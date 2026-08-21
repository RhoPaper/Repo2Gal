"""CLI 薄层测试：参数映射、渲染与退出码矩阵（pipeline 用 fake 注入）。"""

import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import repo2gal.cli as cli  # noqa: E402
from repo2gal.errors import (  # noqa: E402
    FetchError,
    GenerationError,
    PackageError,
    UsageError,
    ValidationFailed,
)
from repo2gal.fetcher import RepoContext  # noqa: E402
from repo2gal.generator import Cast  # noqa: E402
from repo2gal.pipeline import RunArtifacts  # noqa: E402
from repo2gal.validator import Report  # noqa: E402


def _ctx():
    return RepoContext(
        owner="acme",
        name="widget",
        description="A widget",
        language="Rust",
        stars=1,
        created_at="2020-01-01",
    )


def _cast():
    return Cast(entries=[("widget", "项目化身")])


def _artifacts(*, report=None, output_dir=None, prompt="PROMPT", raw="say:x;\nend;\n", clean="say:x;\nend;\n"):
    return RunArtifacts(
        ctx=_ctx(), cast=_cast(), prompt=prompt, raw=raw, clean=clean,
        report=report, output_dir=output_dir,
    )


def test_cli_maps_options_into_run_options(monkeypatch, tmp_path):
    captured = {}

    def fake(options, **kwargs):
        captured["options"] = options
        return _artifacts(output_dir=tmp_path / "out")

    monkeypatch.setattr(cli, "run_pipeline", fake)
    script = tmp_path / "story.txt"
    script.write_text("end;\n", encoding="utf-8")
    output = tmp_path / "custom-out"
    backup = tmp_path / "custom-backup"
    asset_pack = tmp_path / "custom-assets"

    result = CliRunner().invoke(
        cli.main,
        [
            "acme/widget",
            "--reuse-backup",
            "--organization",
            "--threads", "7",
            "--timeout", "60",
            "--script", str(script),
            "--output", str(output),
            "--backup-dir", str(backup),
            "--model", "custom-model",
            "--base-url", "https://custom.example/v1",
            "--asset-pack", str(asset_pack),
            "--public-assets",
        ],
    )

    assert result.exit_code == 0, result.output
    options = captured["options"]
    assert options.owner == "acme" and options.repo == "widget"
    assert options.reuse_backup is True
    assert options.organization is True
    assert options.top_threads == 7
    assert options.llm_timeout == 60
    assert options.script == script
    assert options.output_dir == output
    assert options.backup_root == backup
    assert options.model == "custom-model"
    assert options.base_url == "https://custom.example/v1"
    assert options.asset_pack == asset_pack
    assert options.public_assets is True
    assert "✓ 完成" in result.output


def test_cli_default_paths(monkeypatch):
    captured = {}

    def fake(options, **kwargs):
        captured["options"] = options
        return _artifacts(report=Report())  # dry-run+script 形态

    monkeypatch.setattr(cli, "run_pipeline", fake)
    result = CliRunner().invoke(cli.main, ["acme/widget", "--dry-run", "--script", "s.txt"])
    assert result.exit_code == 0, result.output
    assert captured["options"].output_dir == Path("output") / "widget"
    assert captured["options"].backup_root == Path(".repo2gal") / "backups" / "acme"
    assert "dry-run 校验结束" in result.output


def test_cli_prints_prompt_for_plain_dry_run(monkeypatch):
    monkeypatch.setattr(cli, "run_pipeline", lambda options, **kw: _artifacts())
    result = CliRunner().invoke(cli.main, ["acme/widget", "--dry-run"])
    assert result.exit_code == 0
    assert "PROMPT" in result.output
    assert "dry-run 结束" in result.output


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (UsageError("用法错误"), 2),
        (FetchError("抓取失败"), 3),
        (GenerationError("生成失败"), 4),
        (ValidationFailed("校验失败"), 5),
        (PackageError("打包失败"), 6),
    ],
)
def test_cli_maps_error_to_exit_code(monkeypatch, error, code):
    def boom(options, **kwargs):
        raise error

    monkeypatch.setattr(cli, "run_pipeline", boom)
    result = CliRunner().invoke(cli.main, ["acme/widget"])
    assert result.exit_code == code
    assert str(error) in result.output


def test_cli_unknown_exception_exits_1(monkeypatch):
    def boom(options, **kwargs):
        raise RuntimeError("未预期")

    monkeypatch.setattr(cli, "run_pipeline", boom)
    result = CliRunner().invoke(cli.main, ["acme/widget"])
    assert result.exit_code == 1
    assert "内部错误" in result.output


def test_cli_invalid_repo_exits_2():
    result = CliRunner().invoke(cli.main, ["not a repo"])
    assert result.exit_code == 2
    assert "无法解析仓库标识" in result.output


def test_cli_missing_repo_argument_exits_2():
    result = CliRunner().invoke(cli.main, [])
    assert result.exit_code == 2


def test_assets_init_and_validate_commands(tmp_path):
    root = tmp_path / "new-pack"
    runner = CliRunner()
    initialized = runner.invoke(cli.main, ["assets", "init", str(root)])
    assert initialized.exit_code == 0, initialized.output
    assert (root / "repo2gal-pack.json").exists()

    validated = runner.invoke(cli.main, ["assets", "validate", str(root)])
    assert validated.exit_code == 0, validated.output
    assert "素材包校验通过" in validated.output

    public = runner.invoke(cli.main, ["assets", "validate", str(root), "--public"])
    assert public.exit_code == 2
    assert "公开发布模式" in public.output


def test_assets_validate_built_in_example_in_public_mode():
    result = CliRunner().invoke(
        cli.main, ["assets", "validate", "builtin:cc0-chronicle", "--public"]
    )
    assert result.exit_code == 0, result.output
    assert "CC0" not in result.output  # CLI 只报告校验结果，不复制或改写授权文本。
    assert "公开发布" in result.output
