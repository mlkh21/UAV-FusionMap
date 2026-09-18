# UAV-FusionMap 项目状态

更新日期：2026-09-18；维护角色：Technical Lead。
当前阶段：SIM-00A/B、SIM-01A/B/C及SIM-SPEED-01已完成；SIM-01D持续性、PERF-01
与完整Phase 1仍未完成。
计划交付：2027年3月；阶段安排见[DEVELOPMENT_PLAN](docs/DEVELOPMENT_PLAN.md)。

## 当前完成

- 已确认UAV-FusionMap为系统主仓，4D-Radar-Diffusion为同级独立研究仓库。
- 已静态追踪研究预处理、融合、推理与地图关键路径，并登记入口阻断和未验证能力。
- 已建立根和11个子目录AGENTS，保留原规范与目录，增加application/tests及ros_ws/src占位。
- 已写入七份设计文档、README入口、组件登记、计划、决策和实验记录。
- 已完成INIT-01至INIT-05：24个交付文件覆盖、12份AGENTS七项规则、23份Markdown格式
  与90处本地链接检查通过；研究仓库前后Git状态一致。详细边界见实验记录。
- 已在feature/engineering-initialization功能分支工作；仓库尚无首次提交。
- 已完成ENV-01：确认双ROS选择机制、现有PX4与桥接资产，登记JSBSim/MAVROS缺项和
  GPU驱动/库不一致；结果见[环境清单](configs/ENVIRONMENT_INVENTORY.md)及
  [EXP-20260911-002](experiments/2026-09-11-environment-inventory.md)。
- 已完成ENV-02：形成[候选版本与最小验证方案](docs/SIMULATION_VALIDATION_PLAN.md)，
  ADR-006决定优先评估Noetic/PX4 v1.13.3/JSBSim 1.1.13/MAVROS 1.20.1；核心MAVROS
  APT模拟解析为新增7包、升级0、移除0。证据见[EXP-20260911-003](experiments/2026-09-11-simulation-plan-review.md)。

- 已完成SIM-00A：JSBSim开发包、7个MAVROS相关包及geoid取得并在项目目录解包，
  独立PX4与JSBSim桥接构建通过；依赖解析、包发现、geoid读取及命令环境隔离通过。
  见[构建说明](simulation/BUILD_SIM00A.md)和[EXP-20260912-001](experiments/2026-09-12-sim00a-build.md)。
- ENV-03已落实[精确忽略、提交范围与产物保存规则](docs/VERSION_AND_ARTIFACT_POLICY.md)，
  .runtime有catkin隔离标记；首次提交、第二份资产副本及恢复验收尚未完成。
- 已完成SIM-00B前置核查：确认桥接初始化缺陷，原构造探针失败、审查副本通过，
  已准备2文件5处声明的补丁；历史提案见[EXP-20260912-002](experiments/2026-09-12-sim00b-preflight.md)。
- 用户确认后已应用SIM00B-INIT-01，仅修改项目内桥接副本；新构建与消息回归通过，
  旧二进制保留。SIM-00B实测120.056秒静止遥测通过：IMU 6051条、50Hz，心跳121条，
  ODOMETRY 2407条；未解锁，本次进程和端口清理通过。
  见[EXP-20260912-003](experiments/2026-09-12-sim00b-init-and-smoke.md)及[运行说明](simulation/RUN_SIM00B.md)。

上述SIM-00交付证明文档、独立构建及静止遥测通过；SIM-01A状态/时钟证据见下项。
地图、算法质量和高速飞行仍未验收。

- 09-14已调用system_architect、simulation_engineer、sensor_engineer完成只读分析与
  二次复核，形成[SIM-01A实施提案](docs/SIM01A_IMPLEMENTATION_PLAN.md)，现已获用户确认。
  新发现及边界见[EXP-20260914-001](experiments/2026-09-14-sim01a-agent-review.md)；该记录保留实施前状态。

- 用户09-14确认后，三个子agents与Technical Lead完成SIM-01A：四个ROS消息、源筛选/
  时钟状态机、NED/FRD坐标适配、有界接收门控及两层薄节点；默认Python为Radar-Diffusion。
- 独立catkin与44项单元/契约通过；固定历史重建2103对状态、6051 clock，无FAULT。
  11项实际ROS fixture通过；未解锁静止联调605对状态、2302 clock、30.196秒valid跨度。
  抽查8个Python本次进程及后代均来自Conda；已知端口和进程清理通过。
  见[EXP-20260914-002](experiments/2026-09-14-sim01a-implementation.md)及
  [RUN_SIM01A](simulation/RUN_SIM01A.md)，仍非完整Phase 1或飞行验收。

