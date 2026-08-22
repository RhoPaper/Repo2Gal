"""Chronicle 动态演出：Beat Manifest、Performance Plan 与确定性编译器。

LLM 只返回受限的语义 JSON。WebGAL 命令、资源路径、runtime target、坐标和时序参数
全部由本模块确定性生成。
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from .asset_pack import AssetPack
from .webgal import KNOWN_COMMANDS, statement_body
from .webgal_assets import figure_base_transform

PERFORMANCE_SCHEMA_URI = "https://repo2gal.dev/schemas/performance-plan/v1.json"
DEFAULT_PROFILE = "chronicle-subtle"
PROFILES = {
    "chronicle-subtle": {
        "maxCuesPerBeatRatio": 1 / 3,
        "maxActionsPerCue": 2,
        "maxScreenEffects": 1,
        "allowDramaticShake": False,
    },
    "chronicle-cinematic": {
        "maxCuesPerBeatRatio": 1 / 2,
        "maxActionsPerCue": 3,
        "maxScreenEffects": 2,
        "allowDramaticShake": True,
    },
}

CAPABILITIES: dict[str, Any] = {
    "webgalVersion": "4.6.2",
    "figureMotions": ["none", "from-left", "from-right", "fade"],
    "figureAnimations": ["shockwaveIn", "shockwaveOut", "move-front-and-back"],
    "transitionPresets": ["shockwaveIn", "shockwaveOut"],
    "pixiEffects": ["snow", "rain", "cherryBlossoms", "heavySnow"],
    "slots": ["left", "center", "right"],
    "durations": {"instant": 0, "short": 500, "medium": 1200, "long": 2500},
    "slotTransforms": {
        "left": {"x": -500, "y": 0},
        "center": {"x": 0, "y": 0},
        "right": {"x": 500, "y": 0},
    },
}

_SCHEMA = json.loads(
    resources.files("repo2gal")
    .joinpath("schemas/performance-plan-v1.schema.json")
    .read_text(encoding="utf-8")
)
Draft202012Validator.check_schema(_SCHEMA)


@dataclass(frozen=True)
class Beat:
    id: str
    ordinal: int
    source_line: int
    statement_index: int
    background_statement_index: int | None
    kind: str
    speaker: str | None
    text: str
    branch_path: tuple[str, ...]
    state_before: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ordinal": self.ordinal,
            "sourceLine": self.source_line,
            "backgroundSourceLine": (
                self.background_statement_index + 1
                if self.background_statement_index is not None
                else None
            ),
            "kind": self.kind,
            "speaker": self.speaker,
            "text": self.text,
            "branchPath": list(self.branch_path),
            "stateBefore": self.state_before,
        }


@dataclass(frozen=True)
class BeatManifest:
    scene_id: str
    story_hash: str
    beats: tuple[Beat, ...]
    characters: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "sceneId": self.scene_id,
            "storyHash": self.story_hash,
            "characters": list(self.characters),
            "beats": [beat.to_dict() for beat in self.beats],
        }


@dataclass
class PerformanceReport:
    schema_valid: bool = False
    semantic_valid: bool = False
    degraded: bool = False
    findings: list[dict[str, Any]] = field(default_factory=list)
    cue_count: int = 0
    action_count: int = 0
    compiled_command_count: int = 0
    story_hash: str | None = None
    plan_hash: str | None = None

    @property
    def errors(self) -> int:
        return sum(1 for finding in self.findings if finding.get("kind") == "error")

    def add(self, kind: str, message: str, *, cue_id: str | None = None, beat_id: str | None = None) -> None:
        finding: dict[str, Any] = {"kind": kind, "message": message}
        if cue_id is not None:
            finding["cueId"] = cue_id
        if beat_id is not None:
            finding["beatId"] = beat_id
        self.findings.append(finding)
        if kind == "error":
            self.degraded = True

    def summary(self) -> str:
        if not self.findings:
            return f"演出计划通过：{self.cue_count} 个 cue，{self.action_count} 个动作"
        buckets: dict[str, int] = {}
        for finding in self.findings:
            kind = str(finding.get("kind", "note"))
            buckets[kind] = buckets.get(kind, 0) + 1
        detail = "，".join(f"{key}×{value}" for key, value in sorted(buckets.items()))
        return f"演出计划：{detail}，保留 {self.cue_count} 个 cue"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "schemaValid": self.schema_valid,
            "semanticValid": self.semantic_valid,
            "degraded": self.degraded,
            "cueCount": self.cue_count,
            "actionCount": self.action_count,
            "compiledCommandCount": self.compiled_command_count,
            "storyHash": self.story_hash,
            "planHash": self.plan_hash,
            "webgalVersion": CAPABILITIES["webgalVersion"],
            "capabilityHash": capability_hash(),
            "findings": self.findings,
        }


@dataclass(frozen=True)
class PerformanceInsertion:
    beat_id: str
    anchor: str
    ordinal: int
    cue_id: str
    action_index: int
    lines: tuple[str, ...]


def capability_hash() -> str:
    payload = json.dumps(CAPABILITIES, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_runtime_id(character: str) -> str:
    value = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", character).strip("-")
    return f"fig-{value or 'character'}"


def _split_line(line: str) -> tuple[str | None, str]:
    body = statement_body(line.strip()).strip()
    command, separator, content = body.partition(":")
    return (command.strip(), content.strip()) if separator else (None, body)


def _content_without_args(content: str) -> str:
    if content.startswith("-"):
        return ""
    return content.split(" -", 1)[0].strip()


def _arg(content: str, name: str) -> str | None:
    match = re.search(rf"(?:^| )-{re.escape(name)}=([^ ]+)", content)
    return match.group(1) if match else None


def _has_flag(content: str, name: str) -> bool:
    match = re.search(rf"(?:^| )-{re.escape(name)}(?:=([^ ]+))?(?: |$)", content)
    return match is not None and (match.group(1) is None or match.group(1) == "true")


def _copy_state(state: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(state)


def _initial_state() -> dict[str, Any]:
    return {
        "background": None,
        "backgroundStatementIndex": None,
        "bgm": None,
        "figures": {},
        "figureVersions": {},
        "ambiguousFigures": [],
    }


def _choose_label_targets(content: str) -> list[str]:
    value = content.split(" -", 1)[0]
    targets: list[str] = []
    for part in re.split(r"(?<!\\)\|", value):
        segments = re.split(r"(?<!\\):", part)
        if len(segments) >= 2 and segments[1].strip():
            targets.append(segments[1].strip())
    return targets


def _merge_incoming_states(states: list[dict[str, Any]]) -> dict[str, Any]:
    if len(states) == 1:
        return _copy_state(states[0])
    merged = _initial_state()
    for key in ("background", "backgroundStatementIndex", "bgm"):
        values = [state.get(key) for state in states]
        merged[key] = values[0] if all(value == values[0] for value in values) else None
    all_characters = set().union(*(state.get("figures", {}) for state in states))
    for character in sorted(all_characters):
        figures = [state.get("figures", {}).get(character) for state in states]
        if figures[0] is not None and all(figure == figures[0] for figure in figures):
            merged["figures"][character] = _copy_state(figures[0])
        else:
            merged["ambiguousFigures"].append(character)
    for character in set().union(*(state.get("figureVersions", {}) for state in states)):
        merged["figureVersions"][character] = max(
            int(state.get("figureVersions", {}).get(character, 0)) for state in states
        )
    return merged


def _asset_character_map(asset_pack: AssetPack | None) -> dict[str, dict[str, Any]]:
    if asset_pack is None:
        return {}
    result: dict[str, dict[str, Any]] = {}
    for asset in asset_pack.assets.values():
        if asset.type != "character":
            continue
        character = asset.metadata.get("character")
        if isinstance(character, str) and character not in result:
            result[character] = {
                "character": character,
                "asset": asset.logical_id,
                "emotion": asset.metadata.get("emotion", "normal"),
            }
    return result


def _figure_from_reference(reference: str, asset_pack: AssetPack | None) -> tuple[str, str] | None:
    if asset_pack is None:
        return None
    asset = asset_pack.assets.get(reference)
    if asset is None or asset.type != "character":
        return None
    character = asset.metadata.get("character")
    if not isinstance(character, str):
        return None
    return character, reference


def _apply_scene_command(
    command: str,
    content: str,
    state: dict[str, Any],
    asset_pack: AssetPack | None,
    statement_index: int,
) -> None:
    reference = _content_without_args(content)
    if command == "changeBg":
        state["background"] = reference or None
        state["backgroundStatementIndex"] = statement_index
    elif command == "bgm":
        state["bgm"] = reference or None
    elif command == "changeFigure":
        if reference == "none" or not reference:
            runtime_id = _arg(content, "id")
            if runtime_id:
                for character, figure in list(state["figures"].items()):
                    if figure.get("runtimeId") == runtime_id:
                        state["figureVersions"][character] = int(
                            state["figureVersions"].get(character, 0)
                        ) + 1
                        state["figures"].pop(character, None)
                        if character in state["ambiguousFigures"]:
                            state["ambiguousFigures"].remove(character)
            return
        resolved = _figure_from_reference(reference, asset_pack)
        if resolved is None:
            return
        character, asset_id = resolved
        version = int(state["figureVersions"].get(character, 0)) + 1
        state["figureVersions"][character] = version
        framing = figure_base_transform(asset_pack.assets[asset_id])
        position = "right" if _has_flag(content, "right") else "left" if _has_flag(content, "left") else "center"
        state["figures"][character] = {
            "visible": True,
            "slot": position,
            "asset": asset_id,
            "runtimeId": _arg(content, "id") or _safe_runtime_id(character),
            "framing": framing,
            "storyVersion": version,
        }
        if character in state["ambiguousFigures"]:
            state["ambiguousFigures"].remove(character)


def extract_beats(
    script: str,
    *,
    speakers: Iterable[str] = (),
    asset_pack: AssetPack | None = None,
    scene_id: str = "start",
) -> BeatManifest:
    """从已清洗脚本生成稳定 Beat Manifest。"""
    speaker_names = set(speakers)
    state = _initial_state()
    beats: list[Beat] = []
    ordinal = 0
    branch_path: list[str] = []
    incoming_states: dict[str, list[dict[str, Any]]] = {}
    fallthrough_reachable = True
    for statement_index, original in enumerate(script.splitlines()):
        line = original.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        command, content = _split_line(stripped)
        if command is None and content in KNOWN_COMMANDS:
            command, content = content, ""
        if command == "label":
            label = content.strip()
            incoming = list(incoming_states.get(label, []))
            if fallthrough_reachable:
                incoming.append(_copy_state(state))
            if incoming:
                state = _merge_incoming_states(incoming)
            fallthrough_reachable = bool(incoming)
            branch_path = [label]
        state_before = _copy_state(state)

        kind: str | None = None
        speaker: str | None = None
        text = _content_without_args(content) if command is not None else content
        if command is None or command == "say":
            kind = "narration"
        elif command in speaker_names:
            kind = "dialogue"
            speaker = command
        elif command == "label":
            pass
        elif command == "choose":
            kind = "choice"
        elif command in KNOWN_COMMANDS:
            kind = "scene_command"

        if kind in ("dialogue", "narration"):
            ordinal += 1
            beats.append(
                Beat(
                    id=f"b{ordinal:06d}",
                    ordinal=ordinal,
                    source_line=statement_index + 1,
                    statement_index=statement_index,
                    background_statement_index=state_before.get("backgroundStatementIndex"),
                    kind=kind,
                    speaker=speaker,
                    text=text,
                    branch_path=tuple(branch_path),
                    state_before=state_before,
                )
            )
        if command is not None:
            _apply_scene_command(command, content, state, asset_pack, statement_index)
            if command == "choose":
                for target in _choose_label_targets(content):
                    incoming_states.setdefault(target, []).append(_copy_state(state))
                fallthrough_reachable = False
            elif command == "jumpLabel":
                target = _content_without_args(content)
                if target:
                    incoming_states.setdefault(target, []).append(_copy_state(state))
                if _arg(content, "when") is None:
                    fallthrough_reachable = False

    characters = tuple(sorted(_asset_character_map(asset_pack).values(), key=lambda item: item["character"]))
    story_hash = "sha256:" + hashlib.sha256(script.encode("utf-8")).hexdigest()
    return BeatManifest(
        scene_id=scene_id,
        story_hash=story_hash,
        beats=tuple(beats),
        characters=characters,
    )


def normalize_figure_ids(script: str, asset_pack: AssetPack | None) -> str:
    """为 Asset Pack 角色补入稳定 runtime ID，避免性能动作无法定位目标。"""
    if asset_pack is None:
        return script
    lines: list[str] = []
    for original in script.splitlines():
        stripped = original.strip()
        if not stripped:
            lines.append(original)
            continue
        body = statement_body(stripped).strip()
        command, separator, content = body.partition(":")
        if separator != ":" or command != "changeFigure":
            lines.append(original)
            continue
        reference = _content_without_args(content)
        resolved = _figure_from_reference(reference, asset_pack)
        if resolved is None or _arg(content, "id"):
            lines.append(original)
            continue
        character, _ = resolved
        suffix = content[len(reference) :].rstrip()
        suffix += f" -id={_safe_runtime_id(character)}"
        comment = original[len(stripped) :]
        lines.append(f"{command}:{reference}{suffix};" + comment)
    return "\n".join(lines) + "\n"


def build_performance_prompt(manifest: BeatManifest, *, profile: str = DEFAULT_PROFILE) -> str:
    template = resources.files("repo2gal").joinpath("prompts/performance.md").read_text(encoding="utf-8")
    return (
        template.replace("{profile}", profile)
        .replace("{capabilities}", json.dumps(CAPABILITIES, ensure_ascii=False, indent=2))
        .replace("{manifest}", json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2))
    )


def build_baseline_plan(manifest: BeatManifest, *, profile: str = DEFAULT_PROFILE) -> dict[str, Any]:
    """生成一个不依赖 LLM 的最低演出，避免空计划产出完全静态的性能模式。"""
    action: dict[str, Any] | None = None
    beat: Beat | None = None
    for candidate in manifest.beats:
        for character, figure in candidate.state_before.get("figures", {}).items():
            if figure.get("visible"):
                beat = candidate
                action = {
                    "kind": "figure.animate",
                    "character": character,
                    "preset": "move-front-and-back",
                    "duration": "medium",
                }
                break
        if action is not None:
            break
    if action is None:
        for candidate in manifest.beats:
            if candidate.state_before.get("background"):
                beat = candidate
                action = {
                    "kind": "screen.transition",
                    "phase": "enter",
                    "preset": "shockwaveIn",
                    "duration": "short",
                }
                break
    if action is None and manifest.beats:
        beat = manifest.beats[0]
        action = {
            "kind": "screen.effect",
            "preset": "snow",
            "intensity": "subtle",
        }

    cues = []
    if beat is not None and action is not None:
        cues.append(
            {
                "id": "cue000001",
                "beatId": beat.id,
                "anchor": "during",
                "actions": [action],
            }
        )
    return {
        "$schema": PERFORMANCE_SCHEMA_URI,
        "schemaVersion": 1,
        "sceneId": manifest.scene_id,
        "storyHash": manifest.story_hash,
        "profile": profile,
        "cues": cues,
    }


def _parse_json_response(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    def build(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"演出计划存在重复键：{key}")
            value[key] = item
        return value

    value = json.loads(text, object_pairs_hook=build)
    if not isinstance(value, dict):
        raise ValueError("演出计划顶层必须是 JSON object")
    return value


def load_plan(
    raw: str,
    *,
    report: PerformanceReport,
    story_hash: str | None = None,
    scene_id: str | None = None,
    profile: str | None = None,
) -> dict[str, Any] | None:
    try:
        plan = _parse_json_response(raw)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        report.add("error", f"演出计划不是合法 JSON：{exc}")
        return None
    # These fields describe the current deterministic run, not a creative decision. Bind them
    # locally so a model copying a long hash or profile cannot invalidate an otherwise usable plan.
    for key, expected in (("storyHash", story_hash), ("sceneId", scene_id), ("profile", profile)):
        if expected is None:
            continue
        if plan.get(key) != expected:
            if key in plan:
                report.add("warn", f"LLM 返回的 {key} 已按当前运行上下文修正")
            plan[key] = expected
    cues = plan.get("cues")
    if isinstance(cues, list):
        for cue in cues:
            if not isinstance(cue, dict):
                continue
            actions = cue.get("actions")
            if not isinstance(actions, list):
                continue
            for action in actions:
                if not isinstance(action, dict) or action.get("kind") != "screen.transition":
                    continue
                if "phase" not in action:
                    preset = action.get("preset")
                    action["phase"] = "exit" if preset == "shockwaveOut" else "enter"
                    report.add(
                        "warn",
                        f"screen.transition 缺少 phase，已根据 preset 使用 {action['phase']}",
                        cue_id=cue.get("id") if isinstance(cue.get("id"), str) else None,
                        beat_id=cue.get("beatId") if isinstance(cue.get("beatId"), str) else None,
                    )
                    report.degraded = True
    validator = Draft202012Validator(_SCHEMA)
    errors = sorted(validator.iter_errors(plan), key=lambda error: tuple(str(p) for p in error.absolute_path))
    if errors:
        report.add("error", "演出计划 Schema 校验失败：" + "；".join(error.message for error in errors[:8]))
        return None
    report.schema_valid = True
    report.plan_hash = "sha256:" + hashlib.sha256(
        json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return plan


def _beat_map(manifest: BeatManifest) -> dict[str, Beat]:
    return {beat.id: beat for beat in manifest.beats}


def _base_state_for_beat(beat: Beat) -> dict[str, Any]:
    return _copy_state(beat.state_before)


def _action_character(action: dict[str, Any]) -> str | None:
    value = action.get("character")
    return value if isinstance(value, str) else None


def _sync_story_figures(
    runtime_state: dict[str, Any],
    previous_story: dict[str, Any] | None,
    current_story: dict[str, Any],
) -> None:
    """只在剧情命令实际改变角色时同步，保留两条剧情命令之间的 Performance 状态。"""
    if previous_story is None:
        runtime_state.clear()
        runtime_state.update(_copy_state(current_story))
        return
    for character in set(previous_story) - set(current_story):
        runtime_state.pop(character, None)
    for character, figure in current_story.items():
        if character not in previous_story or figure != previous_story[character]:
            runtime_state[character] = _copy_state(figure)


def validate_plan(
    plan: dict[str, Any],
    *,
    manifest: BeatManifest,
    asset_pack: AssetPack | None,
    profile: str,
) -> PerformanceReport:
    report = PerformanceReport(
        schema_valid=True,
        story_hash=manifest.story_hash,
        plan_hash="sha256:" + hashlib.sha256(
            json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        cue_count=len(plan.get("cues", [])),
        action_count=sum(len(cue.get("actions", [])) for cue in plan.get("cues", [])),
    )
    beats = _beat_map(manifest)
    if plan.get("sceneId") != manifest.scene_id:
        report.add("error", f"sceneId 不匹配：{plan.get('sceneId')}")
    if plan.get("storyHash") != manifest.story_hash:
        report.add("error", "storyHash 与当前 sanitize 后剧情不匹配")
    if plan.get("profile") != profile:
        report.add("error", f"profile 不匹配：期望 {profile}，实际 {plan.get('profile')}")

    character_assets = _asset_character_map(asset_pack)
    seen_cues: set[str] = set()
    screen_effects = 0
    transitioned_backgrounds: set[int] = set()
    plan_figures: dict[tuple[str, ...], dict[str, dict[str, Any]]] = {}
    story_figures: dict[tuple[str, ...], dict[str, dict[str, Any]]] = {}
    seen_beats: set[str] = set()
    for cue in sorted(
        plan.get("cues", []),
        key=lambda item: (
            beats[item["beatId"]].ordinal if item["beatId"] in beats else 10**9,
            item["id"],
        ),
    ):
        cue_id = cue["id"]
        beat_id = cue["beatId"]
        if cue_id in seen_cues:
            report.add("error", f"cue id 重复：{cue_id}", cue_id=cue_id, beat_id=beat_id)
        seen_cues.add(cue_id)
        if beat_id in seen_beats:
            report.add("error", f"同一 beat 只能绑定一个 cue：{beat_id}", cue_id=cue_id, beat_id=beat_id)
        seen_beats.add(beat_id)
        beat = beats.get(beat_id)
        if beat is None:
            report.add("error", f"beat 不存在：{beat_id}", cue_id=cue_id, beat_id=beat_id)
            continue
        if beat.kind not in ("dialogue", "narration"):
            report.add("error", f"beat 不是可演出 dialogue/narration：{beat_id}", cue_id=cue_id, beat_id=beat_id)
        current_story_figures = _copy_state(beat.state_before.get("figures", {}))
        branch_state = plan_figures.setdefault(beat.branch_path, {})
        _sync_story_figures(
            branch_state,
            story_figures.get(beat.branch_path),
            current_story_figures,
        )
        story_figures[beat.branch_path] = current_story_figures
        transform_targets: set[str] = set()
        for index, action in enumerate(cue["actions"]):
            kind = action["kind"]
            character = _action_character(action)
            if character is not None and character in beat.state_before.get("ambiguousFigures", []):
                report.add(
                    "error",
                    f"角色在分支汇合处状态不一致，不能安全演出：{character}",
                    cue_id=cue_id,
                    beat_id=beat_id,
                )
                continue
            if character is not None and character not in character_assets:
                report.add("error", f"角色没有可用立绘：{character}", cue_id=cue_id, beat_id=beat_id)
                continue
            if kind in {"figure.move", "figure.shake", "figure.animate"} and character in transform_targets:
                report.add("error", f"同一 cue 对角色重复安排冲突演出：{character}", cue_id=cue_id, beat_id=beat_id)
            if kind in {"figure.move", "figure.shake", "figure.animate"} and character:
                transform_targets.add(character)
                effective_visible = bool(branch_state.get(character, {}).get("visible"))
                if not effective_visible:
                    report.add("error", f"角色尚未入场：{character}", cue_id=cue_id, beat_id=beat_id)
            if kind == "figure.enter" and character:
                if bool(branch_state.get(character, {}).get("visible")):
                    report.add("error", f"角色重复入场：{character}", cue_id=cue_id, beat_id=beat_id)
                branch_state[character] = {
                    "visible": True,
                    "asset": character_assets[character]["asset"],
                    "slot": action["slot"],
                }
            elif kind == "figure.exit" and character:
                if not bool(branch_state.get(character, {}).get("visible")):
                    report.add("error", f"角色尚未入场或已退场：{character}", cue_id=cue_id, beat_id=beat_id)
                branch_state.pop(character, None)
            if kind == "figure.animate" and action["preset"] not in CAPABILITIES["figureAnimations"]:
                report.add("error", f"未注册的立绘动画 preset：{action['preset']}", cue_id=cue_id, beat_id=beat_id)
            if kind == "screen.transition" and action["preset"] not in CAPABILITIES["transitionPresets"]:
                report.add("error", f"未注册的转场 preset：{action['preset']}", cue_id=cue_id, beat_id=beat_id)
            if kind == "screen.transition":
                if not beat.state_before.get("background"):
                    report.add(
                        "error",
                        "当前 beat 没有可用背景 bg-main，不能执行 screen.transition",
                        cue_id=cue_id,
                        beat_id=beat_id,
                    )
                elif beat.background_statement_index is None:
                    report.add(
                        "error",
                        "无法定位当前背景的 changeBg 语句，不能安全编译 screen.transition",
                        cue_id=cue_id,
                        beat_id=beat_id,
                    )
                elif beat.background_statement_index in transitioned_backgrounds:
                    report.add(
                        "error",
                        "同一次 changeBg 只能绑定一个 screen.transition",
                        cue_id=cue_id,
                        beat_id=beat_id,
                    )
                else:
                    transitioned_backgrounds.add(beat.background_statement_index)
                expected_phase = "exit" if action["preset"] == "shockwaveOut" else "enter"
                if action["phase"] != expected_phase:
                    report.add(
                        "error",
                        f"转场 preset {action['preset']} 必须使用 phase={expected_phase}",
                        cue_id=cue_id,
                        beat_id=beat_id,
                    )
            if kind == "screen.effect":
                screen_effects += 1
                if action["preset"] not in CAPABILITIES["pixiEffects"]:
                    report.add("error", f"未注册的 Pixi preset：{action['preset']}", cue_id=cue_id, beat_id=beat_id)
                if screen_effects > int(PROFILES[profile]["maxScreenEffects"]):
                    report.add("error", "当前 profile 的场景效果数量超限", cue_id=cue_id, beat_id=beat_id)
            if kind == "figure.shake" and action["intensity"] == "dramatic" and not PROFILES[profile]["allowDramaticShake"]:
                report.add("error", "chronicle-subtle 不允许 dramatic shake", cue_id=cue_id, beat_id=beat_id)
            if index >= int(PROFILES[profile]["maxActionsPerCue"]):
                report.add("error", "cue 超过当前 profile 的动作预算", cue_id=cue_id, beat_id=beat_id)

    max_cues = max(1, int(len(manifest.beats) * float(PROFILES[profile]["maxCuesPerBeatRatio"]))) if manifest.beats else 0
    if len(plan.get("cues", [])) > max_cues:
        report.add("error", f"cue 数量超过 {profile} 预算：{len(plan.get('cues', []))}>{max_cues}")
    report.semantic_valid = report.errors == 0
    return report


def _duration(value: str) -> int:
    return int(CAPABILITIES["durations"][value])


def _sync_suffix(anchor: str) -> str:
    return " -parallel" if anchor == "during" else " -next"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _asset_for_character(character: str, asset_pack: AssetPack | None) -> str | None:
    return _asset_character_map(asset_pack).get(character, {}).get("asset")


def _compile_action(action: dict[str, Any], anchor: str, asset_pack: AssetPack | None, state: dict[str, Any]) -> list[str]:
    kind = action["kind"]
    suffix = _sync_suffix(anchor)
    if kind == "figure.enter":
        character = action["character"]
        asset = _asset_for_character(character, asset_pack)
        if asset is None:
            return []
        runtime_id = _safe_runtime_id(character)
        framing = figure_base_transform(asset_pack.assets[asset]) if asset_pack is not None else None
        state[character] = {
            "visible": True,
            "slot": action["slot"],
            "runtimeId": runtime_id,
            "asset": asset,
            "framing": framing,
        }
        transform = copy.deepcopy(framing) if framing is not None else {
            "position": {"x": 0, "y": 0},
            "scale": {"x": 1, "y": 1},
        }
        transform["position"]["x"] += CAPABILITIES["slotTransforms"][action["slot"]]["x"]
        duration = _duration(action["duration"])
        motion = action["motion"]
        slot_flag = f" -{action['slot']}" if action["slot"] in ("left", "right") else ""
        if motion == "none":
            return [
                f"changeFigure:{asset}{slot_flag} -duration=0 -id={runtime_id}{suffix};"
            ]
        final = copy.deepcopy(transform)
        final["alpha"] = 1
        return [
            f"changeFigure:{asset}{slot_flag} -repo2galEnter={motion} -duration=0 "
            f"-id={runtime_id} -next;",
            f"setTransform:{_json(final)} -duration={duration} -target={runtime_id}{suffix};",
        ]
    if kind == "figure.exit":
        figure = state.get(action["character"], {})
        runtime_id = figure.get("runtimeId", _safe_runtime_id(action["character"]))
        state.pop(action["character"], None)
        duration = _duration(action["duration"])
        if action["motion"] == "fade":
            if anchor == "during":
                return [
                    f"setTransform:{_json({'alpha': 0})} -duration={duration} "
                    f"-target={runtime_id} -parallel;"
                ]
            return [
                f"setTransform:{_json({'alpha': 0})} -duration={duration} -target={runtime_id} -next;",
                f"changeFigure:none -id={runtime_id} -duration=0{suffix};",
            ]
        return [f"changeFigure:none -id={runtime_id} -duration=0{suffix};"]
    if kind == "figure.move":
        character = action["character"]
        figure = state.get(character, {})
        runtime_id = figure.get("runtimeId", _safe_runtime_id(character))
        state[character] = {**figure, "visible": True, "slot": action["to"], "runtimeId": runtime_id}
        framing = figure.get("framing") or {}
        framing_position = framing.get("position", {})
        slot_position = CAPABILITIES["slotTransforms"][action["to"]]
        transform: dict[str, Any] = {
            "position": {
                "x": slot_position["x"] + framing_position.get("x", 0),
                "y": framing_position.get("y", slot_position["y"]),
            }
        }
        if framing.get("scale"):
            transform["scale"] = framing["scale"]
        return [
            f"setTransform:{_json(transform)} -duration={_duration(action['duration'])} "
            f"-target={runtime_id} -ease={action['easing']}{suffix};"
        ]
    if kind == "figure.shake":
        character = action["character"]
        figure = state.get(character, {})
        runtime_id = figure.get("runtimeId", _safe_runtime_id(character))
        duration = _duration(action["duration"])
        delta = {"subtle": 24, "normal": 48, "dramatic": 80}[action["intensity"]]
        slot_position = CAPABILITIES["slotTransforms"].get(
            figure.get("slot", "center"), CAPABILITIES["slotTransforms"]["center"]
        )
        framing_position = (figure.get("framing") or {}).get("position", {})
        base_x = float(slot_position["x"] + framing_position.get("x", 0))
        base_y = float(framing_position.get("y", slot_position["y"]))
        quarter = max(1, duration // 4)
        keyframes = [
            {"duration": 0, "position": {"x": base_x, "y": base_y}},
            {"duration": quarter, "position": {"x": base_x - delta, "y": base_y}},
            {"duration": quarter, "position": {"x": base_x + delta, "y": base_y}},
            {"duration": quarter, "position": {"x": base_x - delta // 2, "y": base_y}},
            {"duration": quarter, "position": {"x": base_x, "y": base_y}},
        ]
        return [f"setTempAnimation:{_json(keyframes)} -target={runtime_id}{suffix};"]
    if kind == "figure.animate":
        figure = state.get(action["character"], {})
        runtime_id = figure.get("runtimeId", _safe_runtime_id(action["character"]))
        duration = _duration(action["duration"])
        if action["preset"] == "move-front-and-back":
            scale = (figure.get("framing") or {}).get("scale", {"x": 1, "y": 1})
            base_x = float(scale.get("x", 1))
            base_y = float(scale.get("y", 1))
            half = max(1, duration // 2)
            keyframes = [
                {"duration": 0, "scale": {"x": base_x, "y": base_y}},
                {"duration": half, "scale": {"x": round(base_x * 1.06, 3), "y": round(base_y * 1.06, 3)}},
                {"duration": half, "scale": {"x": base_x, "y": base_y}},
            ]
            return [f"setTempAnimation:{_json(keyframes)} -target={runtime_id}{suffix};"]
        if action["preset"] == "shockwaveIn":
            keyframes = [
                {"duration": 0, "shockwaveFilter": 0, "radiusAlphaFilter": 0},
                {"duration": duration, "shockwaveFilter": 3.05, "radiusAlphaFilter": 1.05},
            ]
        else:
            keyframes = [
                {"duration": 0, "shockwaveFilter": 0},
                {"duration": duration, "shockwaveFilter": 3},
            ]
        return [f"setTempAnimation:{_json(keyframes)} -target={runtime_id}{suffix};"]
    if kind == "screen.transition":
        return []
    if kind == "screen.effect":
        return ["pixiInit;", f"pixiPerform:{action['preset']};"]
    return []


def compile_plan(
    plan: dict[str, Any],
    *,
    manifest: BeatManifest,
    asset_pack: AssetPack | None,
) -> list[PerformanceInsertion]:
    beats = _beat_map(manifest)
    state_by_branch: dict[tuple[str, ...], dict[str, dict[str, Any]]] = {}
    story_state_by_branch: dict[tuple[str, ...], dict[str, dict[str, Any]]] = {}
    insertions: list[PerformanceInsertion] = []
    for cue in sorted(plan.get("cues", []), key=lambda item: (beats[item["beatId"]].ordinal, item["id"])):
        beat = beats[cue["beatId"]]
        state = state_by_branch.setdefault(beat.branch_path, {})
        current_story_state = _copy_state(beat.state_before.get("figures", {}))
        _sync_story_figures(
            state,
            story_state_by_branch.get(beat.branch_path),
            current_story_state,
        )
        story_state_by_branch[beat.branch_path] = current_story_state
        lines: list[str] = [f";[repo2gal performance] {cue['id']} {cue['beatId']}"]
        for index, action in enumerate(cue["actions"]):
            if action["kind"] == "screen.transition":
                phase = action["phase"]
                insertions.append(
                    PerformanceInsertion(
                        beat_id=cue["beatId"],
                        anchor="background",
                        ordinal=beat.ordinal,
                        cue_id=cue["id"],
                        action_index=index,
                        lines=(
                            f";[repo2gal performance] {cue['id']} {cue['beatId']}",
                            f"-{phase}={action['preset']}",
                            f"-{phase}Duration={_duration(action['duration'])}",
                        ),
                    )
                )
                continue
            lines.extend(_compile_action(action, cue["anchor"], asset_pack, state))
        if len(lines) > 1:
            insertions.append(
                PerformanceInsertion(
                    beat_id=cue["beatId"],
                    anchor=cue["anchor"],
                    ordinal=beat.ordinal,
                    cue_id=cue["id"],
                    action_index=0,
                    lines=tuple(lines),
                )
            )
    return insertions


def merge_insertions(script: str, insertions: list[PerformanceInsertion], manifest: BeatManifest) -> str:
    beats = {beat.id: beat for beat in manifest.beats}
    before: dict[int, list[PerformanceInsertion]] = {}
    after: dict[int, list[PerformanceInsertion]] = {}
    background: dict[int, list[PerformanceInsertion]] = {}
    for insertion in sorted(insertions, key=lambda item: (item.ordinal, item.anchor, item.cue_id, item.action_index)):
        beat = beats[insertion.beat_id]
        if insertion.anchor == "background":
            if beat.background_statement_index is not None:
                background.setdefault(beat.background_statement_index, []).append(insertion)
            continue
        target_index = beat.statement_index
        (after if insertion.anchor == "after" else before).setdefault(target_index, []).append(insertion)
    output: list[str] = []
    for index, line in enumerate(script.splitlines()):
        for insertion in before.get(index, []):
            output.extend(insertion.lines)
        for insertion in background.get(index, []):
            output.append(insertion.lines[0])
            line = _patch_change_bg(line, insertion.lines[1:])
        output.append(line)
        for insertion in after.get(index, []):
            output.extend(insertion.lines)
    return "\n".join(output) + "\n"


def _patch_change_bg(line: str, args: tuple[str, ...]) -> str:
    stripped = line.strip()
    body = statement_body(stripped).strip()
    if not body.startswith("changeBg:"):
        return line
    for key in ("enter", "exit", "enterDuration", "exitDuration"):
        body = re.sub(rf"\s+-{key}=[^\s;]+", "", body)
    comment = ""
    semicolon = stripped.find(";")
    if semicolon >= 0:
        comment = stripped[semicolon + 1 :]
    return f"{body} {' '.join(args)};" + comment


def compiled_command_count(insertions: Iterable[PerformanceInsertion]) -> int:
    return sum(
        1
        if insertion.anchor == "background"
        else sum(1 for line in insertion.lines if not line.lstrip().startswith(";"))
        for insertion in insertions
    )


def merge_unanchored_baseline(script: str) -> str:
    """无 dialogue/narration beat 时仍启动一个场景生命周期效果。"""
    return ";[repo2gal performance] baseline\npixiInit;\npixiPerform:snow;\n" + script


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
