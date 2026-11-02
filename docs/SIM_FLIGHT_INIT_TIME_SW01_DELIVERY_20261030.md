# 整数时间生产修复与10秒无控制准备交付

日期：2026-10-30；版本：v0.1；任务：SIM-FLIGHT-INIT-TIME-SW-01。
主责任：simulation_engineer；状态：已完成（隔离生产者修复、单profile 10s无控制准备/故障兼容软件范围）。
依据：[具体修复范围](SIM_FLIGHT_INIT_SELECTOR_SW02_PREPARATION_20261030.md#6-验证源码版本与下一任务)、
[selector离线合同](SIM_FLIGHT_INIT_SELECTOR_SW01_CONTRACT_20261030.md)、ADR-044；
实验：[EXP-20261030-015](../experiments/2026-10-30-sim-flight-initialization-time.md)。

## 1. 本轮结果与验收范围

发送端时间生产修复只用于新的隔离源副本/显式入口；旧488份源码/配置、桥接原树/旧入口/公共消息不改。
新正常一次完成2500 Run/10s、98 raw/98合法查询，四门collection_complete/input_settled/
initialization_ready/output_chain_observed均true，两个必需末检查点2000/2500均ready。
[阶段报告](../.runtime/runs/flight-init-time-sw01-stage-20261030T140716237059/report.json)
passed=true、runtime_accepted=true，关闭本单profile无控制准备软件子范围。

实际2500 HIL_SENSOR/9 HIL_GPS全部有原double源时间/整数发送值收据，独立原始wire逐包核对；
原失败位置step1008现在实际发送4028000us，旧4027999us失败原文/manifest保持原结论。
新7/飞行180/运动84/全仓1083项、真实C++/5016个MAVLink探针包、断连/期限与旧入口兼容通过。
这不是严格周期绑定、非零属性因果、模式/arming、30/40s采样、受控飞行或完整阶段退出；
binding_status仍unverified、control_gate_accepted=false，没有向PX4发送控制命令。

## 2. 新增文件与真实生产消费链

| 文件 | 作用 |
| --- | --- |
| [time_grid.h](../simulation/flight_initialization_time/time_grid.h) | 标准库纯C++校验：源double有限/非负、具名source_step≤2500，按long double计算原4ms/1ns误差，合格后返回source_step×4000的uint64微秒 |
| [adapt.py](../simulation/flight_initialization_time/adapt.py) | 新精确上下文适配，只在副本替换HIL_SENSOR/GPS生成时间调用，并在旧diagnostics副本加当前transaction守门/独立源时间收据；重复/漂移/未知源拒绝 |
| [time_probe.cpp](../simulation/flight_initialization_time/time_probe.cpp) | 实际C++边界探针，调用同一生产函数并用真实MAVLink生成头序列化HIL_SENSOR和GPS，不接PX4/网络 |
| [time_build.py](../ros_ws/sim_flight_initialization_time_build.py) | 独立.runtime/ros/sim-flight-initialization-time-build/<run>，复制原源、先原观察适配再时间适配，原host.cpp/diagnostics.h复用，编译并跑原控制拒绝自检 |
| [time_run.py](../ros_ws/sim_flight_initialization_time_run.py) | 新显式正常/断连/期限入口；机械复用已验98采集装配，只替换build和run前缀，原入口/default不改 |
| [独立预期](../tests/fixtures/sim_flight_initialization_time_cases.json) | 先行16组输入/接受或拒绝/整数期望、1008反例、2501源时刻与原运行界 |
| [C++/wire检查](../tests/sim_flight_initialization_time_probe.py) | 编译真实探针、按冻结字面量对账，由独立pymavlink解码实际生成字节；不以mock替代线格式 |
| [新增测试](../tests/test_sim_flight_initialization_time.py) | 7项：边界/字节、旧截断保持拒绝、新旧源副本分离、漂移/重复、当前transaction/收据界与原预算/控制门 |
| [实际收据审计](../tests/sim_flight_initialization_time_checks.py) | 复用已有wire/物理/原文独立审计，再核每个HIL/GPS源收据与物理before/整数网格/实际发送字节一一对应 |
| [阶段入口](../tests/sim_flight_initialization_time_stage.py) | 只读指定的三actual run，不重跑新正常准备；要求同最终源码，再跑旧1s两例/真实公共往返与全仓回归 |

共10新增文件，最终498源码/配置；原488份逐文本相同。没有修改旧adapt/宿主/query/runner/profile/codec。
真实链为同FGFDMExec源时间/当前step → 新发送时间函数 → 原生MAVLink序列化/发送 → 原PX4 →
既有98只读查询/私有记录 → tests独立审计。新收据只有离线诊断消费者，不进入在线SensorBundle/定位/map/forward。
无新ROS/Gazebo/RViz图、AircraftState/TF权威、公共类型或规划/控制通道。

## 3. 时间生产与拒绝规则

旧桥接double×1e6直接截断是历史失败原因；新构建仅在发送前的两个生产点处理：
jsbsim_bridge的SendSensorMessages参数、sensor_gps_plugin的time_utc_usec赋值。
GPS字段继续承载此仿真的原生模拟时间语义，未声明为真实UTC/实物时钟，也不改更新频率或其他载荷。

纯函数先拒绝非有限/负秒、source_step>2500，再按long double核对
abs(source_seconds×1e9−source_step×4000000)≤1ns，之后返回source_step×4000。
实际hook还要求!emitted、当前宿主step在1..2500、传感器类型为HIL_SENSOR或GPS，
因此运行中source_step只0..2499。纯探针可验证10s/step2500物理端点，但不会发第2501个运行传感器步。
不是任意round或静默fallback；离网格的源不会被补正继续，更不修收到的包、PX4时间或历史wire。
原source物理/4ms/1ns、整数HIL硬门及全部IC/模型/噪声/阈值保持。

新diagnostics/time-grid.jsonl每条精确保存sensor_kind/source_step/source_time_s/time_usec；
源double用17位精度原样输出，时间校验成功后、序列化发送前写收据，写失败停止。
hook最多5000条，单条源字段固定有界；审计另核每行≤256字节、总≤1MiB、唯一类型/step、
与实际wire覆盖一一对应、源值等于该步fdm.sim_time_before_s、整数值等于原网格。
收据只是生产来源证明，不证明selector消费同一IMU消息或执行器对应当前周期。

所有源/适配仅写新.runtime/ros目录，精确源上下文不符或重复适配即拒绝，不修改第三方原树。
回退须显式选择旧入口；旧输入到4.028s仍会遇到原截断失败，不能把回退写成时间修复成功。

## 4. 先行独立预期与C++字节验证

[oracle](../.runtime/runs/flight-init-time-oracle-20261030T135812795388/report.json)记录生产header尚不存在时，
已冻结16组字面量及旧失败step/生产源文本；没有用被测函数生成整数预期，也未新增Hash。
0/.004/4.028/9.996/10秒分别期望0/4000/4028000/9996000/10000000us。
±0.5ns接受，±1.5ns/错step/负/NaN/Inf/超步界/极大值拒绝；拒绝例无包字节字段。
真实C++累加double循环覆盖0..2500共2501时刻，逐个对账整数步长4000us。

[探针报告](../.runtime/runs/flight-init-time-probe-20261030T140317997689/report.json)：
16组中7接受/9拒绝，7×2+2501×2=5016个真实MAVLink包独立解码通过；
边界输出与2501条轨迹输出保存同目录，不称作真实FDM/PX4运行。
每包核对类型、sys/comp身份与uint64时间；原截断值仍在原物理codec严格拒绝，未放宽旧合同。

## 5. 实际正常、故障与资源

正常：[140416952008](../.runtime/runs/flight-init-time-sw01-normal-20261030T140416952008/manifest.json)，
[独立审计](../.runtime/runs/flight-init-time-sw01-stage-20261030T140716237059/normal-audit.json)。

| 对象 | 实际结果及边界 |
| --- | --- |
| 物理/传感器 | 2500成功Run/10s、2500 HIL_SENSOR/9 GPS、2509条源时间收据；全部原始发送时间核对通过 |
| 旧失败位置 | 第1008条wire=4028000us，源仍为原double4.028；本轮未改旧4027999us证据或它的失败状态 |
| 源网格误差 | 2509收据最大约.000656812ns，满足原1ns界；源double未改成网格浮点数再回写 |
| 查询/四门 | 98 raw/98合法事件、七参数/七topic组完成，四门全true；125/250尚缺selector，500起局部ready，2000/2500两个末检查点均通过 |
| 设备/姿态 | 两末检查点primary=5，gyro/accel槽2；attitude/vehicle sample分别7992000→9992000us，身份/姿态/land/年龄门通过，不假定实例号等于设备槽 |
| 合法缺失 | selector共80处数组缺失显式隔离，selector_payload_complete=false；原消费IMU时间null、exact_source_message_verified=false，不补零/1或伪造同tick |
| 执行器 | 第423—2500步2078个真实全零HIL_ACTUATOR_CONTROLS、16路/四属性请求读回0；actuator−HIL仍−4000us，末窗口有500包，严格绑定未通过 |
| 墙钟 | 物理准备约30.7621s<60s，最长组约131.876ms<400ms、单query约9.175ms<200ms；非10s实时倍率、20ms感知/RSS/正式PERF验收 |

两故障均完成125 Run/20条查询；第126条未Run、源时间仍约.5s：

| 用例 | 实际证据 |
| --- | --- |
| disconnect | [140527292790](../.runtime/runs/flight-init-time-sw01-disconnect-20261030T140527292790/manifest.json)：126 HIL/源收据、125 Run/20合法事件、peer_closed；独立审计和清理通过 |
| transaction-timeout | [140631932469](../.runtime/runs/flight-init-time-sw01-transaction-timeout-20261030T140631932469/manifest.json)：第126条原1.01s注入，宿主与监督均停止；126 HIL/源收据、125 Run/20事件、transaction_timeout；超时末条仅保留失败raw，独立审计通过 |

三actual使用同最终498份源码快照，期间与验证后没有代码变化；一次新正常、不重试。
build-only另在[140319100403](../.runtime/runs/flight-init-time-sw01-normal-20261030T140319100403/manifest.json)，只有编译/原五类控制拒绝检查，无实际场景。
旧1s正常/断连另通过：[兼容报告](../.runtime/runs/sim-flight-sw02-stage-20261030T140719368638/report.json)。
[旧真实genpy/全仓](../.runtime/runs/sim-motion-sw04a-20261030T140819220726/report.json)：
77场景字节/36公共往返/18合成源转换、25旧定义/7入口保持；新增7/飞行180/运动84/全仓1083通过。
最后只更新文档/保护审计，见[final-audit.json](../.runtime/runs/flight-init-time-sw01-stage-20261030T140716237059/final-audit.json)。

## 6. 下一任务与未验证能力

本10s准备的软件门已按实际证据关闭，停止反复扩大初始化窗口或调整selector缺失条件。
直接下一项SIM-FLIGHT-SW-03A（计划；主责任integration_engineer）：按
[原公共v2方案](SIM_FLIGHT_DESIGN_20261029.md#5-拟议新窗口与公共承载)和
[准备交接分步](SIM_FLIGHT_INIT_DESIGN_20261030.md#8-实施分工与独立预期)，先冻结独立预期，
再新增ufm_flight_contract离线逻辑/严格codec和独立端点合同，复用现有SceneFrame/SceneStep/SceneCaptureAck生成类型。
v2与旧v1交叉拒绝，冻结ground锚点/注册、10000步/40s元数据及7525..10000的100个未来采样点，
实际生成消息序列化/旧字节兼容与轻量回归；不启动30/40s运行、插件端点/节点或控制命令。
若需生成/构建，仅使用固定Python及隔离.runtime/ros；旧公共消息字段、默认入口/v1预算保持。

后续SW-03B才接长窗准备/采样屏障/唯一TF与原生窗口，必须重新核新profile全部预算和就绪，
不能从本单run推导长窗、所有场景/参数或机载能力；SW-04的严格周期绑定、非零因果、模式/arming/离地另验。
真实设备/研究模型质量、DEM/占据融合、正式资源和完整阶段仍未通过；research继续fail-closed。
无新依赖/Hash/同级研究仓修改/历史删除/自动提交或推送。
