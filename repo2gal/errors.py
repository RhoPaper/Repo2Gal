"""统一错误体系：类型 -> 退出码，集中脱敏。

CLI 是唯一使用 exit_code 的地方；模块内部只抛类型化的错误，
不再各自散落 sys.exit。错误正文在进入日志/终端前统一经 :func:`redact_error`
脱敏（API Key、Bearer 头、带凭据 URL），最多保留 500 字符。
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

MAX_ERROR_CHARS = 500


class Repo2GalError(Exception):
    """所有可预期错误的基类；子类通过 ``exit_code`` 声明 CLI 退出码。"""

    exit_code = 1


class UsageError(Repo2GalError):
    """参数、模式组合或输入路径错误。"""

    exit_code = 2


class AssetPackError(UsageError):
    """本地 Asset Pack 的结构、授权或完整性校验失败。"""


class FetchError(Repo2GalError):
    """GitHub 采集或备份不可用。"""

    exit_code = 3


class GenerationError(Repo2GalError):
    """LLM 调用或生成流程失败。"""

    exit_code = 4


class ValidationFailed(Repo2GalError):
    """--strict 下 validator 存在降级，产物拒绝打包。"""

    exit_code = 5


class PackageError(Repo2GalError):
    """WebGAL 打包失败。"""

    exit_code = 6


def redact_error(text: str, *, secret: str | None = None) -> str:
    """错误正文脱敏：API Key、Bearer 头、带凭据 URL；最多保留 500 字符。"""
    if secret:
        text = text.replace(secret, "***")
    text = re.sub(r"Bearer\s+\S+", "Bearer ***", text)

    def _strip_url(match: re.Match) -> str:
        raw = match.group(0)
        try:
            parsed = urlparse(raw)
            host = parsed.hostname or ""
            try:
                port = parsed.port
            except ValueError:
                port = None
            if port is not None:
                host += f":{port}"
            return urlunparse((parsed.scheme, host, parsed.path, "", "", ""))
        except (TypeError, ValueError):
            return re.sub(r"//[^/@\s]+@", "//", raw).split("?", 1)[0].split("#", 1)[0]

    return re.sub(r"https?://[^\s\"'`]+", _strip_url, text)[:MAX_ERROR_CHARS]
