"""repo2gal 命令行入口：参数解析与结果渲染。

流程编排全部在 ``pipeline.py``；本文件只做三件事：
1. 把 CLI 参数映射为 ``RunOptions``；
2. 调用流水线并转发进度/日志回调；
3. 按统一错误类型的 exit_code 退出，未预期异常兜底 exit 1。
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import click

from .config import (
    DEFAULT_LLM_TIMEOUT,
    default_backup_root,
    default_output_dir,
    resolve_api_key,
    resolve_base_url,
    resolve_github_token,
    resolve_model,
)
from .errors import Repo2GalError
from .fetcher import parse_repo
from .pipeline import RunOptions, run_pipeline


def _log(msg: str) -> None:
    click.echo(click.style("·", fg="cyan") + f" {msg}")


def _warn(msg: str) -> None:
    click.echo(click.style("!", fg="yellow") + f" {msg}")


def _progress(msg: str) -> None:
    click.echo(click.style("  ↳", fg="blue") + f" {msg}")


def _die(msg: str, code: int) -> None:
    click.echo(click.style("✗ ", fg="red") + msg, err=True)
    sys.exit(code)


@click.command()
@click.argument("repo")
@click.option("--output", "-o", default=None, type=click.Path(), help="产物目录，默认 ./output/<repo>")
@click.option("--model", default=None, help="模型名，默认取 REPO2GAL_MODEL 或 deepseek-v4-pro")
@click.option("--base-url", default=None, help="OpenAI 兼容端点，默认取 REPO2GAL_BASE_URL")
@click.option("--threads", default=12, show_default=True, help="从全量备份中选入上下文的热门讨论数")
@click.option(
    "--backup-dir",
    type=click.Path(),
    default=None,
    help="python-github-backup 原始数据目录，默认 .repo2gal/backups/<owner>",
)
@click.option("--reuse-backup", is_flag=True, help="不联网，复用 --backup-dir 中的已有备份")
@click.option("--organization", is_flag=True, help="目标 owner 是 GitHub Organization")
@click.option("--dry-run", is_flag=True, help="只抓数据并打印 prompt，不调用 LLM")
@click.option("--script", type=click.Path(path_type=Path), help="跳过 LLM，改用现成脚本文件")
@click.option("--save-prompt", type=click.Path(), help="把 prompt 存盘，便于调试")
@click.option("--strict", is_flag=True, help="validator 有降级即判失败")
@click.option("--timeout", default=DEFAULT_LLM_TIMEOUT, show_default=True, help="LLM 请求超时（秒）")
def main(
    repo,
    output,
    model,
    base_url,
    threads,
    backup_dir,
    reuse_backup,
    organization,
    dry_run,
    script,
    save_prompt,
    strict,
    timeout,
):
    """把 GitHub 仓库变成可游玩的 WebGAL 视觉小说。

    \b
    示例：
      repo2gal vuejs/core
      repo2gal https://github.com/OpenWebGAL/WebGAL --dry-run
      repo2gal vuejs/core --reuse-backup --script my_story.txt
    """
    try:
        owner, name = parse_repo(repo)
    except Repo2GalError as exc:
        _die(str(exc), exc.exit_code)

    options = RunOptions(
        owner=owner,
        repo=name,
        output_dir=Path(output) if output else default_output_dir(name),
        backup_root=Path(backup_dir) if backup_dir else default_backup_root(owner),
        reuse_backup=reuse_backup,
        organization=organization,
        top_threads=threads,
        token=resolve_github_token(),
        script=Path(script) if script else None,
        dry_run=dry_run,
        strict=strict,
        save_prompt=Path(save_prompt) if save_prompt else None,
        base_url=resolve_base_url(base_url),
        model=resolve_model(model),
        api_key=resolve_api_key(),
        llm_timeout=timeout,
    )

    try:
        artifacts = run_pipeline(options, log=_log, warn=_warn, progress=_progress)
    except Repo2GalError as exc:
        _die(str(exc), exc.exit_code)
    except Exception as exc:  # 兜底：未预期异常保持可调试，退出码 1
        traceback.print_exc()
        _die(f"内部错误：{type(exc).__name__}: {exc}", 1)

    if artifacts.output_dir is None:
        # dry-run 两种形态：只打印 prompt，或只打印校验报告
        if artifacts.report is None:
            click.echo("\n" + "─" * 60)
            click.echo(artifacts.prompt)
            click.echo("─" * 60)
            _log(f"dry-run 结束，prompt 共 {len(artifacts.prompt)} 字")
        else:
            _log(f"dry-run 校验结束：{artifacts.report.summary()}")
        return

    click.echo()
    click.echo(click.style("✓ 完成！", fg="green", bold=True))
    click.echo(f"  本地预览：python3 -m http.server -d {artifacts.output_dir} 8000")
    click.echo("  然后打开 http://localhost:8000")


if __name__ == "__main__":
    main()
