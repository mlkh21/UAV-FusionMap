# 原生质量隔离与21次有界采集交付

日期：2026-10-30；任务：SIM-FLIGHT-SW-02D；主责任：simulation_engineer。
状态：已完成（私有隔离软件、实际有界采集及兼容回归子范围）。
依据：[DIAG-DESIGN-04](SIM_FLIGHT_DIAG_DESIGN04_20261030.md)、ADR-044。
实验：[EXP-20261030-008](../experiments/2026-10-30-sim-flight-quality-collection.md)。

## 1. 结果与边界

独立私有sim_flight_uorb_diagnostic.v2、两字段条件隔离、有界记录器及显式
--uorb-quality-diagnostics已实现；实际21次查询、原生原文/JSON重读、宿主/wire与清理核对通过。
运行参数SYS_AUTOSTART=1033、SYS_CTRL_ALLOC=0、SENS_IMU_MODE=0均实际show读回，没有写参数。
结果为diagnostic_collection_complete=true、body_complete=false、payload_complete=false；
binding_status=unverified、control_gate_accepted=false。私有v2不是公共Scene v2或控制接口。

本次六实例的状态比值共12处nan按同载荷源条件显式隔离；其余非有限仍拒绝。
实际250步/1s内执行器回包仍0；所有已读flags样本cs_tilt_align/cs_yaw_align=False，
selected姿态无载荷，故不能把采集完整当姿态/输出就绪或当前周期执行器绑定通过。
旧SW-02B/C运行结论仍未通过，不回填或自动fallback。

[最终阶段报告](../.runtime/runs/sim-flight-sw02d-stage-20261030T101130232351/report.json)、
[独立关闭审计](../.runtime/runs/sim-flight-sw02d-stage-20261030T101130232351/closeout-audit.json)。
同458份源码飞行92/92、运动84/84、全仓轻量995/995、旧实际入口与消息兼容通过。

## 2. 修改文件与真实链路

| 文件 | 作用及原因 |
| --- | --- |
| [flight_probe_quality.py](../simulation/ufm_simulation/flight_probe_quality.py) | 新私有v2原生解析/严格codec/流校验及源语义基线核对 |
| [sim_flight_uorb_quality.py](../ros_ws/sim_flight_uorb_quality.py) | 独立质量记录器、预检与实际只读客户端；复用旧类的有界IO/guard，不调用旧v1状态解析来放宽NaN |
| [sim_flight_diagnostic_run.py](../ros_ws/sim_flight_diagnostic_run.py) | 唯一改动的既有源码，增加互斥显式分支、检查点及独立结果字段 |
| [sim_flight_quality_cases.json](../tests/fixtures/sim_flight_quality_cases.json) | 20组先行字面量/投影预期、16组源位组合及独立字段期望 |
| [sim_flight_quality_baseline.json](../tests/fixtures/sim_flight_quality_baseline.json) | 机械提取已审计原文、四段源语义及8份原生消息，保护具名解析/隔离条件；没有Hash |
| [sim_flight_quality_fixture.py](../tests/sim_flight_quality_fixture.py) | 测试输入/封套及字面量投影，不由被测v2解析器生成oracle |
| [test_sim_flight_quality.py](../tests/test_sim_flight_quality.py) | 新增23项，覆盖Q01—20、16组合、预启动/写后期限和CLI互斥 |
| [sim_flight_quality_stage.py](../tests/sim_flight_quality_stage.py) | 实际采集一次、独立重读/原文与宿主对照、旧stage及轻量回归 |

配套修改本说明、中文实验、PROJECT_STATUS/README、架构/数据/接口/坐标、开发计划、
ADR-044、实验索引及设计后续。七个新增源码/fixture文件，既有源码仅改诊断runner；
旧codec、记录器、stage、公共消息/profile、C++宿主/桥接和第三方原源保持。
数据链为原宿主逐step收据→监督器暂停next→本次PX4/daemon身份核对→原生只读查询→
原文/私有事件→tests独立审计。没有新ROS话题/服务、状态/TF发布者、定位/地图或模型消费者。

## 3. 合同、源语义与预算

顶层仍精确保存schema_version/query/argv、owner_before/after、last_hil_us/fdm_time_s、
wall_start/end_ns、returncode/stdout/stderr、observation、binding_status/control_gate_accepted，
版本明确为sim_flight_uorb_diagnostic.v2。observation精确含state/reason/instances/parameter。
每实例新增unavailable_fields，只有完整estimator_status块中的两个float32标量可以隔离：

