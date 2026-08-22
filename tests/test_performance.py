"""Performance Plan v1 的离线 Schema、状态机和 WebGAL golden 测试。"""

from __future__ import annotations

import hashlib
import json

import pytest

from repo2gal.asset_pack import load_asset_pack
from repo2gal.performance import (
    CAPABILITIES,
    PerformanceReport,
    build_performance_prompt,
    build_baseline_plan,
    compile_plan,
    extract_beats,
    load_plan,
    merge_insertions,
    normalize_figure_ids,
    validate_plan,
)

PACK = load_asset_pack("builtin:cc0-chronicle")


def make_script() -> str:
    return (
        "changeBg:background.archive;\n"
        "changeFigure:character.guide.normal -left;\n"
        "Repo2Gal:项目开始了;\n"
        "say:档案被打开;\n"
        "end;\n"
    )


def make_manifest():
    script = normalize_figure_ids(make_script(), PACK)
    return script, extract_beats(script, speakers={"Repo2Gal"}, asset_pack=PACK)


def make_plan(manifest, *, cues=None, profile="chronicle-subtle"):
    return {
        "$schema": "https://repo2gal.dev/schemas/performance-plan/v1.json",
        "schemaVersion": 1,
        "sceneId": "start",
        "storyHash": manifest.story_hash,
        "profile": profile,
        "cues": cues or [],
    }


def plan_json(plan):
    return json.dumps(plan, ensure_ascii=False)


def valid_move_cue(beat_id="b000001"):
    return {
        "id": "cue000001",
        "beatId": beat_id,
        "anchor": "during",
        "actions": [
            {
                "kind": "figure.move",
                "character": "guide",
                "to": "center",
                "duration": "short",
                "easing": "easeOut",
            }
        ],
    }


def test_extract_beats_is_stable_and_excludes_control_commands():
    script, manifest = make_manifest()
    assert [beat.id for beat in manifest.beats] == ["b000001", "b000002"]
    assert [beat.kind for beat in manifest.beats] == ["dialogue", "narration"]
    assert manifest.beats[0].statement_index == 2
    assert manifest.beats[0].background_statement_index == 0
    assert manifest.to_dict()["beats"][0]["backgroundSourceLine"] == 1
    assert manifest.beats[0].state_before["figures"]["guide"]["visible"] is True
    assert manifest.story_hash == "sha256:" + hashlib.sha256(script.encode()).hexdigest()


def test_normalize_figure_ids_uses_parser_safe_separator():
    normalized = normalize_figure_ids("changeFigure:character.guide.normal -left;\n", PACK)
    assert normalized == "changeFigure:character.guide.normal -left -id=fig-guide;\n"


def test_performance_schema_accepts_empty_plan():
    _, manifest = make_manifest()
    report = PerformanceReport()
    plan = load_plan(plan_json(make_plan(manifest)), report=report)
    assert plan is not None
    assert report.schema_valid is True
    assert report.plan_hash is not None


def test_performance_schema_rejects_raw_webgal_and_extra_fields():
    _, manifest = make_manifest()
    plan = make_plan(manifest, cues=[valid_move_cue()])
    plan["cues"][0]["actions"][0]["x"] = 500
    report = PerformanceReport()
    assert load_plan(plan_json(plan), report=report) is None
    assert report.degraded is True
    assert report.schema_valid is False


def test_performance_plan_duplicate_keys_are_rejected():
    _, manifest = make_manifest()
    raw = (
        '{"$schema":"https://repo2gal.dev/schemas/performance-plan/v1.json",'
        '"schemaVersion":1,"schemaVersion":1,"sceneId":"start",'
        f'"storyHash":"{manifest.story_hash}","profile":"chronicle-subtle","cues":[]}}'
    )
    report = PerformanceReport()
    assert load_plan(raw, report=report) is None
    assert "重复键" in report.findings[0]["message"]


