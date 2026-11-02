# 工程决策记录

版本：v0.1；更新日期：2026-10-13；维护角色：system_architect / Technical Lead。
状态：记录初始化、候选与构建决定；正式运行选型仍待验收。

## 1. 使用方式

状态为proposed、accepted、superseded、rejected。accepted表示设计决定，不表示运行
通过。重大接口变化需说明影响的生产者/消费者、迁移与验证，再按根AGENTS确认。
旧记录保留，被替代时链接新记录；不能静默改写历史决定。

## 2. 已采用决定

### ADR-001 双仓与研究组件边界

- 日期：2026-09-11；状态：accepted；责任角色：Technical Lead。
- 依据：用户提供独立研究源码路径，并确认先建立UAV-FusionMap工程框架。
- 决定：保留同级独立仓库；algorithms登记来源，perception负责感知适配，mapping
  独立评估研究地图代码。系统启动支持无模型和占位模式。
- 影响：研究文件布局和依赖不成为系统公共接口，不直接修改研究仓库。
- 验证：本次路径/源码只读检查；未来后端通过独立小样本质量和性能验收。
- 证据：[组件登记](../algorithms/README.md)。

### ADR-002 五层架构与ROS装配边界

- 日期：2026-09-11；状态：accepted；责任角色：system_architect。
- 依据：用户要求Simulation、Sensor、Perception、Mapping、Application分层及禁止跨层调用。
- 决定：业务数据沿相邻层公开契约传递；ROS仅负责承载、节点包装、启动与记录。
  状态与变换上下文随SensorBundle和OccupancyObservation传递给mapping。
- 影响：mapping不读取Radar/IR原始数据，application只读地图公开接口。
- 验证：文档生产消费表一致性；未来T-07检查依赖和运行连接。
- 证据：[系统架构](SYSTEM_ARCHITECTURE.md)。

### ADR-003 时间、坐标和未知区域属于必备契约

- 日期：2026-09-11；状态：accepted；责任角色：system_architect。
- 依据：高速飞行需要明确观测时刻、坐标和质量；用户禁止默认坐标相同。
- 决定：采用明确时钟域的采集时间、同观测时刻变换、XYZ网格和独立observed_mask；
  质量缺失标不可用。新run_id隔离时钟重置前后地图。
- 影响：适配器不能用当前位姿、通道猜测或全自由空间掩盖输入缺失。
- 验证：T-02至T-05；本次仅完成逻辑规范和文档检查。
- 证据：[数据契约](DATA_FORMAT.md)、[坐标规范](COORDINATE_SYSTEM.md)。

### ADR-004 先建立基础地图再接入高级能力

- 日期：2026-09-11；状态：accepted；责任角色：mapping_engineer。
- 依据：用户规定Local Map、概率、不确定性、DEM的顺序及阶段目标。
- 决定：Local Map → Probability → Uncertainty → Scene Map → DEM逐项验收。
  DEM通过显式地形先验接口接入；自主控制和实飞另行定义验证范围。
- 影响：研究地图中已有高级方法不构成跳过基础验收的理由。
- 验证：DEVELOPMENT_PLAN的M1—M5与T-08/T-09/T-12。

### ADR-005 本轮仅落地管理文件与目录边界

- 日期：2026-09-11；状态：accepted；责任角色：Technical Lead。
- 依据：用户在只读分析和解释后明确指示“按你说的做”。
- 决定：保留原有根规范并补充流程，建立各目录AGENTS、七份设计文档和PROJECT_STATUS，
  新增application/tests边界及ros_ws/src占位，校正README和源码路径说明。
- 影响：不写算法或运行节点，不安装大型依赖，不删除/移动已有文件。
- 版本操作：使用feature/engineering-initialization；未执行提交、推送或研究仓库修改。
- 验证：[EXP-20260911-001](EXPERIMENT_LOG.md)。

### ADR-006 Phase 1优先验证候选与接入路线

- 日期：2026-09-11；状态：accepted（验证方案决定，正式运行基线未验收）；责任角色：system_architect。
- 依据：用户在ENV-01后要求“下一步”，继续已预告的ENV-02方案工作；选择依据为现有
  Noetic/PX4资产、桥接真实入口及本轮依赖模拟，具体证据见方案。
- 决定：优先测试Ubuntu 20.04.6、Noetic、PX4 v1.13.3、JSBSim 1.1.13和MAVROS 1.20.1；
  采用独立JSBSim可执行程序、MAVROS传输、simulation状态/时钟接入及sensors转换。
- 取舍：保留终端双ROS；本阶段不同时实现Foxy。Humble/Jazzy为独立替代路线，在
  2026-10-15及2027-01-15复审维护与迁移条件。
- 接口：既有AircraftState及五层职责不变；原始ODOMETRY保留源时间/NED/FRD，
  HIGHRES_IMU采样时钟需专门接入。MAVROS默认Unix时钟不能冒充项目仿真经过时间。
- 保护与范围：独立源码/构建/运行目录、按本次PID管理停止、保留stdout/stderr；
  本轮只写文档，不授权安装、驱动修复、外部代码修复或实际仿真运行。
- 条件：模拟解析通过不代表依赖已取得或运行兼容。桥接32位微秒参数须在持续性验收
  前处理；首次短测上限600秒仿真/900秒墙上时间，较早者生效，不据短测关闭风险。
- 验证：[方案](SIMULATION_VALIDATION_PLAN.md)、
  [EXP-20260911-003](../experiments/2026-09-11-simulation-plan-review.md)；运行按SIM-00/SIM-01另验。
- 与ADR-P001关系：已决定优先验证路线；正式组合只有在依赖锁定、运行和恢复验证后
  才能冻结。ADR-P001保留该未完成部分，不把accepted解释为已兼容。

### ADR-007 SIM-00A采用项目依赖前缀与独立构建

- 日期：2026-09-12；状态：accepted（构建方式与证据，运行组合仍待验收）；责任角色：simulation_engineer。
- 依据：用户在ENV-02预告SIM-00A后继续任务，授权最小依赖准备和独立构建；原系统
  Noetic及开发工具可复用，新增依赖可在项目目录解包并通过链接检查。
- 决定：先建立.runtime忽略/CATKIN_IGNORE和保存规则，再取得JSBSim开发包、7个APT
  包及EGM96-5；仅解包到项目前缀，不执行系统安装或改动终端双ROS选择。
- 源码：固定PX4及子模块逐仓独立复制，不修改原PX4或研究仓库。桥接使用显式
  JSBSim静态库和MAVLink头文件路径；首次include路径错误仅修正CMake参数。
- 环境：独立Bash子进程使用Noetic，隔离父环境的ROS/Conda变量；仍读取系统库和
  Python用户目录，完整环境恢复尚未验证，不声明为完整容器或异机备份。
- 结果：PX4与桥接构建通过，动态库解析、包发现、geoid读取和环境隔离通过；桥接
  15条可能未初始化警告登记R-11。未启动仿真或ROS节点，未修改公共业务接口。
- 保存：提交范围/忽略/保存规则已落地；首次提交、第二份副本及恢复证据未完成，
  ENV-03与ADR-P006保留未完成部分。依赖结束支持后的恢复风险没有因此关闭。
- 证据：[构建说明](../simulation/BUILD_SIM00A.md)、
  [EXP-20260912-001](../experiments/2026-09-12-sim00a-build.md)。
- 后续：SIM-00B先核查警告和启动条件，再按既定门槛验证；ADR-P001继续等待运行及恢复验收。

### ADR-008 应用初始化修复并采用独立静止遥测装配

- 日期：2026-09-12；状态：accepted；主责任角色：simulation_engineer。
- 依据：用户对SIM00B-INIT-01应用及回归后继续120秒静止遥测明确“确认”。
- 实施：仅在项目内桥接副本应用2文件5处声明的补丁，保留原外部源码及旧构建；
  新目录完整构建、消息回归通过。补齐解包ROS前缀.catkin标记及MAVROS内部版本查询
  所需command插件，未安装到系统目录或改变双ROS选择。
- 装配：独立ROS master11321、Rascal HEADLESS、PID/日志/rootfs及配置快照；只发送
  消息流配置，未发送解锁、起飞、航点或offboard指令。
- 验证：120.056秒有效采样窗口，IMU 6051条/50Hz、心跳121条、ODOMETRY 2407条；
  未解锁，落盘线格式计数对应，本次进程/端口清理通过。失败运行保留。
- 限制：静止遥测不替代SIM-01接口、回放、坐标/时钟及长期运行；本机Python common
  的未知ID8/411保留原始字节与MAVROS framing证据，不声称独立解码通过。
- 关系：ADR-P007正式应用待决部分由本决定关闭；ADR-P001仍等待Phase 1及恢复验收。
- 证据：[EXP-20260912-003](../experiments/2026-09-12-sim00b-init-and-smoke.md)、
  [RUN_SIM00B](../simulation/RUN_SIM00B.md)。

## 3. 待决事项

| 编号 | 问题与候选 | 主责任角色 | 目标日期 | 阻塞范围与所需证据 |
| --- | --- | --- | --- | --- |
| ADR-P001 | 正式ROS/PX4/JSBSim/桥接运行组合冻结 | system_architect | 2026-10-15（候选方案09-11完成） | ADR-006决定优先验证路线；仍需SIM-00/SIM-01及环境恢复证据 |
| ADR-P002 | 航速、场景、算力、量程、同步/时延预算 | Technical Lead | 2026-09-20 | 阻塞性能验收定义；需用户场景约束与资源事实 |
| ADR-P003 | Radar/IR参数及场景几何/热属性资产格式 | sensor_engineer | 2026-10-15 | 阻塞功能级传感器实现定版；需已知场景样例与字段检查 |
| ADR-P004 | 研究后端运行方式、权重和输入协议基线 | perception_engineer | 2026-11-10 | 阻塞research模式验收；需入口修复状态、有效权重及小样本证据 |
| ADR-P005 | 地图阈值、老化、覆盖、分辨率及定位跳变策略 | mapping_engineer | 2026-12-15 | 阻塞正式地图验收；需已确认性能预算和已知场景测试 |
| ADR-P006 | 提交基线、第二份资产副本及恢复安排 | project_manager | 2026-09-20 | 09-12提交范围/流转/忽略/保存规则已落地；第二副本位置与范围待定，实际提交另按授权，恢复10-15前验收 |
| ADR-P007（已关闭） | SIM00B-INIT-01桥接初始化补丁正式应用范围 | simulation_engineer | 2026-09-12完成 | 用户确认后按ADR-008实施；独立重建、消息回归及静止遥测通过，历史提案保留如下 |
| ADR-P008（已关闭） | SIM-01A ROS编码、内部状态话题、虚拟坐标原点及预热门控 | system_architect | 2026-10-01前 | 09-14用户确认按ADR-009实施；历史评审及提案保留 |

上述待决项不阻塞文档初始化，但不能绕过其条件宣布相应运行阶段完成。

### ADR-P006补充处置：2026-09-18不执行独立归档

- 状态：proposed继续开放；责任角色：project_manager。
- 用户决定：先建立当前Git提交，随后继续PERF-01-A、SIM-01D及其后可执行工作；明确
  不授权重新挂载外部介质、不授权复制或归档仓库与`.runtime`。
- 影响：本轮不执行第二份独立副本和恢复检查；Git提交只保护纳入版本管理的工程文件，
  不等同于保护`.runtime`、第三方bridge dirty源码、构建产物或运行证据。
- 风险：继续实施接受本机单副本风险，R-06与ENV-03保持未关闭；任何删除、清理、磁盘
  操作或未来归档仍须独立授权。

### ADR-P002补充依据：2026-09-18 PERF-01输入确认

- 状态：proposed；责任角色：Technical Lead。
- 已确认：PERF-01采用35、50、70 m/s三个验收航速点；4D Radar参考型号为ARS548，
  视场120°×30°（水平×垂直）、有效距离300 m；
  LiDAR参考型号为mid360，但仅用于`training_data_generation`监督覆盖，不进入在线
  SensorBundle、感知forward、定位或mapping。
- 尚未确认：目标机载CPU/GPU/NPU、内存、功耗、IR型号及参数、飞行高度、障碍物尺寸/距离、
  前视探测距离、转弯/角运动范围、地图分辨率/覆盖和端到端时延阈值。
- 补充估计：先以Jetson Orin NX 16GB/25 W、Micro III Lite 640（640×512、50 Hz、9.1 mm
  临时镜头约48.1°×38.4°）、50 m AGL低空场景、250 m转弯半径、0.5 m地图/20 Hz/100 ms
  老化作为工程预算基线；这些值不是已采购、已标定或已验收事实。
- 决定：先交付参数化预算与计时点设计；在估计值经用户确认和实测前，不启动长时间高速性能验收，
  不用当前开发机规格或参考设备名义代替机载验证。
- 证据：[PERF-01预算](PERF01_BUDGET.md)、[参数配置](../configs/perf01_budget.yaml)、
  [参数冻结记录](../experiments/2026-09-18-perf01-parameter-freeze.md)。

### ADR-P007补充依据：2026-09-12 SIM-00B前置核查

- 状态：proposed。模式开关在实际Load/发送条件前没有初始化；原构造探针在0xA5
  预填存储上保持未初始化表示，候选默认false后通过。消息结构值初始化同时消除
  本翻译单元15条可能未初始化警告；未将编译结果解释为有效遥测。
- 提案：[SIM00B-INIT-01.patch](../simulation/patches/SIM00B-INIT-01.patch)，仅涉及
  本项目.runtime/src桥接副本的2个文件5处声明；原PX4与研究仓库保留。
- 备选：直接运行旧构建不能保证确定初态；更换整套协议/桥接版本会扩大兼容性
  验证范围。建议先做有复现证据的最小初始化修复，时间/节奏问题保持独立任务。
- 审查副本编译及构造测试通过，正式构建源码未改；需按根AGENTS第11.3条第5项
  确认扩展范围后应用、独立完整重建并验证消息有效掩码，再开展SIM-00B。
- 证据：[EXP-20260912-002](../experiments/2026-09-12-sim00b-preflight.md)。

2026-09-11说明：将ADR-P001拆清为ENV-02的候选/维护方案决定与Phase 1的正式运行
基线冻结；原09-20方案目标已提前交付，运行冻结截止与Phase 1出口10-15一致。
没有删除运行验证或改变其门槛，历史ENV-01补充依据保留如下。

### ADR-P001补充依据：2026-09-11 ENV-01

- 状态仍为proposed，本次补充事实不代表选定ROS或批准安装、升级和运行。
- 用户确认交互终端的选择为Foxy(1)/Noetic(2)，本机shell文件与之相符；两版本在独立
  子进程中的环境加载/入口发现检查通过。工具会话未选ROS不作为环境配置故障。
- 既有catkin工作区配置指向Noetic；PX4 v1.13.3和其JSBSim桥接源码已存在，桥接采用
  ROS 1/catkin及MAVROS依赖。Noetic因此属于现有资产复用候选，兼容性尚未运行验证。
- 所查范围未发现JSBSim开发安装或MAVROS，桥接构建目录为空；现有ROS包装的状态
  发布回调仍TODO，需要明确AircraftState和时钟来源。
- GPU沙箱外查询报NVML驱动/库版本不一致；不能从CUDA安装目录推断运行可用。
- 后续选择需说明两个ROS版本的维护期限、独立构建与产物位置，保留现有研究环境和
  用户终端选择机制；Foxy路线必须单独评估ROS 2连接方式。
- 证据：[环境清单](../configs/ENVIRONMENT_INVENTORY.md)、
  [EXP-20260911-002](../experiments/2026-09-11-environment-inventory.md)。

### ADR-P008补充依据：2026-09-14多agent评审

用户授权调用对应子agents推进下一步，三个agents已只读分析并复核
[SIM-01A提案](SIM01A_IMPLEMENTATION_PLAN.md)。建议共用AircraftState、四消息/两节点，
源时钟与状态处理归simulation，虚拟ENU/FLU适配归sensors，新增话题只供sensors内部。
历史原始记录证实启动两次reset及2130次状态先于覆盖时钟到达；需准备期稳定观察、
ACTIVE后终止和接收端门控，完整协方差仍不可用。终止事件必须使用独立身份并传播失效。

