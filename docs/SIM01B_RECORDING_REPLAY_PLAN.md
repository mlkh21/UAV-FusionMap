# SIM-01B：300秒记录与两种ROS回放实施方案

方案日期：2026-09-14；更新：2026-09-15；状态：已确认，已完成B范围验收；主责任：integration_engineer。
Technical Lead统筹；simulation_engineer审查源运行，sensor_engineer负责数据验收，
system_architect审查回放边界。依据：[项目状态](../PROJECT_STATUS.md)、
[总验证方案](SIMULATION_VALIDATION_PLAN.md)、[已验收SIM-01A](../simulation/RUN_SIM01A.md)。
方案阶段调用对应子agents完成只读分析和二次评审；用户随后确认实施。
09-15环境前置、73项单元/契约及11项实际ROS fixture通过；LIVE、B1和B2完整通过，关闭与清理分别通过。
实际实现与失败修复见[EXP-20260915-001](../experiments/2026-09-15-sim01b-implementation.md)。

## 1. 目标与已查明问题

一次现场静止记录，再分别验证成品消息原样回放和sensors重新计算。保持现有v0.1
消息、坐标定义、采样时间和未知质量，不引入感知、地图、控制或R-10修复。

| 当前证据 | 对B的影响 |
| --- | --- |
| sim01_smoke.py监督180墙秒，check_sim01_live.py观察150墙秒、目标30源秒 | 无法直接完成300秒，新增B入口与配置 |
| A只从adapted找source，未反查；姿态只验模长；quality未逐项比较 | B须检查首尾和完整身份多重集、真实旋转及全部质量元数据 |
| A固定sleep(0.2)后关闭，未建立就绪及分阶段排空协议 | B必须显式ready、停止水位、审计封存和落盘完成 |
| 两层节点在同一required launch | B须分别启动和停止源与sensors，避免源停时连带杀死适配节点 |
| 环境入口将任务--help误传给Noetic setup helper，实测exit127 | B前置修复参数隔离和显式环境装配 |
| Noetic Bag.write省略t使用time.time() | bag索引时间必须显式声明，不能默认为仿真采样时间 |

代码证据及本轮轻量探针见[EXP-20260914-003](../experiments/2026-09-14-sim01b-agent-review.md)。

## 2. 三个独立会话

| 会话 | 输入/产物 | 启动的业务节点 | 验收内容 |
| --- | --- | --- | --- |
| LIVE | 项目PX4/JSBSim/MAVROS；live.bag及审计sidecar | simulation与sensors各独立launch | 预热后至少300源秒的连续有效状态、记录完整性 |
| B1 | live.bag选择clock、源状态和适配状态 | 无，仅比较器 | 各话题消息、时间、身份和序列化内容原样交付 |
| B2 | live.bag仅选择clock和源状态；历史适配状态离线作为期望 | 全新sensors实例 | 坐标适配和接收时钟门控重现逐样本输出 |

每个会话新目录、新监督PID、独立Master，建议端口LIVE=11341、B1=11342、B2=11343，
顺序执行。B1/B2均不启动PX4、bridge、MAVROS或simulation源节点。
B2不得同时发布bag中的适配结果；否则历史结果会混入重新计算结果。
原始MAVLink及诊断归档，不送入这两种回放的活业务链；原始MAVLink重建另为独立实验。

## 3. 唯一时钟与三个时间概念

LIVE唯一/clock由simulation有效HIGHRES_IMU生成；B1/B2唯一/clock由播放器重播原消息。
禁止额外clock发布者以及rosbag play的--clock、--loop、--immediate；首轮固定rate=1，
不混入暂停或倍速。播放前后核对发布者，等待所有选定话题订阅就绪，再发送首消息。

| 时间/标识 | 定义 |
| --- | --- |
| header.timestamp、HIGHRES_IMU/ODOMETRY time_usec、Clock内容 | 原采样时刻/源时钟；保持整数纳秒及原run/clock，不回写 |
| receipt_monotonic_ns | 记录器在统一接收入口取得的本机单调时刻 |
| bag索引t | receipt_monotonic_ns - record_start_monotonic_ns；独立非负记录经过时间域 |
| record_seq | 单记录器内递增序号，关联topic、身份、bag t、接收时间及落盘结果 |
| replay_session_id | 每次回放的管理会话；消息原run_id/clock_id/sample_id/source_type保持 |

bag索引使用整除/取模构造ROS时间，不经过浮点秒，不用于生成/clock。
rate=1按已记录接收墙钟节奏调度，源仿真实际速度可以与墙钟不同，二者不得混减。
所有回调在同一锁或单写入队列下分配序号/接收时刻，bag与sidecar由同一串行写路径
输出。保留接收顺序，不按采样时间人为重排。跨话题不要求TCP接收全序相同；话题内部
时间、次数及消息序列须核对。writer队列有界、溢出或写失败立即失败，不能静默丢弃。

