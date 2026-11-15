# 贡献指南

感谢愿意给 Widget 提交改动。请先读 README 的安装与测试章节。

## 开发流程

1. 从 `main` 切分支，改动尽量小；
2. 运行离线测试：`.venv/bin/python -m pytest tests/ -q`；
3. 提交 PR 前确认 CI 通过，并在描述里关联对应 Issue。

## 提交信息

首行一句话概述，正文按要点写动机与影响。
