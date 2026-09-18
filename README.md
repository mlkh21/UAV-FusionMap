# UAV-FusionMap

面向高速固定翼无人机的多传感器感知与地图系统。

项目周期：2026年9月—2027年3月。工程初始化、独立仿真构建、静止遥测及SIM-01A/B状态/时钟与记录回放验证已完成。

## 从这里开始

每次开发按顺序阅读：

1. [AGENTS.md](AGENTS.md)：允许修改什么、如何计划和验证。
2. [PROJECT_STATUS.md](PROJECT_STATUS.md)：当前状态、风险和下一项任务。
3. [系统架构](docs/SYSTEM_ARCHITECTURE.md)：模块分工、依赖方向和运行模式。
4. 涉及目录的AGENTS及[数据格式](docs/DATA_FORMAT.md)、[传感器接口](docs/SENSOR_INTERFACE.md)。

## 系统主链

仿真平台 → 传感器/状态适配 → Radar–IR感知 → 地图 → 应用接口。

目标是形成可复现的感知与地图数据闭环。规划数据接口属于系统范围；自主控制算法、
实机飞行与高真实性传感器物理仿真需要另行定义验证范围和资源。

运行时SensorBundle只包含Radar、IR、可选IMU、权威状态和标定上下文。LiDAR只在
`training_data_generation`配置中与fake Radar/IR同步生成训练target/observed mask，
不进入在线推理、定位或地图；`inference`配置不依赖LiDAR。

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
短窗倍速结果不替代SIM-01D至少40分钟持续性、PERF-01或
35—70m/s感知—地图性能验收。训练监督LiDAR、raw传感器适配和Odometry兼容镜像目前只有
ADR-012设计与阶段任务，尚无ROS消息、节点或启动图实现。