B2使用bag原run_id参数启动新sensors进程；每次重播重建去重账本、缓存与终止锁，
不沿用上次消费状态，不混入旧地图。sensors的0.5墙秒等待仍有效，不关闭源看门狗，
也不将仅sensors的复算称为再次验证simulation源看门狗。

09-15实现修复：仅原生player子进程使用私有namespace，避免Noetic内部相对clock先以
queue1注册而复用bag绝对/clock；不启用生成，监控私有clock计数须为0。Conda exec
小入口启动同一已安装C++播放器并传播真实退出码。EOF话题先注销时只给2墙秒确认
正常退出，随后仍核对完整数据和5墙秒排空；不放宽丢帧、断流或质量门槛。

## 4. 现场窗口与完整性

记录器在产生遥测前就绪，预热原样保留且不计入有效跨度。以源发布调用台账的首条
valid状态为T0，记录器首valid必须相同；不能跳过未匹配首帧而事后挑一段成功窗口。
T1取首个源状态满足T1-T0≥300000000000ns的时刻，冻结闭区间[T0,T1]及首尾身份。
首尾和区间内每个源样本均必须具有适配样本；预热/尾段单列，不掩盖任何致命故障。
clock保留覆盖窗口的边界样本：不晚于T0的最后clock和不早于T1的首clock。

两层薄节点新增默认关闭的内部audit_path，仅B launch启用：publish返回后记录
clock时间序列及状态身份/采样时间，正常关闭封存审计。它证明发布调用完成或已入队，
不表示网络ACK。审计故障令本轮失败，不逐条fsync，关闭及实际重读落盘另核对。
纯业务库和消息字段不变，A默认关闭审计，保持其既有验收行为。

窗口内同时比较身份集合、各身份次数、话题内序列及完整消息，禁止只比较总数或集合：

```text
source发布台账 = source接收 = source bag重读 = B1 source回放接收
sensor发布台账 = sensor接收 = sensor bag重读 = B1 sensor回放接收
source身份 = 去除前缀后的现场sensor身份 = 去除前缀后的B2重新计算身份
clock发布序列 = clock接收/落盘序列 = B1/B2 clock回放序列
```

现场源→适配检查位置/速度轴变换及真实姿态，q/-q等价；B2与现场适配结果比较所有
业务字段。几何误差≤1e-6（m、m/s或无量纲），四元数使用两种整体符号的最小误差；
schema、run、clock、timestamp、status、reason、frame、source_type及完整quality精确。
confidence=None、uncertainty unavailable/value=None及kind/unit/source均保持。
B1各topic序列化字节精确，B2数值按上述容差，不将模长正确当姿态正确。
原始MAVLink报告接收、写入和实际重读数量；没有对MAVROS原始发布端插桩，不能宣称
所有原始总线报文端到端无丢失。未知ID保留原始字节及framing，不宣称全部语义通过。

## 5. 启动与关闭协议

1. 先验证环境/版本/端口，创建新run及配置快照；启动本次独立Master。
2. 记录器完成文件/writer及所有订阅注册，明确ready；两层launch及审计路径就绪。
3. 核对业务连接和唯一clock发布者，再启动本次bridge/PX4/MAVROS并明确流速。
4. 从首源valid冻结T0；达到T1且有clock覆盖后冻结窗口，监督器进入正常关闭阶段。
5. 先正常停止source launch，封存源/clock审计；sensors、Master和记录器继续运行，
   接收途中source/clock。不得等待源断流看门狗制造terminal作为成功结束信号。
6. 核对封存台账及窗口适配身份完整、clock覆盖、等待队列已处理；再停止sensors，
   封存其审计。源和sensors不得同时停止；否则正常尾部排队会被截断。
7. 停止本次剩余仿真输入进程，记录器处理剩余队列、封存sidecar、关闭bag、重读对账，
   写明确closed/complete结果后才停止记录器和Master。
8. B1/B2在新的空状态会话播放。EOF后按期望计数/身份完整、最终clock覆盖、writer完成
   和bag重读判成功；有限墙钟截止前缺数据仍失败，不补造clock/terminal。

关闭阶段建议5墙秒drain上限；它是检查完成期限，不改变业务0.5秒队列有效性。
源正常关闭或审计封存失败、强制kill及无法解释的尾部丢失均不能豁免为通过。
仅清理本次PID/进程组，保留既有PX4及端口占用者，禁用旧启动器和按名称pkill。

## 6. 参数、门槛与失败停止

参数以B独立配置管理，状态/坐标配置引用已确认sim01_state.yaml；大的ns值若进入
ROS1参数服务器使用十进制字符串，保持整数纳秒含义。

