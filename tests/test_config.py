"""集中配置与密钥显示的离线测试。"""

from pathlib import Path

import repo2gal.config as config


def test_resolve_base_url_priority(monkeypatch):
    monkeypatch.delenv("REPO2GAL_BASE_URL", raising=False)
    assert config.resolve_base_url(None) == config.DEFAULT_BASE_URL
    monkeypatch.setenv("REPO2GAL_BASE_URL", "https://env.example/v1/")
    assert config.resolve_base_url(None) == "https://env.example/v1"  # 去尾斜杠
    assert config.resolve_base_url("https://flag.example") == "https://flag.example"  # flag 优先


def test_resolve_model_priority(monkeypatch):
    monkeypatch.delenv("REPO2GAL_MODEL", raising=False)
    assert config.resolve_model(None) == config.DEFAULT_MODEL
    monkeypatch.setenv("REPO2GAL_MODEL", "env-model")
    assert config.resolve_model(None) == "env-model"
    assert config.resolve_model("flag-model") == "flag-model"


def test_resolve_api_key_prefers_repo2gal(monkeypatch):
    monkeypatch.delenv("REPO2GAL_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert config.resolve_api_key() is None
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    assert config.resolve_api_key() == "sk-openai"
    monkeypatch.setenv("REPO2GAL_API_KEY", "sk-repo2gal")
    assert config.resolve_api_key() == "sk-repo2gal"


def test_blank_env_treated_as_unset(monkeypatch):
    monkeypatch.setenv("REPO2GAL_API_KEY", "   ")
    assert config.resolve_api_key() is None


def test_default_paths():
    assert config.default_backup_root("acme") == Path(".repo2gal") / "backups" / "acme"
    assert config.default_output_dir("widget") == Path("output") / "widget"


def test_webgal_cache_dir_respects_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert config.webgal_cache_dir() == tmp_path / "repo2gal"


def test_mask_secret_never_leaks_full_value():
    assert config.mask_secret("github_pat_1234567890") == "gith********7890"
    assert config.mask_secret("abcd") == "****"
    assert "1234567890" not in config.mask_secret("github_pat_1234567890")
