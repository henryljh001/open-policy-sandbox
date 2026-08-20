# Policy Sandbox｜开源政策沙盒

Policy Sandbox 是面向政策研究者、治理部门分析人员和高层管理者的开源政策实验框架。它把政策工具、行为假设和外部压力转成可审计配置，通过可复现的条件情景比较政策组合的总体影响、群体差异、资源代价和失效风险。

当前版本为 `0.6.0`，使用等级为 **Demo**。首个领域插件是“新型城镇化”，MVP 聚焦“农业转移人口市民化 × 县城综合承载能力”。仓库不包含真实政策语料、研究台账、个人数据或人工待签材料。

## 当前可运行纵切

```text
五类合成县域
  → S0—S8 政策包与七类政策工具
  → 默认一万户合成家庭与五类压力
  → 共同随机数重复与公平方案比较
  → 总体结果、群体差距、财政土地账、Pareto 前沿
  → 一页纸摘要与机器审计包
  → 注册式汇总数据适配器与合成校准检查
```

聚合模型负责人口、财政和土地守恒；家庭层只表达技能、来源、家庭结构和空间位置差异。家庭 ID 是程序生成编号，不含姓名、地址、联系方式或真实个人映射。

## 设计底线

- 证据优先：政策事实和校准目标必须关联可定位来源；
- 情景而非预言：输出是条件化模拟，不宣称确定预测；
- 假设显式：政策、行为、压力、阈值、单位和容差不得隐藏；
- 人在回路：不自动替代政策判断、公众参与或法定审批；
- 可复现：记录配置、插件/适配器版本、随机种子、失败原因和摘要；
- 不设暗分：默认不生成综合分，只报告分目标结果与无权重 Pareto 前沿；
- 默认隔离：公开仓库只含合成示例，私有数据不进入版本控制；
- 严格适配：未知适配器、指标、单位、年份和重复记录全部硬拒绝。

## 目录

- `src/policy_sandbox/domains/`：领域状态、守恒、微观行为、编译与目录；
- `src/policy_sandbox/plugins/`：领域、引擎、政策工具和压力注册实现；
- `src/policy_sandbox/adapters/`：汇总数据适配器协议、注册表和实现；
- `src/policy_sandbox/application/`：运行、实验、比较、决策产品和校准检查；
- `schemas/`：场景、实验、比较、简报、审计、数据卡和校准契约；
- `examples/`：全部标记 `synthetic=true` 的配置与数据；
- `docs/domains/new_urbanization/`：政策基线、模型卡、适配协议与验证；
- `tests/`：注册、守恒、schema、压力、比较、校准和隔离测试。

## 本地验证

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python scripts/check_isolation.py
```

运行公平方案比较并生成四件套：

```powershell
$env:PYTHONPATH = "src"
python scripts/compare_scenarios.py `
  --plan examples/new_urbanization/comparison_plan.json `
  --output-dir output/comparison_demo
```

运行合成汇总数据适配与校准检查：

```powershell
$env:PYTHONPATH = "src"
python scripts/run_calibration.py `
  --data examples/new_urbanization/synthetic_aggregate_calibration.json `
  --scenario S0 `
  --output output/calibration_demo.json
```

合成校准通过只证明适配器、口径、容差和审计链可以运行，**不代表 U6 真实校准通过**。

## 使用边界

- 所有家庭、行为概率、政策效应、压力效应、默认阈值和校准示例均为合成假设；
- 重复区间只表达模型内随机性，不是真实地区统计置信区间；
- Pareto 前沿不含价值权重，不构成政策排序或推荐；
- 当前适配器明确 `accepts_real_data=false`，不能读取或背书真实数据；
- 不得把结果用于真实县域预测、排序、审批或正式资源配置；
- U6 真实数据校准、U7 回溯/隐私审查和 U8 人工发布门尚未通过。

项目采用 Apache License 2.0。详见 `CURRENT_STATE.md`、`docs/PATHS_AND_BOUNDARIES.md`、`docs/domains/new_urbanization/MODEL_CARD.md` 和 `DATA_ADAPTER_PROTOCOL.md`。
