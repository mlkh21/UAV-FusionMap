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
