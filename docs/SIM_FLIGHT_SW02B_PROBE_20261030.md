# 有界uORB观察的软件交付与实际未通过记录

日期：2026-10-30；任务：SIM-FLIGHT-SW-02B；主责任：simulation_engineer。
状态：进行中（软件与回归已交付；21次实际查询验收未通过）。
依据：[已确认具体方案](SIM_FLIGHT_DIAG_DESIGN_20261030.md)、ADR-044。
实验：[EXP-20261030-004](../experiments/2026-10-30-sim-flight-uorb-probe.md)。

## 1. 本轮结果

已实现私有查询/快照合同、严格原生文本解析、有界POSIX客户端和显式`--uorb-probe`入口。
实际第二次probe在step125读到三组积分IMU，但第二条`estimator_status`只返回六个实例标题，
没有字段。按原设计拒绝并停止next，不能视为never published、全零或EKF故障标志为0。
因此没有完成21条收据，SW-02B实际验收不通过；没有将回归成功作为运行成功。

飞行49/49、运动84/84、全仓轻量952/952通过；旧normal/disconnect、真实genpy兼容通过。
[兼容报告](../.runtime/runs/sim-flight-sw02-stage-20261030T014816354843/report.json)仅覆盖旧诊断/回归，
新probe结论单独见[probe-audit.json](../.runtime/runs/sim-flight-sw02-stage-20261030T014816354843/probe-audit.json)。

## 2. 修改文件与消费链

| 文件 | 原因及职责 |
| --- | --- |
| [flight_probe_contract.py](../simulation/ufm_simulation/flight_probe_contract.py) | 标准库私有计划/合同、有界JSON及原生输出解析；不导入ROS或模型 |
| [sim_flight_uorb_probe.py](../ros_ws/sim_flight_uorb_probe.py) | 核对本次PX4/daemon身份，调用现有listener/param并保留原文 |
| [sim_flight_diagnostic_run.py](../ros_ws/sim_flight_diagnostic_run.py) | 仅显式probe分支接入125/250检查点，默认两用例保持 |
| [sim_flight_probe_expectations.json](../tests/fixtures/sim_flight_probe_expectations.json) | 独立固定命令、次数、缺失/姿态/参数文本与预期；先保存再实现 |
| [sim_flight_probe_fixture.py](../tests/sim_flight_probe_fixture.py) | tests私有离线收据，不进入运行输入 |
| [test_sim_flight_probe.py](../tests/test_sim_flight_probe.py) | 新增17项合同/坏输入/原生输出/真实子进程限额检查 |
| [sim_flight_probe_run.py](../tests/sim_flight_probe_run.py) | 新probe与旧回归的可复现装配；失败不跳过兼容检查，整体仍失败；本轮未整体执行此新装配器 |

配套修改本说明、实验记录、PROJECT_STATUS、README、架构/数据/传感器/坐标规范、开发计划、
ADR-044、实验索引与原设计的后续更新。没有修改旧C++宿主/桥接、profile、公共消息或第三方原源。
真实链为监督器逐step读取原宿主收据→暂停next→核对PX4 PID/start_ticks/exe/rootfs/socket→
现有`px4-listener`/`px4-param`→原文保存→严格私有快照；数据只供测试诊断。
不进入AircraftState、SensorBundle、定位、mapping或任何控制许可。

## 3. 私有合同与预算

`sim_flight_uorb_query.v1`固定九类topic×125/250检查点及最后三个参数show，共21条计划。
topic：vehicle_imu、estimator_status、estimator_status_flags、estimator_attitude、
estimator_selector_status、vehicle_attitude、vehicle_control_mode、actuator_controls_0、actuator_outputs。
参数期望为SYS_AUTOSTART=1033、SYS_CTRL_ALLOC=0、SENS_IMU_MODE=0。
命令只按argv构造；无自由shell、写参数、`-i`/`-r`、等待新消息或多次采样分支。

`sim_flight_uorb_snapshot.v1`精确键集：schema_version、query、argv、owner_before/after、
last_hil_us、fdm_time_s、wall_start/end_ns、returncode、stdout/stderr、observed、reason、value、
binding_status、control_gate_accepted。owner保存PID/start_ticks/exe/rootfs及socket文件/内核inode。
内核inode必须在本次PX4 fd中，查询前后身份相同；任何身份错误不查询其他会话。

整数微秒/墙钟不换成浮点秒，checkpoint的FDM时间另以1ns界核对；topic时间原样保留。
只按冻结的8份`.msg`完整字段布局解析九类topic，保留所有实例；重复/未知/缺字段拒绝。
布尔、整数位宽、数组尺寸、有限float32打印值分别校验，投影比较保留类型差异。
`never published`才是observed=false/reason=not_published/value=null；有标题无字段仍为错误。
额外字段/训练监督、坏版本/身份/命令/非有限/超限/重复JSON键均拒绝。
快照是顺序现值观察，打印浮点有精度损失，不恢复float32位模式，也不具原子同tick含义。
binding_status固定unverified，control_gate_accepted固定false；读到armed=true立即停止。

每客户端≤200ms、每组≤400ms、stdout+stderr≤32KiB、每收据≤256KiB、文件总量≤8MiB，
深度≤8、节点≤8192、列表≤512、观测≤32；仍计入原5s bootstrap与30s session。
超时/超限/坏UTF-8保留原始可表达输出，停止并清理本次会话；不只杀客户端后继续next。
显式probe仅省略额外6ms监督sleep，原4ms FDM节拍、10ms读轮询及250步/1s硬界保持。
默认normal仍保留原sleep；不放宽期限、不隐藏暂停、不改戳。

