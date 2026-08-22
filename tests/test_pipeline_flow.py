"""流程编排（pipeline）四模式端到端离线测试。

注入 fake 的 fetch / LLM / package，覆盖模式矩阵：
dry-run x script 的四种组合，以及 strict、save-prompt、脚本路径错误。
"""

from pathlib import Path

import pytest

from repo2gal.errors import AssetPackError, GenerationError, UsageError, ValidationFailed
from repo2gal.fetcher import Contributor, RepoContext
from repo2gal.generator import Cast
from repo2gal.pipeline import RunOptions, run_pipeline
from repo2gal.performance import extract_beats

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


def test_performance_audit_options_require_performance_flag(tmp_path):
    options = make_options(tmp_path, save_beat_manifest=tmp_path / "beats.json")
    with pytest.raises(UsageError, match="--performance"):
        run(tmp_path, options=options)


def test_strict_performance_requires_performance_flag(tmp_path):
    options = make_options(tmp_path, strict_performance=True)
    with pytest.raises(UsageError, match="--performance"):
        run(tmp_path, options=options)


def test_default_assets_reject_change_figure_reference(tmp_path):
    llm = FakeLLM(text="changeFigure:character.guide.normal;\nend;\n")
    artifacts = run(tmp_path, llm=llm, package_fn=lambda clean, output, **kw: output)
    assert artifacts.report.downgrades == 1
    assert artifacts.clean.splitlines()[0].startswith(";[repo2gal]")


def test_performance_calls_llm_twice_and_merges_compiled_output(tmp_path):
    script = tmp_path / "story.txt"
    story = "say:第一句。\nend;\n"
    script.write_text(story, encoding="utf-8")
    manifest = extract_beats("say:第一句。;\nend;\n", speakers={"widget"})
    plan = {
        "$schema": "https://repo2gal.dev/schemas/performance-plan/v1.json",
        "schemaVersion": 1,
        "sceneId": "start",
        "storyHash": manifest.story_hash,
        "profile": "chronicle-subtle",
        "cues": [
            {
                "id": "cue000001",
                "beatId": "b000001",
                "anchor": "during",
                "actions": [
                    {"kind": "screen.effect", "preset": "snow", "intensity": "subtle"}
                ],
            }
        ],
    }

    class TwoStageLLM:
        def __init__(self):
            self.calls = []

        def complete(self, prompt, *, temperature=0.8):
            self.calls.append((prompt, temperature))
            return __import__("json").dumps(plan)

    llm = TwoStageLLM()
    options = make_options(
        tmp_path,
        script=script,
        performance=True,
        save_beat_manifest=tmp_path / "beats.json",
        save_performance_plan=tmp_path / "plan.json",
        save_performance_report=tmp_path / "report.json",
    )
    # The supplied script is used, so the first call is the performance call only.
    artifacts = run(tmp_path, options=options, llm=llm, package_fn=lambda clean, output, **kw: output)
    assert len(llm.calls) == 1
    assert llm.calls[0][1] == 0.2
    assert "pixiInit;" in artifacts.clean
    assert artifacts.performance_report is not None
    assert artifacts.performance_report.semantic_valid is True
    assert (tmp_path / "beats.json").exists()
    assert (tmp_path / "plan.json").exists()
    assert (tmp_path / "report.json").exists()


def test_invalid_performance_falls_back_but_strict_performance_fails(tmp_path):
    script = tmp_path / "story.txt"
    script.write_text(SCRIPT, encoding="utf-8")

    class InvalidPerformanceLLM:
        def complete(self, prompt, *, temperature=0.8):
            return "not-json"

    options = make_options(tmp_path, script=script, performance=True)
    artifacts = run(
        tmp_path,
        options=options,
        llm=InvalidPerformanceLLM(),
        package_fn=lambda clean, output, **kw: output,
    )
    assert "pixiPerform:snow;" in artifacts.clean
    assert "say:这是现成剧本。;" in artifacts.clean
    assert artifacts.performance_report.degraded is True

    strict_options = make_options(tmp_path, script=script, performance=True, strict_performance=True)
    with pytest.raises(ValidationFailed, match="strict-performance"):
        run(tmp_path, options=strict_options, llm=InvalidPerformanceLLM())


