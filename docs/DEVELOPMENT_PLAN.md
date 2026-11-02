# 开发计划与阶段验收

版本：v0.2；更新日期：2026-10-28；责任角色：project_manager / Technical Lead。
状态：工程计划基线；SIM-00A/B、SIM-01A/B/C、SIM-SPEED-01及SIM-01D已完成；
PERF-01、ENV-03与完整Phase 1仍阻塞。10-05完成SENS-IR-01功能级短测和
SIM-01D独立持续性验收，不改阶段退出门槛。

2026-10-27按用户确认的审查策略实施OPT-01：先修数据正确性和失效传递，统一
配置解析、限制身份历史、提供无观察器软件入口并整理当前状态与历史。交付及回归见
[修复记录](../experiments/2026-10-27-review-repairs.md)和[运行配置说明](RUNTIME_CONFIGURATION.md)。
仿真软件交付与目标硬件/外部输入分别跟踪；PERF-01、ENV-03及M1→M2门槛和原阶段日期不变。

第二轮审查的5项遗漏另列[OPT-02修改计划](OPT02_REPAIR_PLAN_20261027.md)，状态为已完成（软件与fixture ROS范围）：
2026-10-27用户授权后，按输入/旋转/质量、业务握手与配置快照、集成验收三个批次推进；
不改变原阶段日期或退出条件。

2026-10-27用户明确允许因真实数据阻塞而提前进入下一阶段；执行顺序补充为
[跨阶段软件推进计划](STAGE_ADVANCE_PLAN_20261027.md)：P3-SW-01统一感知入口/输出契约
→ P3-SW-02有界执行/超时 → P3-SW-03软件交接 → M1占据观测回放/应用查询客户端。
研究候选质量按用户要求暂不开展。该排程作为当前下一任务优先于历史段落中的待办表述；
不更改完整阶段退出条件、原目标日期或M1→M2实施门禁。

P3-SW-01/02/03、M1-SW-02和APP-SW-01已完成本批软件交接：独立CPU故障/恢复ROS、
旧placeholder及三模式兼容通过；三组占据记录的快照/查询可复现，应用五类查询和CLI
通过，全仓469项回归，见[EXP-20261027-005](../experiments/2026-10-27-p3-m1-app-handoff.md)。
初次权限阻塞保留在[EXP-20261027-004](../experiments/2026-10-27-p3-perception-engine-worker.md)。
下一软件工作所需的[M2具体方案/试制准入提案](M2_SOFTWARE_TRIAL_PLAN_20261027.md)
已交付，用户随后已确认合成数据软件试制。M2-SW-01合成证据契约/配置及独立分数oracle
已完成：9场景/31消息、479项轻量回归通过，见
[EXP-20261027-007](../experiments/2026-10-27-m2-fixture-oracle.md)。
M2-SW-02固定合成网格累计/查询随后完成，冻结9场景/31观测一致、491项回归通过，见
[EXP-20261027-008](../experiments/2026-10-27-m2-fixed-map.md)。
M2-SW-03离线时序/TTL/滚动也已完成：3组运动场景15观测与40条限额序列、506项全仓
通过，见[EXP-20261027-009](../experiments/2026-10-27-m2-rolling-time.md)。
M2-SW-04独立ROS/回放及应用交接随后完成：15观测/9快照/14查询一致，五类状态与
旧入口通过、515项全仓回归及清理通过，见
[EXP-20261027-010](../experiments/2026-10-27-m2-ros-handoff.md)。
M3-DESIGN-01已交付[合成区间传播具体方案](M3_SOFTWARE_TRIAL_PLAN_20261027.md)：
9项真实链审计事实、3组分数算例及17项既有定向通过，未实现M3或新ROS运行，见
[EXP-20261027-011](../experiments/2026-10-27-m3-design-review.md)。
用户后续“继续”确认具体合成软件试制；M3-SW-01已完成显式profile/config与独立oracle，
10场景/43输入、19项定向及534项全仓通过，见
[EXP-20261027-012](../experiments/2026-10-27-m3-fixture-oracle.md)。
M3-SW-02固定累计随后对保存的10场景43输入预期通过，名义值逐值等于M2；
12项新增定向及546项全仓、受影响M2实际ROS/回放与清理通过，见
[EXP-20261027-013](../experiments/2026-10-27-m3-fixed-map.md)。
M3-SW-03离线滚动/TTL/淘汰/新run组合随后完成：96帧257查询4探针、15项新增定向
及561项全仓通过，见[EXP-20261027-014](../experiments/2026-10-27-m3-rolling-time.md)。
M3-SW-04随后完成独立ROS/公开占据回放/应用质量检查及旧入口交接：
19观测/13快照/19查询、155项运行检查，新增9项及全仓570项通过，五组ROS清理通过，见
[EXP-20261027-015](../experiments/2026-10-27-m3-ros-handoff.md)。
M4-DESIGN-01随后交付[Scene Map/有界子地图具体方案](M4_SOFTWARE_TRIAL_PLAN_20261027.md)：
具名固定map←odom注册、唯一cell所有权、封存/FIFO淘汰、联合原子提交及定位连续性限制；
9项审计与32项既有定向通过，见[EXP-20261027-016](../experiments/2026-10-27-m4-design-review.md)。
用户后续“继续”确认具体合成软件范围，M4-SW-01已完成显式合同、输入及独立所有权预期，
8场景41输入52查询预期实际序列化检查、24项定向及全仓594项通过，见
[EXP-20261028-001](../experiments/2026-10-28-m4-fixture-contract.md)。
M4-SW-02显式纯Python Scene候选随后对保存的8场景41输入52查询、所有权/FIFO及消息承载通过，
新增15项/M4共39项及全仓609项通过，见[EXP-20261028-002](../experiments/2026-10-28-m4-scene-candidate.md)。
M4-SW-03随后通过140帧323查询、4个后段故障和1个域隔离探针，含K=1/N=2/H=3的120帧
周期轨迹、保留项/索引/临时副本计数及保存预期重放；新增13项/M4共52项/全仓622项通过，见
[EXP-20261028-003](../experiments/2026-10-28-m4-time-resources.md)。未修改业务源码，非RSS/性能验收。
M4-SW-04随后通过显式ROS/公开占据回放/独立应用交接：15观测9快照20查询、174项检查，
五类状态/历史质量、旧M1/M2/M3/placeholder及清理通过；新增7项/全仓629项通过，见
[EXP-20261028-004](../experiments/2026-10-28-m4-ros-handoff.md)。M4合成软件工作包完成，
默认仍latest、无公共字段变化。M5-DESIGN-01已交付
[TerrainPrior/DEM具体方案](M5_TERRAIN_PRIOR_DESIGN_20261028.md)，明确基准/no-data/质量/注册、
独立地形层、生产消费与兼容恢复；未实现DEM，正式地图门槛保持。
M5-SW-01随后完成[私有fixture合同/输入校验与独立预期](M5_SW01_CONTRACT_20261028.md)，
45组输入/5个请求语法、16组/7事件预期保存，新增21项/全仓670项通过；
M5-SW-02随后完成[独立地形候选与私有回放](M5_SW02_TERRAIN_CANDIDATE_20261028.md)，
135项保存预期核对、24项新增/M5共45项/全仓694项通过。
M5-SW-03随后完成[时序/资源/失败恢复组合](M5_SW03_TIME_RESOURCES_20261028.md)：
84事件/64版/五处故障、保存输入重放与占据隔离通过，新增10项/M5共55项/全仓704项通过。
私有离线软件子范围关闭。M5-IFACE-DESIGN-01随后已交付
[公共地形具体提案](M5_IFACE_DESIGN_20261028.md)：独立4.msg/1.srv、公共记录、兼容恢复与16组未来验收，
14项源码事实/实际边界探针、74项既有定向通过；公共运行协议未扩展。
用户随后明确授权，M5-IFACE-SW-01已完成[消息/codec/记录合同离线验证](M5_IFACE_SW01_CONTRACT_20261028.md)，
29项新增定向/733项全仓轻量回归通过；随后SW-02已完成[Provider/独立ROS](M5_IFACE_SW02_PROVIDER_20261028.md)，
实际拒绝/新run恢复和旧占据兼容/清理、全仓753项通过；10-29 SW-03随后完成
[客户端/公共执行回放/RViz](M5_IFACE_SW03_DELIVERY_20261029.md)，新增21项/全仓774项、实际录制回放与旧场景兼容通过。
10-29随后P5-DESIGN-01已交付[软件组合场景与REQ-01—14矩阵](PHASE5_SOFTWARE_COMBINATION_DESIGN_20261029.md)：
分开paired-M1、逆观测M4与原生显示，九场景均为待实施，既有76项定向通过。
用户继续后P5-SW-01已完成[37子例输入/独立预期及实际线格式](P5_SW01_INPUT_CONTRACT_20261029.md)，
742次消息往返、31项新增/全仓805项通过。随后P5-SW-02完成
[33个A/B实际ROS子例/公开回放](P5_SW02_ROS_COMBINATION_20261029.md)，216项独立比较、旧默认入口及全仓813项通过；
随后SW-03已完成[S09/C原生图/故障/新run及软件全矩阵交接](P5_SW03_NATIVE_DELIVERY_20261029.md)：
本轮4例与既有A/B收据复核后合计37例/228项，原生八图/清理与全仓819项通过。
冻结软件工作包完成；下一批按第8节整理交付清单/报告，正式Phase 5尚未验收。
用户随后确认，DELIVERY-SW-01已完成[交付清单](SOFTWARE_DELIVERY_20261029.md)与
[含八图报告](REPORT_20261029.md)；SIM-MOTION-DESIGN-01已完成
[同JSBSim FDM/受控Gazebo运动具体设计](SIM_SCENE_MOTION_DESIGN_20261029.md)，16项源码事实、
64项既有定向与公共地形离线回放核验通过。直接下一项SIM-MOTION-SW-01：输入/独立预期、
独立场景推进合同/codec及线格式；SW-02/03再分步实现动力学/采样握手与原生链路交接。
此处只完成设计，未新增节点/协议或启动运动，不改变真实质量/资源及正式阶段门槛。
后续用户继续后SIM-MOTION-SW-01已完成[独立场景协议与输入/字节预期](SIM_MOTION_SW01_CONTRACT_20261029.md)：
2.msg/1.srv、严格codec/有界输入、20组实际genpy对账、26项新增及845项全仓通过，17份旧定义保持。
下一项SW-02验证同FDM坐标/运动与Gazebo受控采样ACK；当前无运行服务或飞机联动，不关闭正式阶段。
后续SW-02已通过[真实引擎/采样软件闸门](SIM_MOTION_SW02_ENGINE_20261029.md)，250步/10对/20 ACK、
运行期故障/terminal、唯一clock/state/TF及全仓856项通过，旧默认入口回归通过。
直接下一项SW-03接端到端感知地图/公开回放和原生运动窗口；首采样启动中断失败保留，正式阶段不关闭。
随后SW-03已完成[单profile运动端到端交接](SIM_MOTION_SW03_DELIVERY_20261029.md)：10组Bundle/占据/快照、
14查询/独立回放、首采样/运行期ACK故障、第二clock拒绝、新run恢复与原生六图/History通过，
新增6项、运动定向43项及全仓862项、旧入口回归通过。
下一项SIM-MOTION-SW-04-DESIGN先冻结多场景姿态/遮挡/无回波/故障恢复及资源上界；不自动加控制或延长窗口。
真实输入/正式资源证据仍缺失，不阻止该方案工作，正式退出门槛不变。

