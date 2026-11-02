# 项目状态历史快照（2026-10-27优化前）

本文件保存优化前的完整状态正文，包含既有未提交工作与失败边界。
相对链接已按本文件位于docs目录机械调整；原事实、日期和结论保留。
当前状态以[PROJECT_STATUS](../PROJECT_STATUS.md)为准，后续不向本快照追加当前任务。

# UAV-FusionMap 项目状态

更新日期：2026-10-27；维护角色：Technical Lead。
当前阶段：SIM-00A/B、SIM-01A/B/C、SIM-SPEED-01及SIM-01D持续性已完成；PERF-01
与ENV-03外部恢复阻塞；2026-10-15正式复核后完整Phase 1仍未通过退出。
计划交付：2027年3月；阶段安排见[DEVELOPMENT_PLAN](../docs/DEVELOPMENT_PLAN.md)。

2026-10-27完成[在线感知失效模式ROS链路](../experiments/2026-10-27-perception-mode-ros-fail-closed.md)
软件子范围：独立disabled、research阻塞各1秒run均收20个有效Bundle、20个
明确unavailable空占据和20个地图拒绝事件，地图快照0、查询revision 0且不可用；
运行时图无训练/LiDAR话题。旧placeholder 2秒run 40组地图闭合，进程/端口清理通过，
新增4项定向及全仓408/408轻量测试通过。首轮观察者就绪失败记录保留。
这是失效态传递与空地图ROS门禁；已有地图不刷新只由纯业务测试验证，不代表
同run模式热切换、旧证据老化、真实设备、研究forward或正式PERF-01完成。

2026-10-26按Phase 2传感器层执行[在线/训练双图软件整合验收](../experiments/2026-10-26-phase2-sensor-integration.md)：
两条独立2秒在线ROS run均通过，参数化fake Radar/IR及专用IR小图分别完成40条Radar
逐点值核对、20个Bundle/占据/地图闭合；小图另完成100条IR原始/20条采用的全像素
值级核对。在线图均有7个必需节点且无训练/LiDAR话题或节点，20次原由拒绝与预期一致。
独立训练`yaw` ROS run通过20组Radar/IR/监督记录、22条状态/clock、20个无回波时间槽
和40次unknown探针，训练LiDAR仅连接训练发布者及记录/观察者；新run进程及端口均清理。
全仓386/386轻量测试通过。此处只确认Phase 2**软件fixture整合子范围**；两条在线run
开发机P99分别为42.984/44.375ms，20ms诊断均未过。真实驱动/设备原始记录、真实
外参与时钟映射、独立IMU交付及完整Phase 2仍未验收，PERF-01/ENV-03不因此关闭。

同日完成[Phase 2 IMU源链与接口门禁](../experiments/2026-10-26-phase2-imu-gate.md)：
已归档SIM-00B原始记录中6051条六轴样本掩码有效、数值有限，采样间隔16–24ms；
项目当前解码只保留IMU时间戳，ROS仅用其推进/clock，既无独立ImuSample公共消息
也没有在线IMU数值出口。新增两项源边界门禁；定向13/13、全仓388/388轻量测试通过。
[生产/消费、兼容及恢复提案](../docs/PHASE2_IMU_GATE_20261026.md)待公共接口确认；本轮
未改生产节点或ROS消息，**不关闭**独立IMU、完整Phase 2、真实标定或正式PERF-01。

同日用户确认上述接口范围后完成[可选仿真IMU独立旁路](../experiments/2026-10-26-phase2-imu-optional-ros.md)：
新增ImuSample消息和默认关闭的源/适配话题，保留采样身份与比力语义，显式虚拟pilot
点FRD→FLU轴转换，协方差仍不可用。独立开启ROS run收到有效源/适配IMU各22条，
源时回退后各追加1条unavailable终止；clock22、状态13。关闭run收到IMU 0条、
clock20、状态13且IMU话题无发布者；两个run均通过且清理。
既有SIM-01 ROS fixture、旧在线fake Radar/IR占位图及全仓394/394轻量测试通过。
此处仅关闭**虚拟IMU可选消息/传输软件子范围**，不把这22条MAVLink fixture写成
真实PX4/JSBSim本次在线传感器或物理标定验收；完整Phase 2、PERF-01和ENV-03仍开放。

同日继续完成[PX4/JSBSim在线IMU虚拟源链短测](../experiments/2026-10-26-phase2-imu-live-px4-jsbsim.md)：
为既有SIM-01监督器增加默认关闭的`--imu-live`，实际独立启动PX4/JSBSim、MAVROS
和两个ROS状态节点；最终版run中30.196秒有效状态窗口，源/适配状态各605条，
原始HIGHRES_IMU与源/适配IMU各2300条按采样身份、时钟及六轴轴变换完全对账，
unknown协方差保留。旧SIM-01 fixture回归和全仓399/399轻量测试通过，端口及
本次进程清理通过。沙箱预检socket被拒的失败目录独立保留。仅验证虚拟pilot点
在线源链；尚未逐帧对照JSBSim内部真值，实物IMU安装/比力标定、设备跨时钟、
真实Radar/IR、完整Phase 2及正式PERF-01仍未验收；旧入口保持默认关闭。

同日完成[JSBSim IMU pilot点比力语义独立对照](../experiments/2026-10-26-phase2-imu-physics-semantics.md)：
沿bridge默认`a-pilot`/HIL_SENSOR、PX4传感器积分和HIGHRES_IMU调用链核对；
单独加载同机型/LSZH，地面、离地早期、±20°滚转四场景通过。
离地0.2秒pilot z=-0.367m/s²（重力模9.822m/s²），接地后pilot z约-9.705m/s²；
±20°初始滚转在0.2秒实际约±18.94°时pilot y相反。
机型EYEPOINT来源为[20,0,5]in，不使用未启用的另一个IMU系统位置。
这只支持**本虚拟配置**pilot点比力/重力符号，不是上次PX4/ROS同run内部真值
逐帧对照或真实安装标定。独立场景和404/404全仓轻量回归通过；真实Radar/IR、
设备时钟、正式PERF-01、完整Phase 2仍开放。

2026-10-16无硬件期间按既定Phase 2传感器计划继续 fake Radar/IR 软件子范围：
[EXP-20261016-001](../experiments/2026-10-16-fake-radar-ir-phase2.md)以两个各2秒的
独立ROS run复核 IR 全像素值和参数化假传感器在线占位链路；各40 Radar/100 IR、
20 Bundle/占据/地图，359项全仓轻量测试通过。20次严格超时拒绝均与预期相符；
两run开发机P99为47.280481/44.385750 ms，20ms诊断均未通过，正式PERF-01、
ENV-03、完整Phase 1/2和真实设备验收仍阻塞。不把训练监督LiDAR加入在线链路。

同日继续完成[EXP-20261016-002](../experiments/2026-10-16-iface-radar-height.md)：新增默认关闭的
fake Radar 原始Frame→采用Bundle逐点值级核对；联合ROS run通过40/20 Radar帧、100/20 IR帧，
值级错误为空。新增独立高度/非水平射线矩阵3场景/9样本通过，其中无回波场景3840个体素
全部unknown；全仓轻量回归为370项通过。开发机P99=43.322513ms仍未通过20ms诊断，正式
PERF-01、真实设备时钟/标定、模型质量和完整Phase 2不变。

2026-10-20完成SENS-TRAIN-COV-01软件覆盖子范围：[独立记录](../experiments/2026-10-20-sens-train-voxel-coverage.md)。
固定距离采样改为正长度线段—体素遍历，端点仍单独标occupied；新增正/负短弦2场景/6记录，
并将完整覆盖oracle用于既有12场景/36记录。全仓372项轻量测试通过；motion/yaw实际ROS
回归各20条训练记录、22条状态/clock并正常清理。未改变公共消息或在线链路；无回波仍unknown。
这是功能级软件fixture结果，不代表真实LiDAR标定、训练质量、硬件性能或正式PERF-01验收。

2026-10-20追加SENS-TRAIN-COV-02边界软件子范围：[独立记录](../experiments/2026-10-20-sens-train-dda-boundaries.md)。
19个固定线段覆盖正反向、面/棱/角、有限网格裁剪、零长度接触及非等距分辨率；退化线段
原遍历器错误返回一个cell，经RED/GREEN只加空线段保护。既有12+2场景、全仓374项轻量
测试及motion/yaw各20条实际ROS训练记录回归通过；不改变训练数据接口、在线图或正式门槛。

2026-10-21完成[T-13A在线ROS图运行时隔离](../experiments/2026-10-21-t13a-online-graph-audit.md)：
新增默认关闭的`--audit-online-graph`诊断和纯函数校验器，拒绝空图、缺失在线节点、
训练/LiDAR话题或节点；在线fake Radar/IR占位ROS run通过，7个预期节点齐全，训练/LiDAR
话题和节点均为空，20个Bundle/Occupancy/Map闭合；训练专用图20条监督记录及隔离收据回归
通过，全仓379项轻量测试通过。开发机P99=42.988710 ms仍未达20 ms诊断；T-13完整、
研究模型forward隔离、真实设备、正式PERF-01和完整Phase 2仍未关闭。

