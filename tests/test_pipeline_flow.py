"""流程编排（pipeline）四模式端到端离线测试。

注入 fake 的 fetch / LLM / package，覆盖模式矩阵：
dry-run x script 的四种组合，以及 strict、save-prompt、脚本路径错误。
"""

from pathlib import Path

import pytest

from repo2gal.errors import AssetPackError, UsageError, ValidationFailed
from repo2gal.fetcher import Contributor, RepoContext
from repo2gal.generator import Cast
from repo2gal.pipeline import RunOptions, run_pipeline

SCRIPT = "say:这是现成剧本。\nend;\n"
LLM_TEXT = "say:LLM 生成的剧本。\nend;\n"
EXAMPLE_PACK = "builtin:cc0-chronicle"


def make_ctx():
    return RepoContext(
        owner="acme",
        name="widget",
        description="A widget",
        language="Rust",
        stars=42,
        created_at="2020-01-01",
        contributors=[Contributor("alice", 100)],
    )


def make_options(tmp_path, **overrides):
    defaults = dict(
        owner="acme",
        repo="widget",
        output_dir=tmp_path / "out",
        backup_root=tmp_path / "backup",
        reuse_backup=True,
        token=None,
        api_key=None,
    )
    defaults.update(overrides)
    return RunOptions(**defaults)


def fake_fetch(options, log, progress):
    log("fake fetch")
    return make_ctx()


class FakeLLM:
    def __init__(self, text=LLM_TEXT):
        self.text = text
        self.calls = []

    def complete(self, prompt, *, temperature=0.8):
        self.calls.append(prompt)
        return self.text


def run(tmp_path, *, options=None, llm=None, package_fn=None, **kwargs):
    options = options or make_options(tmp_path)
    return run_pipeline(
        options,
        llm_client=llm,
        fetch_fn=fake_fetch,
        package_fn=package_fn,
        **kwargs,
    )


# --- 模式矩阵 ---

def test_full_llm_mode_runs_all_stages(tmp_path):
    llm = FakeLLM()
    packaged = {}

    def package_fn(clean, output_dir, **kwargs):
        packaged["clean"] = clean
        return output_dir

    artifacts = run(tmp_path, llm=llm, package_fn=package_fn)

    assert llm.calls  # 调用过 LLM
    assert artifacts.prompt == llm.calls[0]
    assert artifacts.raw == LLM_TEXT
    assert artifacts.clean.endswith("end;\n")
    assert artifacts.report is not None
    assert artifacts.output_dir == tmp_path / "out"
    assert packaged["clean"] == artifacts.clean  # 打包收到的是校验后的脚本


def test_full_script_mode_skips_llm(tmp_path):
    script = tmp_path / "story.txt"
    script.write_text(SCRIPT, encoding="utf-8")
    llm = FakeLLM()
    options = make_options(tmp_path, script=script)
    called = []

    def fake_package(clean, output_dir, **kwargs):
        called.append(1)
        return output_dir

    artifacts = run(tmp_path, options=options, llm=llm, package_fn=fake_package)

    assert not llm.calls
    assert artifacts.raw == SCRIPT
    assert artifacts.output_dir == tmp_path / "out"
    assert called


def test_dry_run_without_script_stops_before_llm(tmp_path):
    llm = FakeLLM()
    options = make_options(tmp_path, dry_run=True)
    artifacts = run(tmp_path, options=options, llm=llm)

    assert not llm.calls
    assert artifacts.prompt
    assert artifacts.raw == "" and artifacts.clean == ""
    assert artifacts.report is None
    assert artifacts.output_dir is None


def test_dry_run_with_script_validates_without_packaging(tmp_path):
    script = tmp_path / "story.txt"
    script.write_text(SCRIPT, encoding="utf-8")
    options = make_options(tmp_path, dry_run=True, script=script)
    packaged = []

    artifacts = run(tmp_path, options=options, package_fn=lambda *a, **kw: packaged.append(1))

    assert artifacts.report is not None
    assert artifacts.clean.endswith("end;\n")
    assert artifacts.output_dir is None
    assert not packaged  # 没有打包


# --- strict ---

