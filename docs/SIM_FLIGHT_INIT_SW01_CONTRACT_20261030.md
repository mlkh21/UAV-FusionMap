# 初始化准备私有离线合同交付

日期：2026-10-30；版本：v0.1；任务：SIM-FLIGHT-INIT-SW-01；主责任：simulation_engineer。
状态：已完成（私有离线合同、合成预期及兼容子范围）。
依据：[INIT-DESIGN-01](SIM_FLIGHT_INIT_DESIGN_20261030.md)、ADR-044；
实验：[EXP-20261030-010](../experiments/2026-10-30-sim-flight-initialization-contract.md)。

## 1. 结果与范围

新增独立准备fixture、私有profile/header/step/query/observation/terminal严格JSON合同，
实现有界JSONL重读、源前/后动力学与接触连续性、原文投影、独立84项查询和离线四门判定。
先冻结独立字面量和原生源基线，再实现checker；没有改旧合同、入口、宿主、公共消息或第三方源。
这些对象只有tests离线消费者，本轮没有实现daemon客户端、准备宿主、ROS节点或实际准备期。

[最终阶段报告](../.runtime/runs/flight-init-sw01-20261030T111445613013/report.json)：
35项新增、飞行127/127、运动84/84、全仓轻量1030/1030通过；
两组合成2500步/84查询的实际JSON字节重读及88次私有JSON往返通过。
旧77组场景字节/36组公共往返/18组合成源转换继续使用实际genpy，25份定义/7入口保持。
私有JSON不是ROS线格式，不能将其往返称作新准备运行或PX4收敛证据。

合成ready例的四门全true也仍binding_status=unverified、control_gate_accepted=false；
缺失例collection_complete=true而initialization_ready/output_chain_observed=false，整体passed=false。
SW-02D上一轮实际selected姿态缺失、执行器0包的事实保持，本轮未重新查询或回填。

## 2. 新增文件与生产消费链

| 文件 | 作用/修改原因 |
| --- | --- |
| [sim_flight_initialization_fixture.json](../configs/sim_flight_initialization_fixture.json) | 独立10s/2500步准备元数据、单位/gear顺序、84查询/参数与固定预算；尚未运行 |
| [flight_initialization_contract.py](../simulation/ufm_simulation/flight_initialization_contract.py) | 精确合同、严格JSON、逐步物理/输出连续性、文件重读和纯预算guard |
| [flight_initialization_observation.py](../simulation/ufm_simulation/flight_initialization_observation.py) | 新封套/原文投影、原生布局来源核对、查询流与初始化评价；无客户端 |
| [sim_flight_initialization_cases.json](../tests/fixtures/sim_flight_initialization_cases.json) | 先行独立时间/查询/单位/缺失/合成判定预期及N01—24分组 |
| [sim_flight_initialization_native.json](../tests/fixtures/sim_flight_initialization_native.json) | 机械提取9原生msg、4段质量语义源和旧status原文；具名布局/源预检消费者，无Hash |
| [sim_flight_initialization_fixture.py](../tests/sim_flight_initialization_fixture.py) | tests专用合成输入/全字段原文与独立投影，不调用被测parser生成预期 |
| [test_sim_flight_initialization.py](../tests/test_sim_flight_initialization.py) | 35项边界/缺失/时序/就绪门及字节/文件重读验证 |
| [sim_flight_initialization_run.py](../tests/sim_flight_initialization_run.py) | 冻结输入→私有字节/文件验证→既有实际genpy与轻量回归；不启动FDM/PX4/ROS |

配套新增本说明/中文实验，并更新状态、README、设计后续、架构/接口/坐标、计划/ADR/实验索引。
八份新增源码/fixture文件；原458份源码/配置逐文本不变，测试时冻结总计466份。
当前链为tests合成/冻结文件→simulation私有checker→tests结果，不接SensorBundle、定位、mapping或forward。
旧实际probe/diagnostic/quality-v2消费者保持，不能用新封套改写旧21项计划。

## 3. 精确合同

所有schema使用sim_flight_initialization_前缀；schema_version是独立版本字符串，不等于公共Scene v2。
每层精确键集，未知键/监督字段、错类型/枚举、缺失/重复字段、非有限、坏UTF-8、过深/超限拒绝。
布尔值不充当数字；run_id为有界安全文本，clock_id必须sim:<run_id>；profile固定observation_only、
commands_enabled/capture_active=false，绑定只unverified、控制门只false。

