"""python-github-backup 落盘结构的离线回归样本。

`tests/fixtures/github-backup-sample/` 的 JSON 字段形状取自真实备份（Issue 的 labels
对象数组、`comment_data`/`reply_data`，Pull 的 `comment_regular_data`/`review_data`，
Discussion 的 camelCase 键），标识符与正文全部替换为合成内容。这组测试把上游 schema
固定在离线套件里：上游格式变化时先更新 fixture，再确认解析器仍然通过。
"""

from pathlib import Path

from repo2gal.fetcher import context_from_backup

BACKUP = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "github-backup-sample"
    / "repositories"
    / "widget"
)


def test_chronicle_reads_real_backup_layout():
    ctx = context_from_backup("acme", "widget", BACKUP, mode="chronicle")

    # 同时解析 issues/、pulls/、discussions/，按评论数降序（同分按创建时间）
    assert [thread.number for thread in ctx.threads] == [2, 4, 5, 3, 1]

    issue = ctx.threads[0]
    assert issue.labels == ["good first issue", "documentation"]
    assert issue.author == "octo-doc"
    assert issue.comment_count == 3  # 2 条评论 + 1 条 reply_data

    pull = next(thread for thread in ctx.threads if thread.kind == "pr")
    assert pull.comment_count == 2  # comment_regular_data + review_data
    discussion = next(thread for thread in ctx.threads if thread.kind == "discussion")
    assert discussion.author == "octo-asker"
    assert "widget.toml" in discussion.body

    # 草稿 Release 不进上下文；仓库概览来自 repo2gal-repository.json
    assert [release.tag for release in ctx.releases] == ["v1.2.0"]
    assert (ctx.stars, ctx.topics, ctx.language) == (42, ["documentation", "example"], "Python")
    assert ctx.readme_excerpt.startswith("# Widget")
    assert "维护者约定" in ctx.wiki_excerpt
    assert "src/" in ctx.file_tree
    assert "pyproject.toml" in ctx.project_files
    assert ctx.contributor_files == ""


def test_quickstart_reads_open_starter_issues_and_contributor_files():
    ctx = context_from_backup("acme", "widget", BACKUP, mode="quickstart")

    # 只取开放且带新人标签的 Issue（good first issue / beginner），编号倒序
    assert [issue.number for issue in ctx.starter_issues] == [3, 2]
    assert ctx.threads == []

    assert "CONTRIBUTING.md" in ctx.contributor_files
    assert "pyproject.toml" in ctx.contributor_files
    assert "ci.yml" in ctx.contributor_files  # .github/workflows 按前缀确定性发现


def test_overview_skips_community_data_but_keeps_repository_files():
    ctx = context_from_backup("acme", "widget", BACKUP, mode="overview")

    assert ctx.threads == []
    assert ctx.starter_issues == []
    assert ctx.contributor_files == ""
    assert "src/" in ctx.file_tree
    assert "pyproject.toml" in ctx.project_files
    assert [release.tag for release in ctx.releases] == ["v1.2.0"]
