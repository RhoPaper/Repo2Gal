"""Chronicle 流程编排：唯一持有“先做什么、后做什么”的地方。

设计原则：
- 一条直线：抓取 -> 选角 -> prompt -> 剧本 -> 校验 -> 打包，无循环、无插件；
- 阶段产物显式化：``RunOptions`` 进、``RunArtifacts`` 出；
- 依赖可注入（fetch/llm/package），整个流程可离线端到端测试；
- 所有失败抛统一错误类型，由 CLI 映射退出码；
- validator 是硬边界：任何剧本（LLM 或 --script）打包前必须过 sanitize。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .asset_pack import AssetPack, load_asset_pack
from .config import (
    DEFAULT_BACKGROUNDS,
    DEFAULT_BASE_URL,
    DEFAULT_BGM,
    DEFAULT_LLM_TIMEOUT,
    DEFAULT_MODEL,
)
from .errors import GenerationError, UsageError, ValidationFailed
from .fetcher import RepoContext, fetch_context
from .generator import Cast, build_cast, build_prompt
from .llm import LLMClient
from .packager import package
from .performance import (
    DEFAULT_PROFILE,
    PROFILES,
    PerformanceReport,
    build_performance_prompt,
    build_baseline_plan,
    compile_plan,
    compiled_command_count,
    extract_beats,
    load_plan,
    merge_insertions,
    merge_unanchored_baseline,
    normalize_figure_ids,
    save_json,
    validate_plan,
)
from .validator import Report, sanitize


@dataclass
class RunOptions:
    """一次运行的完整输入。由 CLI 组装，pipeline 只读取。"""

    owner: str
    repo: str
    output_dir: Path
    backup_root: Path
    reuse_backup: bool = False
    organization: bool = False
    top_threads: int = 12
    token: str | None = None
    script: Path | None = None
    dry_run: bool = False
    strict: bool = False
    save_prompt: Path | None = None
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    api_key: str | None = None
    llm_timeout: int = DEFAULT_LLM_TIMEOUT
    asset_pack: Path | str | None = None
    public_assets: bool = False
    performance: bool = False
    performance_profile: str = DEFAULT_PROFILE
    strict_performance: bool = False
    save_beat_manifest: Path | None = None
    save_performance_plan: Path | None = None
    save_performance_report: Path | None = None


@dataclass
class RunArtifacts:
    """一次运行的全部阶段产物。

    dry-run 不带脚本时 ``raw/clean/report`` 为空（尚未生成剧本）；
    其余路径三者齐备。``output_dir`` 只在完整打包后非空。
    """

    ctx: RepoContext
    cast: Cast
    prompt: str
    raw: str
    clean: str
    report: Report | None
    output_dir: Path | None = None
    asset_pack: AssetPack | None = None
    beat_manifest: dict | None = None
    performance_plan: dict | None = None
    performance_report: PerformanceReport | None = None


def _read_script(path: Path) -> str:
    """严格读取 --script 文件；路径问题属于用法错误。"""
    if path.is_symlink():
        raise UsageError(f"--script 不接受符号链接：{path}")
    if not path.is_file():
        raise UsageError(f"脚本文件不存在：{path}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise UsageError(f"无法按 UTF-8 读取脚本：{path}（{exc}）") from exc


def _save_prompt(path: Path, prompt: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(prompt, encoding="utf-8")
    except OSError as exc:
        raise UsageError(f"无法写入 prompt：{path}（{exc}）") from exc


def _save_json(path: Path, value: object) -> None:
    try:
        save_json(path, value)
    except OSError as exc:
        raise UsageError(f"无法写入审计 JSON：{path}（{exc}）") from exc


def _merge_fallback(
    script: str,
    insertions,
    manifest,
) -> tuple[str, int]:
    if insertions:
        return merge_insertions(script, insertions, manifest), compiled_command_count(insertions)
    return merge_unanchored_baseline(script), 2


def _default_fetch(options: RunOptions, log: Callable, progress: Callable) -> RepoContext:
    return fetch_context(
        options.owner,
        options.repo,
        backup_root=options.backup_root,
        token=options.token,
        organization=options.organization,
        top_threads=options.top_threads,
        reuse_backup=options.reuse_backup,
        log=log,
        progress=progress,
    )


def run_pipeline(
    options: RunOptions,
    *,
    llm_client: LLMClient | None = None,
    fetch_fn: Callable[[RunOptions, Callable, Callable], RepoContext] | None = None,
    package_fn=None,
    log=lambda _m: None,
    warn=lambda _m: None,
    progress=lambda _m: None,
) -> RunArtifacts:
    """按模式矩阵执行全部阶段，返回各阶段产物。"""

    audit_paths = (
        options.save_beat_manifest,
        options.save_performance_plan,
        options.save_performance_report,
    )
    if any(audit_paths) and not options.performance:
        raise UsageError("性能审计 JSON 参数必须与 --performance 一起使用")
    if options.strict_performance and not options.performance:
        raise UsageError("--strict-performance 必须与 --performance 一起使用")
    if options.performance_profile not in PROFILES:
        raise UsageError(f"未知动态演出 profile：{options.performance_profile}")

    # --- 阶段 0：本地素材包先校验，避免无效输入触发慢速采集或付费 LLM ---
    if options.public_assets and options.asset_pack is None:
        raise UsageError("--public-assets 必须与 --asset-pack 一起使用")
    asset_pack = (
        load_asset_pack(options.asset_pack, public=options.public_assets)
        if options.asset_pack is not None
        else None
    )
    if asset_pack is not None:
        log(f"素材包校验通过：{asset_pack.name}@{asset_pack.version}")

    # --- 阶段 1：抓取（在线采集或复用离线备份） ---
    ctx = (fetch_fn or _default_fetch)(options, log, progress)

    # --- 阶段 2：确定性选角 ---
    cast = build_cast(ctx)
    log(f"角色表：{'、'.join(sorted(cast.names))}")

    # --- 阶段 3：prompt 组装与保存 ---
    prompt = (
        build_prompt(
            ctx,
            cast,
            backgrounds=DEFAULT_BACKGROUNDS + asset_pack.logical_ids("background"),
            figures=asset_pack.logical_ids("character"),
            bgm=DEFAULT_BGM + asset_pack.logical_ids("bgm"),
        )
        if asset_pack is not None
        else build_prompt(ctx, cast)
    )
    if options.save_prompt:
        _save_prompt(options.save_prompt, prompt)
        log(f"prompt 已保存至 {options.save_prompt}（{len(prompt)} 字）")

    # --- 阶段 4：dry-run 不带脚本：到此为止（CLI 渲染 prompt） ---
    if options.dry_run and options.script is None:
        return RunArtifacts(
            ctx=ctx,
            cast=cast,
            prompt=prompt,
            raw="",
            clean="",
            report=None,
            output_dir=None,
            asset_pack=asset_pack,
        )

    # --- 阶段 5：剧本来源（现成脚本或 LLM） ---
    if options.script is not None:
        raw = _read_script(options.script)
        log(f"使用现成脚本 {options.script}")
    else:
        client = llm_client or LLMClient(
            base_url=options.base_url,
            model=options.model,
            api_key=options.api_key,
            timeout=options.llm_timeout,
        )
        log("调用 LLM 生成剧本，可能需要一两分钟")
        raw = client.complete(prompt)
        log(f"LLM 返回 {len(raw.splitlines())} 行")

    # --- 阶段 6：校验（不可绕过的硬边界） ---
    if asset_pack is not None:
        asset_catalog = asset_pack.command_catalog()
        asset_catalog["changeBg"] |= frozenset(DEFAULT_BACKGROUNDS)
        asset_catalog["bgm"] |= frozenset(DEFAULT_BGM)
    else:
        asset_catalog = {
            "changeBg": frozenset(DEFAULT_BACKGROUNDS),
            "changeFigure": frozenset(),
            "bgm": frozenset(DEFAULT_BGM),
        }
    clean, report = sanitize(raw, speakers=cast.names, assets=asset_catalog)
    log(report.summary())
    for finding in report.findings:
        if finding.kind in ("downgrade", "warn"):
            warn(f"第 {finding.line_no} 行：{finding.message}")
    if options.strict and report.downgrades:
        raise ValidationFailed(f"strict 模式：存在 {report.downgrades} 处降级")

    # --- 阶段 7：可选动态演出（失败默认不影响已校验剧情） ---
    performance_script = clean
    beat_manifest = None
    performance_plan = None
    performance_report = None
    if options.performance:
        performance_script = normalize_figure_ids(clean, asset_pack)
        manifest = extract_beats(
            performance_script,
            speakers=cast.names,
            asset_pack=asset_pack,
        )
        beat_manifest = manifest.to_dict()
        if options.save_beat_manifest:
            _save_json(options.save_beat_manifest, beat_manifest)

        performance_report = PerformanceReport(story_hash=manifest.story_hash)
        performance_prompt = build_performance_prompt(
            manifest,
            profile=options.performance_profile,
        )
        log("调用 LLM 生成动态演出计划")
        try:
            performance_raw = (llm_client or LLMClient(
                base_url=options.base_url,
                model=options.model,
                api_key=options.api_key,
                timeout=options.llm_timeout,
            )).complete(performance_prompt, temperature=0.2)
            performance_plan = load_plan(
                performance_raw,
                report=performance_report,
                story_hash=manifest.story_hash,
                scene_id=manifest.scene_id,
                profile=options.performance_profile,
            )
        except GenerationError as exc:
            performance_report.add("error", f"动态演出 LLM 调用失败，已回退剧情：{exc}")
            performance_raw = ""
            performance_plan = None
        if options.save_performance_plan:
            _save_json(
                options.save_performance_plan,
                performance_plan if performance_plan is not None else {"raw": performance_raw},
            )
        if performance_plan is not None:
            parse_findings = list(performance_report.findings)
            parse_degraded = performance_report.degraded
            performance_report = validate_plan(
                performance_plan,
                manifest=manifest,
                asset_pack=asset_pack,
                profile=options.performance_profile,
            )
            performance_report.findings = parse_findings + performance_report.findings
            performance_report.degraded = parse_degraded or performance_report.degraded
            if performance_report.semantic_valid:
                insertions = compile_plan(
                    performance_plan,
                    manifest=manifest,
                    asset_pack=asset_pack,
                )
                performance_report.compiled_command_count = compiled_command_count(insertions)
                performance_script = merge_insertions(
                    performance_script,
                    insertions,
                    manifest,
                )
                if not insertions:
                    performance_report.degraded = True
                    fallback_plan = build_baseline_plan(
                        manifest,
                        profile=options.performance_profile,
                    )
                    fallback_report = validate_plan(
                        fallback_plan,
                        manifest=manifest,
                        asset_pack=asset_pack,
                        profile=options.performance_profile,
                    )
                    if fallback_report.semantic_valid:
                        performance_report.add(
                            "warn",
                            "LLM 返回空演出计划，已使用最低确定性演出 fallback",
                        )
                        fallback_insertions = compile_plan(
                            fallback_plan,
                            manifest=manifest,
                            asset_pack=asset_pack,
                        )
                        performance_script, performance_report.compiled_command_count = _merge_fallback(
                            performance_script,
                            fallback_insertions,
                            manifest,
                        )
            else:
                performance_report.degraded = True
                fallback_plan = build_baseline_plan(
                    manifest,
                    profile=options.performance_profile,
                )
                fallback_report = validate_plan(
                    fallback_plan,
                    manifest=manifest,
                    asset_pack=asset_pack,
                    profile=options.performance_profile,
                )
                if fallback_report.semantic_valid:
                    performance_report.add(
                        "warn",
                        "LLM 演出计划无效，已保留剧情并使用最低确定性演出 fallback",
                    )
                    fallback_insertions = compile_plan(
                        fallback_plan,
                        manifest=manifest,
                        asset_pack=asset_pack,
                    )
                    performance_script, performance_report.compiled_command_count = _merge_fallback(
                        performance_script,
                        fallback_insertions,
                        manifest,
                    )
        else:
            performance_report.degraded = True
            fallback_plan = build_baseline_plan(
                manifest,
                profile=options.performance_profile,
            )
            fallback_report = validate_plan(
                fallback_plan,
                manifest=manifest,
                asset_pack=asset_pack,
                profile=options.performance_profile,
            )
            if fallback_report.semantic_valid:
                performance_report.add(
                    "warn",
                    "LLM 未返回可用演出计划，已保留剧情并使用最低确定性演出 fallback",
                )
                fallback_insertions = compile_plan(
                    fallback_plan,
                    manifest=manifest,
                    asset_pack=asset_pack,
                )
                performance_script, performance_report.compiled_command_count = _merge_fallback(
                    performance_script,
                    fallback_insertions,
                    manifest,
                )
        if performance_report is None:
            performance_report = PerformanceReport(story_hash=manifest.story_hash)
        log(performance_report.summary())
        if options.save_performance_report:
            _save_json(options.save_performance_report, performance_report.to_dict())
        if options.strict_performance and performance_report.degraded:
            raise ValidationFailed("strict-performance：动态演出计划校验失败")

    # --- 阶段 8：dry-run 带脚本：只校验不打包（CLI 渲染报告） ---
    if options.dry_run:
        return RunArtifacts(
            ctx=ctx,
            cast=cast,
            prompt=prompt,
            raw=raw,
            clean=performance_script,
            report=report,
            output_dir=None,
            asset_pack=asset_pack,
            beat_manifest=beat_manifest,
            performance_plan=performance_plan,
            performance_report=performance_report,
        )

    # --- 阶段 9：打包 ---
    output_dir = (package_fn or package)(
        performance_script,
        options.output_dir,
        game_name=f"{ctx.full_name} 编年史",
        game_key=f"repo2gal_{options.owner}_{options.repo}",
        asset_pack=asset_pack,
        log=log,
    )
    return RunArtifacts(
        ctx=ctx,
        cast=cast,
        prompt=prompt,
        raw=raw,
        clean=performance_script,
        report=report,
        output_dir=output_dir,
        asset_pack=asset_pack,
        beat_manifest=beat_manifest,
        performance_plan=performance_plan,
        performance_report=performance_report,
    )