SIM-MOTION-SW-04-DESIGN随后已完成[多场景具体方案](SIM_MOTION_SW04_MULTISCENE_DESIGN_20261029.md)：
9核心/3兼容用例、独立IC/box射线/空图/TTL/故障预期、逐case/全套预算；
54项既有定向及13项只读探针通过，本轮未启动新场景或重跑全仓。
直接下一项SW-04A独立测试清单/有界校验/冻结预期和实际线格式；
再SW-04B装配/真实几何切换、SW-04C最终矩阵/原生/恢复交接；均保持1秒上限，无控制指令。

随后SW-04A已完成[独立清单/有界合同/冻结预期与真实线格式](SIM_MOTION_SW04A_CONTRACT_20261029.md)：
77组场景字节/36公共往返、18合成源转换、23新增/66运动定向及885项全仓通过；
旧25份定义和7份配置入口保持，新增多场景运行未执行。
直接下一项SW-04B实现显式IC/SDF装配、暂停几何切换屏障和场景化核验；
定向真实空域/切换/故障为机制准入，最终9核心/3兼容与原生显示留SW-04C。

SW-04B随后完成[显式装配及真实机制准入](SIM_MOTION_SW04B_ENGINE_20261029.md)：
S06零点空图、S07两次暂停几何/五空帧/返回与TTL、S08中途Radar ACK故障及旧默认回归通过；
新增11项、77运动定向/896全仓通过。保留三个真实核验失败和入口重名测试失败，
原48边缘数量假设改为固定零豁免逐射线规则，物理误差界不增加。
直接下一项SW-04C：最终9核心/3兼容、S05/S07原生阶段图、恢复/回放/预算与清理交接，
不同源码的B定向收据不能替代最终全矩阵。

SW-04C随后完成[同源码完整矩阵/原生交接](SIM_MOTION_SW04C_DELIVERY_20261029.md)：
423份冻结源码上9核心/3兼容、84组业务/121查询、75帧box逐射线零豁免、独立回放及14阶段总图通过。
新增7项、运动84项/全仓903项通过；四次真实失败与修复后整套重跑保留，原物理容差不变。
当前无真实数据条件下可推进的直接下一项为SIM-FLIGHT-DESIGN-01，主责任simulation_engineer：
只读核对同FDM/PX4执行器、IC与状态/时钟权威，形成受控短窗、控制命令边界、停止恢复及验收提案。
先交具体可审查方案，控制实现另按确认范围分步执行；本项不发解锁/起飞或延长现有窗口。