def test_run_metadata_is_bound_locally_when_model_copies_hash_incorrectly():
    _, manifest = make_manifest()
    plan = make_plan(manifest, cues=[valid_move_cue()])
    plan["storyHash"] = "sha256:" + "0" * 64
    report = PerformanceReport()
    normalized = load_plan(
        plan_json(plan),
        report=report,
        story_hash=manifest.story_hash,
        scene_id="start",
        profile="chronicle-subtle",
    )
    assert normalized["storyHash"] == manifest.story_hash
    assert any("storyHash" in finding["message"] for finding in report.findings)
    checked = validate_plan(normalized, manifest=manifest, asset_pack=PACK, profile="chronicle-subtle")
    assert checked.semantic_valid is True


def test_missing_transition_phase_uses_deterministic_enter_default():
    _, manifest = make_manifest()
    plan = make_plan(
        manifest,
        cues=[
            {
                "id": "cue000001",
                "beatId": "b000001",
                "anchor": "during",
                "actions": [
                    {
                        "kind": "screen.transition",
                        "preset": "shockwaveIn",
                        "duration": "medium",
                    }
                ],
            }
        ],
    )
    report = PerformanceReport()
    normalized = load_plan(
        plan_json(plan),
        report=report,
        story_hash=manifest.story_hash,
        scene_id="start",
        profile="chronicle-subtle",
    )
    assert normalized["cues"][0]["actions"][0]["phase"] == "enter"
    assert any("缺少 phase" in finding["message"] for finding in report.findings)
    assert report.degraded is True
    checked = validate_plan(normalized, manifest=manifest, asset_pack=PACK, profile="chronicle-subtle")
    assert checked.semantic_valid is True


@pytest.mark.parametrize(
    "broken",
    [
        {"cues": None},
        {"cues": 1},
        {
            "cues": [
                {"id": "cue000001", "beatId": "b000001", "anchor": "during", "actions": None}
            ]
        },
    ],
)
def test_malformed_plan_shapes_reach_schema_fallback_instead_of_type_error(broken):
    _, manifest = make_manifest()
    plan = make_plan(manifest)
    plan.update(broken)
    report = PerformanceReport()
    assert load_plan(plan_json(plan), report=report) is None
    assert report.degraded is True
    assert "Schema" in report.findings[-1]["message"]


def test_validate_and_compile_move_golden():
    script, manifest = make_manifest()
    plan = make_plan(manifest, cues=[valid_move_cue()])
    report = validate_plan(plan, manifest=manifest, asset_pack=PACK, profile="chronicle-subtle")
    assert report.semantic_valid is True
    assert report.plan_hash is not None

    insertions = compile_plan(plan, manifest=manifest, asset_pack=PACK)
    merged = merge_insertions(script, insertions, manifest)
    assert (
        'setTransform:{"position":{"x":-8.697,"y":326.35},"scale":{"x":1.538,"y":1.538}} '
        '-duration=500 -target=fig-guide -ease=easeOut -parallel;'
    ) in merged
    assert merged.index("setTransform:") < merged.index("Repo2Gal:项目开始了;")


def test_compile_enter_shake_transition_and_effect_golden():
    script, manifest = make_manifest()
    plan = make_plan(
        manifest,
        profile="chronicle-cinematic",
        cues=[
            {
                "id": "cue000001",
                "beatId": "b000001",
                "anchor": "before",
                "actions": [
                    {
                        "kind": "figure.exit",
                        "character": "guide",
                        "motion": "fade",
                        "duration": "short",
                    },
                    {
                        "kind": "screen.transition",
                        "phase": "enter",
                        "preset": "shockwaveIn",
                        "duration": "short",
                    },
                    {"kind": "screen.effect", "preset": "snow", "intensity": "subtle"},
                ],
            },
        ],
    )
    # The exit is valid because the beat state says guide is already visible.
    report = validate_plan(plan, manifest=manifest, asset_pack=PACK, profile="chronicle-cinematic")
    assert report.semantic_valid is True
    merged = merge_insertions(script, compile_plan(plan, manifest=manifest, asset_pack=PACK), manifest)
    assert 'setTransform:{"alpha":0} -duration=500 -target=fig-guide -next;' in merged
    assert "changeFigure:none -id=fig-guide -duration=0 -next;" in merged
    assert "changeBg:background.archive -enter=shockwaveIn -enterDuration=500;" in merged
    assert merged.index(";[repo2gal performance] cue000001") < merged.index("changeBg:background.archive")
    assert "pixiInit;\npixiPerform:snow;" in merged


