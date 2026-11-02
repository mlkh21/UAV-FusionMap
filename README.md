# UAV-FusionMap

面向高速固定翼无人机的多传感器感知与地图系统。

项目周期：2026年9月—2027年3月。工程初始化、独立仿真构建、静止遥测及SIM-01A/B状态/时钟与记录回放验证已完成。

## 从这里开始

查看场景和传感器仿真：使用[Gazebo场景 + 原生RViz Radar/IR入口](docs/SENSOR_SCENE_VISUALIZATION.md)，
已于2026-10-28验证并保存[报告图片与图注](experiments/report_assets/sensor-scene-20261028/README.md)。
当前是固定飞机的功能级场景，不是PX4联动飞行、物理传感器或真实模型验收。
此前[地图工作台与回放](docs/ROS_VISUALIZATION.md)保留，不能代替场景传感器可视化。

2026-10-29统一交付：[软件启动/配置/查询/回放清单](docs/SOFTWARE_DELIVERY_20261029.md)、
[阶段进展报告正文](docs/REPORT_20261029.md)。报告于2026-10-30按9月18日报告的表达方式重写，
[最新16页Word与PDF](experiments/report_assets/progress-map-clarified-20261030/README.md)已按四个工作方向整体整编并修正地图对应关系表述，
[此前17页版本](experiments/report_assets/progress-update-20261030/README.md)与
[此前15页版本](experiments/report_assets/progress-20261030/README.md)保留。
[真实高程工具及改进场景入口](docs/REPORT_IMPROVEMENTS_20261030.md)已完成独立真实DSM读取/查询/RViz和稀疏Radar联调。
P5冻结合成软件矩阵37例通过，
真实设备、模型质量、DEM融合和正式阶段验收仍未完成。
后续[SW-02同FDM/受控场景引擎门](docs/SIM_MOTION_SW02_ENGINE_20261029.md)已通过250步/10对真实采样；
该独立短窗无自动解锁/控制，默认静态窗口仍为固定场景，修订报告另配运动场景图片。
随后[SW-03端到端运动交接](docs/SIM_MOTION_SW03_DELIVERY_20261029.md)已通过10组Bundle/占据/快照、
14条公开查询、独立回放及正常/故障恢复；[新运动五图与中文图注](experiments/report_assets/sim-motion-20261029/README.md)已交付。
随后已交付[有界多场景运动具体设计](docs/SIM_MOTION_SW04_MULTISCENE_DESIGN_20261029.md)：
9核心/3兼容用例；[SW-04A独立清单/预期与线格式](docs/SIM_MOTION_SW04A_CONTRACT_20261029.md)已完成，
已完成独立输入/线格式范围，旧profile与公共字段保持。
随后[SW-04B真实定向机制](docs/SIM_MOTION_SW04B_ENGINE_20261029.md)已通过空碰撞域、暂停切换/空回波/返回、
中途Radar ACK故障及旧默认入口回归，运动77项/全仓896项通过。
随后[SW-04C同源码最终矩阵](docs/SIM_MOTION_SW04C_DELIVERY_20261029.md)完成9核心/3兼容、
84组业务/121查询、公开回放与[多场景原生素材](experiments/report_assets/sim-motion-multiscene-20261029/README.md)。
运动84项/全仓903项通过，四次失败与恢复保留；仍为最长1秒、无控制的软件交接，非正式阶段或受控飞行验收。
下一项只做受控飞行联动的具体设计，不自动解锁、起飞或延长当前窗口。
随后[SIM-FLIGHT具体方案](docs/SIM_FLIGHT_DESIGN_20261029.md)已完成19项源码事实及15项独立核验，
84项既有定向通过；本轮仅文档，控制/新v2与较长窗口尚未实现。下一项先做离线IC/执行器收据合同。
2026-10-30 [SIM-FLIGHT-SW-01私有离线合同](docs/SIM_FLIGHT_SW01_CONTRACT_20261030.md)已完成：
新增25项、旧运动84项及全仓928项通过，原公共定义和运行入口保持；没有启动新仿真或发送命令。
直接下一项SW-02为≤1秒/250步的实际HIL只读诊断，执行器时序绑定仍未验证，控制门保持关闭。
随后[SW-02隔离诊断](docs/SIM_FLIGHT_SW02_DIAGNOSTICS_20261030.md)完成正常250步/1s与断连接停止，
飞行32项/旧运动84项/全仓935项通过。实际执行器0包，未就绪事实明确保留；
下一项先只读归因及最小补证方案，不直接开启长窗/v2运行或控制实验。
随后[未就绪归因/最小补证设计](docs/SIM_FLIGHT_DIAG_DESIGN_20261030.md)完成30项源码核验和旧wire离线检查，
未启动新仿真；下一项SW-02B在原1s范围内增加本次PX4的有界uORB快照，控制门保持关闭。
随后[SW-02B软件/实际失败交付](docs/SIM_FLIGHT_SW02B_PROBE_20261030.md)完成私有合同与显式有界查询：
step125读到三组积分IMU，第二条estimator_status空实例严格拒绝，21查询尚未通过。
飞行49/运动84/全仓952项与旧诊断/线格式兼容通过；下一项先针对空实例设计补证，不扩窗或控制。
随后[空实例三态补证设计](docs/SIM_FLIGHT_DIAG_DESIGN03_20261030.md)已交付：独立诊断事件/显式模式，
原strict与失败保留，18组未来验收预期及原21次/1秒限额明确。只读16项核验/49项既有定向通过；
下一项SW-02C实施，尚未实现新分类器/运行；采集完整、载荷可用与控制门分别验收。
随后[SW-02C三态诊断软件/实际未通过记录](docs/SIM_FLIGHT_SW02C_DIAGNOSTICS_20261030.md)已交付：
11次实际查询/10合法事件，250步estimator_status含nan按原规则停止，21次采集未完成。
飞行69/运动84/全仓972项和旧入口/消息兼容通过；下一项先核对原生非有限质量字段的语义与隔离设计，控制门保持关闭。
随后[原生质量隔离具体设计](docs/SIM_FLIGHT_DIAG_DESIGN04_20261030.md)已交付：只在两个比值准确nan且同载荷源位合格时显式标不可用。
20项源核验、16组独立掩码算例/69项既有定向通过；451源码未改，无新运行。
下一项SW-02D实施独立私有v2诊断/显式模式，旧两个合同/失败保持，仍不开放控制或延长窗口。
随后[SW-02D质量隔离与实际21次采集](docs/SIM_FLIGHT_SW02D_QUALITY_20261030.md)已完成：
三参数完整读回，六实例12处比值按同块源条件显式标不可用；采集完整但正文/载荷不完整。
六flags已读样本tilt/yaw尚未对齐、selected姿态缺失、执行器仍0包；控制门关闭，旧B/C失败保留。
飞行92/运动84/全仓995项及旧入口/真实消息兼容通过。
下一项SIM-FLIGHT-INIT-DESIGN-01仅设计无控制初始化准备与SW-03衔接，不重复完整查询或直接扩窗/发命令。
随后[初始化准备具体设计](docs/SIM_FLIGHT_INIT_DESIGN_20261030.md)已完成：24份源文本/32项核验、旧wire重读及
92项既有飞行定向通过，明确先做INIT-SW-01离线合同，再做独立无控制准备；本轮没有新仿真或命令。
拟议7检查点/84查询及最长10s/2500步仅为新方案，未实施或放宽旧1s入口；公共Scene v2与控制仍另验。
随后[INIT-SW-01私有离线合同](docs/SIM_FLIGHT_INIT_SW01_CONTRACT_20261030.md)已完成：两组合成2500步/84查询、
35项新增、飞行127/运动84/全仓1030项与旧真实消息兼容通过；原458份源码保持。
下一项INIT-SW-02才实现独立无控制准备宿主/运行器；本轮没有新仿真，合成就绪不代表PX4收敛或控制准入。
随后[INIT-SW-02宿主/实际失败交付](docs/SIM_FLIGHT_INIT_SW02_PREPARATION_20261030.md)已取得500步/2s与78实际全零执行器/属性读回，
第30次selector数组含nan严格停止，完整84采集/准备未通过。断连接/期限停止及飞行134/运动84/全仓1037项兼容通过；
随后[selector具体设计](docs/SIM_FLIGHT_INIT_SELECTOR_DESIGN_20261030.md)已区分9实例/4设备槽位，
交付独立记录/98查询与前后设备表关联方案；24项源事实/历史原文/134项既有测试通过，476源码保持。
下一项仅INIT-SELECTOR-SW-01离线合同/先行预期；没有新查询/准备运行，原失败/1s入口和控制门保持。
随后[INIT-SELECTOR-SW-01](docs/SIM_FLIGHT_INIT_SELECTOR_SW01_CONTRACT_20261030.md)已完成独立离线合同/98计划，
两组合成2500步/98事件文件、101次JSON往返及新增28/飞行162/全仓1065项通过；旧476源码保持。
下一项SW-02才实际98项装配；未启准备期或开放控制，历史失败不回填。
随后[selector SW-02](docs/SIM_FLIGHT_INIT_SELECTOR_SW02_PREPARATION_20261030.md)实际59项查询/1007次Run/582零包，
500/1000局部就绪；1008条原生HIL少1us被Run前拒绝，完整准备未通过且未重跑。
新11/全仓1076及故障/旧链兼容通过；下一项只修隔离发送端整数时间生产，不扩窗或开放控制。
随后[INIT-TIME-SW-01](docs/SIM_FLIGHT_INIT_TIME_SW01_DELIVERY_20261030.md)已通过单profile完整10s无控制准备：
2500 Run/98合法查询、双末检查点、2078真实零执行器和2509时间源收据通过；旧失败保留，原488源码不改。
新7/全仓1083及故障/旧链兼容通过；下一项公共v2离线合同，不代表严格绑定、长窗采样或受控飞行通过。

