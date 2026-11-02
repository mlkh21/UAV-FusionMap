# 公共flight v2长窗准备与采样装配

日期：2026-11-02；版本：v0.1；任务：SIM-FLIGHT-SW-03B；主责任：integration_engineer。
状态：已完成（单profile 40秒无控制观察、采样/地图/原生窗口及故障兼容软件范围）；依据：[SW-03A离线交接](SIM_FLIGHT_SW03A_CONTRACT_20261102.md#7-sw-03b交接条件与未验证能力)、
[原飞行方案](SIM_FLIGHT_DESIGN_20261029.md)、[初始化准备设计](SIM_FLIGHT_INIT_DESIGN_20261030.md)、ADR-044。
实验：[EXP-20261102-002](../experiments/2026-11-02-sim-flight-scene-runtime.md)。

## 1. 实施范围与真实调用链

新显式入口ros_ws/sim_flight_scene_run.py只观察本机PX4 SITL，不发送heartbeat、模式、arming、manual或参数写。
同一FGFDMExec、原LSZH地面IC/原传感器、4ms真实Run和原整数时间生产语义保持。
simulation/flight_scene/adapt.py只在新.runtime/ros源副本扩展有界宿主/收据，旧2500步宿主与时间函数保持。
新profile和公共v2沿SW-03A固定合同；0—40秒原源与SceneFrame/clock/state保留，采样不改戳或清零。

链路为：本仓隔离宿主 → 原PX4 HIL/零执行器 → 同FDM源样本 → FlightRegistration固定ENU →
FlightTransactions → /uav/flight/scene/step原生暂停Gazebo → 实际Ray/Camera与ROS ACK →
事务成功后单一clock/state → 原state_adapter唯一TF → SceneStream同tick配对 → placeholder → M1 → 公开查询/回放。
ACK/mailbox仍只有基础设施身份/时间/完成状态，不带原始点云、图像、占据或训练监督旁路。
运行图只在新显式入口装配，旧v1/default入口不选择UFM_FLIGHT_SCENE；生成25消息定义保持。

共享纯函数改动限于物理字段校验、白名单原生正文解析和事务校验策略；原封套验证、参数/检查点/默认上限仍严格。
不将新查询改成旧检查点、借旧schema解码后改summary；新查询与物理记录分别使用sim_flight_scene_*独立封套。
v2原生插件按显式编译策略使用具名ground注册/几何、10000步、7525起采样及三个独立端点。
应用前失败返回ROS服务错误而非无版本响应；应用后失败保留真实applied帧及部分收据。

## 2. 长窗准备与提交边界

准备检查点固定125/250/500/1000/1500/2000/2500/5000/7000/7250/7500步。
首125步7参数，11组各13原生topic，合计150次只读查询；owner/PID/start_ticks/socket前后核对、
200ms单查询/400ms组界、16MiB查询文件界不放宽。各topic原时间/质量缺失/设备关联语义复用已验纯解析。
7000/7250步即28/29秒两个末准备点必须实际满足原静稳、身份/健康/姿态/land/未armed门，
7500步即30秒再次核对；姿态sample须递增，28—30秒间至少两个真实零执行器包。
逐步物理收据保持原零控制/未armed、原始时间/四属性读回/同FDM Run；首包后不能断流继续。

仅step>7500且step%25=0采样；准备期禁止raw/ACK/Bundle/占据/快照，公开地图查询为unavailable/revision0。
采样期每步先实际推进/安装帧，等待本step双ACK后才发布公共clock/state；失败tick实际已推进的FDM/Gazebo保留原记录，
不把它写成公共成功，也不回滚或改戳。迟到请求不能复活失败事务，恢复仅新run/clock/空地图。
默认新入口的状态发布者名沿已有组合使用/sim_motion_host，state_adapter仍唯一odom→base_link动态TF，
没有第二PX4估计状态或Gazebo clock进入业务域；Gazebo clock只进diagnostics。

## 3. 预算与恢复

每条物理记录≤16KiB、物理流≤64MiB、时间来源收据≤12288条；HIL wire事件≤49152，原wire载荷≤64MiB。
每订阅流≤12288条、订阅实际序列化总字节≤128MiB；run全部产物≤512MiB，每0.5秒检查。
启动≤60秒、首采样≤3秒、后续事务≤1秒、case≤240秒墙钟；单产品构建≤180秒且只在.runtime/ros。
构建产品复用要求显式给路径，消费build-sources.json逐文本核对所有构建输入，漂移即拒绝，无Hash。
构建不是运行准入，启动时仍检查端口/PX4既有进程、真实准备与数据门；原run产物均独占目录创建。
失败停止next/锁定run并传播最后提交时刻terminal，History与明确时间的地图stale查询分开验。
恢复显式选旧v1入口或新run，不修改历史失败、研究代码、原数据/环境或checkpoint；关机不是着陆证明。

## 4. 验证结果

独立预期和485份源文本在新production目录不存在时保存于
[freeze.json](../.runtime/runs/flight-sw03b-oracle-20261102/freeze.json)，不使用被测实现生成答案。
12项新增定向通过，包括10000步合成物理连续性、独立ENU/FLU算例、准备门、
真实C++时间界、原封套拒绝和分段文件读取；最终全仓1130/1130通过。

首个完整正常run：[142707281102](../.runtime/runs/flight-scene-normal-20261102T142707281102/manifest.json)，
[独立审计/回放](../.runtime/runs/flight-scene-audit-20261102T143055607849/report.json)通过。
10000 Run/40秒、150查询，28/29/30秒准备均true；主实例5/gyro及accel槽2，
selector消费时间仍null/exact_source_message_verified=false，不把顺序观察当同消息因果。
10000 HIL_SENSOR/39 HIL_GPS/9572真实零执行器，10039源收据逐包核对；发送端仅HIL，无控制消息。
10001公共clock/有效状态/TF、100组raw/Bundle/占据/快照、200 ACK及107公开查询/回放通过，
181000 Radar点/Doppler/同tick Context与唯一TF核对；地面采样期IR变化0像素，不声称飞行位移。
run墙钟129.10012035秒<240秒；原始源/状态从0留存，未将30.1秒改成100ms。

首两次实际失败保留：首例125步查询封套重复argv，第2例541步时读取了写入中途半行；
分别修复新封套字段投影和有界JSONL完整行组装，未放宽字节/时间/就绪界，未改原文。
旧收据工具默认值兼容问题经原11项引擎测试复现/修复通过；第一次全仓1128项有1错误，原日志保留。
这些失败不是PX4初始化/真实研究质量失败，不允许用已有10秒结果代替新长窗验收。
第3例7000步/112查询后因监督器全目录盘点干扰查询期限停止；原8.94954ms查询与失败保存，
改为wire/查询实际写入计数、外部日志定期盘点，未放宽期限或预算，后续验证另记。

原生完整正常[143554316028](../.runtime/runs/flight-scene-normal-20261102T143554316028/manifest.json)及
[六图/viewport](../.runtime/runs/flight-scene-normal-20261102T143554316028/figure-validation.json)通过，
[独立审计/进程回放](../.runtime/runs/flight-scene-audit-20261102T144418265689/report.json)通过。
10000 Run/100采样、9574真实零执行器；IR实际启用/接收计数/原戳和渲染目标逐项核，
Radar/IR/地图同图来自本次同run。先前原生IR关闭失败143110573154保留，未以“No Image”验收。
修复只在新入口设置UFM_FLIGHT_SCENE_VIEW，旧窗口默认行为保持；原生图片不代表飞行或研究质量。

四个冻结故障及独立审计均通过，具体目录/结果见实验第3节。
中途缺IR回执：7550 Run/公共停7549/1组地图；首采样缺IR回执：7525 Run/公共停7524/0地图。
禁止采样注入：7500步停止、无raw/ACK/Bundle/占据/快照；原准备ready=true照实保留，未伪造真实未就绪。
断连：126条记录/125 Run/公共125步，末条未Run/peer_closed；所有例的清理/端口通过。

[最终收尾报告](../.runtime/runs/flight-scene-final-20261102T150033101394/report.json)passed=true：
5核心同533份源文本、3旧实际兼容、旧25定义保持；记录的708自有PID无残留，清理/端口均通过。
核心墙钟合计410.575586201秒；登记case/尝试/产品产物1759078395字节，小于5GiB总预算。
原生正常case最终全部产物397467276字节<512MiB、订阅wire94268817字节<128MiB；
高频流10001条<12288，单case138.493777284秒<240秒；这些是软件预算证据，不是RSS或正式PERF。
533份已接受源码当前逐文本保持，之后仅新增tests兼容包装/收尾工具；8份原有源码有明确范围改动，
不再声称整个旧源码逐文本不变。25定义、v1合同/default入口、配置及第三方原源保持并有真实兼容。
首次旧v1兼容误用历史构建目录.runtime/sim-motion-build的偏差已保留，后经测试包装在.runtime/ros重验通过；
此偏差与前述4次工程失败、初次轻量回归1错误均在实验完整披露，不能被后续通过抹去。

## 5. 未验证能力

严格当前执行器周期绑定、非零执行器/属性因果、模式切换/arming、离地和受控飞行仍未验收，
binding_status=unverified/control_gate_accepted=false；本任务不进入SW-04。
本次9574个零执行器包的actuator−HIL原时间差均为−4000us，保留原戳；下一步必须先交付严格绑定
及非零控制因果的具体准入方案/独立预期，不能把该时差、零包、准备通过或收到ACK当作同周期控制许可。
场景是地面无控制观察，不要求或声称前后画面发生飞行位移；原生图验可见性、真实传感器目标与History状态。
placeholder仍只是Radar点体素化，IR/Doppler不参与占据计算；同tick几何/回放不代表研究模型质量。
真实设备、DEM公共服务/地理注册/占据融合、正式PERF及完整阶段门槛继续独立跟踪，research保持fail-closed。

## 6. 文件与验证复现

| 文件 | 作用与修改原因 |
| --- | --- |
| simulation/flight_scene/{adapt.py,time_grid.h,policy.h,time_probe.cpp} | 新隔离源副本的10000步宿主、发送前原1ns时间校验、原生v2几何/采样策略及真实C++时间边界探针 |
| simulation/ufm_simulation/flight_scene.py | 独立ENU/FLU转换、v2事务、逐步物理连续性/零输出/准备门 |
| simulation/ufm_simulation/{flight_initialization_contract.py,flight_initialization_selector.py,scene_motion.py} | 提取纯字段/正文校验和显式事务校验策略，旧封套/默认上限保持；新链不重写旧查询或时间 |
| simulation/gazebo_scene_step.cpp、sensors/scene_motion_capture.h | 以UFM_FLIGHT_SCENE显式选择v2端点/注册/采样，应用前错误用服务错误，默认v1策略保持 |
| ros_ws/sim_flight_scene_{build,run,queries,delivery}.py | 独立构建/运行薄装配、owned只读查询和原生/公开地图交接；不复制感知或地图算法 |
| ros_ws/native_scene_rviz.cpp | 只在新flight窗口显式启用IR与计数/原戳收据，修复实际No Image失败；旧默认行为保持 |
| tests/fixtures/sim_flight_scene_runtime_expectations.json | 先行独立时间/采样/检查点/故障预期 |
| tests/sim_flight_scene_{freeze,checks,stage,legacy,finalize}.py | 先行源保护、原始wire/正文/图像独立审计、进程回放、隔离目录旧入口兼容与最终预算/PID核对 |
| tests/test_sim_flight_scene_runtime.py | 12项新离线/真实C++边界与已复现工程错误回归 |
| tests/check_sim_motion_live.py、tests/motion_delivery_checks.py | 显式收据容量/目录/codec参数与原时间采样表；默认旧容量/codec和时间规则保持 |
| 本文、experiments/2026-11-02-sim-flight-scene-runtime.md | 中文交付/所有失败与实际结果、范围和恢复 |
| PROJECT_STATUS.md、docs/{DATA_FORMAT,SENSOR_INTERFACE,COORDINATE_SYSTEM,SYSTEM_ARCHITECTURE,DECISION_LOG,DEVELOPMENT_PLAN,EXPERIMENT_LOG}.md | 项目状态、数据/时间/坐标/端点与必要索引 |

固定环境下先`--build-only`，后可显式`--products`复用相同源产品，默认正常run包含原生窗口；
`--no-native`只关闭窗口，不省略真实Gazebo采样。`--case`为normal/disconnect/missing-ir-ack/
first-missing-ir-ack/not-ready，均独立run且默认命令关闭，不提供控制客户端。
`tests/sim_flight_scene_stage.py <run目录>...`仅重读指定已完成run并执行公开回放，不推进新物理。
详细命令和日志见实验，已有接受run不能直接用当前阶段脚本覆盖旧产物。
共34个交付文件，18新增、16修改；无消息定义、研究仓、模型/数据/checkpoint或历史产物修改。
