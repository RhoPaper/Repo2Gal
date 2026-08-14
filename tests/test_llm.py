"""LLMClient 错误矩阵的离线测试：所有失败都必须包装为 GenerationError。"""

import pytest
import requests

import repo2gal.llm as llm_module
from repo2gal.errors import GenerationError
from repo2gal.llm import LLMClient, MISSING_KEY_MESSAGE


class FakeResponse:
    def __init__(self, *, ok=True, status_code=200, text="", payload=None, json_fail=False):
        self.ok = ok
        self.status_code = status_code
        self.text = text
        self._payload = payload
        self._json_fail = json_fail

    def json(self):
        if self._json_fail:
            raise ValueError("not json")
        return self._payload


def client(**kwargs):
    defaults = {"base_url": "https://example.test/v1", "model": "m", "api_key": "sk-secret-123"}
    defaults.update(kwargs)
    return LLMClient(**defaults)


def test_complete_success(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return FakeResponse(payload={"choices": [{"message": {"content": "剧本"}}]})

    monkeypatch.setattr(llm_module.requests, "post", fake_post)
    assert client().complete("prompt") == "剧本"
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["json"]["messages"] == [{"role": "user", "content": "prompt"}]


def test_missing_api_key_raises_generation_error(monkeypatch):
    monkeypatch.delenv("REPO2GAL_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(GenerationError) as exc:
        client(api_key=None).complete("prompt")
    assert "REPO2GAL_API_KEY" in str(exc.value)


def test_network_error_wrapped_and_redacted(monkeypatch):
    def fake_post(url, **kwargs):
        raise requests.ConnectionError("连接 https://user:sk-secret-123@example.test/v1 失败")

    monkeypatch.setattr(llm_module.requests, "post", fake_post)
    with pytest.raises(GenerationError) as exc:
        client().complete("prompt")
    message = str(exc.value)
    assert "sk-secret-123" not in message  # 密钥不出现在任何输出
    assert "LLM 请求失败" in message


def test_http_error_wrapped_and_redacted(monkeypatch):
    monkeypatch.setattr(
        llm_module.requests,
        "post",
        lambda *a, **kw: FakeResponse(
            ok=False, status_code=401, text='{"error":"invalid key sk-secret-123"}'
        ),
    )
    with pytest.raises(GenerationError) as exc:
        client().complete("prompt")
    message = str(exc.value)
    assert "401" in message
    assert "sk-secret-123" not in message


def test_non_json_response_wrapped(monkeypatch):
    monkeypatch.setattr(
        llm_module.requests, "post", lambda *a, **kw: FakeResponse(json_fail=True)
    )
    with pytest.raises(GenerationError) as exc:
        client().complete("prompt")
    assert "JSON" in str(exc.value)


def test_malformed_structure_wrapped(monkeypatch):
    monkeypatch.setattr(
        llm_module.requests, "post", lambda *a, **kw: FakeResponse(payload={"choices": []})
    )
    with pytest.raises(GenerationError) as exc:
        client().complete("prompt")
    assert "响应结构异常" in str(exc.value)


def test_non_string_content_wrapped(monkeypatch):
    monkeypatch.setattr(
        llm_module.requests,
        "post",
        lambda *a, **kw: FakeResponse(payload={"choices": [{"message": {"content": 123}}]}),
    )
    with pytest.raises(GenerationError) as exc:
        client().complete("prompt")
    assert "不是字符串" in str(exc.value)
