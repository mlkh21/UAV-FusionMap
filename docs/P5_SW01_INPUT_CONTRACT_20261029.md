# P5-SW-01：组合场景输入与独立预期

日期：2026-10-29；版本：v1；主责任：tester。
状态：已完成（测试输入/合同/离线线格式范围）。
后续更新：SW-02已完成[33个A/B实际ROS组合/公开回放](P5_SW02_ROS_COMBINATION_20261029.md)，
原SW-01结论保持离线范围；S09/C继续由SW-03验收。
再后续[SW-03](P5_SW03_NATIVE_DELIVERY_20261029.md)已实际补齐S09/C并交接37例软件矩阵，冻结输入/预期未变。
依据：[P5-DESIGN-01](PHASE5_SOFTWARE_COMBINATION_DESIGN_20261029.md)、ADR-041；
实际结果见[EXP-20261029-003](../experiments/2026-10-29-phase5-input-contract.md)。

## 1. 已有代码与本轮范围

沿用现有仿真/传感器fixture构造器、公开消息codec、M4输入checker及公共地形dataset合同。
本轮只增加tests私有的场景声明、独立预期、严格读取/限额、输入物化、离线验证命令及测试。
未新增公共消息、服务、运行节点、组合launch、客户端或显示器；未改变旧业务字段与默认入口。

| 新文件 | 责任 |
| --- | --- |
| [p5_combination_inputs.json](../tests/fixtures/p5_combination_inputs.json) | 三类配置、公共时间/空间参数、seed序列及九组37子例调度 |
| [p5_combination_expectations.json](../tests/fixtures/p5_combination_expectations.json) | 独立保存95检查点/228项可观测预期、6个生命周期声明、23份载荷的独立字段投影 |
| [p5_contract.py](../tests/p5_contract.py) | 仅标准库的严格schema/有界JSON读取、序列展开、覆盖/事件/录制预算检查；不导入ROS或业务实现 |
| [p5_oracle.py](../tests/p5_oracle.py) | 不导入生产/构造器的Fraction算式核对；独立检查运动、同步、TTL、M3区间与高程包络种子 |
| [p5_payloads.py](../tests/p5_payloads.py) | 构造143组采样/12份显式逆观测输入、23份公开载荷样例；没有perception forward/地图累计/Provider执行 |
| [p5_fixture_run.py](../tests/p5_fixture_run.py) | 先保存输入与预期、逐子例完整载荷，再从磁盘读取做实际生成消息序列化/解码和独立投影比较；可运行全仓轻量回归 |
| [test_p5_contract.py](../tests/test_p5_contract.py) | 21项schema/算术/反例测试 |
| [test_p5_wire.py](../tests/test_p5_wire.py) | 10项真实线格式、几何、质量/flags和旧消息兼容测试 |

这不是新组合运行器。A中物化的Bundle只用于合同对照，后续SW-02须沿源状态与传感器构造/适配链
实际生成它，不能直接发布保存的Bundle来冒充完整传感器链。B仍是具名逆观测测试输入；
C仅声明原生窗口/独立图层检查，不增加飞机运动或Gazebo/DEM注册。

## 2. 输入schema与调度语义

私有schema为`test.p5.inputs.v1`，根对象只允许schema_version、fixture_only、event_columns、
profiles、sequences、cases六字段；fixture_only必须为bool true。A/B/C与terrain、limits显式分开。
每个子例具有独立case ID，执行时绑定新的run/clock；原始dataset采集时间仍属于其自身时钟域。
v1固定九组37子例，删减/重复/未知子例均拒绝，不静默跳过尚未具备运行器的场景。

事件按`[id, operation, time_ns, wall_ns, arguments]`存储；time_ns是整数业务时间，
wall_ns是该子例单调墙钟相对调度点，不是源采样时间，也不与业务时间相减。
普通源动作只向前推进业务时间；仅S04.reset允许明确回退。重复clock推进接收墙钟但不推进业务时间。
查询时间独立于源时钟，特意保留旧M1允许未来查询、旧时间查询不自动墙钟失效的现实行为。

`seed`是显式四帧序列：0/50/100/150ms。展开后253个声明事件；clock_repeat/clock_steps
各自含具名count和period_ns，预算按实际包数计，不把展开次数藏在一个事件额度内。
相同子例不能重复事件ID；序列仅一次展开，不允许循环引用、未知序列或跨run继承。

| 操作 | 解释与边界 |
| --- | --- |
| sample | 生成同一观测的源状态、适配状态、Radar/可选IR与Bundle对照；默认speed=0、pose_age=0、IR delta=0、IR存在；固定odom场景点(1.25,4.25,0.25) |
| clock / clock_repeat / clock_steps | 单包、相同业务时刻重复、按周期推进；不生成占据证据 |
| map_query / terrain_query | 只读请求；地图显式point/frame/max_age，地形按2×2中心索引及可选前一组pin |
| observation | B专用公开逆观测输入；先发该时刻基础设施clock，再发占据消息；具名sequence/point/body/kind/quality，禁止改用placeholder域 |
| backend | 仅测试后端注入；normal/bad_output/exception/untrusted_context/slow，slow显式给duration与deadline；不注册research模型 |
| service / clock_control / poll | 测试服务停止/阻塞/延迟/实例重启、clock停包/来源不符及墙钟轮询；不是新公共控制接口 |
| recording | 新目录start、close、replay与专门的篡改预期负例；不可复用目录或覆盖历史 |
| graph / cleanup / new_run / view | 后续装配检查动作；new_run须先创建/结束具名previous_run并保留旧实例身份，再建立全新域；view只允许native_separate |