SIM-FLIGHT-DESIGN-01随后完成[具体方案/源码审查](SIM_FLIGHT_DESIGN_20261029.md)，
19项源码事实、15项只读核验及84项既有定向/实际消息往返通过，本轮未重跑全仓或执行新控制。
直接下一项SIM-FLIGHT-SW-01仅私有IC/执行器收据逻辑合同、冻结预期/小fixture及限额测试；
SW-02再做≤1秒无命令实际诊断，SW-03独立v2/新profile无控制准备，SW-04才逐门准入受限控制实验。
各步只关闭其软件子范围，受控飞行须实际离地/响应证据，不以命令ACK或源码替代。
2026-10-30 SW-01已完成[私有合同/冻结预期与有界校验](SIM_FLIGHT_SW01_CONTRACT_20261030.md)，
新增25项、旧运动84项与全仓928项通过，旧公共类型与运行入口不变。
直接下一项SW-02（计划；主责任simulation_engineer）：隔离构建实际HIL/属性/FDM只读诊断，
最多250步/1秒、不发送heartbeat/arm/manual/参数写；ground IC仅用于私有诊断，不进入旧Gazebo v1。
须保存bootstrap/缺包/终止原始证据，不能将离线unverified记录提升为控制门通过；SW-03/04依赖不变。
SW-02随后完成[实际有界诊断/断连接交接](SIM_FLIGHT_SW02_DIAGNOSTICS_20261030.md)，
正常250步/1s、断连接125次Run后停止与新增7项/全仓935项通过，控制门仍false。
实际执行器0包，新增SIM-FLIGHT-DIAG-DESIGN-02（计划；主责任simulation_engineer）作为直接下一项：
只读追踪当前未就绪链路，提出最小补证具体方案，不重复同一短窗或自动扩大窗口。
计划调整原因是缺少实际当前周期回包关联，而非真实数据/模型质量缺失；SW-03长窗与SW-04控制不开放。
DIAG-DESIGN-02随后完成[只读归因与最小补证方案](SIM_FLIGHT_DIAG_DESIGN_20261030.md)，
30项源核验、376个旧HIL_SENSOR离线检查及32项既有飞行定向通过，本轮未改代码/启新仿真或重跑全仓。
直接下一项SW-02B（计划；主责任simulation_engineer）：原1s/250步内增加本次PX4有界uORB观察，
9类topic×2检查点+3参数show，共21次；先冻结预期/校验，再一次实际probe和相关回归。
只读取既有daemon，不安装ULog依赖、写参数或扩窗；依据实际内部收据继续归因，不能把GPS缺失定为唯一原因。
SW-02B随后完成[软件/实际未通过交付](SIM_FLIGHT_SW02B_PROBE_20261030.md)：
私有查询/快照、完整原生解析及有界POSIX包装已实现；实际step125只取得三组积分IMU，
第二条estimator_status六实例无字段，按既定规则停止，21查询验收保持未通过。
49飞行/84运动/952全仓、旧normal/disconnect与真实genpy兼容通过，不替代新probe验收。
直接下一项DIAG-DESIGN-03（计划；主责任simulation_engineer）：就该实际空实例问题设计三态/独立诊断事件，
明确精确语法与继续/停止规则；保持命令白名单、原1s/250步及墙钟预算，不静默降级或自动进入SW-03/04。
DIAG-DESIGN-03随后完成[空实例三态具体设计](SIM_FLIGHT_DIAG_DESIGN03_20261030.md)：
九份源文本/16项核验与49项既有定向通过，445份源码保持；未实现新合同/模式或启仿真。
直接下一项SW-02C（计划；主责任simulation_engineer）：先冻结18组独立原文/三态预期，
实现独立diagnostic事件、显式--uorb-diagnostics及有界采集；旧strict和SW-02B失败保持。
混合完整/空块逐实例保存，部分字段/畸形/armed/身份/期限错误停；采集完整与载荷完整分开，控制门仍false。
随后一次新增观察规则的实际21查询及旧诊断/线格式/轻量回归，不扩大命令白名单或1秒/墙钟/资源界。
SW-02C随后交付[三态软件与实际NaN停止记录](SIM_FLIGHT_SW02C_DIAGNOSTICS_20261030.md)：
先冻结18组预期，新增20项/飞行69项/运动84项/全仓972项及旧实际入口/线格式兼容通过。
125步九topic和250步IMU可读，第11次状态含12处nan严格拒绝，11查询/10合法事件，完整21次未验收。
同源宿主/wire副本独立审计250次Run/1s且执行器0包；17自有PID清理，不改变原strict或控制门。
直接下一项DIAG-DESIGN-04（计划；主责任simulation_engineer）：审查原生非有限质量字段语义并交显式隔离/继续停止方案，
不重跑相同失败或扩窗/控制，不将NaN默认为0或空载荷；原失败与完整采集门槛保持。
DIAG-DESIGN-04随后完成[两字段源语义/条件隔离具体设计](SIM_FLIGHT_DIAG_DESIGN04_20261030.md)：
九份源文本/20项核验、六实例12处nan及同载荷标志核对、16组独立掩码算例/69项既有定向通过，451源码保持。
直接下一项SW-02D（计划；主责任simulation_engineer）：先冻结20组独立原文/隔离预期，
实现私有diagnostic.v2与独立显式模式，仅在两字段准确nan及同块源条件满足时显式标质量不可用。
旧两个合同/失败保持，采集/正文/载荷完整分开；其他非有限、错条件、畸形/身份/armed/期限错误仍停止。
随后一次新增规则的实际21查询及旧入口/线格式/轻量回归；原白名单、1s/250步及墙钟/资源界不变。
此v2是私有记录版本，不实施公共Scene v2、长窗或命令，不能由隔离采集通过推导受控飞行准入。
SW-02D随后完成[私有质量隔离与实际有界采集](SIM_FLIGHT_SW02D_QUALITY_20261030.md)：
先冻结20组独立预期/源基线，21次查询/三参数及原文独立重读通过；六实例12处缺失显式隔离。
采集完整但正文/载荷不完整，六flags已读样本tilt/yaw未对齐、selected姿态缺失、执行器0包。
新增23项/飞行92项/运动84项/全仓995项及旧实际入口/消息兼容通过，27自有PID清理；旧B/C失败不回填。
直接下一项SIM-FLIGHT-INIT-DESIGN-01（计划；主责任simulation_engineer）：只读审查地面IC/真实动力学、
同FDM/IMU、初始化/收敛条件与源时间/墙钟/停止界，交无控制准备期及SW-03衔接的具体方案。
明确是否需要独立新profile/窗口与验收；不假设扩窗必定恢复，不重复完整21查询或实施新IC/公共v2/命令。
随后INIT-DESIGN-01完成[无控制初始化准备具体方案](SIM_FLIGHT_INIT_DESIGN_20261030.md)：
32项源码事实/旧wire重读及92项既有定向通过，明确7检查点/84查询、N01—24验收预期与四门独立判定。
直接下一项INIT-SW-01（计划；主责任simulation_engineer）先冻结独立字面量，实施新私有合同/fixture和有界离线测试，
旧解析器/公共消息/入口保持，不启动新FDM/PX4。INIT-SW-02再验最长10s/2500步私有无控制准备，
SW-03A公共v2离线及SW-03B采样装配另分步；这些新运行范围尚未实施。
随后INIT-SW-01完成[私有离线合同/文件清单](SIM_FLIGHT_INIT_SW01_CONTRACT_20261030.md)：
先行独立预期、两组2500步/84查询/88次JSON往返与四门分离通过；35项新增、飞行127/运动84/全仓1030项及旧真实消息兼容通过。
原458源码保持，无准备期运行；直接下一项INIT-SW-02（计划；主责任simulation_engineer）按独立新profile实现私有宿主/适配/薄装配，
先离线故障再无控制准备、断连接/期限停止与实际wire/物理/查询/清理对账，到10s界未就绪即失败。
不改IC/模型/噪声/阈值、不放宽旧入口预算或自动启公共v2/命令，四门与严格绑定/控制分别验收。
随后INIT-SW-02已交[独立宿主/部分实际运行与故障兼容](SIM_FLIGHT_INIT_SW02_PREPARATION_20261030.md)：
正常500步/2s及78全零执行器/属性读回，第30条selector含nan严格拒绝，完整2500步/84查询未通过。
断连接/期限停止、飞行134/运动84/全仓1037项及旧实际入口/消息兼容通过，不提升控制/完整准备状态。
下一项INIT-SELECTOR-DESIGN-01（计划；主责任simulation_engineer）先审查selector estimator/IMU槽位的来源/身份、
精确隔离条件/缺失表示、独立观测/反例与schema/查询预算迁移；不直接放宽合同或重复正常run。
随后INIT-SELECTOR-DESIGN-01已完成[具体设计](SIM_FLIGHT_INIT_SELECTOR_DESIGN_20261030.md)：
24项源事实、历史流/8处nan与原严格拒绝重读、134项既有飞行测试通过，476源码保持；仅文档。
直接下一项INIT-SELECTOR-SW-01（计划；主责任simulation_engineer）：先冻结S01—24预期及源基线，
新增独立私有selector合同/有界codec/98项计划/纯关联和四门判定，保留原84/物理合同/入口，不启动运行。
再INIT-SELECTOR-SW-02单独新增98项装配与实际有界准备/故障/清理交接，四门按实测分报，
不改IC/阈值/10s界；表观测不证明同消息消费或严格控制绑定，公共v2/命令另属后续。
随后INIT-SELECTOR-SW-01已完成[独立离线合同/七文件](SIM_FLIGHT_INIT_SELECTOR_SW01_CONTRACT_20261030.md)：
24组先行预期、两组2500步/98事件、101次JSON往返及新28/飞行162/运动84/全仓1065项通过，原476源码保持。
直接下一项INIT-SELECTOR-SW-02（计划；主责任simulation_engineer）新增独立98项薄装配，复用原物理宿主/硬门，
先离线故障再一次新规则准备与断连接/期限、原wire/物理/关联/旧入口兼容及自有进程清理；
原400ms组期限/10s/2500步及IC/阈值保持，结果分门报告，不由离线通过开放控制或公共v2。
随后INIT-SELECTOR-SW-02完成[实际部分证据/故障与兼容交接](SIM_FLIGHT_INIT_SELECTOR_SW02_PREPARATION_20261030.md)：
59合法查询/1007 Run/582真实零包、500/1000局部就绪；第1008条发送端double微秒截断少1us，原界拒绝且未Run。
新11/飞行173/运动84/全仓1076和旧实际/真实线格式兼容通过；完整准备仍未通过，未重跑正常场景。
直接下一项INIT-TIME-SW-01（计划；主责任simulation_engineer）按该交接具体范围冻结整数预期，
只新增隔离源副本发送前网格量化/HIL与GPS源时核对及显式构建/入口，旧默认/原源/IC与所有预算保持。
先实际C++/MAVLink边界再有实质修复的新准备和故障/兼容/清理，不改接收包或历史原戳、不再设计selector缺失豁免。
随后INIT-TIME-SW-01完成[隔离整数时间生产/完整10s准备交付](SIM_FLIGHT_INIT_TIME_SW01_DELIVERY_20261030.md)：
16先行预期/5016真实探针包，实际2500 Run/98查询/2509源收据/2078零包、双末检查点及四门通过；
新7/飞行180/运动84/全仓1083与实际故障/旧入口兼容通过，原488源码保持；仅本单profile无控制准备门关闭。
直接下一项SIM-FLIGHT-SW-03A（计划；主责任integration_engineer）按原公共v2方案，先独立预期/100采样点，
新增离线逻辑/codec与端点合同、复用已有生成类型、真实消息往返与v1交叉拒绝；不启动长窗/插件节点或控制。
SW-03B再验30/40s采样/唯一TF/原生窗口，SW-04再验严格绑定/非零因果/arming/离地，不从准备通过自动放行。

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

