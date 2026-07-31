"""WebGAL 产物打包。

策略：克隆官方发行版模板，覆盖 game/ 下的脚本与配置。
不修改引擎源码，不依赖任何 WebGAL CLI（那玩意儿不存在：
npm 上 `webgal` 是 0.0.0 占位包，OpenWebGAL/WebGAL-Server 已于 2022 年归档）。
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import zipfile
from pathlib import Path

import requests

WEBGAL_VERSION = "4.6.2"
WEBGAL_ASSET = f"WebGAL-{WEBGAL_VERSION}-web.zip"
WEBGAL_URL = (
    f"https://github.com/OpenWebGAL/WebGAL/releases/download/{WEBGAL_VERSION}/{WEBGAL_ASSET}"
)
WEBGAL_SHA256 = "299a18b8e0e4a9bc48e659fe50a3a640c71743ed11647acb81a9384149ff9355"


class PackageError(RuntimeError):
    pass


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "repo2gal"


def ensure_template(*, log=lambda _m: None) -> Path:
    """下载并缓存 WebGAL 发行版模板，返回模板根目录。"""
    dest = cache_dir() / f"webgal-{WEBGAL_VERSION}"
    marker = dest / "index.html"
    if marker.exists():
        log(f"复用已缓存模板 {marker.parent}")
        return marker.parent

    log(f"下载固定版本 {WEBGAL_ASSET}（仅首次）")
    blob = requests.get(WEBGAL_URL, timeout=600)
    if not blob.ok:
        raise PackageError(f"模板下载失败：HTTP {blob.status_code}")
    digest = hashlib.sha256(blob.content).hexdigest()
    if digest != WEBGAL_SHA256:
        raise PackageError(f"模板 SHA-256 不匹配：期望 {WEBGAL_SHA256}，实际 {digest}")

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(blob.content)) as zf:
        zf.extractall(dest)

    # 压缩包可能多包一层目录，把 index.html 所在层拎出来
    if not (dest / "index.html").exists():
        found = next(iter(sorted(dest.glob("*/index.html"))), None)
        if not found:
            raise PackageError("模板结构异常：找不到 index.html")
        inner = found.parent
        for item in inner.iterdir():
            shutil.move(str(item), str(dest / item.name))
        inner.rmdir()

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


def package(
    script: str,
    output_dir: Path,
    *,
    game_name: str,
    game_key: str,
    template: Path | None = None,
    log=lambda _m: None,
) -> Path:
    """把脚本注入模板副本，产出可直接托管的静态目录。"""
    template = template or ensure_template(log=log)
    output_dir = Path(output_dir)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    log(f"克隆模板到 {output_dir}")
    shutil.copytree(template, output_dir)

    scene_dir = output_dir / "game" / "scene"
    scene_dir.mkdir(parents=True, exist_ok=True)

    # 清掉官方 demo 场景，避免混进产物
    for stale in scene_dir.glob("demo_*.txt"):
        stale.unlink()
    for stale in scene_dir.glob("function_test.txt"):
        stale.unlink()

    # start.txt 是引擎固定入口
    (scene_dir / "start.txt").write_text(script, encoding="utf-8")
    (output_dir / "game" / "config.txt").write_text(
        build_config(game_name=game_name, game_key=game_key), encoding="utf-8"
    )

    log(f"产物完成：{output_dir}")
    return output_dir
