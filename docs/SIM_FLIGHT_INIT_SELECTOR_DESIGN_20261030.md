# 初始化selector槽位隔离与关联观测设计

日期：2026-10-30；版本：v0.1；任务：SIM-FLIGHT-INIT-SELECTOR-DESIGN-01。
主责任：simulation_engineer；状态：已完成（具体设计/只读审查，尚未实现）。
依据：[实际拒绝/剩余任务](SIM_FLIGHT_INIT_SW02_PREPARATION_20261030.md#6-剩余能力与下一任务)、
[原离线合同](SIM_FLIGHT_INIT_SW01_CONTRACT_20261030.md)、ADR-044。
实验：[EXP-20261030-012](../experiments/2026-10-30-sim-flight-initialization-selector-design.md)。

## 1. 问题、范围与结论

原INIT-SW-02实际normal在500步/2s、第30次查询严格拒绝selector的8处nan，保留30份raw/29合法事件。
本设计区分9个estimator槽位与4个IMU槽位，提出独立私有selector观测合同及98项查询；
原84合同、codec/入口、失败结论、物理宿主和公共消息保持，不将历史raw重封装成当时合法事件。
本轮只有文档及离线审查，没有新配置/codec、daemon查询、FDM/PX4或ROS运行。

拟议处理允许准确、具名的非选中槽位缺失进入诊断记录，保留null/原token/原因；
选中设备仍需有限误差、前后独立设备表的稳定关联及原初始化门。
设备表与selector不是原子快照，也不能证明selector实际消费了该表的同一条消息。
后者明确未验证，不拿补查表伪造消费时间、严格周期绑定或控制许可。

## 2. 已审查的真实生产消费链

本轮冻结[6份原生源文本](../.runtime/runs/flight-init-selector-design01-20261030T121653053407/selector-sources.json)，
[24项定位事实](../.runtime/runs/flight-init-selector-design01-20261030T121653053407/source-facts.json)包含源码路径/行号/字面量。
源根是.runtime/src/px4-v1.13.3；没有修改第三方源或研究仓。

| 事实 | 源码与实际含义 |
| --- | --- |
| F01—03 | EKF2Selector.hpp:59/132/133：受限分支max=2，否则9；比值初始NAN。本设计只面向当前非受限SITL，不能推广到所有PX4构建 |
| F04—06 | EKF2Selector.cpp:265—310：收到estimator_status才登记设备/原时间；available取max(i+1)，不是当前健康数，也不是IMU数量。重选时对已见范围relative置0；范围内可以有历史/空洞 |
| F07—08 | 同文件:281—324：selector内部会将无效vel/pos/hgt比值换成1，并更新healthy/timeout；这是PX4内部算法，不授权诊断器补1，也不证明healthy=true等于姿态精对齐 |
| F09—15 | 同文件:153—232：只在消费sensors_status_imu时更新四槽误差；各自设备ID=0分支写NAN，非零分支累加并fmaxf(...,0)。gyro/accel分别判设备，不能互借身份 |
| F16/23/24 | 同文件:810—837：发布9比值/healthy及4误差，timestamp为selector发布时刻；没有发布消费的_last_update_us或完整IMU ID数组 |
| F17—19 | voted_sensors_update.h:65、.cpp:140—154：四槽来自vehicle_imu的uORB索引，分别存accel/gyro设备ID；不是EKF实例号，也不能强求gyro/accel主设备处于同一槽 |
| F20—22 | voted_sensors_update.cpp:400—429：新status零初始化；仅内部设备非零且配置priority>0时填该类槽，包含ID/inconsistency/healthy/priority，最后独立取timestamp发布。ID=0也可能表示未启用，不证明硬件物理不存在 |

上游链为vehicle_imu → VotedSensorsUpdate::sensorsPoll → sensors_status_imu →
EKF2Selector::UpdateErrorScores → PublishEstimatorSelectorStatus；另一路estimator_status更新9个实例。
下游当前为新准备宿主 → 原PX4 → ros_ws/sim_flight_initialization_queries.py →
simulation/ufm_simulation/flight_initialization_observation.py → tests独立审计。
原parse_native除estimator_status两字段条件隔离外使用严格_block/_native_field；selector准确nan仍报probe_native_float。
原checkpoint_ready读selector的身份/健康和vehicle_imu设备关联，不读四槽误差；拟议新判定必须补选中槽位条件。
没有SensorBundle/定位/TF/map/研究forward消费者，不能借私有诊断更改在线状态权威。

## 3. 拟议解析规则与缺失表示

先按冻结原生布局校验完整键集、重复字段、类型、定长数组、原生打印语法和整数时间，再作槽位判断。
selector只能是完整单载荷（未知原生实例号仍null），或沿原合同的未发布/无载荷态；
部分正文、额外字段或混合畸形不是“不可用”。原生准确小写nan仅可出现在下表列出的数组元素。
其余字段沿原严格规则；inf/-inf/+nan/NaN、带括号伪token、JSON NaN、非有限数字均拒绝。

| 字段/条件 | 新合同拟议动作 |
| --- | --- |
| instances_available=A，primary=p | 有载荷时要求1≤A≤9、0≤p<A；整数严格，healthy长度9且仅bool |
| combined/relative，0≤i<A | 必须有限，不接受nan；combined>0，relative可负/零。不凭healthy=false豁免。A是高水位，范围内历史空洞保持拒绝，不能猜其没用 |
| combined/relative，A≤i<9 | 当前9实例构建下要求准确nan且healthy[i]=false；两数组各自完整隔离。非有限无通用豁免；与冻结源假设矛盾的有限尾值也拒绝，不兼容其他构建的零初始化尾槽 |
| accumulated_gyro_error / accumulated_accel_error，0≤i<4 | 有限时须≥0，零和负零保留原义；准确nan可记录为native_imu_slot_unavailable。两类分别处理，不能由A、p或healthy推断设备ID |
| 选中IMU误差为nan | 可以完整记录此原生缺失，但该检查点不就绪；绝不补零或跳过选中槽判定 |

有缺失时实例state=payload_quality_unavailable，顶层state同名、reason=native_optional_quality_unavailable；
原文stdout不改，fields保留全部字段和定长数组，允许处仅该元素为null。
selector的unavailable_fields每项精确为field/index/native_token/reason，按字段顺序combined、relative、gyro、accel及索引递增；
field只能是这四字段，index各0..8或0..3，native_token只能nan；
reason只能native_estimator_slot_not_seen或native_imu_slot_unavailable，分别对应两组规则。
每个null恰有一项说明，有限元素无说明；删/增/重排/重复/错索引/错token或原因不符均拒绝。
此前estimator_status的vel/pos两标量仍只采用原同块mask/三键说明，不能添加index或套用selector规则。

native_imu_slot_unavailable表示本次selector报告该槽没有可用误差，其来源是冻结生产分支；
它不提供本次设备ID、所消费消息时间、当前健康或真实设备不存在证明。
单条解析不依赖后来查询倒填身份；关联信息由第5节独立评价，不能事后改原事件。
第30条原文在未来新解析器中的预期仅是8个null/8项说明，不能由它单独获得就绪或历史运行通过。

## 4. 拟议独立schema、文件与迁移

为避免重写原宿主，将物理记录和新观测数据集显式组合。新增文件范围拟为：
configs/sim_flight_initialization_selector_fixture.json、simulation/ufm_simulation/flight_initialization_selector.py，
tests独立字面量/native基线/输入工厂/单元测试及离线阶段工具；本轮均未创建。
随后运行器另新增ros_ws/sim_flight_initialization_selector_queries.py和..._run.py，不改原入口默认行为。

| 新schema | 精确顶层键与值 |
| --- | --- |
| sim_flight_initialization_selector_fixture.v1 | schema_version/profile_id/fixture_only/simulation_only/observation_only/commands_enabled/capture_active/physical_profile/checkpoints/topics/parameters/limits；profile_id=sim-flight-initialization-selector-observe-v1，fixture_only/simulation_only/observation_only均true，commands_enabled/capture_active=false。physical_profile为原完整fixture精确副本；其余按本设计固定 |
| sim_flight_initialization_selector_recording.v1 | schema_version/run_id/clock_id/profile/physical_files/binding_status/control_gate_accepted；profile为新fixture全文，clock_id=sim:<run_id>，绑定只unverified、控制只false |
| sim_flight_initialization_selector_query.v1 | schema_version/run_id/clock_id/checkpoint/query_index/kind/name；类型与旧query一致，但只能匹配新98项计划 |
| sim_flight_initialization_selector_observation.v1 | schema_version/query/argv/owner_before/owner_after/last_hil_us/fdm_time_s/wall_start_ns/wall_end_ns/returncode/stdout/stderr/observation/binding_status/control_gate_accepted；封套类型/owner/原文投影约束沿原合同，新query和第3节实例缺失结构除外 |

fixture_only/simulation_only/observation_only是三个独立true字段（非新运行能力声明）。
limits复制原数值/精确键集，query_records仍128；98是由新固定计划强制的精确条数，不新增max_queries别名。
physical_profile内部旧84计划原样保留，仅描述物理生产profile，
不是新数据集查询数；顶层topics/parameters/checkpoints与98计划才是新观测唯一权威。

新header文件名selector-header.json，physical_files精确四键：
header=header.json，steps=diagnostics/steps.jsonl，terminal=diagnostics/terminal.json，wire=diagnostics/wire.jsonl。
这些是同run固定相对路径，无任意路径/符号链接逃逸或外仓读取；只读实际物理文件，不另造改戳副本。
原物理header/step/terminal仍为sim_flight_initialization_* v1，原C++无需新增schema。
新离线组合校验先用原物理合同校验header/steps/terminal和原profile，再核对两套header的run/clock/文件路径、
末step和物理时间完全关联，之后校验新观测。新fixture绝不传给原物理header validator冒充兼容。
新queries只存selector-queries/observations.jsonl；raw、组metadata与新header也用独立新目录文件，原84 reader不能读取。
同run不能同时执行84/98两计划；原新query/observation/fixture/recording交叉版本拒绝，绝无自动检测后降级或fallback。
原物理codec纯校验、旧字段解析纯函数可以复用；不得通过改全局PREFIX/TOPICS、伪造旧query或热改旧parser来实现。

新源基线先冻结10份原生msg（原9+sensors_status_imu）和本次6份selector/传感器源文本，
具名消费者为布局/隔离源语义预检，漂移即spawn前拒绝。无需新增Hash；源文本不证明实际二进制任意更新仍兼容，
运行阶段还须核原SITL构建/宿主适配身份；新/受限构建不是本方案静默支持对象。

## 5. 98项查询与关联/就绪判定

保持125/250/500/1000/1500/2000/2500七检查点，125步先原七show参数。
每组13项依次为sensors_status_imu_before、selector_before、vehicle_imu、estimator_status、
estimator_status_flags、estimator_attitude、vehicle_attitude、vehicle_control_mode、actuator_controls_0、
actuator_outputs、vehicle_land_detected、selector_after、sensors_status_imu_after。
逻辑before/after是计划中的重复位置，不是新话题或argv别名；name仍sensors_status_imu/estimator_selector_status。
新argv仅原owned px4-listener --instance 0 <精确name> -n 1或原七px4-param show，不能附加任意参数。
总7+7×13=98；各组query_index为8—20、21—33、34—46、47—59、60—72、73—85、86—98。
500步新selector_before将是35，但历史第30条绝不改编号或转成新35条运行证据。

sensors_status_imu严格解析冻结的11个原生字段：timestamp、accel_device_id_primary、accel_device_ids[4]、
accel_inconsistency_m_s_s[4]、accel_healthy[4]、accel_priority[4]，gyro对应五项。
timestamp uint64、ID uint32、priority uint8、healthy bool；两inconsistency数组全有限且≥0，不能豁免nan。
ID为0的输出槽按生产零初始化须inconsistency=0/healthy=false/priority=0；非零ID不等于healthy=true。
gyro/accel各自非零ID不得重复，零可重复；矛盾数据拒绝，不能从另一类或实例号推ID。
单实例原编号null仍只表示原生单载荷；无需伪造实例0才能查设备表。

结构合法但未发布/无载荷/过期、设备变动或身份不一致时，采集可以继续，检查点显式不就绪：

1. 先执行原selector前后稳定主实例/变更计数/四设备ID、status/flags/姿态/vehicle_imu/land/mode与年龄门。
   新增前后A相同、selector故障标志均false；保留原参数、单位四元数、原生整数/未来/倒退拒绝。
2. 两份sensors_status_imu均完整、新鲜（timestamp>0、≤last HIL、年龄≤200000us），原戳不倒退。
   各类四槽ID向量和primary ID须前后一致且分别等于selector主设备ID；每个主ID在本类表中恰出现一次，
   由此分别得gyro_slot/accel_slot，不要求两槽相同，不要求槽号=primary_instance。
3. 这两个主槽在前后设备表中healthy=true且priority>0；在前后selector相应误差数组中均有限。
   其他非零设备槽若selector报nan，或ID=0而selector仍有限，则关联不一致，不就绪；记录原样留存。
   非选中且ID=0的缺失槽可存在；不能让全四槽nan通过主槽门。
4. 此关联只是当前前后观测一致：不要求sensor timestamp=selector timestamp，不写入推测消费时间，
   不宣称丢失的中间更新不存在。缺失/不一致只影响本次关联和初始化门，不自动推断当前物理设备故障。
   重新到下一固定检查点观察，不临时加查询/重试/扩窗；2000/2500仍须同时满足原连续静稳/初始化门。

新增关联结果每检查点精确键：checkpoint/association_kind/reason/gyro_slot/accel_slot/
sensors_before_timestamp_us/sensors_after_timestamp_us/selector_before_timestamp_us/selector_after_timestamp_us/
selector_consumed_imu_timestamp_us/exact_source_message_verified。
association_kind只observed_stable_ids/unavailable/inconsistent；reason依次允许空字符串、
imu_table_unavailable_or_stale、imu_table_changed、imu_primary_identity、imu_slot_unhealthy、selector_imu_slot_mismatch，
按上述检查顺序返回首原因；缺失时间/槽为null，其余为原uint64/0..3整数。
selector_consumed_imu_timestamp_us始终null，exact_source_message_verified始终false，禁止填最近观测时间。
四门仍为collection_complete/input_settled/initialization_ready/output_chain_observed；
另报selector_payload_complete（含任何数组null即false）和上述关联，不把采集完整写成所有数值可用。
通过原四门的合成结果也不改变binding_status=unverified/control_gate_accepted=false。

## 6. 有界、停止与恢复

98项严格顺序/一次性；未达到全数不能判完整，不因部分不可用跳组或缩减计数。
所有本地类型、精确键、重复/坏JSON/UTF-8、监督字段和编码前文本界沿原合同；
event≤256KiB、raw stdout+stderr≤32KiB、query含metadata总量≤16MiB、深度8/节点8192/list512保持。
step≤16KiB/2500条/64MiB、wire≤16MiB/8192事件、case≤256MiB，含新header/profile/raw/日志全计。
增加14次查询不会自动提高任何总量；新嵌套profile/说明也必须在原深度/总量界内。
墙钟build180s/startup60s/preparation60s/session120s、transaction1s/client200ms/group400ms保持；
13项是否可在400ms内完成属于后续实际验证，超时失败，不静默调宽。
查询须在本检查点Run后、下一HIL前原文与合法事件落盘；原source/HIL时间及1ns容差不改。

owner/argv/错身份/armed/非零执行器/未来或倒退时间/结构与数值违规/期限或字节超界仍立即停止；
原文先保存，非法对象不写成正常事件。保存失败即停止；不以继续采集覆盖故障。
单纯结构合法的未发布/不可用/关联不一致保留本检查点否决，至2500步未就绪明确失败。
仅清理本run进程/端口，不写参数/命令；回退为显式选择原84入口，原合同仍会拒绝同样nan，
不能把回退当成功恢复。旧30raw失败保留，新增run另目录，禁止补采或回填旧manifest。

## 7. 先行独立预期与实施拆分

下一项INIT-SELECTOR-SW-01先保存手工字面量/原生源基线，再实现新离线合同；
独立预期不调用被测parser/plan生成。以下S01—24是拟议测试分组，不是本轮新增测试通过数：

| 组 | 独立预期 |
| --- | --- |
| S01—04 | 历史30raw新解析精确8个null/说明且单独不就绪；原codec仍报probe_native_float；A=9无尾缺失；A=1主实例0合法且剩余8槽缺失 |
| S05—08 | A=0/10、p越界、bool充整数拒绝；范围内nan/healthy=false不能豁免；范围外healthy=true或有限尾值拒绝；错数组长度/删除字段/错说明索引与顺序拒绝 |
| S09—12 | 主实例1但gyro槽2/accel槽0可稳定关联；gyro/accel零ID独立、全槽nan不就绪；重复ID、零ID配非零inconsistency/priority或healthy=true拒绝；主ID缺失/变更/healthy=false/priority0不就绪 |
| S13—16 | 非主槽nan与设备表不符不就绪；所有非豁免nan/inf/大小写伪token拒绝；新鲜不同topic时间可记录而exact_source_message_verified=false；未来/倒退/小数时间拒绝，过期仅不就绪 |
| S17—20 | 98精确顺序/七参数和七组编号；少/多/重复/改argv/owner/跨run拒绝；84与98封套交叉拒绝、物理组合错run/path拒绝；旧两字段mask条件保持及监督字段/坏JSON拒绝 |
| S21—24 | 编码前超长、深度/字节/节点/总量和期限边界；2000/2500双末检查点、原静稳/姿态/输出门与关联缺失分别否决；独立合成2500步/98事件实际字节与文件重读；源漂移预检拒绝，旧公共线格式/入口/历史失败兼容 |

SW-01只新增私有fixture/严格codec/纯判定、独立输入/预期及tests阶段工具，不启动FDM/daemon或改旧运行器。
完成后再INIT-SELECTOR-SW-02：独立显式98项薄装配，复用原同FDM物理宿主/硬门，先离线坏原文/故障，
再一次新规则正常准备及断连接/期限停止、原始wire/物理/原文/设备关联和清理对账。
按实际结果报告完整/不可用/未就绪，不能为通过改IC/模型/阈值或延长10s；旧失败不改。
公共Scene v2/长窗采样、严格周期绑定/非零属性因果、模式/arming/manual和离地继续属于后续SW-03/04，
研究质量、真实数据/DEM/占据融合/机载资源不在这两个私有工作包中。

## 8. 本轮验证与限制

[审查报告](../.runtime/runs/flight-init-selector-design01-20261030T121653053407/report.json)：
24项源码定位、历史实际wire/500条物理记录/29事件重读、8处原文索引和旧严格拒绝复现通过；
既有飞行定向134/134通过，476份源码/配置与上一阶段快照逐文本相同。
这些验证旧代码和设计依据，未执行新解析规则、98计划或新准备运行。
本轮只改文档，未重跑全仓；1037/1037仍是上一轮实际结果，不能算本轮新协议验证。
完整准备/选中姿态就绪、同消息消费身份、严格绑定/控制和飞行验收均未新增通过证据。

2026-10-30后续：[INIT-SELECTOR-SW-01](SIM_FLIGHT_INIT_SELECTOR_SW01_CONTRACT_20261030.md)已完成独立私有离线合同，
两组合成2500步/98事件/101次JSON往返与新28/飞行162/运动84/全仓1065项通过，原476源码/旧失败保持。
下一项SW-02才单独新增98项实际装配/准备与故障交接；本设计所列同消息消费/控制能力仍未验证。