截至2026-10-26，[Phase 2软件双图整合验收](../experiments/2026-10-26-phase2-sensor-integration.md)
已用独立在线/训练ROS run确认fake Radar/IR的值级传递、SensorBundle到占位地图、
无训练LiDAR泄漏，以及训练监督时空/unknown边界；386项轻量测试通过。此为
软件fixture子范围，不改原退出门槛：真实驱动、设备记录、外参和时钟映射仍待输入，
独立IMU交付未由本次运行覆盖；完整Phase 2保持进行中。
同日[IMU源链门禁](../experiments/2026-10-26-phase2-imu-gate.md)确认归档
HIGHRES_IMU六轴确有源数据，但现行simulation只使用其时间戳推进/clock，
没有独立ImuSample出口；源边界门禁和388项轻量回归通过。
下一步需先确认[公共承载、坐标/质量合同及兼容恢复](PHASE2_IMU_GATE_20261026.md)，
本轮不改公共消息或把源遥测算作独立IMU交付，阶段日期及退出条件不变。
用户随后按上述[接口门禁](PHASE2_IMU_GATE_20261026.md)确认继续，
[可选IMU独立ROS旁路](../experiments/2026-10-26-phase2-imu-optional-ros.md)已新增
ImuSample编码并通过开启/关闭双图、旧SIM-01 fixture和394项轻量测试；
仅功能级虚拟pilot点传输子范围完成，完整Phase 2仍待真实源比力/安装位置核对、
真实Radar/IR驱动、设备外参/时钟和质量来源，不改原计划日期及退出门槛。
随后[EXP-20261026-004](../experiments/2026-10-26-phase2-imu-live-px4-jsbsim.md)
补上真实PX4/JSBSim进程的虚拟pilot点IMU在线短测：独立原始HIGHRES_IMU与
两路ROS IMU 2300个有效样本逐值/身份/时间匹配，旧fixture及399项轻量回归通过；
这仅关闭虚拟源链短测缺口，不关闭内部物理真值对照、真实安装标定、跨设备同步、
真实Radar/IR、正式PERF-01或完整Phase 2退出门槛。
再由[EXP-20261026-005](../experiments/2026-10-26-phase2-imu-physics-semantics.md)
独立JSBSim地面、早期离地、正负初始滚转四场景及源码核对确认pilot点虚拟比力
语义与EYEPOINT来源；不是PX4/JSBSim同run内部真值逐帧核对，不能替代实物
IMU安装外参、跨设备同步或真实Radar/IR输入。Phase 2仍按原退出条件进行中；
正式PERF-01与ENV-03阻塞不变。
2026-10-27继续按允许的小规模占位联调范围完成
[在线感知失效模式ROS验收](../experiments/2026-10-27-perception-mode-ros-fail-closed.md)：
disabled与research前置阻塞分别通过独立ROS图，验证不可用占据不会新增地图证据；
旧placeholder入口回归及408项轻量测试通过。只关闭软件失效传递子范围，
不提前关闭完整Phase 2/3、模型质量或正式PERF-01，也不更改阶段时间。