2026-10-23完成[ALG-01 / T-13B研究后端前置审计与感知模式fail-closed](../experiments/2026-10-23-alg-01-t13b-research-preflight.md)：
新增研究preflight checker、输入契约和disabled/placeholder/research最小分发；旧
placeholder默认入口保持兼容。真实目录报告明确阻塞于缺失checkpoint-chain CLI、VAE/LDM
权重、阈值、归一化绑定、model_lidar坐标契约和研究适配器；研究失败不会fallback到占位。
6项定向测试、全仓385项轻量回归和旧placeholder 2秒ROS在线图审计通过；未执行模型forward、
训练、正式PERF-01或科研对照试验。

同日完成ALG-01-R研究仓库入口与checkpoint资产恢复审计：研究仓库存在多组候选
VAE/LDM/CD及threshold，但launcher默认的`formal_v2_80m_86p8_v1`资产目录不存在；三个
正式launcher仍引用缺失的`diagnose_checkpoint_chain.py`。本仓preflight已能识别真实
`radar_normalization_v1/v2`结构、threshold结构、标定文件存在性并列出候选资产；显式
候选检查仍因checkpoint-chain CLI、已验证model_lidar坐标契约和UAV research adapter
缺失而`BLOCKED`。未加载checkpoint、未执行forward，不修改研究仓库。
本轮新增定向测试7/7、全仓轻量回归386/386通过。

同日完成研究仓库checkpoint-chain CLI恢复性审计及用户授权的临时验证：文件由历史
`7b22149`精确恢复后，正式路径`--help`通过；真实 VAE/LDM 父链和 VAE/LDM/CD 完整链
均以`formal_chain_v2`通过协议校验。未执行`--construct`、forward或完整推理；验证后
已删除临时文件，研究仓库恢复为操作前状态，既有未提交改动均保留。因此正式launcher
路径当前仍缺失该文件，preflight继续fail-closed。

同日完成现有研究结果的只读质量否决审计：研究仓库已有16帧Radar+IR LDM离线评估保存
汇总为occupied 3D IoU `0.573125`、precision `0.628417`、recall `0.867223`、
ground false-positive rate `0.733570`，threshold safety recall资格为`not_qualified`；
对应报告还显示16/16帧低于LiDAR目标自编码上界，未知域占据密度异常。该上界不是可部署
基线，但现有Radar+IR结果已足以否决当前候选接入。4帧CD A/B CPU smoke虽通过保存预测
评估协议，但两者指标完全相同，occupied IoU `0.566494`、free recall `0`、ground
false-positive rate `1`，且安全召回资格同样未通过，不能作为质量或模型差异证据。当前
研究候选标记为`rejected_for_integration`；不新增研究适配器，research模式继续不可用且
不回退placeholder。该审计不等同于完整模型质量验收完成，根因定位、替代模型和正式质量
门仍待研究仓库独立工作。

## 当前完成

- 已确认UAV-FusionMap为系统主仓，4D-Radar-Diffusion为同级独立研究仓库。
- 已静态追踪研究预处理、融合、推理与地图关键路径，并登记入口阻断和未验证能力。
- 已建立根和11个子目录AGENTS，保留原规范与目录，增加application/tests及ros_ws/src占位。
- 已写入七份设计文档、README入口、组件登记、计划、决策和实验记录。
- 已完成INIT-01至INIT-05：24个交付文件覆盖、12份AGENTS七项规则、23份Markdown格式
  与90处本地链接检查通过；研究仓库前后Git状态一致。详细边界见实验记录。
- 已在feature/engineering-initialization功能分支建立首次提交`4bd0c33`；后续实现为工作区改动。
- 已完成ENV-01：确认双ROS选择机制、现有PX4与桥接资产，登记JSBSim/MAVROS缺项和
  GPU驱动/库不一致；结果见[环境清单](../configs/ENVIRONMENT_INVENTORY.md)及
  [EXP-20260911-002](../experiments/2026-09-11-environment-inventory.md)。
- 已完成ENV-02：形成[候选版本与最小验证方案](../docs/SIMULATION_VALIDATION_PLAN.md)，
  ADR-006决定优先评估Noetic/PX4 v1.13.3/JSBSim 1.1.13/MAVROS 1.20.1；核心MAVROS
  APT模拟解析为新增7包、升级0、移除0。证据见[EXP-20260911-003](../experiments/2026-09-11-simulation-plan-review.md)。

- 已完成SIM-00A：JSBSim开发包、7个MAVROS相关包及geoid取得并在项目目录解包，
  独立PX4与JSBSim桥接构建通过；依赖解析、包发现、geoid读取及命令环境隔离通过。
  见[构建说明](../simulation/BUILD_SIM00A.md)和[EXP-20260912-001](../experiments/2026-09-12-sim00a-build.md)。
- ENV-03已落实[精确忽略、提交范围与产物保存规则](../docs/VERSION_AND_ARTIFACT_POLICY.md)，
  .runtime有catkin隔离标记；首次提交已完成，第二份资产副本及恢复验收尚未完成。
- 已完成SIM-00B前置核查：确认桥接初始化缺陷，原构造探针失败、审查副本通过，
  已准备2文件5处声明的补丁；历史提案见[EXP-20260912-002](../experiments/2026-09-12-sim00b-preflight.md)。
- 用户确认后已应用SIM00B-INIT-01，仅修改项目内桥接副本；新构建与消息回归通过，
  旧二进制保留。SIM-00B实测120.056秒静止遥测通过：IMU 6051条、50Hz，心跳121条，
  ODOMETRY 2407条；未解锁，本次进程和端口清理通过。
  见[EXP-20260912-003](../experiments/2026-09-12-sim00b-init-and-smoke.md)及[运行说明](../simulation/RUN_SIM00B.md)。

上述SIM-00交付证明文档、独立构建及静止遥测通过；SIM-01A状态/时钟证据见下项。
地图、算法质量和高速飞行仍未验收。

- 09-14已调用system_architect、simulation_engineer、sensor_engineer完成只读分析与
  二次复核，形成[SIM-01A实施提案](../docs/SIM01A_IMPLEMENTATION_PLAN.md)，现已获用户确认。
  新发现及边界见[EXP-20260914-001](../experiments/2026-09-14-sim01a-agent-review.md)；该记录保留实施前状态。

- 用户09-14确认后，三个子agents与Technical Lead完成SIM-01A：四个ROS消息、源筛选/
  时钟状态机、NED/FRD坐标适配、有界接收门控及两层薄节点；默认Python为Radar-Diffusion。
- 独立catkin与44项单元/契约通过；固定历史重建2103对状态、6051 clock，无FAULT。
  11项实际ROS fixture通过；未解锁静止联调605对状态、2302 clock、30.196秒valid跨度。
  抽查8个Python本次进程及后代均来自Conda；已知端口和进程清理通过。
  见[EXP-20260914-002](../experiments/2026-09-14-sim01a-implementation.md)及
  [RUN_SIM01A](../simulation/RUN_SIM01A.md)，仍非完整Phase 1或飞行验收。

- SIM-01B已完成：300.008001秒连续valid LIVE记录、B1成品逐字节回放、B2全新sensors复算
  分别通过。15,794 clock和源/适配各6,003条逐话题身份、完整质量与落盘重读一致。
- 73项单元/契约、11项实际ROS fixture及增量catkin通过；三个成功会话均已正常退出，
  清理无强制信号或审计PID残留。B1/B2额外clock计数均为0；未解锁或发送控制命令。
- B实施由对应子agents与Technical Lead完成；原生clock队列复用、EOF交接及退出码
  问题已在项目入口修复，三次失败B1原始证据保留。见[EXP-20260915-001](../experiments/2026-09-15-sim01b-implementation.md)
  与[RUN_SIM01B](../simulation/RUN_SIM01B.md)。本次完成不代表整个Phase 1或高速飞行通过。

- 用户确认后，多个对应子agents与Technical Lead完成SIM-01C第一批实施。F0—F7已在
  独立run中通过实际故障注入、唯一终止原因、terminal后零valid、监督清理及新run恢复
  验收；故障帧使用真实MAVLink编码并通过source和sensors链路，F0与F6按各自无上游输入/
  sensors本地回退的边界验收。证据见[实施记录](../experiments/2026-09-16-sim01c-implementation.md)
  与[运行说明](../simulation/RUN_SIM01C.md)。
- 修复前bridge倍速实测未通过：2倍三次实际为1.6982、1.6945、1.6896，均低于1.7下限；
  0.5倍因float getter截断为0而自由运行，一次20源秒窗口测得71.4543倍，随后发生
  `estimator_reset` terminal。现状RED及失败运行均保留；未修改bridge、PX4、公共消息
  或业务状态机。该历史结果触发SIM-SPEED-01，不能被修复后结果覆盖。
- SIM-SPEED-01已按[具体实施方案](../docs/SIM_SPEED_01_IMPLEMENTATION_PLAN.md)实施：仅将
  `getRealtimeFactor()`返回类型由`int`改为`float`，并把elapsed改为
  `step_stop_time - step_start_time`。独立候选
  `.runtime/build/jsbsim-bridge-speed01/jsbsim_bridge`为71,059,096字节，SHA-256为
  `d846038cddbd64859e1d48e414d994248c70c408ec3552d39cb472e2beb63ddf`。
