# 私有初始化宿主与实际准备交接

日期：2026-10-30；版本：v0.1；任务：SIM-FLIGHT-INIT-SW-02；主责任：simulation_engineer。
状态：已完成（宿主/采集软件、实际部分证据、故障与兼容子范围）；完整准备运行未通过。
依据：[准备设计](SIM_FLIGHT_INIT_DESIGN_20261030.md)、[离线合同](SIM_FLIGHT_INIT_SW01_CONTRACT_20261030.md)、ADR-044。
实验：[EXP-20261030-011](../experiments/2026-10-30-sim-flight-initialization-preparation.md)。

## 1. 本轮结论

已实现独立同FDM准备宿主/hook、精确原源复制适配、隔离构建/薄运行器及固定84项只读查询。
实际正常run在500步/2s、第30次selector查询遇到非有限数组槽位，按原合同停止，
保存30份查询原文/29合法事件；没有扩大NaN白名单、补零、跳查询或重跑同一正常场景。
故完整2500步/10s、84次采集、两个末检查点初始化与输出门均未通过，不能进入SW-03运行或控制。

本轮新增实证为78个真实全零HIL_ACTUATOR_CONTROLS、逐包属性请求/读回0和对应78次成功Run。
首包第423步，HIL1688000us/执行器1684000us；78包的actuator-HIL差均−4000us。
这些是实际未armed输出证据，仍binding_status=unverified、control_gate_accepted=false，
不把收到包、时差固定或地面舵面输出升级为严格当前周期/非零属性因果或飞行验收。

[阶段报告](../.runtime/runs/flight-init-sw02-stage-20261030T120415015778/report.json)
保留passed=false、runtime_accepted=false；software_regression_and_fault_checks_passed=true。
新增7项、飞行134/134、运动84/84、全仓1037/1037及旧实际入口/消息兼容通过。

## 2. 修改文件及真实链

本轮新增10个源码/fixture文件，原466份源码/配置不改；同级研究仓、原flight_bridge/诊断入口、
公共消息/profile/codec、PX4核心与第三方原源保持。配套更新本说明/实验和管理/接口索引。

| 文件 | 当前问题与实现 |
| --- | --- |
| [diagnostics.h](../simulation/flight_initialization/diagnostics.h) | 新私有hook声明，沿原桥接回调顺序，不进入业务层 |
| [diagnostics.cpp](../simulation/flight_initialization/diagnostics.cpp) | 原始wire、逐step源前后动力学/三支柱接触、16路/四属性及Run收据；硬门/期限/总量与控制拒绝 |
| [host.cpp](../simulation/flight_initialization/host.cpp) | 一个FGFDMExec，next/quit及2500步硬界、原IC安装；无ROS/控制发送 |
| [sim_flight_initialization_build.py](../ros_ws/sim_flight_initialization_build.py) | 新.runtime/ros目录，复用原精确上下文纯adapt到源副本，编译新宿主及C++离线控制拒绝检查 |
| [sim_flight_initialization_queries.py](../ros_ws/sim_flight_initialization_queries.py) | 固定84项原生listener/show、owner前后、原文保存/投影、期限/字节界；复用原有界客户端/身份函数 |
| [sim_flight_initialization_run.py](../ros_ws/sim_flight_initialization_run.py) | 默认独立normal，另disconnect/transaction-timeout；配置/源预检、逐步守门/实际查询、四门分报及自有进程清理 |
| [sim_flight_initialization_checks.py](../tests/sim_flight_initialization_checks.py) | 独立解码原始MAVLink、逐step传感器/执行器float32位值/属性/时间与查询原文/组期限审计 |
| [sim_flight_initialization_selector_rejection.json](../tests/fixtures/sim_flight_initialization_selector_rejection.json) | 机械保存第30条实际selector原文，仅为严格拒绝回归，不作在线状态或传感器输入 |
| [test_sim_flight_initialization_runtime.py](../tests/test_sim_flight_initialization_runtime.py) | 7项：预spawn/写后期限、总量、原文失败无重试、精确源副本、FDM原容差及实际NaN拒绝 |
| [sim_flight_initialization_stage.py](../tests/sim_flight_initialization_stage.py) | 显式重读本次三run证据，复现正常拒绝、故障停止、旧实际1s两例及全仓；不重启失败的正常准备 |

生产链为新宿主同FDM→原HIL发送/原PX4→只读查询→私有记录→tests审计。
没有SensorBundle/定位/TF/map/研究forward消费者，没有新ROS/Gazebo/RViz图或公共Scene v2端点。
第三方源仅复制到.runtime/ros/sim-flight-initialization-build/<run>再作原有精确适配；原树不写。
地面IC、模型、噪声、接触系数和EKF阈值不改，不循环RunIC/trim或冻结位姿来伪造静稳。