允许在不改变阶段门槛的情况下使用占位接口进行小规模联调。
真实感知未达标时，占位成功只证明工程链路，不能据此关闭Phase 3质量目标。
DEM排在基础地图之后；阶段延期须评审范围和时间，不能直接跳过基础阶段。
截至2026-10-04，PERF-01原定09-20预算确认日期已逾期；Phase 1的10-15
退出日期存在风险。Phase 2可以提前做有边界的传感器验证，但不得以此倒填Phase 1通过；
若门槛届时仍未满足，保留阻塞状态并另行评审日期与范围，不自动顺延或降格验收。
2027年3月仍是原交付目标，不因文档重排自动获得可实现性承诺。
2026-10-15已执行[Phase 1正式退出复核](PHASE1_EXIT_REVIEW_20261015.md)：
仿真子项已有归档通过证据，但PERF-01正式输入与ENV-03独立副本/恢复仍阻塞；
完整Phase 1未通过原目标日的退出，不自动调整本表日期或宣称Phase 2替代其验收。
当日退出复核仅同步审查状态；新日期/范围另见下述同日复审。
同日[日期/范围复审](PHASE1_DATE_SCOPE_REVIEW_20261015.md)维持原门槛：
没有可信的硬件/外部恢复可执行日期，新Phase 1退出日待输入及用户确认，
不是本表日期的自动顺延。允许提前实施的Phase 2软件验证见
[EXP-20261015-001](../experiments/2026-10-15-iface01-sens-train-audit.md)，
不改变本表Phase 2原开始日，也不解除PERF-01或ENV-03。
同日后续[EXP-20261015-002](../experiments/2026-10-15-iface-replay-training-ray-m1-resource.md)
增加只读设备JSONL回放、训练已知场景离轴false-free拒绝，以及默认关闭的
M1软件fixture进程RSS诊断；不改变阶段原日期、公共接口或正式阶段门槛，
未取得真实设备输入/目标平台资源与功耗证据，M1和Phase 1仍阻塞。

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

## 4. 下一批任务与2026-10-08优先级复核

ENV-01已于2026-09-11完成只读核查，见[环境清单](../configs/ENVIRONMENT_INVENTORY.md)。
ENV-02已于同日交付[候选版本与最小验证方案](SIMULATION_VALIDATION_PLAN.md)，
证据见[EXP-20260911-003](../experiments/2026-09-11-simulation-plan-review.md)。
SIM-00A于09-12完成依赖准备与独立构建，见[构建证据](../experiments/2026-09-12-sim00a-build.md)。
ENV-03的忽略/保存规则已落地，第二副本及恢复工作未完成且外部归档未获授权；
SIM-01A/B已完成，SIM-01C与SIM-SPEED-01已于09-17正式关闭。10-03端点短测
三条大图P99分别为58.745/78.635/53.507 ms，均未达20 ms，且物理采样时钟
不可用；10-04热点ROS短测虽通过，但现有观察器仅核对IR时间戳、尺寸和像素数量，
没有核对热点/背景数值。证据分别见[端点探针](../experiments/2026-10-03-perf01a-endpoint-probe.md)、
[热点短测](../experiments/2026-10-04-fake-ir-hotspots.md)及
[`perf01a_async_run.py`](../ros_ws/perf01a_async_run.py)。
因此PERF-01保持全项目首位，插入小范围IR数值守恒门禁；SIM-01D独立验收，
SENS-TRAIN-01在IR门禁后推进。若同一人承担多项任务，按以下次序分配时间，
不假设角色等于实际并行人力。计划变更只调整执行次序与增加验证，不改变公共接口、
已确认指标、阶段或历史结果；按根AGENTS对各实施范围分别确认。
10-05 [SENS-IR-01独立ROS值级短测](../experiments/2026-10-05-sens-ir-value-transport.md)
通过（100帧发布IR、20帧被Bundle采用且逐像素/时间/身份闭合）；额外观察订阅
仅供功能级验收，不作为PERF-01性能样本。随后完成[SIM-01D跨边界持续性验收](../experiments/2026-10-05-sim01d-continuity.md)，
有效跨度为`2400004000000 ns`，bag回读、checker、排空与清理均通过；不改变PERF-01预算阻塞。
10-06完成[PERF-01正式输入与证据预检](../experiments/2026-10-06-perf01-formal-preflight.md)：
当前x86开发机不是参考Jetson目标平台，未发现真实ARS548/Micro III Lite输入、外部功耗和设备
采样时钟证据；正式门禁仍为`reference_only`。新增预检只读取manifest，拒绝fixture频率、
仿真时间和`/clock`替代物理测量，不启动正式ROS性能运行。
10-08完成[证据内容数值预检](../experiments/2026-10-08-perf01-metric-preflight.md)：
六类JSON证据须按同一run/航速/时钟域逐样本及汇总数值对账；空文件、仅`passed=true`、
伪造或超标P99、同步/年龄、丢帧/超时和功耗超限均拒绝。未新增ROS/机载性能证据，
正式输入阻塞不变。
10-08新增[三航速大图ROS短测](../experiments/2026-10-08-perf01a-three-speed-fixture.md)
均失败：每档40 Radar/100 IR均有收据，但40 Radar全被严格拒绝、0地图闭合，
P99无有效样本；XML-RPC可选空配置的启动错误已以最小修复并保留失败记录。
须先预登记可控传输/时钟调度候选并复测严格oracle；不能据资源采样和清理成功
补写性能通过，设备和外部功耗等正式输入仍缺失。
随后[零噪声IR fixture生成候选](../experiments/2026-10-08-perf01a-zero-noise-candidate.md)
在不改5ms同步、40ms严格匹配和20ms目标下恢复35/50/70m/s三档大图功能闭合：
每档20采用/20严格拒绝及20个Bundle/占据/地图闭合；开发机回调到占据P99分别
49.703/49.834/60.720ms，均未达标。旧失败保留；下一步转向已闭合样本的实际
等待/传输分段和目标机硬件正式起止点，不重复把fake IR生成优化当作设备性能。
同日[正式证据追加审阅](../experiments/2026-10-08-perf01-evidence-audit.md)
补齐设备时钟身份、非有限误差和聚集/倒序采样负例；合成`formal_ready`仍不能
鉴定真实仪表来源，标称周期的保守帧间距门禁需等待设备抖动合同确认。
可选[70m/s匹配/线格式探针](../experiments/2026-10-08-perf01a-probe-after-fastpath.md)
的同帧联接成功但P99仍44.872ms，最慢帧IR线格式与调度混合成本清晰；
此前无探针`ready_to_encode`长尾未重现。探针有额外开销，不能用本run
宣称相对无探针优化或替正式20ms实测。
10-09[IR回调一次临时拷贝候选](../experiments/2026-10-09-perf01a-ir-decode-copy.md)
以同口径A-B-B-A四条2秒开发机ROS大图短测验证：严格oracle和地图闭合
四次全通过，端到端P99中位数降幅仅7.83%，低于预登记10%采纳门槛；
默认开关保持关闭。下一步先确认正式平台/设备/设备时钟和20ms起止点；
缺硬件时可继续同帧分析等待与ROS传输长尾，但不得改严格门限、
将探针run替正式验收、追加任意长测或把局部解码提速写成PERF-01达标。

