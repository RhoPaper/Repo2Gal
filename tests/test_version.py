"""包版本必须与发行元数据一致，防止发版时版本号漂移。"""

import importlib.metadata

import repo2gal


def test_module_version_matches_distribution_metadata():
    assert repo2gal.__version__ == importlib.metadata.version("repo2gal")