- 真实suite `sim01c-suite-20260916T143604636221`及matrix
  `sim-speed01-matrix-20260916T143604603286`的预注册九run全部`COMPLETE`：0.5倍实测
  0.492476—0.492647、1倍0.971738—0.972527、2倍1.899797—1.909010，逐run零terminal
  且清理通过。前置历史仍见[EXP-20260916-002](../experiments/2026-09-16-sim-speed01-preflight.md)，
  实施证据见[EXP-20260916-003](../experiments/2026-09-16-sim-speed01-implementation.md)。
- 工具开发期间有一项证据保护偏差：历史1.689637552倍RED目录的
  `scenario-result.json`曾被checker CLI以相同失败结论重写，mtime改变；对应
  `manifest.json`、`speed-result.json`和原始观测未改。技术验收结论不变，但不把
  该历史文件声明为字节未改；详情已进入EXP-20260916-003。2026-09-17用户明确接受
  该已披露偏差，并要求保留完整记录、不伪造原时间且不尝试恢复。依据该处置，
  SIM-SPEED-01及SIM-01C已正式关闭；该接受不改变修复前RED结论，也不关闭SIM-01D、
  PERF-01、完整Phase 1或高速地图测试。
- 09-16用户确认[ADR-012](../docs/DECISION_LOG.md)设计边界：保留现有AircraftState状态链，
  定位先作为权威职责而非新增目录；PointCloud2/Image仅作驱动载荷，设备无关契约与
  模型预处理分层；fake LiDAR只在训练数据生成配置为fake Radar/IR产生监督标签，禁止
  进入在线SensorBundle、forward、定位和mapping。本项是文档/计划更新，节点尚未实现。

- 2026-09-22完成PERF-01-A异步扩展：Radar/IR由独立发布进程产生，sensors层维护有界
  匹配缓存并按原Radar采样时间构建SensorBundle；唯一`/clock`、5 ms同步阈值、40 ms
  等待、10 ms位姿年龄和500 ms墙钟上限均按配置执行。7/7确定性场景（正常异步、5 ms
  相位、抖动、乱序、缺帧、缓存溢出、恢复）及640×512 IR正常场景通过；生成/接收/采用/
  未采用/预期拒绝/意外丢失分账与地图身份、时间、unknown语义闭合。证据见
  [EXP-20260922-001](../experiments/2026-09-22-perf01a-async.md)。配对等待纳入的20 ms
  诊断仍失败（约43.5—46.7 ms P99）；该09-22结果不包括09-23运动短测。

- 2026-09-23完成[高速运动时空一致性功能级基线](../experiments/2026-09-23-perf01a-motion.md)：
  35/50/70m/s状态、固定世界障碍物采样时刻Radar相对测量、真实历史姿态及地图更新
  已经小图实际ROS短测；50/70m/s的5ms历史位姿偏差约0.25/0.35m。70m/s断流
  恢复与乱序拒绝后clock域地图老化/恢复核对通过，全仓194项轻量契约通过。格网边界RED
  和大图恢复oracle理由失败均保留；大图normal功能通过但感知P99=69.328ms未达20ms。
  此基线不是高速实时验收、PX4飞行、研究模型质量或机载资源验收。

- 2026-10-03完成fake Radar/IR功能级参数化：保留旧函数兼容和默认固定载荷，新增可选FOV、
  最大量程、位置/强度噪声、Radar扫描持续时间、IR背景/噪声和曝光持续时间；异步生产器、
  旧场景包装和配置校验已接通。新增fake传感器测试及相关motion、contract、scenario、async、
  wrapper、wire回归通过。该结果仅证明功能级参数入口和可重复性，不证明真实设备驱动、物理
  真实性、机载资源或研究模型质量；LiDAR仍不得进入在线SensorBundle、forward、定位或mapping。
  证据见[EXP-20261003-002](../experiments/2026-10-03-fake-sensor-parameterization.md)。
- 2026-10-03完成参数化fake Radar/IR真实ROS短链路：启用FOV、量程、强度/IR噪声和扫描/
  曝光时长后，独立发布器→匹配→SensorBundle→placeholder→Local Map的修正版2秒run通过，
  20个有效样本闭合。首轮位置噪声使静态点跨越0.5m地图格并触发严格oracle失败，原始失败
  保留；未放宽校验，改为在静态oracle场景关闭位置噪声。位置噪声仍需独立动态地图oracle，
  本次不产生20ms性能结论。证据见[EXP-20261003-003](../experiments/2026-10-03-fake-sensor-ros-parameterized.md)。
- 2026-10-03补齐位置噪声动态地图oracle：新增`map_oracle: radar_points`，以已接收Bundle
  的Radar点和`T_mapping_source`独立计算体素，再核对地图累计cell集合、概率、observed和
  最后观测时间。`parameterized_position_noise`开启0.01m位置噪声的2秒ROS run通过，20个
  有效样本闭合；不复用固定静态格点、不放宽地图或同步门限，不产生20ms或真实Radar质量结论。
  证据见[EXP-20261003-004](../experiments/2026-10-03-fake-sensor-position-noise-oracle.md)。
- 2026-10-04完成fake IR空间热点扩展：新增可重复的像素坐标圆形热点、重叠增量和边界校验；
  默认空热点列表保持固定背景行为。`parameterized_sensors`真实ROS 2秒run通过，热点经
  IR发布、匹配、SensorBundle、placeholder和Local Map链路闭合。热点仍只是
  `fixture_intensity`结构，不代表温度/辐射物理或真实IR质量；不改变5ms/20ms边界。
  证据见[EXP-20261004-001](../experiments/2026-10-04-fake-ir-hotspots.md)。
- 2026-10-05完成SENS-IR-01同帧IR数值守恒门禁：新无噪声4×3场景真实ROS 2秒run
  采集100帧原始发布IR，20个采用帧的Bundle与发布帧按run/clock/sample/frame、采样/
  曝光时间及全部12个像素逐帧核对；热点中心索引5与背景索引0对oracle成立。严格配对
  拒绝20/20、状态/时钟排空、地图闭合与进程清理通过；首次null配置失败run保留，
  全仓226项轻量测试通过。20ms诊断P99=45.144325ms未通过，额外订阅不可作为性能证据；
  在该SENS-IR-01记录完成时，SIM-01D至少40分钟长测及训练监督LiDAR均未执行；随后
  SIM-01D已由EXP-20261005-003独立验收。见[EXP-20261005-001](../experiments/2026-10-05-sens-ir-value-transport.md)。
- 2026-10-05完成PERF-01正式测量门禁预检：新增只读
  [`perf01_budget_gate.py`](../ros_ws/perf01_budget_gate.py)和`formal_measurement`配置组，
  当前明确输出`reference_only`而非性能通过。目标平台、正式起止端点、设备采样时钟/跨时钟
  映射、Radar/IR选定配置和持续时长共10项阻塞保持显式；5 ms同步和20 ms P99目标由测试
  锁定，未启动ROS或长测。证据见[EXP-20261005-002](../experiments/2026-10-05-perf01-budget-gate.md)。
- 2026-10-05完成SIM-01D独立持续性验收：专用候选bridge、独立Master/端口和Conda
  环境启动约41分钟，源状态有效跨度`2400004000000 ns`，跨越边界
  `2147483647000 ns`；clock/source/sensor频率约50/20/20 Hz，最大间隔分别为
  24.001/60/60 ms，源状态与适配状态各48002条，clock 120786条。实时记录、bag
  回读、writer排空、边界checker和进程/端口清理均`passed=true`；未执行控制命令、未
  进入训练LiDAR或PERF-01性能判定。证据见[EXP-20261005-003](../experiments/2026-10-05-sim01d-continuity.md)。
- 2026-10-06完成PERF-01正式输入与证据预检：只读审计确认当前为x86笔记本，未发现
  Jetson Orin NX、ARS548或Micro III Lite物理输入，亦无外部功耗和设备采样时钟证据；
  当前门禁保持`reference_only`、10项正式输入阻塞。新增
  [`perf01_formal_preflight.py`](../ros_ws/perf01_formal_preflight.py)及契约测试，拒绝以
  fixture频率、仿真时间或`/clock`替代物理采样依据；未启动正式ROS性能运行。证据见
  [EXP-20261006-001](../experiments/2026-10-06-perf01-formal-preflight.md)。
- 2026-10-08完成PERF-01证据内容数值预检：六类JSON证据按同一run/航速/时钟域
  对账，逐样本单调时间重算P50/P95/P99，并检查单样本年龄、5ms Radar—IR同步、
  10ms姿态年龄、输入输出及丢帧/超时率、功耗/内存和连续时长。先复现空文件、
  `passed=true`、虚报或超标P99均被旧门禁接受的RED，再以严格拒绝规则实现GREEN；
  全仓243项轻量测试通过。测试仅为合成证据，未采集硬件或新增ROS性能运行；实际
  配置仍`reference_only`，PERF-01及Phase 1未验收。见
  [EXP-20261008-001](../experiments/2026-10-08-perf01-metric-preflight.md)。