def test_figure_enter_uses_center_base_with_framing_slot_offset():
    script = "say:角色即将入场;\nend;\n"
    manifest = extract_beats(script, speakers={"Repo2Gal"}, asset_pack=PACK)
    plan = make_plan(
        manifest,
        cues=[
            {
                "id": "cue000001",
                "beatId": "b000001",
                "anchor": "before",
                "actions": [
                    {
                        "kind": "figure.enter",
                        "character": "guide",
                        "slot": "left",
                        "motion": "from-left",
                        "duration": "short",
                    }
                ],
            }
        ],
    )
    report = validate_plan(plan, manifest=manifest, asset_pack=PACK, profile="chronicle-subtle")
    assert report.semantic_valid is True
    lines = compile_plan(plan, manifest=manifest, asset_pack=PACK)[0].lines
    assert "changeFigure:character.guide.normal -left -repo2galEnter=from-left" in lines[1]
    assert '-target=fig-guide -next;' in lines[2]
    assert '"position":{"x":-508.697,"y":326.35}' in lines[2]


def test_enter_exit_and_animation_duration_are_compiled():
    script = "say:角色即将入场;\nsay:入场完成;\nsay:继续演出;\nsay:角色准备退场;\nend;\n"
    manifest = extract_beats(script, speakers={"Repo2Gal"}, asset_pack=PACK)
    plan = make_plan(
        manifest,
        profile="chronicle-cinematic",
        cues=[
            {
                "id": "cue000001",
                "beatId": "b000001",
                "anchor": "before",
                "actions": [
                    {"kind": "figure.enter", "character": "guide", "slot": "center", "motion": "fade", "duration": "long"},
                    {"kind": "figure.animate", "character": "guide", "preset": "move-front-and-back", "duration": "long"},
                ],
            },
            {
                "id": "cue000002",
                "beatId": "b000004",
                "anchor": "after",
                "actions": [
                    {"kind": "figure.exit", "character": "guide", "motion": "fade", "duration": "long"}
                ],
            },
        ],
    )
    report = validate_plan(plan, manifest=manifest, asset_pack=PACK, profile="chronicle-cinematic")
    assert report.semantic_valid is True
    merged = merge_insertions(script, compile_plan(plan, manifest=manifest, asset_pack=PACK), manifest)
    assert "-duration=2500 -target=fig-guide -next;" in merged
    assert '"duration":1250' in merged
    assert 'setTransform:{"alpha":0} -duration=2500' in merged


def test_shake_restores_current_semantic_slot():
    script, manifest = make_manifest()
    plan = make_plan(
        manifest,
        cues=[
            {
                "id": "cue000001",
                "beatId": "b000001",
                "anchor": "during",
                "actions": [
                    {"kind": "figure.shake", "character": "guide", "intensity": "normal", "duration": "short"}
                ],
            }
        ],
    )
    report = validate_plan(plan, manifest=manifest, asset_pack=PACK, profile="chronicle-subtle")
    assert report.semantic_valid is True
    line = compile_plan(plan, manifest=manifest, asset_pack=PACK)[0].lines[1]
    assert line.count('"x":-508.697') == 2


