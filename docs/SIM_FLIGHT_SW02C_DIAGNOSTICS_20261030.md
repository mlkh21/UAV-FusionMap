# 三态uORB诊断的软件交付与非有限输出停止

日期：2026-10-30；任务：SIM-FLIGHT-SW-02C；主责任：simulation_engineer。
状态：进行中（软件/回归已交付，21次实际采集验收未通过）。
依据：[DIAG-DESIGN-03具体方案](SIM_FLIGHT_DIAG_DESIGN03_20261030.md)、ADR-044。
实验：[EXP-20261030-006](../experiments/2026-10-30-sim-flight-diagnostic-collection.md)。

## 1. 结论

已实现独立三态诊断合同、显式`--uorb-diagnostics`及有界记录器，旧strict/probe和默认两用例保持。
实际完成125步九topic观察并推进到250步，第11次estimator_status原文含六组vel_test_ratio/pos_test_ratio的nan，
按非有限拒绝规则停止；共11次查询、10条合法事件，未凑齐21次或读取最后三个参数。
diagnostic_collection_complete=false、payload_complete=false、binding_status=unverified、control_gate_accepted=false。
未以三态采集提高旧SW-02B验收状态，也未改变NaN规则使本次运行通过。

[最终阶段报告](../.runtime/runs/sim-flight-sw02c-stage-20261030T093533859011/report.json)整体passed=false，
compatibility_passed=true；飞行69/69、运动84/84、全仓轻量972/972及旧实际消息兼容通过。
软件与回归完成不能替代完整采集、载荷质量或受控飞行准入。

## 2. 修改文件与消费链

| 文件 | 作用及原因 |
| --- | --- |
| [flight_probe_diagnostic.py](../simulation/ufm_simulation/flight_probe_diagnostic.py) | 新私有三态原生解析、严格JSON事件和流校验；不改旧snapshot |
| [sim_flight_uorb_diagnostics.py](../ros_ws/sim_flight_uorb_diagnostics.py) | 复用已有daemon身份/有界客户端，独立记录原文/事件/组时段，超时停止 |
| [sim_flight_diagnostic_run.py](../ros_ws/sim_flight_diagnostic_run.py) | 显式新模式接入125/250检查点；互斥旧probe、disconnect、build-only |
| [sim_flight_diagnostic_cases.json](../tests/fixtures/sim_flight_diagnostic_cases.json) | 先保存18组独立预期/实际空原文、完整/缺失/参数样例，不进入在线链 |
| [sim_flight_diagnostic_fixture.py](../tests/sim_flight_diagnostic_fixture.py) | tests私有事件封套/模式文本，预期与被测解析器分离 |
| [test_sim_flight_diagnostic_observations.py](../tests/test_sim_flight_diagnostic_observations.py) | 新增20项测试，覆盖C01—18与期限/预算/互斥行为 |
| [sim_flight_diagnostic_stage.py](../tests/sim_flight_diagnostic_stage.py) | 新采集、成功流独立重读/宿主和原文对照、旧诊断与轻量回归装配 |

另更新本说明、实验记录、PROJECT_STATUS、README、架构/数据/接口/坐标、开发计划、ADR-044、
实验索引及设计实施后续。上述七个源码/fixture文件中六个新增，仅诊断runner为既有文件改动。
真实链为同一C++宿主收据→监督器停止next→本次PX4身份与socket所有权→固定只读客户端→
保存原文→独立三态事件。没有新增ROS topic/service、状态/TF权威或mapping/模型消费者。

## 3. 独立合同与停止规则

sim_flight_uorb_diagnostic.v1与旧snapshot v1互相拒绝；query仍复用固定query v1白名单，
125/250步各九topic、最后SYS_AUTOSTART/SYS_CTRL_ALLOC/SENS_IMU_MODE三项show，共21条。
事件精确顶层字段：schema_version、query、argv、owner_before/after、last_hil_us、fdm_time_s、
wall_start/end_ns、returncode、stdout/stderr、observation、binding_status、control_gate_accepted。
observation精确含state/reason/instances/parameter；每块只含instance/state/fields。

