"""Repo2Gal Asset Pack v1 的本地加载、初始化与确定性校验。"""

from __future__ import annotations

import hashlib
import errno
import json
import os
import re
import shutil
import stat
import tempfile
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path, PurePosixPath
from typing import Any

import langcodes
import semver
from coloraide import Color
from jsonschema import Draft202012Validator, FormatChecker
from packaging.licenses import InvalidLicenseExpression, canonicalize_license_expression
from PIL import Image, UnidentifiedImageError

from .errors import AssetPackError

MANIFEST_NAME = "repo2gal-pack.json"
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_ASSET_BYTES = 128 * 1024 * 1024
MAX_PACK_BYTES = 512 * 1024 * 1024
MAX_SUPPORT_FILE_BYTES = 8 * 1024 * 1024
MAX_SUPPORT_FILES = 512
MIME_SAMPLE_BYTES = 2 * 1024 * 1024

ASSET_COMMANDS: dict[str, str] = {
    "background": "changeBg",
    "character": "changeFigure",
    "bgm": "bgm",
}

_MIME_SUFFIXES: dict[str, frozenset[str]] = {
    "image/png": frozenset({".png"}),
    "image/jpeg": frozenset({".jpg", ".jpeg"}),
    "image/webp": frozenset({".webp"}),
    "image/avif": frozenset({".avif"}),
    "audio/mpeg": frozenset({".mp3"}),
    "audio/ogg": frozenset({".ogg", ".oga"}),
    "audio/wav": frozenset({".wav"}),
    "audio/flac": frozenset({".flac"}),
    "audio/mp4": frozenset({".m4a", ".mp4"}),
}

_MIME_ALIASES = {
    "audio/x-wav": "audio/wav",
    "audio/vnd.wave": "audio/wav",
    "audio/x-flac": "audio/flac",
    "image/jpg": "image/jpeg",
}
_PIL_FORMATS = {
    "image/png": "PNG",
    "image/jpeg": "JPEG",
    "image/webp": "WEBP",
    "image/avif": "AVIF",
}

_BCP47_LEXICAL = re.compile(r"^[A-Za-z0-9]{1,8}(?:-[A-Za-z0-9]{1,8})*$")


@dataclass(frozen=True)
class Asset:
    logical_id: str
    type: str
    relative_file: PurePosixPath
    source_file: Path
    mime_type: str
    sha256: str
    size: int
    metadata: dict[str, Any]


@dataclass(frozen=True)
class AssetPack:
    root: Path
    manifest: dict[str, Any]
    assets: dict[str, Asset]
    support_files: dict[str, tuple[str, int]]

    @property
    def name(self) -> str:
        return self.manifest["name"]

    @property
    def version(self) -> str:
        return self.manifest["version"]

    def logical_ids(self, asset_type: str) -> list[str]:
        return sorted(a.logical_id for a in self.assets.values() if a.type == asset_type)

    def command_catalog(self) -> dict[str, frozenset[str]]:
        return {
            command: frozenset(self.logical_ids(asset_type))
            for asset_type, command in ASSET_COMMANDS.items()
        }


_FORMATS = FormatChecker()


@_FORMATS.checks("semver", raises=(TypeError, ValueError))
def _valid_semver(value: object) -> bool:
    return isinstance(value, str) and value.isascii() and semver.Version.parse(value) is not None


@_FORMATS.checks("spdx", raises=(TypeError, InvalidLicenseExpression))
def _valid_spdx(value: object) -> bool:
    if not isinstance(value, str) or not value.isascii():
        return False
    canonicalize_license_expression(value)
    return True


@_FORMATS.checks("bcp47", raises=(TypeError, ValueError))
def _valid_bcp47(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.isascii()
        and _BCP47_LEXICAL.fullmatch(value) is not None
        and langcodes.tag_is_valid(value)
    )


@_FORMATS.checks("css-color", raises=(TypeError, ValueError))
def _valid_css_color(value: object) -> bool:
    if not isinstance(value, str) or value.startswith("color(--"):
        return False
    return Color.match(value, fullmatch=True) is not None


def _load_schema() -> dict[str, Any]:
    schema_file = resources.files("repo2gal").joinpath("schemas/asset-pack-v1.schema.json")
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


_SCHEMA = _load_schema()


