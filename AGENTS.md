# Policy Sandbox 项目规则

本文件适用于本目录及其子目录，优先于用户级通用导航中的项目默认设置。

## 项目定位

本项目是可公开的政策沙盒应用工程，不是研究数据仓库。默认只能使用本仓库中的合成示例或用户明确授权的数据。

## 单一真相源

1. 产品边界：`docs/PRODUCT_SCOPE.md`
2. 技术架构：`docs/ARCHITECTURE.md`
3. 跨模块契约：`schemas/*.schema.json`
4. 隔离规则：`docs/adr/0001-research-app-isolation.md`
5. 当前路线：`docs/ROADMAP.md`
6. 首个领域：`docs/domains/new_urbanization/README.md`
7. 路径边界：`docs/PATHS_AND_BOUNDARIES.md`
8. 开源许可：`LICENSE` 与 `NOTICE`

## 强制规则

- 不读取、复制或软链接相邻研究项目的语料、台账、截图和待签数据，除非用户逐项授权；
- 不在代码、文档、测试和配置中写入本机项目绝对路径；
- 不提交 `.env`、密钥、个人信息、私有数据或不可核实的真实政策数字；
- 核心域层不得依赖具体 Web 框架、数据库或模型供应商；
- 新增模拟引擎、指标计算器或干预策略时，使用唯一注册名、注册装饰器和工厂；
- 未知插件名必须显式报错，不静默回退；
- 模拟结果必须携带输入摘要、引擎名/版本、随机种子、警告和可复现标识；
- LLM 只能作为可选适配器；自由生成的数字不得进入政策事实字段；
- 所有公开示例标明 `synthetic=true`。

## 每次改动最低校验

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python scripts/check_isolation.py
```

JSON Schema 或示例变化时，还要运行 schema/示例互校。首次公开发布前必须完成许可证、安全披露与贡献治理裁决。

