# Asset Pack v1 依赖调研

> 调研日期：2026-08-21。范围仅覆盖 v0.4.0 的 Schema、本地校验和 WebGAL Adapter；
> Git/AI Provider 在实现前必须重新核对传输、归档和生成服务依赖。

Repo2Gal 不自行实现 JSON Schema、SemVer、SPDX、BCP 47、文件类型识别或 CSS Color
解析。以下依赖只通过公开 API 做薄适配。

| 能力 | 选择与版本范围 | 功能与接口 | 维护/采用（调研时） | 许可证与风险 |
|---|---|---|---|---|
| JSON Schema | `jsonschema[format-nongpl]>=4.26,<5` | `Draft202012Validator` + 显式 `FormatChecker`；不允许远程 `$ref` 获取 | 4.26.0（2026-01）；4,973 stars；约 84 万依赖仓库；2026-08 仍有提交，未 archived | MIT，GPL-3.0 兼容；传递依赖较多，`rpds-py` 源码构建可能需要 Rust |
| SemVer | `semver>=3.0.4,<4` | `Version.parse()` 严格要求完整版本；适配层额外拒绝非 ASCII | 3.0.4（2025-01）；523 stars；2026-08 仍有提交，未 archived | BSD-3-Clause；纯 Python、零运行时依赖 |
| SPDX | `packaging>=26.3,<27` | `packaging.licenses.canonicalize_license_expression()`；支持标准 ID、表达式与 `LicenseRef-*` | 26.3（2026-08）；745 stars；PyPA 基础组件，未 archived | Apache-2.0 或 BSD-2-Clause；纯 Python、零运行时依赖 |
| BCP 47 | `langcodes>=3.5.1,<4` | `tag_is_valid()`；适配层先拒绝 `_`、空 subtag 和非 ASCII | 3.5.1（2025-12）；迁移后仓库 31 stars；2026 年仍维护，未 archived | MIT；默认纯 Python，不安装非必需语言数据 extra |
| MIME magic | `python-magic>=0.4.27,<0.5` + `libmagic` | `magic.from_buffer(..., mime=True)`；只读取受限头部，不解压，不按扩展名猜测 | Python wrapper 2,917 stars；PyPI 0.4.27，仓库 2026-07 仍有提交，未 archived | wrapper MIT，libmagic BSD-style；依赖系统 magic 数据库，结果需做少量 IANA alias 归一化 |
| CSS Color | `coloraide>=8.11.1,<9` | `Color.match(..., fullmatch=True)`；支持 CSS Color 4 与 `oklch()`，适配层拒绝其私有 `color(--*)` 扩展 | 8.11.1（2026-08）；351 stars；2026-08 仍有提交，未 archived | MIT；纯 Python，无网络和文件访问 |

公开来源：

- https://python-jsonschema.readthedocs.io/en/stable/validate/
- https://github.com/python-jsonschema/jsonschema
- https://github.com/python-semver/python-semver
- https://packaging.pypa.io/en/stable/licenses.html
- https://github.com/georgkrause/langcodes
- https://github.com/ahupp/python-magic
- https://facelessuser.github.io/coloraide/color/

## 未选择的候选

| 候选 | 结论 |
|---|---|
| `license-expression` | Apache-2.0、维护活跃且 SPDX AST 能力完整，但标准 symbol 校验默认不接受项目需要的自定义 `LicenseRef-*`；当前只需合法性/规范化，`packaging.licenses` 更薄。未来做许可证集合分析时再评估。 |
| `puremagic` | MIT、纯 Python。兼容 Python 3.10 的 1.30 无法可靠区分 Ogg 容器且含旧 MIME；改进后的 2.2.0 要求 Python 3.12，不符合本项目 `>=3.10`。不作为安全校验依据。 |
| `packaging.version` | 实现 PEP 440，不是严格 SemVer，会接受或规范化本规范应拒绝的版本。 |
| `tinycss2` / `webcolors` | 前者只分词、不验证完整 `<color>` 语义；后者不支持 `oklch()`。自行补 grammar 违反“不重复造轮子”。 |

## 安全边界

- manifest 限 1 MiB、256 个资产；媒体单文件限 128 MiB、授权材料单文件限 8 MiB，
  全部声明文件总计限 512 MiB；
- Schema、格式、路径、普通文件、符号链接、扩展名、magic MIME、SHA-256 和 Profile 分层校验；
- `libmagic` 仅在实际校验 Asset Pack 时延迟加载，不影响不使用素材包的默认流程；
- 包内逐级使用 `openat`/`O_NOFOLLOW`；打包时在同一源 fd 上哈希并复制，目标以 `O_EXCL`
  创建，处理“校验后文件被替换”的 TOCTOU；缺少这些 OS 能力时只拒绝 Asset Pack 路径；
- 不执行包内脚本，不下载远程 `$ref`，不转码用户素材。