def test_strict_raises_validation_failed_on_downgrade(tmp_path):
    llm = FakeLLM(text="say:你好;\nunknownCommand:foo;\nend;\n")
    options = make_options(tmp_path, strict=True)
    with pytest.raises(ValidationFailed) as exc:
        run(tmp_path, options=options, llm=llm)
    assert "strict" in str(exc.value)


def test_strict_allows_clean_script(tmp_path):
    llm = FakeLLM(text=LLM_TEXT)
    options = make_options(tmp_path, strict=True)
    artifacts = run(tmp_path, options=options, llm=llm)
    assert artifacts.output_dir is not None


# --- save-prompt 与脚本路径 ---

def test_save_prompt_writes_file(tmp_path):
    target = tmp_path / "nested" / "prompt.md"
    options = make_options(tmp_path, dry_run=True, save_prompt=target)
    artifacts = run(tmp_path, options=options)
    assert target.read_text(encoding="utf-8") == artifacts.prompt


def test_missing_script_raises_usage_error(tmp_path):
    options = make_options(tmp_path, script=tmp_path / "missing.txt")
    with pytest.raises(UsageError):
        run(tmp_path, options=options)


def test_script_symlink_rejected(tmp_path):
    real = tmp_path / "real.txt"
    real.write_text(SCRIPT, encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(real)
    options = make_options(tmp_path, script=link)
    with pytest.raises(UsageError):
        run(tmp_path, options=options)


def test_cast_whitelist_applies_to_script(tmp_path):
    """角色白名单对 --script 同样生效：未声明的 ASCII 角色会被降级。"""
    script = tmp_path / "story.txt"
    script.write_text("stranger:你好;\nend;\n", encoding="utf-8")
    options = make_options(tmp_path, script=script, strict=True)
    with pytest.raises(ValidationFailed):
        run(tmp_path, options=options)


# --- Asset Pack v1 ---

def test_asset_pack_flows_from_prompt_through_validator_to_packager(tmp_path):
    script = tmp_path / "story.txt"
    script.write_text(
        "changeBg:background.archive;\n"
        "changeFigure:character.guide.normal;\n"
        "bgm:bgm.archive;\n"
        "changeBg:bg.webp;\n"
        "bgm:s_Title.mp3;\n"
        "end;\n",
        encoding="utf-8",
    )
    options = make_options(
        tmp_path,
        script=script,
        asset_pack=EXAMPLE_PACK,
        public_assets=True,
        strict=True,
    )
    captured = {}

    def fake_package(clean, output_dir, **kwargs):
        captured["clean"] = clean
        captured["pack"] = kwargs["asset_pack"]
        return output_dir

    artifacts = run(tmp_path, options=options, package_fn=fake_package)

    assert "background.archive" in artifacts.prompt
    assert "character.guide.normal" in artifacts.prompt
    assert "bgm.archive" in artifacts.prompt
    assert "bg.webp" in artifacts.prompt and "s_Title.mp3" in artifacts.prompt
    assert artifacts.report.downgrades == 0
    assert captured["clean"] == artifacts.clean
    assert captured["pack"].name == "@repo2gal/example-cc0-chronicle"
    assert artifacts.asset_pack is captured["pack"]


def test_invalid_asset_pack_fails_before_fetch(tmp_path):
    called = []
    options = make_options(tmp_path, asset_pack=tmp_path / "missing")

    def should_not_fetch(*args):
        called.append(1)
        return make_ctx()

    with pytest.raises(AssetPackError):
        run_pipeline(options, fetch_fn=should_not_fetch)
    assert not called


def test_public_assets_requires_asset_pack_before_fetch(tmp_path):
    called = []
    options = make_options(tmp_path, public_assets=True)

    with pytest.raises(UsageError, match="--asset-pack"):
        run_pipeline(options, fetch_fn=lambda *args: called.append(1))
    assert not called


def test_default_assets_reject_change_figure_reference(tmp_path):
    llm = FakeLLM(text="changeFigure:character.guide.normal;\nend;\n")
    artifacts = run(tmp_path, llm=llm, package_fn=lambda clean, output, **kw: output)
    assert artifacts.report.downgrades == 1
    assert artifacts.clean.splitlines()[0].startswith(";[repo2gal]")
