# 原生NaN质量字段的语义与隔离补证设计

日期：2026-10-30；版本：v0.1；任务：SIM-FLIGHT-DIAG-DESIGN-04。
主责任：simulation_engineer；状态：已完成（具体设计/只读核验，尚未实施新合同或模式）。
依据：[SW-02C实际NaN拒绝](SIM_FLIGHT_SW02C_DIAGNOSTICS_20261030.md)、ADR-044、
[EXP-20261030-007](../experiments/2026-10-30-sim-flight-native-quality-design.md)。

## 1. 决定与范围

SW-02C实际11次查询/10条合法事件，第11次estimator_status的六实例均有vel_test_ratio、
pos_test_ratio原文nan，按有限数值合同停止，完整21次采集未通过。本轮不重跑相同失败或改写此结果。

只为这两个源代码明确含不可用默认值的诊断比值设计隔离表示：完整保留原文，
在同一实例的完整载荷中核对固定源标志条件，才允许将该字段标为显式不可用。
NaN不成为合法浮点，也不归为空载荷或有效状态；其他字段/不符条件的非有限仍立即停止。
现有snapshot v1、diagnostic v1及两个显式模式保持严格拒绝和历史失败。

直接实施工作包SIM-FLIGHT-SW-02D（计划）：独立私有sim_flight_uorb_diagnostic.v2与
显式--uorb-quality-diagnostics正常用例，固定原21次查询/1s/250步及原墙钟/资源界。
这是私有记录版本2，不是Scene公共protocol_version=2，不增加ROS业务端点或控制能力。
本轮没有实现/运行该新合同或模式。

## 2. 源码事实与已有输出

本轮[冻结九份源文本](../.runtime/runs/flight-diag-design04-20261030T094904639779/source-evidence.json)，
[20项语句/行号核验](../.runtime/runs/flight-diag-design04-20261030T094904639779/source-checks.json)通过。

