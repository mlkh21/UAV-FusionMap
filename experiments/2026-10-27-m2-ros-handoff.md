# EXP-20261027-010：M2-SW-04独立ROS、回放与应用交接

日期：2026-10-27；主责任：tester；状态：已完成（合成软件交接范围）。
依据：[已确认M2方案](../docs/M2_SOFTWARE_TRIAL_PLAN_20261027.md)、SW-03交付及用户“继续”。
分支`feature/engineering-initialization`；先检查Git状态及忽略规则，保留全部既有改动。
所有Python经`bash ros_ws/sim01_env.sh`使用指定Radar-Diffusion解释器；无提交/推送。

## 只读审计与实现

此前真实调用链为`perf01a_map_node.main → SparseLocalMap`，
`local_map_replay.main → replay_observations → SparseLocalMap`；
M2固定/滚动候选只有离线显式入口，应用经既有MapQueryClient/ROS MapQuery查询。
本轮修改装配和回放选择，不修改M1/M2的累计、滚动或查询算法。

新增模块内[create_map](../mapping/ufm_mapping/factory.py)供ROS与回放共用：
默认latest沿用M1参数；显式m2_fixture才惰性导入固定/滚动候选，必须提供具名合成
配置、run_id、clock_id。候选参数只来自配置，不接受分散覆盖；缺配置、身份、
未知模式或配置/模式冲突均明确失败，不自动fallback。

[既有地图节点](../ros_ws/src/uav_fusionmap_mapping/scripts/perf01a_map_node.py)新增私有
map_backend（默认latest）、m2_fixture_config及候选clock_id要求；rolling_enabled复用
已有私有开关，选择固定/滚动候选。发布解析后的后端和通用配置供复核。
更新与查询仍共用一个地图实例及RLock。旧launch未改，不会自动读取M2配置。
`enable_query`默认关闭、已有诊断开关及旧就绪握手均保持。

[回放业务入口](../mapping/ufm_mapping/replay.py)默认仍为latest，增加显式候选选项；
[独立CLI](../ros_ws/local_map_replay.py)保存选定后端、参数与时钟，按原接收顺序重建
快照/查询，另外核对保存的接受/拒绝结果。既有revision选择规则保留，不模拟原线程交错。
应用没有修改，只通过公开查询消费状态、概率、质量和证据时刻。

新增[显式launch](../ros_ws/launch/m2_fixture.launch)、
[监督器](../ros_ws/m2_stage_run.py)及[ROS检查器](../tests/check_m2_stage_ros.py)。
测试器只发布已标fixture且声明逆观测域的OccupancyObservation与独立公共clock；
没有新造模型或传感器节点，不接研究环境、LiDAR、target或训练mask。
沿用已有消息/服务，无公共字段、版本或五层架构变化。

## 运行过程与实际证据

首轮`m2-stage-20261027T154602672869`在受限沙箱创建本机socket时得到
`PermissionError:[Errno 1] Operation not permitted`，尚未启动子进程；
清理端口探针也因同一限制不能执行，原manifest/cleanup失败记录保留。
随后按用户既有授权通过工具权限审查运行独立本机ROS图，不改系统环境或已有服务。

首个可通信run `m2-stage-20261027T154626338310`通过业务查询与回放，但测试公共clock
直接跟随坏/迟到观测时刻，存在回退，不作为最终单调clock证据。随后修正测试器，
将clock与被拒绝的观测时间分离，并保存单调clock及逐条事件；原run结果没有覆盖。

最终run为[m2-stage-20261027T155027526446](../.runtime/runs/m2-stage-20261027T155027526446/manifest.json)，
隔离Master端口11641，实际结果：

- 15条观测，9次覆盖/累计快照、14次公开查询，94项断言通过；
  [validation.json](../.runtime/runs/m2-stage-20261027T155027526446/validation.json)。
- 两次0.75累计0.9；重复投递不再累计；合法失效不刷新证据；
  同ID改内容、旧时刻、末尾越界体素、错误观测域共4条明确拒绝。
  坏帧未来时间不污染水位，后续40ms合法帧恢复；原子拒绝后没有部分移动/更新。
- 偏航/平移保留同一世界cell；140ms恰等于最后40ms证据的TTL边界，仍新鲜；
  150ms空帧移动只增加revision，证据仍40ms，查询stale；早于新覆盖时间的查询
  unavailable。160ms新贡献从先验得0.75，后续显式free抵消为observed unknown再变free。
- 远移淘汰、返回重新累计；occupied/free/unknown/stale/unavailable五类均由现有
  应用客户端保真消费；独立应用CLI另一次查询得到occupied/0.75且退出0。