def test_valid_empty_plan_uses_fallback_and_strict_performance_rejects(tmp_path):
    script = tmp_path / "story.txt"
    script.write_text(SCRIPT, encoding="utf-8")
    manifest = extract_beats("say:这是现成剧本。;\nend;\n", speakers={"widget"})
    empty_plan = {
        "$schema": "https://repo2gal.dev/schemas/performance-plan/v1.json",
        "schemaVersion": 1,
        "sceneId": "start",
        "storyHash": manifest.story_hash,
        "profile": "chronicle-subtle",
        "cues": [],
    }

    class EmptyPerformanceLLM:
        def complete(self, prompt, *, temperature=0.8):
            return __import__("json").dumps(empty_plan)

    options = make_options(tmp_path, script=script, performance=True)
    artifacts = run(
        tmp_path,
        options=options,
        llm=EmptyPerformanceLLM(),
        package_fn=lambda clean, output, **kw: output,
    )
    assert "pixiPerform:snow;" in artifacts.clean
    assert artifacts.performance_report.degraded is True

    strict_options = make_options(tmp_path, script=script, performance=True, strict_performance=True)
    with pytest.raises(ValidationFailed, match="strict-performance"):
        run(tmp_path, options=strict_options, llm=EmptyPerformanceLLM())


def test_no_dialogue_plan_uses_unanchored_scene_effect_fallback(tmp_path):
    script = tmp_path / "story.txt"
    script.write_text("intro:只有标题;\nend;\n", encoding="utf-8")
    empty_plan = {
        "$schema": "https://repo2gal.dev/schemas/performance-plan/v1.json",
        "schemaVersion": 1,
        "sceneId": "start",
        "storyHash": extract_beats("intro:只有标题;\nend;\n").story_hash,
        "profile": "chronicle-subtle",
        "cues": [],
    }

    class EmptyPerformanceLLM:
        def complete(self, prompt, *, temperature=0.8):
            return __import__("json").dumps(empty_plan)

    options = make_options(tmp_path, script=script, performance=True)
    artifacts = run(
        tmp_path,
        options=options,
        llm=EmptyPerformanceLLM(),
        package_fn=lambda clean, output, **kw: output,
    )
    assert artifacts.clean.startswith(";[repo2gal performance] baseline\npixiInit;\npixiPerform:snow;")
    assert artifacts.performance_report.compiled_command_count == 2


def test_repaired_transition_compiles_normally_but_strict_performance_rejects(tmp_path):
    script = tmp_path / "story.txt"
    transition_story = "changeBg:bg.webp;\nsay:这是现成剧本。;\nend;\n"
    script.write_text(transition_story, encoding="utf-8")
    manifest = extract_beats(transition_story, speakers={"widget"})
    repaired_plan = {
        "$schema": "https://repo2gal.dev/schemas/performance-plan/v1.json",
        "schemaVersion": 1,
        "sceneId": "start",
        "storyHash": manifest.story_hash,
        "profile": "chronicle-subtle",
        "cues": [{
            "id": "cue000001",
            "beatId": "b000001",
            "anchor": "during",
            "actions": [{
                "kind": "screen.transition",
                "preset": "shockwaveIn",
                "duration": "short",
            }],
        }],
    }

    class RepairedPerformanceLLM:
        def complete(self, prompt, *, temperature=0.8):
            return __import__("json").dumps(repaired_plan)

    options = make_options(tmp_path, script=script, performance=True)
    artifacts = run(
        tmp_path,
        options=options,
        llm=RepairedPerformanceLLM(),
        package_fn=lambda clean, output, **kw: output,
    )
    assert "changeBg:bg.webp -enter=shockwaveIn -enterDuration=500;" in artifacts.clean
    assert artifacts.performance_report.degraded is True

    strict_options = make_options(tmp_path, script=script, performance=True, strict_performance=True)
    with pytest.raises(ValidationFailed, match="strict-performance"):
        run(tmp_path, options=strict_options, llm=RepairedPerformanceLLM())


def test_performance_llm_failure_falls_back_but_strict_performance_fails(tmp_path):
    script = tmp_path / "story.txt"
    script.write_text(SCRIPT, encoding="utf-8")

    class FailedPerformanceLLM:
        def complete(self, prompt, *, temperature=0.8):
            raise GenerationError("演出服务不可用")

    options = make_options(tmp_path, script=script, performance=True)
    artifacts = run(
        tmp_path,
        options=options,
        llm=FailedPerformanceLLM(),
        package_fn=lambda clean, output, **kw: output,
    )
    assert artifacts.performance_report.degraded is True
    assert "pixiPerform:snow;" in artifacts.clean
    assert "say:这是现成剧本。;" in artifacts.clean

    strict_options = make_options(tmp_path, script=script, performance=True, strict_performance=True)
    with pytest.raises(ValidationFailed, match="strict-performance"):
        run(tmp_path, options=strict_options, llm=FailedPerformanceLLM())