| 源码 | 与本问题相关的事实 | 解释限制 |
| --- | --- | --- |
| [EKF2::PublishStatus](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF2.cpp#L1206) | 同一status正文包含control_mode_flags，并由get_innovation_test_status填各比值 | 不使用另一次flags话题的“最新值”替代本载荷条件 |
| [get_innovation_test_status](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/ekf_helper.cpp#L890) | vel/pos先设NAN，GPS分支可更新两者，EV速度只更新vel、EV位置只更新pos | 默认NAN不独自证明滤波器数值崩溃 |
| 同函数921行 | 唯一水平辅助源为光流时可更新vel | opt_flow=true不一定是唯一源，但本方案保守拒绝其vel NaN隔离 |
| [isOnlyActiveSourceOfHorizontalAiding](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/estimator_interface.cpp#L504) | 还计GPS、EV位置/速度及空速与侧滑组合源 | 不手写近似逻辑把任意光流NaN放行 |
| [filter_control_status_u](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/common.h#L465) | GPS=bit2、光流=bit3、EV位置=bit12、EV速度=bit24；完整结构含32位 | 以冻结版本源码/消息位定义为依据，不凭变量名猜位序 |
| [estimator_status.msg](../.runtime/src/px4-v1.13.3/msg/estimator_status.msg#L87) | 两比值是float32，控制模式为uint32 | 原生打印的nan不是该工程合同里的有限数值 |
| [原生打印](../.runtime/src/px4-v1.13.3/platforms/common/uORB/uORB.cpp#L349) | float按%.4f打印，flags另印由同值生成的二进制标注 | 原文投影不能恢复float32位模式或同tick控制绑定 |
| [现有finite解析](../simulation/ufm_simulation/flight_probe_contract.py#L105)及[diagnostic v1](../simulation/ufm_simulation/flight_probe_diagnostic.py#L14) | nan仍拒绝，不支持字段隔离 | 原两个合同不因新设计而变更 |

辅助源标志表示相应融合的意图/状态；不是“收到GPS包”的同义词，也不是整架飞机是否存在水平辅助。
例如EV位置可启用而速度比值仍无对应报告源，空速/侧滑组合也可能影响水平辅助计数却不直接填这两个比值。
因此隔离原因只能称native_ratio_source_not_selected，不能叫“整机没有定位”或“唯一根因已确定”。

[第11次输出的离线字段核对](../.runtime/runs/flight-diag-design04-20261030T094904639779/archived-status-field-audit.json)
确认六实例0..5字段集完整，各两个token准确为nan，其余字段可按既有类型规则解析；
control_mode_flags均为537002496（0x20020200），与原文32位二进制标注一致。
GPS/光流/EV位置/EV速度四位均0，因此符合下节两条拟议条件。
这是对已存原文的源语义投影，不是新事件已接受、有效EKF状态/姿态或采集完整证明。
旧两个解析器仍报probe_native_float，旧run和10条合法事件未改写。

## 3. 两字段白名单与同载荷条件

仅限query.name=estimator_status、msg字段类型为float32标量，且该实例正文/全字段集合完整。
分类前先检查所有字段/重复键/类型/尺寸/标注，收集原始token；不得遇到nan就跳过剩余字段。
只能使用同一块完整control_mode_flags的uint32整数，不取其他实例、查询、历史或另一个topic的标志。
该flags行须具有原生完整32位二进制标注，位值与十进制相同；缺失/矛盾/未知布局均停止。

| 字段 | 允许隔离的全部条件 | 固定掩码 |
| --- | --- | --- |
| vel_test_ratio | 原token恰为小写nan，GPS=0、EV速度=0、光流=0 | flags & 0x0100000c == 0（16777228） |
| pos_test_ratio | 原token恰为小写nan，GPS=0、EV位置=0 | flags & 0x00001004 == 0（4100） |

条件逐字段、逐实例核对，可只隔离一项；另一项仍须独立满足条件或为合法有限数。
速度条件故意比原生“光流非唯一源”路径更窄：任何光流位为1都不隔离速度NaN，
避免复制飞控内部辅助源选择逻辑。GPS/相应EV源位为1时出现nan仍失败，不推断为正常缺失。
有限值沿原类型/打印精度规则保留，0不改为缺失；本条件不是由比值大小推断置信质量。

只接受准确token nan；NaN、-nan、nan(payload)、inf、-inf、溢出、额外标注/尾文均拒绝。
姿态q、IMU、执行器值、位置精度、output_tracking_error、mag/hgt/tas/hagl/beta比值等不在白名单，
即使别处源码也存在NAN默认路径，本包仍拒绝，不能预先扩大范围。
fault_flags等有限整数原样保留为诊断，不能由可隔离的两个比值推出fault=0或其他状态有效。
同块任一其他字段坏、缺失、重复或非有限，整条查询失败，不能生成“部分成功”来继续。

## 4. 新私有事件表示

拟议sim_flight_uorb_diagnostic.v2的顶层精确字段与v1相同：schema_version、query、argv、
owner_before/after、last_hil_us、fdm_time_s、wall_start/end_ns、returncode、stdout/stderr、
observation、binding_status、control_gate_accepted；版本值必须明确为v2。
query仍复用原sim_flight_uorb_query.v1的固定21项，owner与原始时间语义、有限JSON限制不变。

observation仍精确包含state、reason、instances、parameter，但新增第四个显式state：
payload_quality_unavailable，reason=native_optional_quality_unavailable。
原payload、not_published、payload_unavailable三态语义保持；未知状态/字段不能默认接受。
每实例精确键改为instance、state、fields、unavailable_fields，不回写或交叉送入v1 codec。

| 实例state | fields | unavailable_fields |
| --- | --- | --- |
| payload | 冻结msg完整字段集，所有数值有限且类型正确 | [] |
| payload_unavailable | null，仅合法标题无任何正文 | [] |
| payload_quality_unavailable | 完整字段集；只允许白名单中获准隔离的项为null，其余字段严格有效 | 1或2条显式描述，不能省略 |

每个unavailable_fields描述精确键为field、native_token、reason；field只能为上述两项，
native_token固定字符串nan，reason固定native_ratio_source_not_selected。
按vel_test_ratio、pos_test_ratio的固定顺序保存，禁止重复/乱序/超过2项。
fields中每个null与描述一一对应，必须能从原文、同块flags和固定条件重新核对；
没有描述的null、描述存在但原文为有限数、原文nan却伪造0均拒绝。
此处null是有原文与明确原因的不可用值，不是默默替换；原始浮点NaN永远不能进入JSON数值。

混合实例的顶层归并顺序：有完全无正文块→payload_unavailable；否则有质量隔离块→
payload_quality_unavailable；否则全为payload。每块的fields/隔离描述仍完整保留，不能被顶层遮蔽。
native明确never published时instances=[]，只有not_published；不能同正文混合。
单实例无显式编号仍为null，多实例保留编号/顺序，不能用完整块代替空块或推断primary。
非estimator_status块不得携带任何unavailable_fields条目；参数仍只允许完整payload且值1033/0/0。
任一完整模式块armed=true仍立刻停止，不因其他实例/质量不可用而忽略。

新codec按原文重新构造并逐类型比较投影，拒绝额外/训练监督字段、重复JSON键、坏身份/版本/时间、
bool整数、非有限JSON数值、未知reason、超限/错误UTF-8；v2与两个旧schema双向拒绝。
即使原文已保存，非法字段不能伪装成已验收的v2事件；只保留失败原文及停止结果。

## 5. 显式模式、预算与报告

拟议--uorb-quality-diagnostics与--uorb-probe、--uorb-diagnostics互斥，拒绝disconnect/build-only组合。
新run前缀sim-flight-sw02d-quality-，新目录uorb-quality-diagnostics/quality-diagnostics.jsonl。
原两个模式/默认两用例不自动切换，旧C阶段runner也不得因失败重开D模式。
新合同与薄记录器分别归simulation/ros_ws，tests先保存独立原文/预期；没有公共消息或五层业务数据消费者。

保持125/250检查点、九类topic×2和最后三参数的原21项顺序，不新增flags查询、自由命令、-i/-r或重试。
只向本次PX4 PID/start_ticks/exe/rootfs及已核对socket所有权查询；任何身份变化、PX4死亡、
坏输出、非白名单非有限、armed、超时/超限均停next并清理本次会话，不更换daemon或profile补救。
只有精确两字段隔离可在新模式继续采集，不能用于状态、定位、mapping、模型输入或控制。

原每客户端200ms/每组400ms、stdout+stderr32KiB、事件/头256KiB、事件32/查询文件总8MiB、
深度8/节点8192/列表512、run_id120字节/路径1024字节、5s bootstrap/30s session及250步/1s均保持。
原文、布局、报告和隔离描述同计体积，核对/解析/投影/落盘计入期限；spawn前、写后、next前检查。
新模式只沿用此前声明省略的额外6ms监督sleep，4ms FDM节拍/10ms轮询和默认旧行为保持。
250步之后不再Run/新HIL；不足预算就失败，不扩窗、赶步、隐藏准备或改戳。

报告必须分别保存：

- diagnostic_collection_complete：21项顺序/身份/时间上下文/原文投影/预算、宿主wire及清理全部合格。
- payload_complete：18次topic全部为payload才true，任何缺失/空块/质量隔离均false。
- body_complete：18次topic均有完整正文，可含明确质量隔离，但不含空块或未发布；不代表数值全部可用。
- 四态query/实例计数、每项隔离的字段/原token/实例/原时间与源条件、未知编号/旧戳/primary关联缺口。
- binding_status=unverified、control_gate_accepted=false；旧SW-02B/C runtime仍未通过，不能回填历史。

通用passed/退出码如存在，仅指该显式模式的采集及软件检查，必须伴scope和上述三个独立布尔量。
“有完整正文”不再因NaN被误写成“没有发布”，也不因隔离成功变成“有效姿态/控制绑定”。
若实际仍失败，保留新原文并据新增证据交接；不重跑同原因、不扩大两字段白名单或自动进入SW-03/04。

## 6. 独立预期与实施顺序

本轮已先保存并核对[16组源标志算例](../.runtime/runs/flight-diag-design04-20261030T094904639779/independent-mask-examples.json)，
它们仅验证拟议掩码的算术，不是新分类器/合同或完整验收测试。下一实施须先冻结以下字面量/原文预期，
不能由被测解析器生成oracle，不能改写旧原文或旧失败。

| 组 | 输入/触发 | 独立预期 |
| --- | --- | --- |
| Q01 | 保存的六实例两nan、mask=537002496 | 6质量不可用块/12条隔离描述，非payload、非空块；旧两个codec仍拒绝 |
| Q02 | 两比值均为有限值，包括0 | 原值/类型保持，描述=[]，不因源位为0改成缺失 |
| Q03 | 只有vel或pos为nan且各自条件合格 | 只隔离对应一项，另一有限值保持 |
| Q04 | GPS位1、两nan | 拒绝，不声称正常无源 |
| Q05 | EV速度位1、vel nan | 拒绝；EV位置单独位1并不禁止vel隔离 |
| Q06 | EV位置位1、pos nan | 拒绝；EV速度单独位1并不禁止pos隔离 |
| Q07 | 光流位1、vel nan，即使另有其他辅助源 | 保守拒绝；pos仍独立按GPS/EV位置判据 |
| Q08 | nan拼写/符号/载荷变体、inf、溢出 | 全部拒绝，不以isnan泛化 |
| Q09 | q、执行器、位置精度或其他比值为nan | 拒绝，无额外白名单 |
| Q10 | 全字段不齐/重复/未知/监督字段/坏数组或类型 | 整条拒绝，即使两比值恰好可隔离 |
| Q11 | 同实例flags缺失/坏uint32/二进制标注矛盾 | 拒绝，禁止借其他块/旧查询标志 |
| Q12 | 多实例不同源条件，一项不符 | 整条查询失败，不能部分成功继续 |
| Q13 | 完整、质量隔离、空块混合/单实例无编号 | 分块保留/按固定优先级归并；不补编号或质量 |
| Q14 | 描述多/少/重复/乱序/错字段或伪造null、0 | 原文与严格投影校验拒绝 |
| Q15 | v2与v1/snapshot交叉、额外键/重复JSON键/非有限JSON | 拒绝；原v1日志字节与严格拒绝保持 |
| Q16 | 模式armed=true、非空stderr/异常文本/坏UTF-8、超时洪泛 | 保存原文后停止整个自有会话；不以质量隔离兜底 |
| Q17 | 越白名单/错run-clock/daemon所有权或时间上下文 | 编码/查询前拒绝，不读其他实例daemon |
| Q18 | 限额边界、隔离描述/报告体积和解析落盘超期 | 原边界保持，超界停，不在期限过后spawn或next |
| Q19 | 21项合法事件含质量隔离 | 采集可完整、payload_complete=false；body_complete仅由正文完整性决定，控制门false |
| Q20 | 少/多/重排、源/原文不对应、三个参数缺失或不符 | 拒绝，不凑齐流或改profile |

SW-02D拟修改：新增simulation私有flight_probe_quality.py、ros_ws独立薄质量诊断记录器、
tests独立字面量/坏输入测试与sim_flight_quality_stage.py；现有诊断监督器只加新互斥显式分支。
复用固定query、原生有限字段/类型、有界客户端及身份函数；不改原两个codec或新增通用fallback。
布局与关键源语义在新run冻结并核对，协议位定义/源文件变化应拒绝假定旧条件仍成立。
保留旧C++宿主/profile、公共类型/默认launch/两个旧stage runner及第三方原源，不新增ULog依赖。

先完成离线原文/JSON往返、20组反例与跨schema拒绝，再一次新增隔离规则的实际正常采集。
按影响执行既有69项+新增定向、旧normal/disconnect、实际genpy兼容和全仓轻量回归。
不重复无改动的整个ROS/Gazebo/RViz矩阵，不启动训练/完整模型或正式PERF。

## 7. 本轮验证与交付边界

本轮20项源核验、六实例/12个nan原文与其余字段/标注核对、16组独立掩码算例及
69/69既有飞行测试通过；451份源码/配置、8原生msg/30桥接原源与旧冻结逐文本一致。
只修改本设计、中文实验与管理/必要接口索引，没有新生产合同/分类器/模式、fixture或公共字段。
没有新SITL/客户端查询、ROS/Gazebo、ULog解码或全仓重跑；972项全仓/84项运动仍是上一轮结果。
新v2隔离/20组验收及21次完整采集、三参数/姿态选择后段和正向执行器绑定均未验证。
所有旧失败/原文保持；未来失败只停止自有会话，以新run恢复，不把关机当disarmed或着陆确认。

## 8. 后续实施记录

2026-10-30 [SIM-FLIGHT-SW-02D](SIM_FLIGHT_SW02D_QUALITY_20261030.md)已按本方案完成私有v2、
条件隔离/源语义预检、显式模式及一次实际21查询/三参数，先行独立预期与输入保持。
原文/事件/宿主独立重读及飞行92/运动84/全仓995项回归通过；12处质量缺失明确记录。
采集完整但正文/载荷不完整，六flags已读样本tilt/yaw未对齐、selected姿态缺失、执行器0包。
旧两个v1与B/C失败保留，私有v2不开放公共Scene v2/控制；下一项仅初始化准备条件与SW-03衔接设计。
