# selector实际采集、停止与时间边界交接

日期：2026-10-30；版本：v0.1；任务：SIM-FLIGHT-INIT-SELECTOR-SW-02。
主责任：simulation_engineer；状态：已完成（装配/部分实际证据/故障兼容软件子范围）；完整准备未通过。
依据：[具体设计](SIM_FLIGHT_INIT_SELECTOR_DESIGN_20261030.md)、[离线合同](SIM_FLIGHT_INIT_SELECTOR_SW01_CONTRACT_20261030.md)、ADR-044。
实验：[EXP-20261030-014](../experiments/2026-10-30-sim-flight-initialization-selector-preparation.md)。

## 1. 本轮结果

已实现独立98项owned daemon只读采集/运行入口与原始wire/物理/查询审计。
唯一一次新规则正常运行取得59条raw/59条合法事件、1007次成功Run/4.028s及582个真实全零执行器包。
第500/1000步两个实际局部检查点按当前合同就绪，主实例4、gyro/accel槽1；仍非2000/2500双末检查点。
第1008条实际HIL时间为4027999us，整数网格应为4028000us；宿主在Run前拒绝，Python严格拒绝该raw。
完整2500步/98采集、双末检查点与全局四门未通过；不改原戳、物理容差或重跑正常场景。

[阶段报告](../.runtime/runs/flight-init-selector-sw02-stage-20261030T133918017071/report.json)：
passed=false、runtime_accepted=false；software_regression_and_fault_checks_passed=true。
新增11项、飞行173/173、运动84/84、全仓1076/1076及旧实际入口/真实genpy兼容通过。
始终binding_status=unverified、control_gate_accepted=false，没有发heartbeat/arm/manual/参数写或其他控制请求。

## 2. 文件与真实生产消费链

| 文件 | 本轮修改与原因 |
| --- | --- |
| [selector_queries.py](../ros_ws/sim_flight_initialization_selector_queries.py) | 新增：固定98项、owner前后/跨流、原文先保存、解析/落盘期限及metadata总量、失败锁定无重试 |
| [selector_run.py](../ros_ws/sim_flight_initialization_selector_run.py) | 新增：源/profile前检、复用原隔离构建/同FDM宿主、显式正常/断连/期限三例、原物理记录+新header/查询、四门分报与自有进程清理 |
| [selector_checks.py](../tests/sim_flight_initialization_selector_checks.py) | 新增：独立MAVLink解码、真实原戳/float32/16路/逐步单位与Run、查询原文/组期限/关联及拒绝raw单列审计 |
| [selector_stage.py](../tests/sim_flight_initialization_selector_stage.py) | 新增：显式指向保留三run，只审计不重跑正常准备；旧1s正常/断连、真实公共往返/全仓回归及保护检查 |
| [selector_runtime测试](../tests/test_sim_flight_initialization_selector_runtime.py) | 新增11项：前/后期限、raw/事件保存失败、畸形/锁定、总量、七参数一次性、末查询/宿主终态、固定运行链接和截断拒绝 |
| [私有selector合同](../simulation/ufm_simulation/flight_initialization_selector.py) | 修改：先复现再修正两处离线组合边界，见下一节；不改槽位条件、98计划或实际时间生产者 |

新增5文件、已有483份中仅修改此私有合同，最终488份源码/配置；旧物理合同/84入口/C++宿主/适配与公共消息保持。
simulation原同FDM/原IC/传感器 → 原PX4 → 新ros_ws只读客户端 → 私有合同/记录 → tests审计，
不新增ROS/Gazebo/RViz图、AircraftState/TF权威或SensorBundle/定位/map/研究forward消费者。
所有编译仍由原build函数在新.runtime/ros/sim-flight-initialization-build/<run>复制适配，第三方原树不改。

## 3. 先复现的两处离线边界修正

1. 原宿主在第2500次Run/emit后立即写物理terminal，Python随后采集最后13项。
   新离线合同此前误将物理terminal当查询录制结束，合成复现selector_query_after_physical_boundary。
   现在仅当物理2500次成功、未unsafe/失败且terminal=window_complete时，允许最后检查点查询晚于该物理终态；
   非末组仍须早于下一HIL/物理终态，所有查询仍受原60s/组400ms等期限，不改任何原时间。
