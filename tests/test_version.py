"""包版本必须与发行元数据一致，防止发版时版本号漂移。"""

import importlib.metadata
from pathlib import Path

import repo2gal

ROOT = Path(__file__).resolve().parents[1]


def test_module_version_matches_distribution_metadata():
    assert repo2gal.__version__ == importlib.metadata.version("repo2gal")


def test_version_is_synced_across_release_entries():
    """CONTRIBUTING 的发版清单：README、CHANGELOG、AGENTS、架构文档必须同步版本号。

    只改 pyproject.toml / __init__.py 时这条测试失败，避免出现“代码 0.9.0、文档 0.8.0”
    的半发版状态。
    """
    tag = f"v{repo2gal.__version__}"
    expectations = {
        "README.md": f"当前版本：{tag}",
        "CHANGELOG.md": f"## {tag} — ",
        "AGENTS.md": f"当前稳定基线为 `{tag}`",
        "docs/dev/architecture.md": f"当前基线：`{tag}`",
    }
    for relative, needle in expectations.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert needle in text, f"{relative} 缺少 {needle!r}，发版时未同步版本号"