| kind/schema | 精确键集及约束 |
| --- | --- |
| profile / fixture.v1 | schema_version/profile_id/fixture_only/simulation_only/observation_only/commands_enabled/capture_active/ic/model/actuator_channels/time/checkpoints/topics/parameters/limits；所有值、嵌套键和类型精确等于独立配置定义 |
| header / recording.v1 | schema_version/run_id/clock_id/profile/peer/initial_wall_ns/initial_properties/initial_kinematics/initial_ground；初始时间0、AGL/地面/姿态/vt按原IC读回界，属性四值0 |
| step / step.v1 | schema_version/run_id/clock_id/profile_id/step_index/source_step/hil_sensor_time_us/has_actuator/actuator/reason/properties/fdm/wall/kinematics_before/kinematics_after/ground_before/ground_after/binding_status/control_gate_accepted |
| query / query.v1 | schema_version/run_id/clock_id/checkpoint/query_index/kind/name；逐项严格匹配新84项顺序 |
| observation / observation.v1 | schema_version/query/argv/owner_before/owner_after/last_hil_us/fdm_time_s/wall_start_ns/wall_end_ns/returncode/stdout/stderr/observation/binding_status/control_gate_accepted；原文投影逐值/逐类型一致 |
| terminal / terminal.v1 | schema_version/run_id/clock_id/profile_id/last_step/reason/wall_ns/binding_status/control_gate_accepted；固定原因枚举，window_complete/not_ready_at_limit只允许last_step=2500；整体门结论由独立evaluate产出，terminal单条不作为准入证据 |

model包含原airframe/model/config/mixer，加gear_names、source_units、ft_to_m=.3048、
lbf_to_n=4.4482216152605；这些是单位/来源约定，不是地理配准或物理模型验收。
kinematics精确含sim_time_s/agl_m/asl_m/geodetic_altitude_m/terrain_m/ecef_ft/vel_ned_ftps/
vel_ned_mps/euler_deg/pqr_radps/pilot_accel_ftps2/pilot_accel_mps2/true_airspeed_mps。
向量均固定3、有限，源/米制对应逐值差≤1e-9；不要求径向ASL等于地面+.5，不把CG AGL当支柱间隙。
ground为固定3项，按LEFT_MLG/RIGHT_MLG/TAIL_LG顺序，精确name/wow/compression_lbf/compression_n；
WOW必须bool，力保留正负和单位。它不能携带或补填PX4 landed/at_rest。

fdm精确ran/result/sim_time_before_s/sim_time_after_s/hil_sensor；hil_sensor新增嵌套time_usec/
accel_mps2/gyro_radps，保存本步实际HIL原值，供独立输入范围门使用，不能从FDM源后值反推。
这落实设计中“实际HIL数值”要求，不新增顶层业务字段。sensor原微秒须等于本步hil_sensor_time_us。
properties精确before/requested/after，wall精确hil_sent_ns/actuator_received_ns/properties_applied_ns/fdm_finished_ns。
actuator精确receive_sequence/peer/time_usec/flags/mode/armed/controls，沿原16路float32及通道规则，
准备流仅mode=1、armed=false、16路全0，四属性请求/读回全0。
has_actuator=false时actuator/requested/received/applied均null，reason=preparation_no_actuator；
不能将零属性编码成收到零包。HIL与actuator原时间保留，未声称相等即证明当前周期绑定。

源时间按4ms网格/1ns界，HIL按(source_step*4000)uint64整数；step连续、peer/接收序号/执行器原戳单调，
前后物理/接触与下一step.before连续。首包后缺包不得Run；未Run必须result=null且前后状态/时间相同，
Run失败与未执行分开。unsafe源前不得Run，源后越界可留该条证据但流锁定终止，后续记录拒绝。
超界/非有限无法构成合法对象的原文由未来宿主另存失败原文，本codec不伪造正常记录。

## 4. 原生观测、时序与预算

固定7检查点125/250/500/1000/1500/2000/2500，FDM后.5/1/2/4/6/8/10s，last HIL为
496000/996000/1996000/3996000/5996000/7996000/9996000us。
125步先show七参数，再每检查点11topic（selector前后各一）；总7+77=84，不容许少/多/重排/重试。
参数期望1033/0/0/.1000/0/0/1，EKF2_ANGERR_INIT严格float32四位小数，其余int32；
这是合成fixture期望，不是七参数本轮实际PX4读回。旧SW-02D实测三参数结论不被改写。

原生9消息与冻结源文本不等即拒绝；阶段工具还核对两比值固定隔离条件的4段源语义。
只复用旧_native_field、_block、_status_block，不将新checkpoint伪造成旧query再调用旧顶层解析器。
完整/never published/空标题/质量不可用四态与同实例mask/准确nan规则保持；未知单实例编号null。
其余nan/inf、错误条件/标注、畸形/部分输出、异常stderr/退出码拒绝，armed模式样本拒绝。
owner前后及整流必须是同PID/start_ticks/executable/rootfs/socket文件/内核身份；argv仅固定listener/show。
本轮只校验身份收据，未实际核对活daemon所有权；运行核对由INIT-SW-02承担。
原生timestamp/sample不能在当前HIL未来，同topic/实例原戳不得倒退；慢topic可重复旧样本，不能冒充新鲜。
query必须在本检查点Run完成后、下一step发送HIL前落盘；不把顺序读取声称原子同tick。

