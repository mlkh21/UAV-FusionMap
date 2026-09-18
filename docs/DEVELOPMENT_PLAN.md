# 开发计划与阶段验收

版本：v0.1；更新日期：2026-09-18；责任角色：project_manager / Technical Lead。
状态：工程计划基线；SIM-00A/B、SIM-01A/B/C及SIM-SPEED-01已完成，
SIM-01D、PERF-01与Phase 1仍待验收。

## 1. 管理方式

目标交付时间为2027年3月。采用逐阶段验收；不以目录、代码或进程存在代替功能通过。
任务至少包含编号、唯一主责任角色、输入依赖、交付物、完成条件、状态和证据。
角色尚未落实到个人时由Technical Lead协调，不假定已有多人并行开发资源。

每周更新PROJECT_STATUS中的已完成、进行中、计划、风险和下一步；每个阶段结束进行
证据审查。计划变更记录原因、影响和决策，不通过删除验证工作追回进度。

## 2. 阶段与时间

| 阶段 | 目标时间 | 主责任角色 | 交付物 | 退出条件 |
| --- | --- | --- | --- | --- |
| Phase 0 工程初始化 | 2026-09-11—09-20 | Technical Lead | AGENTS、七份设计文档、状态台账、目录边界和源码登记 | 文件覆盖、链接、接口/边界一致性通过；未决项有责任、日期和阻塞范围 |
| Phase 1 仿真平台 | 09-21—10-15 | simulation_engineer | PX4+JSBSim+所选ROS连接、状态/时钟记录回放、场景来源 | 版本组合可复现；带时间状态可连续输出；暂停/重置/坐标行为通过 |
| Phase 2 传感器层 | 10-16—11-10 | sensor_engineer | 功能级Radar/IR/IMU、驱动适配、标定、同步、SensorBundle及训练监督生成支路 | 在线Bundle字段/坐标/时间正确；fake Radar/IR与LiDAR监督同步；推理启动图无LiDAR泄漏 |
| Phase 3 感知层 | 11-11—12-15 | perception_engineer | 统一感知接口、模型特定预处理、disabled/placeholder、真实Radar/IR融合后端 | 占位链路通过；训练监督与forward隔离；真实后端满足输入、质量、时延与资源指标 |
| Phase 4 地图层 | 12-16—2027-02-10 | mapping_engineer | Local Map、概率、不确定性、Scene Map、DEM和应用数据接口 | 按下述子阶段通过；查询保持未知/过期语义，运行资源符合预算 |
| Phase 5 系统测试 | 02-11—03-15 | integration_engineer | 高速、转弯、遮挡、复杂环境、丢帧/断流系统试验 | 需求—测试矩阵完成，感知质量与数据闭环分别验收 |
| 交付与修复缓冲 | 03-16—03-31 | Technical Lead | 修复、版本交付清单、复现实验及维护说明 | 无未说明的阻断项；从记录可重现已验收功能 |

允许在不改变阶段门槛的情况下使用占位接口进行小规模联调。
真实感知未达标时，占位成功只证明工程链路，不能据此关闭Phase 3质量目标。
DEM排在基础地图之后；阶段延期须评审范围和时间，不能直接跳过基础阶段。

## 3. Phase 0任务与当前交付

| 编号 | 工作 | 主责任角色 | 交付/完成条件 |
| --- | --- | --- | --- |
| INIT-01 | 核对两仓目录和实际研究入口 | Technical Lead | algorithms/README登记路径、源码证据、阻断和未验证项 |
| INIT-02 | 模块规则和目录边界 | system_architect | 根与11个子目录AGENTS具有七项约束；新增application/tests边界 |
| INIT-03 | 系统与数据设计 | system_architect | 七份docs文档形成一致的分层、字段、时空与异常行为 |
| INIT-04 | 计划、状态和决策记录 | project_manager | PROJECT_STATUS可指向下一任务，待决项有日期与责任 |
| INIT-05 | 初始化验收 | tester | 文件、相对链接、格式、契约关键项、保护范围检查记录 |

INIT任务的实际状态与证据见[PROJECT_STATUS](../PROJECT_STATUS.md)和
[EXPERIMENT_LOG](EXPERIMENT_LOG.md)。本阶段不编写算法、运行节点或执行模型训练。