- 2026-10-08预登记的35/50/70m/s各2秒640×512开发机真实ROS短测均未通过：
  三档均收到40 Radar/100 IR，却各自严格拒绝40 Radar，0 Bundle/Occupancy/Map，
  P99因无有效样本不可计算。首次35m/s运行触发可选`null`无法经ROS XML-RPC
  封送，修复仅省略写入参数服务器的空字段并新增测试；首次失败和三档失败目录
  全部保留。资源角色/采样及进程端口清理成功，不能替代配对/地图闭合，
  不把失败标为速度可用或机载性能通过。见
  [EXP-20261008-002](../experiments/2026-10-08-perf01a-three-speed-fixture.md)。
- 2026-10-08预登记零噪声IR生成局部优化：保留非零噪声、热点、消息、1ms时钟与
  5ms同步/40ms匹配截止；全仓245项轻量测试通过。35/50/70m/s各2秒640×512
  真ROS开发机run均按原oracle达到20采用/20严格拒绝、20个Bundle/占据/地图闭合，
  收据/资源/时钟和清理通过；此前全拒绝的失败run原样保留。
  实测回调到占据P99分别49.703/49.834/60.720ms，仍均高于20ms。
  设备采样时钟不可用且正式平台/功耗证据缺失，功能恢复不等于PERF-01达标。
  见[EXP-20261008-003](../experiments/2026-10-08-perf01a-zero-noise-candidate.md)。
- 2026-10-08追加正式证据预检审阅：补齐两路设备时钟身份、非有限时间误差与
  聚集/倒序采样的拒绝规则和合成负例；全仓248项轻量测试通过，预算配置
  `--require-formal`仍为`reference_only`、10项输入阻塞。工具不能证明自报的
  平台/时钟/功耗实际存在；标称频率帧间距上界保守，正式传感器抖动合同待确认。
  见[EXP-20261008-004](../experiments/2026-10-08-perf01-evidence-audit.md)。
- 2026-10-08在已闭合70m/s大图fixture上另跑2秒匹配锁/线格式插桩诊断：
  20采用/20严格拒绝与地图、资源、进程/端口清理通过；同帧只读联接通过，
  最慢帧IR序列化/线格式到反序列化混合区间/反序列化约6.18/11.62/6.83ms。
  插桩P99=44.872ms仍超20ms，无探针run约29.96ms的`ready_to_encode`
  长尾本次未重现；不能将探针前后P99当受控A/B或宣称解决了调度成本。
  见[EXP-20261008-005](../experiments/2026-10-08-perf01a-probe-after-fastpath.md)。
- 2026-10-09预登记IR回调借用列表的单候选、按70m/s大图运行A-B-B-A：
  四次均20严格采用/20原由拒绝并完成地图闭合，250项轻量回归通过；
  解码P50显著下降，但端到端P99的A/B中位数54.700/50.416ms，
  降幅7.83%未达预设10%采纳门槛，默认保持关闭；四次均超20ms。
  不改变严格拒绝、5ms同步、正式`reference_only`或目标硬件阻塞。
  见[EXP-20261009-001](../experiments/2026-10-09-perf01a-ir-decode-copy.md)。

## 进行中

2026-09-20线格式成本归因与旁路订阅对照已完成，见
[EXP-20260920-004](../experiments/2026-09-20-perf01a-wire-cost.md)。实际serialize/deserialize
探针、两端身份审计及本次进程树CPU/RSS采样已落地；full/light/metadata正式汇总感知
P99为33.257/31.377/27.546ms。metadata取消大图旁路订阅，独立IR无接收者，不能将该路
发布尝试写作交付成功；bundle业务交付由两端记录核对。单个NumPy接收解码候选端到端
降幅中位数0.950%，未达预登记10%，保留standard默认。全仓141项契约、33个短ROS run
功能检查通过，15个正式run的20ms诊断全部失败。采样有可测CPU开销，GPU/NPU/功耗与
目标机载平台仍未验收；SIM-01D长测已于2026-10-05通过，ENV-03归档/恢复仍未执行。

2026-09-20大图耗时只读定位完成：最慢30.376ms样本中，bundle就绪至感知回调约
18.806ms，回调内约0.817ms；内存微基准提示完整图像检查也有显著观察开销。
分段计时源码写入两次因权限审查超时未执行；分析见[PERF-01预算](../docs/PERF01_BUDGET.md)。
该定位没有新增ROS性能验收结果。

2026-09-20后续完整IR与同步故障检查完成：full_ir为640×512测试图；修复待clock状态
被覆盖及逐像素深拷贝开销后，六个ROS场景功能检查通过，128项回归通过。
大图40/40地图更新，但感知P99=30.376ms，高于20ms工程目标；PERF-01仍进行中。
见[EXP-20260920-002](../experiments/2026-09-20-perf01a-load-faults.md)。

2026-09-20 PERF-01-A短时占位闭环技术验证通过：统一运行器等待订阅就绪后发送160样本，
六路业务接收各160条、800条事件全部valid、160根样本闭合；实际地图和进程/端口清理通过。
全仓122项契约通过。当前为静止单Radar点、2×2 IR、小格网；不作为35/50/70m/s或机载验收。
SIM-01D补齐候选路径门控和只读checker，6项前置测试通过；该记录形成时长测仍未执行，
后续长测见EXP-20261005-003。
实现/失败/限制与09-18零事件报告被重建的证据偏差见
[EXP-20260920-001](../experiments/2026-09-20-perf01a-integration.md)。此技术结果不关闭PERF-01。

2026-09-18已完成PERF-01输入参数冻结的第一步：用户确认35/50/70 m/s三个验收航速点，
并指定ARS548为4D Radar参考，确认视场120°×30°、有效距离300 m，mid360为训练监督LiDAR参考。
按常用工程估计补入Jetson Orin NX 16GB/25 W、Micro III Lite 640和低空场景/地图初始阈值；
这些值仍需用户确认与实测，本次未启动性能仿真或感知/地图测量。mid360继续只属于
`training_data_generation`监督支路，不进入在线SensorBundle、感知forward、定位或mapping。

SIM-01C已按[方案](../docs/SIM01C_FAULT_CLOCK_PLAN.md)完成F0—F7实际场景；SIM-SPEED-01
九run技术矩阵通过。2026-09-17用户明确接受历史RED派生文件同语义重写及
mtime变化的已披露偏差，要求保留完整记录、不伪造原时间且不尝试恢复；
因此SIM-SPEED-01与SIM-01C已正式关闭。修复前RED、只读核查和修后九run
分别保留在EXP-20260916-001/002/003，偏差处置见EXP-20260917-001。当前进行中的
Phase 1工作还包括PERF-01和ENV-03恢复；SIM-01D已由独立长测关闭R-10，
不能由短窗倍速结果替代其他持续性或性能门槛。

ENV-03进行中：本地工作资产与保存责任已登记，第二份副本的介质/位置需在09-20前
明确，10-15前完成恢复检查。LIVE/B1/B2已退出，本任务不留下仿真或回放进程。
2026-09-18用户明确授权先建立Git提交并继续除归档外的任务，同时明确不授权、不执行
外部归档；因此第二份独立副本及恢复验收保持未完成，后续实施接受本机单副本风险。
交互终端仍按用户习惯选择Foxy(1) / Noetic(2)，工具会话未选择版本不作为安装故障；
SIM-00A通过独立子进程使用Noetic，不改变父终端的ROS/Conda环境。

SIM-01A/B/C已完成。2026-09-18已完成SIM-01D的32位微秒边界前置修复、独立候选构建、
HIL_SENSOR/HIL_GPS边界RED/GREEN、SIM-00B初始化回归、SIM-SPEED getter回归和正式SIM-01
Python 97/97契约回归；2026-10-05已完成独立连续运行器的跨边界长测、bag回读和清理对账。
ENV-03外部归档未执行，本机单副本风险保持开放，PERF-01与完整Phase 1仍未完成。
默认所有新增Python使用Conda Radar-Diffusion；不修改原环境和终端ROS菜单。
实施分工已明确：simulation_engineer负责源状态/时钟，sensor_engineer负责坐标适配，
system_architect负责契约审查，Technical Lead负责薄ROS包装、集成与管理文件。

## 计划

2026-10-15已完成[Phase 1日期/范围复审](../docs/PHASE1_DATE_SCOPE_REVIEW_20261015.md)：
原目标日未通过，不删PERF-01或ENV-03关口；外部输入/授权与验收排程均未确认，
**新退出日期待定**，不擅改原计划。建议输入到齐即复核，最迟在原Phase 2
结束日2026-11-10复查风险（此为待确认管理检查点，非新退出日）。
同日按计划允许的提前独立软件子范围完成
[IFACE-01/SENS-TRAIN-01记录与标签审计](../experiments/2026-10-15-iface01-sens-train-audit.md)：
设备记录拒绝伪造时间来源/跨frame流；训练标签新增命中前保守free子集、
越界free拒绝及严格布尔mask。RED先复现，随后15项设备、49项训练、
全仓353项轻量测试及新目录12场景/36记录离线矩阵通过；不关闭完整Phase 2、
IFACE-01真实设备
或SENS-TRAIN-01模型质量。地图下一步仅准备
[M1真实输入与资源验收矩阵](../docs/M1_INPUT_RESOURCE_GATE_20261015.md)：
当前缺实物输入/资源时钟，不能验收M1或提前开发M2；Phase 4原定2026-12-16开始。
本次仍不改`.gitignore`：新增实验及被忽略测试不会自动出现于普通`git status`，
后续版本纳入需逐文件审核；未提交/推送，未动同级研究仓库或历史run。

