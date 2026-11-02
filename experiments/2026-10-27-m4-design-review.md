# M4-DESIGN-01：Scene Map与子地图边界设计审查

编号：EXP-20261027-016；日期：2026-10-27；主责任：mapping_engineer。
状态：已完成（具体设计与既有入口审计）；M4实现及软件试制尚未开始。
输入：用户在M3-SW-04交接后确认继续；
[当前具体方案](../docs/M4_SOFTWARE_TRIAL_PLAN_20261027.md)。

## 目的、环境与保护范围

按Local Map→Probability→Uncertainty→Scene Map顺序推进，明确有界子地图生命周期、
参考系/注册、覆盖/时间/质量查询、资源与恢复，给出可独立验证的下一批工作包。
不重开暂缓的研究模型质量或以缺少真实数据为由反复重做已通过的M3场景。

先读取根规范、PROJECT_STATUS、SYSTEM_ARCHITECTURE、相关模块规则和接口/坐标文档，
核对实际工厂、地图更新/滚动/查询、ROS包装/消息编解码、应用与回放调用链。
分支feature/engineering-initialization；工作树已有大量历史未提交改动，本轮全部保留。
`.runtime/runs/m4-design-probe`的忽略检查命中；不提交运行产物、无Git提交或推送。
只在本仓新增/更新设计与索引文档，不修改同级研究仓库、环境、配置或业务/测试源码。

解释器核对为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，
所有Python经`bash ros_ws/sim01_env.sh ...`运行；没有ROS Master、网络、GPU或模型加载。
审计脚本与产物独立保存于
[m4-design-20261027T191440068147](../.runtime/runs/m4-design-20261027T191440068147/report.json)，
精确脚本保存在该目录audit.py，既有测试日志为baseline-tests.log。

## 只读事实及审计结果

以下`passed`表示源码事实或承载能力符合审计预期，不表示缺失功能已实现。
源代码证据及符号位置列于[方案第1节](../docs/M4_SOFTWARE_TRIAL_PLAN_20261027.md#1-源码事实与验证边界)。

| 探针 | 实际事实 | 设计含义 |
| --- | --- | --- |
| P1 选型 | 当前create_map('m4_fixture')明确unknown backend | M4尚无创建入口，后续仍须显式选型 |
| P2 移出窗口 | M3首帧有cell，合法远移空帧后无cell，原点查询unknown | 历史子地图不能直接用滚动缓存替代 |
| P3 返回 | 再用空帧返回原窗口仍unknown/observed=false | 现有M3不恢复旧历史，Scene保留/再观测策略必须单列 |
| P4 快照结构 | 当前快照是单套odom网格，不含context/submap目录 | Scene需先在mapping内形成同一map网格的完整视图 |
| P5 状态域 | SpatialContext无独立reset/epoch或map←odom字段 | 同run未声明跳变无法可靠识别；不能据此关闭正式定位/注册门槛 |
| P6 消息承载 | 手工map网格fixture实际serialize/deserialize保留map frame、Scene index和身份 | 当前字段可承载一个固定Scene视图，不表示M4转换器存在 |
| P7 应用承载 | 同一手工map查询响应经真实编码/解码，MapQueryClient原样保真 | 应用可消费显式map点，未做坐标转换、子地图查询或真实模型推理 |
| P8 历史质量 | 现有M3超TTL查询stale，保持原贡献时间/范围；query不改快照 | Scene封存/查询不得刷新质量或时间 |
| P9 独立坐标算例 | Fraction计算非零平移后的Scene index=[80,32,8] | 验证拟用格点公式的一个设计算例，不是M4场景验收 |

全部9项通过；report明确`m4_implementation_executed=false`、`ros_master_started=false`。
P6/P7的输入是单独手工fixture，未将其写入实际地图或冒充M4公开输出。
不修改已有收据、权重或历史实验，不做Hash清单。

## 具体设计交付与限制

方案选择一个活动M3和有界封存子地图目录；Scene不对累计快照再做概率累计。
窗口切换前保留旧估计，重叠cell转移唯一所有权；新贡献整条接管概率/质量/时间，
缺失范围不能向旧子地图借用。旧副本移除，最新owner淘汰后不回搜旧版本。
封存几何固定、数值不再融合，但可因所有权/资源删除条目；不承诺内存中保留全量档案。
原始实验收据继续独立保留。

坐标采用具名、绑定run/clock/有效时段的固定合成T_map_odom，显式非零整格平移。
公开使用一套固定map Scene网格，index与同revision快照一致；缺cell/覆盖空洞仍unknown。
首版不支持旋转、动态注册、非整格重采样或把odom改名map。
Scene结构变化时刻与贡献时刻分离，封存/空移动/淘汰不能刷新证据。
联合事务须在局部暂存和Scene导出校验成功后一次提交，Scene后段失败不能污染M3水位。

定位reset仍要求显式新run和空实例；现有公共上下文缺独立epoch，未声明同run跳变
不能可靠识别。真实定位连续性、map←odom动态修正和历史重注册继续单列为正式M4缺项。
配置/字段的本轮行为保持不变，拟用m4_fixture及配置文件当前不可运行。

工作包依次为SW-01显式合同/输入/独立所有权预期，SW-02纯Python候选，
SW-03时序/资源/联合原子性组合，SW-04实际ROS/公开回放/应用和旧入口交接。
完整生产者/消费者、兼容、恢复和独立验收矩阵见方案第7—8节。

## 本轮验证

既有定向回归使用tests/test_m3_rolling_map.py（15项）、test_local_map_replay.py（4项）、
test_map_query_ros.py（7项）及test_application_query_client.py（6项），共32/32通过。
覆盖当前滚动/TTL/有界状态、公开回放、新run、消息五状态和应用质量保真。
未新增算法测试或业务代码；本轮不重复全仓570项或ROS回归，之前M3-SW-04的570项及
ROS记录仅作为已有基线引用，不写成本轮新运行结果。

可复现审计与既有定向检查命令：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B .runtime/runs/m4-design-20261027T191440068147/audit.py
```

该脚本为已有公开API的只读探针/手工承载fixture和测试调用，每次创建新审计输出目录，
不运行Scene Map、ROS Master或模型。没有失败探针或新增运行回归失败。
文档相对链接/代码符号与状态一致性检查、git diff --check通过。

## 修改文件与下一交付

新增：docs/M4_SOFTWARE_TRIAL_PLAN_20261027.md、本记录。
更新：PROJECT_STATUS.md、docs/DEVELOPMENT_PLAN.md、docs/STAGE_ADVANCE_PLAN_20261027.md、
docs/SYSTEM_ARCHITECTURE.md、docs/COORDINATE_SYSTEM.md、docs/RUNTIME_CONFIGURATION.md、
docs/DECISION_LOG.md、docs/EXPERIMENT_LOG.md。
原因是登记具体设计、现有证据与下一工作包，未修改公共字段或运行配置。

已有能力：M3滚动累计、现有快照/查询/应用与公开回放。
本轮已交付：M4具体设计、9项事实/承载审计及非零注册算例。
本轮已验证：上述探针和32项既有定向；没有M4候选或M4实际ROS验证。
尚未验证：M4实现、真实注册/定位跳变、真实质量、机载资源、正式PERF-01/阶段退出。

下一项M4-SW-01（计划，mapping_engineer）按具体方案确认后执行：先保存显式注册/输入、
轨迹及独立目录/所有权/时间预期，不运行Scene候选。后续依次推进，不提前做DEM、
模型质量研究或科研对照；研究仓库不改动，research保持fail-closed。