状态为proposed：ROS字段编码、新话题、虚拟原点和预热对原fail-stop的细化均需确认。
暂不新增TF、IMU、地图消息或独立安装打包，不在实施时隐式扩大范围。
记录见[EXP-20260914-001](../experiments/2026-09-14-sim01a-agent-review.md)。

## 4. 环境选型的已知外部约束

- ROS官方说明ROS1最后一个版本Noetic已于2025-05-31结束支持。选择继续使用时应记录
  环境保存、维护责任和升级边界，不能仅凭当前catkin目录名推断已选版本。
  来源：[ROS官方生命周期说明](https://www.ros.org/blog/noetic-eol/)。
- ROS 2 Foxy已于2023-06-20结束支持，不能仅因其属于ROS 2就作为覆盖2027年3月的
  受支持版本。来源：[ROS官方维护者最终发布公告](https://discourse.ros.org/t/new-packages-for-foxy-fitzroy-2023-06-20/32039)。
- PX4官方将JSBSim集成标为社区维护，说明其与当前PX4版本的兼容性需要确认。
  因此必须验证具体版本组合，不能直接将文档命令标为本机可用。
  来源：[PX4 JSBSim文档](https://docs.px4.io/main/en/sim_jsbsim/)。
- 对本机v1.13.3还应参考[PX4 v1.13 JSBSim文档](https://docs.px4.io/v1.13/en/simulation/jsbsim)：
  文档示例测试环境为Ubuntu 18.04，ROS桥接依赖MAVROS；本机Ubuntu 20.04组合需实际验证。
- 来源核查日期：2026-09-11。以后选择或升级版本时重新核对。

## 5. 新决策模板

```text
编号 / 标题：
日期 / 状态 / 主责任角色：
问题和证据：
备选方案及取舍：
采用决定及确认依据：
影响模块、生产者和消费者：
兼容与迁移方式：
验证方式及实际结果：
替代/被替代记录：
```

## ADR-009 SIM-01A实施确认与默认Conda Python

日期：2026-09-14；状态：accepted；主责任：Technical Lead。
确认依据：用户“确认，默认所有python环境使用conda环境 Radar-Diffusion”。
采用[SIM-01A提案](SIM01A_IMPLEMENTATION_PLAN.md)的四消息、两层节点、内部状态话题、
虚拟原点及PREPARING/ACTIVE/FAULT规则；关闭ADR-P008，保持Phase 1退出条件。

Python工具、单元测试、catkin消息生成、ROS Python节点、观察器、roscore/rosmaster及
roslaunch统一使用`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`（3.8.12）。
Noetic提供ROS库；缺少的pymavlink 2.4.49及netifaces 0.10.4从现有安装复制到项目
.runtime/deps/python-radar，来源有清单；不修改Conda、系统ROS或终端菜单。
roslaunch通过项目rosmaster shell入口显式选择Conda，避免系统shebang隐式改解释器。
历史SIM-00A/B命令和产物保留原环境记录；该决定控制后续新开发默认值。

业务契约不新增必需字段；纳秒、帧、未知质量和终止身份按DATA_FORMAT保持。
FAULT节点留活发送终止，监督器收到终止或致命诊断后停止本run并清理本次进程组。
本轮仅SIM-01A轻量验证，300秒bag/回放、暂停倍速、R-10修复和40分钟另验。

## ADR-P009 SIM-01B记录时间域、发布审计与独立回放

日期：2026-09-14；状态：proposed；主责任：system_architect。
依据：三个对应子agents再次分析及二次评审，[具体提案](SIM01B_RECORDING_REPLAY_PLAN.md)
已写入；用户要求推进下一步，本轮先交付具体方案，尚未确认B代码及运行。

提案：LIVE一次300源秒记录，B1成品原样与B2新sensors复算分别在独立Master验收；
仅原clock、保留原业务run与采样身份，bag索引采用独立接收单调经过时间。
两层薄节点默认关闭审计、B启用publish调用台账，核对数量/身份次数/序列/全部字段；
源正常停后sensors排空，再封存记录/重读bag，不能同步杀死两层或造terminal结束。

前置环境修复隔离任务参数，固定Noetic路径与元变量替代隐式系统Python helper，
Conda默认保持ADR-009；已有依赖无需新增安装，CLI参数故障按RED/GREEN验证。
保持业务消息、状态机/坐标库和A默认行为；新的传输审计参数及B运行范围需用户确认。
探针和风险见[EXP-20260914-003](../experiments/2026-09-14-sim01b-agent-review.md)。
尚未据此接受实现、升级系统或关闭Phase 1、R-10、ENV-03恢复风险。

## ADR-010 SIM-01B实施确认

登记日期：2026-09-15；状态：accepted；主责任：Technical Lead。
确认依据：用户针对[SIM-01B具体方案](SIM01B_RECORDING_REPLAY_PLAN.md)回复“确认”，
随后要求“继续”。接受ADR-P009的独立LIVE/B1/B2、发布调用审计、单调接收记录时间域、
分阶段排空及固定Noetic/Conda环境前置修复。原提案保留实施前证据。

业务消息、simulation/sensors纯业务库、PX4/bridge与研究仓库不在修改范围内。
三项会话及各自关闭、消息/身份/字段对账分别通过后才验收B；本范围连续完成不重复确认。
09-15结果：环境RED/GREEN、增量catkin、73项单元/契约和11项ROS fixture通过；
LIVE连续valid 300.008001秒，B1逐字节及B2全新sensors复算分别通过，关闭/清理均通过。
原生player私有namespace避开内部clock队列1复用；不生成额外clock。Conda exec传播
原生真实退出码，EOF注销仅给予2墙秒正常退出交接，仍核对全部序列与排空，不豁免缺帧。
三次失败B1不改写，详情见[EXP-20260915-001](../experiments/2026-09-15-sim01b-implementation.md)。
公共话题/消息/时间与质量不变；Phase 1、R-10及ENV-03退出门槛保持原计划。

## ADR-P011 SIM-01C异常矩阵与倍速分界

日期：2026-09-15；实施更新：2026-09-16；状态：accepted（已实施；2026-09-17正式关闭）；
主责任：integration_engineer。
依据：[SIM-01C具体方案](SIM01C_FAULT_CLOCK_PLAN.md)和
[前置核查](../experiments/2026-09-15-sim01c-preflight.md)。

提案把启动等待、IMU/ODOMETRY独立断流、全暂停恢复、IMU回退、ACTIVE estimator
reset、sensors本地clock回退及新run恢复分为F0—F7。预期故障以唯一原因、terminal
传播、terminal后零valid、ERROR触发监督清理及端口/PID释放共同验收；每项新run。

倍速使用实际PX4/JSBSim/MAVROS测源clock与单调墙钟，不用rosbag参数代替。静态发现
0.5被bridge int getter截断及单步耗时方向错误；先保存当前二进制RED，修复另提
SIM-SPEED-01，不在本提案中改bridge。40分钟边界仍属R-10/SIM-01D。

确认依据：用户明确要求调用对应子agents完成SIM-01C并继续，接受第一批场景监督、
测试工具、F0—F7及当前bridge 0.5/2倍现状测量；不授权修改bridge、PX4、公共消息或
业务状态机。该确认替代“具体第一批实施范围须确认后执行”的09-15前置状态。

修复前实施结果：F0—F7在独立run中通过实际故障注入、唯一终止原因、terminal后零valid、
ERROR触发监督清理及新run恢复。2倍最终三次实际因子为1.6982、1.6945、1.6896，低于
1.7下限；0.5倍因getter截断为0而自由运行，一次20源秒窗口测得71.4543倍，随后发生
`estimator_reset` terminal。因此只接受异常矩阵实现与证据，不接受倍速能力或整个
SIM-01C/Phase 1完成声明。详见[运行说明](../simulation/RUN_SIM01C.md)和
[实施记录](../experiments/2026-09-16-sim01c-implementation.md)。

后续决定：把getter类型、单步耗时方向和2倍不足归入独立SIM-SPEED-01，先形成最小
修改、恢复和验证方案并重新确认，不借本决定修改第三方源码。PERF-01优先级和09-20
门禁不降低；40分钟边界仍属R-10/SIM-01D。失败运行保留且不得被修复后结果覆盖。
该后续项现已按accepted的ADR-P013实施，短窗倍速技术矩阵通过；但ADR-P013存在一项
历史证据保全偏差。2026-09-17用户明确接受该偏差并要求保留完整记录、
不伪造原时间且不尝试恢复，故SIM-01C正式关闭。上述修复前RED仍保持原
失败结论，也不据此关闭SIM-01D、PERF-01、Phase 1或高速地图测试。

## ADR-012 定位权威、统一传感器适配与训练专用LiDAR监督

日期：2026-09-16；状态：accepted（设计边界，尚未实现）；主责任：system_architect。
确认依据：用户在现有ROS规划讨论后明确要求修改计划和AGENTS，并确认LiDAR数据只用于
配合fake Radar/IR生成训练监督，其他运行阶段不使用。

决定：保留五层主链和已验证的`/uav/sensors/state` AircraftState，不新建独立
localization目录。把连续odom、状态来源/reset/质量和唯一odom→base_link发布者定义为
定位权威职责；未来可提供nav_msgs/Odometry兼容镜像，但不得用其替代run/clock/sample、
来源和失效语义，mapping不直接订阅最新Odometry。

Radar/IR驱动可用PointCloud2/Image承载原始数据，sensors设备适配器转换为设备无关的
RadarFrame/InfraredFrame；模型特定voxel、归一化和张量布局归perception。SensorBundle
仍是运行时感知唯一入口，只包含Radar、IR、可选IMU、状态、标定和SpatialContext。

新增`training_data_generation`设计配置：fake Radar/IR作为模型输入，fake LiDAR只生成
独立监督点云、occupancy target和observed mask。LiDAR及其派生标签不得进入SensorBundle、
Radar+IR模型forward、定位或mapping；`inference`配置不得启动或依赖fake LiDAR。
`training_lidar`监督坐标与历史`model_lidar`逻辑参考系分别登记，在线不要求LiDAR硬件。

影响：更新根/模块规范、系统架构、数据/坐标/连接契约、阶段计划、项目状态和研究登记；
不修改现有消息、节点、话题、配置或研究仓库，不声称fake传感器、Odometry镜像或训练
标签节点已经实现。实现前需分别提出IFACE-01与SENS-TRAIN-01具体方案。

验证：本轮仅做文档链接、术语、生产消费和禁止路径一致性检查。后续T-13/T-14必须
检查训练/推理ROS图、标签泄漏、观测域、时间外参、唯一TF和历史状态插值。

## ADR-P013 SIM-SPEED-01最小修复与九run验收

日期：2026-09-16；处置更新：2026-09-17；状态：accepted（已实施；已正式关闭）；
主责任：simulation_engineer。
依据：[具体实施方案](SIM_SPEED_01_IMPLEMENTATION_PLAN.md)和
[只读前置核查](../experiments/2026-09-16-sim-speed01-preflight.md)；用户确认该具体方案后
授权按锁定范围实施。

问题与证据：SIM-01C保留的RED已确认两个源码根因：float倍速经int getter返回时使
0.5截断为0；单步elapsed使用反向相减，使节奏补偿方向错误。提案阶段尚未修改bridge、
构建或运行候选版本；该前置历史保留在EXP-20260916-002，不能用修后结果改写。

决定：只把`configuration_parser.h:62`的`getRealtimeFactor()`返回类型由
`int`改为`float`，并把`jsbsim_bridge.cpp:213`的elapsed由
`step_start_time - step_stop_time`改为`step_stop_time - step_start_time`；要求在项目内
独立构建/运行目录生成候选，并不覆盖init01二进制、失败run或前置核查证据。公共消息、
业务状态机、PX4和研究仓库均不纳入该两行生产修改。两行生产修改按决定实施完成。

候选身份：`.runtime/build/jsbsim-bridge-speed01/jsbsim_bridge`，71,059,096字节，
SHA-256为`d846038cddbd64859e1d48e414d994248c70c408ec3552d39cb472e2beb63ddf`。
真实suite `sim01c-suite-20260916T143604636221`和matrix
`sim-speed01-matrix-20260916T143604603286`按预注册顺序执行0.5、1、2倍各三次；九run
全部`COMPLETE`，0.5倍实测0.492476—0.492647、1倍0.971738—0.972527、2倍
1.899797—1.909010，逐run零terminal且清理通过。实现与运行证据见
[EXP-20260916-003](../experiments/2026-09-16-sim-speed01-implementation.md)。

流程偏差与正式门禁：checker兼容性复核曾对历史目录
`.runtime/runs/sim01c-suite-20260916T085553794733/speed-2`调用会写结果的CLI，使其
`scenario-result.json`以相同RED语义重写并改变mtime；`manifest.json`、
`speed-result.json`及原始观测未改。技术矩阵结论不受影响，但这不满足方案§6/§7的
“历史run未改写”保护条件，且方案规定任一门禁失败保持阻塞。因当时未取得偏差处置，
2026-09-16按方案暂记阻塞；该描述保留为当时的门禁状态。2026-09-17用户明确接受该已披露偏差：
保留完整记录，不伪造原时间，不尝试恢复`scenario-result.json`或其mtime。
因此本决定继续保持accepted且已实施，SIM-SPEED-01与SIM-01C正式关闭，
R-13关闭。该处置不改变修复前RED结论，也不将历史文件声明为字节未改或原mtime。

边界：32位微秒约35.8分钟越界仍属于R-10/SIM-01D，至少40分钟跨边界持续性不得
混入本任务或被短窗九run关闭。PERF-01的09-20预算门禁及其35—70m/s航速、目标算力
和时空预算仍为第一优先级。本决定接受SIM-SPEED-01实施范围及技术矩阵结果，不越过
上述证据保全门禁，也不代表SIM-01D、完整Phase 1、35—70m/s地图更新、Radar—IR感知
或训练监督LiDAR已经验证。

## ADR-P014 PERF-01-A功能级闭环实施

日期：2026-09-20；状态：已实施（短时技术验证）；主责任：Technical Lead。
依据：用户09-18授权先提交Git、继续除归档外的任务，并在09-20继续实施。

决定：使用独立静止source fixture和Radar/IR占位输入建立最小SensorBundle→Occupancy→
MapSnapshot闭环，按DATA_FORMAT §12落实受限ROS编码。业务仍各归其层；simulation不再
导入sensors fixture，地图只消费Occupancy及context。新消息无历史已验收消费者，统一
重新生成ROS消息后运行；不修改既有AircraftState编码。暂不宣称已实现完整设备合同。

ROS运行器统一管理观察窗口、连接就绪、固定样本数、排空和清理；本机monotonic只用于
性能事件，业务采样纳秒保留。丢帧以未闭合根样本计算；禁止以重复拒绝抵消其他样本丢失。
map采用严格递增时间与最近样本去重、固定odom格网、有限稀疏cell；完整滚动窗口后续另验。

验证：122项契约通过；两次160样本短时闭环通过，最终运行800事件和六路各160消息、
进程/端口清理通过。具体负载和命令见[实施记录](../experiments/2026-09-20-perf01a-integration.md)。
本次完成不关闭PERF-01、SIM-01D或ENV-03；09-18旧零事件报告被重建的偏差已披露，
尚无用户接受处置，不用本次新运行结果替代该处置。

2026-09-20后续实施：新增完整IR和固定同步故障profile，ROS字段不变。
实际大图run出现40→39样本，改用已有StateClockGate保留多条等待clock状态，容量/超时
门槛不变；IR像素独立容器复制替代逐元素deepcopy。时延起点扩为fixture生成开始，
报告注明计时范围，场景功能通过与20ms诊断分别输出。六个短场景功能检查通过，
完整IR感知P99=30.376ms仍超目标；见[EXP-20260920-002](../experiments/2026-09-20-perf01a-load-faults.md)。

2026-09-20分段与对照后续：依据用户明确要求，沿用PerfEvent兼容增加20个可选计时阶段，
各业务发布后发送已捕获的单调时间区间，业务消息字段和架构不变。full/light维持相同
订阅、完整身份/计数/时间与丢帧检查，仅full遍历像素；报告明确light的像素校验缺项。
publish开始至回调只能解释为消息承载混合区间，不能称为纯网络延迟；逐样本连续分解，
不累计嵌套区间或独立P99。最大区间的4MiB读缓冲试调未显示稳定收益，保留64KiB默认。
134项契约和22个短run功能检查通过，但18个正式大图20ms诊断均失败，PERF-01仍进行中。
依据与复现见[EXP-20260920-003](../experiments/2026-09-20-perf01a-segmented-timing.md)。

2026-09-20线格式成本后续：依据用户“按你说的做”，在项目进程内测量真实生成消息
serialize/deserialize，正常退出后以独立小型审计文件核对身份、数量和线格式区间。
不修改ROS系统包、消息字段或算法。新增metadata观察模式明确取消IR/bundle旁路订阅，
独立IR无连接时只验证发布尝试，bundle实际交付由sensor/perception两端核对；所有模式
维持map/occupancy等低载荷检查，不把缺失消费记录当作零丢帧。

整链基础资源采样记录本次进程树CPU/RSS、主机负载与代表CPU频率，活动窗口与采样自身
开销显式记录。第一版高开销硬件轮询矩阵保留为探索结果，第二版正式对照不混用其统计。
单个生成代码NumPy接收候选保持线格式及Python容器，三对端到端降幅中位数0.950%，
低于预登记10%筛选条件，决定不改standard默认，仅保留候选复现入口。
15个正式run均未达20ms，PERF-01、机载资源与SIM-01D验收不关闭。
证据见[EXP-20260920-004](../experiments/2026-09-20-perf01a-wire-cost.md)。

## ADR-015 异步匹配边界与高速运动时空一致性基线

日期：2026-09-23；状态：已实施（功能级运动基线，PERF-01仍阻塞）；主责任：integration_engineer。
依据：用户授权补齐大图失败记录并推进35/50/70m/s运动基线及PERF-01等待策略评估。

保留5ms Radar/IR门限、10ms历史位姿年龄、40ms采样截止及500ms墙钟缓存上限。
预登记oracle以理想1x到达为假设；实际迟到改变采用数量与墙钟过期仅改变拒绝理由分别
记录，但均不豁免原oracle失败。历史失败目录和报告不重建。

运动fixture沿world_ned北向匀速，p_ned=(v*t,0,0)，R_ned_frd=I，v_body=(v,0,0)。
经现有适配后p_odom=(0,v*t,0)，Radar到Body仅采用已命名fixture单位外参；固定世界
障碍物以odom/ENU同原点表达，采样时逆旋转生成相对点。真值仅由生成器及独立评测使用，
不加到业务消息。无FOV、噪声、转弯、扫描去畸变或物理可探测性验收。

当前策略为最近历史位姿而非插值。直线运动误差为v*pose_age，上限0.35/0.50/0.70m；
连续坐标一致性、体素归属、误差预算分别报告，不能把误差预算内的体素漂移当成严格重合。
地图拒绝期间保留最后观测时间，老化不增加revision、不制造free，新有效输入恢复新鲜度。

提前配对候选`exact`只用于每流采样时刻唯一的fixture：同刻有效IR、同刻有效状态均已
到达且通过原门控时，时间距离0已是最优，不必等40ms。只处理Radar有序队首；其余仍
走原截止/墙钟拒绝。默认`deadline`对照保留；候选不能声称任意乱序设备流已验证。
接收审计增加锁等待、业务decode与缓存处理耗时，发布到回调仍为含序列化/反序列化的
混合区间，不能命名为纯网络延迟。通过短run不关闭高速实时、SIM-01D或机载验收。
实际小图和大图结果、格网边界RED及保留的oracle失败见
[EXP-20260923-001](../experiments/2026-09-23-perf01a-motion.md)。

### ADR-015补充：2026-09-23边界量化与异步线格式复核

地图核对以消息携带Radar点和历史位姿变换所得连续odom坐标按半开格网`floor`
量化；理想静态世界坐标仅用于连续世界误差及`v*pose_age`预算。临界点不容差
吸附、不以理想体素覆盖实际结果。独立核对Occupancy索引和MapSnapshot索引；
不改变对外格网几何、时空接口或地图实现。修订后的实验解释及历史失败并存。
可选真实ROS编解码探针含观测开销，发送serialize到接收deserialize起点仅为
复制/队列/传输/调度混合区间。大图recovery严格oracle仍失败，尚无可接受的
双时钟预期规则，不借修改理由或门限让失败转绿。见
[EXP-20260923-002](../experiments/2026-09-23-perf01a-boundary-wire.md)。

### ADR-015补充：2026-09-23跨话题状态排空和双时钟诊断

在runner宣布本次异步完成前，要求源实际状态数量全部到达/发布、状态门控
pending=0以及最后真实收到的clock覆盖源审计的终点；只读汇总由matcher
状态参数发布，纳秒值按十进制字符串绕开ROS XML-RPC的32位整数限制。
未完成则有界失败，不合成clock。双时钟`wall_clock_carryover`仅作为基于
实际IR收据与matcher决策时刻的差异解释，不能豁免原预登记oracle失败。
修后证据及两次接入RED详见
[EXP-20260923-003](../experiments/2026-09-23-perf01a-clock-drain.md)。

### ADR-015待确认提案：2026-09-24双时钟理由边界

候选规则不是已接受验收变更：仅在IR真实接收、同run/clock身份、决定时未达
500ms墙钟上限、最终`wall_timeout`，且相对于Radar超出5ms和理想1x过期时，
允许**解释**`infrared_unavailable`与`radar_ir_timeout`拒绝理由差异。
仍需确认是否将这种有证据的差异作为新的预登记验收条件；在获确认前
继续严格逐样本匹配原oracle，保留全部旧失败。若采纳，也不得豁免采用数量、
消息顺序、时钟覆盖、地图、丢帧或20ms目标。2026-09-24固定配置recovery
一次run恰好在Radar19决定前wall超时而严格通过，证实旧理由差异非必现；
见[EXP-20260924-001](../experiments/2026-09-24-perf01a-dual-clock-preflight.md)。

## ADR-016 2026-10-10训练监督最小fixture与时空合同

用户确认项目计划中的IFACE-01训练时空子范围和SENS-TRAIN-01隔离训练支路；
实施依据为[已确认方案](SENS_TRAIN_01_IMPLEMENTATION_PLAN.md)。选择具名
`sens_train_01_simulated_mount_v1`仿真安装外参，`T_odom_training_lidar(t) =
T_odom_body(t) · T_body_training_lidar`；状态唯一权威仍为AircraftState。
采集参考时刻为Radar扫描/IR曝光/LiDAR扫描中点；仅此fixture扫描时长为零，
相对Radar偏移至多5ms、使用历史状态年龄至多10ms，超出或身份不符即拒绝。
目标网格在`training_lidar`，仅可证明的射线首回波之前标free、首回波标occupied，
其余unknown；无回波不自动推自由。IR热点需实际投影落显式配置像素。

独立训练launch发布Radar/IR公共帧与`/uav/training/lidar_supervision`
`std_msgs/String`版本化JSON记录；仅训练记录器消费监督，不新增公共ROS消息，
不修改在线SensorBundle、推理或地图图。字典中的数值与外参是**功能级fixture**，
绝非真实标定、物理雷达功率或热辐射测量。详见
[EXP-20261010-001](../experiments/2026-10-10-sens-train-01-fixture.md)。
后续若转换为公共LiDAR消息、改变同步策略或引入正式标定，须重新审查公共消费者
并单独确认；本决策不关闭IFACE-01全部子项、PERF-01或科研对照试验。

### ADR-016补充：2026-10-10无设备时的最小合同扩展

正式平台/物理采样时钟/功耗数据未就绪时，保留PERF-01阻塞且不替换验收门槛。
SENS-TRAIN-01新增双障碍双射线fixture：必须有严格正长度的实体内穿透才给
首回波；数值级擦边保持unknown；多个射线射到同一体素时已证实的occupied
不被另一射线沿程free覆盖。两个IR热点分别受标定投影校验；每次运行仍须图隔离。

IFACE-01仅增加**离线fixture子集**的PointCloud2解码/业务适配，明示字段名、
位置单位、Doppler正方向/参考系、强度量纲和run/clock身份。当前公共RadarPoint
无逐点时间槽，因此非零扫描或未知原始字段一律拒绝，不悄悄丢掉可能的时间信息。
现有ROS公共消息和在线话题图不变；真实设备规格与时钟转换方案形成前，不启用
测量来源或将fixture输入写成实际驱动。证据见
[EXP-20261010-002](../experiments/2026-10-10-iface01-sens-train-multiray.md)。

### ADR-016补充：2026-10-12非零扫描训练fixture合同

正式平台、物理传感器时钟和功耗输入仍未就绪，因此本补充不推进PERF-01，也不改变
公共ROS消息。SENS-TRAIN-01在离线纯函数范围增加schema `0.2`：非零LiDAR扫描必须
声明偶数纳秒扫描时长、从0到总时长有序覆盖的逐点时间偏移，并提供同一run/clock内
完整覆盖扫描起止的有效估计AircraftState历史。每条回波先在其采集时刻用
`T_odom_training_lidar(t)`求交，再转换到扫描中点；记录原始坐标、补偿坐标、逐点时间
和插值状态sample_id，位置线性插值、姿态最短弧SLERP。

本次只通过功能级两障碍/三射线fixture审计：两束回波经补偿后占据标签稳定，第三束
无回波保持unknown；缺历史、乱序、时间偏移未覆盖、v0.1承载非零扫描均fail-closed。
ROS v0.1零时长训练图、在线SensorBundle、perception、定位和mapping不变。该结果
不等于真实设备逐点时钟、真实标定、实时性能或研究模型质量验收；对照试验仍放在
工程数据门禁和接口闭合之后。

### ADR-016补充：2026-10-13训练记录逐射线时间审计

为避免把“没有回波”误写成“没有采集时间”，训练记录必须保存配置中全部射线的有序
`ray_time_offsets_ns`。有回波点使用唯一`ray_index`引用时间槽；无回波射线不生成点，
但其时间槽仍保留，且不产生free标签。记录验证器拒绝缺失/不一致时间槽、重复射线
返回和畸形点结构。历史v0.1零时长记录可兼容缺失偏移并按全零解释，新写入记录显式
保存偏移列表。该补充仍是离线纯函数记录合同，不新增公共ROS字段，不推进PERF-01，
也不改变LiDAR不进入在线SensorBundle、perception、定位和mapping的边界。

## ADR-017 2026-10-13 ARS548与Mid-360型号特定设备时间合同

**状态：已接受（字段合同）；实机时钟验证未完成。**

用户已明确项目使用Continental ARS548毫米波雷达和Livox Mid-360激光雷达。本次按
型号公开协议/驱动消息核对可直接取得的时间字段，结论如下：

1. ARS548的`DetectionList`保留`timestamp_seconds`、`timestamp_nanoseconds`和
   `timestamp_syncstatus`作为列表级时间；检测记录没有逐点时间。因此工程适配只输出
   列表级观测时刻，检测点的`point_time_ns`与偏移必须为不可用，不能用ROS接收时刻或
   列表时间复制冒充逐点采样。
2. Mid-360的`CustomMsg.timebase`和`CustomPoint.offset_time`可展开为每点时间；原始
   UDP包的`time_type`及设备状态用于区分启动时间、PTP/gPTP和GPS。由于`CustomMsg`
   不带`time_type`，驱动消息单独到达时只能保留逐点时间，不能确认同步来源。
3. 新增`sensors/ufm_sensors/device_time_adapter.py`作为纯函数字段适配器，身份必须
   包含`run_id`、`clock_id`、`sample_id`和`frame_id`；新增定向测试覆盖时间展开、
   计数/顺序/范围错误和缺失同步类型。该模块不估计跨设备偏移，不启动设备，不改变
   ROS公共消息和在线SensorBundle。
4. Mid-360仍严格属于训练监督输入；本决策不允许LiDAR进入在线感知、定位、地图或
   Radar+IR模型输入。正式PERF-01、功耗、实机同步残差及对照试验继续保持独立门槛。

资料链接与字段语义见[数据格式4.1](DATA_FORMAT.md#41-型号特定设备时间字段审查-2026-10-13)。

## ADR-018 2026-10-13 设备时间落盘与映射状态分离

**状态：已接受（记录合同）；真实设备回放未完成。**

设备到位前先固定`device_time_record_v1`，每条解码记录必须同时保存设备采集时间、
主机接收时间、接收时钟域、设备身份和原始payload。`device_timestamp_ns`来自
ARS548检测列表时间或Mid-360首点/逐点展开；`receive_timestamp_ns`只用于接收审计，
禁止覆盖采集时间。

`time_mapping_status`固定为`unmapped`，offset、drift和误差上界必须保持空值，直到
取得同一公共时钟或可审查的PPS/PTP/gPTP/原始包证据。Mid-360的原始`time_type`只能
标记来源类别，`time_sync_verified`仍为false；ARS548没有逐检测时间，不生成伪造偏移。

实现放在`sensors/ufm_sensors/device_time_record.py`，输入审计为纯函数，不新增ROS
消息、不启动真实驱动，不改变Mid-360仅训练监督的边界。收到实机记录后，先做离线
字段回放、设备/主机时钟残差和丢包/重复审计，再评审ROS记录器与非零扫描训练路径。

## ADR-019 2026-10-13 硬件缺失时独立推进非零扫描ROS训练闭环

**状态：已接受（用户“继续”确认的软件子范围）；完整训练任务未验收。**

真实设备/实测记录缺失只阻塞相关设备验收，不阻塞仿真软件开发。沿用训练独立图和
JSON schema `0.2`，将既有逐点时间/运动补偿接入ROS记录路径；不等待真实Mid-360
记录，不把仿真时钟当作设备时钟，不修改研究仓库、公共消息或在线SensorBundle。

训练源增加覆盖首尾扫描的状态，sensors维护有界历史，仅当状态和clock共同覆盖
扫描末端才生成样本；状态身份/顺序或clock不合法拒绝，输入停滞时明确停止。
ROS节点直接读取同一配置快照，避免XML-RPC整型上限且保持纳秒精度。具名仿真标定
的排他有效期延长到2.2s，只为覆盖最后扫描末端2.1s，不增加真实标定声明。

验收以实际ROS传输、独立JSONL回读、五类收据、解析几何oracle及图隔离为证据；
原有两个零时长入口回归，首轮XML-RPC失败目录保留。详见
[EXP-20261013-005](../experiments/2026-10-13-sens-train-motion-ros.md)。
此决定补充ADR-018的仿真执行顺序，真实设备记录审计要求不变；正式PERF-01仍阻塞，
后续优先几何/运动场景和数据统计，对照试验留到工程数据门禁之后。

## ADR-020 2026-10-13 训练场景统计与体素边界数值稳定性

**状态：已接受（用户“继续”确认的场景/统计子范围）；实机与完整数据质量未验收。**

通过独立离线矩阵扩充几何/运动场景，使用具名运动学源、既有训练状态缓存/生成
函数及JSON记录合同；不修改ROS图、在线SensorBundle、研究模型或PERF配置。评测
只调用公开入口，独立面交点与解析位姿核对数据，避免用生产射线/插值私有函数
作为oracle。每次新输出目录隔离run身份，保留全部配置、源状态、标签与失败报告。

35/50m/s场景复现同一表面因约1e-15m舍入跨过网格整数边界，产生伪重复occupied。
训练索引在8倍float64机器epsilon的缩放误差内先吸附整数，再floor，其余保持floor；
真实1e-9m边界两侧保持区别。此修复仅稳定数值边界，不改变射线擦边、FOV、量程、
时间同步、未知区域语义或公共schema，也不回写任何历史实验。

覆盖率统计按每帧网格单元计数，不当作唯一世界体素覆盖、感知召回或训练充分性；
无回波误差为空值，几何残差为理想fixture数值一致性，非设备测量精度。偏航源是
平移叠加姿态变化，不代表动力学一致的固定翼转弯。通过结果与失败见
[EXP-20261013-006](../experiments/2026-10-13-sens-train-scene-statistics.md)。

## ADR-021 2026-10-13 ROS训练fixture偏航与插值验收

**状态：已接受（训练支路软件子范围）；非实机、非正式性能、非模型质量验收。**

在不改变公共Radar/IR消息、在线SensorBundle、研究模型或PERF-01配置的前提下，训练
专用ROS源支持配置声明的运动学fixture profile。新增小角速度偏航配置，保留原有
直线、single和multiray入口行为；200ms监督扫描继续由唯一`/clock`和状态源覆盖首尾。
50ms和150ms射线槽通过状态历史插值，所有射线槽仍落盘，无回波槽不产生点或自由空间。

runner按配置核对旋转状态、body速度、Radar/IR收据、原始/补偿点、逐点sample_id、
occupied/free/unknown标签和图隔离；偏航验收必须有非零角速度及插值回波。该profile
仅表示北向平移叠加独立偏航，不代表固定翼动力学转弯或PX4估计。真实ARS548、Mid-360
记录、设备时钟残差、标定和功耗仍按IFACE-01/PERF-01单独验收。

实际ROS run与旧入口回归见[EXP-20261013-007](../experiments/2026-10-13-sens-train-yaw-ros.md)。
下一步为T-14的Odometry兼容镜像/唯一TF设计与契约测试；对照试验仍放在真实数据和模型
质量门禁之后。

## ADR-022 2026-10-14 AircraftState派生Odometry与唯一TF

**状态：已接受（软件兼容镜像子范围）；真实定位质量与设备协方差未验收。**

保留`AircraftState`为唯一定位权威和完整状态合同。在已有`state_adapter_node`内增加
默认关闭的`publish_odom`与`broadcast_tf`开关：由同一条适配状态分别派生
`/uav/localization/odom`和动态`odom -> base_link`，不新增定位目录、不新增第二个
状态适配器、不让mapping订阅Odometry。镜像直接保留AircraftState采样纳秒和odom/base_link
帧语义；未知质量不填造协方差，terminal/unavailable不产生几何消息。

采用ROS标准`nav_msgs/Odometry`是兼容工具需要，消息本身规定pose使用header.frame_id、
twist使用child_frame_id，符合当前odom/base_link边界。[ROS aerial interface REP-147](https://github.com/ros-infrastructure/rep/blob/master/rep-0147.rst)
也将`nav_msgs/Odometry`作为航空器通用里程计接口。实机定位来源、真实协方差、外部
时钟和长期TF缓存仍待后续记录审计。

验证见[EXP-20261014-008](../experiments/2026-10-14-t14-odom-tf.md)。

## ADR-023 2026-10-14 基础地图单点查询ROS承载

**状态：已接受；固定网格单点查询软件子范围已完成，完整地图能力仍开放。**

复用已有SparseLocalMap及地图节点，在新增MapQuery.srv/MapQueryResult.msg中承载
DATA_FORMAT §9.1单点子集。查询默认关闭，启用时与地图更新共用实例与锁，不新建
旁路地图缓存；消息扩展为新增类型，不改变已有MapSnapshot及历史bag字段。
协议保留缺失概率/索引/观测时间/quality的显式可用性，五类状态不互相降格成free。
合法身份/坐标/地图不匹配返回unavailable，畸形请求明确以service error拒绝。
不自动查TF、不消费AircraftState/LiDAR、不以当前处理时间刷新地图。

阈值必须成对显式配置；未配置时查询仍返回有效历史概率但不猜测占据/自由分类。
fixture的0.3/0.7不构成飞行默认值。当前只做单点和固定odom轴对齐网格，区域查询、
滚动窗口、概率累计和规划控制另行确认。验证与失败产物见
[EXP-20261014-010](../experiments/2026-10-14-local-map-query-ros.md)：三种fixture模式、
338项全仓轻量测试和旧PERF-01-A真实ROS入口回归通过；首轮公共`/clock`连接图误判目录
保留。该决定不关闭正式PERF-01，也不批准滚动地图、概率融合或对照试验；下一步须另行
确认滚动局部地图具体方案。

## ADR-024 2026-10-14 可选基础滚动Local Map

**状态：已接受；仅完成软件fixture子范围，Phase 4与正式性能门槛未关闭。**

在用户确认后，沿用原有`SparseLocalMap`及ROS节点，以默认关闭的
`rolling_enabled`/`rolling_grid`开关启用观测时刻body位置驱动的轴对齐odom
整格移动窗口；不变更OccupancyObservation、MapSnapshot、MapQuery字段。
原因：有限cell缓存淘汰只能控制条目数，不能移动固定coverage，飞行越界后新观测
必然无法纳入地图。配置初始origin为格点锚，以shape/resolution确定固定大小窗口；
每次有效观测按观测SpatialContext位置移动，重叠cell重映射并保留时间/质量，
移出部分清除，新范围默认为unknown。输入格网需为同一锚点整格且odom轴对齐；
变换不合法、乱序、重复冲突或身份域变化不得部分移动。断流不移动，旧单元
按查询时刻老化；新run/clock由外部重启地图实例；大位移无重叠直接淘汰。

固定入口与旧查询默认不变，可关闭滚动开关恢复；回退仅限本新增实现及fixture，
保留旧实验和未提交工作。风险：当前没有自动odom重置检测/定位质量证据、
任意倾斜输入重采样、历史版本查询及真实机载RSS/时延验收；不增加mapping
对AircraftState、Odometry、Radar/IR、LiDAR的订阅，不推进概率累计、DEM或控制。
测试和失败run详见[EXP-20261014-011](../experiments/2026-10-14-local-map-rolling.md)。

## ADR-025 2026-10-26 可选仿真IMU独立ROS承载

**状态：已接受；仅功能级虚拟pilot点旁路通过，真实IMU与完整Phase 2未关闭。**

前一轮[源链与接口门禁](PHASE2_IMU_GATE_20261026.md)提出生产、消费、兼容及恢复
方案；用户后续“继续”确认按此阶段范围实施。新增`ImuSample.msg`承载既有
ObservationHeader身份、采样纳秒、比力/角速度、加速度类别及显式不可用协方差。
simulation只在显式`publish_imu=true`时从HIGHRES_IMU校验值向相邻sensors
发布`/uav/sim/imu`；sensors要求`sim_pilot_virtual_flu_v1`虚拟标定并只向
诊断/记录发布`/uav/sensors/imu`，FRD→FLU仅是轴变换，不假定实际安装原点。
旧状态、/clock、Radar/IR、placeholder、训练图保持原样；IMU不加入SensorBundle、
定位、mapping、研究forward或LiDAR监督；开关默认false可恢复旧运行图。

接口变更仅为**新增消息与可选话题**，不修改旧消息字段和既有bag结构；
失效源明确拒绝或标记unavailable，不自动回退成空值读数。消息往返、源拒绝、
适配时钟门控、开启/关闭独立ROS图、旧SIM-01 fixture和在线占位图已通过，
记录见[EXP-20261026-003](../experiments/2026-10-26-phase2-imu-optional-ros.md)。
未有真实PX4/JSBSim本次在线IMU验收、安装/偏置/设备时钟证据；后续依据实际
原始设备记录审查语义和坐标，再决定真实驱动与质量门槛，不自动提高阶段状态。

## ADR-026 2026-10-27 审查修复、配置来源与有界身份历史

**状态：已接受；用户确认按审查策略修复，限于软件正确性和工程收敛。**

问题：受限PointCloud2适配混淆字段顺序，PERF编码将未知变换枚举解释为可用，
同格Radar点导致整帧失败且异常只产生旁路诊断；配置浅/深合并不一致、身份账本
无界、旧实验入口依赖观察器，当前状态混入大量历史，新增测试/记录被整目录忽略。

决定：按字段字节偏移解码；共用既有ROS契约包的Header与枚举校验；地图在修改状态
前拒绝无效Header；同格点只保留一个fixture体素，后端异常输出空unavailable观测。
不可信解码仅诊断拒绝。消息仍为0.1及原字段，不引入跨层实现导入。

异步runner与业务测试共用load_profile，按defaults → 场景 → 显式CLI深合并。
感知/地图ROS节点共用local_map_fixture.yaml和装配层解析器，保存最终配置；
新增无诊断/无观察器依赖的inference_fixture启动图，旧实验runner保留原就绪检查。
State/IMU共用有界身份历史，默认1000条，按采样时间淘汰并以水位拒绝过旧重传；
终止状态独立保留。窗口外不承诺识别被重写为未来时间的旧身份，生产者唯一身份
约束不变。未验证机载RSS或硬件功耗，不通过放宽同步/等待阈值改善性能数字。

兼容：保留旧ROS事件导入路径为转发入口，源状态fixture只在simulation维护；
未采纳的NumPy/TCP_NODELAY/IR借用候选及所有历史命令、run与失败证据保留。
恢复旧实验图使用原runner；恢复代码仅针对本轮补丁，不重置已有工作区或环境。
PROJECT_STATUS只保留当前事实，优化前正文完整保存在历史快照；测试和小型实验
记录解除目录级忽略，提交仍须逐文件授权，不自动提交或推送。

验证与文件清单见[EXP-20261027-002](../experiments/2026-10-27-review-repairs.md)，
配置及限制见[运行配置说明](RUNTIME_CONFIGURATION.md)。本决定不关闭正式PERF-01、
ENV-03、真实设备/研究模型质量、完整Phase 1/2/3或M1→M2门槛。

## ADR-027 2026-10-27 OPT-02第二轮遗漏修复

**状态：已接受；完成范围为软件契约和fixture ROS短测。**

第二轮复核发现消息字段可解码但组合关系未验证、available变换接受反射、关闭观察器时跳过
必需业务连接、纳秒配置直接写ROS参数会溢出，以及质量字段可携带NaN/空available元数据。
本轮在感知消费入口增加组合校验，统一检查可用4x4变换为齐次正旋转；ROS质量路径和纯地图
入口都执行有限值、范围和既有occupancy_variance语义检查；业务ready始终等待必需业务连接，
观察器保持可选；纳秒快照以十进制字符串承载并兼容旧整数读取。错误输入在地图更新前拒绝，
不刷新历史revision、cell或观测时间。

ROS启动图把paired/async/rolling已有同步门限同时注入生产侧和消费侧；没有新增消息字段、
没有引入定位层、没有把LiDAR加入在线SensorBundle。442项轻量测试和7组独立ROS短测通过，
证据见[EXP-20261027-003](../experiments/2026-10-27-opt02-repair.md)。本决定不关闭正式
PERF-01、真实设备/研究模型质量、硬件性能、完整Phase 1/2/3或M1→M2门槛。

## ADR-028 2026-10-27 外部数据阻塞时提前推进下一阶段软件

**状态：排程原则已接受；具体工作包为计划，尚未实施。**

依据：用户要求按总体进度制定下一步计划，并明确允许当前阶段因真实数据阻塞时提前
进入下一阶段；此前要求暂不研究4D-Radar-Diffusion模型质量。

决定：外部设备、标定/时钟和正式性能验收保持独立阻塞，软件主线转入Phase 3统一
感知入口/输出契约、有界后端执行和组合验收，再提前进行Phase 4 M1公开占据回放与
应用查询客户端。既有OPT-01/02和传感器/IMU验收作为输入，不重复包装为新交付。
计划见[STAGE_ADVANCE_PLAN_20261027](STAGE_ADVANCE_PLAN_20261027.md)。

本决定只允许按依赖提前安排软件工作，不接受现有研究候选，不引入新的公共消息、
定位层或在线LiDAR，不宣布完整阶段退出。M2概率累计仍须符合既有M1→M2门槛；
若需独立软件试制，另给出明确准入提案。原阶段日期保留作偏差跟踪，2026-11-10
复查外部输入风险；2027年3月交付目标不据此自动获得可实现性承诺。

## ADR-029 2026-10-27 统一感知执行边界与可选CPU任务隔离

**状态：已完成软件交接；真实后端/GPU及正式阶段验收未关闭。**

依据：用户授权执行跨阶段软件计划P3-SW-01/02/03。将模式选择、组合校验、后端
异常与输出校验移入perception纯业务入口，保留现有消息字段/默认placeholder和
research不可用语义；ROS包装只负责承载。输出核对同一输入身份、时刻、坐标、
配置几何和质量，禁止坏后端结果新增地图证据。

有界执行采用默认关闭的spawn CPU子进程，最多1个活动任务、零等待队列；
显式墙钟deadline包括启动开销。忙碌新帧明确unavailable并使旧结果不再发布；
超时/关闭终止并回收子进程，故障后按新输入恢复。该机制只验CPU测试替身，
不提供真实研究/GPU取消安全或20ms性能结论。未改变同步预算、层间接口与M1门禁。

初次461项轻量回归通过时ROS审批超时，事实保留在
[EXP-20261027-004](../experiments/2026-10-27-p3-perception-engine-worker.md)。
用户再次授权后独立ROS故障/恢复、旧入口和三模式兼容均通过，软件交接证据见
[EXP-20261027-005](../experiments/2026-10-27-p3-m1-app-handoff.md)。

## ADR-030 2026-10-27 M1公开占据回放与应用查询客户端

**状态：已完成软件范围。**

按已授权跨阶段计划，在mapping中复用既有公开占据receipts，经update/snapshot/query
复现同版本结果；不排序或自动继承不同run。查询用记录revision选择地图版本，不宣称
墙钟调度一致。application只消费公开MapQueryResult，ROS包装独立，保留五类状态、
时间和质量；服务不可用输出明确unavailable，不推断free或发送控制指令。

不新增公共消息/服务、不改变地图融合规则或既有默认入口。三组回放、实际查询ROS及
独立CLI/缺失服务通过，全仓469项通过，记录见上述EXP-20261027-005。
正式M1资源/真实输入、M2实施准入、研究质量和PERF-01门槛保持原约定。

## ADR-031 2026-10-27 M2合成逆观测软件试制提案

**状态：合成数据软件试制已获用户确认；M2-SW-01/02/03/04已完成，正式M1/M2未验收。**

按下一任务制定[M2方案](M2_SOFTWARE_TRIAL_PLAN_20261027.md)：首版拟仅允许明确标识的
合成逆观测fixture输入，在独立、默认关闭的候选中验证有界log-odds、去重、TTL、
滚动与公开查询；不把当前placeholder的固定0.9或研究模型后验当成独立似然累计。
缺少校准时confidence/uncertainty保持不可用，无回波/失效/中性输入不刷新证据时间。

先验、限额与阈值在具名fixture配置中显式给定，先固定网格再接时序/滚动和ROS。
软件试制许可与正式M1→M2验收分开；初次设计不标记正式M1通过，设计审查见
[EXP-20261027-006](../experiments/2026-10-27-m2-design-review.md)。
用户后续“按你说的做”确认具体合成软件范围。M2-SW-01新增默认关闭的fixture参数、
输入契约与测试专用合成消息/独立分数oracle；9场景/31消息及479项轻量回归通过，
记录见[EXP-20261027-007](../experiments/2026-10-27-m2-fixture-oracle.md)。
本步没有累计器、ROS候选模式或公共字段变化；后续同一软件范围按已确认工作包推进，
无需重复请求相同确认。正式资源/真实质量门槛保持原约定。

后续M2-SW-02采用独立`FixedProbabilityMap`，复用同模块M1的snapshot/query但独立实现
update，不先覆盖再回改cell。固定候选逐帧有界log-odds，先校验/暂存再提交；
基础有界身份/水位和TTL重启在本步提供，确保公开查询不误激活过期证据。
9场景/31观测与上一工作包冻结oracle一致，12项定向及491项回归通过，见
[EXP-20261027-008](../experiments/2026-10-27-m2-fixed-map.md)。
M1默认运行和公共字段保持；滚动/ROS候选图尚未完成，不以基础TTL测试关闭SW-03。

后续M2-SW-03新增显式`RollingProbabilityMap`，共享固定累计的原子更新路径，
只在滚动候选接受有效动态body位姿和同格点odom观测origin；固定合同保持原限制。
重叠cell连同L和原证据时间迁移，移出一起淘汰。合法空帧可改变覆盖revision，
不推进证据时间；内部记录覆盖变化时刻，早于该时刻的查询返回unavailable。
不新增公共字段，也不改变M1源码或默认启动。3组运动场景15观测、40条限额序列、
M2共37项定向和全仓506项通过，见
[EXP-20261027-009](../experiments/2026-10-27-m2-rolling-time.md)。
SW-03仅完成离线合成范围，实际ROS候选/回放/应用交接仍由SW-04验证。

后续SW-04以模块内共享`create_map`装配ROS与回放，节点私有`map_backend`默认latest，
只在显式m2_fixture时惰性导入候选，必须有合成配置和clock_id；参数冲突/缺失或
未知模式明确失败，不自动fallback。独立launch/runner只注入公开合成占据，
地图仍只订阅occupancy及基础设施clock；公共消息字段、旧launch和M1规则不变。
15观测/9快照/14查询、4条坏输入拒绝及公开收据回放一致；应用五类状态、独立CLI、
旧固定/滚动/placeholder ROS、515项轻量回归与清理通过，见
[EXP-20261027-010](../experiments/2026-10-27-m2-ros-handoff.md)。
关闭M2合成软件工作包，下一项仅计划M3不确定性方案；不宣称正式M2、真实概率或机载资源通过。

## ADR-032 2026-10-27 M3合成区间表达与传播提案

**状态：M3合成软件试制已获用户后续“继续”确认；DESIGN-01/SW-01/02/03/04已完成合成软件范围。**

按用户“继续”完成[具体方案](M3_SOFTWARE_TRIAL_PLAN_20261027.md)。沿现有质量生产/
消费链确认M1保留最新帧quality、M2明确清除累计质量；通用格式检查不能证明类型单位、
协方差形状或真实校准，自定义应用transport还缺少独立质量验证。
9项只读探针、3组有理数算例和17项既有定向通过，记录见
[EXP-20261027-011](../experiments/2026-10-27-m3-design-review.md)。

首版拟在默认关闭的独立fixture候选中，用既有Uncertainty字段表达标量概率区间，
沿已声明M2算术单调传播上下界；输入/累计source标识分开，不将累计输出再次当输入。
区间不代表置信水平/真实误差覆盖率，不从概率、熵、观测次数或confidence伪造质量。
任何有效贡献缺范围则本cell周期累计质量不可用，直到TTL重启或淘汰；
时序/坐标/限额、原子拒绝及五类查询语义保持。先合同/oracle，再固定、滚动/TTL和
ROS/应用交接，具体工作包与恢复方式见方案。

初次设计轮仅修改方案/状态/记录。用户随后“继续”确认具体合成软件试制，
SW-01新增显式配置、纯合同检查、测试fixture/独立有理数oracle与输入生成器。
均值先确定float32值，区间不可用与零宽分开；输出舍入关系用端点nearest-even映像
检查，不使用任意epsilon或改写载荷，来源input/output严格分离。
10场景43输入、19项定向及534项全仓通过，记录见
[EXP-20261027-012](../experiments/2026-10-27-m3-fixture-oracle.md)。
本步只生成输入/预期，不执行M3累计或新ROS；后续同一合成范围按SW-02—04连续推进。
不增加公共字段、不恢复研究质量、位姿协方差融合、Scene Map/DEM或正式性能任务。
默认M1/M2和正式验收门槛保持。

SW-02新增显式固定`FixedIntervalProbabilityMap`，仅在M2暂存路径提取`_updated_cell`
构造扩展点，M2默认质量和名义算术保持；M3均值及端点L在同一按cell限额的不可变
私有状态项中提交/淘汰，公开消息不泄漏L。缺失范围锁存到该cell TTL重启或淘汰，
输出confidence仍None。保存预期直接对账，不重算oracle；10场景43输入、
12项新增定向/M3共31项/全仓546项通过；受影响M2实际ROS及回放/清理通过，见
[EXP-20261027-013](../experiments/2026-10-27-m3-fixed-map.md)。
默认factory、M1和ROS入口未改为M3；固定基本TTL已有证据，完整M3滚动/TTL组合及
M3 ROS/应用交接仍由SW-03/04完成，不提高正式质量或资源验收状态。

SW-03仅新增显式滚动子类和测试工具，复用同模块M2滚动准备与固定M3暂存构造，
没有修改既有M1/M2/固定M3源码、默认factory或ROS。范围/缺失状态、均值和贡献时间
共同迁移/淘汰；无证据和非valid不刷新证据，未来窗口不回答过去查询。
3组运动场景16帧及80帧多cell限额序列、257查询、4探针通过；保存预期重放一致，
名义值逐值等于M2。15项新增/M3共46项/全仓561项通过，见
[EXP-20261027-014](../experiments/2026-10-27-m3-rolling-time.md)。
这只关闭SW-03离线范围，下一项SW-04实际ROS/应用交接；不声明校准、真实质量或RSS/功耗通过。

SW-04随后在既有factory/节点/回放增加显式m3_fixture，完整配置与clock必需，默认latest；
混配、缺配置、覆盖参数或非法输入拒绝，不切换后端。应用仅消费公开结果，新增通用质量
检查及具名概率区间包含关系检查，使用nearest-even float32映像保留原端点；其他合法kind
仍透传。无公共字段/架构变化，不访问研究代码、GPU或checkpoint。
19观测/13快照/19查询、155项运行检查、4条拒绝、五类状态、公开回放及缺失后TTL恢复通过；
旧M1/M2/placeholder、五组ROS清理及570项全仓通过，见
[EXP-20261027-015](../experiments/2026-10-27-m3-ros-handoff.md)。
关闭M3合成软件试制；按阶段顺序下一项为M4-DESIGN-01具体设计，未实现Scene Map或DEM，
不以合成区间结果关闭真实质量或正式M1/M2/M3门槛。

## ADR-033 2026-10-27 M4固定合成注册与有界子地图提案

**状态：用户后续“继续”确认具体合成软件范围；DESIGN-01/SW-01/02/03/04已完成，仅关闭合成软件试制。**

按地图层顺序交付[具体方案](M4_SOFTWARE_TRIAL_PLAN_20261027.md)。源码审计确认
滚动M3移出窗口即丢弃历史，MapSnapshot只表达一套网格且没有注册目录，
SpatialContext没有独立reset/epoch或map←odom字段。现有map坐标手工fixture经真实消息
序列化/应用保真通过，9项审计与32项既有相关测试通过；不表示M4已运行。

拟在mapping内部保留1个活动M3和至多K个固定几何封存子地图，经显式固定map←odom
注册导出一个固定map网格的公开视图。Scene只管理历史估计与唯一cell所有权，
不融合累计快照或把旧历史反灌M3；概率/quality/原时间整条转移，缺失不借旧范围。
目录FIFO有界，所有权旧副本移除，不在淘汰后复活；Local与Scene联合暂存后提交。

先选非零整格平移、同分辨率固定合成注册，不支持任意旋转、动态修正或隐式odom=map。
定位reset仍按显式新run/空实例处理，未声明同run跳变不可识别，正式定位/注册门槛保持。
私有候选名称拟为m4_fixture，当前工厂未注册；默认M1/M2/M3、ROS消息/订阅和应用接口不变。
下一项计划M4-SW-01合同/输入/独立预期，再依次候选、时序/资源及ROS交接。
不恢复研究质量、DEM或正式PERF-01，详见
[EXP-20261027-016](../experiments/2026-10-27-m4-design-review.md)。

2026-10-28 SW-01实现m4_fixture.v1完整配置及纯注册/输入checker。注册声明run/clock、
方向、fixture来源、左闭右开有效期和非零整格平移；输入复用M3合同，新增完整活动窗口
Scene envelope检查及严格公开字段隔离，nonvalid不使用不可用变换移动窗口。
无状态checker不宣称解决去重/事件水位或定位reset；这些保持后续候选及正式门禁。

8组合成场景的41输入/52查询预期、目录所有权表与完整case配置先保存，再做输入checker
及真实消息序列化。38条输入合同接受、3条拒绝；重复/迟到等有状态结果只是冻结预期。
独立分数/坐标和显式生命周期表不调用Scene候选生成答案，质量/来源/时间不借旧值补齐。
24项定向及全仓594项通过；没有Scene/累计/ROS Master执行，见
[EXP-20261028-001](../experiments/2026-10-28-m4-fixture-contract.md)。
下一项SW-02显式纯Python候选对冻结预期，工厂仍未注册M4，默认与公共消息保持。

SW-02已新增显式SceneMap，完整M4配置/run/clock必需；仅组合活动M3公开接口和
有界封存目录，不修改M1/M2/M3算法。所有权索引引用唯一估计载荷，重叠转移不二次累计；
新missing整条接管，不借旧范围。空记录删除后按封存序号FIFO淘汰，旧副本不复活。
活动与Scene在同一临时状态中更新/校验，成功后单引用提交；基础后段故障恢复测试通过。

独立运行器直接读取SW-01保存输入/预期，不导入oracle重算答案。8场景41输入52查询、
目录所有权/FIFO、公开快照/查询与实际消息序列化一致；15项新增/M4共39项、全仓609项通过，见
[EXP-20261028-002](../experiments/2026-10-28-m4-scene-candidate.md)。
默认factory和ROS不变，无M4实际ROS/真实注册或性能结论；下一项SW-03时序/资源与
联合原子性组合，基础TTL/故障样例不能替代完整组合和临时副本资源审计。

SW-03只新增测试工具，对保存的140帧323查询（含K=1/N=2/H=3的120帧周期轨迹）
核对时序、TTL、FIFO淘汰/返回、缺失质量及原证据/结构时刻；4个提交后段故障点
均保持活动M3/Scene/身份水位原样，同一身份/时间重试成功且重复不二次融合。
新run/错域/注册过期隔离和实际消息序列化通过，业务源码无需修改。

保留项与临时对象分别计数：H是消息条数，载荷按H*V；测试V=3/N=2时保留9个
身份voxel而只有2个活动cell，不能用H*N冒充实际输入占用。
mapping行/返回边界采样包含已提交/临时状态、查找索引、前后快照和输出列表；
不覆盖分配器内部瞬时字节峰值、调用方保留结果或RSS。13项新增/M4共52项及622项全仓通过，见
[EXP-20261028-003](../experiments/2026-10-28-m4-time-resources.md)。
下一项SW-04实际ROS/公开回放/独立应用交接；固定合成范围不关闭真实定位/质量/资源门禁。

SW-04已在共享工厂/既有ROS节点/公开回放增加显式m4_fixture，默认latest。
完整配置、run/clock和rolling必需，混候选配置、覆盖参数或注册错误启动失败；
运行错误报告拒绝并保留已提交地图，不转M1/M2/M3或fixture替代输出。
不新增公共字段/消息/业务订阅；默认老化诊断通过公开snapshot与TTL兼容Scene。
实际ROS的15观测9快照20查询/174项检查、4条拒绝、五类状态与历史质量保真，
公开回放和独立应用map CLI均通过；五组旧ROS及清理通过，新增7项/全仓629项通过，见
[EXP-20261028-004](../experiments/2026-10-28-m4-ros-handoff.md)。
关闭固定合成注册下的M4软件工作包，真实注册/reset识别/动态修正及质量/资源门槛保持。
按阶段顺序下一项M5-DESIGN-01仅交付TerrainPrior基准/no-data/质量、生产消费与兼容恢复方案；
DEM实现与公共接口扩展未授权，本轮不开展。

## ADR-034 2026-10-28 原生RViz报告界面与公开地图只读适配

**状态：用户明确要求10-30周五前交付，并指定RViz；APP-VIS-01默认软件渲染报告版本已完成。**

本轮优先级从M5设计转为报告可视化，不改变地图阶段门槛。沿现有公开snapshot/query
增加application只读SnapshotView，ROS/Qt包装嵌入本机原生RViz，标准MarkerArray显示，
标准PointStamped仅承载本界面查询点。无原始传感器/模型/地图私有状态旁路，无公共业务字段变化。
坐标由公开origin/index/resolution计算，不猜测frame或补注册；未知、过期、失效保留语义。
live显式master/clock/TTL，不启动业务图；demo具名独立fixture；replay只读公开快照，
历史帧不调用当前地图服务。输入/模式错误明确失败，不自动fallback。

GUI进程继续指定Conda Python，仅该进程选择RViz所需系统Qt/TIFF；配置与缓存隔离到新run。
截图读取自身Qt部件与Ogre目标，附来源/时间/查询JSON，避免遮挡桌面混入证据。
系统显卡路径出现过一次未定位初始化SIGSEGV，不宣称已修复；报告入口显式固定已有Mesa
软件渲染，不自动切换。默认路径的demo/独立回放/live及像素与清理通过，全仓638项通过。

交付物：[使用说明](ROS_VISUALIZATION.md)、[报告图片/图注](../experiments/report_assets/rviz-20261028/README.md)、
[EXP-20261028-005](../experiments/2026-10-28-rviz-report-delivery.md)。
恢复仅关闭界面或清理自己创建的demo/replay会话；不改现有地图、原环境或研究仓库。
本次仅关闭报告软件功能，真实模型、硬件、标定、资源、正式性能和系统显卡稳定性仍独立验收。

## ADR-035 2026-10-28 独立场景驱动Radar/IR及标准RViz显示

状态：按用户澄清的场景、Radar点云/IR、三维场景窗口范围实施，SENS-VIS-01功能级软件范围已完成。
APP-VIS-01仅地图工作台不能代表该目标完成，原记录/实现保留。

新增独立Gazebo场景模式，不替换PX4/JSBSim：同源几何/热材质驱动几何Radar和IR强度相机，
sensors输出既有SensorBundle，placeholder→Local Map不读取场景真值或训练监督。
Gazebo真值经既有AircraftState合同与state_adapter显式scene_ground_truth/具名ENU注册，
保留ground_truth来源和唯一动态TF职责；默认PX4 estimated分支不变，混源/缺注册拒绝。
标准RViz直接显示PointCloud2/Image/TF，地图适配仅消费公开MapSnapshot，不新增公共业务字段。

Radar为静态目标首表面几何近似，任意强度不冒充RF功率；IR独立材质通道不是测温。
Gazebo lockstep用于采集时序稳定，仍保留5ms配对、10ms姿态年龄、40ms待配对上限；
时钟回退锁定run，无回波/过期/失效不产生free，不自动fallback到旧fake输出。
原生Qt/Ogre自身读回截图，界面配置及Mesa软件渲染环境只作用于新会话。

实际场景扰动、数据/像素与旧ROS/649项轻量回归/清理见
[EXP-20261028-006](../experiments/2026-10-28-sensor-scene-visualization.md)。
恢复为停止本会话、新run重建；不改研究仓库、原Conda或默认旧入口。
飞机固定，不宣称PX4/Gazebo联动飞行、真实传感器物理质量或正式性能达标。

## ADR-036 2026-10-28 M5地形先验设计与公共接口闸门

状态：用户明确要求继续M5-DESIGN-01，具体方案已交付；实现与公共协议扩展尚未执行。

沿真实工厂/Scene/ROS/应用链确认TerrainPrior只有文档预留，MapCell/MapQueryResult
不能无损携带高程、地形版本、证据角色和两种时间域。现有M4固定fixture注册不是地理注册。
采用[独立地形高程层方案](M5_TERRAIN_PRIOR_DESIGN_20261028.md)，先规划私有离线fixture合同、
输入校验与独立预期，不将高程直接转成occupied/free，不改变M1—M4的概率、质量或证据时间。

设计明确水平/垂直基准、像素采样、轴序和单位、具名map注册、no-data、源采集时间与运行有效期、
米制高度质量、原子版本/资源/失败恢复。缺基准或注册不可用时fail-closed，不采用零高程或仿真地面fallback。
LiDAR监督/标签仍不进入在线输入、定位或地图。旧入口不加载地形依赖、文件或研究模型。

若后续确需ROS/应用地形接口，单独确认独立版本协议及mapping生产者、application消费者、
消息往返、新旧并行、服务缺失和回退矩阵后再实施；不复用占据reason/source_types藏结构化数据。
DEM占据辅助融合还需分源证据、两个时间域、贡献撤销/相关性与独立质量准入，不由本设计批准。

10条源码事实、10项现有边界/数字检查与40项既有定向回归见
[EXP-20261028-007](../experiments/2026-10-28-m5-design-review.md)。只关闭设计交付，
真实DEM/地理控制点、候选实现、ROS交接、正式地图/Phase 4与性能门槛保持。
下一建议M5-SW-01为私有fixture合同/输入校验及独立预期，不执行候选、真实DEM或公共协议扩展。

## ADR-037 2026-10-28 M5私有fixture输入与候选前置隔离

状态：用户继续授权后M5-SW-01输入/预期软件范围已完成；地形候选与公共接口未实施。

mapping内显式m5_contract模块只校验单个小型私有JSON fixture及请求语法，不接工厂、ROS、
应用或占据更新。冻结schema/字段、DTM/fixture来源、源/目标水平和垂直基准、north-up中心采样、
row-major高程/布尔no-data、具名非零平移/整格注册、独立dataset时间/运行授权与固定限额。
逐样本height_interval是绝对源高程界，height_offset_interval是tz平移界，均为m；
缺失质量明确unavailable，不借用M3概率区间或补零误差。真实基准/必须校正网格操作拒绝。

load_fixture最多读16KiB+1，超限在JSON解码前失败，拒绝重复key/非有限数；
对象校验仅检查已持有输入，不声称能消除调用者已有分配或保证未来候选峰值。
validate_request不返回地形状态，注册/eligibility到期、版本去重、事务/复原和64事件缓存行为留待SW-02/03。
独立预期先于候选保存为固定JSON，不由候选源码反算，不新增Hash。

45组输入4接收/41拒绝、5请求语法、16组/7条未来事件预期已保存；新增21项/全仓670项通过，
见[EXP-20261028-008](../experiments/2026-10-28-m5-fixture-contract.md)及[合同](M5_SW01_CONTRACT_20261028.md)。
默认latest/M2/M3/M4不导入地形或GIS，M5选型仍拒绝；公共消息、SensorBundle及占据/应用链不变。
恢复为停止离线检查，新run重新验证输入，不写回或清理历史载荷；尚无候选状态需要迁移。
下一项SW-02为显式独立地形候选/私有回放，ROS/公共协议和DEM占据融合仍须另行确认。

## ADR-038 2026-10-28 独立地形候选与整版事务

状态：用户继续授权后M5-SW-02离线合成候选已完成，公共接口/ROS与占据融合未扩展。

在mapping内显式构造TerrainFixture，不通过地图工厂、占据回放或application私有文件旁路接入。
固定SW-01地形/坐标/注册/几何与run/clock，按版本整体替换高程/掩码/质量；
输入校验、样本/质量准备及新身份目录都在临时状态完成，最后单次提交，失败保留旧状态及身份水位。
同活动版本规范载荷重复幂等、同身份异内容拒绝、退役版不复活；不刷新原采集、授权或安装时间。

高程是m制几何值，没有occupied/free推导；源高程界加注册tz界，缺任一质量时保持unavailable，
float64端点必要时向外扩一ULP，溢出或格点精度丢失安装失败。
注册过期无高程载荷；eligibility过期但注册有效可返回显式stale历史；查询不推进运行时钟。
observe_clock回退锁定本实例，disable也不会返回旧高程；恢复另建实例，实际运行采用新run。

规范JSON原载荷用于版本冲突消费者，最多64身份且每个≤16KiB，不计算Hash或遗忘淘汰身份；
这不包含全部活动/候选/输出副本内存，更不能等同RSS预算。私有回放≤64事件、独立新实例，
不读取expected字段决定业务结果；完整组合/临时峰值留待SW-03。

实际135项保存预期核对、24项新增/M5共45项/全仓694项通过，见
[EXP-20261028-009](../experiments/2026-10-28-m5-terrain-candidate.md)与
[候选说明](M5_SW02_TERRAIN_CANDIDATE_20261028.md)。
旧工厂/公共消息/在线链保持，未启ROS/Gazebo、真实DEM或研究模型，不关闭正式地图/质量/性能门槛。

## ADR-039 2026-10-28 私有地形软件组合关闭与资源口径

状态：用户继续授权后M5-SW-03已完成；公共地形协议尚未实施。

独立保存4组84事件/44查询/19拒绝及期望，64版每版16,000字节的身份载荷与16样本压力、
第64版五处提交前故障/同身份重试、满目录拒绝/reset/disable及占据逐值隔离通过。
保存输入重放的输入/结果逐值一致；新增10项/M5共55项与最终全仓704项通过。

只在私有_text校验提前拒绝字符数大于16,384的文本，防止必然超限对象先进入JSONEncoder；
原规范JSON总大小限制保持。当前片段还须考虑Unicode代理对转义，最坏12×16,384+2字节。
稳定身份载荷、两目录引用、旧/新/返回样本与编码片段分开统计，
不将16样本或1MiB身份逻辑限额当作完整内存/RSS、分配器峰值或正式PERF-01证据。

详见[说明](M5_SW03_TIME_RESOURCES_20261028.md)及
[EXP-20261028-010](../experiments/2026-10-28-m5-time-resources.md)。
关闭私有离线软件范围；真实DEM、公共地形ROS/应用及占据辅助融合仍另验/另审。
下一项M5-IFACE-DESIGN-01仅交生产消费、完整公共合同、兼容恢复与验收具体方案，
实际新增公共字段/消息/服务/客户端/显示前须另确认，在线默认入口保持。

## ADR-040 2026-10-28 公共地形查询/状态/记录具体提案

状态：M5-IFACE-DESIGN-01设计已交付；实际公共类型与运行实施待确认，未改变公共运行协议。

选择独立消息包4消息/1服务，地形层与占据层并行；不向旧SensorBundle、OccupancyObservation、
MapSnapshot、MapQueryResult或Uncertainty添加字段。明确float64高度/绝对界、availability flags、
源采集/授权/安装/evaluation时间、实例+revision绑定、独立状态心跳和安装错误。
Provider只订阅基础设施clock，注册/run来源绑定须显式装配与图审计，不订阅定位/传感器或训练监督。

拟议live层明确拒绝未来请求及当前注册失效时的历史高程，并以实际evaluation补充到期判断；
这不改变私有离线query语义，也不是已经实现的门控。客户端要求单个未完成调用和墙钟期限，
不把等待服务期限冒充调用取消，不把latched状态或重启后的相同revision当作当前同一版本。
首个ROS实现仅启动装载一版；公共记录单独定义有界dataset/事件，缺输入/截断严格incomplete。

具体字段/生产消费/兼容恢复、16组待执行验收及SW-01/02/03分工见
[提案](M5_IFACE_DESIGN_20261028.md)，审计与74项既有定向通过见
[EXP-20261028-011](../experiments/2026-10-28-m5-interface-design.md)。本轮只改文档，不生成新类型或启动ROS。
下一项SW-01按具体新增清单确认后先做消息/codec/记录合同离线验证；实际Provider/ROS与客户端/显示另分步验收。
真实DEM/基准/质量与占据融合、研究模型质量、正式M5/Phase 4和PERF-01门槛保持。

2026-10-28后续实施更新：用户已明确授权M5-IFACE-SW-01所列4.msg/1.srv及配套离线范围。
新增独立消息包与`ufm_terrain_contract`，公开逻辑合同放在该无运行副作用的共享包中，
不预先创建尚未实施的Provider；mapping仅增加dataset包装/Context投影与recording结构校验。
这是ADR-040的SW-01实施，不扩展旧公共字段/包运行依赖或改变五层架构。
字段、记录schema、规范空槽、独立编码/字节限额见[实施合同](M5_IFACE_SW01_CONTRACT_20261028.md)，
真实生成消息与独立预期/29项定向/733项全仓验证见
[EXP-20261028-012](../experiments/2026-10-28-m5-interface-contract.md)。
Provider/实际ROS及客户端/录制回放执行/RViz继续分别属于SW-02/03；原设计时点结论保留。

2026-10-28继续实施更新：用户“继续”确认已排定SW-02，现已交付默认关闭的独立Provider/节点。
不改SW-01字段或旧占据链，仅增加实际evaluation/clock来源与存活门控、实例/pin及状态/单启动安装。
显式装配绑定run/clock/唯一发布者，图与callerid核对不冒充设备时钟映射或安全认证；不新增定位/TF权威。
坏候选保留旧版并披露拒绝，reset/注册改变/身份目录满要求新实例；实际reset恢复使用新run。
实现及观察窗口/业务槽/资源限制见[SW-02说明](M5_IFACE_SW02_PROVIDER_20261028.md)，
实际ROS28查询/15状态/38检查、旧占据兼容/清理和753项回归见
[EXP-20261028-013](../experiments/2026-10-28-m5-provider-ros.md)。
后续客户端、录制/执行回放及RViz地形仍属SW-03，正式M5/Phase 4与真实DEM/融合/资源门槛保持。

2026-10-29继续实施更新：用户“继续”后SW-03已完成独立应用客户端、公共录制/执行回放和可选RViz地形，
只消费公开合同；发现/调用/状态期限、单未完成worker和整组pin/到期切换拒绝与实例重启分别验证。
公共记录v1字段不变，不能无损表达的来源错误/无结果query/并发busy明确incomplete，不用隐藏元数据兜底；
严格回放独立执行Provider，对外原实例为recorded身份，播放器另有会话ID。
live与recorded Marker分开，不画no-data零高程，不新增定位/TF权威或占据融合。
边界与实际774项/ROS/RViz/旧场景证据见[交付说明](M5_IFACE_SW03_DELIVERY_20261029.md)、
[EXP-20261029-001](../experiments/2026-10-29-m5-terrain-delivery.md)。
M5公共合成接口三步软件范围关闭；按总体计划下一项先做Phase 5软件组合场景/需求矩阵设计，
不重启外部数据阻塞任务，真实DEM/质量/机载资源与完整M5/Phase 4/5门槛保持。

## ADR-041 2026-10-29 Phase 5软件组合场景设计与验收分界

设计交付时状态：P5-DESIGN-01具体设计已交付；当时P5-SW-01—03计划，新组合未实现或运行。

选择以公开收据联合验证现有层间失效/老化/恢复，先保存独立输入与预期，再做实际消息往返和组合ROS。
paired-M1完整功能级链与显式逆观测M4配置分开，禁止将placeholder占据域直接送累计fixture；
独立地形可共享时钟但没有Gazebo/Scene共同地理注册时不作空间融合或叠图。
IR缺失无Bundle与可信后端失败unavailable分别验收；不可信上下文拒绝，均不能创造free。

保留实现差异：旧M1按请求时间老化，不等价于地形的墙钟存活/reset门控；旧MapQueryClient
没有主动调用期限，测试只以子进程隔离观察阻塞，不未经具体评审重构生产接口。
公共地形录制64事件计入每个clock，短记录与长时场景分开；v1不可表达失败保持incomplete，
不扩字段、不静默截尾或拼接生命周期来取得通过。

15项源码事实、三类配置、九组待实施场景、REQ-01—14覆盖与SW-01—03分工见
[具体方案](PHASE5_SOFTWARE_COMBINATION_DESIGN_20261029.md)，本轮76项既有定向与文档审查见
[EXP-20261029-002](../experiments/2026-10-29-phase5-combination-design.md)。
这是总体计划内提前软件设计，不恢复用户暂缓的质量研究，不关闭真实DEM/占据融合、
机载资源、PERF-01或完整Phase 4/5；本轮未改变公共协议/五层架构或启动新运行。

2026-10-29后续实施更新：用户继续后P5-SW-01已实现tests私有调度/预期及有界schema，
先保存独立expected与完整输入，再从磁盘读取做真实生成消息往返；没有候选输出生成答案。
沿既有worker规则分开独立deadline与较新busy抑制旧输出子例；owner/封存数量作为declared，
不冒充旧公共消息字段或增加application私有缓存读取。只改tests与配套文档，不改公共协议/业务入口。
九组37子例、253事件、742次序列化、31项新增与全仓805项通过，见
[输入合同](P5_SW01_INPUT_CONTRACT_20261029.md)、[EXP-20261029-003](../experiments/2026-10-29-phase5-input-contract.md)。
这不是组合运行或Provider/地图累计验收；下一项SW-02实际测试装配/ROS，SW-03原生图与清理交接。

2026-10-29再后续实施更新：用户继续后SW-02已完成tests专用源/故障/观察装配，
用原有业务入口实际执行A/B链与两种独立公开回放，不改变消息/默认入口或业务算法。
真实getBusInfo屏障补齐两个业务/观察消费者；诊断按parent_sample_id关联。
同步地图调用的外部隔离先预热，再在服务真实进入后计500ms，受控终止/回收该测试子进程，
不把外部取消等价为MapQueryClient新增deadline。墙钟调度延迟另存，不延长地形1s期限。
实际33例/216项比较、公开收据回放、旧默认入口与813项轻量回归见
[SW-02交付](P5_SW02_ROS_COMBINATION_20261029.md)、[EXP-20261029-004](../experiments/2026-10-29-phase5-ros-combination.md)。
保留初次装配失败与审批超时/重试事实；只关闭A/B软件范围，下一项SW-03执行S09/C原生图/全矩阵交接。

2026-10-29后续SW-03实施更新：补齐冻结S09/C，实际注册冲突clock、错误消费remap及foreign run，
由实际图/ready身份/TCPROS目的节点拒绝；rospy基础设施clock订阅允许但不放宽业务订阅边界。
旧run先实际建立地图与地形pin，新run重启业务节点并核对revision 0、新实例和旧pin拒绝。
哨兵由父监督器独立持有，子例正常/故障清理后须仍存活；宿主/proc另核对实际进程无残留。
原生场景与地形分Master/分窗，未注册地形不叠图；C聚合显示明确用260s监督预算，
内部110s/90s包含原生入口既有预算，普通A/B与负向C仍45s，不冒充性能或业务期限调整。
源码/冻结合同相同的既有A/B收据重新对账，本轮不重跑33例；四例C与其合计37例/228项通过，
新增6项及819项全仓通过，见[SW-03交付](P5_SW03_NATIVE_DELIVERY_20261029.md)、
[EXP-20261029-005](../experiments/2026-10-29-phase5-native-delivery.md)。
两次初始测试设施失败保留；冻结合成软件工作包完成，正式Phase 4/5及真实质量/资源/DEM门槛保持。

## ADR-042 2026-10-29 软件交付整理与运动场景的时间/状态权威

状态：DELIVERY-SW-01与SIM-MOTION-DESIGN-01已完成；运动SW-01—03为计划，协议/运行未实现。
用户确认先整理报告交付，再设计PX4/JSBSim场景运动联动；不返回暂缓的真实数据/模型质量任务。

交付清单记录实际HEAD d96d443及大量dirty/untracked范围，单一提交不冒充完整release。
已有37例矩阵、819项回归与原生八图分别标来源，报告不合并不同运行或把旧测试写成本轮重跑。
不外部归档/打包依赖、不提交/推送；ENV-03保持未完成。

当前PX4状态入口固定estimated并自带clock，静态Gazebo场景另有clock/ground_truth，
直接拼接会造成状态、时钟、原点及采样时刻混用。选择显式jsbsim_scene_truth新模式：
本仓薄宿主持有同一FDM并复用已有桥接类，Gazebo暂停并受控步进，实际Radar/IR采样ACK后
才提交唯一公共clock/真值状态。原始LastMeasurementTime不改写，不用最新pose覆盖历史观测。
旧估计入口及静态场景默认不变，新模式不fallback；唯一odom→base_link仍由state_adapter发布。
质心/ENU注册与杆臂速度明确记录，不把真值功能验证当作PX4估计定位或实机标定质量。

后续拟独立场景推进2.msg/1.srv、严格codec与有界握手；先冻结输入/独立预期再验证真实线格式，
随后验证真实引擎/受控相机线程握手，最后接感知地图与原生窗口。
若World::Step与相机完成确认不能满足设计，保留失败并修订方案，禁止改戳或双自由clock规避。
首版无解锁/起飞/航点/offboard和控制器，不恢复研究模型/训练/真实DEM或正式PERF-01。
16项源码事实、12组未来验收、工作包和限制见[具体设计](SIM_SCENE_MOTION_DESIGN_20261029.md)，
本轮57项核验、64项既有定向与地形公开执行回放见
[EXP-20261029-006](../experiments/2026-10-29-software-delivery-motion-design.md)。

2026-10-29后续SW-01实施更新：按用户继续授权，独立uav_fusionmap_sim_scene_msgs生成2.msg/1.srv，
不改旧消息/codec/launch。公开SceneFrame固定有效真值目标，terminal仍走原AircraftState失效链，
其实际真值传播修补留SW-02，不把terminal几何混入有效推进帧。
响应逻辑None由明确bool与规范空槽承载，失败可保留当前请求的部分应用/采样，但accepted=false不能推进。
时间/step严格整数；物理响应绑定采用位置/速度/角速度1e-9、四元数符号等价1e-12，仅校验不修改值。
新codec补齐嵌套旧质量无效槽和字节类型检查，genpy前先扫描有界线格式，旧兼容行为保持。
固定profile/FDM输入只做有限值/时间网格/旋转检查；独立坐标oracle不冒充实际FDM转换器。
20组保存字节与真实生成消息一致、26项新增/全仓845项通过；审查中修补证据防覆盖后另开新目录复验，
见[SW-01合同](SIM_MOTION_SW01_CONTRACT_20261029.md)、[EXP-20261029-007](../experiments/2026-10-29-sim-motion-contract.md)。
下一项SW-02实际引擎/受控渲染握手，正式阶段、研究质量、DEM及资源门槛不变。

2026-10-29 SW-02实施更新：同一FGFDMExec由本仓宿主持有，重新链接已有桥接源到独立构建目录；
固定ECEF/初始大地纬度ENU与质心FLU注册，原始时间和整数步同时记录，旧默认入口不变。
SceneFrame通过同进程基础设施邮箱同步安装并发布同内容ROS镜像，避免元数据回调竞争；
不在邮箱交换点云/图像或跨层业务结果，采样完成ACK仍经真实ROS回路校验来源/身份/时刻。
Ray自动更新与暂停world的竞争由真实第二帧失败证实，改为world四子步完成后的真实强制Ray更新；
Camera内部1kHz准备缓冲、公共整100ms/10Hz发布，LastMeasurementTime、首帧和冻结门槛均不改。
末帧先排空有效state/TF再发非几何terminal，SceneStream清空旧pending并锁定，失败不能补clock。
250步/10对/20 ACK、运行期第250步丢IR回执停止与清理、856项回归及旧估计/静态入口通过；
首采样立即故障时PX4启动中断255的两次完整用例仍保留失败，不通过放宽退出码隐藏。
文件、真实原始载荷对账和失败见[SW-02交接](SIM_MOTION_SW02_ENGINE_20261029.md)、
[EXP-20261029-008](../experiments/2026-10-29-sim-motion-engine.md)。下一项SW-03端到端地图/回放/原生窗口，
不据本轮关闭全部运动用例、受控飞行、真实质量、DEM或正式资源门槛。

2026-10-29 SW-03交接更新：运动模式显式要求SceneStream精确pose，旧默认≤10ms历史pose策略保持；
首轮真实链路发现5帧使用早4ms pose后保留失败并收紧新模式，不扩大等待或改戳。
同FDM→真实Radar/IR→Bundle→placeholder→M1→公开query/replay和原生Gazebo/RViz实际通过，
10组/14查询/独立回放、首采样与运行期ACK故障、第二clock冲突、新run恢复和History清空均有证据。
无回波不产生free，地图服务仍按显式query_timestamp老化；History是显示状态，不是服务liveness门。
首采样PX4关闭严格区分shutdown客户端255和daemon退出0，保存两者，不以客户端断IPC掩盖daemon状态。
下一项先设计多场景运动回归和遮挡/无回波预期，不扩大飞行窗口或加入控制指令。

## ADR-043 2026-10-29 有界多场景运动的独立几何与空观测判据

状态：已完成（具体设计）；主责任：simulation_engineer；新增多场景尚未实施。
依据：[具体方案](SIM_MOTION_SW04_MULTISCENE_DESIGN_20261029.md)、
[EXP-20261029-010](../experiments/2026-10-29-sim-motion-multiscene-design.md)。

固定motion profile v1继续逐字段匹配；新建独立测试清单枚举9核心用例及3个兼容回归，
不扩公共消息/服务字段，不静默改变旧场景/入口。各case保持同一FDM、1秒/250步、
原时间与唯一clock/state/TF，无控制指令或新监督通道。

现有world生成器自动添加ground，清空objects不等于无回波；新空碰撞域必须明确去地面，
以真实零点Ray、有效IR/ACK贯通空占据/快照/query。有效空观测推进header/revision，
未命中cell仍无证据，旧cell证据时间不刷新，更不能解释为free。
独立原始FDM坐标/box最近相交核验补足下游自洽检查；几何切换仅在暂停且无pending事务边界，
真实collision/visual和时间读回确认，不丢点伪造、不额外推进world刷新相机。

按SW-04A清单/预期/实际线格式、SW-04B装配/屏障、SW-04C矩阵/窗口/恢复交接推进。
每case收据16MiB/每流512、120s等原界保持，另设全套产物/墙钟预算；逻辑预算不等于RSS/PERF。
本次54项既有定向、13探针与20组真实字节/17旧定义通过，仅关闭设计，正式阶段门槛保持。

2026-10-29 SW-04A实施更新：新增独立测试清单/有界校验与7具名几何模板，
旧固定profile/公共协议/入口不放宽；测试侧先保存独立姿态/box/空图/TTL/故障预期，
77组协议字节与真实genpy一致，36组旧公共消息往返、18合成源转换通过。
验证器拒绝缺项/重排输入及部分证据复用，不把漏验当完成；25份定义与7份旧配置入口逐值保持。
新增23项、66运动定向/885全仓通过，见[SW-04A合同](SIM_MOTION_SW04A_CONTRACT_20261029.md)、
[EXP-20261029-011](../experiments/2026-10-29-sim-motion-multiscene-contract.md)。
这只是离线合同，不是新真实空回波/轨迹/窗口或资源验收；下一项B装配/屏障，再C最终矩阵。

2026-10-29 SW-04B实施更新：新增显式case入口/IC/SDF装配、S07标准类型几何端点与共享事务锁，
仅暂停/无pending且step100/225时切换；实际collision/具名visual/标准model读回及时刻一致。
S06真实零点→空图/unknown、S07五空帧/旧证据TTL/返回、S08第125步Radar ACK故障及旧默认入口通过。
独立核验发现三处问题并保留失败：原始矩阵与单位旋转比较、Link父visual误计、48近边缘数量假设。
源矩阵保持原1e-9界，独立极分解后按1e-12比较单位旋转；visual按唯一具名对象读取，不弱化几何检查。
原48条数量假设在S07末帧63条时失败，不提高误差容差或回写预期。后续新run明确冻结
strict_all_rays_no_exemptions_v1：所有边缘同样严格匹配名义最近面/命中集合/点序及原5e-6rad/0.011m，
豁免始终0，近边缘数只诊断，替代旧可选边界分支/数量门槛；旧清单48字段保留兼容。
新增11项、77运动定向/896全仓通过，25份定义保持；见[SW-04B交付](SIM_MOTION_SW04B_ENGINE_20261029.md)、
[EXP-20261029-012](../experiments/2026-10-29-sim-motion-multiscene-engine.md)。
只关闭真实定向机制软件范围；最终同源码9核心/3兼容、原生阶段图和完整阶段门槛仍未完成。

2026-10-29 SW-04C交接更新：同一423份源码文本冻结下9核心/3兼容通过，
84组业务/121查询、75帧box解析零豁免、独立回放、S08实际身份→S09恢复及14阶段总图/12 viewport交付。
四轮实际失败保留：极分解与Markley估计不同、旧gamma覆盖theta、S05视场离开后的合法零点、
RViz五帧显示范围掩盖返回Camera；每次修正后新目录整套重跑，不拼接部分收据。
测试侧现以独立标量Markley估计保持原1e-12比较界，原始矩阵1e-9门禁/源值不变；
仅生成的非零pitch IC省略冲突gamma，不改第三方源IC或冻结角度。
仅新多场景RViz视图设Median window=1；实采时间/32FC1、业务合同和旧默认视图配置不变。
每例/全套预算含独立回放目录与共享构建；逻辑/产物观察不能代替RSS、功耗或正式PERF。
新增7项、运动84项/全仓903项通过；全部尝试364自有PID无残留，旧25份定义保持。
见[SW-04C说明](SIM_MOTION_SW04C_DELIVERY_20261029.md)、
[EXP-20261029-013](../experiments/2026-10-29-sim-motion-multiscene-delivery.md)。
这只关闭1秒无控制软件交接；下一项只做受控飞行具体设计，公共控制实施另按确认范围分步推进。

## ADR-044 2026-10-29 PX4受控短窗的执行器因果收据与分步准入

状态：已完成（具体提案）；SW-01—04计划，未新增控制/公共承载或运行能力。
主责任：simulation_engineer。依据：[具体方案](SIM_FLIGHT_DESIGN_20261029.md)、
[EXP-20261029-014](../experiments/2026-10-29-sim-flight-design.md)。

真实源码链已有PX4执行器写入同一FDM，但接收未绑定时序/身份、poll超时可继续旧值，
FDM Run结果未导出。故SW-04C连接/短窗不能推出严格闭环或飞行验收。
先建立私有有界IC/执行器记录与独立预期，再隔离构建只读诊断；不改第三方原源、旧宿主/profile或研究仓库。
新v2/更长准备与命令能力分步实施，复用消息生成类型也须独立codec/端点且交叉拒绝，不能静默放宽v1。
新profile拟真实地面准备30s、活动≤10s，源时钟与FDM从0留证，raw固定30.1s起，不能隐藏预热或改戳。
JSBSim IC altitude按AGL解释，ground锚点/注册另定义；原8m运动注册不变，不引入真实DEM。
最后才允许冻结PX4 STABILIZED输入、正常模式/arm并核对实际状态；不含force/绕preflight、
offboard/自主任务或地图控制。命令ACK、地面舵面响应、实际离地/姿态响应分别验收。
失败停next/锁定run/terminal，关机不假充着陆或已disarmed；新身份恢复，迟到控制不能复活旧run。

本轮19项源码事实、15项独立核验及84项既有定向/真实线格式通过；只关闭设计。
直接下一项SW-01离线私有合同，不生成新消息、运行节点、控制客户端或延长旧窗口。

2026-10-30 SW-01实施更新：用户继续后已交付[私有IC/执行器收据合同](SIM_FLIGHT_SW01_CONTRACT_20261030.md)
及[EXP-20261030-001](../experiments/2026-10-30-sim-flight-contract.md)。固定observe profile不能开启命令，
缺包显式null、float32原值/uint64微秒保存、属性读回及FDM结果/时间/JSONL连续性有界校验。
所有绑定保持unverified，control_gate_accepted固定false；这不宣称已解决真实HIL因果关联。
先冻结预期后完成8组私有JSON往返、3通道探针/100采样时刻/两条合成记录，新增25项、旧运动84项/全仓928项通过。
旧25定义/7入口/423份源码及19项设计源事实保持，无新仿真或控制；初次测试设施失败保留。
下一项SW-02隔离实际只读诊断仍≤250步/1秒，不发heartbeat/arm/manual/参数写；
ground .5m只用私有诊断，不接旧Gazebo v1。v2/40s运行与命令仍按SW-03/04门槛分步推进。

2026-10-30 SW-02实施更新：已交付[隔离桥接诊断/宿主与实际收据](SIM_FLIGHT_SW02_DIAGNOSTICS_20261030.md)，
[EXP-20261030-002](../experiments/2026-10-30-sim-flight-diagnostics.md)。源码副本只在.runtime/ros适配，
真实wire/属性/Run结果留证，bootstrap5s、250步/1s及断连接拒绝保持；不改第三方原源或发命令。
初次ASL419.7假设失败后按本模型径向定义独立计算，大地高另核对；不放宽原微米界，失败保留。
最终439份同源码两实际用例、飞行32/旧运动84/全仓935项通过，实际执行器仍0包，控制门固定false。
SW-02仅关闭诊断软件/短窗失效子范围，不能宣称正向执行器/当前周期关联通过。
据此直接下一项调整为SIM-FLIGHT-DIAG-DESIGN-02只读归因与最小补证方案，
不重复相同短测或凭诊断passed直接进入SW-03长窗/SW-04命令；未关闭的准入事实独立登记。

2026-10-30 DIAG-DESIGN-02设计更新：完成[只读归因与最小补证具体方案](SIM_FLIGHT_DIAG_DESIGN_20261030.md)，
[EXP-20261030-003](../experiments/2026-10-30-sim-flight-readiness-design.md)。
30项源核验和376个旧HIL_SENSOR解码表明需要当前run内部IMU/EKF/姿态选择/模式/混控/发送收据；
GPS不是姿态初始化的无条件前置，wire瞬时输入首428ms进入数值范围也不代表内部滤波已就绪。
拟SW-02B只在原1s内125/250步取九类topic及最后三个param show，用已有listener的n=1/不指定instance分支，
避免暂停源时等新消息；严格绑定本次PX4身份、处理native缺失/坏输出并限制查询墙钟/体积。
本轮只改文档，32项既有飞行定向通过、439份源码保持；未新增或执行客户端、采集/ULog解码或新仿真。
后续实施不改变公共字段或控制准入；实际SW-02B完成后再据证据决定下一步，不能自动扩窗。

2026-10-30 SW-02B实施更新：已交付[私有合同/有界包装/实际未通过记录](SIM_FLIGHT_SW02B_PROBE_20261030.md)，
[EXP-20261030-004](../experiments/2026-10-30-sim-flight-uorb-probe.md)。
独立预期先保存，新增6文件并仅改显式诊断入口；既有profile/第三方原源/旧25定义/7入口保持。
首probe因设备打印注释嵌套语法失败，依源码修正并补测试；第二次step125读到三实例IMU，
第二条estimator_status仅六实例标题，按原设计拒绝并停止，21查询验收未通过。
Manager::orb_exists只核对advertised，listener快照忽略copy失败，空标题不能当never published或字段全零；
源码路径不等于已取得此次内部返回码/唯一根因。所有绑定仍unverified、控制门false。
飞行49/运动84/全仓952项、旧两诊断及真实线格式兼容通过，11自有PID无残留/强制清理；失败完整保留。
直接下一项DIAG-DESIGN-03针对空实例设计独立三态诊断事件与继续/停止边界，
不改写SW-02B原验收、不重复相同probe、不放宽原预算或自动启v2/长窗/控制。

2026-10-30 DIAG-DESIGN-03设计更新：已交付[空实例三态/有界补证具体方案](SIM_FLIGHT_DIAG_DESIGN03_20261030.md)，
[EXP-20261030-005](../experiments/2026-10-30-sim-flight-empty-instance-design.md)。
新诊断拟独立schema/显式模式，旧strict与失败保持；完整、原生未发布、本次无载荷分别记录，
混合完整/空块顶层不可用，部分字段/异常文本仍立即失败；单实例无标签不猜实例/primary。
三态只描述可核对输出，不声称已取得内部errno或定位唯一根因；诊断继续不作为状态/控制放行。
18组先行验收预期、精确字段及21次原白名单/1秒/墙钟预算已定义；采集完整/载荷完整/控制门分开。
九份源文本/16项事实、旧原文严格拒绝及49项既有飞行测试通过，445源码保持；只改设计/记录/索引。
直接下一项SW-02C按此方案先冻结独立预期再实现/实际补证；本轮无新分类器/客户端模式/运行或全仓重跑。

2026-10-30 SW-02C实施更新：交付[独立三态诊断/显式模式](SIM_FLIGHT_SW02C_DIAGNOSTICS_20261030.md)，
[EXP-20261030-006](../experiments/2026-10-30-sim-flight-diagnostic-collection.md)。
先冻结18组独立预期，再实现私有事件/严格codec、有界记录器、独立阶段runner；新增6文件，仅改授权诊断入口。
新runner初次同名遮蔽ROS模块导致前检失败，改名后整套新run验证；旧测试未改，失败保留。
实际125步九topic完整采集，250步第11次estimator_status六组vel/pos比值nan触发既定拒绝；
共11查询/10合法事件，完整21次仍未通过；未把nan转成0/null或第三态继续，旧strict/失败保持。
源码显示比值可能主动以NAN表达辅助源不可用，不单凭此判数值崩溃或当前run唯一原因。
69飞行/84运动/972全仓及旧入口/实际消息兼容通过，250步宿主/wire副本独立核对、实际执行器0包，
17自有PID无残留/强制清理；全部产物保留，不发控制或增加ROS端点。
下一项DIAG-DESIGN-04先审查原生非有限质量语义/精确字段与独立隔离表示和继续/停止规则；
不改写SW-02B/C失败或放宽现有合同、白名单、1s/250步及墙钟/资源界，不自动进入v2/长窗/命令。

2026-10-30 DIAG-DESIGN-04设计更新：已交付[原生质量字段隔离具体方案](SIM_FLIGHT_DIAG_DESIGN04_20261030.md)，
[EXP-20261030-007](../experiments/2026-10-30-sim-flight-native-quality-design.md)。
只允许estimator_status的vel_test_ratio/pos_test_ratio准确nan，并分别满足同块GPS/EV速度/光流位0、
GPS/EV位置位0的固定条件时显式隔离；不把辅助源比值不可用等同整机无水平辅助或数值崩溃。
拟独立私有diagnostic.v2、质量不可用状态/原token/原因与显式模式，旧两个v1/模式/失败保持；
其他字段/错条件非有限、部分/畸形输出仍停止。采集完整、正文完整、载荷完整和控制门分开。
九份源文本/20项事实、六实例12处原文nan与同块源位、16组独立算例及69项既有定向通过，451源码保持。
本轮只设计/记录/索引，未实现新codec/fixture/模式或启仿真、重跑全仓。
下一项SW-02D先冻结20组独立预期再实施和有界补证，原21次白名单/1秒/墙钟界不变；
私有v2不等于公共Scene v2或长窗/命令能力，不据设计提高旧运行状态。

2026-10-30 SW-02D实施更新：交付[独立质量隔离/21查询采集](SIM_FLIGHT_SW02D_QUALITY_20261030.md)，
[EXP-20261030-008](../experiments/2026-10-30-sim-flight-quality-collection.md)。
先冻结20组独立预期及源/消息基线，再实施私有diagnostic.v2、严格codec、显式互斥模式及有界记录器。
仅两字段准确nan且同块固定源位满足时，以null/原token/原因一一对应显式隔离；其余非有限仍拒绝。
8份消息/4段关键源语义有具名预检消费者，漂移即拒绝；运行前后核对完整源文本，无Hash。
实际21查询/三参数和独立原文/宿主/wire核对通过，六实例12处质量不可用；
采集完整而正文/载荷不完整，六flags已读样本tilt/yaw未对齐、selected姿态缺失、实际执行器0包。
飞行92/运动84/全仓995项、旧实际入口/真实消息兼容及27自有PID清理通过；旧B/C失败不改写。
控制门false、绑定unverified，旧两个v1/公共定义/业务链/原1s界保持，不把采集通过当飞行准入。
下一项SIM-FLIGHT-INIT-DESIGN-01仅审查初始化条件/地面IC/真实动力学并交无控制准备期与SW-03衔接方案，
不重复已完整查询或自动扩窗、新IC、公共Scene v2/命令；未验证能力继续独立跟踪。

2026-10-30 INIT-DESIGN-01设计更新：交付[无控制初始化准备与SW-03衔接方案](SIM_FLIGHT_INIT_DESIGN_20261030.md)，
[EXP-20261030-009](../experiments/2026-10-30-sim-flight-initialization-design.md)。
24份源文本/32项核验、旧SW-02D 21事件/250条HIL_SENSOR重读及92项既有飞行定向通过，458源码保持。
完整status的生产分支证明曾完成initialiseFilter，仍不能替代tilt精对齐/选中姿态和输出准入；
143个瞬时范围样本仅428000..996000us，旧记录没有逐步地面动力学/接触，不能由此认定扩窗必定恢复。
拟新最长10s/2500步私有准备，不改IC/模型/噪声/阈值，不钳制静止或以WOW填PX4 land状态。
先INIT-SW-01冻结独立合同/84项查询与N01—24预期，再INIT-SW-02实际准备；四门分开、未就绪到界失败。
SW-03拆公共v2离线与采样装配两步，本轮未实施新合同/宿主/运行，旧入口/预算与控制门false保持。

2026-10-30 INIT-SW-01实施更新：交付[私有离线合同与有界重读](SIM_FLIGHT_INIT_SW01_CONTRACT_20261030.md)，
[EXP-20261030-010](../experiments/2026-10-30-sim-flight-initialization-contract.md)。
先冻结独立fixture/字面量及原生基线，再新增八文件，原458源码保持；旧合同/模式/公共消息/宿主不改。
新step落实源前后动力学/支柱接触、fdm.hil_sensor原输入与缺包null；新84查询独立封套复用纯块解析，
完整原文投影/typed参数/同块两字段隔离、整数/未来/倒退时间和严格总量/期限均有离线校验。
合成物理静稳、初始化和零输出门分离；未Run/失败不计成功输出，所有合成ready仍控制false/绑定unverified。
两组2500步/84查询、88次私有JSON往返，新增35/飞行127/运动84/全仓1030项及旧实际genpy兼容通过。
首轮33项/1028全仓通过后增加两边界并以新run重跑，旧产物保留；没有新FDM/PX4/daemon/ROS运行或控制发送。
下一项INIT-SW-02实现独立私有准备宿主/hook/薄运行器并按10s硬界验收，不改IC/模型/阈值或自动顺延，
公共v2/长窗/控制继续后续分步；不把软件合同或合成就绪升级为真实初始化/飞行通过。

2026-10-30 INIT-SW-02实施更新：交付[独立私有宿主与实际准备失败/故障交接](SIM_FLIGHT_INIT_SW02_PREPARATION_20261030.md)，
[EXP-20261030-011](../experiments/2026-10-30-sim-flight-initialization-preparation.md)。
新增同FDM宿主/hook、源副本隔离构建/只读查询薄装配及独立wire/物理/原文审计，旧466源码/公共定义/入口不改。
实际正常500步/2s得到78未armed全零执行器与四属性请求/读回0；原执行器时间均比本步HIL早4ms，绑定仍unverified。
第30条selector比值未用实例槽位/IMU误差槽位含8处nan，按原合同严格拒绝，30 raw/29合法事件；不放宽两字段白名单。
完整2500步/84查询、两末检查点和运行准入未通过；本轮不重跑同一正常场景或用局部静稳/零包当控制证据。
断连接及期限故障在126条/125 Run停；首次期限审计误用double精确相等，先复现再按原1ns界修正/新run通过，失败保留。
沙箱端口权限失败未启动子进程，回环执行许可后才做实际运行；未改环境/网络配置。
新增7项、飞行134/运动84/全仓1037项与旧实际入口/真实genpy兼容通过，实际case源码差异明确登记，
阶段passed=false/runtime_accepted=false与software_regression_and_fault_checks_passed=true分别报告。
下一项INIT-SELECTOR-DESIGN-01仅审查精确槽位有效性/来源/身份、不可用表示和独立观测/反例/迁移预算；
不把estimator可用实例数充作IMU设备表，不先放宽合同或启动新准备/公共v2/命令。

2026-10-30 INIT-SELECTOR-DESIGN-01设计更新：交付[精确槽位/独立设备表及迁移方案](SIM_FLIGHT_INIT_SELECTOR_DESIGN_20261030.md)，
[EXP-20261030-012](../experiments/2026-10-30-sim-flight-initialization-selector-design.md)。
available是9实例索引高水位，四槽gyro/accel误差来自各自设备ID；不以healthy=false或实例号豁免任意nan。
拟独立selector私有fixture/recording/query/observation、逐元素null/原token/原因，原物理header/step/terminal不改。
增加每检查点前后sensors_status_imu，总98项；query_records128、400ms组期限和10s/2500步等预算保持。
独立表只证明前后观测一致，不证明selector消费该消息；消费时间null/同消息验证false，选中槽有限和原初始化门保持。
24项源事实、历史500步/78零包/29事件/8处nan重读、旧严格拒绝和134项既有飞行测试通过，476源码不变。
本轮仅文档，无新codec/配置/查询/运行，原正常准备失败不回填；未重跑全仓。
下一项INIT-SELECTOR-SW-01先冻结独立预期再离线合同/纯判定，SW-02另作98项实际装配与故障交接，
不由设计/合成准入开启公共v2、长窗、命令或控制；真实数据/研究质量继续独立暂缓。

2026-10-30 INIT-SELECTOR-SW-01实施更新：交付[独立私有selector合同/纯关联判定](SIM_FLIGHT_INIT_SELECTOR_SW01_CONTRACT_20261030.md)，
[EXP-20261030-013](../experiments/2026-10-30-sim-flight-initialization-selector-contract.md)。
先保存24组独立预期/10消息/6生产源及原质量语义，再新增7文件；原476源码/配置、84入口/物理宿主和公共消息保持。
新4封套/98计划、9比值槽与4设备槽精确隔离、原文投影/有界文件和前后关联已离线实现，
选中误差缺失/表身份不明不就绪；消费时间null/同消息验证false，不冒充原子快照或周期绑定。
两组合成2500步/98事件实际文件、101次JSON往返，新28/飞行162/运动84/全仓1065及旧真实genpy兼容通过。
历史第30条只作新规则离线8处投影，原codec仍probe_native_float，原500步/29合法事件/完整准备失败不变。
本轮无新daemon查询/FDM/PX4/ROS或控制；两组合成wire为空，不作实际wire验收，阶段runtime_accepted=false。
下一项INIT-SELECTOR-SW-02单独新增98项装配并做一次新规则实际准备/故障/原始wire与关联/兼容清理，
不改400ms组期限、IC/模型/阈值或10s/2500步界，不由软件通过开启公共v2/长窗/命令。

2026-10-30 INIT-SELECTOR-SW-02实施更新：交付[98项独立装配/部分实际采集/时间拒绝交接](SIM_FLIGHT_INIT_SELECTOR_SW02_PREPARATION_20261030.md)，
[EXP-20261030-014](../experiments/2026-10-30-sim-flight-initialization-selector-preparation.md)。
新增5文件，仅修私有selector离线组合两边界：物理成功2500终态后的末组查询、跳过精确PX4资源链接且不读取，旧协议/入口不改。
实际正常59 raw/59合法事件、1007 Run/4.028s、582全零执行器；500/1000局部ready、primary4/IMU槽1，32数组缺失显式隔离。
第1008条HIL4027999us≠网格4028000，原桥接static_cast截断来源已核；源double在1ns内但错误整数戳不能接纳。
原wire/raw/manifest保留，末条未Run，未重跑正常场景；完整2500/98/双末检查点未通过，控制false/绑定unverified。
断连/期限126 raw/125 Run/20查询停止通过；新11/飞行173/运动84/全仓1076及旧1s/真实genpy兼容通过。
新三actual同源码，之后仅补tests审计/阶段/截断反例，报告列差异；stage passed/runtime_accepted=false、software_regression_and_fault_checks_passed=true分报。
下一项INIT-TIME-SW-01先冻结整数预期，仅在新的隔离发送源副本中用校验源step/原1ns界产生uint64微秒，核HIL/GPS，
先C++/字节边界再有生产修复的新准备/故障；旧默认/原源/IC/阈值/10s与预算保持，不修接收包/历史戳或启控制。

2026-10-30 INIT-TIME-SW-01实施更新：交付[隔离发送端整数时间及完整10s无控制准备](SIM_FLIGHT_INIT_TIME_SW01_DELIVERY_20261030.md)，
[EXP-20261030-015](../experiments/2026-10-30-sim-flight-initialization-time.md)。
先冻结16组独立预期/旧失败源，再新增10文件；原488源码/配置、旧adapt/宿主/入口与第三方原源保持。
只在新源副本中发送前按当前source_step/原4ms与1ns界检查double后生成uint64微秒，HIL/GPS各留原源收据；
离网格/非有限/负/越界拒绝，不做通用round/fallback或修改接收包、PX4时间、历史wire。
C++16边界/2501时刻、5016真实MAVLink探针包通过；一次实际2500 Run/10s、98查询、2509源收据、2078零包，
四门与2000/2500双末检查点通过，主实例5/IMU槽2；旧1008条失败不回填。
三actual同最终498源码，断连/期限126 raw/125 Run停止、旧1s/真实genpy兼容通过；新7/飞行180/运动84/全仓1083通过。
阶段passed/runtime_accepted=true只关闭单profile无控制准备软件范围，绑定unverified/控制false、同消息消费验证false保持。
下一项SW-03A按原方案仅离线公共v2逻辑/codec/端点合同、100采样点/真实生成消息交叉拒绝；
不由本10s结果放行长窗/插件运行、模式/arming/严格绑定/非零因果或飞行，真实质量/DEM/正式资源继续独立暂缓。

2026-11-02 SIM-FLIGHT-SW-03A实施更新：用户已明确授权本范围及基线/阶段Git提交，
完成[公共flight v2离线合同/严格codec](SIM_FLIGHT_SW03A_CONTRACT_20261102.md)、
[EXP-20261102-001](../experiments/2026-11-02-sim-flight-v2-contract.md)。
先保存独立输入/100点表/边界拒绝及245组v2字节、20组旧字节，再实现同场景包内ufm_flight_contract；
只复用旧纯字段校验/公开state转换，25消息定义、v1合同、旧入口/原生源码保持。
冻结ground [0,0,.5]/jsbsim_cg_to_flight_enu_v1、4ms/10000步、30.1..40秒采样及三独立端点名称/类型，
不实现端点、节点/客户端/原生插件或运行新长窗。
发现SceneStepResponse外层无版本：无applied_frame失败响应无法在不改布局/v1的条件下区分版本。
决定v2仅接受带真实已应用v2帧的响应；应用前失败由SW-03B报服务错误，不补造applied_frame，
应用后失败保存真实帧和部分采样收据。旧v1无帧失败仍保留；所有合法v2字节因此可被旧v1拒绝。
28项新定向、245真实genpy/20旧字节双向拒绝、59文件逐文本保护通过；本轮基线1090、最终1118项全仓通过。
直接下一项SW-03B按交付第7节另行实现原生合同、长窗无控制准备/采样屏障、唯一TF及故障/清理/兼容。
binding_status=unverified/control_gate_accepted=false保持，不自动进入SW-04或改变研究质量/DEM/正式资源门槛。

## ADR-045 2026-10-30 真实高程独立预览与显式参数化报告场景

- 状态：accepted；主责任：integration_engineer。
- 依据：用户明确授权安装高程工具，完成真实高程测试及既定场景、Radar、报告改进。
- 决定：将Python 3.8兼容的Rasterio/pyproj安装至项目隔离目录，由统一sim01入口的显式子环境加载。
  真实Copernicus DSM独立读取/查询/静态导出，不改旧M5合成合同；原始高程坐标与显示相对高度分开命名。
  原生RViz只显示明确的静态地表，不创建Gazebo地理注册或占据融合。
- Radar：新显式报告配置在几何命中后加入距离相关检测概率、漏检和基础高斯误差，保留时间、坐标、
  Doppler和任意强度含义；默认旧配置继续走原几何模式。源停止与unknown/free语义保持。
- 影响：不引入新的在线传感器、训练监督输入、公共消息字段、TF权威或飞行控制；
  沿现有运动观测链进行实际验证，相关构建放`.runtime/ros`，旧报告和实验产物保留。
- 验证：[工具/运行交付](REPORT_IMPROVEMENTS_20261030.md)、
  [EXP-20261030-017](../experiments/2026-10-30-report-terrain-radar-improvements.md)。

## ADR-044后续 2026-11-02 SW-03B无控制长窗软件交接

状态：已完成（单profile无控制观察软件范围）；主责任：integration_engineer。
用户在SW-03A后明确继续，实施[SW-03B](SIM_FLIGHT_SW03B_DELIVERY_20261102.md)，
实验见[EXP-20261102-002](../experiments/2026-11-02-sim-flight-scene-runtime.md)。
独立宿主/时间生产副本、原生v2编译策略与端点、真实长窗准备/采样屏障及唯一clock/state/TF装配已交付。
共享物理字段/原生正文纯校验与事务策略，旧封套/2500步时间函数、v1/25定义/default入口不扩大。
7000/7250/7500三个准备点重验，150只读查询，首采样固定30.1秒，40秒100组；原时刻从0留存，
准备期无观测不能解释为free，失败实际物理tick保留却不提交业务状态。
5核心同533源码、4冻结故障/3旧实际兼容、原生六图/真实IR、独立wire/查询重读/公开进程回放及1130全仓通过，
708自有PID无残留。4次工程失败/初次轻量回归错误均保留；首次旧兼容误用历史.runtime/sim-motion-build的
目录偏差明确披露，测试包装只指定隔离.runtime/ros后重验，不改变旧生产默认入口或删除旧产品。
9574零包actuator−HIL仍−4000us，未证明当前周期严格绑定/非零因果；mode/arming/离地及受控飞行未验收。
下一项先交严格绑定/非零因果的具体准入方案与独立预期，不以本次软件通过直接发命令或进入SW-04运行。
research继续fail-closed，真实设备/模型、DEM公共服务/注册/融合及正式PERF/完整阶段退出保持独立门槛。
