# 空实例输出的三态诊断与补证设计

日期：2026-10-30；版本：v0.1；任务：SIM-FLIGHT-DIAG-DESIGN-03。
主责任：simulation_engineer；状态：已完成（具体设计与只读核验，尚未实施新模式）。
依据：[SW-02B软件/实际失败](SIM_FLIGHT_SW02B_PROBE_20261030.md)、ADR-044、
[EXP-20261030-005](../experiments/2026-10-30-sim-flight-empty-instance-design.md)。

## 1. 问题与决定

SW-02B的第二次运行在step125读取到三组积分IMU，第二条estimator_status返回六个实例标题，
没有任何字段；原严格合同拒绝并停止，21次查询未完成。保留该结论和所有历史产物。
本方案不把空标题改判成有效快照，而是提出独立的诊断事件，允许在明确不可用的情况下继续收集
其余白名单信息；继续仅限无控制、最多250步/1秒的诊断，不代表状态有效、disarmed或free。

直接实施工作包为SIM-FLIGHT-SW-02C（计划），增加显式`--uorb-diagnostics`正常用例、
独立`sim_flight_uorb_diagnostic.v1`事件与采集完整性验收。现有`--uorb-probe`、
snapshot/query v1、旧normal/disconnect、C++宿主/profile及公共消息保持原行为。
新模式不得被旧probe自动调用或作为失败fallback；本轮未新增这些代码/参数。

## 2. 当前证据与源码边界

本轮[冻结九份源文本](../.runtime/runs/flight-diag-design03-20261030T012035582753125Z/source-evidence.json)，
[16项源核验](../.runtime/runs/flight-diag-design03-20261030T012035582753125Z/source-checks.json)记录具体行号。
[旧输出重新核对](../.runtime/runs/flight-diag-design03-20261030T012035582753125Z/archived-output-audit.json)
确认只有一份有效快照，原空实例输出和部分流仍被旧校验器拒绝。

