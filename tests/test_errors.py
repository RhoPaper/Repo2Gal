"""统一错误体系与脱敏的离线测试。"""

from repo2gal.errors import (
    FetchError,
    GenerationError,
    PackageError,
    Repo2GalError,
    UsageError,
    ValidationFailed,
    redact_error,
)


def test_exit_code_contract():
    """CLI 退出码是错误类型的契约，不能漂移。"""
    assert UsageError.exit_code == 2
    assert FetchError.exit_code == 3
    assert GenerationError.exit_code == 4
    assert ValidationFailed.exit_code == 5
    assert PackageError.exit_code == 6


def test_errors_are_repo2gal_errors():
    for error in (UsageError, FetchError, GenerationError, ValidationFailed, PackageError):
        assert issubclass(error, Repo2GalError)


def test_redact_replaces_secret():
    secret = "sk-super-secret-key"
    assert secret not in redact_error(f"请求失败，key={secret}", secret=secret)


def test_redact_masks_bearer_header():
    text = "Authorization: Bearer abcdef1234567890 failed"
    out = redact_error(text)
    assert "abcdef1234567890" not in out
    assert "Bearer ***" in out


def test_redact_strips_url_credentials():
    out = redact_error("GET https://user:pass@example.test:8443/v1?api_key=hidden#frag 失败")
    assert "pass" not in out
    assert "api_key" not in out
    assert "example.test:8443/v1" in out


def test_redact_caps_length():
    assert len(redact_error("x" * 5000)) == 500


def test_redact_plain_text_untouched():
    assert redact_error("普通错误消息") == "普通错误消息"