服务重启子例S07.instance显式重发150ms clock，等待新Provider安装后才继续旧组pin查询；
不能假设新节点会收到未latched的旧clock。状态存活/组pin验证仍须在SW-02实际运行，不能靠本文件推定通过。

## 3. 独立预期与可观测分界

`test.p5.expectations.v1`与运行输入分开保存。每条检查点的after必须引用本子例真实事件，
values中的字段有严格类型和枚举，禁止用自由文本脚本表达条件。缺失值写null，不能填0或free。
实例用`$first`绑定首次实际实例，`$different`必须与已保存的前一实例不同；后续比较器不得把它解释为任意字符串。

`declared`仅供B记录owner/封存数量的独立生命周期表。旧公共消息没有这两个字段，
不能把该声明当实际观测或要求application读取地图私有状态。后续通过公开cell唯一性、
封存点/淘汰点/返回点查询、原证据时间与区间核对其可观察后果，声明本身不算运行通过。
其余values也区分业务公开结果和测试控制/诊断收据；后者须由具名测试观察器提供，不冒充公共协议字段。

沿worker真实源码增加两个独立子例：S03.deadline没有较新busy输入，超时应输出unavailable；
S03.slow已有更新的busy响应，旧任务超时输出被水位丢弃，因此timeout检查occupancy.delta=0。
这是已有行为的分开验收，不是本轮修改worker。paired超同步门限的现有reason为radar_ir_timeout。

运动与M3的预期由独立分数算式核对，不调用待测地图决定答案；所有权/质量缺失/TTL重建
采用明确保存的表，而非从未来候选输出补写。高程界逐值保持float64，整数探针为2^53+1。
地图概率/confidence按float32映像比较；原始payload整体按该声明精度核对。
旋转矩阵的理想系数投影单独允许1e-12浮点容差，几何点检查1e-9；
时间/身份/flags/质量界不应用此容差，不以容差修补cell索引或状态。

23份公共载荷含AircraftState、RadarFrame、InfraredFrame、SensorBundle、占据、快照、
两种查询请求、五类地图结果及valid/no-data/stale/unavailable/零高/负高地形结果和状态。
这些是协议样例，不是Provider/地图实际运行收据；真实genpy序列化与独立字段投影检查不能替代后续业务验收。

## 4. 限额与失败

单份JSON读取最多1MiB+1哨兵字节，解析前拒绝超长文件；拒绝重复key、NaN/Inf、坏编码，
递归深度≤20、结构节点≤100000、文本≤1024 UTF-8字节、列表≤4096、对象≤256项。
整数时间拒绝bool/float/负数/超限；XYZ维度/finite、分类阈值、场景域、注册窗口及训练监督字段严格检查。
未知字段/操作/版本/预期信号、错case/事件引用、未声明reset、假完整录制均拒绝，不静默规范化。

测试调度维持45s外层、15s启动、5s排空、5s清理；每子例≤128声明事件、重复count≤128、
每话题≤256收据、总16MiB。B的业务和查询均保持[0,1s)注册窗口，地形业务授权[100ms,1.5s)，
注册[0,3s)；这些是组合输入的显式授权，不修改原M5配置的纳秒级样例。

S08.record预算为10 clock + 4 query + 1来源 + 1安装 + 16状态变化预留 + 1停用 = 33事件，
低于公共地形64事件限额。S08.overflow明确69个clock、含预留总88，预期incomplete；
来源不符也按v1不可表达失败预期incomplete，不把不完整记录截尾改complete。
预算只是测试输入上界；本轮没有测量运行时收据峰值、RSS或正式机载性能。

## 5. 运行、实际结果与恢复

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -c 'import sys; print(sys.executable); assert sys.executable == "/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python"'
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/p5_fixture_run.py --full
```

每次新建`.runtime/runs/p5-sw01-<时间戳>/`。先写inputs/expectations、payloads下37个子例的完整
输入及wire-inputs，再从磁盘读取执行codec；输出23份实际bin、逐例decoded、报告和测试日志。
命令不从待测结果生成预期，也不启动ROS Master/服务、感知后端或地图累计；最终运行中742次实际序列化通过。
生成类型确实来自`.runtime/ros/devel/lib/python3/dist-packages/`，未重建外层catkin_ws。
31项新增定向、805项全仓轻量测试通过，旧字段/运行入口保持。

下一项P5-SW-02才实现显式测试源/故障装配、公开观察器与实际ROS/独立回放；
P5-SW-03负责原生窗口/图隔离/清理交接。真实设备、研究模型质量、DEM/占据融合、
Gazebo地理注册、资源及完整Phase 4/5未验证。恢复只停离线命令/撤回本批tests增量，
保留所有历史目录和既有未提交改动；不自动提交或推送。