纯check_budget为后续spawn前、保存后、next前调用提供同一检查；本轮只有离线预算反例，未验证运行调度。
source≤2500步/10s，session≤120s、initial后≤60s、startup≤60s、build≤180s；transaction≤1s、
client≤200ms、group≤400ms。JSON header/event≤256KiB、step≤16KiB、raw≤32KiB，
depth8/nodes8192/list512；stream≤2500条/64MiB、query合同84条（外部预算上界128）/16MiB，
wire≤16MiB/8192事件、case全部产物≤256MiB。所有本地字符串、路径/argv、原文分别有界，编码前先拒绝超长文本。
预算是逻辑和文件载荷门，不是RSS、实时倍率或正式PERF；未来宿主仍需核对外部日志与实际时限。

## 5. 合成验收与已验证内容

[先行oracle](../.runtime/runs/flight-init-sw01-oracle-20261030T110243259023/sim_flight_initialization_cases.json)
在生产实现前保存手工字面量/时间/单位/缺失预期及机械提取原生基线；本次输入与其逐字节保持。
两组合成物理源为tests输入，不是新动力学轨迹：每例2500条step/84条原文事件，实际写JSONL再独立重读。
ready例2001—2500共500个合成零执行器，missing例无执行器；后者仍可input_settled=true但整体不通过。
88次私有JSON往返包括profile/header/step/query和84个事件，terminal另有独立往返/坏字段测试。

四门分别为collection_complete、input_settled、initialization_ready、output_chain_observed。
物理静稳在2000/2500检查点前连续250步达到具名门槛；中断即重新累计，不由WOW推PX4静止。
初始化需两末检查点选中实例/设备关联、完整姿态/单位四元数、tilt/yaw、故障/healthy、PX4 landed/at_rest和未armed，
慢快topic各自年龄合格；姿态sample还需跨末检查点严格增长。未知实例、旧/未来/倒退样本或缺失不放行。
输出门至少两个不同2000步后、实际成功Run的零执行器记录；未Run/失败不计成功输出，
controls/outputs原文可用性另报，不据缺失造零载荷；所有门仅合成评价，始终不产生控制许可。

N01—24及追加反例共35项：独立时间/单位/顺序、旧schema交叉拒绝、缺包/全零/armed/非零/错peer，
四态/准确nan/同块mask/额外字段/非有限、类型/整数时间、两末检查点/primary/健康/年龄，
断流/失败/新run/终态、总量/期限与坏JSON/UTF-8/重复键/训练监督字段均覆盖。
127项飞行/84项运动/1030项全仓通过；旧消息实际genpy兼容结果见
[legacy报告](../.runtime/runs/sim-motion-sw04a-20261030T111502953376/report.json)。

首次完整stage已通过33项新增/1028全仓；复核增加原生未来/倒退时间和“未Run不计成功输出”两个边界测试后，
以新run重跑35项新增/1030全仓通过。首轮产物保留，不以旧结果冒充最终源码验证。
未重跑无改动ROS/Gazebo/RViz或旧实际1s诊断，因本次未触及这些运行入口；未启动准备期、训练/推理或正式PERF。

## 6. 下一任务与未验证能力

直接下一项SIM-FLIGHT-INIT-SW-02（计划；主责任simulation_engineer）：按已交设计新增独立
私有宿主/hook/精确源复制适配与薄运行器，先离线故障，再验证同FDM/同IC、最长2500步/10s
无控制准备与断连接/期限停止，原wire/逐步动力学/接触/84查询及清理独立对账。
本轮未修改旧flight_bridge/runner，不执行该新范围；后续不改IC/模型/噪声/阈值或自动延长到就绪。
实际未就绪到界明确失败，不能回到重复空值表示设计或声称采集完整即控制就绪。

未验证真实准备期收敛/selected姿态、实际零执行器输出链、当前周期绑定/非零属性因果，
公共Scene v2/40s采样、模式/arming/manual命令和实际离地；SW-03A/B与SW-04分步保持。
真实设备/模型质量/DEM/占据融合/机载资源继续独立暂缓；既有dirty、历史失败与原文保留，无提交或推送。

2026-10-30后续：[INIT-SW-02](SIM_FLIGHT_INIT_SW02_PREPARATION_20261030.md)已实现独立宿主/运行器，
实际500步/78零包后第30条selector含nan按本合同拒绝，完整准备未通过；本合同未放宽。
断连接/期限停止和134/84/1037项回归/旧实际兼容通过，下一项仅selector槽位/来源及不可用表示具体设计。