def test_invalid_state_and_capability_are_rejected():
    _, manifest = make_manifest()
    cue = valid_move_cue()
    cue["actions"][0]["character"] = "missing"
    plan = make_plan(manifest, cues=[cue])
    report = validate_plan(plan, manifest=manifest, asset_pack=PACK, profile="chronicle-subtle")
    assert report.semantic_valid is False
    assert any("没有可用立绘" in finding["message"] for finding in report.findings)

    cue = valid_move_cue()
    cue["actions"][0] = {
        "kind": "figure.animate",
        "character": "guide",
        "preset": "not-registered",
        "duration": "short",
    }
    plan = make_plan(manifest, cues=[cue])
    report = validate_plan(plan, manifest=manifest, asset_pack=PACK, profile="chronicle-subtle")
    assert report.semantic_valid is False
    assert any("未注册" in finding["message"] for finding in report.findings)


def test_subtle_profile_rejects_dramatic_shake():
    _, manifest = make_manifest()
    cue = valid_move_cue()
    cue["actions"][0] = {
        "kind": "figure.shake",
        "character": "guide",
        "intensity": "dramatic",
        "duration": "short",
    }
    plan = make_plan(manifest, cues=[cue])
    report = validate_plan(plan, manifest=manifest, asset_pack=PACK, profile="chronicle-subtle")
    assert report.semantic_valid is False
    assert any("dramatic" in finding["message"] for finding in report.findings)


def test_branch_figure_state_does_not_leak_between_paths():
    script = normalize_figure_ids(
        "changeFigure:character.guide.normal -left;\n"
        "label:branch_one;\n"
        "Repo2Gal:第一条路径;\n"
        "say:分支继续;\n"
        "label:branch_two;\n"
        "Repo2Gal:第二条路径;\n"
        "say:第二条继续;\n"
        "end;\n",
        PACK,
    )
    manifest = extract_beats(script, speakers={"Repo2Gal"}, asset_pack=PACK)
    plan = make_plan(
        manifest,
        profile="chronicle-cinematic",
        cues=[
            {
                "id": "cue000001",
                "beatId": "b000001",
                "anchor": "before",
                "actions": [
                    {"kind": "figure.exit", "character": "guide", "motion": "fade", "duration": "short"}
                ],
            },
            {
                "id": "cue000002",
                "beatId": "b000003",
                "anchor": "before",
                "actions": [
                    {"kind": "figure.move", "character": "guide", "to": "center", "duration": "short", "easing": "linear"}
                ],
            },
        ],
    )
    report = validate_plan(plan, manifest=manifest, asset_pack=PACK, profile="chronicle-cinematic")
    assert report.semantic_valid is True


def test_story_figure_changes_resynchronize_performance_state():
    script = normalize_figure_ids(
        "changeFigure:character.guide.normal -left;\n"
        "Repo2Gal:先移动;\n"
        "say:剧情继续;\n"
        "changeFigure: -id=fig-guide;\n"
        "Repo2Gal:重新入场;\n"
        "say:入场结束;\n"
        "end;\n",
        PACK,
    )
    manifest = extract_beats(script, speakers={"Repo2Gal"}, asset_pack=PACK)
    plan = make_plan(
        manifest,
        profile="chronicle-cinematic",
        cues=[
            {"id": "cue000001", "beatId": "b000001", "anchor": "during", "actions": [
                {"kind": "figure.move", "character": "guide", "to": "center", "duration": "short", "easing": "linear"}
            ]},
            {"id": "cue000002", "beatId": "b000003", "anchor": "before", "actions": [
                {"kind": "figure.enter", "character": "guide", "slot": "center", "motion": "fade", "duration": "short"}
            ]},
        ],
    )
    report = validate_plan(plan, manifest=manifest, asset_pack=PACK, profile="chronicle-cinematic")
    assert report.semantic_valid is True
    merged = merge_insertions(script, compile_plan(plan, manifest=manifest, asset_pack=PACK), manifest)
    assert merged.count("changeFigure:character.guide.normal") == 2


