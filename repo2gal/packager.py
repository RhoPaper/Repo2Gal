"""WebGAL 产物打包。

策略：克隆官方发行版模板，覆盖 game/ 下的脚本与配置。
不修改引擎源码，不依赖任何 WebGAL CLI（那玩意儿不存在：
npm 上 `webgal` 是 0.0.0 占位包，OpenWebGAL/WebGAL-Server 已于 2022 年归档）。

两个可靠性保证：
1. 模板下载校验 SHA-256 后解压到临时目录，再原子替换缓存；
2. 产物先在输出同父目录 staging，完成后原子替换旧产物，失败保留旧产物。

流程图（flowchart.json）由确定性代码生成最小版本（仅 start.txt 节点），
替换官方模板中引用 demo 场景的版本，保证游戏内可正常打开。
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

import requests

from .config import webgal_cache_dir as cache_dir
from .errors import PackageError, redact_error

WEBGAL_VERSION = "4.6.2"
WEBGAL_ASSET = f"WebGAL-{WEBGAL_VERSION}-web.zip"
WEBGAL_URL = (
    f"https://github.com/OpenWebGAL/WebGAL/releases/download/{WEBGAL_VERSION}/{WEBGAL_ASSET}"
)
WEBGAL_SHA256 = "299a18b8e0e4a9bc48e659fe50a3a640c71743ed11647acb81a9384149ff9355"


def ensure_template(*, log=lambda _m: None) -> Path:
    """下载并缓存 WebGAL 发行版模板，返回模板根目录。"""
    dest = cache_dir() / f"webgal-{WEBGAL_VERSION}"
    marker = dest / "index.html"
    if marker.exists():
        log(f"复用已缓存模板 {marker.parent}")
        return marker.parent

    log(f"下载固定版本 {WEBGAL_ASSET}（仅首次）")
    try:
        blob = requests.get(WEBGAL_URL, timeout=600, stream=True)
    except requests.RequestException as exc:
        raise PackageError(f"模板下载失败：{redact_error(str(exc))}") from exc
    if not blob.ok:
        raise PackageError(f"模板下载失败：HTTP {blob.status_code}")

    total = int(blob.headers.get("Content-Length", 0))
    downloaded = 0
    next_report = 0
    content = io.BytesIO()
    checksum = hashlib.sha256()
    for chunk in blob.iter_content(chunk_size=1024 * 1024):
        if not chunk:
            continue
        content.write(chunk)
        checksum.update(chunk)
        downloaded += len(chunk)
        if total:
            percent = min(100, downloaded * 100 // total)
            if percent >= next_report:
                log(f"WebGAL 下载进度：{percent}%（{downloaded / 1024 / 1024:.1f} MB）")
                next_report = percent + 10
        elif downloaded // (10 * 1024 * 1024) >= next_report:
            log(f"WebGAL 已下载：{downloaded / 1024 / 1024:.1f} MB")
            next_report += 1

    digest = checksum.hexdigest()
    if digest != WEBGAL_SHA256:
        raise PackageError(f"模板 SHA-256 不匹配：期望 {WEBGAL_SHA256}，实际 {digest}")

    # 解压到缓存同父目录的 staging，校验结构后原子替换缓存，避免留下半个模板。
    staging = Path(
        tempfile.mkdtemp(prefix=f".webgal-{WEBGAL_VERSION}.staging-", dir=str(dest.parent))
    )
    try:
        content.seek(0)
        with zipfile.ZipFile(content) as zf:
            zf.extractall(staging)

        # 压缩包可能多包一层目录，把 index.html 所在层拎出来
        if not (staging / "index.html").exists():
            found = next(iter(sorted(staging.glob("*/index.html"))), None)
            if not found:
                raise PackageError("模板结构异常：找不到 index.html")
            inner = found.parent
            for item in inner.iterdir():
                shutil.move(str(item), str(staging / item.name))
            inner.rmdir()

        if dest.exists():
            shutil.rmtree(dest)
        staging.rename(dest)
    except OSError as exc:
        raise PackageError(f"模板缓存失败：{exc}") from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

    log(f"模板就绪：{dest}")
    return dest


def _escape_config(value: str) -> str:
    """config.txt 同样按 ';' 切分，值里的分号必须转义。"""
    return value.replace(";", "\\;")


def build_config(*, game_name: str, game_key: str) -> str:
    return (
        f"Game_name:{_escape_config(game_name)};\n"
        f"Game_key:{_escape_config(game_key)};\n"
        "Title_img:WebGAL_New_Enter_Image.webp;\n"
        "Title_bgm:s_Title.mp3;\n"
        "Game_Logo:WebGalEnter.webp;\n"
        "Enable_Appreciation:true;\n"
        "Enable_Continue:true;\n"
        "Enable_flowchart:true;\n"
    )


def build_flowchart(game_name: str) -> dict:
    """生成最小 flowchart.json：只有 start.txt 一个根节点。

    官方模板自带的 flowchart 引用十几个 demo 场景，打包时这些场景会被删除，
    直接保留会让游戏内流程图指向不存在的文件。这里用确定性代码重建一份
    只含当前剧本入口的最小流程图。
    """
    return {
        "flowcharts": [
            {
                "id": "main",
                "name": game_name,
                "type": "main",
                "nodes": [
                    {
                        "id": "start",
                        "type": "root",
                        "position": {"x": 0, "y": 0},
                        "data": {"label": "开始", "sceneName": "start.txt", "isRoot": True},
                    }
                ],
                "edges": [],
            }
        ]
    }


def package(
    script: str,
    output_dir: Path,
    *,
    game_name: str,
    game_key: str,
    template: Path | None = None,
    log=lambda _m: None,
) -> Path:
    """把脚本注入模板副本，产出可直接托管的静态目录。

    使用同父目录 staging：任一阶段失败只删除 staging，已有成功输出保持原样；
    staging 完成后再原子替换正式 output_dir。
    """
    output_dir = Path(output_dir)
    if output_dir.is_symlink() or (output_dir.exists() and not output_dir.is_dir()):
        raise PackageError(f"输出路径已存在但不是普通目录：{output_dir}")

    template = template or ensure_template(log=log)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=str(output_dir.parent))
    )
    old_output: Path | None = None

    try:
        log(f"克隆模板到 {staging}")
        shutil.copytree(template, staging, dirs_exist_ok=True)

        scene_dir = staging / "game" / "scene"
        scene_dir.mkdir(parents=True, exist_ok=True)

        # 清掉官方 demo 场景，避免混进产物
        for stale in scene_dir.glob("demo_*.txt"):
            stale.unlink()
        for stale in scene_dir.glob("function_test.txt"):
            stale.unlink()

        # start.txt 是引擎固定入口
        (scene_dir / "start.txt").write_text(script, encoding="utf-8")
        (staging / "game" / "config.txt").write_text(
            build_config(game_name=game_name, game_key=game_key), encoding="utf-8"
        )
        (staging / "game" / "flowchart.json").write_text(
            json.dumps(build_flowchart(game_name), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        # 二次检查后原子替换：旧产物移走 -> staging 顶替 -> 清理旧产物
        if output_dir.is_symlink() or (output_dir.exists() and not output_dir.is_dir()):
            raise PackageError(f"输出路径已存在但不是普通目录：{output_dir}")
        if output_dir.exists():
            old_output = Path(
                tempfile.mkdtemp(prefix=f".{output_dir.name}.old-", dir=str(output_dir.parent))
            )
            old_output.rmdir()
            output_dir.rename(old_output)
        try:
            staging.rename(output_dir)
        except OSError as swap_exc:
            rollback_exc: OSError | None = None
            if old_output and old_output.exists():
                try:
                    old_output.rename(output_dir)
                except OSError as exc:
                    rollback_exc = exc
            if rollback_exc is not None:
                raise PackageError(
                    f"替换产物失败：{swap_exc}；恢复旧产物也失败：{rollback_exc}；"
                    f"旧产物保留在 {old_output}"
                ) from swap_exc
            raise PackageError(f"替换产物失败，旧产物已恢复：{swap_exc}") from swap_exc
        if old_output and old_output.exists():
            try:
                shutil.rmtree(old_output)
            except OSError as exc:
                log(f"清理旧产物备份失败，已保留 {old_output}：{exc}")
    except PackageError:
        raise
    except OSError as exc:
        raise PackageError(f"打包失败：{exc}") from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

    log(f"产物完成：{output_dir}")
    return output_dir