## 4. 下一批任务

ENV-01已于2026-09-11完成只读核查，见[环境清单](../configs/ENVIRONMENT_INVENTORY.md)。
ENV-02已于同日交付[候选版本与最小验证方案](SIMULATION_VALIDATION_PLAN.md)，
证据见[EXP-20260911-003](../experiments/2026-09-11-simulation-plan-review.md)。
SIM-00A于09-12完成依赖准备与独立构建，见[构建证据](../experiments/2026-09-12-sim00a-build.md)。
ENV-03的忽略/保存规则已落地，第二副本及恢复工作未完成；SIM-01A/B已完成，SIM-01C
与SIM-SPEED-01已于09-17正式关闭；SIM-01D、PERF-01及后续任务仍按各自门槛推进。
按根AGENTS在确认的具体范围内连续完成，不改变原阶段退出门槛。

| 编号 | 任务 | 主责任角色 | 目标日期 | 完成条件 |
| --- | --- | --- | --- | --- |
| ENV-01 | 只读核查现有OS、ROS、PX4、JSBSim、桥接、CPU/GPU及已有环境 | simulation_engineer | 2026-09-18（实际09-11完成） | 已交付安装事实、可复用资产与缺项清单；不是仿真/GPU运行通过 |
| ENV-02 | 选择并记录候选版本组合与最小仿真验证方案 | system_architect | 2026-09-20（实际09-11完成） | ADR-006决定优先验证候选；已交付维护周期、依赖处理、独立构建、状态/时钟源及步骤；ADR-P001运行冻结另验 |
| PERF-01 | 确认航速、算力、场景和接口预算 | Technical Lead | 2026-09-20 | 下节关键参数获得数值、来源与验证方法，或明确阻塞项 |
| ENV-03 | 版本和产物管理基线（进行中） | project_manager | 2026-09-20 | 提交范围/流转/忽略/保存规则已落地；第二副本目标待定，10-15前恢复验收；实际提交另按授权 |
| SIM-00A | 最小依赖准备与隔离构建（已完成） | simulation_engineer | 2026-09-23（实际09-12完成） | JSBSim/MAVROS/geoid在项目目录准备，PX4/桥接构建及依赖检查通过；未安装到系统或启动仿真 |
| SIM-00B | 无界面Rascal遥测短测（已完成） | simulation_engineer | 2026-09-25（实际09-12完成） | 用户确认初始化修复后，独立重建/消息回归/120.056秒遥测及清理通过；不解锁、不起飞 |
| SIM-01 | 最小飞行状态到ROS的记录/回放（A/B/C完成，D待验收） | simulation_engineer | 2026-10-01；持续性10-15前 | C的故障链及短窗倍速已验收；D仍须完成至少40分钟跨边界持续性，Phase 1不提前关闭 |
| SIM-SPEED-01 | 倍速缺陷修复（已完成） | simulation_engineer | 2026-10-01前（实际09-17正式关闭） | 两行修复及独立候选0.5/1/2倍九run技术矩阵通过；用户接受已披露偏差，完整保留历史记录且不尝试恢复 |
| SIM-01C | 异常与时钟场景（已完成） | integration_engineer | 2026-10-01前（实际09-17正式关闭） | F0—F7与短窗倍速验收通过；不含SIM-01D、PERF-01、高速地图、感知或LiDAR验收 |
| IFACE-01 | 定位权威、驱动载荷与业务契约细化 | system_architect | 2026-10-15 | 保留AircraftState；明确可选Odometry镜像、PointCloud2→RadarFrame适配和唯一TF责任；接口测试方案通过 |
| SENS-TRAIN-01 | fake Radar/IR与LiDAR训练监督方案 | sensor_engineer | 2026-11-10 | training/inference配置、时间与外参、target/observed mask、记录清单及防泄漏测试通过；实现另按具体方案确认 |
| ALG-01 | 研究后端接入前置条件清单 | perception_engineer | 2026-11-10 | 核对缺失CLI、权重、归一化、标定、参考系和环境；不阻塞占位链路 |

