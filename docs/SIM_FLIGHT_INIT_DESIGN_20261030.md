# 无控制初始化准备与SW-03衔接方案

日期：2026-10-30；版本：v0.1；任务：SIM-FLIGHT-INIT-DESIGN-01；主责任：simulation_engineer。
状态：已完成（只读审查及具体方案）；下述INIT-SW-01/02及SW-03拆分均为计划。
依据：[SW-02D实际采集](SIM_FLIGHT_SW02D_QUALITY_20261030.md)、ADR-044；
实验：[EXP-20261030-009](../experiments/2026-10-30-sim-flight-initialization-design.md)。

## 1. 结论与范围

直接下一项为SIM-FLIGHT-INIT-SW-01：先冻结独立输入/预期，实施新的私有准备合同和离线校验。
再由INIT-SW-02验证独立、最长10s/2500步的无控制准备会话，补逐步地面动力学与初始化进展证据。
这是拟议新profile，不修改或延长旧1s入口，也不直接执行原40s方案、公共Scene v2或控制命令。
10s是一次试制的硬上限，不是估计器收敛时间保证；到界未就绪明确失败，不顺延或临时改IC/参数。
本轮没有实现这些新合同、profile、宿主或运行器，没有新SITL/ROS/Gazebo运行。

原[飞行总体方案](SIM_FLIGHT_DESIGN_20261029.md)的SW-03先拆分：完成本准备工作包后，
SW-03A再做公共v2离线codec/独立端点合同，SW-03B再接准备/采样屏障及实际原生图。
旧v1高度/时间门、两个诊断v1、质量diagnostic.v2与全部历史失败保持。
研究模型质量、真实设备、DEM、占据融合和正式资源门继续独立暂缓，不作为本软件工作的前置。

## 2. 当前run能证明什么

本轮只重读SW-02D的21条原始事件及原始wire，没有重跑该采集。
[独立重读](../.runtime/runs/flight-init-design01-20261030T103243156519/sw02d-reload.json)、
[wire输入核对](../.runtime/runs/flight-init-design01-20261030T103243156519/wire-input-audit.json)保持：

| 证据 | 当前事实 | 不能推导 |
| --- | --- | --- |
| 六实例完整status/flags | status sample=908000us；flags sample=884000us或748000us，tilt/yaw=False | 不是原子同tick，也不能外推整个窗口 |
| 完整消息的生产分支 | EKF2只在_ekf.update()成功分支发布这些正文；Ekf::update先完成initialiseFilter | 已越过首次滤波初始化，不等于倾角精对齐或姿态有效 |
| selected姿态/执行器 | 无正文/实际HIL执行器0包 | 不填零执行器、不认定仅缺GPS或唯一根因 |
| 250个HIL_SENSOR | 原戳0..996000us，每步4000us；无HIL_GPS | 仅发送输入，非内部250次积分/融合成功 |
| 原始加速度/角速度 | 模长约2.22e-9..52.238495m/s²，角速度最大.893392rad/s | 不是EKF低通值，也不能证明静稳或数值崩溃 |
| 原始数值范围比较 | 143个连续样本从428000至996000us，同时满足.8g..1.2g与≤15°/s | 两端相距568ms，不是1s静稳证据或tilt门通过 |
| 初始几何 | AGL约.5m、Euler约[0,0,90]度、vt=0，初始四属性0 | 不是地面接触/静态平衡；旧收据没有逐步AGL、姿态、速度、支柱WOW |

范围比较仅用于选择后续观测，不能把raw输入重新滤波后冒充内部_accel_lpf/_gyro_lpf。
完整status证明曾进入更新分支，不证明其他时刻均更新；baro_hgt=True本身也不是首次初始化成功证据。
质量隔离的12处比值仍明确不可用；不能照抄选择器内部局部代值来制造有限质量。

## 3. 源码链与32项核验