## 4. 两次实际probe与归因边界

| 运行 | 实际结果 | 处置 |
| --- | --- | --- |
| [014231618309](../.runtime/runs/sim-flight-sw02b-probe-20261030T014231618309/manifest.json) | 第一条vehicle_imu原文的设备标注包含嵌套括号，解析器报probe_native_annotation | 依据Device.hpp打印语法修正并补测试，独立既有预期未改；保留失败 |
| [014636029383](../.runtime/runs/sim-flight-sw02b-probe-20261030T014636029383/manifest.json) | 第一条成功，第二条estimator_status六实例均无字段，probe_native_incomplete | 按既定规则停止，未继续其余19次；不重试同一短窗或放宽标准 |

第二次共125条宿主收据，FDM停于约.5s、最后HIL=496000us；终止原因为command_pipe_closed。
第一条有效快照逐字节JSON重新严格读取，三实例0/1/2均timestamp=timestamp_sample=492000us，
两个积分dt均4000us，设备ID分别1310988/1310996/1311004。该快照不能替代EKF内部低通或对齐状态。
原文见[01-raw](../.runtime/runs/sim-flight-sw02b-probe-20261030T014636029383/uorb-probe/01-raw.json)、
[02-raw](../.runtime/runs/sim-flight-sw02b-probe-20261030T014636029383/uorb-probe/02-raw.json)。
第二条退出码0、stderr空，只有六个Instance标题；不从exit0推导任何有效业务数据。

新增源码复核冻结[六份源文本](../.runtime/runs/sim-flight-sw02-stage-20261030T014816354843/probe-source-evidence.json)：
Manager::orb_exists检查is_advertised；listener快照打印标题后忽略listener_print_topic返回值；
后者只在orb_copy成功时打印字段。DeviceNode::copy在没有数据缓冲时返回false，
Manager::orb_copy对长度不符返回错误；因此存在“advertised但无法复制有效载荷”的源码路径。
EKF2构造即advertise状态话题，PublishStatus/Flags受`_ekf.update()`成功分支约束。
这些解释空标题为何不能当正常数据；本轮没有直接导出内部返回码或缓冲指针，
故不能断言此次复制失败的唯一原因、tilt_align=false或六实例都没有执行过update。
其余topic及三个参数未查询，姿态/模式/PWM/发送段仍无本run完整证据。

## 5. 实际验证、保护与恢复

独立预期原始字节先冻结于[oracle目录](../.runtime/runs/sim-flight-sw02b-oracle-20261030T013515386163/independent-expectations.json)，
审计确认当前字节未变。新17项+旧32项飞行共49项，覆盖缺失与0、非连续多实例、
无载荷实例、设备注释、坏类型/时间/身份/命令、超限及真实子进程超时/洪泛/坏UTF-8等。
超时测试只终止自己的测试子进程；四个实际会话均无强制清理。

最终[旧阶段runner](../.runtime/runs/sim-flight-sw02-stage-20261030T014816354843/report.json)在445份冻结源码上通过：
normal250条/250次Run/1s，disconnect126条/125次Run/停.5s，均实际执行器0包；
49飞行、84运动、952全仓轻量测试通过。[真实线格式报告](../.runtime/runs/sim-motion-sw04a-20261030T014856941104/report.json)
核对77组场景字节、36组旧公共往返及18合成源转换。没有mock替代这些线格式检查。

[最终审计](../.runtime/runs/sim-flight-sw02-stage-20261030T014816354843/probe-audit.json)确认：
原439文件仅改显式诊断runner，新增6文件；原25定义/7入口、两次probe的30份桥接原源与8份原生msg保持。
所有11个实际自有PID均退出，各会话端口free、无强制退出；probe文件分别23539/27816字节。
当前branch/HEAD与全部既有dirty/未跟踪内容保留，无提交/推送、依赖安装、Hash或研究仓修改。
恢复方式是维持原默认入口；诊断失败会话已经结束，后续必须新run，不复用旧记录或回写历史产物。

## 6. 直接下一任务

SIM-FLIGHT-DIAG-DESIGN-03（计划；主责任simulation_engineer）：针对实际空实例标题设计补证，
先冻结独立三态判据：完整载荷、明确never published、已advertise但本次copy无载荷；
第三态不能伪装成成功快照或赋零，且不得改写SW-02B原fail-closed验收。
设计需明确是否增加独立诊断事件/显式新模式，什么精确原文可分类、哪些畸形/混合输出仍须立即停止，
以及如何在不扩命令白名单、不增1s/250步/原墙钟限额下完成余下链路观测。
本轮仅提出此工作包，尚未实现三态合同、继续查询策略或新的21次运行；先交具体方案再实施。
不重跑同一失败probe，不自动进入SW-03/04；实际执行器/属性、因果绑定、v2、长窗与受控飞行仍未验证。

2026-10-30后续：[DIAG-DESIGN-03具体方案](SIM_FLIGHT_DIAG_DESIGN03_20261030.md)已完成，
明确独立三态diagnostic事件与显式模式、混合完整/空块及畸形拒绝，旧strict与本轮失败保持。
下一项SW-02C先冻结独立预期后实施，尚未完成新21次采集；不据设计提高本任务状态。