- [receipts.json](../.runtime/runs/m2-stage-20261027T155027526446/receipts.json)保存实际
  ROS编解码后的输入、快照、查询、结果分类、事件和单调clock序列。
  该组坏输入测试不会重置公共clock或改写观测timestamp。
- [graph.json](../.runtime/runs/m2-stage-20261027T155027526446/graph.json)：mapping只订阅
  `/uav/perception/occupancy`与基础设施`/clock`；唯一clock发布者为检查器，
  图中无训练/LiDAR话题或订阅。

监督器随后调用独立回放CLI，使用保存配置和明确run/clock、rolling及m2_fixture选择。
[回放报告](../.runtime/runs/local-map-replay-20261027T155030303481/report.json)通过，
15输入、9快照、14查询及4条拒绝与ROS收据一致；比较所有公开字段，
浮点承载容差沿用1e-6，身份/时间保持严格相等。

[清理报告](../.runtime/runs/m2-stage-20261027T155027526446/cleanup-audit.json)通过：
roscore、mapping、observer、replay全部退出0，无强制信号、无残留审计Python进程，
端口11641释放。manifest保存实际命令、进程解释器审计和输出路径。

## 回归与复现

本轮新增9项轻量测试（6项选择/回放与3项节点测试）：
[test_m2_selection.py](../tests/test_m2_selection.py)、
[test_map_query_node.py](../tests/test_map_query_node.py)。
包括新进程验证默认latest不导入候选、错误配置fail-closed、真实节点包装累计、
旧placeholder拒绝、M2配置未选候选不能静默启动latest，以及保存预期0.75改为0.8时
独立CLI必须失败。该负例只修改临时收据，原成功产物不变。

M2共43项定向、全仓515/515项轻量回归通过；`git diff --check`通过。
测试日志归档于最终M2 run。受共同装配改动影响的旧实际ROS入口均回归：

| 入口 | 结果与证据 |
| --- | --- |
| 固定query + 应用CLI | [local-map-query-enabled-20261027T154726034172](../.runtime/runs/local-map-query-enabled-20261027T154726034172/manifest.json)，运行/清理通过；其原latest收据独立[回放](../.runtime/runs/local-map-replay-20261027T155413858884/report.json)通过 |
| 原滚动fixture | [local-map-query-rolling-20261027T154729266950](../.runtime/runs/local-map-query-rolling-20261027T154729266950/manifest.json)，运行/清理通过；其原latest滚动收据独立[回放](../.runtime/runs/local-map-replay-20261027T155413851809/report.json)通过 |
| fake Radar/IR → SensorBundle → placeholder → Map | [local-map-query-inference-20261027T154743897525](../.runtime/runs/local-map-query-inference-20261027T154743897525/manifest.json)，无诊断观察订阅者的旧入口运行/图检查/解释器/清理通过 |

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/m2_stage_run.py --port 11641
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/local_map_query_run.py --mode enabled --application-client --port 11642
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/local_map_query_run.py --mode rolling --port 11643
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/local_map_query_run.py --mode inference --port 11644
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

## 修改清单、恢复与阶段结论

代码/装配：新增mapping/ufm_mapping/factory.py、ros_ws/m2_stage_run.py、
ros_ws/launch/m2_fixture.launch、tests/check_m2_stage_ros.py及tests/test_m2_selection.py；
修改mapping/ufm_mapping/replay.py、ros_ws/runtime_config.py、ros_ws/local_map_replay.py、
ros_ws/src/uav_fusionmap_mapping/scripts/perf01a_map_node.py、tests/test_map_query_node.py；
configs/m2_fixture.yaml只澄清读取范围注释，数值不变。
文档同步PROJECT_STATUS及M2方案、开发/跨阶段计划、运行配置、架构、数据/接口说明、
M1正式矩阵补充、决策和实验索引。全仓其他既有未提交改动继续保留，不归入本轮。

恢复为停止独立候选图，用新run启动旧launch/latest；不能把M2缓存续接到M1。
旧默认入口未改为M2，应用和上游不需迁移消息字段。

已完成M2-SW-01—04的合成软件范围，包括真实ROS通信；未完成的是正式M1/M2、
真实模型概率校准、多帧相关性/地图质量、真实标定、研究checkpoint/forward、
目标平台持续资源/功耗及正式PERF-01。本轮不安装依赖、不启模型/GPU/训练，
不修改同级研究仓库，不开发M3、Scene Map、DEM或控制。
下一项计划为M3-DESIGN-01：沿现有Uncertainty合同审计来源、单位、不可用传播，
先给可测试的软件方案，再按具体范围推进实现；不退回已暂缓的研究质量任务。
