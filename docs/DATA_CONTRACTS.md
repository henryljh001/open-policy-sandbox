# 数据契约｜Policy Sandbox

## 1. 契约对象

| 对象 | 文件 | 作用 |
|---|---|---|
| Evidence | `schemas/evidence.schema.json` | 记录来源、定位、哈希与核验状态 |
| Commitment | `schemas/commitment.schema.json` | 表达政策目标、对象、口径和证据引用 |
| Scenario | `schemas/scenario.schema.json` | 表达基线、干预、引擎、参数与种子 |
| SimulationRun | `schemas/simulation_run.schema.json` | 表达单次运行、总体/分组结果和警告 |
| ExperimentRun | `schemas/experiment_run.schema.json` | 表达重复次数、分位数、标准差和失败率 |
| DomainConfig | `schemas/domains/*.domain.schema.json` | 表达领域模块、尺度和时间步长 |
| MicrosimScenario | `schemas/domains/*_microsim_scenario.schema.json` | 表达合成家庭、行为和压力配置 |

## 2. 契约原则

- ID 稳定、不可复用；
- 原始表达与标准化字段并存；
- 数值、单位、时间和语义分列；
- 事实、假设、状态和结果不得共用字段；
- 证据使用引用 ID，不在结果中复制大段原文；
- 所有合成数据和目标必须标记 `synthetic=true`；
- schema 版本采用显式字段，不依赖文件名猜测；
- 未知字段默认拒绝，以便及早发现接口漂移。

## 3. 情景最小语义

`Scenario` 把事实和假设分开：

- `commitment_ids` 只引用事实层；
- `baseline` 表达初始状态；
- `interventions` 表达政策动作与显式参数；
- `pressure_package` 表达外部压力与显式参数；
- `microsim_config` 表达样本规模、行为概率和合成校准目标；
- `engine` 表达插件名与配置；
- `random_seed` 固定随机性；
- `assumptions` 明示无法由事实直接推出的判断。

## 4. 单次运行审计

`SimulationRun` 必须保留：场景 ID/版本与摘要哈希、引擎名/版本、随机种子、状态、总体结果、分组结果、警告和可复现标志。单次运行不得把家庭记录本身嵌入公开结果。

## 5. 重复实验审计

`ExperimentRun` 必须保留：

- 原场景与重复配置的输入摘要；
- 基础种子、总重复数、成功数和失败数；
- 明确的失败原因计数与失败率；
- 每个总体/分组指标的均值、标准差、P05、P50 和 P95；
- “模型内随机区间，不是真实地区置信区间”的边界警告；
- 可复现与合成标记。

## 6. 校准接口

每个目标矩必须声明 `target`、`tolerance` 和 `mode=absolute|relative`。目标来源由适配层负责；I3 只接受 `synthetic_targets=true`，因此接口通过不等于 U6 经验校准通过。

## 7. 版本兼容

- 破坏性字段变化提升 schema 主版本；
- 新增可选字段提升次版本；
- 适配器负责旧版迁移，核心不隐式猜测；
- 每个公开数据集附数据卡、许可和生成脚本版本。