每次开发按顺序阅读：

1. [AGENTS.md](AGENTS.md)：允许修改什么、如何计划和验证。
2. [PROJECT_STATUS.md](PROJECT_STATUS.md)：当前状态、风险和下一项任务。
3. [系统架构](docs/SYSTEM_ARCHITECTURE.md)：模块分工、依赖方向和运行模式。
4. 涉及目录的AGENTS及[数据格式](docs/DATA_FORMAT.md)、[传感器接口](docs/SENSOR_INTERFACE.md)。

## 系统主链

仿真平台 → 传感器/状态适配 → Radar–IR感知 → 地图 → 应用接口。

目标是形成可复现的感知与地图数据闭环。规划数据接口属于系统范围；自主控制算法、
实机飞行与高真实性传感器物理仿真需要另行定义验证范围和资源。

运行时SensorBundle只包含Radar、IR、权威状态和标定上下文；可选IMU为独立旁路。LiDAR只在
`training_data_generation`配置中与fake Radar/IR同步生成训练target/observed mask，
不进入在线推理、定位或地图；`inference`配置不依赖LiDAR。

独立软件fixture可通过以下入口运行，包含独立Master、地图查询验证及进程清理，
不需要实验观察订阅者，不发布性能诊断话题：

```bash
bash ros_ws/sim01_env.sh python ros_ws/local_map_query_run.py --mode inference
```