## 3. 守门、记录与预算

独立新宿主允许首零包前显式missing推进，始终记录null/零初始属性而不是伪造收到反馈；
首包后每步须有新包、source身份/序号/原戳正确，缺包在Run前停止。
只接system/component=1、mode=1、flags≤1、16路有限且全0；armed/非零/错身份/非有限立即Run前拒绝。
原桥接2/5/7/4通道顺序、−1/−1/−1/+1符号保持，请求和实际属性必须全0。
源前/后真实AGL、ECEF、NED速度、Euler/PQR、pilot比力与三支柱WOW/压缩力通过公开JSBSim API读取，
单位/时间按SW-01合同保留，不把CG AGL或WOW转成PX4 landed/at_rest。
HIL原微秒/float32与FDM原double时间分开；原4ms/1ns界、单FDM一次Run/step不变。

原始wire只允许宿主发HIL_SENSOR/HIL_GPS，接收PX4启动请求/heartbeat与执行器；没有本仓heartbeat/
模式/arm/manual/参数写。每次查询用owned daemon的PID/start_ticks/exe/rootfs/socket文件/内核身份前后核对。
七参数在125步先show实际通过1033/0/0/.1000/0/0/1；11topic组、所有实例原文、未知编号null、
准确两字段nan条件隔离和其他非有限拒绝保持；第30条selector数组不在允许隔离范围。

硬门仍2500步/10s，initial后60s/session120s/startup60s/build180s、transaction1s、client200ms/group400ms。
源前不安全不得Run、源后越界留该条并停止；每次next/query前、原文/事件保存后复查期限，
查询文件连同消息/源元数据≤16MiB、原文≤32KiB/事件≤256KiB，step≤16KiB/64MiB，
wire原字节≤16MiB/8192事件、case所有文件≤256MiB；外部日志随监督10ms轮询核对。
源时间不因观测而重置，等待PX4只消费墙钟不隐藏时间；超限原文保留且不编码为合法正常事件。
期限故障末条wall超1s只能作为失败raw证据，不能伪造合法step或用末条正常合同放行。
这些仅是该run的门禁，不是RSS、实时倍率、端到端20ms或正式PERF。

## 4. 实际结果与独立证据

新normal：[115944038112](../.runtime/runs/flight-init-sw02-normal-20261030T115944038112/manifest.json)。
[独立wire/查询审计](../.runtime/runs/flight-init-sw02-stage-20261030T120415015778/normal-audit.json)、
[逐流物理/零包审计](../.runtime/runs/flight-init-sw02-stage-20261030T120415015778/normal-physics-audit.json)。

| 对象 | 实际结果 | 验收分界 |
| --- | --- | --- |
| 原生wire/FDM | 500 HIL_SENSOR/1 HIL_GPS、500次Run、2s，wire44366字节/580块 | 不足2500步/10s，不能关闭完整准备 |
| 实际零执行器 | 第423—500步共78包，16路/四属性均0、mode1/armed=false，差值−4000us | 已有正向零输出/读回；没有严格当前周期或非零属性证据 |
| 地面接触/物理 | 两主支柱第33步、尾支柱91步首次WOW；2s AGL≈.310829m、pitch≈8.422156°，真空速≈.002941m/s | 正常地面接触瞬态有记录，不再凭.5m IC猜静止或接触 |
| 输入静稳 | 第500检查点前连续250步满足本合同输入门；前125/250不满足 | 未到2000/2500两个必需末检查点，整体input_settled仍未通过 |
| 七参数/查询 | 七参数实际读回；125/250两topic组和参数组共29合法事件；第30次/500步第一selector查询失败 | 30 raw≠84合法事件，不跳过selector继续或声称完整姿态就绪 |
| selector实际原文 | primary=1、available=6，combined/relative各索引6—8为nan；accumulated gyro/accel各索引3为nan，共8槽 | 原文非有限严格拒绝，不填0/1、截数组或视为全部有效 |

仅selector第30条有primary/healthy等原文信息，未生成合法事件，不拿这些未经合同接纳的字段作运行准入。
500步flags/estimator_attitude/vehicle_attitude尚未执行查询，不能由零回包倒推出其本run完整就绪状态。
同run既有125/250样本仍有缺失/旧时间，不能当末窗口状态。

两故障均在125次成功Run后第126条停于约.5s，Run=false/result=null；末HIL500000us保留：

