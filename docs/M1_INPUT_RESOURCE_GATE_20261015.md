# M1 Local Map真实输入与资源验收矩阵（待实施）

版本：v0.1；日期：2026-10-15；状态：待外部输入，未执行正式M1验收；
主责任角色：mapping_engineer，Technical Lead协调设备、资源和PERF-01证据。
依据：[阶段计划§2/§6](DEVELOPMENT_PLAN.md)、[现有滚动fixture](../experiments/2026-10-14-local-map-rolling.md)、
[PERF-01预算](../configs/perf01_budget.yaml)、[Phase 1正式复核](PHASE1_EXIT_REVIEW_20261015.md)。

原计划Phase 4为**2026-12-16—2027-02-10**；本表是准备后续正式验收的
输入/判定清单，不提前启动地图阶段或新性能运行。当前`SparseLocalMap`
可选整格滚动、有界活跃cell、同实例单点查询和快照均仅由软件fixture验证。
`map_budget`的0.5m、20Hz、1024MB及覆盖范围标注为参考估计，**不是**
目标机资源/质量验收的已确认阈值；`max_active_cells`不等于实际RSS上限。

| 项目 | 取得输入后应验证的结果 | 当前判定/所缺证据 |
| --- | --- | --- |
| 来源、时钟及坐标 | 只收perception的OccupancyObservation及同观测时刻SpatialContext；记录run/clock、采集时间、frame、标定和状态质量。旋转/跳变必须有显式变换；缺失或超龄不能当free | **阻塞**：真实Radar/IR与设备时钟映射、有效外参/状态及其记录未到位；不得订阅AircraftState/Odometry/训练LiDAR绕过合同 |
| 运动与窗口 | 真实输入在约定航速、平移/转弯/大位移及断流/恢复条件下，逐观测对齐窗口原点、覆盖、重叠保留、移出淘汰、新区域unknown和查询/快照revision | **未验收**：既有35/50/70m/s与滚动短测只为具名fixture；速度点已确认，转弯/连续时长和适用场景待正式约束 |
| 内存与处理时延 | 同一目标平台、同一run记录地图进程RSS峰值/持续窗口、活动cell数、更新耗时分布及查询读时延；对照经确认的资源预算和采样时钟 | **阻塞**：目标平台、实际监测/功耗、内存/查询阈值及正式时长未冻结；不能以`max_active_cells`或开发机测试代替 |
| 边界与降级 | 重复、乱序、未知、无回波、断流老化、新run及服务关闭/开启的身份、状态和拒绝理由可重现；不刷新旧证据，不将未观测当free | 软件fixture已覆盖部分；缺真实输入与资源证据，单点服务之外的区域查询另列范围，不偷换成既有能力 |

外部条件具备后，先确认正式指标/场景和采集许可证据，采用独立run记录输入、
逐帧输出、进程资源和关闭审计，再由tester审查回放与测量；有失败保留原始run。
M1真实输入/资源门槛尚未通过，**M2 Probability只保留原计划定义**：未来多帧
累计、去重、老化须单独提方案和验收，当前不实现。DEM、研究模型质量、自主
控制与科研对照不属于此验收。回退只需停止后续候选入口，既有固定/滚动fixture
和旧查询保持原状，不动历史运行目录。

## 2026-10-15补充：可选软件资源诊断，非正式验收

`bash ros_ws/sim01_env.sh python -B ros_ws/local_map_query_run.py --mode rolling
--sample-resources --port 11473`只对当前软件fixture的地图ROS进程采样；
省略开关仍是旧查询行为。采样器在同run输出`resources.json`，要求
同一地图进程至少两次采样，报告RSS采样峰值和原始样本，显式将硬件、
功耗和正式性能标为未验证。[本次记录](../experiments/2026-10-15-iface-replay-training-ray-m1-resource.md)
仅得到开发机一次短测的11次RSS样本、5快照/7占据/20查询及旧服务回归；
**不是**长时间实际RSS上限或目标平台测量。目标平台、真实同run输入、
活跃cell和更新/查询时延分布、功耗/温度、连续时间与批准预算仍缺失；
资源诊断入口不能解除上表任一正式阻塞项。

## 2026-10-27补充：独立软件推进与M2提案

[P3交接、M1公开占据回放及应用客户端](../experiments/2026-10-27-p3-m1-app-handoff.md)
已完成软件子范围，上表真实输入/物理资源门禁仍开放。
已交付[M2概率更新与合成数据软件准入提案](M2_SOFTWARE_TRIAL_PLAN_20261027.md)，
用户随后已确认默认关闭的合成逆观测软件试制，区别于正式M1→M2通过。
当前[SW-01输入契约、配置及独立oracle](../experiments/2026-10-27-m2-fixture-oracle.md)已完成；
SW-02固定合成累计/查询及基础TTL也已完成，见
[固定候选记录](../experiments/2026-10-27-m2-fixed-map.md)；
SW-03滚动/完整时序及有界状态离线验证随后完成，见
[滚动记录](../experiments/2026-10-27-m2-rolling-time.md)。
SW-04实际ROS候选及公开占据回放/应用交接随后完成，见
[软件交接记录](../experiments/2026-10-27-m2-ros-handoff.md)。上述cell/身份上限及
合成ROS收据不证明RSS/查询时延或功耗达标，不据此修改原正式门槛。
