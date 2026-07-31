"""repo2gal 命令行入口。"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from .fetcher import FetchError, GitHubClient, fetch_context, parse_repo
from .generator import GenerationError, build_cast, build_prompt, call_llm
from .packager import PackageError, package
from .validator import sanitize


def _log(msg: str) -> None:
    click.echo(click.style("·", fg="cyan") + f" {msg}")


def _warn(msg: str) -> None:
    click.echo(click.style("!", fg="yellow") + f" {msg}")


def _die(msg: str, code: int) -> None:
    click.echo(click.style("✗ ", fg="red") + msg, err=True)
    sys.exit(code)


@click.command()
@click.argument("repo")
@click.option("--output", "-o", default=None, type=click.Path(), help="产物目录，默认 ./output/<repo>")
@click.option("--model", default=None, help="模型名，默认取 REPO2GAL_MODEL 或 gpt-4o")
@click.option("--base-url", default=None, help="OpenAI 兼容端点，默认取 REPO2GAL_BASE_URL")
@click.option("--threads", default=12, show_default=True, help="抓取的热门 Issue/PR 条数")
@click.option("--dry-run", is_flag=True, help="只抓数据并打印 prompt，不调用 LLM")
@click.option("--script", type=click.Path(exists=True), help="跳过 LLM，改用现成脚本文件")
@click.option("--save-prompt", type=click.Path(), help="把 prompt 存盘，便于调试")
@click.option("--strict", is_flag=True, help="validator 有降级即判失败")
def main(repo, output, model, base_url, threads, dry_run, script, save_prompt, strict):
    """把 GitHub 仓库变成可游玩的 WebGAL 视觉小说。

    \b
    示例：
      repo2gal vuejs/core
      repo2gal https://github.com/OpenWebGAL/WebGAL --dry-run
    """
    try:
        owner, name = parse_repo(repo)
    except FetchError as exc:
        _die(str(exc), 2)

    out_dir = Path(output) if output else Path("output") / name

    # --- 1. 抓取 ---
    try:
        gh = GitHubClient()
        if not gh.authenticated:
            _warn("未设置 GITHUB_TOKEN，匿名配额 60 次/小时，容易触顶")
        ctx = fetch_context(owner, name, client=gh, top_threads=threads, log=_log)
    except FetchError as exc:
        _die(f"抓取失败：{exc}", 3)

    # --- 2. 构造 prompt ---
    cast = build_cast(ctx)
    _log(f"角色表：{'、'.join(sorted(cast.names))}")
    prompt = build_prompt(ctx, cast)

    if save_prompt:
        Path(save_prompt).write_text(prompt, encoding="utf-8")
        _log(f"prompt 已保存至 {save_prompt}（{len(prompt)} 字）")

    if dry_run:
        click.echo("\n" + "─" * 60)
        click.echo(prompt)
        click.echo("─" * 60)
        _log(f"dry-run 结束，prompt 共 {len(prompt)} 字")
        return

    # --- 3. 生成剧本 ---
    if script:
        raw = Path(script).read_text(encoding="utf-8")
        _log(f"使用现成脚本 {script}")
    else:
        _log("调用 LLM 生成剧本，可能需要一两分钟")
        try:
            raw = call_llm(prompt, model=model, base_url=base_url)
        except GenerationError as exc:
            _die(f"生成失败：{exc}", 4)
        _log(f"LLM 返回 {len(raw.splitlines())} 行")

    # --- 4. 校验降级 ---
    clean, report = sanitize(raw, speakers=cast.names)
    _log(report.summary())
    for f in report.findings:
        if f.kind in ("downgrade", "warn"):
            _warn(f"第 {f.line_no} 行：{f.message}")

    if strict and report.downgrades:
        _die(f"strict 模式：存在 {report.downgrades} 处降级", 5)

    # --- 5. 打包 ---
    try:
        result = package(
            clean,
            out_dir,
            game_name=f"{ctx.full_name} 编年史",
            game_key=f"repo2gal_{owner}_{name}",
            log=_log,
        )
    except PackageError as exc:
        _die(f"打包失败：{exc}", 6)

    click.echo()
    click.echo(click.style("✓ 完成！", fg="green", bold=True))
    click.echo(f"  本地预览：python3 -m http.server -d {result} 8000")
    click.echo("  然后打开 http://localhost:8000")


if __name__ == "__main__":
    main()
