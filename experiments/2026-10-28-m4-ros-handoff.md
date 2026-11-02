# M4-SW-04：显式ROS、公开回放与独立应用交接

编号：EXP-20261028-004；日期：2026-10-28；主责任：tester。
状态：已完成（固定合成注册下的软件交接）；依据：用户继续执行已确认的
[M4具体方案](../docs/M4_SOFTWARE_TRIAL_PLAN_20261027.md)，前置为
[SW-03时序/资源组合](2026-10-28-m4-time-resources.md)。

## 审计与范围

读取根/模块规则、PROJECT_STATUS、架构及数据/坐标/传感器契约，沿
factory→ROS节点→SceneMap→公开snapshot/query→应用CLI和公开占据回放核对真实调用。
分支feature/engineering-initialization，保留全部已有未提交修改；
核对.runtime/runs下新产物命中忽略规则，不提交或推送，不修改同级研究仓库或Conda环境。

已有能力：SW-01—03已提供注册checker、固定合成Scene候选、冻结独立预期及离线时序/资源证据；
已有MapSnapshot/MapQuery编码与应用客户端。此前factory/节点/回放尚未注册M4，不能用离线通过
代替实际ROS交接；原老化诊断还依赖Local Map专属stale_cells/TTL属性，Scene不提供这些属性。

本轮只修改共享装配/回放与测试，不修改Scene、M2/M3累计算法或公共消息。
不启动模型、checkpoint、GPU、训练、真实设备、PX4/JSBSim、DEM、科研对照或正式PERF-01。
恢复为停止M4，显式选择旧后端并建立新run/实例；不迁移私有目录或自动fallback。

## 已实现能力与代码证据

| 文件/符号 | 本轮变化 |
| --- | --- |
| [factory.create_map](../mapping/ufm_mapping/factory.py) | 显式m4_fixture且完整配置/rolling=true时惰性创建SceneMap，run/clock受注册合同校验；默认latest不导入M4 |
| [runtime_config.load_m4_config](../ros_ws/runtime_config.py) | 显式路径读取及m4_contract完整校验，不代填注册或使用隐式配置 |
| [perf01a_map_node.main](../ros_ws/src/uav_fusionmap_mapping/scripts/perf01a_map_node.py) | 私有M4选择/配置、混候选及参数覆盖拒绝，Scene几何记录；更新/查询同实例同锁，错误保留拒绝；诊断从公开快照/解析TTL记录 |
| [local_map_replay.main](../ros_ws/local_map_replay.py) | 显式M4配置/clock/rolling重建公开占据，逐值对账snapshot/query/outcome；缺配置、混配置、错注册或阈值覆盖失败 |
| [m4_fixture.launch](../ros_ws/launch/m4_fixture.launch) | 仅装配既有mapping节点；候选配置/run/clock必需，显式rolling和查询，老化诊断目录可选 |
| [m4_stage_run.main](../ros_ws/m4_stage_run.py) | 独立master/新run，保存完整配置并显式重绑定run/clock，K=1；ROS检查→Python审计→公开回放→退出/端口清理 |
| [check_m4_stage_ros.main](../tests/check_m4_stage_ros.py) | 公开消息真实序列化、独立指定坐标/区间/时间预期、五类查询、独立应用CLI及图审计 |
| [test_m4_selection.py](../tests/test_m4_selection.py) | 新增5项工厂/配置/回放CLI/篡改收据拒绝与默认不导入检查 |
| [test_map_query_node.py](../tests/test_map_query_node.py) | 新增2项M4私有选型、map服务及老化诊断、混配置/隐式配置拒绝，扩展缺配置循环 |
| [test_m4_fixture_contract.py](../tests/test_m4_fixture_contract.py) | 更新“未注册M4”的历史预期为“必须显式完整配置”，继续核对默认不导入 |

在线业务输入仍只有OccupancyObservation。SensorBundle、OccupancyObservation、MapSnapshot、
MapQuery字段不变；无LiDAR/target/observed_mask、状态/原始传感器或私有目录消费旁路。
未知/无观测、失效、过期仍分别保留unknown/unavailable/stale，不能替代为free。

## 实际ROS验证

