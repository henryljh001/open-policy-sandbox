# 版本与发布规范

本文定义 Policy Sandbox 的可持续更新路径。`main` 是唯一公开集成主线；正式版本由不可变的带注释 Git 标签和 GitHub Release 共同标识。

## 版本规则

项目采用语义化版本 `MAJOR.MINOR.PATCH`：

- `MAJOR`：稳定契约发生不兼容变更，并提供迁移说明；
- `MINOR`：向后兼容的新能力、新插件、新适配器或新输出；
- `PATCH`：向后兼容的缺陷、安全、验证或文档修复。

在 `1.0.0` 之前，破坏性变更可随 `MINOR` 发布，但必须在 Changelog 中标为 `BREAKING`，写明受影响契约和迁移办法。Schema、插件 ID、适配器 ID 与审计字段不能静默改义。

版本号必须同时更新并由测试强制对齐：

1. `pyproject.toml` 的 `project.version`；
2. `src/policy_sandbox/__init__.py` 的 `__version__`；
3. `README.md` 的当前版本；
4. `CURRENT_STATE.md` 的应用版本；
5. `CHANGELOG.md` 的对应版本节。

## 分支与提交

- `main` 始终保持可验证、可构建；
- 日常变更从短期主题分支进入，建议命名 `feat/*`、`fix/*`、`docs/*`、`release/*`；
- 每个 Pull Request 必须通过 CI；涉及 Schema、插件协议或适配器协议时，必须同步示例、测试和迁移说明；
- 禁止强推 `main`，禁止移动或复用已经发布的标签；
- 紧急修复从当前发布标签派生，合并回 `main` 后发布新的 `PATCH`，不改写旧 Release。

## 发布闸门

每次正式发布至少满足：

1. `ruff`、完整单元测试和隔离扫描通过；
2. Schema 与示例契约通过专门测试；
3. wheel 构建成功，版本面一致；
4. `CHANGELOG.md`、`CURRENT_STATE.md` 与使用边界同步；
5. GitHub Actions 在目标提交上全部通过；
6. 创建带注释标签 `vMAJOR.MINOR.PATCH`；
7. GitHub Release 绑定该标签并附 wheel 的 SHA-256；
8. 保存提交、树、标签、CI、Release 和制品哈希的本地绑定记录。

若任一硬门失败，版本只能保持候选状态，不得创建或移动正式标签。

## 标准发布流程

```text
主题分支 / release 分支
  → 同步版本面与 Changelog
  → 本地验证
  → Pull Request 与远端 CI
  → 合并 main
  → 再次验证 main
  → 创建不可变 annotated tag
  → 构建 wheel、计算 SHA-256
  → 创建 GitHub Release
  → 写入本地来源绑定记录
```

维护命令示例：

```powershell
$env:PYTHONPATH = "src"
python -m ruff check src tests scripts
python -m unittest discover -s tests -v
python scripts/check_isolation.py
python -m pip wheel . --no-deps --wheel-dir dist
git tag -a v0.6.1 -m "Policy Sandbox v0.6.1"
git push origin main
git push origin v0.6.1
```

标签只能在目标提交的远端 CI 通过后创建。示例中的版本号必须替换为实际新版本。

## 兼容性与迁移

- 带版本的 Schema 或协议在其版本内只做兼容扩展；删除字段、收紧合法值或改变单位语义需要新契约版本；
- 已发布的插件和适配器标识不得指向不同语义；新语义使用新 ID；
- 审计包必须记录核心包、领域插件、适配器、Schema 和输入摘要版本；
- 弃用至少跨一个 `MINOR` 保留警告，下一次不兼容发布方可删除；
- 真实数据能力、U6—U8 门和软件版本彼此独立，升级软件版本不自动提高使用等级。

## 当前演进路径

- `0.6.x`：稳定合成沙盒、隔离门、适配协议、CI 与发布工程；
- 后续 `0.x`：在授权和审计边界内扩展新型城镇化适配与决策工作台；
- `1.0.0`：至少两个独立插件或适配器验证核心契约，迁移政策、发布自动化、安全与治理流程达到稳定状态后再评估。

路线只定义兼容与发布秩序，不承诺尚未通过的真实校准、回溯、隐私审查或人工发布门。
