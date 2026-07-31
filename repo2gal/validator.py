"""WebGAL 脚本校验与降级。

存在的理由：WebGAL 遇到不认识的命令**不会报错**，而是把命令名当作角色名、
把余下内容当作台词渲染出来（见 commandParser.ts 的 `?? commandType.say`）。
所以 LLM 幻觉出的 `showCode:print(1);` 会变成一个叫 showCode 的角色在说话，
产物永远"能跑"却处处错渲染，靠肉眼玩游戏去发现的成本极高。

本模块在生成之后、打包之前把脚本收敛到白名单子集内：
不认识的一律降级为旁白，绝不放行。遵循 v5 文档的 Rule 2 ——
解析失败降级成旁白，永不抛异常中断构建。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .webgal import KNOWN_COMMANDS, SAFE_COMMANDS, statement_body

#: 形似命令的 ASCII 标识符（camelCase / snake_case），用于识别 LLM 幻觉命令。
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: Markdown 代码围栏，LLM 极爱用它包裹输出。
_FENCE = re.compile(r"^\s*```")

#: 纯 Markdown 噪声行：标题、水平线、列表符号。
_MD_NOISE = re.compile(r"^\s*(#{1,6}\s|---+\s*$|\*\*\*+\s*$)")


@dataclass
class Finding:
    """一次修改记录。"""

    line_no: int
    kind: str
    message: str
    before: str
    after: str | None


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def add(self, line_no: int, kind: str, message: str, before: str, after: str | None) -> None:
        self.findings.append(Finding(line_no, kind, message, before, after))

    @property
    def downgrades(self) -> int:
        return sum(1 for f in self.findings if f.kind == "downgrade")

    def summary(self) -> str:
        if not self.findings:
            return "校验通过，无改动。"
        buckets: dict[str, int] = {}
        for f in self.findings:
            buckets[f.kind] = buckets.get(f.kind, 0) + 1
        parts = [f"{k}×{v}" for k, v in sorted(buckets.items())]
        return "校验完成：" + "，".join(parts)


def _split_command(body: str) -> tuple[str | None, str]:
    """按第一个冒号切出命令区与内容区。

    对应 scriptParser.ts 的 `/:/.exec()` —— 注意引擎在这一步**不认转义**，
    所以正文里的第一个冒号一样会被当作分隔符。
    """
    idx = body.find(":")
    if idx < 0:
        return None, body
    return body[:idx], body[idx + 1 :]


def sanitize(
    raw: str,
    *,
    speakers: set[str] | None = None,
    allowed: frozenset[str] = SAFE_COMMANDS,
) -> tuple[str, Report]:
    """把 LLM 原始输出收敛成安全的 WebGAL 脚本。

    Args:
        raw: LLM 原文。
        speakers: 允许出现的角色名白名单（我们在 prompt 里声明过的那批）。
            ASCII 角色名必须在此列出，否则会被当成幻觉命令降级。
        allowed: 允许的命令白名单。

    Returns:
        (清洗后的脚本, 报告)
    """
    speakers = speakers or set()
    report = Report()
    out: list[str] = []
    labels: set[str] = set()
    jumps: list[tuple[int, str, int]] = []  # (行号, 目标, out 索引)

    for line_no, original in enumerate(raw.splitlines(), start=1):
        line = original.rstrip()
        stripped = line.strip()

        if not stripped:
            out.append("")
            continue

        if _FENCE.match(line):
            report.add(line_no, "strip", "移除 Markdown 代码围栏", original, None)
            continue

        if _MD_NOISE.match(line):
            report.add(line_no, "strip", "移除 Markdown 噪声行", original, None)
            continue

        if stripped.startswith(";"):
            out.append(stripped)  # 已经是注释，原样保留
            continue

        body = statement_body(stripped).strip()
        if not body:
            out.append(stripped)
            continue

        cmd, content = _split_command(body)

        # --- 情形 1：没有冒号 -> 引擎视为「连续对话」，安全 ---
        if cmd is None:
            out.append(f"{body};")
            continue

        cmd = cmd.strip()

        # --- 情形 2：白名单命令 ---
        if cmd in allowed:
            if cmd == "label":
                labels.add(content.strip())
            elif cmd == "jumpLabel":
                target = content.split(" -")[0].strip()
                jumps.append((line_no, target, len(out)))
            elif cmd == "choose":
                for target in _choose_targets(content):
                    jumps.append((line_no, target, len(out)))
            if " -" in content and cmd in ("say",):
                report.add(
                    line_no,
                    "warn",
                    "旁白正文含 ' -'，会被解析成参数区且无法转义",
                    original,
                    None,
                )
            out.append(f"{body};")
            continue

        # --- 情形 3：已知但不在白名单的命令 -> 降级 ---
        if cmd in KNOWN_COMMANDS:
            safe = f"say:{content.strip()};"
            report.add(
                line_no,
                "downgrade",
                f"命令 '{cmd}' 不在安全子集内，降级为旁白",
                original,
                safe,
            )
            out.append(safe)
            continue

        # --- 情形 4：声明过的角色 -> 正常对话 ---
        if cmd in speakers:
            if " -" in content:
                report.add(
                    line_no,
                    "warn",
                    "台词含 ' -'，会被解析成参数区且无法转义",
                    original,
                    None,
                )
            out.append(f"{body};")
            continue

        # --- 情形 5：形似命令的 ASCII 标识符 -> 判定为幻觉命令，降级 ---
        if _IDENTIFIER.match(cmd):
            safe = f"say:{content.strip()};"
            report.add(
                line_no,
                "downgrade",
                f"未知命令 '{cmd}' 会被引擎误当成角色名，降级为旁白",
                original,
                safe,
            )
            out.append(safe)
            continue

        # --- 情形 6：非 ASCII（多半是中文角色名）-> 当对话放行，但记一笔 ---
        report.add(
            line_no,
            "note",
            f"'{cmd}' 未在角色表中声明，按对话处理",
            original,
            None,
        )
        out.append(f"{body};")

    _repair_jumps(out, labels, jumps, report)
    _ensure_end(out, report)
    return "\n".join(out) + "\n", report


def _choose_targets(content: str) -> list[str]:
    """抽出 choose 的全部跳转目标。

    语法：`选项:目标|选项:目标 -defaultChoose=1`
    选项部分可能带 `(显示条件)->` 或 `[启用条件]->` 前缀。
    """
    content = content.split(" -")[0]
    targets: list[str] = []
    for part in re.split(r"(?<!\\)\|", content):
        segs = re.split(r"(?<!\\):", part)
        if len(segs) >= 2:
            targets.append(segs[1].strip())
    return targets


def _repair_jumps(
    out: list[str],
    labels: set[str],
    jumps: list[tuple[int, str, int]],
    report: Report,
) -> None:
    """跳转目标解析不到 label 时，注释掉该行避免玩家卡死。

    含 '.' 的目标会被引擎当成场景文件而非 label，这里一并放行。
    """
    for line_no, target, idx in jumps:
        if not target or target in labels or "." in target:
            continue
        before = out[idx]
        out[idx] = f";[repo2gal] 跳转目标 '{target}' 不存在，已注释：{before}"
        report.add(
            line_no,
            "downgrade",
            f"跳转目标 '{target}' 未定义，注释该行以免流程断死",
            before,
            out[idx],
        )


def _ensure_end(out: list[str], report: Report) -> None:
    """保证脚本以 end; 收尾，否则播放到底会卡住。"""
    for line in reversed(out):
        if line.strip():
            if statement_body(line.strip()).strip() == "end":
                return
            break
    out.append("end;")
    report.add(len(out), "fix", "脚本缺少 end;，已补齐", "", "end;")