2. PX4会自动安装rootfs/etc指向本仓.runtime/build/px4-v1.13.3/etc的运行资源链接，
   原新loader遍历全部产物时将其误判为记录输入链接，先以合成数据复现selector_recording_symlink。
   现在只跳过此精确路径/目标，不读取/遍历其内容；所有记录路径、根/祖先与其他内部链接仍拒绝。

[前置复现目录](../.runtime/runs/flight-init-selector-sw02-preflight-20261030T132908465690/terminal-boundary-reproduction.json)、
[固定资源链接复现](../.runtime/runs/flight-init-selector-sw02-preflight-20261030T132908465690/runtime-link-reproduction.json)。
两项均在实际准备前修正并加反例，原schema、字段、物理/身份/未知语义及预算不变；
本轮未达到真实第2500步，终态后末组顺序仅合成验证，不冒充实际末组交接通过。

## 4. 实际新正常与两个故障

正常：[133458680660](../.runtime/runs/flight-init-selector-sw02-normal-20261030T133458680660/manifest.json)；
[独立审计](../.runtime/runs/flight-init-selector-sw02-stage-20261030T133918017071/normal-audit.json)。

| 对象 | 实际结果/分界 |
| --- | --- |
| wire/物理 | 1008 HIL_SENSOR/4 HIL_GPS，1007 Run/4.028s；前1007条合法，第1008条拒绝raw不作为合法step |
| 全零执行器 | 582包，第426—1007步，mode1/armed=false/16路和四属性均0；actuator-HIL差均−4000us，仍未证明严格周期绑定 |
| 查询 | 七参数+125/250/500/1000四组共59 raw/59合法事件，无缺失/重试/改计划；尚非98项完整采集 |
| selector缺失 | 500/1000组前后共32处数组缺失按新合同显式隔离；未补0/1，旧84 codec/历史第30次拒绝不改 |
| 局部就绪 | 125/250 selector未发布，检查点否决；500/1000按合同ready=true，primary=4、gyro/accel槽1，原姿态/设备/land/年龄门通过 |
| 输入/输出全局门 | 500/1000前连续250步物理输入静稳，但未到2000/2500，全局input_settled/initialization_ready/output_chain_observed仍false；582零包不替代规定末窗口 |
| 时间/资源 | 完成五组，最长109313459ns≈109.3ms，最长单查询7752928ns≈7.75ms；query目录352590字节（metadata另计） |

本次时间/载荷仅此run所列逻辑与墙钟结果，不是RSS、20ms感知时延、完整10s预算或正式PERF。
前后表原时间独立保留，selector消费消息时间null、exact_source_message_verified=false；局部ready不开放控制。

两故障均先完成125步、七参数/首组共20条合法查询，下一步停止：

| 用例 | 证据与结果 |
| --- | --- |
| disconnect | [133633428328](../.runtime/runs/flight-init-selector-sw02-disconnect-20261030T133633428328/manifest.json)：126原始HIL/125 Run、20 raw/事件，peer_closed，末条未Run且源时保持约.5s，独立审计通过 |
| transaction-timeout | [133730530101](../.runtime/runs/flight-init-selector-sw02-transaction-timeout-20261030T133730530101/manifest.json)：仅126步allow_run前原注入1.01s，宿主/监督期限均触发；126 raw/125合法Run/20事件，transaction_timeout，独立审计通过 |

期限末条超过正常transaction1s，只保留失败raw，不伪装合法step。所有actual子进程和端口已清理，无强制信号。
旧1s两例另外通过：[兼容报告](../.runtime/runs/sim-flight-sw02-stage-20261030T133918636560/report.json)，
不是重跑本次新正常准备；旧源码/场景入口不改。

## 5. 新失败的源码与数值证据