ENV-01已知条件：用户交互终端选择Foxy(1)/Noetic(2)，两者均有安装及独立环境加载证据；
现有PX4 v1.13.3桥接使用ROS 1/catkin，JSBSim开发安装和MAVROS未在所查范围发现。
ENV-02已决定先验证Noetic/PX4 v1.13.3/JSBSim 1.1.13/MAVROS 1.20.1；状态发布TODO由
后续simulation状态/时钟接入与sensors适配解决，不直接改动共享catkin工作区。
GPU的NVML版本不一致已登记R-07，修复和CUDA验证属于独立明确范围后的任务，不阻塞
无模型的CPU仿真方案设计。正式运行任务仍需各自验收，不能由环境清单代替。

09-12进展：上述ENV-01缺项已通过项目目录解包满足本轮构建，系统安装状态保持原样；
桥接尚有15条可能未初始化警告，登记R-11，需在短测前审查。构建提前完成不代表
Phase 1提前验收。保存与恢复要求见[VERSION_AND_ARTIFACT_POLICY](VERSION_AND_ARTIFACT_POLICY.md)。

同日SIM-00B前置核查进一步确认模式开关及消息结构初始化缺陷；
[SIM00B-INIT-01](../experiments/2026-09-12-sim00b-preflight.md)已形成2文件5处声明的提案，
原构造测试失败，审查副本通过。随后用户确认应用范围，项目内副本修复及静止遥测
通过，见[EXP-20260912-003](../experiments/2026-09-12-sim00b-init-and-smoke.md)。
仅处理初始化，不混入R-10的32位微秒问题或后续SIM-SPEED-01节奏修复，不调整原日期
或验收门槛。

SIM-01A/B/C分别负责消息接入、300秒记录回放和异常/时钟验证，详见具体方案。
桥接32位微秒参数作为R-10独立修复项，方案目标日期为2026-10-05；随后SIM-01D在10-15前完成
至少40分钟跨边界测试及按PERF-01细化的持续性验收。10-01是最小闭环目标，不表示
Phase 1所有验收均已通过；ENV-02增补这些执行细节，没有减少原阶段退出要求。

09-14补充：SIM-01A的[具体实施提案](SIM01A_IMPLEMENTATION_PLAN.md)已由三个对应
子agent分析并二次评审。主责任simulation_engineer负责源/时钟，sensor_engineer负责
状态坐标，system_architect评审消息契约，Technical Lead承担ROS集成。公共编码、
内部话题、虚拟原点和预热例外09-14获用户确认，Python默认Radar-Diffusion。
SIM-01A现已完成独立构建、44项单元/契约、11项ROS fixture及30.196秒valid静止联调，
605对源/适配状态；证据见[EXP-20260914-002](../experiments/2026-09-14-sim01a-implementation.md)。
当日SIM-01B/C/D仍未执行；09-15 B完成见下项，不提前关闭Phase 1或R-10；R-08接入范围已验收，异常场景另验。
预热10秒及缓存/等待参数只用于首轮工程验证，不替代下表性能预算。

09-14后续三个agents交付[SIM-01B具体方案](SIM01B_RECORDING_REPLAY_PLAN.md)，一次
300秒LIVE与B1成品/B2新sensors复算分别验收，主集成责任为integration_engineer。
发布调用台账、接收/落盘/回放多方对账和分层排空用于补全A轻量检查的覆盖范围；
环境参数隔离及显式Noetic元变量为B前置修复。该方案随后获用户确认，09-15已交付
运行与验收工具；环境、增量catkin、73项单元/契约和11项ROS fixture通过。
LIVE连续valid 300.008001秒、B1逐字节回放及B2全新sensors复算均通过；各6,003条
源/适配状态和15,794 clock完整对账，关闭重读与本次进程清理通过。原生clock队列与EOF
交接修复保留失败记录，证据见[EXP-20260915-001](../experiments/2026-09-15-sim01b-implementation.md)。
方案阶段证据见[EXP-20260914-003](../experiments/2026-09-14-sim01b-agent-review.md)；
C/D、性能预算与恢复仍待验收，原阶段日期和门槛不变。

