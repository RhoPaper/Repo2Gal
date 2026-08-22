"""Asset Pack v1 到 WebGAL 目录/脚本语义的确定性适配。"""

from __future__ import annotations

import hashlib
import json
import os
import re
from importlib import resources
from pathlib import Path

from .asset_pack import ASSET_COMMANDS, Asset, AssetPack, open_asset_pack_file
from .config import DEFAULT_BACKGROUNDS, DEFAULT_BGM
from .errors import AssetPackError, PackageError
from .webgal import statement_body

_WEBGAL_DIRS = {
    "background": "background",
    "character": "figure",
    "bgm": "bgm",
}
_WEBGAL_STAGE_WIDTH = 2560
_WEBGAL_STAGE_HEIGHT = 1440
_FIGURE_TOP_MARGIN = 24


def target_filename(asset: Asset) -> str:
    """逻辑 ID 全量参与文件名，避免不同 ID 的末段发生碰撞。"""
    return f"{asset.logical_id.replace('.', '-')}{asset.source_file.suffix.lower()}"


def figure_framing_transform(asset: Asset) -> dict[str, dict[str, float]] | None:
    """把引擎无关的归一化 framing 标注编译为 WebGAL 4.6.2 Pixi transform。"""
    framing = asset.metadata.get("framing")
    if not isinstance(framing, dict) or framing.get("mode") != "upper-body":
        return None
    width = float(asset.metadata["width"])
    height = float(asset.metadata["height"])
    base_scale = min(_WEBGAL_STAGE_WIDTH / width, _WEBGAL_STAGE_HEIGHT / height)
    fitted_height = height * base_scale
    base_y = (
        _WEBGAL_STAGE_HEIGHT / 2
        if fitted_height >= _WEBGAL_STAGE_HEIGHT
        else _WEBGAL_STAGE_HEIGHT - fitted_height / 2
    )
    top = float(framing["top"]) * height
    bottom = float(framing["bottom"]) * height
    center_x = float(framing["centerX"]) * width
    scale = (_WEBGAL_STAGE_HEIGHT - 2 * _FIGURE_TOP_MARGIN) / (base_scale * (bottom - top))
    position_x = -scale * base_scale * (center_x - width / 2)
    position_y = (
        _FIGURE_TOP_MARGIN
        - base_y
        + scale * base_scale * (height / 2 - top)
    )

    def rounded(value: float) -> float:
        result = round(value, 3)
        return 0.0 if result == -0.0 else result

    return {
        "position": {"x": rounded(position_x), "y": rounded(position_y)},
        "scale": {"x": rounded(scale), "y": rounded(scale)},
    }


def figure_base_transform(asset: Asset) -> dict[str, dict[str, float]]:
    """所有 Asset Pack 角色都使用中心基准；无 framing 时退回 WebGAL contain 比例。"""
    return figure_framing_transform(asset) or {
        "position": {"x": 0.0, "y": 0.0},
        "scale": {"x": 1.0, "y": 1.0},
    }


def _target_map(pack: AssetPack) -> dict[str, dict[str, str]]:
    mapping: dict[str, dict[str, str]] = {command: {} for command in ASSET_COMMANDS.values()}
    seen: set[tuple[str, str]] = set()
    for asset in pack.assets.values():
        command = ASSET_COMMANDS[asset.type]
        filename = target_filename(asset)
        key = (_WEBGAL_DIRS[asset.type], filename.casefold())
        if key in seen:
            raise PackageError(f"素材目标文件名碰撞：{filename}")
        seen.add(key)
        mapping[command][asset.logical_id] = filename
    return mapping