- vel_test_ratio准确为nan且同块flags & 0x0100000c == 0，即GPS/EV速度/光流源位均0。
- pos_test_ratio准确为nan且同块flags & 0x00001004 == 0，即GPS/EV位置源位均0。

flags必须为uint32且十进制与完整32位二进制标注一致，不能借另一实例/旧查询的标志。
完整检查其余字段后才判断隔离；准确原token、native_ratio_source_not_selected原因与字段名显式保存，
对应字段为null。null与描述一一对应，固定顺序，NaN本身不进入合法JSON数值。
新增payload_quality_unavailable及native_optional_quality_unavailable原因，不归为空正文或payload。
混合块按空正文优先、其次质量不可用、否则全payload归并；各块内容与描述不丢失。
单实例无显式编号保持null，多实例编号/顺序保留，不能推断primary或控制许可。

其他字段的nan/inf、拼写变体、错条件/未知字段/缺失或重复字段/坏类型/数组、坏JSON/schema/
身份/UTF-8/时间/监督字段均拒绝。有限0/负号按原规则保留，不以质量条件覆盖原值。
三个参数仍只允许完整show和值1033/0/0，任一已读模式块armed=true立即停。
两个旧v1 codec对原NaN原文继续拒绝，v2与两个旧schema交叉拒绝。

构建前核对冻结的消息布局与get_innovation_test_status、控制位结构、PublishStatus及
辅助源选择四段关键源语义；变化时拒绝假设旧条件成立。运行前保存四份完整源文本，退出后逐文本核对。
这些文本有明确消费者和失败行为，没有新增Hash；旧原文只供测试验证，不被在线当传感器/状态输入。

独立新run前缀sim-flight-sw02d-quality-，uorb-quality-diagnostics内保存原文/quality-diagnostics.jsonl及组记录。
只在正常用例显式启用，与旧probe/diagnostics、disconnect/build-only互斥，不自动切换。
固定125/250步各九topic及最后三个show，共21查询，无重试、额外flags查询、-i/-r或控制命令。
所有查询绑定本次PX4 PID/start_ticks/exe/rootfs和socket文件/内核所有权，前后不符即停并清理自有会话。
期限覆盖身份核对、执行、解析、投影、落盘；spawn前、写后和下一query/next前复查。

保持每客户端200ms/每组400ms、原文32KiB、事件/头256KiB、事件32/查询文件总8MiB、
深度8/节点8192/列表512和原5s bootstrap/30s session、250步/1s源时间硬界。
头/布局/源基线/报告/隔离描述均计预算，新模式仅省略已声明额外6ms监督sleep，4ms源步长/10ms轮询保持。
不放宽门槛，不隐藏准备或改戳。质量隔离仅允许诊断继续，不给业务状态/控制放行。

## 4. 实际证据与剩余缺口

独立预期和机械来源基线先冻结于[oracle目录](../.runtime/runs/sim-flight-sw02d-oracle-20261030T100529339136/sim_flight_quality_cases.json)，
之后才实现v2与记录器；当前fixture、oracle和实际run输入逐字节一致。
本轮没有失败后调阈值或扩大白名单，完整stage一次通过；旧失败全部保留。
实际run为[101131381746](../.runtime/runs/sim-flight-sw02d-quality-20261030T101131381746/manifest.json)。

| 检查点/对象 | 实际观察 | 边界 |
| --- | --- | --- |
| 两组IMU | 各3实例；125组timestamp/sample=492000us，250组992000us | 积分IMU可读，不等于EKF倾角对齐 |
| 125组status/flags/attitude | 各6空实例；selector/vehicle_attitude/outputs亦无正文 | 明确不可用，不填0/姿态或执行器值 |
| 250组estimator_status | 6完整正文，各两比值获准隔离；mask=537002496，timestamp988000us/sample908000us | 12条显式质量不可用，非完整有限载荷或fresh证明 |
| 250组estimator_status_flags | 6实例样本均tilt/yaw=False、baro_hgt=True、gps=False；0/1的timestamp964000us，2..5为828000us | 各自原戳，不能作为原子同tick或对齐完成证据 |
| estimator_attitude/selector/vehicle_attitude | 250组仍无载荷 | 尚无被选姿态和primary关联 |
| vehicle_control_mode | 125/250组timestamp24000/528000us，armed=False、manual=True、rates/attitude=False | 只说明两个已读样本，不能外推整段disarmed/fresh或作为准入 |
| actuator_controls_0/outputs | 两组controls均never published，outputs无正文，真实wire执行器0包 | 不转成零控制或已施加属性 |
| 三参数show | 1033/0/0，均完整原文/整数校验通过 | 运行配置核对，不表示姿态/控制已就绪 |