09-16补充：用户确认后，多个对应子agents按[SIM-01C方案](SIM01C_FAULT_CLOCK_PLAN.md)
完成第一批实现和运行。F0—F7实际故障链、terminal锁止、监督清理及新run恢复均通过；
具体边界与复现方式见[运行说明](../simulation/RUN_SIM01C.md)和
[EXP-20260916-001](../experiments/2026-09-16-sim01c-implementation.md)。原“尚未执行”
仅是09-15前置状态，不再代表当前进展。

修复前倍速门槛未通过：2倍最终三次为1.6982、1.6945、1.6896，均低于1.7；0.5倍因getter
把0.5截为0而自由运行，一次20源秒窗口为71.4543倍，随后出现`estimator_reset`
terminal。当时bridge、PX4、消息和业务状态机均未修改，失败证据保留。该结果只接受
SIM-01C故障矩阵子范围，并触发独立SIM-SPEED-01；PERF-01的09-20预算门禁及其优先级
保持不变，SIM-01D持续性仍另验。

SIM-SPEED-01的[只读前置核查](../experiments/2026-09-16-sim-speed01-preflight.md)已完成，
并形成[具体实施方案](SIM_SPEED_01_IMPLEMENTATION_PLAN.md)；该段只记录实施前状态，
EXP-20260916-002及既有RED不作改写。用户确认后，实施仅将`getRealtimeFactor()`返回
类型由`int`改为`float`，并将elapsed修正为`step_stop_time - step_start_time`。
独立候选`.runtime/build/jsbsim-bridge-speed01/jsbsim_bridge`为71,059,096字节，SHA-256
为`d846038cddbd64859e1d48e414d994248c70c408ec3552d39cb472e2beb63ddf`。

真实suite `sim01c-suite-20260916T143604636221`和matrix
`sim-speed01-matrix-20260916T143604603286`严格执行预注册0.5/1/2倍各三次：九run均
`COMPLETE`，0.5倍实测0.492476—0.492647、1倍0.971738—0.972527、2倍
1.899797—1.909010，逐run零terminal且清理通过。实施证据见
[EXP-20260916-003](../experiments/2026-09-16-sim-speed01-implementation.md)。因此
SIM-SPEED-01及SIM-01C短窗倍速技术矩阵已通过；checker CLI曾把历史1.689637552倍
RED目录的`scenario-result.json`以相同失败语义重写并改变mtime，违反方案§6/§7的
历史run保护门禁。2026-09-17用户明确接受该已披露偏差，要求保留完整记录、
不伪造原时间且不尝试恢复；SIM-SPEED-01与SIM-01C因此正式关闭。
32位微秒越界仍归R-10/SIM-01D，不能用本九run关闭。PERF-01仍是管理顺序第一项。
SIM-01D和Phase 1仍未完成；本次没有验证35—70m/s地图更新、Radar—IR感知或训练监督LiDAR。

## 5. 必须量化的性能与场景预算

以下均为待确认项，不能把示例数字或研究数据集设置当作系统默认值。

| 参数组 | 需要确定的内容 | 主责任角色 | 确定时点/阻塞范围 |
| --- | --- | --- | --- |
| 飞行与场景 | v_max、转弯/角速度范围、障碍尺寸/距离、高度与复杂环境定义 | Technical Lead | PERF-01；阻塞“高速可用”的验收声明 |
| 运行资源 | 目标CPU/GPU、内存、功耗约束与测量环境 | integration_engineer | PERF-01；阻塞性能阈值验收 |
| 传感器 | Radar/IR/IMU频率、FOV、量程、图像大小、时间误差；训练监督LiDAR的FOV/range/扫描仅用于标签覆盖 | sensor_engineer | PERF-01初定，Phase 2前细化 |
| 同步与延迟 | 最大采集偏差、姿态年龄、缓存/等待上限、端到端P50/P95/P99及超时率 | system_architect | PERF-01；Phase 1退出前必须可测量 |
| 地图 | 覆盖范围、分辨率、更新频率、内存上限、老化时限、free/occupied阈值 | mapping_engineer | PERF-01初定，Phase 4前冻结 |
| 感知质量 | Occupancy IoU/F1/召回率及距离/高度分层评估，置信度/不确定性验证方式 | perception_engineer | Phase 2退出前确定，阻塞真实模型质量验收 |
| 稳定性 | 连续运行时长、丢帧率、重复/乱序/断流场景与可接受退化 | tester | Phase 1退出前确定，Phase 5执行 |