def test_repeated_identical_story_figure_command_resets_performance_slot():
    script = normalize_figure_ids(
        "changeFigure:character.guide.normal -left;\n"
        "Repo2Gal:先移动到右边;\n"
        "changeFigure:character.guide.normal -left;\n"
        "Repo2Gal:剧情重新要求左边;\n"
        "say:继续;\n"
        "say:结束;\n"
        "end;\n",
        PACK,
    )
    manifest = extract_beats(script, speakers={"Repo2Gal"}, asset_pack=PACK)
    plan = make_plan(
        manifest,
        profile="chronicle-cinematic",
        cues=[
            {"id": "cue000001", "beatId": "b000001", "anchor": "during", "actions": [
                {"kind": "figure.move", "character": "guide", "to": "right", "duration": "short", "easing": "linear"}
            ]},
            {"id": "cue000002", "beatId": "b000002", "anchor": "during", "actions": [
                {"kind": "figure.shake", "character": "guide", "intensity": "subtle", "duration": "short"}
            ]},
        ],
    )
    report = validate_plan(plan, manifest=manifest, asset_pack=PACK, profile="chronicle-cinematic")
    assert report.semantic_valid is True
    lines = [line for insertion in compile_plan(plan, manifest=manifest, asset_pack=PACK) for line in insertion.lines]
    shake = next(line for line in lines if line.startswith("setTempAnimation:"))
    assert shake.count('"x":-508.697') == 2


def test_story_reentry_after_performance_exit_is_visible_to_validator():
    script = normalize_figure_ids(
        "changeFigure:character.guide.normal -left;\n"
        "Repo2Gal:先退场;\n"
        "changeFigure:character.guide.normal -left;\n"
        "Repo2Gal:剧情重新入场;\n"
        "say:继续;\n"
        "say:结束;\n"
        "end;\n",
        PACK,
    )
    manifest = extract_beats(script, speakers={"Repo2Gal"}, asset_pack=PACK)
    plan = make_plan(
        manifest,
        profile="chronicle-cinematic",
        cues=[
            {"id": "cue000001", "beatId": "b000001", "anchor": "during", "actions": [
                {"kind": "figure.exit", "character": "guide", "motion": "fade", "duration": "short"}
            ]},
            {"id": "cue000002", "beatId": "b000002", "anchor": "during", "actions": [
                {"kind": "figure.move", "character": "guide", "to": "center", "duration": "short", "easing": "linear"}
            ]},
        ],
    )
    report = validate_plan(plan, manifest=manifest, asset_pack=PACK, profile="chronicle-cinematic")
    assert report.semantic_valid is True


def test_branch_merge_with_inconsistent_figure_state_rejects_character_action():
    script = normalize_figure_ids(
        "changeFigure:character.guide.normal -left;\n"
        "choose:退场:path_a|保留:path_b;\n"
        "label:path_a;\n"
        "changeFigure: -id=fig-guide;\n"
        "say:A 路径;\n"
        "jumpLabel:merge;\n"
        "label:path_b;\n"
        "say:B 路径;\n"
        "jumpLabel:merge;\n"
        "label:merge;\n"
        "say:汇合;\n"
        "end;\n",
        PACK,
    )
    manifest = extract_beats(script, speakers={"Repo2Gal"}, asset_pack=PACK)
    merge_beat = manifest.beats[-1]
    assert "guide" in merge_beat.state_before["ambiguousFigures"]
    plan = make_plan(manifest, cues=[{
        "id": "cue000001",
        "beatId": merge_beat.id,
        "anchor": "during",
        "actions": [{
            "kind": "figure.move", "character": "guide", "to": "center",
            "duration": "short", "easing": "linear",
        }],
    }])
    report = validate_plan(plan, manifest=manifest, asset_pack=PACK, profile="chronicle-subtle")
    assert report.semantic_valid is False
    assert any("分支汇合" in finding["message"] for finding in report.findings)


