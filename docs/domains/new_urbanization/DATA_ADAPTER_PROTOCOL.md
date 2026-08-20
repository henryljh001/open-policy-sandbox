# 汇总数据适配器协议｜新型城镇化

## 目标

把外部汇总数据与模型校准目标之间的转换做成可注册、可拒绝、可追踪的边界。适配器负责口径和来源，不负责修改模型参数，也不把数据来源的相关性解释为政策因果效应。

## 依赖方向

```mermaid
flowchart LR
    A["数据卡 + 汇总记录"] --> B["注册式适配器"]
    B --> C["标准校准目标 + 来源追踪"]
    C --> D["重复实验"]
    D --> E["总体矩误差与容差"]
    E --> F["校准运行记录"]
```

模拟引擎不读取文件，不依赖具体数据源。应用层通过适配器工厂获得标准目标，再调用既有重复实验与校准接口。

## 数据卡必填项

- 数据集标识、标题、发布者、来源类型、许可和授权状态；
- 空间层级与地区标识；
- 参考年份和指标清单；
- 处理步骤、局限和 `synthetic` 标记。

每条记录必须有独立 `record_id`、指标、数值、单位、参考年份和状态。任何单位、年份或重复指标冲突均硬拒绝，不静默换算。

## 当前八指标映射

| 适配指标 | 模型输出 | 单位 | 默认容差 |
|---|---|---|---|
| total_population | final_total_population | person | 相对 2% |
| urbanization_rate | final_urbanization_rate | percent | 绝对 1 |
| employment_rate | final_employment_rate | percent | 绝对 1 |
| debt_to_revenue | final_debt_to_revenue | percent | 绝对 5 |
| education_capacity_per_1000 | final_education_capacity_per_1000 | capacity/1000 | 绝对 2 |
| health_capacity_per_1000 | final_health_capacity_per_1000 | capacity/1000 | 绝对 0.5 |
| housing_occupancy_rate | final_housing_occupancy_rate | percent | 绝对 1 |
| used_construction_land | final_used_construction_land | synthetic area | 绝对 2 |

容差是显式配置，不是统计置信区间或法定标准。真实适配阶段必须重新论证并版本化。

## 注册与工厂

适配器通过 `@register_aggregate_adapter` 注册，以配置对象构造。工厂对未知名称硬失败并列出可用项，不回退默认实现。实现模块自动发现；导入失败直接暴露。

当前唯一实现 `new_urbanization_synthetic_aggregate_v1` 明确声明 `accepts_real_data=false`，并拒绝任何 `synthetic=false` 数据。

## 真实数据接入门

新增真实适配器前必须满足：

1. 明确许可、授权范围和可公开字段；
2. 固定来源 URL/文件摘要、版本和下载日期；
3. 记录口径、修订、缺失、单位换算和行政区划处理；
4. 私有读取器与凭据不进入公开仓库；
5. 通过独立回溯与外推检查；
6. U6 由校准证据另行裁定，不因适配器可运行而自动通过。