同步预算考虑`v_max × delta_t`及角运动；前视探测距离、更新延迟和固定翼机动约束
需要共同评估，不能将通用刹停距离直接作为固定翼安全能力证明。

## 6. 地图阶段内部顺序

| 子阶段 | 交付 | 验收重点 |
| --- | --- | --- |
| M1 Local Map | 有界地图、明确frame/origin/resolution及查询 | 单帧已知几何、滚动范围、unknown、坐标变换 |
| M2 Probability | 多帧更新、去重、老化 | 重复观测不重复累计，时间顺序、已知/未知/过期保持正确 |
| M3 Uncertainty | 有来源和单位的质量表达/融合 | 缺失与已知区分，模型量与几何方差不混用 |
| M4 Scene Map | 子地图管理和场景更新 | 定位跳变、跨子地图参考系、覆盖与资源边界 |
| M5 DEM | 显式TerrainPrior接入 | 水平/垂直基准、no-data、时间和高度不确定性 |

每个子阶段需有独立证据。研究仓库已有地图代码不自动满足这些条件。

## 7. 需求与测试对应

测试编号是后续验收设计标识，目前不代表测试代码已存在。

| 需求 | 测试 | 阶段 | 验收对象 |
| --- | --- | --- | --- |
| REQ-01 无研究模型运行 | T-01 | Phase 3/联调 | disabled/placeholder不依赖模型、权重或GPU |
| REQ-02 标准字段及异常语义 | T-02 | Phase 2—4 | 有效值、单位、空值、模式来源、序列化往返 |
| REQ-03 坐标正确 | T-03 | Phase 1—4 | 已知旋转/平移、外参方向、模型布局、动态位姿 |
| REQ-04 时间与同步 | T-04 | Phase 1—5 | 采集时刻、偏差、插值、暂停/回退、扫描时间 |
| REQ-05 未知区域保留 | T-05 | Phase 3—5 | 无回波、缺失输出、未知掩码均不伪造自由空间 |
| REQ-06 真实Radar–IR融合与占据质量 | T-06 | Phase 3/5 | 有效模型输出、模态贡献、分层质量与失效行为 |
| REQ-07 无跨层调用 | T-07 | 各代码阶段 | 依赖检查、节点职责和实际话题连接 |
| REQ-08 多帧地图 | T-08 | Phase 4 | 位姿变化、去重、老化、覆盖与内存边界 |
| REQ-09 应用查询 | T-09 | Phase 4/5 | occupied/free/unknown/stale/unavailable状态 |
| REQ-10 可复现 | T-10 | 各阶段 | 代码/环境/配置/场景/种子/产物记录与回放 |
| REQ-11 高速与持续运行 | T-11 | Phase 5 | 已确认航速、端到端延迟、数据年龄、资源与稳定性 |
| REQ-12 DEM辅助更新 | T-12 | Phase 4/5 | 基准注册、no-data、更新效果与不确定性 |
| REQ-13 训练监督隔离 | T-13 | Phase 2/3 | fake LiDAR只生成target/observed mask；不进入SensorBundle、forward、定位或地图 |
| REQ-14 定位权威与兼容镜像 | T-14 | Phase 2/4 | AircraftState身份/失效语义保留；Odometry/TF不形成冲突来源，地图只用观测时刻上下文 |

## 8. 交付与维护

交付清单包括版本标识、安装/启动说明、配置、接口、实验索引、已知限制与恢复方法。
每次开发前读根AGENTS、PROJECT_STATUS、SYSTEM_ARCHITECTURE及局部规则。
任务完成后更新状态，架构变化记录决策，运行验证记录实验。

main仅承载经过验收的基线，develop承载经过检查的集成，feature/*承载具体任务。
目前仓库尚无首次提交；创建功能分支不等于已有可恢复的提交基线。
数据、checkpoint、日志、结果和会话文件保留原位，首次提交前逐项核对，不能批量混入。