| 编号 | 任务 | 主责任角色 | 目标日期 | 完成条件 |
| --- | --- | --- | --- | --- |
| ENV-01 | 只读核查现有OS、ROS、PX4、JSBSim、桥接、CPU/GPU及已有环境 | simulation_engineer | 2026-09-18（实际09-11完成） | 已交付安装事实、可复用资产与缺项清单；不是仿真/GPU运行通过 |
| ENV-02 | 选择并记录候选版本组合与最小仿真验证方案 | system_architect | 2026-09-20（实际09-11完成） | ADR-006决定优先验证候选；已交付维护周期、依赖处理、独立构建、状态/时钟源及步骤；ADR-P001运行冻结另验 |
| PERF-01 | 确认航速、算力、场景和接口预算（全项目第一优先级；进行中，正式输入阻塞） | Technical Lead | 原定2026-09-20，已逾期；10-15阶段复核 | [正式预检](../experiments/2026-10-06-perf01-formal-preflight.md)确认当前主机和设备证据不足，仍需20 ms正式起止点、跨设备时钟、目标平台/IR镜头/同步、资源功耗和连续性证据；原5 ms门限、严格拒绝理由与20 ms目标不变；开发机短测P99超标，不得判机载达标 |
| ENV-03 | 版本和产物管理基线（进行中；外部副本未获授权） | project_manager | 原定2026-09-20，已逾期；10-15复核 | 提交范围/流转/忽略/保存规则已落地；首次提交已有基线；第二副本及恢复验收待单独授权，未授权时仅记录本机单副本风险 |
| SIM-00A | 最小依赖准备与隔离构建（已完成） | simulation_engineer | 2026-09-23（实际09-12完成） | JSBSim/MAVROS/geoid在项目目录准备，PX4/桥接构建及依赖检查通过；未安装到系统或启动仿真 |
| SIM-00B | 无界面Rascal遥测短测（已完成） | simulation_engineer | 2026-09-25（实际09-12完成） | 用户确认初始化修复后，独立重建/消息回归/120.056秒遥测及清理通过；不解锁、不起飞 |
| SIM-01 | 最小飞行状态到ROS的记录/回放（A/B/C已完成） | simulation_engineer | 2026-10-01（A/B/C已完成） | C的故障链与短窗倍速已验收；不代替D的持续性门槛 |
| SENS-IR-01 | 同一IR帧的热点/背景数值守恒短测（已完成） | sensor_engineer | 2026-10-08计划门槛（实际10-05） | [独立ROS验收](../experiments/2026-10-05-sens-ir-value-transport.md)：按IR sample_id对齐100帧原始发布与20个Bundle采用帧，全像素、热点/背景和曝光时间闭合；旧passed=true不作为完成证据 |
| SIM-01D | 跨32位微秒边界的持续性验收（已完成） | simulation_engineer | 2026-10-15原阶段目标（实际10-05完成） | [独立长测](../experiments/2026-10-05-sim01d-continuity.md)有效跨度`2400004000000 ns`并跨越边界；实时记录、bag回读、状态/时钟和清理对账通过；不代替PERF-01 |
| SIM-SPEED-01 | 倍速缺陷修复（已完成） | simulation_engineer | 2026-10-01前（实际09-17正式关闭） | 两行修复及独立候选0.5/1/2倍九run技术矩阵通过；用户接受已披露偏差，完整保留历史记录且不尝试恢复 |
| SIM-01C | 异常与时钟场景（已完成） | integration_engineer | 2026-10-01前（实际09-17正式关闭） | F0—F7与短窗倍速验收通过；不含SIM-01D、PERF-01、高速地图、感知或LiDAR验收 |
| IFACE-01 | 定位权威、驱动载荷与业务契约细化（进行中，T-14软件子范围通过） | system_architect | 2026-10-15 | [ARS548/Mid-360型号设备时间合同](../experiments/2026-10-13-device-time-contract.md)、[设备时间记录审计](../experiments/2026-10-13-device-time-record-audit.md)和[T-14兼容镜像](../experiments/2026-10-14-t14-odom-tf.md)通过；真实设备回放/采样时钟误差、公共逐点时间、真实协方差与正式平台仍阻塞 |
| SENS-TRAIN-01 | 同场景fake Radar/IR与仅训练LiDAR监督（进行中，ROS直线/偏航和离线统计子范围已完成） | sensor_engineer | 2026-11-10原阶段目标 | [ROS偏航闭环](../experiments/2026-10-13-sens-train-yaw-ros.md)、[ROS直线闭环](../experiments/2026-10-13-sens-train-motion-ros.md)与[12场景/36记录统计](../experiments/2026-10-13-sens-train-scene-statistics.md)通过；20组ROS偏航记录含插值/无回波槽，旧入口回归及315项轻量测试通过；真实设备/规模/研究模型质量未验收 |
| MAP-QUERY-01 | 固定Local Map单点查询ROS承载（软件子范围已完成） | mapping_engineer | 2026-10-14实际完成；不改变Phase 4原日期 | [EXP-20261014-010](../experiments/2026-10-14-local-map-query-ros.md)三种fixture模式、消息构建、图隔离、并发只读和清理通过；滚动窗口、概率累计、真实输入和机载性能未验收 |
| MAP-ROLL-01 | 基础滚动Local Map（软件fixture子范围已完成） | mapping_engineer | 2026-10-14用户确认后开展；不改变Phase 4原日期 | [EXP-20261014-011](../experiments/2026-10-14-local-map-rolling.md)：整格平移、重叠/淘汰/unknown、偏航、身份/时序、断流恢复、活跃cell上限、ROS短测和固定模式回归；未关闭正式资源上限、设备时钟、概率融合或Phase 4 |
| ALG-01 | 研究后端接入前置条件清单（进行中，T-13B、ALG-01-R软件审计与现有质量否决子范围已完成） | perception_engineer | 2026-11-10 | [T-13B/ALG-01-R记录](../experiments/2026-10-23-alg-01-t13b-research-preflight.md)已核对真实launcher、候选权重/threshold、归一化结构、标定文件、参考系、环境和已有离线质量产物；当前Radar+IR候选被标记`rejected_for_integration`，缺失checkpoint-chain CLI、已验证坐标契约和UAV适配器，真实后端仍阻塞 |