| 源码/真实入口 | 已核对事实 | 不能据此推断 |
| --- | --- | --- |
| [Manager::orb_exists](../.runtime/src/px4-v1.13.3/platforms/common/uORB/uORBManager.cpp#L231) | 检查node存在及is_advertised，未要求载荷已可读 | 有实例不等于已输出有效状态 |
| [listener快照](../.runtime/src/px4-v1.13.3/src/systemcmds/topic_listener/listener_main.cpp#L59) | 先计数，打印TOPIC/Instance，再调用复制；忽略复制返回值 | 退出码0不证明每实例载荷完整 |
| [listener_print_topic](../.runtime/src/px4-v1.13.3/src/systemcmds/topic_listener/topic_listener.hpp#L54) | 512字节上限；orb_copy成功才打印正文 | 无正文不直接给出内部errno或唯一原因 |
| [Manager::orb_copy](../.runtime/src/px4-v1.13.3/platforms/common/uORB/uORBManager.cpp#L412) | read失败或长度不等于元数据尺寸均报错 | 标题不能替代copy结果/缓冲内容 |
| [DeviceNode::copy](../.runtime/src/px4-v1.13.3/platforms/common/uORB/uORBDeviceNode.hpp#L228) | 没有数据缓冲时可返回false，read随后可返回0字节 | 本次是否走此路径没有直接内部观测 |
| [EKF2构造/multi_init](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF2.cpp#L168) | 状态与姿态等话题可预先advertise；PublishStatus/Flags受update成功分支约束 | 六实例空标题不能填tilt_align=false或断言从未update |
| [当前私有解析器](../simulation/ufm_simulation/flight_probe_contract.py#L136) | 已有完整字段/尺寸/类型及缺失校验，空实例和部分流均拒绝 | 本轮不能通过更改旧判据让旧run通过 |
| [当前监督器](../ros_ws/sim_flight_diagnostic_run.py#L116) | 125/250步在收到实际宿主收据后查询，再决定next | 顺序查询不是原子同tick事务 |

单实例分支只有`TOPIC: name`，没有`Instance n`，并调用orb_subscribe而不是逐个已advertise实例复制。
新事件的单实例编号取null，表示原生文本没有显式编号；不得从“仅一个advertise”推出其编号/primary。
多实例编号只取原文标签。此保守标注不修改旧snapshot解析器的编号约定，也不修补PX4原源。
来源时间、设备ID和primary若无法在本组证据中对应，只报告关联未知。

## 3. 独立三态及精确语法

仅在白名单query、当前PX4/daemon身份前后相同、客户端正常结束、returncode=0、stderr严格为空、
原文UTF-8/字节与时限均合格之后分类。stdout须LF换行，仅忽略真正的空行；
拒绝CR、TAB、ANSI/NUL及其他控制字符，不以strip删除任意异常文本。原始字节另行保留。

| observation.state | 精确输入与内容 | 继续条件 |
| --- | --- | --- |
| payload | 指定topic标题及全部已知字段；每个实例正文完整、唯一且类型/尺寸合法；或参数show精确完整 | 仅诊断继续；已读到armed=true仍立即停止 |
| not_published | topic输出除空行外只有一行`never published`；instances=[]、parameter=null | 记录原生“未发布”文本；不推断字段值或从来没有发布过 |
| payload_unavailable | topic标题合法，至少一个实例只有标题，没有正文；允许另有完整实例 | 仅新诊断模式继续；空实例fields=null，不能输出旧有效快照 |

topic标题仅两种：`TOPIC: <准确白名单名>`或`TOPIC: <名> N instances`，N为2..9。
单实例只能有零个或一个` <名>`正文标记，不允许Instance标签；无标记才可归为无载荷。
多实例必须恰有N个升序、互异的`Instance i:`，i=0..8，可非连续；不凭数组位置补编号。
每块只能是“完全没有正文标记/字段”，或“一个正文标记+冻结msg的全字段集”。
已有正文标记却无字段、只印部分字段、重复正文/键、坏类型/非有限/未知/训练监督字段，均立即失败。
缺少Instance标签/数量不符、错topic、正文前字段、错误/警告文本、标题和never published矛盾，也失败。
混合情况只允许上述完整块与完全空块并存，顶层必须payload_unavailable；完整块原值保留，不能代表空块。
多实例中任何完整vehicle_control_mode块flag_armed=true，即使另有空块，也先保存证据后停止。

参数没有“空载荷可继续”例外：必须是既有严格show形状与整数值，三项均要求1033/0/0；
缺失、无正文、值不符、未知参数/多参数或额外行立即停止，禁止更换profile或写参数修复。
输出形状可能由原生copy失败、进程内部异常或其他原因造成；新reason只描述“本次输出无载荷”，
不命名为“从未初始化”“copy errno=...”或“EKF故障”。在恰好标题边界结束的输出无法仅靠文本
区分合法空块与内部截断，因此仅容许诊断不可用，不给状态准入，也不声称已确定内部原因。

## 4. 拟议私有事件与校验

新事件精确顶层键集：schema_version、query、argv、owner_before、owner_after、last_hil_us、
fdm_time_s、wall_start_ns、wall_end_ns、returncode、stdout、stderr、observation、binding_status、
control_gate_accepted。schema_version固定`sim_flight_uorb_diagnostic.v1`。
query复用既有固定`sim_flight_uorb_query.v1`计划；不新开命令或运行时自由选项。
owner保留现有PID/start_ticks/exe/rootfs及socket文件/内核身份；所有查询绑定同一所有者。
原始HIL微秒、源FDM秒、查询单调墙钟与原生topic时间分开，不填补或重写时间。

observation精确键为state、reason、instances、parameter：

- payload：reason为空；topic时parameter=null，instances非空且每块均payload；参数时instances=[]，parameter={integer: 原值}。
- not_published：reason=native_not_published，instances=[]、parameter=null；只适用于topic。
- payload_unavailable：reason=native_payload_unavailable，parameter=null，instances非空且至少一块无载荷。

每个instances项精确键instance、state、fields；instance为显式0..8整数，单实例无标签时为null。
state只允许payload或payload_unavailable；前者fields为全字段字典，后者fields=null。
不能以空字典代替null，不能用bool冒充整数，不能由新事件反填旧snapshot/actuator记录。
编码前校验精确键集和有界结构；解码拒绝重复JSON键、坏UTF-8/版本/非有限、超长整数/深度/尺寸；
按原文重新解析并以严格类型逐值比对投影。旧codec必须拒绝新schema，新codec也必须拒绝旧snapshot schema。
新私有合同不生成公共消息、不进入ROS图、SensorBundle、定位、mapping或模型forward。

## 5. 新显式运行、期限与报告

拟议参数`--uorb-diagnostics`与`--uorb-probe`互斥，且拒绝disconnect/build-only组合。
新run前缀`sim-flight-sw02c-diagnostics-`，目录`uorb-diagnostics/`，JSONL为diagnostics.jsonl；
原uorb-probe目录和snapshots.jsonl不复用。旧默认入口不新增行为。
复用现有POSIX有界执行/所有权核对，但用独立分类器和记录器；不得在捕获任意ValueError后泛化成第三态。
原strict parser/validator/stream及对应测试保留；新模块显式解析上述封闭语法。

固定顺序仍为125步九topic、250步九topic、最后三param，共21次；无重试、额外query或-i/-r。
源在查询组内不发next，125组结束合格才继续原下一步，250后不再Run/发新HIL。
每次仍检查当前进程与socket身份；身份变化、PX4死亡、超时/超限、armed或畸形输出立即停next并清理会话。
native_payload_unavailable和not_published只在新模式下作为诊断事件继续；数据不用于控制或状态发布。

保持每客户端≤200ms、每组≤400ms、stdout+stderr≤32KiB、每事件/头≤256KiB、
事件≤32、查询文件总量≤8MiB、深度≤8、节点≤8192、列表≤512；run_id≤120 UTF-8字节、
路径≤1024字节、枚举reason只用上述固定值。原5s bootstrap墙钟、30s session、250步/1s均不延长。
省略的仅为probe原已声明的额外6ms sleep，4ms源步长与10ms读取轮询保持，不承诺倍率。
期限覆盖身份核对、执行、解析和持久化；每次spawn之前、写入之后、进入下一query/next之前重新核对。
只要剩余时间/体积不足即失败，不以“客户端用时合格”掩盖组解析/落盘超期，不在期限已过后再spawn。
原文写入和报告/布局文件同计文件预算；保留失败原文，清理由原监督器完成，不终止其他会话或回写历史。

新报告必须分别输出：

- diagnostic_collection_complete：21事件均有序、同身份/时刻上下文/预算合格，宿主与wire核对及清理合格。
- payload_complete：18次topic查询均为payload才true；任何明确未发布或空块均false，不由采集完整反推。
- 各态query数量/实例数量、混合块/未知编号、原生时间与两检查点逐实例对照、primary关联缺口。
- binding_status=unverified、control_gate_accepted=false，独立记录旧SW-02B仍未通过。

若保留通用passed/退出码，只能表示本显式诊断采集及软件检查，必须与上述字段和scope同时输出。
即使payload_complete=true，时间0/回退、编号未知、primary无对应样本、打印精度/跨时钟缺口
仍不能据此判fresh或绑定当前HIL。缺失节点只定位证据范围，不凭依赖图确定唯一故障。
新模式采集完成不关闭旧SW-02B原验收，也不自动解锁SW-03长窗、v2或SW-04命令。

## 6. 独立验收预期与实施顺序

以下为先行冻结的设计预期，尚未由新分类器执行；未来须先保存独立字面量/原文再实现，
不能由被测分类器生成其自身oracle。实际旧原文应复制到新测试证据中，禁止改写旧目录。

| 组 | 输入/触发 | 独立预期 |
| --- | --- | --- |
| C01 | 已保存六个空Instance标题 | 新事件payload_unavailable，6块fields=null；旧strict仍拒绝 |
| C02 | 完整单实例，包括0及负浮点 | payload、原值/类型保留，instance=null，不推断primary |
| C03 | 只有合法单实例TOPIC标题 | payload_unavailable，单块编号null/fields=null；不填instance0 |
| C04 | 单独never published | not_published，空instances，不赋字段0或armed=false |
| C05 | 完整多实例0/2 | payload，两个显式编号保留；不重排/补1 |
| C06 | 完整0+空2，或空0+完整2 | 顶层payload_unavailable，分别保留全字段/null；新诊断可继续 |
| C07 | 标题计数与块不符、重复/逆序/越界编号 | 失败停止，不分类为空载荷 |
| C08 | 正文已出现而字段为0个或不全 | 失败停止，即使混有另一完整块 |
| C09 | 重复/未知/监督字段、坏数组/非有限/坏枚举 | 失败停止，不由异常处理兜底第三态 |
| C10 | 错topic、never published+正文、异常行/ANSI/CR/TAB | 失败停止，原文保留 |
| C11 | 返回码非0、非空stderr、坏UTF-8、超时/洪泛 | 失败并清理整个自有会话，不能只杀客户端继续 |
| C12 | 混合块中任一完整模式块armed=true | 保存原文后停止，不因顶层不可用忽略已读armed |
| C13 | 三参数完整1033/0/0及不符/空/多项 | 前者保留整数0，后者停止；没有第三态参数 |
| C14 | 新/旧schema交叉、额外键/重复JSON键/布尔整数 | 编解码均拒绝；旧输出字节与测试保持 |
| C15 | query越白名单、错run/clock/daemon或PID复用 | 编码/执行前拒绝；不得向其他instance查询 |
| C16 | 临界字节/事件/深度/组墙钟/预启动期限 | 界内接受，超界停；解析/写入也计入预算 |
| C17 | 21条合法诊断，其中含空块或not_published | 采集完整可true，payload_complete=false，控制门false |
| C18 | 少/多/重排事件、跨checkpoint源时间/lastHIL不对应宿主 | 不完整/拒绝；禁止凑齐或填造缺失事件 |

SW-02C实施范围：simulation新增独立flight_probe_diagnostic.py；ros_ws新增薄诊断记录器并显式接入
现有监督器；tests新增独立预期/codec和反例/阶段runner。复用既有query、类型与身份/执行限额函数，
不改旧strict的含义。当前文件名是具体实施建议，尚不存在这些新实现。
先完成C01—18的离线合同/原文及跨schema拒绝，再跑一次新增观察规则的实际normal诊断；
实际失败须保留原文并据新证据推进，不能重试同一原因或放宽预算。
执行相关49项基线及新增定向、旧normal/disconnect/实际线格式兼容、全仓轻量回归；
不重跑未受影响的整套Gazebo/RViz矩阵，不做训练/完整模型/正式PERF。

## 7. 本轮验证与交付边界

本轮只读审计旧证据与源码，16项核验、49/49既有飞行测试通过，445份源码/配置与旧冻结一致；
8份原生msg/30份桥接原源保持。没有修改/新增运行代码、合同实现、测试fixture或公共字段。
只修改本方案、中文实验和管理/必要接口索引，无新SITL/查询/ROS/Gazebo/ULog解析或全仓重跑。
952项全仓、84项运动及11自有PID清理是上一轮已验证结果，本轮不冒充再次执行。
新schema/三态分类、混合输出策略、21次新运行及正向执行器绑定仍未验证；仅设计交付已完成。
后续出错只停止自有会话，以新run恢复；旧失败和默认入口不需回滚，不删除历史产物。

## 8. 2026-10-30实施后续

[SW-02C交付](SIM_FLIGHT_SW02C_DIAGNOSTICS_20261030.md)已实现本设计私有事件、三态分类及显式运行。
18组独立预期先冻结，新增20项、飞行69/运动84/全仓972项与旧链兼容通过；原strict保持。
实际125步九topic完成，250步第11次estimator_status有nan，按本方案C09规则停止，11查询/10合法事件。
本设计已实施的软件范围不等于21次采集通过；下一项先审查原生非有限诊断字段语义及隔离补证设计，
不改写原失败、不重跑相同原因或放宽原数值/墙钟/源时间门槛。