- SIM-01B已完成：300.008001秒连续valid LIVE记录、B1成品逐字节回放、B2全新sensors复算
  分别通过。15,794 clock和源/适配各6,003条逐话题身份、完整质量与落盘重读一致。
- 73项单元/契约、11项实际ROS fixture及增量catkin通过；三个成功会话均已正常退出，
  清理无强制信号或审计PID残留。B1/B2额外clock计数均为0；未解锁或发送控制命令。
- B实施由对应子agents与Technical Lead完成；原生clock队列复用、EOF交接及退出码
  问题已在项目入口修复，三次失败B1原始证据保留。见[EXP-20260915-001](experiments/2026-09-15-sim01b-implementation.md)
  与[RUN_SIM01B](simulation/RUN_SIM01B.md)。本次完成不代表整个Phase 1或高速飞行通过。

- 用户确认后，多个对应子agents与Technical Lead完成SIM-01C第一批实施。F0—F7已在
  独立run中通过实际故障注入、唯一终止原因、terminal后零valid、监督清理及新run恢复
  验收；故障帧使用真实MAVLink编码并通过source和sensors链路，F0与F6按各自无上游输入/
  sensors本地回退的边界验收。证据见[实施记录](experiments/2026-09-16-sim01c-implementation.md)
  与[运行说明](simulation/RUN_SIM01C.md)。
- 修复前bridge倍速实测未通过：2倍三次实际为1.6982、1.6945、1.6896，均低于1.7下限；
  0.5倍因float getter截断为0而自由运行，一次20源秒窗口测得71.4543倍，随后发生
  `estimator_reset` terminal。现状RED及失败运行均保留；未修改bridge、PX4、公共消息
  或业务状态机。该历史结果触发SIM-SPEED-01，不能被修复后结果覆盖。
- SIM-SPEED-01已按[具体实施方案](docs/SIM_SPEED_01_IMPLEMENTATION_PLAN.md)实施：仅将
  `getRealtimeFactor()`返回类型由`int`改为`float`，并把elapsed改为
  `step_stop_time - step_start_time`。独立候选
  `.runtime/build/jsbsim-bridge-speed01/jsbsim_bridge`为71,059,096字节，SHA-256为
  `d846038cddbd64859e1d48e414d994248c70c408ec3552d39cb472e2beb63ddf`。
- 真实suite `sim01c-suite-20260916T143604636221`及matrix
  `sim-speed01-matrix-20260916T143604603286`的预注册九run全部`COMPLETE`：0.5倍实测
  0.492476—0.492647、1倍0.971738—0.972527、2倍1.899797—1.909010，逐run零terminal
  且清理通过。前置历史仍见[EXP-20260916-002](experiments/2026-09-16-sim-speed01-preflight.md)，
  实施证据见[EXP-20260916-003](experiments/2026-09-16-sim-speed01-implementation.md)。
- 工具开发期间有一项证据保护偏差：历史1.689637552倍RED目录的
  `scenario-result.json`曾被checker CLI以相同失败结论重写，mtime改变；对应
  `manifest.json`、`speed-result.json`和原始观测未改。技术验收结论不变，但不把
  该历史文件声明为字节未改；详情已进入EXP-20260916-003。2026-09-17用户明确接受
  该已披露偏差，并要求保留完整记录、不伪造原时间且不尝试恢复。依据该处置，
  SIM-SPEED-01及SIM-01C已正式关闭；该接受不改变修复前RED结论，也不关闭SIM-01D、
  PERF-01、完整Phase 1或高速地图测试。
- 09-16用户确认[ADR-012](docs/DECISION_LOG.md)设计边界：保留现有AircraftState状态链，
  定位先作为权威职责而非新增目录；PointCloud2/Image仅作驱动载荷，设备无关契约与
  模型预处理分层；fake LiDAR只在训练数据生成配置为fake Radar/IR产生监督标签，禁止
  进入在线SensorBundle、forward、定位和mapping。本项是文档/计划更新，节点尚未实现。

## 进行中

2026-09-18已完成PERF-01输入参数冻结的第一步：用户确认35/50/70 m/s三个验收航速点，
并指定ARS548为4D Radar参考，确认视场120°×30°、有效距离300 m，mid360为训练监督LiDAR参考。
按常用工程估计补入Jetson Orin NX 16GB/25 W、Micro III Lite 640和低空场景/地图初始阈值；
这些值仍需用户确认与实测，本次未启动性能仿真或感知/地图测量。mid360继续只属于
`training_data_generation`监督支路，不进入在线SensorBundle、感知forward、定位或mapping。