这只验证无模型软件闭环。共享配置、旧实验入口及限制见
[运行配置说明](docs/RUNTIME_CONFIGURATION.md)，当前能力以[项目状态](PROJECT_STATUS.md)为准。

## 目录职责

| 目录 | 职责 |
| --- | --- |
| simulation | PX4、JSBSim、场景、飞行状态和仿真时间 |
| sensors | Radar、IR、IMU、驱动适配、标定、同步、状态权威适配及训练监督生成 |
| perception | 占位感知、统一输入输出、算法后端适配 |
| mapping | Local Map、概率更新、不确定性、Scene Map、后期DEM |
| application | 地图查询、规划数据接口、可视化适配 |
| ros_ws | Noetic消息、simulation/sensors薄节点、启动和记录回放 |
| algorithms | 外部研究组件的来源、版本和接入条件 |
| configs | 配置职责、参数单位、标定与环境版本记录 |
| tests | 契约、跨模块集成和系统验收 |
| experiments | 实验配置、结果、复现步骤和产物索引 |
| docs | 系统设计、开发计划、决策和实验记录 |

各目录AGENTS定义局部边界。目录存在和文件存在不表示相应功能已实现。

## 已有研究基础

4D-Radar-Diffusion位于同级独立仓库：
`/home/zxj/catkin_ws/src/4D-Radar-Diffusion/`。
相对本README所在目录为`../4D-Radar-Diffusion/`。
已有实现、入口阻断和适配要求见[组件登记](algorithms/README.md)。
系统通过perception接口接入研究算法，并支持不加载模型的占位运行。