| 用例 | 证据与实际结果 |
| --- | --- |
| disconnect | [120111523545](../.runtime/runs/flight-init-sw02-disconnect-20261030T120111523545/manifest.json)：只停止本run PX4；126原始HIL/125 Run/18合法query，peer_closed；独立审计通过 |
| transaction-timeout | [120254975810](../.runtime/runs/flight-init-sw02-transaction-timeout-20261030T120254975810/manifest.json)：仅第126步allow_run前注入1.01s墙钟延迟；宿主和监督器期限均生效，126 raw/125 Run/18合法query、transaction_timeout；独立审计通过 |

故障只验证停止，不制造完整初始化通过。所有实际记录/查询原文保留；本仓没下发控制请求。

## 5. 失败、修正与源码版本

首次[build-only](../.runtime/runs/flight-init-sw02-normal-20261030T115737174599/manifest.json)隔离构建/C++五类拒绝检查通过。
首次实际入口[115854283131](../.runtime/runs/flight-init-sw02-normal-20261030T115854283131/manifest.json)
在端口核查被沙箱拒绝Operation not permitted，无子进程启动；获得本机回环执行许可后才启动上述真实run。
这是权限限制，不是自动审批拒绝或仿真技术失败；没有修改系统网络/环境来绕过。

初次[期限测试120147090064](../.runtime/runs/flight-init-sw02-transaction-timeout-20261030T120147090064/manifest.json)
确实在Run前停止，但审计代码将原始.5000000000000003与.5作精确相等，导致软件结论误判失败。
已先复现该比较错误，再沿原1ns界修正并加反例，以新run重验通过；未放宽物理容差/期限或改戳，旧失败保留。
正常run的selector失败没有重跑，也没有借修复故障审计更改其原结论。

新正常/断连接/期限证据分属本轮不同源码快照：正常后只补运行清理统计与期限审计的1ns修复，
并增强tests；C++宿主/hook、query包装、SW-01合同和源输入逐文本相同。
阶段报告列出各case之后变化的三个文件；不称为同一最终源码上通过完整矩阵。
最终476份源码上飞行134/134（新7项）、运动84/84、全仓1037/1037通过。
[旧实际normal/disconnect](../.runtime/runs/sim-flight-sw02-stage-20261030T120421643861/report.json)
仍分别250条/250 Run/1s、126条/125 Run/.5s停止，通过原wire/IC/清理。
旧77场景字节/36公共往返/18合成源转换使用真实genpy；25份定义/7入口保持。
最终回归后只更新文档/关闭审计，不重复测试或额外场景运行。

## 6. 剩余能力与下一任务

宿主/有界查询及停止软件子范围交付；完整84采集、10s准备、两个末检查点初始化/输出判定仍未通过。
当前新增缺口明确为selector数组非有限表示，不能再次仅靠增窗或重复旧21/84查询解决。
原[选择器源码文本](../.runtime/runs/flight-init-sw02-stage-20261030T120415015778/selector-source-evidence.json)
显示未使用estimator比值初始为NAN，IMU误差无设备时写NAN；但selector本身没有完整IMU槽位设备表，
不能只凭当前primary/available猜accumulated数组的所有nan都合法或以healthy=False作通用豁免。

直接下一项SIM-FLIGHT-INIT-SELECTOR-DESIGN-01（计划；主责任simulation_engineer）：
只读审查selector两组比值/两组IMU误差数组的有效槽位、生产来源、原始身份及所需独立观测，
交付精确字段/索引条件、显式不可用表示、schema/查询迁移、预算/停止及独立反例方案。
旧合同/本次失败保持，不先实现放宽、不重跑正常准备、不增加查询或修改public protocol。
该设计须先区分estimator实例和IMU设备槽位，无法从现有原文证明的条件保持不可用。

正向非零属性因果/严格周期绑定、公共Scene v2/长窗采样、模式/arming/手动命令、离地/受控飞行仍未验证。
研究质量、真实设备、DEM/占据融合与正式资源继续独立暂缓；本轮未安装依赖/Hash/改研究仓，未提交/推送。

2026-10-30后续：[INIT-SELECTOR-DESIGN-01](SIM_FLIGHT_INIT_SELECTOR_DESIGN_20261030.md)已完成只读具体设计，
24项源事实/历史重读/134项既有飞行测试通过，476源码保持；拟独立98项观测及设备关联，原合同和本次失败不变。
直接下一项INIT-SELECTOR-SW-01仅实施独立离线合同/先行预期；尚未实现新规则或重跑准备期。