SIM-01C已按[方案](docs/SIM01C_FAULT_CLOCK_PLAN.md)完成F0—F7实际场景；SIM-SPEED-01
九run技术矩阵通过。2026-09-17用户明确接受历史RED派生文件同语义重写及
mtime变化的已披露偏差，要求保留完整记录、不伪造原时间且不尝试恢复；
因此SIM-SPEED-01与SIM-01C已正式关闭。修复前RED、只读核查和修后九run
分别保留在EXP-20260916-001/002/003，偏差处置见EXP-20260917-001。当前进行中的
Phase 1工作还包括PERF-01、ENV-03恢复及SIM-01D至少40分钟跨边界持续性，
不能由短窗倍速结果替代。

ENV-03进行中：本地工作资产与保存责任已登记，第二份副本的介质/位置需在09-20前
明确，10-15前完成恢复检查。LIVE/B1/B2已退出，本任务不留下仿真或回放进程。
2026-09-18用户明确授权先建立Git提交并继续除归档外的任务，同时明确不授权、不执行
外部归档；因此第二份独立副本及恢复验收保持未完成，后续实施接受本机单副本风险。
交互终端仍按用户习惯选择Foxy(1) / Noetic(2)，工具会话未选择版本不作为安装故障；
SIM-00A通过独立子进程使用Noetic，不改变父终端的ROS/Conda环境。

SIM-01A/B/C已完成，D尚未开始；本次进程已退出并通过清理检查，
Phase 1仍未完成。
默认所有新增Python使用Conda Radar-Diffusion；不修改原环境和终端ROS菜单。
实施分工已明确：simulation_engineer负责源状态/时钟，sensor_engineer负责坐标适配，
system_architect负责契约审查，Technical Lead负责薄ROS包装、集成与管理文件。

## 计划

| 顺序 | 任务 | 主责任角色 | 目标日期 | 交付 |
| --- | --- | --- | --- | --- |
| 1 | PERF-01 性能预算 | Technical Lead | 2026-09-20 | 航速、场景、机载算力和时空预算；开发机规格不代替目标约束，优先级不因SIM-01C调试降低 |
| 2 | SIM-SPEED-01 倍速缺陷修复（已完成） | simulation_engineer | 2026-10-01前（实际09-17正式关闭） | 两行修复及0.5/1/2倍各三次技术矩阵通过；用户接受已披露的历史RED派生文件同语义重写偏差，原记录保留且不尝试恢复 |
| 3 | SIM-01C 异常与时钟场景（已完成） | integration_engineer | 2026-10-01前（实际09-17正式关闭） | F0—F7及短窗倍速门槛通过；不含SIM-01D或飞行/感知/地图验收 |
| 4 | ENV-03 版本与产物管理基线 | project_manager | 2026-09-20 | 规则已落地；第二副本位置和复制范围待定，实际提交另按授权，恢复验收10-15前完成 |
| 5 | SIM-01 仿真状态到ROS | simulation_engineer | 2026-10-01 | 实际状态输出、记录回放及坐标时间验证；持续性门槛在10-15前另验 |
| 6 | IFACE-01 定位权威与驱动/业务接口 | system_architect | 2026-10-15 | AircraftState兼容迁移、可选Odometry镜像、PointCloud2适配与唯一TF方案 |
| 7 | SENS-TRAIN-01 训练监督生成支路 | sensor_engineer | 2026-11-10 | fake Radar/IR输入与fake LiDAR target/observed mask同步方案及防泄漏测试 |

表中角色尚未分配给具体人员时由Technical Lead协调。任务实施先遵守根AGENTS的计划与确认流程。

## 风险