实际执行：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/m4_stage_run.py --port 11661
```

唯一新run：[m4-stage-20261028T123353707205](../.runtime/runs/m4-stage-20261028T123353707205/manifest.json)。
本机ROS socket按授权使用隔离端口；没有关闭既有进程。首个完整M4 ROS run通过。
保存的完整配置包含fixture注册T_map_odom=[I, (32,0,0)]、有效期[0,1e9)ns及K=1。
ROS映射进程、master、监督器的实际解释器审计均为指定Conda Python（真实可执行文件python3.8）。

| 检查 | 实际结果 |
| --- | --- |
| 公开观测及快照 | 15观测，9 fused/2 not_fused/4 rejected，9快照；revision与原证据时间正确 |
| map坐标 | odom点[8.25,.25,.25]经显式注册对应map点[40.25,.25,.25]，Scene index=[80,32,8]；错误frame不可用，未转换的原odom点无观测 |
| 子地图/TTL | P→Q封存保留原时间；恰TTL新鲜、超1ns stale，不同cell年龄区分；P→Q→R淘汰P后unknown，返回free从0.25重建，无旧owner复活 |
| 拒绝/恢复 | 重复not_fused；同ID区间冲突、迟到、未来越界、末尾坏单位共4条拒绝；无效body变换不移动地图；后续较早合法帧可恢复 |
| 质量/结构时间 | free与occupied冲突后p=0.5仍observed且unknown；missing后known不借旧范围；空移动不刷新贡献，早于结构时间查询unavailable；TTL后新贡献恢复区间 |
| 应用 | 20次查询、五类状态及独立进程map CLI通过；不伪造confidence，历史区间/缺失来源保真；注册到期不可用 |
| 图隔离 | mapping仅订阅/clock和/uav/perception/occupancy，唯一clock生产者为checker，无LiDAR/训练话题 |
| 收据重放 | 同factory对9快照/20查询与15条融合/拒绝结果一致；错误不会改写收据或fallback |

合计[174项运行检查](../.runtime/runs/m4-stage-20261028T123353707205/validation.json)通过。
原始[receipts](../.runtime/runs/m4-stage-20261028T123353707205/receipts.json)、
[graph](../.runtime/runs/m4-stage-20261028T123353707205/graph.json)、
[独立CLI](../.runtime/runs/m4-stage-20261028T123353707205/application-cli.json)、
[老化诊断](../.runtime/runs/m4-stage-20261028T123353707205/map-aging.json)与
[回放报告](../.runtime/runs/local-map-replay-20261028T123356928948/report.json)均保留。
数值沿既有wire概率float32比较（绝对误差<1e-6）、区间float64比较（<1e-12）；
身份、时间、revision、索引、来源、状态精确检查，不修补质量值。

## 回归与清理

定向执行test_m4_selection共5/5、test_map_query_node共12/12通过。
全仓实际命令：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

结果：629/629通过（21.907s）；相对622基线新增7项，不以文档更新改变测试结果。
以下实际ROS回归通过（同一环境入口/解释器，各自独立master），没有模型推理：

| 命令尾部/端口 | 原始报告 |
| --- | --- |
| ros_ws/m3_stage_run.py --port 11662 | [M3及公开回放](../.runtime/runs/m3-stage-20261028T123559332152/manifest.json) |
| ros_ws/m2_stage_run.py --port 11663 | [M2及公开回放](../.runtime/runs/m2-stage-20261028T123606216468/manifest.json) |
| ros_ws/local_map_query_run.py --mode enabled --application-client --port 11664 | [旧固定placeholder/应用](../.runtime/runs/local-map-query-enabled-20261028T123625739760/manifest.json) |
| ros_ws/local_map_query_run.py --mode rolling --port 11665 | [旧滚动placeholder](../.runtime/runs/local-map-query-rolling-20261028T123633851074/manifest.json) |
| ros_ws/local_map_query_run.py --mode inference --port 11666 | [独立inference placeholder](../.runtime/runs/local-map-query-inference-20261028T123641642394/manifest.json) |

共享回放CLI还对本轮旧固定/滚动公开收据执行latest回归（显式free=0.3/occupied=0.7，
滚动另加--rolling），两者通过：
[固定](../.runtime/runs/local-map-replay-20261028T123729056387/report.json)、
[滚动](../.runtime/runs/local-map-replay-20261028T123729532701/report.json)。
六组ROS清理均通过，无强杀、无审计进程残留，11661—11666端口释放；
[M4清理](../.runtime/runs/m4-stage-20261028T123353707205/cleanup-audit.json)，各旧run同名文件保留。

配套文档更新：PROJECT_STATUS、M4计划、DEVELOPMENT_PLAN、STAGE_ADVANCE_PLAN、
RUNTIME_CONFIGURATION、SYSTEM_ARCHITECTURE、DATA_FORMAT、COORDINATE_SYSTEM、
SENSOR_INTERFACE、DECISION_LOG、EXPERIMENT_LOG及本记录；历史实验/原始产物保留。

## 未验证能力与下一步

本轮关闭的是M4固定合成注册下的有界Scene软件工作包及ROS交接。
真实Radar/IR、真实标定/设备时钟、真实map注册、同run未声明定位reset识别、动态注册修正、
真实模型质量/forward、RSS/目标机资源/功耗、正式PERF-01和完整M1—M4/Phase 4均未关闭。
测试占据与区间有fixture来源，不能称为真实感知或已校准不确定性。

按地图阶段顺序下一项M5-DESIGN-01（计划；mapping_engineer），只交付TerrainPrior的
水平/垂直基准、map注册、no-data/过期、时间/质量、生产者/消费者、兼容恢复及分步验收方案。
本轮未实现DEM；若设计需要公共字段变化，必须先给出具体迁移方案并等待确认。
暂缓的研究质量任务及现有fail-closed状态保持，不重复已关闭的交接充作阶段推进。
