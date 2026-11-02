# EXP-20261027-006：M2概率更新方案与软件试制准入审查

日期：2026-10-27；主责任：mapping_engineer；类型：源码审计/设计检查，非算法运行。
状态：方案交付已完成，M2算法及试制配置尚未实现；具体软件试制准入待确认。
交付：[M2_SOFTWARE_TRIAL_PLAN_20261027](../docs/M2_SOFTWARE_TRIAL_PLAN_20261027.md)。

## 审计依据与结论

当前`SparseLocalMap.update`校验run/clock、严格参考时序、坐标/网格和质量后，
以`_cells.update(pending)`覆盖最新概率；滚动只重映射索引并保留已有cell时间。
`query`根据请求时间和max_age返回stale，不做概率衰减或累计。
placeholder的0.9是确定性fixture值，confidence不可用，不能声称具有独立测量似然。

方案首版限定显式合成逆观测domain的fixture，研究model及当前placeholder不能直接累计。
用有界log-odds验证算术/时序，TTL失效并在新证据到达后从先验重启；不把读取、
空/无回波、中性或失效消息当作新的自由/占据证据，不刷新最后贡献时间。
真实模型概率校准、观测相关性、动态环境与M3不确定性融合均没有由方案宣告解决。

## 本轮只读验证

- 已检查当前分支`feature/engineering-initialization`及脏工作区，保留全部既有改动。
- 只读打开并确认P3组合ROS、三组M1回放及最终应用ROS的5份主报告均`passed=true`。
  这些是[上轮软件交接](2026-10-27-p3-m1-app-handoff.md)的既有证据，没有重跑或覆盖。
- 在指定解释器`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`下核对方案数值：
  先验0.5、界限±ln(9)，合成0.75/0.75/0.25/0.25/0.25依次给出
  0.75/0.9/0.75/0.5/0.25。此为设计算例检查，不是M2实现或模型效果测试。
- 检查状态/开发计划/M1门禁/决策/设计文档的引用、边界与相对链接；`git diff --check`通过。

本轮只修改中文设计、状态与索引，不新增业务测试、不运行ROS、训练、forward或正式性能。
最近的469项轻量回归来自EXP-20261027-005，本轮不追加一次同样的回归数量作为新算法证据。

## 准入、文件与恢复

已交付G0—G5准入条件、M2-SW-01—04工作包及A—L共12类验收。
正式M1真实输入/资源门禁保持；软件试制是单独提议，不在本轮自动改为通过。
后续第一项为M2-SW-01：独立合成证据fixture、显式参数和数值oracle，再开发固定网格候选、
时序/TTL/滚动及独立ROS/回放交接。

新增本记录和M2设计，更新PROJECT_STATUS、DEVELOPMENT_PLAN、STAGE_ADVANCE_PLAN、
M1门禁附注、DECISION_LOG和EXPERIMENT_LOG。没有改变公共ROS字段、默认地图行为、
研究仓库、模型资产或历史run，不提交/推送。恢复仅需修订后续排程，不涉及运行代码回退。
