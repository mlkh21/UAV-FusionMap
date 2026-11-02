# M3-SW-04：独立ROS、公开回放与应用质量交接

编号：EXP-20261027-015；日期：2026-10-27；主责任：tester。
状态：已完成（合成软件交接）；依据：用户连续“继续”确认的
[M3方案](../docs/M3_SOFTWARE_TRIAL_PLAN_20261027.md)。

## 只读审计与问题

修改前核对Git状态、功能分支、忽略规则及真实生产/消费链，保留全部已有未提交改动。
分支为feature/engineering-initialization，运行产物仍在忽略的.runtime/runs；未提交或推送。
已读根及mapping/application/ros_ws/tests/docs/experiments规范、状态、架构和相关接口约定。

| 真实位置/符号 | 本轮前已有能力 | 本轮前证据界限 |
| --- | --- | --- |
| [FixedIntervalProbabilityMap](../mapping/ufm_mapping/fixed_interval_probability_map.py)、[RollingIntervalProbabilityMap](../mapping/ufm_mapping/rolling_interval_probability_map.py) | 显式固定/滚动区间累计、缺失锁存及TTL/淘汰重建 | SW-01—03已有离线与消息序列化证据，尚非M3实际ROS |
| [create_map](../mapping/ufm_mapping/factory.py) | 共享latest/M2选型，默认不导入候选 | 修改前不识别m3_fixture |
| [mapping main](../ros_ws/src/uav_fusionmap_mapping/scripts/perf01a_map_node.py) | 占据→地图→快照/查询，同实例和锁；错误事件拒绝，无fallback | 修改前仅显式M2候选装配 |
| [replay_observations](../mapping/ufm_mapping/replay.py)、[replay CLI](../ros_ws/local_map_replay.py) | 保存接收顺序、按revision复核公开快照/查询及拒绝结果 | CLI修改前不接受M3配置 |
| [MapQueryClient.query](../application/ufm_application/query_client.py) | 保留五类状态，校验身份/概率/证据时间 | 修改前自定义字典transport绕过codec后缺少独立quality检查 |

研究模型不可用/质量暂缓、真实设备/标定/时钟及正式性能阻塞不属于本轮修复对象。
本轮实现范围限于上述装配和消费缺口，无公共接口扩展。

## 实现、影响与恢复

工厂增加显式m3_fixture的固定/滚动选择，研究与M3模块不进入latest启动路径。
runtime_config增加完整M3配置加载；ROS必须显式提供m3_fixture_config和clock_id，
禁止混用M2/M3配置和用私有参数覆盖候选配置。选型错误、缺配置或配置非法时启动失败，
错误占据报告拒绝且不更新原地图，均不回退latest/M2/placeholder。
回放CLI使用同一工厂和完整显式配置，保留输入顺序，比较快照、查询及拒绝结果。

应用层仅校验公开结果，不跨层导入mapping实现。confidence为None或有限[0,1]值，
uncertainty检查状态、文本元数据、available有限非空数值和unavailable空逻辑值；
保留旧None表示和其他合法kind。occupancy_variance沿通用单非负值约定；
occupancy_probability_interval检查dimensionless、双端点、有序[0,1]范围及名义概率包含。
逻辑结果可严格包含；wire结果允许round32(lower)≤float32(mean)≤round32(upper)，
精确nearest-even，不改字段或加任意epsilon。坏响应为unavailable并清空证据载荷，
不把坏quality补成有效零值，也不改变合法结果分类或历史质量。
元数据保留不等于来源真实性或统计覆盖率验收，应用不计算新的累计质量。

没有修改消息、SensorBundle或OccupancyObservation字段、M1/M2更新算法及M3累计算法。
没有模型/GPU/checkpoint、原始传感器、LiDAR、target、observed_mask或最新状态旁路。
恢复方式为停止候选、用新run显式启动latest或m2_fixture，不续接M3私有缓存。

## 实际ROS与独立预期

新增[m3_stage_run.py](../ros_ws/m3_stage_run.py)、
[m3_fixture.launch](../ros_ws/launch/m3_fixture.launch)及
[check_m3_stage_ros.py](../tests/check_m3_stage_ros.py)。复用既有进程监督/端口探测，
输出新run并保存配置和launch副本。测试工具是显式合成OccupancyObservation生产者，
不是research节点。检查器以独立分数端点作为数值预期，不从地图私有状态产生预期。

[实际manifest](../.runtime/runs/m3-stage-20261027T183857889507/manifest.json)、
[validation](../.runtime/runs/m3-stage-20261027T183857889507/validation.json)、
[收据](../.runtime/runs/m3-stage-20261027T183857889507/receipts.json)记录：
19观测、13快照、19查询，155项运行检查全部通过；13条fused、2条not_fused、4条rejected。

| 场景 | 实际结果 |
| --- | --- |
| 初次occupied/free及未知区域 | 0.75/[0.7,0.8]、0.25/[0.2,0.3]和未观测unknown分别保真，confidence均None |
| 二次累计及重复/同ID冲突 | 0.9/[49/58,0.9]；重复无更新，同ID更改拒绝 |
| unavailable、迟到和坏未来帧 | 不移动/不刷新；迟到拒绝；末尾体素单位m2错误整帧拒绝，合法前部不泄漏，后续较早合法帧仍可恢复 |
| 平移/偏航、TTL边界和空帧移动 | 同一世界cell索引变化、区间随cell迁移；恰TTL新鲜；空帧只改覆盖；旧覆盖时刻unavailable、超TTL stale保留原证据时间和范围 |
| 恢复及显式free反证 | 超TTL从先验重建；0.5/[7/19,12/19]仍为observed unknown，再次free为0.25/[7/55,36/85] |
| 远移/返回 | 新区域unknown；返回重新从先验构造，不复活旧范围 |
| known→missing→known及TTL恢复 | 缺少一次有效贡献范围后，后续known仍质量unavailable，来源保持missing_range；TTL后新贡献恢复[0.7,0.8] |
| 应用查询 | occupied/free/unknown/stale/unavailable五类均覆盖；独立应用CLI保留累计区间来源 |