### 4.1 执行顺序与验收关口

| 顺序 | 当前状态与直接下一步 | 独立门槛和证据 |
| --- | --- | --- |
| P0-1 PERF-01 | 进行中；预算、manifest及证据数值预检完成；10-08零噪声候选恢复三航速功能闭合但P99仍49.703/49.834/60.720ms；10-09 IR 借用列表 A-B-B-A仅降7.83%，未采纳为默认且四次均超20ms；下一步同帧定位等待/线格式长尾，优先确认正式平台/真实传感器/20ms起止点/物理采样时钟及功耗证据 | 保持开发机Radar回调→占据就绪P99诊断与正式设备采样年龄分开；不得改严格拒绝理由和5 ms同步门限，空P99不能判通过，不合并不同样本分位数；20 ms目标不变，达标需目标平台和资源/功耗证据。正式单run证据还必须通过[数值预检](../ros_ws/perf01_formal_preflight.py)，不把合成正例当作实测 |
| P0-2 SENS-IR-01 | 已完成；10-05独立ROS短测、像素oracle与失败目录保留 | [EXP-20261005-001](../experiments/2026-10-05-sens-ir-value-transport.md)按run/clock/IR sample_id/frame_id、采样/曝光时间、热点/背景及全图像素核对100帧发布、20个Bundle采用；`float32[]`绝对容差1e-6，严格拒绝/排空/清理通过。该观察器额外订阅，不用于PERF-01性能判定 |
| P0-3 SIM-01D | 已完成；10-05独立端口/PID前检后运行专用候选并完成收尾 | [validation.json](../.runtime/runs/sim01d-live-20261005T231430430819/validation.json)、[writer-closed.json](../.runtime/runs/sim01d-live-20261005T231430430819/writer-closed.json)和[cleanup-audit.json](../.runtime/runs/sim01d-live-20261005T231430430819/cleanup-audit.json)均通过；有效跨度、边界前后样本、排空和端口/PID清理闭合，原始产物保留。该结果不关闭PERF-01或ENV-03 |
| P1-1 IFACE-01 | 进行中；设备时间合同、记录审计、受限PointCloud2合同、非零扫描训练合同、T-14 fixture及fake Radar值级fixture验证了字段/时间/状态边界，**无真实raw在线节点或设备驱动** | AircraftState保留身份与失效语义；Odometry/TF为同节点可选镜像；真实设备记录回放、跨设备时钟误差、真实协方差和正式平台仍需实测，不用fixture冒充实测 |
| P1-2 SENS-TRAIN-01 | 进行中；[ROS直线/偏航路径](../experiments/2026-10-13-sens-train-yaw-ros.md)、[离线几何/运动统计](../experiments/2026-10-13-sens-train-scene-statistics.md)及[高度/无回波矩阵](../experiments/2026-10-16-iface-radar-height.md)已通过；在线图不变 | 继续训练数据覆盖与契约边界；真实设备时钟、标定与数据规模另列阻塞；训练监督不进入在线SensorBundle、forward、定位、mapping，不提前对照试验 |
| P1-4 MAP-QUERY-01 / MAP-ROLL-01 | 固定单点查询及可选基础滚动网格的软件子范围已完成；旧入口默认固定 | 独立正式输入、资源/时延和Phase 4关口仍待验收；不把fixture单点服务或活跃cell限额写成完整地图查询、真实内存性能或正式飞行验收 |
| P1-3 ENV-03 | 进行中但外部副本阻塞；project_manager保持已落实的保存规则，等待新的归档授权 | 10-15前评审单副本风险；无授权不复制外部资产、不写恢复验收通过，Phase 1仍记录未闭合 |
| P2 ALG-01及后续 | 进行中但研究候选被质量否决；研究后端、地图高级特性不得抢占当前门禁 | disabled/placeholder、Local Map先行；先由研究仓库修复或替换候选并完成独立质量门，再谈checkpoint加载、UAV适配器、真实标定、机载部署、DEM/飞行验收 |

SENS-IR-01和SIM-01D不新增IR物理温度或模型质量结论，也不引入LiDAR；
PERF-01的20 ms、目标平台资源、真实模型质量和Phase 1退出状态仍分别待验。