def rewrite_script(script: str, pack: AssetPack) -> str:
    """把已校验脚本中的逻辑 ID 改写为 WebGAL 所需裸文件名。"""
    mapping = _target_map(pack)
    out: list[str] = []
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            out.append(line)
            continue
        body = statement_body(stripped).strip()
        command, separator, content = body.partition(":")
        if not separator or command not in mapping:
            out.append(line)
            continue
        reference, marker, args = content.partition(" -")
        target = mapping[command].get(reference.strip())
        if target is None:
            defaults = DEFAULT_BACKGROUNDS if command == "changeBg" else DEFAULT_BGM if command == "bgm" else []
            if reference.strip() in defaults:
                out.append(line)
                continue
            raise PackageError(f"脚本包含未通过 validator 的素材引用：{command}:{reference.strip()}")
        suffix = f" -{args}" if marker else ""
        framing_suffix = ""
        if command == "changeFigure":
            transform = figure_base_transform(pack.assets[reference.strip()])
            arg_parts = args.split(" -") if marker else []
            enter_motion = next(
                (
                    part.removeprefix("repo2galEnter=")
                    for part in arg_parts
                    if part.startswith("repo2galEnter=")
                ),
                None,
            )
            slot_offset = 0
            if any(part in ("left", "left=true") for part in arg_parts):
                slot_offset = -500
            elif any(part in ("right", "right=true") for part in arg_parts):
                slot_offset = 500
            arg_parts = [
                part
                for part in arg_parts
                if part not in ("left", "right")
                and not part.startswith("left=")
                and not part.startswith("right=")
                and not part.startswith("transform=")
                and not part.startswith("repo2galEnter=")
            ]
            transform["position"]["x"] = round(transform["position"]["x"] + slot_offset, 3)
            if enter_motion in ("from-left", "from-right", "fade"):
                transform["alpha"] = 0
                if enter_motion == "from-left":
                    transform["position"]["x"] -= 100
                elif enter_motion == "from-right":
                    transform["position"]["x"] += 100
            framing_suffix = " -transform=" + json.dumps(
                transform, ensure_ascii=False, separators=(",", ":")
            )
            suffix = "" if not arg_parts else " -" + " -".join(arg_parts)
        out.append(f"{command}:{target}{framing_suffix}{suffix};")
    return "\n".join(out) + "\n"


def _safe_pack_slug(pack: AssetPack) -> str:
    raw = f"{pack.name}-{pack.version}".replace("@", "")
    return re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-._") or "asset-pack"


def _open_output_file(staging: Path, parts: list[str]) -> tuple[int, int]:
    if os.open not in os.supports_dir_fd or not hasattr(os, "O_NOFOLLOW"):
        raise PackageError("当前平台缺少安全复制 Asset Pack 所需的 openat/O_NOFOLLOW")

    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    file_flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    directory_fds: list[int] = []
    file_fd: int | None = None
    parent_fd: int | None = None
    try:
        current_fd = os.open(staging, directory_flags)
        directory_fds.append(current_fd)
        for part in parts[:-1]:
            try:
                next_fd = os.open(part, directory_flags, dir_fd=current_fd)
            except FileNotFoundError:
                os.mkdir(part, mode=0o755, dir_fd=current_fd)
                next_fd = os.open(part, directory_flags, dir_fd=current_fd)
            current_fd = next_fd
            directory_fds.append(current_fd)
        file_fd = os.open(parts[-1], file_flags, mode=0o644, dir_fd=current_fd)
        parent_fd = os.dup(current_fd)
        result = (file_fd, parent_fd)
        file_fd = None
        parent_fd = None
        return result
    except OSError as exc:
        if file_fd is not None:
            try:
                os.unlink(parts[-1], dir_fd=current_fd)
            except OSError:
                pass
        raise PackageError(f"无法安全创建素材目标文件 {'/'.join(parts)}：{exc}") from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if parent_fd is not None:
            os.close(parent_fd)
        for directory_fd in reversed(directory_fds):
            os.close(directory_fd)


def _copy_pack_file(
    pack: AssetPack,
    relative: str,
    staging: Path,
    destination_parts: list[str],
    expected_hash: str,
    expected_size: int,
) -> int:
    source_fd: int | None = None
    destination_fd: int | None = None
    destination_parent_fd: int | None = None
    digest = hashlib.sha256()
    total = 0
    created = False
    success = False
    try:
        source_fd = open_asset_pack_file(pack.root, relative, label=f"打包文件 {relative}")
        destination_fd, destination_parent_fd = _open_output_file(staging, destination_parts)
        created = True
        while chunk := os.read(source_fd, 1024 * 1024):
            total += len(chunk)
            if total > expected_size:
                raise PackageError(f"素材包文件在校验后超过原大小：{relative}")
            digest.update(chunk)
            view = memoryview(chunk)
            while view:
                written = os.write(destination_fd, view)
                if written == 0:
                    raise OSError("目标文件写入返回 0 字节")
                view = view[written:]
        if total != expected_size or digest.hexdigest() != expected_hash:
            raise PackageError(f"素材包文件在校验后发生变化：{relative}")
        success = True
        return total
    except AssetPackError as exc:
        raise PackageError(f"素材包文件在校验后不可安全读取：{relative}（{exc}）") from exc
    except OSError as exc:
        raise PackageError(f"复制素材包文件失败：{relative}（{exc}）") from exc
    finally:
        if source_fd is not None:
            os.close(source_fd)
        if destination_fd is not None:
            os.close(destination_fd)
        if created and not success:
            try:
                os.unlink(destination_parts[-1], dir_fd=destination_parent_fd)
            except OSError:
                pass
        if destination_parent_fd is not None:
            os.close(destination_parent_fd)