[graph](../.runtime/runs/m3-stage-20261027T183857889507/graph.json)确认mapping只订阅
/uav/perception/occupancy和基础设施/clock；唯一测试clock生产者，图无LiDAR或训练话题。
[独立应用CLI](../.runtime/runs/m3-stage-20261027T183857889507/application-cli.json)通过。
监督器随后启动独立公开收据回放，完整快照/查询与拒绝结果一致，见
[回放报告](../.runtime/runs/local-map-replay-20261027T183900701257/report.json)。
回放比较公开浮点载荷使用既有1e-6容差；具名端点的独立ROS检查使用1e-12，未放宽原规则。

解释器入口为指定Radar-Diffusion/bin/python，实际进程可执行文件解析到同环境python3.8，
manifest的Python审计通过。隔离端口11651；
[cleanup](../.runtime/runs/m3-stage-20261027T183857889507/cleanup-audit.json)显示
各子进程exit=0、forced=[]、remaining_audited_python_pids=[]、端口释放。

## 测试与旧入口回归

新增[test_m3_selection.py](../tests/test_m3_selection.py)五项，扩展节点与应用各两项，
共新增9项；定向M3共51项、节点10项、应用6项通过，全仓570/570通过。
覆盖显式固定/滚动、默认无候选导入、缺/坏/隐式或混用配置无fallback，
公开回放拒绝保真、篡改quality来源被查出、坏quality原子拒绝后恢复；
自定义transport坏confidence/元数据/区间/方差拒绝，合法未知kind及None保真，
float32零宽区间与相邻不可接受值分开。

首轮新增选型测试将内部浮点0.7499999999999999直接与0.75作相等断言而失败；
依据既有logit/sigmoid数值合同改为近似比较，未修改算法、预期数学值或接受阈值。
其后定向与全仓通过；M3实际ROS首轮通过。

| 回归范围 | 证据与结果 |
| --- | --- |
| M2候选ROS/公开回放 | [manifest](../.runtime/runs/m2-stage-20261027T183953618468/manifest.json)，运行、回放和清理通过 |
| 旧固定M1/应用 | [manifest](../.runtime/runs/local-map-query-enabled-20261027T184005763108/manifest.json)，运行/清理通过；[公开回放](../.runtime/runs/local-map-replay-20261027T184202172108/report.json)一致 |
| 旧滚动M1 | [manifest](../.runtime/runs/local-map-query-rolling-20261027T183959003927/manifest.json)，运行/清理通过；[公开回放](../.runtime/runs/local-map-replay-20261027T184202170345/report.json)一致 |
| fake Radar/IR→SensorBundle→placeholder→Map | [manifest](../.runtime/runs/local-map-query-inference-20261027T184017943367/manifest.json)，旧入口运行、图/Python检查和清理通过 |

五组ROS均无强制终止和剩余受审计Python进程；各自端口释放。不操作他人已有进程。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/m3_stage_run.py --port 11651
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/m2_stage_run.py --port 11652
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/local_map_query_run.py --mode enabled --application-client --port 11653
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/local_map_query_run.py --mode rolling --port 11654
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/local_map_query_run.py --mode inference --port 11655
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

ROS因沙箱禁止本地套接字而通过已授权的沙箱外短测执行；没有安装依赖或访问外网。
git diff --check通过，相关文档相对链接核对通过；既有改动保留，未自动提交/推送。

## 文件清单、限制与下一阶段

本轮修改已有源码：mapping/ufm_mapping/factory.py、application/ufm_application/query_client.py、
ros_ws/runtime_config.py、ros_ws/local_map_replay.py、
ros_ws/src/uav_fusionmap_mapping/scripts/perf01a_map_node.py、
tests/test_map_query_node.py、tests/test_application_query_client.py。
新增源码：ros_ws/m3_stage_run.py、ros_ws/launch/m3_fixture.launch、
tests/check_m3_stage_ros.py、tests/test_m3_selection.py。
配套更新：PROJECT_STATUS.md、docs/DEVELOPMENT_PLAN.md、docs/STAGE_ADVANCE_PLAN_20261027.md、
docs/M3_SOFTWARE_TRIAL_PLAN_20261027.md、docs/RUNTIME_CONFIGURATION.md、docs/DATA_FORMAT.md、
docs/SENSOR_INTERFACE.md、docs/DECISION_LOG.md、docs/EXPERIMENT_LOG.md及本记录。

已有能力为离线合成区间累计；本轮实现显式ROS/回放装配和应用质量校验；
已验证合成ROS与公开服务/回放/旧入口兼容，不代表真实模型质量或校准区间覆盖率。
未执行研究权重加载、forward、训练、质量实验、真实设备/标定、机载RSS/功耗或正式PERF-01；
正式M1/M2/M3和完整Phase 2/3/4仍未关闭。运行产物在本地忽略目录，外部归档/恢复仍按ENV-03单列。

本轮关闭M3-SW-04及M3合成软件试制。下一项按阶段顺序为M4-DESIGN-01（计划，
mapping_engineer）：沿快照/查询生产消费链设计Scene Map/子地图生命周期、跨子地图坐标、
定位跳变处理、覆盖/新鲜度/质量、容量与恢复，以及独立合成软件工作包。
先交付具体方案；本轮未实现M4、不改公共字段、不推进DEM或重开暂缓的模型质量任务。
