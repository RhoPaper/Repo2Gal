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
from .errors import UsageError, ValidationFailed
from .fetcher import RepoContext, fetch_context
from .generator import Cast, build_cast, build_prompt
from .llm import LLMClient
from .packager import package
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

    # --- 阶段 7：dry-run 带脚本：只校验不打包（CLI 渲染报告） ---
    if options.dry_run:
        return RunArtifacts(
            ctx=ctx,
            cast=cast,
            prompt=prompt,
            raw=raw,
            clean=clean,
            report=report,
            output_dir=None,
            asset_pack=asset_pack,
        )

    # --- 阶段 8：打包 ---
    output_dir = (package_fn or package)(
        clean,
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
        clean=clean,
        report=report,
        output_dir=output_dir,
        asset_pack=asset_pack,
    )