同日增量[EXP-20261015-002](../experiments/2026-10-15-iface-replay-training-ray-m1-resource.md)：
只读IFACE-01设备JSONL回放入口、训练场景离轴false-free拒绝、默认关闭的
地图进程RSS诊断；359项轻量测试、12场景/36记录新目录离线回读及滚动/旧查询
四次独立ROS fixture（滚动+旧三模式）均通过。地图采样仅11次、
开发机RSS采样峰值45,383,680字节，
没有真实设备来源、目标机/功耗及同run完整延迟分布，不能关闭M1、PERF-01、
完整Phase 1/2或ENV-03，不启动M2/DEM/对照试验。原计划时间保持不变。

2026-10-15已执行[Phase 1退出门禁正式复核](../docs/PHASE1_EXIT_REVIEW_20261015.md)：
现存SIM-01D三份报告均`passed=true`且跨边界，A/B/C及倍速只按既有记录
认可软件子范围；当日PERF-01预算门禁仍为`reference_only/ready=false`、
10项外部输入阻塞，`--require-formal`以退出码1正确拒绝参考模式；
不能形成正式20ms或机载资源/功耗结论。ENV-03无新增
外部归档授权或经验证的第二份副本/新目录恢复收据，单副本风险保持开放。
因此完整Phase 1在原2026-10-15日期**阻塞，未通过退出**；原计划日期、
门槛和历史记录保留，新日期/范围待单独评审。此次没有重读原始bag、
重跑长仿真、执行外部归档或改动业务代码；2026-10-16的软件子项可独立推进，
不得据此倒填Phase 1完成或提前对照试验。

2026-10-14完成[Phase 1退出门禁预复核](../docs/PHASE1_EXIT_PREREVIEW_20261014.md)：
仅核对既有SIM-01D验证/记录/清理产物（均通过），重跑只读PERF-01预算门禁
仍为`reference_only`、`ready=false`、10项正式输入阻塞；ENV-03第二份副本
仍未获授权。2026-10-15的正式复核尚未执行，完整Phase 1不宣告完成；
该日缺输入时应分别保留阻塞并评审日期/范围，不自动改阶段计划。
本次未接入硬件、未执行正式性能运行或外部归档，历史实验不变。

同日无硬件软件续审：[PERF-01同帧只读复核](../experiments/2026-10-14-perf01-phase1-readonly.md)
核对四条既有A-B-B-A短测的各20个闭合样本；各run的20/20有效帧均高于
开发机20ms诊断线，四条最慢同帧配对等待23.027—44.439ms、
Bundle发送→回调9.390—20.157ms。分析未运行新ROS、未修改算法或放宽门限，
不合并run分位数；正式门禁复跑仍为`reference_only`/10项阻塞，
Phase 1和PERF-01不因此关闭。ENV-03只读核查还发现当前未提交的`.gitignore`
整目录忽略`experiments/`和`tests/`，新记录与测试普通`git status`不可见；
未修改用户现有规则、Git索引或执行归档，版本化方案需另行确认。
SIM-01独立只读复核已在[预复核表补充](../docs/PHASE1_EXIT_PREREVIEW_20261014.md)
限定A/B/C/D历史产物范围：F6只是sensors本地`/clock`回退，F7是新run恢复；
未重新回读全部原始bag或启动新的仿真，既有验收结论和10-15门槛不变。

2026-10-08更新：[开发计划§4](../docs/DEVELOPMENT_PLAN.md)保持PERF-01全项目第一优先级；
预算、manifest及数值门禁预检已完成，但正式测量输入仍阻塞。
10-03三条大图开发机短测感知P99为58.745/78.635/53.507 ms，均超20 ms且无物理采样时钟；
10-04热点短测`passed=true`原仅核对IR帧身份/时间戳、图像尺寸和像素数；10-05的独立
SENS-IR-01短测已按同帧值级oracle通过；SIM-01D的40分钟持续性随后已独立通过，ENV-03
恢复验收仍未执行；不以传感器短测代替正式持续性或性能验收。
原09-20 PERF-01及ENV-03日期已逾期，10-15 Phase 1退出存在风险，未另行确认新阶段日期。
10-04计划修订未运行新ROS；10-05执行SENS-IR-01短测、PERF-01预算预检、SIM-01D独立
持续性验收与轻量测试，未训练或运行研究模型。10-06完成平台/设备只读审计和正式证据
预检契约测试；因当前主机与真实传感器不满足正式输入条件，未启动正式性能运行。

| 执行次序 | 任务 | 主责任角色 | 目标日期 | 下一交付与完成边界 |
| --- | --- | --- | --- | --- |
| P0-1 | PERF-01 性能预算（进行中，正式输入阻塞） | Technical Lead | 原定2026-09-20已逾期；10-15复核 | [预算门禁](../experiments/2026-10-05-perf01-budget-gate.md)、[manifest预检](../experiments/2026-10-06-perf01-formal-preflight.md)及[证据数值预检](../experiments/2026-10-08-perf01-metric-preflight.md)已覆盖结构和阈值反例；实际配置仍`reference_only`，无目标平台/真实Radar-IR/设备时钟/外部功耗证据；严格拒绝理由、5 ms同步门限与20 ms目标不变，开发机功能短测不等于机载实时通过 |
| P0-2 | SENS-IR-01 同IR帧热点/背景数值守恒（已完成） | sensor_engineer | 2026-10-08计划门槛（实际10-05） | 新[EXP-20261005-001](../experiments/2026-10-05-sens-ir-value-transport.md)真实ROS短测按IR sample_id核对100帧发布IR与20个采用它的SensorBundle的全像素、时间、热点与背景；失败run保留，旧`passed=true`未用于关闭本项 |
| P0-3 | SIM-01D 持续性验收（已完成） | simulation_engineer | 2026-10-15原阶段目标（实际10-05完成） | [独立长测](../experiments/2026-10-05-sim01d-continuity.md)有效跨度`2400004000000 ns`并跨越32位微秒边界；bag回读、状态/时钟对账和清理通过；不等同于PERF-01或完整Phase 1 |
| P1-1 | IFACE-01 定位权威与驱动/业务接口（进行中，T-14及fake Radar值级fixture子范围通过） | system_architect | 2026-10-15 | [ARS548/Mid-360设备时间合同](../experiments/2026-10-13-device-time-contract.md)、[设备时间记录审计](../experiments/2026-10-13-device-time-record-audit.md)、[T-14 fixture](../experiments/2026-10-14-t14-odom-tf.md)及[Radar值级核对](../experiments/2026-10-16-iface-radar-height.md)通过；AircraftState仍为唯一状态权威；真实设备记录回放/跨设备时钟误差、真实协方差和正式平台仍未验收 |
| P1-2 | SENS-TRAIN-01 训练监督生成支路（进行中，ROS直线/偏航、12场景、高度/无回波及体素覆盖/边界fixture子范围通过） | sensor_engineer | 2026-11-10 | [ROS偏航闭环](../experiments/2026-10-13-sens-train-yaw-ros.md)、[ROS直线闭环](../experiments/2026-10-13-sens-train-motion-ros.md)、[高度矩阵](../experiments/2026-10-16-iface-radar-height.md)、[完整体素覆盖](../experiments/2026-10-20-sens-train-voxel-coverage.md)和[DDA边界](../experiments/2026-10-20-sens-train-dda-boundaries.md)软件子范围通过；真实标定/设备时钟/规模/模型质量仍未验收 |
| P1-3 | ENV-03 版本与产物管理基线（外部副本未获授权） | project_manager | 原定2026-09-20已逾期；10-15复核 | 规则和首次提交已有；无新授权不得执行外部归档/恢复验收，本机单副本风险保持开放 |
| P2 | ALG-01及后续研究/高级地图（进行中，T-13B软件子范围已完成） | perception_engineer | 2026-11-10起按阶段评审 | preflight已明确研究阻塞；disabled/placeholder兼容且fail-closed；真实后端、融合质量、机载部署及DEM/飞行分别验收 |

SIM-SPEED-01及SIM-01C已于09-17正式关闭，SIM-01A/B/C成果及原失败记录保持。
表中角色尚未分配给具体人员时由Technical Lead协调，执行次序不表示已有并行人力。
任务实施先遵守根AGENTS的计划与确认流程；10-15若门槛未过，另行评审日期，
不得用省略测试或自动顺延宣布Phase 1完成。

## 风险