def _json_without_duplicate_keys(text: str) -> dict[str, Any]:
    def build(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError(f"JSON 中存在重复键：{key}")
            out[key] = value
        return out

    value = json.loads(text, object_pairs_hook=build)
    if not isinstance(value, dict):
        raise ValueError("manifest 顶层必须是 JSON object")
    return value


def _schema_error_path(error) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    return f"{path}: {error.message}" if path else error.message


def _relative_parts(relative: str, *, label: str) -> list[str]:
    if not isinstance(relative, str) or not relative:
        raise AssetPackError(f"{label} 路径为空")
    if "\\" in relative or "\x00" in relative:
        raise AssetPackError(f"{label} 必须使用包内 POSIX 相对路径：{relative!r}")

    raw_parts = relative.split("/")
    posix_path = PurePosixPath(relative)
    if posix_path.is_absolute() or any(part in ("", ".", "..") for part in raw_parts):
        raise AssetPackError(f"{label} 路径不能逃出素材包：{relative!r}")
    return raw_parts


def open_asset_pack_file(root: Path, relative: str, *, label: str) -> int:
    """以不跟随符号链接的 openat 链打开包内普通文件；调用方负责关闭 fd。"""
    parts = _relative_parts(relative, label=label)
    if os.open not in os.supports_dir_fd or not hasattr(os, "O_NOFOLLOW"):
        raise AssetPackError("当前平台缺少安全打开 Asset Pack 所需的 openat/O_NOFOLLOW")

    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    directory_fds: list[int] = []
    file_fd: int | None = None
    try:
        current_fd = os.open(root, directory_flags)
        directory_fds.append(current_fd)
        for part in parts[:-1]:
            current_fd = os.open(part, directory_flags, dir_fd=current_fd)
            directory_fds.append(current_fd)
        file_fd = os.open(parts[-1], file_flags, dir_fd=current_fd)
        if not stat.S_ISREG(os.fstat(file_fd).st_mode):
            raise AssetPackError(f"{label} 文件不存在或不是普通文件：{relative}")
        result = file_fd
        file_fd = None
        return result
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            raise AssetPackError(f"{label} 路径包含符号链接或非目录：{relative}") from exc
        raise AssetPackError(f"无法安全打开 {label}：{relative}（{exc}）") from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        for directory_fd in reversed(directory_fds):
            os.close(directory_fd)


def _inspect_pack_file(
    root: Path,
    relative: str,
    *,
    label: str,
    max_bytes: int,
    capture: bool = False,
) -> tuple[int, str, bytes, bytes | None]:
    """在同一个安全 fd 上做有界读取、SHA-256 与 MIME 头采样。"""
    file_fd = open_asset_pack_file(root, relative, label=label)
    digest = hashlib.sha256()
    sample = bytearray()
    content = bytearray() if capture else None
    total = 0
    try:
        with os.fdopen(file_fd, "rb") as stream:
            while chunk := stream.read(min(1024 * 1024, max_bytes + 1 - total)):
                total += len(chunk)
                if total > max_bytes:
                    raise AssetPackError(f"{label} 超过 {max_bytes // (1024 * 1024) or 1} MiB 上限")
                digest.update(chunk)
                if len(sample) < MIME_SAMPLE_BYTES:
                    sample.extend(chunk[: MIME_SAMPLE_BYTES - len(sample)])
                if content is not None:
                    content.extend(chunk)
    except OSError as exc:
        raise AssetPackError(f"无法读取 {label}：{relative}（{exc}）") from exc
    return total, digest.hexdigest(), bytes(sample), bytes(content) if content is not None else None


def _detected_mime(sample: bytes, *, label: str) -> str:
    try:
        import magic
    except (ImportError, OSError) as exc:
        raise AssetPackError(
            "Asset Pack MIME 校验需要 python-magic 与系统 libmagic（Debian/Ubuntu: libmagic1）"
        ) from exc
    try:
        detected = magic.from_buffer(sample, mime=True)
    except magic.MagicException as exc:
        raise AssetPackError(f"无法检测素材 MIME：{label}（{exc}）") from exc
    return _MIME_ALIASES.get(detected, detected)


def _image_dimensions(root: Path, relative: str, *, label: str, mime_type: str) -> tuple[int, int]:
    file_fd = open_asset_pack_file(root, relative, label=label)
    try:
        with os.fdopen(file_fd, "rb") as stream:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(stream, formats=[_PIL_FORMATS[mime_type]]) as image:
                    dimensions = image.size
                    image.verify()
                    return dimensions
    except (
        OSError,
        SyntaxError,
        ValueError,
        UnidentifiedImageError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as exc:
        raise AssetPackError(f"无法安全读取图片尺寸或结构：{label}（{exc}）") from exc


def _validate_profiles(manifest: dict[str, Any], assets: dict[str, Asset]) -> None:
    profiles = set(manifest["profiles"])
    types = {asset.type for asset in assets.values()}
    normal_character = any(
        asset.type == "character" and asset.metadata.get("emotion") == "normal"
        for asset in assets.values()
    )
    has_palette = bool(manifest.get("theme", {}).get("palette"))

    missing: list[str] = []
    if profiles & {"repo2gal.palette", "repo2gal.theme", "repo2gal.complete"} and not has_palette:
        missing.append("theme.palette")
    if profiles & {"repo2gal.character", "repo2gal.chronicle", "repo2gal.complete"}:
        if "character" not in types or not normal_character:
            missing.append("normal 表情的 character")
    if profiles & {"repo2gal.audio", "repo2gal.chronicle", "repo2gal.complete"} and "bgm" not in types:
        missing.append("bgm")
    if profiles & {"repo2gal.chronicle", "repo2gal.complete"} and "background" not in types:
        missing.append("background")
    if missing:
        raise AssetPackError("Profile 最低素材不完整：" + "、".join(missing))


def load_asset_pack(path: Path | str, *, public: bool = False) -> AssetPack:
    """加载并完整校验一个本地目录包；不执行包内任何代码。"""
    if str(path) == "builtin:cc0-chronicle":
        path = resources.files("repo2gal").joinpath("examples/cc0-chronicle-pack")
    requested = Path(path)
    if requested.is_symlink():
        raise AssetPackError(f"素材包根目录不接受符号链接：{requested}")
    if not requested.is_dir():
        raise AssetPackError(f"素材包目录不存在：{requested}")
    root = requested.resolve()

    _, manifest_hash, _, manifest_bytes = _inspect_pack_file(
        root,
        MANIFEST_NAME,
        label="manifest",
        max_bytes=MAX_MANIFEST_BYTES,
        capture=True,
    )
    try:
        manifest = _json_without_duplicate_keys(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise AssetPackError(f"无法读取 {MANIFEST_NAME}：{exc}") from exc

    validator = Draft202012Validator(_SCHEMA, format_checker=_FORMATS)
    errors = sorted(
        validator.iter_errors(manifest), key=lambda error: tuple(str(p) for p in error.absolute_path)
    )
    if errors:
        detail = "\n".join(f"- {_schema_error_path(error)}" for error in errors[:20])
        suffix = f"\n- 另有 {len(errors) - 20} 项错误" if len(errors) > 20 else ""
        raise AssetPackError(f"Asset Pack Schema 校验失败：\n{detail}{suffix}")

    if manifest["license"]["file"] != "LICENSE":
        raise AssetPackError("包级 license.file 必须固定为 LICENSE")
    support_files = {MANIFEST_NAME: (manifest_hash, len(manifest_bytes))}
    support_bytes = len(manifest_bytes)

    def record_support(relative: str, label: str) -> None:
        nonlocal support_bytes
        _relative_parts(relative, label=label)
        if relative in support_files:
            return
        if len(support_files) >= MAX_SUPPORT_FILES:
            raise AssetPackError(f"授权与审计材料超过 {MAX_SUPPORT_FILES} 个文件上限")
        size, digest, _, _ = _inspect_pack_file(
            root,
            relative,
            label=label,
            max_bytes=MAX_SUPPORT_FILE_BYTES,
        )
        support_bytes += size
        if support_bytes > MAX_PACK_BYTES:
            raise AssetPackError("素材包全部声明文件总计超过 512 MiB 上限")
        support_files[relative] = (digest, size)

    record_support("LICENSE", "包级许可证")
    record_support("NOTICE.md", "素材声明")
    provenance = manifest["provenance"]
    if provenance["sourceType"] == "ai-generated":
        record_support(provenance["promptFile"], "AI provenance promptFile")

    all_licenses = [manifest["license"]]
    assets: dict[str, Asset] = {}
    total_bytes = 0
    for logical_id, item in sorted(manifest["assets"].items()):
        if not logical_id.startswith(f"{item['type']}."):
            raise AssetPackError(
                f"逻辑 ID {logical_id!r} 必须以素材类型 {item['type']!r} 加点号开头"
            )
        framing = item.get("framing")
        if framing is not None and framing["bottom"] - framing["top"] < 0.1:
            raise AssetPackError(f"素材 {logical_id} framing 的 bottom 必须显著大于 top")
        size, actual_hash, mime_sample, _ = _inspect_pack_file(
            root,
            item["file"],
            label=f"素材 {logical_id}",
            max_bytes=MAX_ASSET_BYTES,
        )
        if size == 0:
            raise AssetPackError(f"素材 {logical_id} 不能为空文件")
        total_bytes += size
        if support_bytes + total_bytes > MAX_PACK_BYTES:
            raise AssetPackError("素材包全部声明文件总计超过 512 MiB 上限")

        expected_mime = item["mimeType"]
        suffix = PurePosixPath(item["file"]).suffix.lower()
        if suffix not in _MIME_SUFFIXES[expected_mime]:
            raise AssetPackError(
                f"素材 {logical_id} 扩展名 {suffix or '（无）'} 与 {expected_mime} 不一致"
            )
        actual_mime = _detected_mime(mime_sample, label=logical_id)
        if actual_mime != expected_mime:
            raise AssetPackError(
                f"素材 {logical_id} MIME 不匹配：声明 {expected_mime}，magic 检测 {actual_mime}"
            )
        if expected_mime.startswith("image/"):
            actual_dimensions = _image_dimensions(
                root,
                item["file"],
                label=f"素材 {logical_id}",
                mime_type=expected_mime,
            )
            declared_dimensions = (item["width"], item["height"])
            if actual_dimensions != declared_dimensions:
                raise AssetPackError(
                    f"素材 {logical_id} 图片尺寸不匹配：声明 {declared_dimensions[0]}x{declared_dimensions[1]}，"
                    f"实际 {actual_dimensions[0]}x{actual_dimensions[1]}"
                )
        if actual_hash != item["sha256"]:
            raise AssetPackError(
                f"素材 {logical_id} SHA-256 不匹配：期望 {item['sha256']}，实际 {actual_hash}"
            )

        license_info = item.get("license")
        if license_info:
            all_licenses.append(license_info)
            for key in ("file", "evidence"):
                if license_info.get(key):
                    record_support(license_info[key], f"素材 {logical_id} {key}")
        assets[logical_id] = Asset(
            logical_id=logical_id,
            type=item["type"],
            relative_file=PurePosixPath(item["file"]),
            source_file=root.joinpath(*item["file"].split("/")),
            mime_type=expected_mime,
            sha256=item["sha256"],
            size=size,
            metadata=item,
        )

    if public:
        proprietary = [
            lic["spdx"]
            for lic in all_licenses
            if "LicenseRef-" in canonicalize_license_expression(lic["spdx"])
        ]
        if proprietary:
            raise AssetPackError(
                "公开发布模式不接受 LicenseRef 或未标准化许可证：" + "、".join(proprietary)
            )

    _validate_profiles(manifest, assets)
    return AssetPack(root=root, manifest=manifest, assets=assets, support_files=support_files)


def init_asset_pack(path: Path | str) -> Path:
    """创建最小本地包骨架；绝不覆盖已有文件。"""
    root = Path(path)
    staging: Path | None = None
    removed_empty_root = False
    try:
        if root.is_symlink():
            raise AssetPackError(f"初始化目标不接受符号链接：{root}")
        if root.exists() and (not root.is_dir() or any(root.iterdir())):
            raise AssetPackError(f"初始化目标必须不存在或为空目录：{root}")
        root.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{root.name}.init-", dir=str(root.parent)))

        for dirname in (
            "backgrounds",
            "characters",
            "audio",
            "fonts",
            "ui",
            "generation",
            "licenses",
        ):
            (staging / dirname).mkdir()

        raw_name = re.sub(r"[^a-z0-9._-]+", "-", root.name.lower()).strip("-._")
        manifest = {
            "$schema": "https://repo2gal.dev/schemas/asset-pack/v1.json",
            "manifestVersion": 1,
            "name": raw_name or "local-asset-pack",
            "version": "0.1.0",
            "displayName": root.name or "Local Asset Pack",
            "description": "本地 Repo2Gal 素材包，请补充描述。",
            "authors": [{"name": "TODO"}],
            "license": {"spdx": "LicenseRef-Proprietary", "file": "LICENSE"},
            "locale": "zh-CN",
            "profiles": [],
            "assets": {},
            "provenance": {
                "sourceType": "manual",
                "createdAt": datetime.now(timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z"),
            },
        }
        (staging / MANIFEST_NAME).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (staging / "LICENSE").write_text(
            "Replace this file with the complete license text before distribution.\n",
            encoding="utf-8",
        )
        (staging / "NOTICE.md").write_text(
            "# Asset Pack Notice\n\nRecord authorship, attribution, and third-party sources here.\n",
            encoding="utf-8",
        )

        if root.exists():
            root.rmdir()
            removed_empty_root = True
        staging.rename(root)
        staging = None
        return root
    except AssetPackError:
        raise
    except OSError as exc:
        if removed_empty_root and not root.exists():
            try:
                root.mkdir()
            except OSError:
                pass
        raise AssetPackError(f"无法初始化素材包 {root}：{exc}") from exc
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