三态为payload、not_published、payload_unavailable：完整字段保留类型/原值；明确never published才记第二态；
合法标题而完全无正文才记第三态，fields=null。完整/空块混合逐块保存，顶层不可用。
单实例没有显式Instance标签时编号null，多实例保留原文标签，不能从数组位置猜primary。
正文已开始而字段不全、计数/顺序/类型/尺寸错误、未知/训练监督字段、非有限、异常文本均停止。
stderr要求严格为空，拒绝CR/TAB/ANSI/NUL；旧strict仍把空实例判为不完整。
参数必须精确完整且等于1033/0/0，没有空参数可继续的例外；不允许set或自由命令。
任何完整模式块armed=true即停，不能因顶层混有空块而忽略已读armed。
原文投影严格逐类型比较，拒绝bool冒充整数、重复JSON键、坏版本/身份/UTF-8/深度/尺寸。

每次查询前后绑定本次PID/start_ticks/exe/rootfs/socket文件与内核inode；期限覆盖核对、
执行、解析及持久化，spawn前、写后与下一query/next前检查；错误时清理本次整个会话。
原≤200ms客户端、≤400ms组、≤32KiB原文、≤256KiB事件/头、≤32事件/≤8MiB查询文件保持，
深度8/节点8192/列表512、5s bootstrap/30s session/250步及1s源时限均不延长。
新模式只省略已声明额外6ms监督sleep，原4ms FDM步长/10ms轮询不改；旧默认sleep保持。

新run前缀sim-flight-sw02c-diagnostics-，独立uorb-diagnostics目录及diagnostics.jsonl，
不复用旧probe路径/快照，不自动fallback。采集完整、18次topic载荷完整与控制许可分别报告；
即使全有载荷，未知实例、旧戳、primary无法关联、顺序快照和浮点打印精度仍限制解释。
完整流的summary可生成逐实例时间/标志与缺口；本次部分流未生成完整成功报告。

## 4. 实际步骤及失败保留

独立字面量先冻结于[oracle目录](../.runtime/runs/sim-flight-sw02c-oracle-20261030T093048549326/independent-expectations.json)，
同时保存原SW-02B六空实例原文及源码/git基线；审计确认独立预期字节未改。
新18组预期按设计保存后才实现合同/运行器，测试未用被测分类器生成oracle。
首次69项定向通过；新增阶段runner最初与ROS的sim_flight_diagnostic_run同名，导致旧测试导入被遮蔽，
阶段前检失败且尚未启动PX4。改名sim_flight_diagnostic_stage后新run重跑，未改旧测试或放宽期望。
失败保留于[093502242784](../.runtime/runs/sim-flight-sw02c-stage-20261030T093502242784/flight-targeted.log)。

实际新诊断仅运行一次，目录为[093534728429](../.runtime/runs/sim-flight-sw02c-diagnostics-20261030T093534728429/manifest.json)。
结果如下；表中三态只覆盖已严格编码/独立重读通过的10条事件。

| 检查点/查询 | 实际结果 | 可解释范围 |
| --- | --- | --- |
| 125 / vehicle_imu | 三组完整，编号0/1/2 | 原始时间与积分值可读，非EKF对齐证明 |
| 125 / estimator_status、flags、attitude | 各六空实例，第三态 | 本次无载荷，不能填状态0或tilt_align=false |
| 125 / selector、vehicle_attitude | 单标题无正文，第三态，编号null | 未取得被选姿态或primary的有效载荷 |
| 125 / vehicle_control_mode | 完整，timestamp=24000us，flag_armed=False，manual=True、rates/attitude=False | 仅本次旧样本值，不能视为整个窗口始终disarmed或当前周期新鲜模式 |
| 125 / actuator_controls_0 | 明确never published，第二态 | 不由此生成零控制 |
| 125 / actuator_outputs | 单标题无正文，第三态 | 没有输出载荷，不能替代MAVLink回包 |
| 250 / vehicle_imu | 三组完整 | 第二次IMU快照通过 |
| 250 / estimator_status，第11次 | 六实例有正文，各vel_test_ratio/pos_test_ratio为nan，共12处非有限文本 | 严格拒绝，不生成第11条合法事件；后续topic/参数未查询 |

合法事件计数payload=3、not_published=1、payload_unavailable=6；实际文件总量60390字节。
125组9查询墙钟39117822ns，只有一次组观测，不是时延统计/RSS/正式性能结果。
已严格重读的10条与原文argv/输出/退出码、宿主步号/HIL/源FDM时间逐项一致；
部分流仍报diagnostic_stream_incomplete，第11次原文仍报probe_native_float，未提升为第三态。
见[独立关闭审计](../.runtime/runs/sim-flight-sw02c-stage-20261030T093533859011/closeout-audit.json)及
[第11次原文](../.runtime/runs/sim-flight-sw02c-diagnostics-20261030T093534728429/uorb-diagnostics/11-raw.json)。