| 编号 | 风险与影响 | 主责任角色 | 关闭条件 |
| --- | --- | --- | --- |
| R-01 | 构建、静止状态/时钟、300秒记录回放、F0—F7异常恢复、短窗倍速及SIM-01D持续性已通过；环境恢复仍未验收，Noetic/Foxy均已结束支持 | simulation_engineer | 环境恢复通过后冻结ADR-P001；候选/运行决定见ADR-006至011及ADR-P013 |
| R-02 | 研究正式推理启动引用缺失CLI，模型质量/速度未验收 | perception_engineer | ALG-01和真实后端小样本验证；不阻塞占位模式 |
| R-03 | 航速点和一套工程估计已形成，但机载硬件、IR镜头/同步、场景、地图与质量阈值仍未确认或实测 | Technical Lead | PERF-01及阶段细化，形成可测量验收条件 |
| R-04 | model_lidar逻辑参考系与Body/Radar关系、真实training_lidar外参和跨设备时钟误差仍未验证；ARS548/Mid-360字段语义已按型号固化，功能级非零扫描合同已验证 | sensor_engineer | 完成真实标定/独立设备记录/ROS记录验证和时钟残差审计；不要求在线LiDAR |
| R-05 | 低空场景已有初始估计，但场景几何和热属性来源未确认 | simulation_engineer | ADR-P003及已知场景传感器测试 |
| R-06 | 已建立提交基线4bd0c33；第二份资产副本和恢复验收未完成，用户不授权归档 | project_manager | 保持本机资产；外部副本任务仅在后续获授权后执行 |
| R-07 | GPU查询在沙箱外仍报NVML驱动/库版本不一致，阻塞GPU可用性验收 | integration_engineer | 独立确认修复范围后复测NVML和目标环境CUDA；不阻塞CPU上的环境设计 |
| R-08 | 接入/预热/双门控及F0—F7异常整run停止已实测通过；协方差仍未知 | simulation_engineer | 保持未知质量，后续补可用协方差来源，不直接改名原始话题 |
| R-09 | SIM-00B入口已规避旧启动器：独立PID/完整日志及清理实测通过 | integration_engineer | 本入口范围已关闭；后续启动装配保持相同进程保护要求 |
| R-10（已关闭） | 桥接32位微秒窄化的前置修复、独立候选和跨边界持续运行已完成；实时记录、bag回读及清理对账通过 | simulation_engineer | 2026-10-05 [SIM-01D](../experiments/2026-10-05-sim01d-continuity.md)满足至少40分钟有效持续性和边界checker；不并入SIM-SPEED-01关闭 |
| R-11 | SIM00B-INIT-01已应用，初始化/消息回归、完整构建及静止遥测通过 | simulation_engineer | 当前独立SITL入口范围已关闭；不代表全部HIL/串口路径均已审计 |
| R-12 | 零时长与非零扫描训练fixture的ROS图/私有JSON记录、离线PointCloud2受限适配、型号时间合同、设备记录审计及T-14可选镜像已验证；真实raw驱动、公共ROS逐点时间、真实标定/大规模监督未验收 | system_architect | [EXP-20261014-008](../experiments/2026-10-14-t14-odom-tf.md)只关闭T-14软件fixture子范围；IFACE-01剩余实机回放、时钟残差、真实协方差、T-13仍待通过，不得关闭Phase 2/3 |
| R-13（已关闭） | SIM-SPEED-01两行修复及九run技术矩阵通过，但一份历史RED派生`scenario-result.json`被同语义重写、mtime改变，未满足方案§6/§7证据保全门禁 | simulation_engineer | 2026-09-17用户明确接受已披露偏差并关闭本风险；保留完整记录、不伪造原时间、不尝试恢复，且不用本处置关闭R-10/SIM-01D |
| R-14（已关闭） | 10-04 fake IR热点ROS短测只检查IR身份/时间和Bundle尺寸/像素数量，旧`passed=true`不能证明像素传输/配对守恒 | sensor_engineer | 2026-10-05 [SENS-IR-01](../experiments/2026-10-05-sens-ir-value-transport.md)独立真实ROS run按同IR sample_id及run/clock/frame对齐100帧原始发布与20个Bundle采用帧，曝光时间/全部像素及热点/背景通过；不关闭PERF-01、SIM-01D或训练监督隔离 |

## 下一步任务

2026-10-26软件整合、可选IMU在线值级短测及[独立JSBSim比力语义对照](../experiments/2026-10-26-phase2-imu-physics-semantics.md)
和2026-10-27[感知失效模式软件ROS门禁](../experiments/2026-10-27-perception-mode-ros-fail-closed.md)
已具各自证据；不要重复运行相同短测充作新交付。下一关口是取得**真实**设备
原始记录审查Radar/IR驱动载荷、安装外参、设备时钟映射和质量来源；如果还需要
PX4/JSBSim同run逐帧物理数值误差，须另设隔离真值导出和对时方案，不用两条
JSBSim run的均值替代。没有设备原始数据时仅开展经确认的独立软件子任务，
不新造真实驱动或宣布完整Phase 2退出。
软件双图分账见[既有记录](../experiments/2026-10-26-phase2-sensor-integration.md)。

2026-10-16 fake Radar值级核对与高度/无回波标签矩阵已完成软件子范围；下一步仍需取得IFACE-01真实设备原始记录、
跨设备时钟映射/误差及质量来源，用只读JSONL工具复核解码合同，同时
保留原始包供真实性复查；SENS-TRAIN-COV-01完整体素覆盖与SENS-TRAIN-COV-02边界
软件fixture子范围已完成，SENS-TRAIN-01仍需真实标定、设备时钟、规模和训练质量证据。
外部输入之前仅开展经确认的
具名fixture，不把未知、过期或无回波写成free，训练LiDAR继续与在线链路隔离。
T-13A在线占位图隔离软件子范围已完成；T-13完整仍需研究后端forward边界审计，不能以
当前占位图运行时图结果代替模型质量或真实部署证据。
地图M1真实输入、同run进程RSS/更新/查询延迟和连续场景门槛按
[待执行矩阵](../docs/M1_INPUT_RESOURCE_GATE_20261015.md)先收集证据；
M1正式通过前不实施M2概率、DEM或科研对照，阶段日期保持原计划。

2026-10-14最新状态：[Local Map纯业务单点查询](../experiments/2026-10-14-local-map-query.md)
及其[ROS单点服务](../experiments/2026-10-14-local-map-query-ros.md)软件子范围已完成：
7项纯业务定向、11项查询/ROS定向、338项全仓轻量测试通过；消息构建和实际ROS
启用/关闭/未配置阈值三种fixture均通过。启用复测包含30次有效查询、5条观测发布、
2次快照和并发只读，端口/Python清理通过；默认`enable_query=false`保持旧链路行为。
首轮连接图检查因ROS仿真时间自动订阅公共`/clock`失败，失败目录保留并已修正图
规则，仍禁止传感器、状态、Odometry、Radar及训练LiDAR订阅。当前关闭固定网格单点
查询软件子范围，不代表滚动窗口、概率融合、模型质量、正式PERF-01或对照试验通过。
下一步为滚动局部地图的具体方案、契约和测试矩阵，实施前仍需另行确认；不参考开题计划
时间，不以硬件缺失为由倒填正式PERF-01或提前对照试验。

后续经用户确认实施[MAP-ROLL-01基础滚动Local Map](../experiments/2026-10-14-local-map-rolling.md)：
可选整格odom移动窗口，以OccupancyObservation自带观测时刻SpatialContext中body位置
定位，旧固定模式仍为默认。10项滚动定向、348项全仓轻量测试通过；独立ROS
滚动fixture有5次快照、7条occupancy、20次查询及清理/图隔离通过，旧三种查询
模式及PERF-01-A旧入口回归通过。首轮ROS fixture身份复用失败及沙箱端口受限
记录保留，修正后重跑通过。此为基础滚动软件子范围，不代表Phase 4整体关闭；
真实机载地图RSS/时延、设备时钟/功耗、正式PERF-01、概率累计、DEM或对照试验
均尚未验证/仍需外部输入。按DEVELOPMENT_PLAN阶段时间执行，对照试验最后开展。

2026-10-14继续推进：[T-14 Odometry/TF兼容镜像](../experiments/2026-10-14-t14-odom-tf.md)
已完成12场景、36组离线记录，35/50/70m/s、偏航、插值、遮挡及无回波均有具名
功能级fixture证据；observed=1.09375%、最大补偿残差3.08461e-7m只是理想小场景
统计，不是传感器精度、感知召回或数据充分性。新矩阵复现并修复同一命中表面的
float64标签索引分裂，40项定向、309项全仓轻量测试及motion/single/multiray
三个实际ROS入口回归通过；失败run与中间版本报告保留。随后偏航/插值接入ROS训练
短测：20组schema 0.2记录、22条状态/clock收据、20个插值回波和20个无回波时间槽
通过独立几何/标签/ROS收据核验；实际run及图审计见[ROS偏航记录](../experiments/2026-10-13-sens-train-yaw-ros.md)。
此结果仍是运动学fixture，不是实机时钟或固定翼动力学验收。T-14随后完成可选Odometry/TF
兼容镜像的ROS fixture验收，下一步转入基础 Local Map 契约与占位链路；真实设备、正式
PERF-01、研究模型质量及对照试验仍不前移。

