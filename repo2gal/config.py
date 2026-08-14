"""集中配置：默认值、环境解析、路径常量与密钥脱敏显示。

所有“默认值写在哪”的问题在这里一次性解决，禁止其他模块各自硬编码
base_url / model / 目录规则。显示用途的脱敏（终端输出）也集中在这里；
错误正文脱敏在 ``errors.redact_error``。
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_LLM_TIMEOUT = 300

# WebGAL 发行版自带的素材。数量少得可怜，这是当前产物观感的主要瓶颈。
DEFAULT_BACKGROUNDS = ["bg.webp", "WebGalEnter.webp", "WebGAL_New_Enter_Image.webp"]
DEFAULT_BGM = ["s_Title.mp3"]


def env_value(name: str) -> str | None:
    """读取并去空白的环境变量；空白视为未设置。"""
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None


def resolve_base_url(base_url: str | None) -> str:
    return (base_url or env_value("REPO2GAL_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def resolve_model(model: str | None) -> str:
    return model or env_value("REPO2GAL_MODEL") or DEFAULT_MODEL


def resolve_api_key() -> str | None:
    """REPO2GAL_API_KEY 优先，OPENAI_API_KEY 兜底。"""
    return env_value("REPO2GAL_API_KEY") or env_value("OPENAI_API_KEY")


def resolve_github_token() -> str | None:
    return env_value("GITHUB_TOKEN")


def default_backup_root(owner: str) -> Path:
    return Path(".repo2gal") / "backups" / owner


def default_output_dir(repo: str) -> Path:
    return Path("output") / repo


def webgal_cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "repo2gal"


def mask_secret(value: str) -> str:
    """保留少量首尾字符，禁止把完整凭据写到终端。"""
    if len(value) <= 4:
        return "*" * len(value)
    visible = 2 if len(value) <= 10 else 4
    return f"{value[:visible]}{'*' * min(8, len(value) - visible * 2)}{value[-visible:]}"
