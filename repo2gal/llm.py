"""LLM transport 薄客户端：OpenAI-compatible Chat Completions。

刻意不锁定厂商：任何兼容该协议的服务（DeepSeek、Kimi、本地 vLLM 等）都可通过
base_url 接入。本模块只负责网络与响应解析，并把所有失败统一包装成
:class:`~repo2gal.errors.GenerationError`（CLI 退出码 4），错误正文一律脱敏。
叙事 prompt 的组装在 ``generator.py``，重试策略刻意不在此实现（保持 v0.2.0
行为，需要时再单独调研依赖）。
"""

from __future__ import annotations

import requests

from .config import DEFAULT_LLM_TIMEOUT, resolve_api_key
from .errors import GenerationError, redact_error

MISSING_KEY_MESSAGE = "缺少 API Key，请设置环境变量 REPO2GAL_API_KEY"


class LLMClient:
    """一次运行复用一个客户端；complete() 是唯一入口。"""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: int = DEFAULT_LLM_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def complete(self, prompt: str, *, temperature: float = 0.8) -> str:
        """调用一次 Chat Completions 并返回 content 字符串。"""
        api_key = self.api_key or resolve_api_key()
        if not api_key:
            raise GenerationError(MISSING_KEY_MESSAGE)
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                },
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise GenerationError(
                f"LLM 请求失败：{redact_error(str(exc), secret=api_key)}"
            ) from exc
        if not resp.ok:
            raise GenerationError(
                f"LLM 返回 {resp.status_code}：{redact_error(resp.text, secret=api_key)}"
            )
        try:
            data = resp.json()
        except ValueError as exc:
            raise GenerationError("LLM 响应不是合法 JSON") from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GenerationError("LLM 响应结构异常：缺少 choices[0].message.content") from exc
        if not isinstance(content, str):
            raise GenerationError("LLM 响应 content 不是字符串")
        return content