## 工程文档

- [数据格式](docs/DATA_FORMAT.md)、[传感器接口](docs/SENSOR_INTERFACE.md)、[坐标系统](docs/COORDINATE_SYSTEM.md)
- [开发计划](docs/DEVELOPMENT_PLAN.md)、[决策记录](docs/DECISION_LOG.md)、[实验记录](docs/EXPERIMENT_LOG.md)
- [本机环境清单](configs/ENVIRONMENT_INVENTORY.md)：双ROS选择、PX4/桥接资产、依赖缺项和GPU核查边界
- [仿真验证方案](docs/SIMULATION_VALIDATION_PLAN.md)：候选版本、依赖、状态/时钟、独立构建与验收步骤
- [实际构建说明](simulation/BUILD_SIM00A.md)：SIM-00A版本、项目前缀、构建命令、结果与限制
- [版本与产物管理](docs/VERSION_AND_ARTIFACT_POLICY.md)：忽略、提交范围、保存责任和恢复要求

ENV-01环境核查和ENV-02方案已完成。交互终端仍按现有菜单选择Foxy(1)或Noetic(2)。
首次优先验证Noetic + PX4 v1.13.3 + JSBSim 1.1.13 + MAVROS 1.20.1；正式运行组合尚未
验收。SIM-00A已于2026-09-12完成依赖解包和独立构建；日常ROS/Conda环境保持原样。
SIM00B-INIT-01已按确认应用，SIM-00B已通过120.056秒未解锁静止遥测，
可按[运行说明](simulation/RUN_SIM00B.md)复现；这不是完整系统启动或高速飞行验收。
SIM-01A已通过44项单元/契约、11项ROS fixture及30.196秒有效静止状态联调。
后续Python默认Conda `Radar-Diffusion`，入口为`bash ros_ws/sim01_env.sh ...`，
构建、验证及实际命令见[RUN_SIM01A](simulation/RUN_SIM01A.md)。
SIM-01B已完成300.008001秒LIVE、B1逐字节回放和B2全新sensors复算，
73项单元/契约、11项ROS fixture及三个会话关闭/清理通过，见[RUN_SIM01B](simulation/RUN_SIM01B.md)。
SIM-01C的F0—F7异常矩阵已通过；SIM-SPEED-01两行bridge修复及0.5/1/2倍各三次
预注册技术矩阵也已通过。但工具开发期间一份历史RED派生结果被同语义重写，
违反已确认的历史run保护门禁；用户已于2026-09-17明确接受偏差，要求保留记录、
不伪造原时间且不尝试恢复，SIM-SPEED-01与SIM-01C据此正式关闭。
SIM-01D至少40分钟持续性已于2026-10-05独立通过；短窗倍速不替代该验收或
PERF-01、35—70m/s感知—地图实时验收。训练监督LiDAR独立图、受限raw适配、
Odometry镜像及基础滚动地图已有软件fixture证据，真实设备与模型质量仍需独立验收。