| 项目 | B门槛/来源 |
| --- | --- |
| valid源跨度 | T1-T0≥300秒，总方案已定义 |
| clock请求/实际 | 50Hz / ≥40Hz；按边界覆盖序列(N-1)/(t_last-t_first)计算 |
| ODOMETRY请求/有效状态 | 20Hz / source及sensor各≥10Hz，按各自采样跨度计算 |
| 最大有效间隔 | clock/source/sensor各≤0.5源秒；回退/重复发布/身份冲突/未解释缺失0次 |
| 源安全截止 | 整run绝对源时间600秒，含预热/尾部；同时观察clock及解码有效原始IMU |
| 会话墙钟截止 | LIVE/B1/B2各最多900秒；启动等待60秒，回放无进展监督2秒 |
| 业务参数 | 稳定观察10源秒；源双流各2墙秒；队列100条/0.5墙秒；quat容差0.001 |
| 排空 | 5墙秒期限内期望身份/计数及写入完成；不得用固定sleep代替条件 |
| writer队列 | 上限10000条，沿用A原始订阅量级作为首轮配置；队列满立即失败，不能静默丢弃 |
| 不可用质量 | confidence和完整协方差仍未知；不得改为高置信或零方差 |

这些是工程冒烟门槛，PERF-01高速/硬件预算另定。A实测首valid16.059999源秒，
clock约0.9076源秒/墙秒；据此估算B窗口结束约316源秒、采样推进约348墙秒，
每次回放接近原接收时长，总计三次会话；只是安排估算，不是运行性能承诺。

端口冲突/既有PX4、Python不符、启动超时、ACTIVE reset或源回退、双流断流、terminal/
ERROR、pending timeout/overflow、audit/writer故障、必需进程意外退出、任何解锁心跳、
安全截止、集合/次数/数值/质量/关闭不一致，均失败停止并保留证据，不自动放宽阈值。
已批准的PREPARING估计器reset重启观察按原规则执行，不能扩成ACTIVE恢复。

## 7. 具体文件与唯一修改责任

| 所有权/责任 | 计划新增或最小修改 |
| --- | --- |
| integration_engineer | 新ros_ws/sim01b_record.py、sim01b_replay.py及传输审计小工具 |
| integration_engineer | 新ros_ws/launch/sim01b_source.launch、sim01b_sensors.launch；各仅一层节点，sensors launch同时用于B2 |
| integration_engineer | 两个现有薄节点仅增加默认关闭的audit_path和正常关闭封存，不变业务算法 |
| system_architect | configs/sim01_environment.bash及ros_ws/sim01_env.sh的参数/环境修复；新configs/sim01b_recording.yaml |
| sensor_engineer | 新tests/check_sim01b_recording.py、check_sim01b_replay.py及test_sim01b_recording.py：窗口、完备性、真实旋转、质量和尾部 |
| simulation_engineer | 核对LIVE源时间/流速/安全边界，维护simulation/RUN_SIM01B.md，审查无需改纯业务库 |
| Technical Lead / experiment_manager | PROJECT_STATUS、阶段计划、决策、实验索引及新的实际运行记录 |

Technical Lead为本步主集成责任，具体agents按文件所有权执行，不能回退他人改动。
原PX4/bridge/研究仓库、四消息和simulation/sensors纯业务库不在本次修改清单。

环境前置修复方案：保存任务参数后以空positional args加载环境，再exec原参数；
项目已有显式ROS搜索路径，补声明已核对的Noetic ROS_VERSION/PYTHON_VERSION/DISTRO/
ROOT/ETC及pkg-config基线，替代会执行系统Python helper的隐式setup装配。它属于
固定Noetic源码运行环境，不宣称覆盖任意ROS安装hook。先验证CLI --help、包发现、
rosbag导入/原生播放器库、已有44项契约和11项ROS fixture，再开始300秒实际记录。
若前置检查失败，保留证据并停止，不能静默换回系统Python。
参数传递检查覆盖--help、带空格、空字符串和字面特殊字符；增量catkin确认消息生成
解释器。对账fixture覆盖缺首/尾source或sensor、相同数量却错ID、重复/额外输出、
完整quality来源变化、单位模长但错误旋转、最终clock未覆盖、落盘不全及EOF未完成。

## 8. 实施顺序、确认与风险

确认后：最小环境修复及RED/GREEN → bag/sidecar与对账fixture → 发布台账与分层launch →
一次300秒LIVE及完整关闭 → B1成品回放 → B2重新计算 → 各自结果/清理/状态更新。
只有三项结果分别通过才标SIM-01B完成；失败仅标相应阻断，不改A历史验收结果。

方案阶段已检查Conda rosbag/roslz4/Crypto模块、3消息离线bag字节与索引往返及原生播放器
动态库，当时没有启动新Master或300秒仿真；该历史证据保留。原始研究、环境、历史运行和checkpoint保留。
R-10时间边界及节奏、ENV-03异机恢复/第二副本、未知协方差和实机原点仍开放；审计IO
影响需要在实际频率中反映。B不验收暂停/倍速/主动断流整run停止、40分钟或高速飞行。

本提案涉及新B运行入口、审计及环境代码；根[AGENTS](../AGENTS.md)11.3要求
“扩大范围、改变公共接口或架构时，先补充具体方案再确认”。方案先行交付后已获用户确认，
连续完成该范围不重复请求同一确认。