21条query状态为8 payload（含3参数）、2 not_published、10 payload_unavailable、1 payload_quality_unavailable；
实例计数14 payload、30无载荷、6质量不可用。21条实际JSONL79062字节，连同查询元数据共446431字节。
125 topic/250 topic/参数组实际墙钟分别37416114/45050790/13511114ns；最后组结束距初始墙钟2719938252ns。
这些仅为本次预算核对，不是RSS、时延统计/实时倍率或正式PERF。

[独立重读](../.runtime/runs/sim-flight-sw02d-stage-20261030T101130232351/acquisition-result.json)
重新解码21条、核对每份原文argv/输出/返回码、宿主检查点/HIL/FDM、三组时间与summary一致。
同run[宿主/wire验证](../.runtime/runs/sim-flight-sw02d-quality-20261030T101131381746/verification.json)
确认250次Run/1s、250个实际HIL_SENSOR、RX2启动消息、执行器0包、原高度界与terminal保持。

源码[PublishAttitude](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF2.cpp#L635)要求attitude_valid，
[后者](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/estimator_interface.h#L123)需要有限四元数及tilt_align。
本次flags已有“尚未对齐”的直接样本，并有姿态缺失证据，缺口收敛到初始化/姿态准入段，
不再仅凭wire缺回包猜测；但不同戳快照不能判唯一根因、收敛时间或证明扩窗必定恢复。
[三份源文本](../.runtime/runs/sim-flight-sw02d-stage-20261030T101130232351/initialization-source-evidence.json)另行冻结。

## 5. 回归、保护与恢复

新增23项与旧69项飞行共92项通过，运动84项/全仓995项通过；
[旧normal/disconnect](../.runtime/runs/sim-flight-sw02-stage-20261030T101151637988/report.json)
分别250条/250次Run/1s、126条/125次Run/停.5s，通过原wire/高度/清理；执行器均0包。
旧真实genpy线格式为77组场景字节、36组公共往返、18合成源转换，详见旧stage的legacy_report；
不是以mock替代线格式。测试里的transport替身只验证可控的预启动/写后期限停止，不作实际客户端证据。

关闭审计确认原451文件仅改诊断runner，新增7文件；25份旧定义/7入口、8原生msg、
四份源语义文件/30份桥接原源保持，458份源码在实际采集/回归期间逐文本未变。
三实际会话27个自有PID均退出，端口free，无强制清理；不清理其他会话或删除历史产物。
没有安装依赖、算Hash、修改同级研究仓或自动提交/推送，全部既有dirty/未跟踪内容保留。
后续恢复用新run，旧入口维持；清理不冒充已着陆或disarmed确认。

## 6. 未验证与直接下一任务

本包只关闭私有质量隔离软件/21次有界采集及兼容子范围。未验证有效selected姿态、
正向执行器属性施加/当前周期绑定、公共Scene v2、长窗准备、命令及受控飞行。
没有启动新ROS/Gazebo/RViz图、真实DEM/占据融合、训练/完整模型或正式PERF；研究质量继续暂缓。

直接下一项SIM-FLIGHT-INIT-DESIGN-01（计划；主责任simulation_engineer）：
以本次六实例tilt/yaw未对齐、选中姿态缺失和同FDM/IMU输入为依据，形成无控制准备期与SW-03衔接的具体方案。
先只读审查地面IC/真实动力学、初始化/收敛条件、源时间/墙钟/停止界及所需观测，
明确是否需要独立新profile/窗口与相应验收，不假设“多跑几秒就会恢复”。
本轮没有批准或实施扩窗、新IC、公共v2/长准备/命令，不重复已完整的21查询作为新任务；
任何后续运行范围变化须先交具体方案，旧1s入口/预算和控制门保持。

2026-10-30后续：[INIT-DESIGN-01](SIM_FLIGHT_INIT_DESIGN_20261030.md)已交初始化准备具体方案，
32项源码核验、保存wire重读及92项既有定向通过；没有新准备期运行。
直接下一项INIT-SW-01先做独立私有合同/预期，原SW-02D结论和控制门保持。