2026-10-13用户确认在无硬件/实测记录条件下继续非零扫描ROS训练闭环，
[ADR-019](DECISION_LOG.md#adr-019-2026-10-13-硬件缺失时独立推进非零扫描ros训练闭环)
记录此独立软件执行顺序。正式PERF-01管理优先级和原项目日期不变，不让外部设备
输入阻塞无依赖软件子任务；不引用开题计划时间，也不提前开展科研对照试验。

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
截至该SIM-SPEED-01实施记录时，SIM-01D和Phase 1仍未完成；本次没有验证35—70m/s地图更新、Radar—IR感知或训练监督LiDAR。
SIM-01D随后于2026-10-05单独完成，见本计划§4及[EXP-20261005-003](../experiments/2026-10-05-sim01d-continuity.md)。

## 5. 必须量化的性能与场景预算

35/50/70 m/s航速点及ARS548参考视场/距离已确认；目标机载平台、IR镜头/同步、
场景和其他质量/资源阈值仍有工程估计或待定值，不能把示例数字或研究数据集设置当成
系统默认值，更不能把开发机20 ms失败诊断写成目标平台性能验收。

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

2026-10-28用户将10-30周五前的报告用ROS可视化列为本轮优先任务，并明确必须采用RViz。
APP-VIS-01已于10-28交付[原生RViz工作台](ROS_VISUALIZATION.md)及
[主图/图注](../experiments/report_assets/rviz-20261028/README.md)：实际demo、公开回放、
旧Radar/IR占位链live、五类查询/失效与图像像素检查通过，全仓638项通过。
本轮顺延M5-DESIGN-01设计，地图阶段顺序与正式退出门槛不变；可视化不构成模型质量或飞行验收。
用户后续澄清要求场景与Radar点云/IR模拟，并要求三维场景窗口；APP-VIS-01仅地图工作台
不满足该完整目标。SENS-VIS-01随后交付[独立Gazebo场景 + 标准RViz](SENSOR_SCENE_VISUALIZATION.md)，
场景几何/热投影、物体位移联动、原生截图、旧ROS与649项全仓回归通过，
见[EXP-20261028-006](../experiments/2026-10-28-sensor-scene-visualization.md)。
该模式飞机固定，使用显式ground_truth注册并复用既有唯一TF状态适配器；未联动PX4/JSBSim飞行，
不关闭真实设备、模型质量、完整阶段或正式性能门槛。

用户随后确认继续M5-DESIGN-01，已完成[具体设计](M5_TERRAIN_PRIOR_DESIGN_20261028.md)
与[EXP-20261028-007审查](../experiments/2026-10-28-m5-design-review.md)：10条现状审计、
4项现有边界探针/6项数字算例和40项既有定向通过，规划16组地形验收预期。
首批只规划独立私有地形高程层，公共ROS/应用协议和DEM占据融合分别另审，不把高度或质量塞入现有占据字段。
M5-SW-01已按后续授权完成合同/小输入/独立预期及输入校验，见
[EXP-20261028-008](../experiments/2026-10-28-m5-fixture-contract.md)；
SW-01时未实施真实DEM、地形候选或新ROS。用户继续后SW-02已实现独立候选与私有回放，
见[EXP-20261028-009](../experiments/2026-10-28-m5-terrain-candidate.md)；
后续SW-03已完成多版本时效/资源/失败恢复组合，见
[EXP-20261028-010](../experiments/2026-10-28-m5-time-resources.md)；
只关闭私有离线软件范围，不是RSS/真实DEM或实际ROS验收。
M5-IFACE-DESIGN-01随后已交付独立地形查询/状态/回放协议、生产消费及兼容恢复
[具体方案](M5_IFACE_DESIGN_20261028.md)，见[EXP-20261028-011](../experiments/2026-10-28-m5-interface-design.md)。
用户随后明确授权，M5-IFACE-SW-01已实现独立类型/codec/dataset/recording合同，
见[EXP-20261028-012](../experiments/2026-10-28-m5-interface-contract.md)；
实际Provider/ROS与客户端/显示按SW-02/03分别验收，真实DEM与占据融合仍未实施。

后续SW-02已通过[实际Provider/clock/服务与旧占据兼容恢复](../experiments/2026-10-28-m5-provider-ros.md)，
只关闭合成独立运行范围；下一项SW-03尚未实施，不能将公共recording结构校验当执行回放。

10-29后续SW-03已通过[实际公共录制/执行回放、客户端与地形显示及旧场景兼容](../experiments/2026-10-29-m5-terrain-delivery.md)。
M5公共合成软件范围完成；Phase 5软件组合场景/需求矩阵[具体方案](PHASE5_SOFTWARE_COMBINATION_DESIGN_20261029.md)随后已交付，
P5-SW-01输入/独立预期与线格式、SW-02 A/B实际组合随后完成，SW-03现已完成
[原生图/S09与软件全矩阵交接](P5_SW03_NATIVE_DELIVERY_20261029.md)，下一批按第8节整理交付证据，
不因缺真实数据反复重做旧fixture，
也不将这些软件结果写成正式DEM/占据融合、资源或完整阶段验收。

| 子阶段 | 交付 | 验收重点 |
| --- | --- | --- |
| M1 Local Map | 有界地图、明确frame/origin/resolution及单点查询 | 已完成基础滚动整格odom网格fixture子范围；真实输入/物理资源/任意坐标变换及区域查询仍待后续独立验收 |
| M2 Probability | 多帧更新、去重、老化 | 重复观测不重复累计，时间顺序、已知/未知/过期保持正确 |
| M3 Uncertainty | 有来源和单位的质量表达/融合 | 缺失与已知区分，模型量与几何方差不混用 |
| M4 Scene Map | 子地图管理和场景更新 | 定位跳变、跨子地图参考系、覆盖与资源边界 |
| M5 DEM | 显式TerrainPrior接入 | 水平/垂直基准、no-data、时间和高度不确定性 |

每个子阶段需有独立证据。研究仓库已有地图代码不自动满足这些条件。
M4-DESIGN-01及SW-01—04已完成[固定合成注册/有界子地图软件试制](M4_SOFTWARE_TRIAL_PLAN_20261027.md)，
未声明正式M4通过；现有SpatialContext缺独立reset/epoch，首版只验证新run/显式注册域隔离，
真实定位跳变识别、动态注册和旧子地图重注册仍另验。
M1真实输入与进程资源/查询时延等尚缺项见[待执行验收矩阵](M1_INPUT_RESOURCE_GATE_20261015.md)；
当前缺硬件与实测不提前批准M2/DEM或以活跃cell数推断正式内存达标。
2026-10-27增加[M2合成数据软件试制提案](M2_SOFTWARE_TRIAL_PLAN_20261027.md)，
区分提前开发的软件准入与正式M1→M2准入；用户后续已确认合成软件试制，
当前SW-01/02/03/04合成软件试制及实际ROS/回放交接已完成；正式M1/M2门槛及原退出条件保持。

## 7. 需求与测试对应

测试编号是后续验收设计标识，目前不代表测试代码已存在。

| 需求 | 测试 | 阶段 | 验收对象 |
| --- | --- | --- | --- |
| REQ-01 无研究模型运行 | T-01 | Phase 3/联调 | disabled/placeholder不依赖模型、权重或GPU |
| REQ-02 标准字段及异常语义 | T-02 | Phase 2—4 | 有效值、单位、空值、模式来源、序列化往返；SENS-IR-01实测同帧热点中心/背景像素守恒 |
| REQ-03 坐标正确 | T-03 | Phase 1—4 | 已知旋转/平移、外参方向、模型布局、动态位姿 |
| REQ-04 时间与同步 | T-04 | Phase 1—5 | 采集时刻、偏差、插值、暂停/回退、扫描时间；SENS-IR-01核对同sample_id的曝光时间及Bundle采样时间 |
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
当前feature/engineering-initialization已有首次提交`4bd0c33`，之后仍有大量未提交工作；
提交基线不等于ENV-03第二份独立副本或恢复演练完成。数据、checkpoint、日志、
结果和会话文件保留原位，每次后续提交前逐项核对清单，不能批量混入。