NaN源语义初核：[EKF2::PublishStatus](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF2.cpp#L1210)
调用get_innovation_test_status；[ekf_helper.cpp](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/ekf_helper.cpp#L890)
先设vel/pos=NAN，再按GPS、EV等辅助源条件更新，存在主动表达不可用的路径。
[两份源文本](../.runtime/runs/sim-flight-sw02c-stage-20261030T093533859011/nan-source-evidence.json)已冻结。
所以原文nan不能直接判为滤波器数值崩溃；它也不能进入当前有限数值合同或被静默改成0/null。
本轮没有读取完整flags/后续姿态选择链来确认此次每一辅助源状态，不能由源码路径宣布唯一根因。

## 5. 实际验证与保护

同451份冻结源码上新20项+旧49项飞行共69项通过；运动84项、全仓轻量972项通过。
旧normal250条/250次Run/1s、disconnect126条/125次Run/停.5s通过；均实际执行器0包。
[旧链报告](../.runtime/runs/sim-flight-sw02-stage-20261030T093554293952/report.json)与
[真实genpy线格式](../.runtime/runs/sim-motion-sw04a-20261030T093634636431/report.json)
包含77组场景字节、36组旧公共往返、18合成源转换，旧25定义/7入口保持；未用mock替代这些线格式检查。
单元测试中的transport替身仅用于可控地推进期限、确认停止行为，不作为实际客户端成功证据。

新诊断已经完成250条宿主记录，但query失败前未执行常规最终wire检查。
因此本轮将四个原始诊断文件复制到新stage的independent-host-copy，再运行既有独立校验器；
它在副本目录新增recording.jsonl，原输入逐字节保持，未回写失败run或重开仿真。
[独立宿主/wire报告](../.runtime/runs/sim-flight-sw02c-stage-20261030T093533859011/independent-host-audit.json)
确认250次Run/1s、250个实际HIL_SENSOR、RX2启动消息、实际HIL执行器0包，terminal为diagnostic_window_complete。
这只验证同FDM/wire子范围，不改变采集完整性失败。

源码审计确认原445文件仅改授权诊断入口，新增6文件；旧strict、旧profile、C++宿主/适配、
25定义/7入口、8原生msg/30原桥接源保持。三实际会话17自有PID均退出、端口free，无强制清理。
目录内所有历史失败/原文保留，无删除/Hash/依赖安装、同级研究仓修改或自动提交/推送。
恢复方式为新run，旧默认入口不受影响；退出和清理不冒充着陆/disarmed确认。

## 6. 未验证与下一任务

未验证：完整21次采集、三个runtime参数、250步之后的flags/姿态选择/控制/输出链、
正向执行器属性施加与当前周期绑定、v2/长窗/命令及受控飞行。
本次没有启ROS/Gazebo/RViz、真实DEM/占据融合、模型训练/完整推理或正式PERF；
research继续fail-closed，训练监督不进入在线链。

直接下一项SIM-FLIGHT-DIAG-DESIGN-04（计划；主责任simulation_engineer）：
基于已存第11次原文与get_innovation_test_status调用链，明确原生NaN的有效性语义及隔离补证方案。
重点是如何显式表示已确认不可用的诊断质量字段、保留原文/完整性和继续或停止边界，
而不把NaN作为合法浮点、异常当空块、整个状态当有效或放宽现有两个合同。
必须先审查精确字段/辅助源判据、异常反例、独立schema/显式模式是否必要及可执行范围；
原SW-02B/C未通过事实、21次白名单/1s/250步和墙钟/资源界保持，不重跑相同失败或自动扩窗/控制。

2026-10-30后续：[DIAG-DESIGN-04具体方案](SIM_FLIGHT_DIAG_DESIGN04_20261030.md)已交付，
精确限定两字段准确nan及同实例源标志条件、独立私有v2隔离表示与显式模式、20组未来验收。
本记录第11次拒绝和未完成采集结论保持；新合同/模式尚未实施，留SW-02D独立验证。