def _write_output(staging: Path, parts: list[str], content: bytes) -> None:
    destination_fd, destination_parent_fd = _open_output_file(staging, parts)
    success = False
    try:
        view = memoryview(content)
        while view:
            written = os.write(destination_fd, view)
            if written == 0:
                raise OSError("目标文件写入返回 0 字节")
            view = view[written:]
        success = True
    except OSError as exc:
        raise PackageError(f"写入 {'/'.join(parts)} 失败：{exc}") from exc
    finally:
        os.close(destination_fd)
        if not success:
            try:
                os.unlink(parts[-1], dir_fd=destination_parent_fd)
            except OSError:
                pass
        os.close(destination_parent_fd)


def _write_trusted_output(staging: Path, parts: list[str], content: bytes) -> None:
    """固定 Repo2Gal 内容可在不支持 openat 的平台使用 staging 内独占创建。"""
    if os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW"):
        _write_output(staging, parts, content)
        return
    destination = staging.joinpath(*parts)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("xb") as stream:
            stream.write(content)
    except OSError as exc:
        raise PackageError(f"写入 {'/'.join(parts)} 失败：{exc}") from exc


def _markdown_cell(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def install_asset_pack(staging: Path, pack: AssetPack) -> None:
    """在 staging 内复制素材和原始授权材料；失败不触碰正式产物。"""
    _target_map(pack)  # 在复制任何文件前先完成碰撞检查。
    for asset in sorted(pack.assets.values(), key=lambda item: item.logical_id):
        _copy_pack_file(
            pack,
            asset.relative_file.as_posix(),
            staging,
            ["game", _WEBGAL_DIRS[asset.type], target_filename(asset)],
            asset.sha256,
            asset.size,
        )

    material_parts = ["third_party", "asset-packs", _safe_pack_slug(pack)]
    for relative, (expected_hash, expected_size) in sorted(pack.support_files.items()):
        _copy_pack_file(
            pack,
            relative,
            staging,
            material_parts + relative.split("/"),
            expected_hash,
            expected_size,
        )


def write_third_party_notices(
    staging: Path,
    *,
    webgal_version: str,
    pack: AssetPack | None = None,
) -> None:
    """为每个 WebGAL 产物写入引擎许可证，并按需追加 Asset Pack 声明。"""
    mpl_text = resources.files("repo2gal").joinpath("legal/MPL-2.0.txt").read_bytes()
    _write_trusted_output(staging, ["third_party", "WebGAL", "LICENSE"], mpl_text)

    notice = (
        "# Third-Party Notices\n\n"
        "Repo2Gal 程序的 GPL-3.0 许可证不会改变下列引擎与媒体素材的许可证。\n\n"
        "## WebGAL\n\n"
        f"- 版本：{webgal_version}\n"
        "- 项目：https://github.com/OpenWebGAL/WebGAL\n"
        f"- 对应源代码：https://github.com/OpenWebGAL/WebGAL/tree/{webgal_version}\n"
        "- 许可证：MPL-2.0\n"
        "- 许可证全文：`third_party/WebGAL/LICENSE`\n"
    )
    if pack is None:
        _write_trusted_output(
            staging, ["THIRD_PARTY_NOTICES.md"], (notice + "\n").encode("utf-8")
        )
        return

    manifest = pack.manifest
    authors = "、".join(_markdown_cell(author["name"]) for author in manifest["authors"])
    material_path = f"third_party/asset-packs/{_safe_pack_slug(pack)}"
    rows = []
    package_license = manifest["license"]
    for asset in sorted(pack.assets.values(), key=lambda item: item.logical_id):
        license_info = asset.metadata.get("license", package_license)
        source = license_info.get("source", "见包级 provenance/NOTICE")
        attribution = license_info.get("attribution", "按包级声明")
        rows.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    asset.logical_id,
                    asset.type,
                    license_info["spdx"],
                    source,
                    attribution,
                )
            )
            + " |"
        )

    notice += (
        f"\n## {manifest['displayName']}\n\n"
        f"- 包：`{manifest['name']}@{manifest['version']}`\n"
        f"- 作者：{authors}\n"
        f"- 默认许可证：`{package_license['spdx']}`\n"
        f"- 原始清单、许可证与 NOTICE：`{material_path}/`\n\n"
        "| 逻辑 ID | 类型 | 许可证 | 来源 | 署名 |\n"
        "|---|---|---|---|---|\n"
        + "\n".join(rows)
        + "\n"
    )
    _write_trusted_output(staging, ["THIRD_PARTY_NOTICES.md"], notice.encode("utf-8"))