2026-10-13用户明确无硬件/实测记录，并确认继续独立软件任务：
[非零扫描ROS训练闭环](../experiments/2026-10-13-sens-train-motion-ros.md)已完成，
实际ROS `motion`短测20组记录及两个旧入口回归通过；31项定向、300项全仓轻量
测试通过。首轮XML-RPC超限启动失败保留，配置改为本地读取，纳秒值未截断。
当前可执行下一关口是更多几何/运动场景及训练数据覆盖/补偿误差统计，随后推进
Odometry镜像/唯一TF已在2026-10-14的T-14 fixture中验证；下一步按项目阶段建设基础
Local Map，真实设备和功耗仍为外部输入阻塞，各新增范围仍先评审具体方案。
真实设备记录、标定、跨设备时钟、功耗和正式PERF-01继续记录为外部输入阻塞，
不再作为独立仿真训练路径的前置。研究模型接入和对照试验不前移。
下文保留此前计划及失败历史，不以新子范围通过重写原结论。

2026-10-08优先顺序以[开发计划§4.1](../docs/DEVELOPMENT_PLAN.md)为准：PERF-01
预算边界、manifest与证据数值预检已完成，下一步仍是取得正式平台、IR/Radar配置、20 ms起止端点和采样时钟；
本日三航速大图旧短测因IR生成迟于时钟未闭合，预登记的零噪声生成候选已恢复
三档功能级闭合，但回调到占据P99仍为49.703/49.834/60.720ms；继续按真实收据
定位剩余配对等待与线格式成本，不改严格配对门限，也不把功能通过写成20ms达标；
SENS-IR-01值级门禁与SIM-01D跨边界持续性均已独立通过。下一项按计划推进
SENS-TRAIN-01，但[同场景训练监督与IFACE-01时空契约具体方案](../docs/SENS_TRAIN_01_IMPLEMENTATION_PLAN.md)
在2026-10-08仍待确认；2026-10-10用户确认最小子范围并完成具名fixture、训练专用
LiDAR节点与标签、训练/推理分图的[独立ROS短测](../experiments/2026-10-10-sens-train-01-fixture.md)。
因此下一步聚焦IFACE-01未闭合的真实驱动载荷/时间/定位权威边界和SENS-TRAIN-01多场景
标签质量、非零扫描运动补偿；PERF-01正式输入仍是项目管理第一优先，研究模型接入
及科研对照试验留待上述合同和可复现数据门禁之后。
2026-10-10用户说明正式平台、物理时钟和功耗暂缺：PERF-01正式门禁维持阻塞，
不停用既有预算与证据预检，但本轮执行先转向不依赖设备的[IFACE-01受限
PointCloud2 fixture及双射线训练监督](../experiments/2026-10-10-iface01-sens-train-multiray.md)。
下一独立开发关口为将ARS548/Mid-360字段合同接入真实记录格式审查、设备状态/原始包
记录和公共记录路径；本轮已完成设备时间/接收时间分离的JSON-ready输入审计；功能级标签边界
审计已扩展至遮挡、量程、FOV及三类场景矩阵；
本次已先完成不依赖设备的型号字段合同、非零扫描纯函数合同与审计，但真实设备接口仍需
原始记录、时钟状态和跨设备误差。ALG-01研究接入和科研对照试验不前移，对照试验继续
放在工程数据门禁和接口闭合之后。
当前最小外部输入为：目标平台唯一ID/功耗模式、实际Radar频率与物理时间误差、IR变体/镜头/触发
与时间误差、正式起止端点、设备时钟映射、连续时长及资源/功耗/温度/丢帧证据。输入未到位前
不得填充正式配置、启动长测或将`formal_ready`写成性能通过。
严格拒绝理由、5 ms门限及20 ms目标保持，Phase 1、训练LiDAR和真实融合均未因
10-05功能级值级短测获验收。以下按日期保留原定位、失败与诊断记录。

2026-09-23补齐异步验收边界：历史640×512矩阵分别6/7、10/14通过，整体失败；
包含容量拒绝、IR实际迟到和墙钟过期导致的oracle理由差异，原失败产物保留。
见[EXP-20260922-001补充](../experiments/2026-09-22-perf01a-async.md)。
“高速运动时空一致性基线”的小图功能短测已完成，见
[EXP-20260923-001](../experiments/2026-09-23-perf01a-motion.md)；大图normal功能通过，
但大图recovery严格oracle失败，20ms实时门槛继续阻塞PERF-01。提前配对`exact`
仅对同刻IR和状态有效；不同步/历史位姿偏差仍等40ms。接收锁等待、回调内解码及
缓存/发布已量测；ROS回调前大图反序列化/排队及格网边界量化仍需进一步定位，
不得调宽5ms同步门限或抹去失败记录。

2026-09-23追加[EXP-20260923-002](../experiments/2026-09-23-perf01a-boundary-wire.md)：
按实收Radar点和历史变换的连续odom坐标量化格网，并单独检查真值世界误差，
50m/s的4.25/6.25m边界新ROS短测通过，旧边界失败保留；全仓196项契约通过。
可选真实ROS线格式审计覆盖IR/Bundle的发送serialize、接收deserialize及回调，
70m/s大图normal的exact/deadline功能通过但P99=44.181/79.776ms，
大图recovery的Radar19拒绝理由仍与理想1x oracle不同，整run失败保留。
重复大图recovery再次于Radar19失败；第二次大图deadline出现221条状态已接收、
仅219条发布的末尾排空失败，新失败run亦保留。这仅缩小了承载定位范围，不构成
20ms实时或稳定配对收益验收；下一步先确立状态/clock排空门禁及双时钟oracle边界，
格网合同不得以容差掩盖真实体素漂移。

2026-09-23继续[EXP-20260923-003](../experiments/2026-09-23-perf01a-clock-drain.md)：
runner现在等待真实source clock到达matcher、全部源状态发布且pending清空后才
请求finish；大图deadline在2200ms/221条状态短run验证通过，全仓198项契约通过。
双时钟诊断确认大图recovery Radar19所见旧IR按实际墙钟未过期、理想1x
则已过期，但仍保持原预登记严格oracle失败。两次新增探针参数编码失败run
保留，未抹去EXP-002的末尾状态排空失败。大图修后感知P99=81.030ms仍未达
20ms；新的理由验收政策、长期重现及机载资源继续待定。

2026-09-24按[EXP-20260924-001](../experiments/2026-09-24-perf01a-dual-clock-preflight.md)
预登记并执行70m/s大图normal的AB/BA四个2秒run及recovery一个run；5/5严格
功能通过，均正常清理，但五条感知P99均超20ms。recovery此次IR24在Radar19
决策前墙钟过期，理由与理想oracle一致；09-23旧run在决策后过期且仍保持失败。
诊断加了候选终态/身份和决策覆盖负例，全仓200项契约通过。
双时钟理由政策仅为待确认提案，不能用此次通过替历史失败背书或关闭PERF-01。

2026-09-24按[EXP-20260924-002](../experiments/2026-09-24-perf01a-ir-transport.md)
逐样本归因后，仅评估IR订阅`TCP_NODELAY`单候选：70m/s、640×512
normal/exact四条2秒A/B/B/A严格功能均通过，端到端P99分别为
48.384/53.779/46.431/50.356ms；未在两组都降低至少10%，
**未采纳**，显式诊断选项保持默认关闭。5ms同步、严格oracle和20ms
目标不变；PERF-01的大图到达/发送/锁等待及目标机载承载仍需继续定位。

2026-09-24 [EXP-20260924-003](../experiments/2026-09-24-perf01a-critical-path.md)
对上述四条run开展只读逐样本关键路径复核：各20条采用样本身份闭合；
尾部既有IR晚到/反序列化，也有25-30ms回调后待决定和约27ms Bundle
混合排队区间。下一轮先补齐状态/clock/worker锁与配对就绪的时间证据，
再预登记单点优化；尚未执行该定位run，不能断言单一瓶颈或实时达标。

2026-09-26 [EXP-20260926-001](../experiments/2026-09-26-perf01a-match-trace.md)
完成默认关闭的matcher标量追踪及逐样本只读关联；四条独立2秒run
中首条因IR85实际回调越过截止导致Radar34严格oracle失败并保留，
后三条严格功能通过但P99为60.528/59.226/57.276ms，均超20ms。
终版trace的20条采用样本闭合：Radar22就绪到worker锁21.143ms，
其中另一状态回调持锁20.298ms；Radar32 worker锁内到决定18.228ms。
均为墙钟、尚未区分CPU和调度，下一步先测状态回调和worker内部阶段，
再预登记单点性能候选；不得用新增探针短测宣称实时验收或抹去失败。