第1008条宿主invalid_input，监督器initialization_hil_time；无Run/result=null、前后物理/属性相同。
实际原生桥接jsbsim_bridge.cpp:172读取double simtime，:193用static_cast<uint64_t>(simtime * 1e6)，
mavlink_interface.cpp:231原样赋给sensor_msg.time_usec，之后hook在Run前检查网格拒绝。
另sensor_gps_plugin.cpp:77也使用同类截断，当前四个GPS未构成本次停止原因；不能推导所有未来GPS时间均正确。

[源全文/四事实](../.runtime/runs/flight-init-selector-sw02-stage-20261030T133918017071/time-source-evidence.json)、
[数值证据](../.runtime/runs/flight-init-selector-sw02-stage-20261030T133918017071/time-numeric-evidence.json)、
[原始拒绝step副本](../.runtime/runs/flight-init-selector-sw02-stage-20261030T133918017071/time-failed-raw-step.json)：

- 原double显示4.028，其乘1e6实际为4027999.9999999995，截断后4027999；网格期望4028000。
- 原源时间相对4ms网格误差约−4.1922e-7ns，仍在既有1ns物理界内；整数化却产生−1us。
- wire审计确认发送的就是4027999，并与拒绝raw一致，没有将其重写为期望值。
- 宿主在接收执行器/属性施加/Run前停止，没有借1ns容差接受错误整数时间或放宽协议。

这是当前已定位的发送端double→uint64微秒量化问题，不是selector规则或新IMU表缺失造成的新失败。
本轮只保存证据/补严格拒绝回归，未修改时间生产者/旧适配/本次wire/manifest或再次运行正常场景。

## 6. 验证、源码版本与下一任务

build-only隔离编译/原C++五类拒绝通过，新增停止测试先9项、补链接后10项通过；实际后再补截断反例共11项。
新三actual case使用同一488份源码快照，之后仅tests审计/阶段工具/新增测试增强；
新查询/runner、私有合同、C++宿主及输入逐文本不变。阶段报告逐case列later_test_changes，
不声称三个actual在最终所有审计代码上重新跑过，也不重跑正常准备。
最终飞行173/运动84/全仓1076通过，旧77场景字节/36公共往返/18合成源转换仍用真实genpy、25定义/7入口保持。
[最终保护审计](../.runtime/runs/flight-init-selector-sw02-stage-20261030T133918017071/final-audit.json)核文件/预期、Git、PID和链接。

直接下一项SIM-FLIGHT-INIT-TIME-SW-01（计划；主责任simulation_engineer）：依据本次具体事实，
先冻结1008步反例与0/.004/4.028/9.996/10s等独立整数预期，再新增显式隔离的时间生产适配。
只在新.runtime/ros源副本中，于序列化/发送前检查源double有限、非负、具名source_step和原4ms/1ns网格，
以校验通过的source_step×4000产生uint64微秒；HIL_SENSOR与同Run实际GPS源时间分别核对，原GPS字段语义不改。
拒绝非有限/负/越界/离网格，不对收到的包、PX4时间或历史wire做修正，不新增通用fallback/容差或Hash。
旧适配/宿主/84与98入口默认保持；以新显式构建/入口接入，先真实C++边界及生成MAVLink字节检查，
再一次具有该实质生产者修复的新规则准备与故障、实际原戳/逐步物理/查询/清理对账。
若原源上下文漂移、超预算或10s仍未就绪，应留证失败，不改IC/模型/阈值、扩窗或重复同样失败。

本轮完整准备未关闭；SW-03A公共v2离线和SW-03B长窗/采样仍按前案分步，
严格绑定/非零属性因果、命令/arming/离地/飞行仍未验证；研究质量、真实DEM/占据融合和正式资源继续独立暂缓。
无依赖安装/Hash/同级研究仓修改/历史删除/自动提交或推送。

2026-10-30后续：[INIT-TIME-SW-01](SIM_FLIGHT_INIT_TIME_SW01_DELIVERY_20261030.md)已在独立源副本修复发送端量化，
新一次2500 Run/98采集、2509源收据/2078零包、双末检查点及四门通过，旧本次4027999us失败保持。
新7/飞行180/全仓1083及故障/旧入口兼容通过；仅单profile无控制准备门关闭，下一项公共v2离线合同。
