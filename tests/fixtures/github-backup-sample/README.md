# github-backup 回归样本

本目录是一份**结构真实、内容合成**的 `python-github-backup` 落盘样本，供
`tests/test_backup_fixture.py` 做离线回归。目录布局与上游 `>=0.65,<0.66` 的公开 CLI
输出一致：

```text
repositories/<repo>/
├── repo2gal-repository.json   # Repo2Gal 受控 REST 补充的仓库概览
├── issues/<number>.json
├── pulls/<number>.json
├── discussions/<number>.json
├── releases/<id>.json
├── wiki/<page>.md
└── repository/                # 源码工作树（此处不含 .git）
```

约定：

- **JSON 字段形状**取自真实备份（Issue 的 `labels` 为对象数组、`comment_data` 含
  `reply_data`，Pull 的 `comment_regular_data` / `review_data`，Discussion 的
  camelCase 键与 `author` 键），用于在离线测试里固定上游 schema；
- **所有标识符、账号、标题与正文均为合成内容**，不对应任何真实仓库或用户；
- 不得把真实第三方仓库备份或生成产物复制进本目录（`AGENTS.md` 第 7 节）；
- 上游备份格式变化时，先更新本样本，再确认解析器仍通过。

`tests/test_backup_fixture.py` 覆盖三种模式从同一份备份构建 `RepoContext` 的差异：
Chronicle 读全部讨论、Quick Start 只取开放且带新人标签的 Issue 并读取贡献者入口文件、
Overview 完全跳社区数据。