已保存[24份当前源文本](../.runtime/runs/flight-init-design01-20261030T103243156519/source-evidence.json)、
[32项准确语句/行号核验](../.runtime/runs/flight-init-design01-20261030T103243156519/source-checks.json)。
以下只说明源码路径，实际门值仍以本run观测为准。

| 核验 | 源码与事实 | 设计影响 |
| --- | --- | --- |
| I01—03 | [旧宿主](../simulation/flight_bridge/host.cpp#L25)250步；[缺包界](../simulation/flight_bridge/diagnostics.cpp#L145)500步/5s；[IC](../ros_ws/sim_flight_diagnostic_run.py#L19)去gamma | 不可只放大Python时间或复用旧profile/缺包放行 |
| I04—06 | [Rascal接触](../.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/models/Rascal/Rascal110-JSBSim.xml#L54)三BOGEY弹簧阻尼；[IMU默认](../.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/include/sensor_imu_plugin.h#L103)pilot比力与PQR、[噪声](../.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/src/sensor_imu_plugin.cpp#L116)dt>0后加入 | 固定地面IC仍可能有接触瞬态，不钳制位姿或合成静止IMU |
| I07—10 | [setIMUData](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/estimator_interface.cpp#L61)积分降采样/延迟；[initialiseFilter](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/ekf.cpp#L125)低通/计数；[initialiseTilt](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/ekf.cpp#L227)低通范围 | wire、vehicle_imu积分均值和内部低通分开记 |
| I11—14 | [发布分支](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF2.cpp#L589)、[精对齐](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/control.cpp#L52)、[初始方差](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/covariance.cpp#L1083)、[初值参数](../.runtime/src/px4-v1.13.3/src/modules/ekf2/ekf2_params.c#L1034) | 首次初始化与tilt_align是不同门；源码默认不是本run实测参数 |
| I15—19 | [mag控制](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/mag_control.cpp#L82)先等tilt；[静止辅助](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/zero_velocity_update.cpp#L46)要求at_rest；[fake_pos](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/fake_pos_control.cpp#L41)可作无水平辅助精对齐；[land输入](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF2.cpp#L535)来自PX4 | 不把GPS作无条件前置；JSBSim WOW不能填成PX4 landed/at_rest |
| I20—24 | [attitude_valid](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/estimator_interface.h#L123)需tilt；[选择器](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF2Selector.cpp#L396)拒重复/旧姿态，初选与healthy有别，内部比值代1；[flags](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF2.cpp#L1246)约1Hz或变化发布 | 姿态、primary、健康和新鲜度各自验；不把缺值代1或统一套10ms界 |
| I25—26 | [states](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF2.cpp#L1183)仅协方差对角；[旋转方差](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/ekf_helper.cpp#L1063)一般含交叉项 | 不新增states查询来伪造精确方差门或私有低通观测 |
| I27—30 | [接触只读API](../.runtime/deps/jsbsim-1.1.13/usr/include/JSBSim/models/FGGroundReactions.h#L101)、[逐支柱WOW](../.runtime/deps/jsbsim-1.1.13/usr/include/JSBSim/models/FGLGear.h#L255)；[旧高度门](../simulation/ufm_simulation/scene_motion.py#L38)；[桥接poll](../.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/src/mavlink_interface.cpp#L341) | 新准备仅私有宿主；首执行器后不能缺包继续/沿用旧值 |
| I31—32 | [旧query](../simulation/ufm_simulation/flight_probe_contract.py#L76)固定21次；[float show](../.runtime/src/px4-v1.13.3/src/systemcmds/param/param.cpp#L618)四位小数 | 新查询独立schema/计划，不伪造旧检查点，新增参数按真实类型严格解析 |

[数字核对](../.runtime/runs/flight-init-design01-20261030T103243156519/design-numerics.json)：
3°平方约.0027415568rad²；源码默认两轴初始方差和.02rad²约为该界7.295倍。
这只解释为什么“初始化一次”不自动等于精对齐，不推导收敛时间、线性衰减或当前方差值。

## 4. 拟议准备profile与停止边界

新sim-flight-initialization-observe-v1只供私有初始化评价，simulation_only/observation_only=true，
commands_enabled/capture_active/control_gate_accepted=false；单FDM、同桥接原生传感器与同源4ms步长。
IC保持已核对AGL=.5m、terrain=419.2m、vt=0、Euler=[0,0,90]度、gamma缺失，初始四属性0。
不改IC、模型、噪声、重力、接触系数或EKF阈值，不使用RunIC循环/trim/冻结位置/额外动力学预热。
如真实动力学不能形成静稳或初始化失败，留证并停止，不在同run替换更容易通过的输入。

源步最多2500、源时间最多10s；不得把旧sim_flight_fixture.v1放大或调用其旧500步缺包策略。
新宿主每步仅next/quit，源前/后分别记录FDM真实时间、AGL、原始ECEF、局部速度、Euler/PQR、
pilot比力、三支柱WOW和支柱压缩力、四控制属性；换算单位与源API/模型索引在头中冻结。
GetVel是局部NED ft/s，GetPQR是body FRD rad/s，Euler为NED/FRD姿态；不得写成ENU/FLU。
AGL是CG对当前地面距离，不是支柱离地；压缩力保留原LBF及换算N，不能用属性默认0冒充API读数。
源前真实pilot比力与本步HIL（含噪）分别保留，源后状态不能倒写成本步传感器真值。
每步确认一次且仅一次Run，4ms/1ns原界不变；不输出业务clock/state/TF或传感器图。

新准备专用策略允许首执行器尚未来时只用已明确初始化的零属性推进至准备硬界，
每条明确actuator=null/reason=preparation_no_actuator/binding=unverified；这不是反馈或有效零执行器。
第一次收到执行器后必须逐步有新包，否则在Run前停，不复用旧控制；收到包仅允许mode=1、
原16路有限且全0、原peer/system/component匹配，属性请求/读回全0；非零/armed立即Run前停。
原时间戳/flags保留而不强制宣称当前周期绑定；正向非零控制与严格时序准入仍留后续工作包。

无控制硬停止拟：非有限/错身份/时间不单调/Run失败、AGL不在[-.05,1]m、
|roll|>30°、|pitch|>25°、水平离初始位置>2m、真空速>5m/s、pilot比力模长>10g、
PQR模长>2rad/s、意外armed/非零执行器/非零控制属性、接触数/顺序变化及任何预算超界。
这些是该地面fixture的试制限制，不是实机包线；初始落地瞬态允许不满足静稳门，但不得越过硬界。
观测到来源冲突、坏正文/非白名单非有限或超时仍停；空标题、未发布、两字段合格质量缺失可以记录继续，
却不能给就绪门补默认值。失败后不再next，不为取得disarm/ACK继续源循环；仅清理本次PID/端口。

## 5. 独立合同与观测计划

拟新增私有schema，均由simulation拥有，ros_ws薄装配，tests独立核对；不新增公共消息或ROS节点：

| schema | 精确内容与主要约束 |
| --- | --- |
| sim_flight_initialization_fixture.v1 | schema_version/profile_id/fixture_only/simulation_only/observation_only/commands_enabled/capture_active/ic/model/actuator_channels/time/checkpoints/topics/parameters/limits；固定值/精确键集，拒绝未知和训练监督字段 |
| sim_flight_initialization_step.v1 | schema_version/run_id/clock_id/profile_id/step_index/source_step/hil_sensor_time_us/has_actuator/actuator/reason/properties/fdm/wall/kinematics_before/kinematics_after/ground_before/ground_after/binding_status/control_gate_accepted；缺包显式null，几何/动力学有限，记录前后及失败是否Run |
| sim_flight_initialization_query.v1 | schema_version/run_id/clock_id/checkpoint/query_index/kind/name；精确匹配新固定84项顺序，不借旧v1查询封套 |
| sim_flight_initialization_observation.v1 | schema_version/query/argv/owner_before/owner_after/last_hil_us/fdm_time_s/wall_start_ns/wall_end_ns/returncode/stdout/stderr/observation/binding_status/control_gate_accepted；原文投影一致及四态/实例缺失语义保持 |
| sim_flight_initialization_recording.v1 | schema_version/run_id/clock_id/profile/peer/initial_wall_ns/initial_properties/initial_kinematics/initial_ground；头后只接连续step，query文件独立绑定同run/checkpoint，终态单独报告 |

INIT-SW-01须先将上表嵌套对象、dtype/单位/缺失、所有限额及终态精确键集写入交付合同，
冻结字面量预期后才实现checker；不以“原msg字段大致相同”替代完整有界校验。
JSON拒绝重复键/坏UTF-8/非有限/超长/坏枚举/错身份/额外监督字段；整数时间拒绝bool/float。
has_actuator=false不产生requested/received/applied值，不将未执行Run写成false成功。

旧两个v1和质量v2的封套/21项计划不改。新解析器只复用现有纯字段/完整块函数（_native_field、
_block、_status_block）及固定两字段掩码语义；新顶层完整/空块语法、layout和query独立校验。
不得将新checkpoint改成125/250后交旧parse_native，也不得调用旧stream校验器后修改其summary。
新增vehicle_land_detected使用其完整原生msg；不引入通用容错parser或复制整套旧codec。

固定源检查点为125/250/500/1000/1500/2000/2500步，即FDM后.5/1/2/4/6/8/10s；
last HIL原微秒分别496000/996000/1996000/3996000/5996000/7996000/9996000，不改成FDM后戳。
每处固定11查询：selector前读、vehicle_imu、estimator_status、estimator_status_flags、
estimator_attitude、vehicle_attitude、vehicle_control_mode、actuator_controls_0、actuator_outputs、
vehicle_land_detected、selector后读，共77；没有states/私有低通或额外flags查询。
listener仍n=1且不传-i/-r；所有实例完整保留，未知单实例编号null，不据首行猜primary。

首125步先独立组show七参数：SYS_AUTOSTART=1033、SYS_CTRL_ALLOC=0、SENS_IMU_MODE=0，
EKF2_ANGERR_INIT=0.1000（float）、EKF2_MAG_TYPE=0、EKF2_HGT_MODE=0、EKF2_AID_MASK=1（整数）。
后三整数及浮点为拟议固定fixture期望/源码默认，本轮没有读回其runtime值；不符即停，不写参数。
新参数语法沿原完整show头/索引/尾计数，按声明类型解析四位小数或int32，不接受nan/inf/类型替换。
总84次，无重试/临时加查询；首次参数组在.5s后验证配置，未通过不再推进。

## 6. 就绪、输出与SW-03准入

判定均只用于离线初始化评价；各gate独立，不能用collection_complete替代。

1. input_settled：在8s和10s两个检查点各自前连续250步，逐步至少一支柱WOW、AGL在[0,1]m、
   局部速度模长≤.5m/s、PQR模长≤15°/s、实际HIL加速度模长在[.8g,1.2g]。
   此1s物理/输入门是本fixture独立预期，仍不称EKF低通门或PX4 land detector结果。
2. initialization_ready：两个末检查点均满足input_settled、同组前后selector的primary/变更计数一致，
   primary在可用范围且对应设备ID/实例可核对；该实例status故障0、tilt/yaw=True、reported healthy=True，
   对应estimator_attitude与vehicle_attitude均完整有限且四元数范数误差≤.001、sample单调。
   PX4 land样本须landed/at_rest=True，模式样本须armed=False；任何缺失/身份不明确不通过。
3. 新鲜度分别对实际last HIL核对：status/vehicle_imu≤200ms、flags/selector/land/mode≤1.2s、
   estimator/vehicle姿态sample≤20ms；不得为通过把较旧flags改戳或设所有topic统一10ms。
   只允许原始timestamp/sample不晚于本检查点且非0；重复慢topic不冒充新样本。
   同组双selector只约束观测身份稳定，不构造原子快照/严格因果证明；选择器内部10ms发布门保持。
4. output_chain_observed：末两检查点间实际至少两个不同源step收到合格零执行器包，
   原wire/16路、请求/读回0及Run能对账；controls/outputs原生正文与实际更新单独报告。
   initialization_ready即使为true，输出仍缺则本工作包运行未通过，不跳去控制实验。

结论字段固定分开collection_complete/input_settled/initialization_ready/output_chain_observed、
binding_status=unverified/control_gate_accepted=false及失败原因/最后step/检查点列表。
两末检查点都通过才关闭准备运行子范围；不要求所有辅助源比值变有限，也不将其缺失当free或正常质量。
若初始窗口内未就绪，只在新证据指向的本仓工程缺陷范围修复；不重复设计空值表示或无限增窗。

SW-03A可在本准备合同与运行证据齐备后实施原公共v2的独立codec/交叉拒绝及冻结100采样点；
SW-03B再接同FDM准备、场景采样屏障、精确上下文/唯一TF、预算和停止后History。
本10s会话不输出新状态/TF，不把PX4 selected姿态替换为场景真值权威；
原30s准备/40s总窗在SW-03B具体profile中重新核对全部预算/就绪，不由本10s结果自动放行。
严格当前周期执行器绑定、非零属性因果、arming检查/命令与真离地仍留后续SW-04门，不能由零包补齐。

## 7. 预算、兼容与恢复

新case拟构建≤180s、启动≤60s、initial后准备墙钟≤60s、spawn后session≤120s；
源≤2500步/10s，每次transaction≤1s，query≤200ms、每组≤400ms（七topic组和一参数组）。
各deadline覆盖身份、解析、写盘，spawn前/保存后/下一query与next前复查；不暂停计时等待PX4就绪。
现有10ms监督轮询可保留，4ms源步长不变；构建不计源准备但必须独立有界。
单step≤16KiB、最多2500；query原文≤32KiB、单事件/头≤256KiB、事件≤128，query全文件≤16MiB；
depth≤8/nodes≤8192/list≤512，几何数组固定3、旋转4/9（若使用）、支柱数固定3，字符串限额沿旧合同。
wire原始字节≤16MiB/事件≤8192、step/物理记录文件≤64MiB、case全部产物≤256MiB，
含元数据/报告/基线/rootfs日志，外部日志每.5s核对；构建目录单独登记，不冒充RSS或PERF。

不改变PX4原源、第三方模型/桥接源树/系统依赖；适配仅复制到新.runtime/ros构建路径，精确上下文漂移即拒绝。
旧25公共定义/7入口、全部旧profile/schema/预算及实际normal/disconnect兼容须核对；
旧SW-02B/C失败和SW-02D完整采集保留，不用新准备回填或覆盖旧产物。
失败不继续业务提交/源推进，仅按自有PID/start_ticks清理并核端口；重启必须新run/clock/rootfs。
不把进程退出当disarmed或着陆，不使用force或尝试处理其他会话。

## 8. 实施分工与独立预期

| 任务 | 主责任 | 具体修改范围 | 验收 |
| --- | --- | --- | --- |
| INIT-SW-01（直接下一项） | simulation_engineer | 新configs/sim_flight_initialization_fixture.json、simulation/ufm_simulation/flight_initialization_contract.py、tests独立字面量/原文fixture与离线测试/runner；配套合同/实验/状态。旧解析器不改，纯块函数可复用 | 先保存下表独立预期，再严格schema/codec/序列重读；现有92飞行定向、真实消息兼容和全仓轻量。无新宿主/适配/运行或公共类型 |
| INIT-SW-02 | simulation_engineer | 新simulation/flight_initialization私有宿主/hook/精确源复制适配、ros_ws独立构建/运行薄包装、tests实际wire/逐步物理/原文独立审计；不改旧flight_bridge或运行入口 | 先离线故障，再一次正常准备与断连接/超时独立停止、旧入口回归；采集/初始化/零输出及清理分开，无ROS或控制 |
| SW-03A | integration_engineer | 原方案公共v2离线类型/codec/独立插件端点合同及交叉拒绝 | 实际生成消息序列化及旧字节兼容，不启动长窗或命令 |
| SW-03B | integration_engineer | 经确认的新profile/准备与采样屏障/端点装配、同tick地图/原生窗口 | 新profile逐帧证据/故障/清理，未满足准备门不激活采样；控制门仍不自动开放 |

INIT-SW-01至少先冻结以下独立字面量和反例，不能用被测生成器写oracle：

| 组 | 独立预期 |
| --- | --- |
| N01—03 | 7检查点/77 topic/7参数共84顺序及整数HIL原戳；2500步/10s硬边界；旧schema/封套交叉拒绝 |
| N04—06 | 同IC/AGL与径向ASL区分、NED/FRD/英制换算及三支柱顺序；源前/后不能交换；接触与PX4 landed分开 |
| N07—09 | 缺包显式null/零属性；合法零包16路；首包后断流、非零/armed/错peer在Run前拒绝 |
| N10—12 | 四态完整/空/未发布/两字段合格缺质量；同块mask与原token；其他nan/变体/部分字段/身份/版本/非有限/超限拒绝 |
| N13—15 | 浮点0.1000与整数参数不混；少/重复/多查询拒绝；新checkpoint不得伪造旧query复用 |
| N16—18 | input_settled连续250步、任一中断清零；首次初始化与tilt/yaw分门；两个末检查点、primary稳定/设备及慢快topic年龄分别验 |
| N19—21 | healthy/姿态/输出分别缺失；零包不产生绑定/控制许可；末界未就绪报告失败而不顺延 |
| N22—24 | 预启动/写后/next前期限与总文件界；旧身份/迟到/坏JSON/训练监督字段拒绝；失败step未Run/新身份恢复及旧profile保持 |

本轮只核对这些设计的算术和源码依据，尚无N01—24新checker或完整测试结果。

## 9. 本轮验证与交付限制

32项源码核验、SW-02D原21事件独立重读、250个保存wire消息解码、7检查点/84查询预算算术通过，
92/92既有飞行定向通过；458份源码/配置及上述24份源文本逐文本保持。
未重跑全仓；995项全仓/84项运动是SW-02D上一轮结果，不写成本轮新结果。
未实现新profile/codec/解析器或启新FDM/PX4/daemon查询，无ROS/Gazebo/RViz、控制、训练/推理或PERF。
完整交付只关闭本设计；初始化准备、有效selected姿态/零执行器链、公共v2/长窗和受控飞行仍未验证。

## 10. 后续离线实施

2026-10-30 [INIT-SW-01](SIM_FLIGHT_INIT_SW01_CONTRACT_20261030.md)已按本方案先冻结独立预期，
再实现新私有fixture/step/query/observation/终态合同、严格codec和有界序列/文件校验；
fdm.hil_sensor明确落实实际HIL输入字段，controls/outputs可用性与真实零输出成功Run分开报告。
两组合成2500步/84查询、35新增/飞行127/运动84/全仓1030项及旧真实消息兼容通过，原458源码保持。
本轮未实现新宿主/适配/客户端或启动准备期；下一项INIT-SW-02，实际四门与公共v2/控制仍未验收。

2026-10-30后续：[INIT-SW-02实际交付](SIM_FLIGHT_INIT_SW02_PREPARATION_20261030.md)已实现独立宿主与有界查询；
500步/2s、78真实零执行器/属性读回可核对，但第30条selector非有限被拒绝，完整准备未通过。
故障/旧入口及134/84/1037项回归通过不改变原预算/控制门；下一项先selector槽位身份/表示设计，不重复正常run。