def test_conditional_jump_merges_fallthrough_state_at_label():
    script = normalize_figure_ids(
        "changeFigure:character.guide.normal -left;\n"
        "jumpLabel:merge -when=flag;\n"
        "changeFigure: -id=fig-guide;\n"
        "label:merge;\n"
        "say:条件汇合;\n"
        "end;\n",
        PACK,
    )
    manifest = extract_beats(script, speakers={"Repo2Gal"}, asset_pack=PACK)
    beat = manifest.beats[0]
    assert "guide" in beat.state_before["ambiguousFigures"]


def test_screen_transition_requires_an_existing_background():
    script = "say:没有背景;\nend;\n"
    manifest = extract_beats(script, speakers={"Repo2Gal"}, asset_pack=PACK)
    plan = make_plan(manifest, cues=[{
        "id": "cue000001",
        "beatId": "b000001",
        "anchor": "during",
        "actions": [{
            "kind": "screen.transition", "phase": "enter", "preset": "shockwaveIn",
            "duration": "short",
        }],
    }])
    report = validate_plan(plan, manifest=manifest, asset_pack=PACK, profile="chronicle-subtle")
    assert report.semantic_valid is False
    assert any("没有可用背景" in finding["message"] for finding in report.findings)


def test_screen_transition_replaces_existing_background_transition_args():
    script = "changeBg:bg.webp -enter=old -enterDuration=1 -next;\nsay:切换完成;\nend;\n"
    manifest = extract_beats(script, speakers={"Repo2Gal"}, asset_pack=PACK)
    plan = make_plan(manifest, cues=[{
        "id": "cue000001",
        "beatId": "b000001",
        "anchor": "during",
        "actions": [{
            "kind": "screen.transition", "phase": "enter", "preset": "shockwaveIn",
            "duration": "medium",
        }],
    }])
    report = validate_plan(plan, manifest=manifest, asset_pack=PACK, profile="chronicle-subtle")
    assert report.semantic_valid is True
    merged = merge_insertions(script, compile_plan(plan, manifest=manifest, asset_pack=PACK), manifest)
    assert "old" not in merged
    assert "changeBg:bg.webp -next -enter=shockwaveIn -enterDuration=1200;" in merged


def test_during_exit_is_parallel_and_does_not_block_dialogue():
    script, manifest = make_manifest()
    plan = make_plan(manifest, cues=[{
        "id": "cue000001",
        "beatId": "b000001",
        "anchor": "during",
        "actions": [{
            "kind": "figure.exit", "character": "guide", "motion": "fade", "duration": "long",
        }],
    }])
    report = validate_plan(plan, manifest=manifest, asset_pack=PACK, profile="chronicle-subtle")
    assert report.semantic_valid is True
    lines = compile_plan(plan, manifest=manifest, asset_pack=PACK)[0].lines
    assert lines[1] == 'setTransform:{"alpha":0} -duration=2500 -target=fig-guide -parallel;'
    assert not any(line.startswith("changeFigure:none") for line in lines)


def test_performance_prompt_contains_no_full_repo_context():
    _, manifest = make_manifest()
    prompt = build_performance_prompt(manifest)
    assert "舞台导演" in prompt
    assert manifest.story_hash in prompt
    assert "setTransform" in prompt
    assert "项目开始了" in prompt
    assert "GitHub" not in prompt


def test_baseline_plan_guarantees_one_character_animation():
    _, manifest = make_manifest()
    plan = build_baseline_plan(manifest)
    assert plan["cues"][0]["beatId"] == "b000001"
    assert plan["cues"][0]["actions"][0]["kind"] == "figure.animate"
    assert plan["cues"][0]["actions"][0]["preset"] == "move-front-and-back"


def test_capability_registry_is_stable():
    assert CAPABILITIES["webgalVersion"] == "4.6.2"
    assert CAPABILITIES["durations"]["short"] == 500
