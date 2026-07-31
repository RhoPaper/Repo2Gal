"""validator 的行为约束。

这些用例锁的是「WebGAL 静默错渲染」这一类问题，
每条都对应 docs/dev/webgal-script-reference.md 里核实过的解析器行为。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from repo2gal.validator import sanitize  # noqa: E402
from repo2gal.webgal import statement_body  # noqa: E402


def run(raw, **kw):
    return sanitize(raw, **kw)


def test_hallucinated_command_downgraded():
    """LLM 幻觉命令必须降级，否则会变成一个叫 showCode 的角色在说话。"""
    out, rep = run("showCode:print(1);\n")
    assert "showCode:" not in out
    assert "say:print(1);" in out
    assert rep.downgrades == 1


def test_declared_speaker_kept():
    out, _ = run("Reactive:我是响应式精灵;\nend;\n", speakers={"Reactive"})
    assert "Reactive:我是响应式精灵;" in out


def test_undeclared_ascii_speaker_downgraded():
    """未声明的 ASCII 名字与幻觉命令无法区分，一律降级。"""
    out, rep = run("Mystery:你好;\nend;\n", speakers=set())
    assert "say:你好;" in out
    assert rep.downgrades == 1


def test_cjk_speaker_passes_with_note():
    out, rep = run("尤雨溪:那就重写吧;\nend;\n", speakers=set())
    assert "尤雨溪:那就重写吧;" in out
    assert any(f.kind == "note" for f in rep.findings)


def test_known_but_unsafe_command_downgraded():
    """pixiPerform 是真命令，但不在安全子集里。"""
    out, rep = run("pixiPerform:snow;\nend;\n")
    assert "pixiPerform" not in out
    assert rep.downgrades == 1


def test_code_fence_and_markdown_stripped():
    out, _ = run("```webgal\nsay:你好;\n```\n## 第一章\n---\nend;\n")
    assert "```" not in out
    assert "## 第一章" not in out
    assert "---" not in out
    assert "say:你好;" in out


def test_missing_semicolon_added():
    out, _ = run("say:没有分号\nend;\n")
    assert "say:没有分号;" in out


def test_end_appended_when_absent():
    out, rep = run("say:结尾没有 end;\n")
    assert out.rstrip().endswith("end;")
    assert any(f.kind == "fix" for f in rep.findings)


def test_end_not_duplicated():
    out, _ = run("say:你好;\nend;\n")
    assert out.count("end;") == 1


def test_dangling_jump_commented_out():
    out, rep = run("jumpLabel:nowhere;\nend;\n")
    assert out.splitlines()[0].startswith(";[repo2gal]")
    assert rep.downgrades == 1


def test_valid_jump_preserved():
    out, rep = run("jumpLabel:ch2;\nlabel:ch2;\nsay:到了;\nend;\n")
    assert "jumpLabel:ch2;" in out
    assert rep.downgrades == 0


def test_choose_targets_validated():
    raw = "choose:选A:a|选B:missing;\nlabel:a;\nsay:A;\nend;\n"
    out, rep = run(raw)
    assert out.splitlines()[0].startswith(";[repo2gal]")
    assert rep.downgrades == 1


def test_choose_with_conditions_parsed():
    raw = "choose:(v==true)->可见:ok|[p>1]->能量:ok;\nlabel:ok;\nsay:x;\nend;\n"
    out, rep = run(raw)
    assert "choose:" in out.splitlines()[0]
    assert rep.downgrades == 0


def test_choose_scene_file_target_allowed():
    """含 '.' 的目标是场景文件，不该按 label 校验。"""
    out, rep = run("choose:继续:next.txt;\nend;\n")
    assert rep.downgrades == 0


def test_continuous_dialogue_line_kept():
    """没有冒号的行是「连续对话」，引擎行为安全。"""
    out, rep = run("这是一句没有冒号的旁白\nend;\n")
    assert "这是一句没有冒号的旁白;" in out
    assert rep.downgrades == 0


def test_arg_region_warning():
    """正文里的 ' -' 会被当成参数区，且 WebGAL 没有 \\- 转义。"""
    _, rep = run("say:这是 -个陷阱;\nend;\n")
    assert any(f.kind == "warn" for f in rep.findings)


def test_inline_comment_preserved():
    out, _ = run("changeBg:bg.webp; // 切背景\nend;\n")
    assert "changeBg:bg.webp;" in out


def test_leading_semicolon_comment_kept():
    out, _ = run(";这是注释\nend;\n")
    assert ";这是注释" in out


def test_statement_body_respects_escape():
    assert statement_body("say:a\\;b;注释") == "say:a\\;b"