2026-09-28按[EXP-20260928-001](../experiments/2026-09-28-perf01a-stage-trace.md)
在默认关闭的追踪中补充分段墙钟/线程CPU，新目录单条70m/s大图
2秒run严格功能通过（20采用/20拒绝，排空和清理通过），
端到端P99=56.002ms，20ms继续失败。长段分别涉及
`matcher.advance`、`matcher.add_state`、Bundle编码/发布和统计发布，
不是可归咎一个阶段的稳定瓶颈；下一步重复诊断后才可预登记
单点优化。双时钟理由oracle仍严格，历史失败产物不变。

2026-09-28按[EXP-20260928-002](../experiments/2026-09-28-perf01a-stage-repeat.md)
完成同配置三条70m/s大图、normal/exact、2秒的独立重复诊断；
每条20采用/20拒绝，严格功能、wire、状态/clock排空、运动地图与
进程清理通过，P99=59.749/49.122/53.014ms，均未达20ms。
最慢三个采用样本中CPU与墙钟同超10ms的stage分别为
`decision.emit`、`matcher.advance`、无，未满足跨run重复判定；
不采纳单点优化或降低门槛。短run仅诊断，SIM-01D及机载承载
仍待独立验收。

2026-09-28 [EXP-20260928-003](../experiments/2026-09-28-perf01a-end-to-end-wait.md)
只读关联上述三条run的60个采用样本，形成大图端到端等待归因表：
IR真实回调与线/业务解码、配对就绪和worker获锁、决定与Bundle发送、
感知接收及占据就绪均按同根样本对齐。最慢样本的长段分别落在
就绪后未解释的worker入锁前间隔、`matcher.advance`、IR反序列化；
另有Bundle传输/排队混合区间和clock/state持锁长段，不能将
不同样本阶段P99相加或归因于单一可重复瓶颈。现有账本不能解释
关键空档，已登记仅在确认范围后执行的默认关闭标量探针及新目录
短测门禁；未运行补测、未选择A/B或修改matcher。严格拒绝理由、
5ms同步与20ms目标不变，PERF-01仍进行中。

2026-09-28按[EXP-20260928-004](../experiments/2026-09-28-perf01a-wait-probe.md)
为默认关闭的追踪补充worker睡眠/醒来与锁内线程CPU缺口，
不改变matcher业务或ROS传输。新目录串行三条70m/s大图
normal/exact、2秒run均严格功能通过（各20采用/20拒绝，
wire/地图/clock及状态排空/资源/清理均通过），P99分别
90.011/47.413/53.940ms，仍超20ms；最慢样本分别体现
IR接收前混合等待、决定后Bundle编码与IR反序列化等不同长段。
决定前>=10ms墙钟及CPU的命名stage仅一条run的
`matcher.advance`满足，未选单点A/B，原始旧run及阈值不变。
探针有开销，尚不能确认机载实时性或纯网络/调度原因。

2026-09-28 [EXP-20260928-005](../experiments/2026-09-28-perf01a-20ms-feasibility.md)
只读复算上述三条新run全部60个采用样本，按Radar实际回调、
IR实际回调、matcher决定、Bundle线序列化、感知回调和占据就绪
组成逐样本互斥时间表。三条run分别20/20样本超过20ms，
各自最快亦为23.155/22.689/22.099ms；43/60个样本仅IR
回调偏移与Bundle线序列化起至感知回调两个互斥区间已超20ms。
这是当前带探针ROS路径的常态预算冲突，非目标平台物理不可达
证明；不同样本分位数不相加，不据此选单点A/B或放宽门槛。
下一步先确认20ms计时边界及目标平台预算，并明确混合区间的
可观察/可控部分；新试验或架构改动另行预登记。

2026-09-29 [EXP-20260929-001](../experiments/2026-09-29-perf01a-budget-boundary.md)
只读核对20ms目标与实际计时：异步诊断测量Radar真实ROS回调到
`occupancy_ready`，不覆盖设备采样到回调、占据发布到订阅者收到；
matcher的`data_age_ns`是仿真时钟域，不能与墙钟时延相加。
现有机载平台为参考估计，真实采样参考点、两个20ms指标的终点
与跨设备时钟误差仍待Technical Lead确认；当前不新增补测、
不选单点A/B或调整matcher。原三条短测的20ms诊断失败结论、
严格拒绝理由和5ms同步门限不变，PERF-01仍进行中。

2026-10-03预登记[EXP-20261003-001](../experiments/2026-10-03-perf01a-endpoint-probe-prereg.md)：
因现有账本仍有未归因区间，下一轮仅补齐输入端点/时钟域标记、worker与state/clock
混合等待、以及occupancy/map下游端点。探针默认关闭，不记录大图，不改变匹配决定、
Bundle格式、严格拒绝理由、5ms同步或20ms目标；P1没有真实设备采样时钟时必须报告缺失，
不得用fixture时间戳补齐；当时仍待Technical Lead确认验收起止点和目标平台，故未执行该预登记短测。

2026-10-03按[EXP-20261003-001](../experiments/2026-10-03-perf01a-endpoint-probe.md)
完成默认关闭的端点/时钟探针三条独立短测：70m/s、640x512 IR、exact、
`--wire-profile --match-trace`，三条严格功能及资源/清理门禁通过，
Radar回调到占据P99为58.745/78.635/53.507ms，仍未达20ms。
占据就绪到MapSnapshot事件增量P99仅2.085/3.314/2.049ms，不能解释主长尾；
输入采样时钟均为unavailable，不能形成物理数据年龄。决定前混合等待、Bundle
发送混合区间和未覆盖间隔仍跨run不重复，未满足A/B采纳条件，不修改matcher。

PERF-01-A已完成分段计时与观察器对照，见
[EXP-20260920-003](../experiments/2026-09-20-perf01a-segmented-timing.md)：134项契约通过，
18个10秒大图对照均200/200闭合、零意外丢帧且清理通过；3个故障回归准确拒绝并恢复。
64KiB基线full/light汇总感知P99为32.376/33.965ms，最大段为bundle发送至感知回调；
像素扫描明显增加观察器CPU，但省略扫描或关闭新增探针均未稳定降低尾延迟。
4MiB读缓冲候选未显示稳定收益，默认保留64KiB；18个20ms诊断全部失败，原结果保留。
上述EXP-003之后，已完成实际线格式细分、取消大图旁路订阅对照、进程树CPU/RSS及
单候选复测，详见EXP-004。编解码存在明显实际CPU成本；NumPy候选未达采纳条件，
标准解码和20ms目标保持。独立传感器发布/有界匹配缓存已按
[EXP-20260922-001](../experiments/2026-09-22-perf01a-async.md)完成；航速功能级短测
已另按EXP-20260923-001执行，机载GPU/NPU/功耗仍独立待验。静止短时复现：
`bash ros_ws/sim01_env.sh python ros_ws/perf01a_run.py --duration-s 8`。
09-18历史零事件派生报告被重建的偏差已记录，尚无用户处置，不据本次技术通过消除该事实。

PERF-01仍是第一优先级。35/50/70m/s航速点、ARS548参考Radar和mid360训练监督参考已于
09-18确认；Jetson Orin NX/25 W、Micro III Lite 640和低空场景已按常用工程估计填入，
仍需确认镜头/同步、平台可用性和实测阈值，预算不能写成性能验收通过。
SIM-SPEED-01短窗技术矩阵通过不构成这些指标的验证。2026-09-17用户已接受
证据保全偏差，SIM-SPEED-01与SIM-01C已正式关闭；已披露历史继续保留，
不伪造原时间、不尝试恢复。
继续保持原采样时间、未知质量、Conda默认与仅清理本次PID的规则，不放宽业务超时。
R-10的桥接32位微秒前置修复已于09-18完成：HIL_SENSOR/HIL_GPS四个边界值的C++ RED/GREEN、
独立候选构建和短回归通过；专用SIM-01D运行器、配置、checker及契约单测已补齐。2026-10-05
独立端口/PID前检通过，实际长测有效跨度`2400004000000 ns`并跨越边界，bag回读、排空和清理
对账通过，R-10关闭。正式Phase 1基线仍待PERF-01与环境恢复完整验收。本次35—70m/s仅验证
已知真值功能级地图更新；尚未验证真实Radar—IR融合感知或训练监督LiDAR。

## 开发入口与证据

- 规则：[根AGENTS](../AGENTS.md) → [系统架构](../docs/SYSTEM_ARCHITECTURE.md) → 涉及目录AGENTS。
- 接口：[数据格式](../docs/DATA_FORMAT.md)、[传感器连接](../docs/SENSOR_INTERFACE.md)、[坐标](../docs/COORDINATE_SYSTEM.md)。
- 决定：[DECISION_LOG](../docs/DECISION_LOG.md)；验证：[EXPERIMENT_LOG](../docs/EXPERIMENT_LOG.md)。
- 研究来源：[algorithms/README](../algorithms/README.md)。
- 本机环境与缺项：[ENVIRONMENT_INVENTORY](../configs/ENVIRONMENT_INVENTORY.md)。
- 下一阶段执行方案：[SIMULATION_VALIDATION_PLAN](../docs/SIMULATION_VALIDATION_PLAN.md)。

## 更新规则

每次开发结束更新实际完成、验证边界、风险和下一步；每周复核进度和待决项。
完成项必须链接证据，未执行写未执行；不将日期到达或文档创建视为运行验收通过。