| 编号 | 风险与影响 | 主责任角色 | 关闭条件 |
| --- | --- | --- | --- |
| R-01 | 构建、静止状态/时钟、300秒记录回放、F0—F7异常恢复及短窗倍速已通过；持续性及环境恢复仍未验收，Noetic/Foxy均已结束支持 | simulation_engineer | SIM-01D及环境恢复通过后冻结ADR-P001；候选/运行决定见ADR-006至011及ADR-P013 |
| R-02 | 研究正式推理启动引用缺失CLI，模型质量/速度未验收 | perception_engineer | ALG-01和真实后端小样本验证；不阻塞占位模式 |
| R-03 | 航速点和一套工程估计已形成，但机载硬件、IR镜头/同步、场景、地图与质量阈值仍未确认或实测 | Technical Lead | PERF-01及阶段细化，形成可测量验收条件 |
| R-04 | model_lidar逻辑参考系与Body/Radar关系、training_lidar监督外参和时间均未验证 | sensor_engineer | 分别完成模型逻辑变换与训练监督时间/外参测试；不要求在线LiDAR |
| R-05 | 低空场景已有初始估计，但场景几何和热属性来源未确认 | simulation_engineer | ADR-P003及已知场景传感器测试 |
| R-06 | 尚无提交基线或第二份资产副本；会话配置现已精确忽略，但忽略不等于备份 | project_manager | ENV-03建立经授权的版本基线、第二副本及恢复证据，保护原有文件 |
| R-07 | GPU查询在沙箱外仍报NVML驱动/库版本不一致，阻塞GPU可用性验收 | integration_engineer | 独立确认修复范围后复测NVML和目标环境CUDA；不阻塞CPU上的环境设计 |
| R-08 | 接入/预热/双门控及F0—F7异常整run停止已实测通过；协方差仍未知 | simulation_engineer | 保持未知质量，后续补可用协方差来源，不直接改名原始话题 |
| R-09 | SIM-00B入口已规避旧启动器：独立PID/完整日志及清理实测通过 | integration_engineer | 本入口范围已关闭；后续启动装配保持相同进程保护要求 |
| R-10 | 桥接32位微秒参数约35.8分钟后越界；短窗倍速修复不能证明已跨越该边界 | simulation_engineer | 作为独立SIM-01D在10-15前完成至少40分钟跨边界持续运行；不得并入SIM-SPEED-01关闭 |
| R-11 | SIM00B-INIT-01已应用，初始化/消息回归、完整构建及静止遥测通过 | simulation_engineer | 当前独立SITL入口范围已关闭；不代表全部HIL/串口路径均已审计 |
| R-12 | 训练专用LiDAR监督、raw驱动适配和可选Odometry镜像仅有设计，尚无消息/节点/启动图验证 | system_architect | IFACE-01、SENS-TRAIN-01及T-13/T-14通过；不得用文档关闭Phase 2/3 |
| R-13（已关闭） | SIM-SPEED-01两行修复及九run技术矩阵通过，但一份历史RED派生`scenario-result.json`被同语义重写、mtime改变，未满足方案§6/§7证据保全门禁 | simulation_engineer | 2026-09-17用户明确接受已披露偏差并关闭本风险；保留完整记录、不伪造原时间、不尝试恢复，且不用本处置关闭R-10/SIM-01D |

## 下一步任务

PERF-01仍是第一优先级。35/50/70m/s航速点、ARS548参考Radar和mid360训练监督参考已于
09-18确认；Jetson Orin NX/25 W、Micro III Lite 640和低空场景已按常用工程估计填入，
仍需确认镜头/同步、平台可用性和实测阈值，预算不能写成性能验收通过。
SIM-SPEED-01短窗技术矩阵通过不构成这些指标的验证。2026-09-17用户已接受
证据保全偏差，SIM-SPEED-01与SIM-01C已正式关闭；已披露历史继续保留，
不伪造原时间、不尝试恢复。
继续保持原采样时间、未知质量、Conda默认与仅清理本次PID的规则，不放宽业务超时。
R-10的至少40分钟跨边界持续性仍为独立SIM-01D，目标日期保持10-15；该任务尚未开始。
正式Phase 1基线仍待SIM-01D、PERF-01与环境恢复完整验收。本次也未验证
35—70m/s地图更新、Radar—IR感知或训练监督LiDAR。

## 开发入口与证据

- 规则：[根AGENTS](AGENTS.md) → [系统架构](docs/SYSTEM_ARCHITECTURE.md) → 涉及目录AGENTS。
- 接口：[数据格式](docs/DATA_FORMAT.md)、[传感器连接](docs/SENSOR_INTERFACE.md)、[坐标](docs/COORDINATE_SYSTEM.md)。
- 决定：[DECISION_LOG](docs/DECISION_LOG.md)；验证：[EXPERIMENT_LOG](docs/EXPERIMENT_LOG.md)。
- 研究来源：[algorithms/README](algorithms/README.md)。
- 本机环境与缺项：[ENVIRONMENT_INVENTORY](configs/ENVIRONMENT_INVENTORY.md)。
- 下一阶段执行方案：[SIMULATION_VALIDATION_PLAN](docs/SIMULATION_VALIDATION_PLAN.md)。

## 更新规则

每次开发结束更新实际完成、验证边界、风险和下一步；每周复核进度和待决项。
完成项必须链接证据，未执行写未执行；不将日期到达或文档创建视为运行验收通过。
