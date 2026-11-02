# UAV-FusionMap 项目状态

更新日期：2026-11-02；维护角色：Technical Lead。
计划交付：2027年3月；阶段日期与退出条件见[开发计划](docs/DEVELOPMENT_PLAN.md)。
原状态全文已保存在[历史快照](docs/PROJECT_HISTORY_20261027.md)，历史实验继续保留原位。

## 当前完成

SIM-FLIGHT-SW-03A：已完成（公共flight v2离线合同/严格codec范围），见
[合同/22文件清单](docs/SIM_FLIGHT_SW03A_CONTRACT_20261102.md)、
[EXP-20261102-001](experiments/2026-11-02-sim-flight-v2-contract.md)。先保存独立输入/边界/拒绝预期与245组v2字节、20组旧字节，
再实现ufm_flight_contract/固定观察profile/独立端点名称类型合同，复用真实Scene生成类型、显式protocol_version=2。
冻结ground锚点/具名ENU、4ms/10000步与7525..10000共100采样点；28项新定向、真实genpy往返/双向拒绝、
旧25定义/59文件保护通过。本轮基线1090项、最终全仓1118项均重跑通过。
无版本的未应用失败响应在v2拒绝，未来应用前失败用服务错误、不伪造applied_frame；旧v1保持。
未实现/启动长窗、插件端点/节点或控制；binding仍unverified、control_gate_accepted=false，下一项SW-03B另验。
本轮按用户授权先提交既有基线e51c752，再独立提交SW-03A；不推送或改变ENV-03验收状态。

报告更新（2026-10-30）：按用户确认完成真实高程独立读取/查询/RViz显示、显式分散场景与参数化Radar，
补齐同次动力学运行的场景/点云/IR前后对照。报告随后按四个工作方向整体整编，
最新[Word/PDF](experiments/report_assets/progress-map-clarified-20261030/README.md)16页、9图、2张表，无三级标题；
按用户指出的问题，修正将运动观测、占位地图接口记录和独立合成地图图像混称为“已有对应”的表述，
地图与同场景障碍物的空间对应验证列入后续；[修订核对](experiments/2026-10-30-report-map-claim-correction.md)。
[整编记录](experiments/2026-10-30-report-integrated-revision.md)包含正文、嵌图与排版核对。
[此前17页版](experiments/report_assets/progress-update-20261030/README.md)与
[15页版](experiments/report_assets/progress-20261030/README.md)保留。
工具与入口见[交付说明](docs/REPORT_IMPROVEMENTS_20261030.md)，
1090项全仓回归及实际高程/运动/旧默认兼容见[实验](experiments/2026-10-30-report-terrain-radar-improvements.md)。

| 范围 | 状态 | 已验证能力与证据 |
| --- | --- | --- |
| REPORT-UPDATE-SW-01 | 已完成（真实高程独立预览/参数化演示与报告） | Rasterio/pyproj隔离安装，Copernicus四川201×201源高程/49查询对照及RViz地表通过；180×140m/30障碍物、实际每帧161～256回波、10对/14查询/公开回放与旧入口通过，两次原始Radar/IR字节可复现；新增7项/全仓1090项及17页报告交付。真实地形公共服务/场景注册/融合与飞行控制后续单列 |
| 工程基线与仿真 | 已完成（所列子范围） | SIM-00A/B、SIM-01A/B/C、SIM-SPEED-01及[SIM-01D持续性](experiments/2026-10-05-sim01d-continuity.md)；不代表完整Phase 1退出 |
| Phase 2在线/训练软件图 | 已完成（fixture子范围） | [双图整合](experiments/2026-10-26-phase2-sensor-integration.md)、[Radar值级传递](experiments/2026-10-16-iface-radar-height.md)、[IR值级传递](experiments/2026-10-05-sens-ir-value-transport.md)、[训练体素覆盖](experiments/2026-10-20-sens-train-voxel-coverage.md)与[边界](experiments/2026-10-20-sens-train-dda-boundaries.md) |
| 可选仿真IMU | 已完成（虚拟源子范围） | [可选ROS旁路](experiments/2026-10-26-phase2-imu-optional-ros.md)、[PX4/JSBSim短测](experiments/2026-10-26-phase2-imu-live-px4-jsbsim.md)、[独立比力语义核对](experiments/2026-10-26-phase2-imu-physics-semantics.md)；非实物标定或同run内部真值逐帧对照 |
| 状态兼容镜像 | 已完成（fixture子范围） | [T-14 Odometry/唯一TF](experiments/2026-10-14-t14-odom-tf.md)；AircraftState仍为状态权威 |
| 基础Local Map | 已完成（软件子范围） | [单点查询](experiments/2026-10-14-local-map-query-ros.md)与[滚动网格](experiments/2026-10-14-local-map-rolling.md)；M1保持latest覆盖，M2合成累计单列；Scene Map和DEM未验收 |
| 感知失效传递 | 已完成（软件子范围） | [disabled/research拒绝链路](experiments/2026-10-27-perception-mode-ros-fail-closed.md)；research尚无可用forward |
| OPT-01审查修复 | 已完成（软件范围） | [修复、配置收敛及回归记录](experiments/2026-10-27-review-repairs.md)；423项轻量测试及独立/旧入口/异步/失效/IMU/滚动/训练ROS回归通过 |
| P3-SW-01/02/03 | 已完成（软件范围） | 统一感知入口/输出契约、可选有界CPU执行及独立ROS坏输出/忙碌/超时/恢复通过；[交接记录](experiments/2026-10-27-p3-m1-app-handoff.md) |
| M1-SW-02 / APP-SW-01 | 已完成（软件范围） | 三组公开占据收据回放逐值一致；应用五类查询及独立CLI/缺失服务通过；全仓469项回归，详见上述交接记录 |
| M2-DESIGN-01 | 已完成（方案交付） | [概率更新与软件试制方案](docs/M2_SOFTWARE_TRIAL_PLAN_20261027.md)及[设计审查](experiments/2026-10-27-m2-design-review.md)；用户后续已确认合成数据软件试制，正式M1/M2门槛保持 |
| M2-SW-01 | 已完成（软件范围） | [合成证据/显式参数/独立分数oracle](experiments/2026-10-27-m2-fixture-oracle.md)，9场景/31消息和10项定向、479项全仓回归通过；未执行地图累计 |
| M2-SW-02 | 已完成（固定合成网格软件范围） | [候选累计与公开查询](experiments/2026-10-27-m2-fixed-map.md)，9场景/31观测对冻结oracle一致，12项定向及491项全仓回归通过；未运行滚动M2或ROS候选图 |
| M2-SW-03 | 已完成（离线合成软件范围） | [时序/TTL与滚动集成](experiments/2026-10-27-m2-rolling-time.md)，3组运动场景/15观测及40条限额序列通过，M2共37项定向、全仓506项通过；实际ROS证据见SW-04 |
| M2-SW-04 | 已完成（合成软件交接） | [独立ROS/回放/应用交接](experiments/2026-10-27-m2-ros-handoff.md)：15观测/9快照/14查询、五类状态及4条坏输入拒绝，公开收据回放一致；旧固定/滚动/placeholder ROS通过，全仓515项通过，清理通过 |
| M3-DESIGN-01 | 已完成（方案交付） | [来源/单位/缺失传播与合成区间方案](docs/M3_SOFTWARE_TRIAL_PLAN_20261027.md)，沿真实链审计9项事实、核对3组分数算例，既有质量相关17项定向通过；[审查记录](experiments/2026-10-27-m3-design-review.md)。未实现M3候选或运行新ROS |
| M3-SW-01 | 已完成（输入/预期软件范围） | [显式区间合同、配置与独立oracle](experiments/2026-10-27-m3-fixture-oracle.md)：10场景/43输入实际消息序列化往返通过，19项定向及534项全仓通过；未执行M3累计或新ROS图 |
| M3-SW-02 | 已完成（固定合成网格软件范围） | [固定区间累计与冻结预期对账](experiments/2026-10-27-m3-fixed-map.md)：10场景/43输入一致、名义值逐值等于M2，12项新增定向、M3共31项及全仓546项通过；受影响M2 ROS/回放/清理通过，M3滚动/ROS仍待后续 |
| M3-SW-03 | 已完成（离线合成滚动范围） | [区间滚动/TTL与有界状态](experiments/2026-10-27-m3-rolling-time.md)：96帧/257查询/4探针及五类状态通过，名义值逐值等于M2；新增15项、M3共46项、全仓561项通过；M3实际ROS/应用交接待SW-04 |
| M3-SW-04 | 已完成（合成软件交接） | [独立ROS/回放/应用质量检查](experiments/2026-10-27-m3-ros-handoff.md)：19观测/13快照/19查询、155项运行检查、五类状态与4条坏输入拒绝通过；公开回放、旧M1/M2/placeholder及清理通过，全仓570项通过 |
| M4-DESIGN-01 | 已完成（具体设计） | [Scene Map/有界子地图方案](docs/M4_SOFTWARE_TRIAL_PLAN_20261027.md)及[审查记录](experiments/2026-10-27-m4-design-review.md)：9项审计、32项既有定向通过；明确唯一所有权、具名非零map←odom注册、联合原子提交和定位reset限制，未实现M4或启动新ROS |
| M4-SW-01 | 已完成（输入/预期软件范围） | [注册/输入合同与独立生命周期预期](experiments/2026-10-28-m4-fixture-contract.md)：8场景/41输入/52查询预期已保存，输入与预期载荷实际序列化通过；24项定向、全仓594项通过；未运行Scene候选或M4 ROS |
| M4-SW-02 | 已完成（离线合成候选范围） | [有界Scene候选与冻结预期对账](experiments/2026-10-28-m4-scene-candidate.md)：8场景/41输入/52查询、目录所有权/FIFO与实际消息序列化通过；新增15项、M4共39项/全仓609项通过，未接入工厂或ROS |
| M4-SW-03 | 已完成（离线合成组合范围） | [时序/资源与联合原子性](experiments/2026-10-28-m4-time-resources.md)：140帧/323查询、4故障点及1域隔离探针与保存预期通过，120帧K=1/N=2/H=3状态/索引/副本计数有界；新增13项/M4共52项/全仓622项通过，非RSS或M4 ROS验收 |
| M4-SW-04 | 已完成（合成软件交接） | [显式ROS/回放/独立应用map查询](experiments/2026-10-28-m4-ros-handoff.md)：15观测/9快照/20查询、174项运行检查及4条拒绝通过；五类状态/历史质量、公开回放、旧M1/M2/M3/placeholder与清理通过，新增7项/全仓629项通过；不关闭正式M4 |
| APP-VIS-01 | 已完成（地图工作台软件子范围） | 用户要求10-30周五前交付原生RViz；[10-28交付记录](experiments/2026-10-28-rviz-report-delivery.md)与[报告图片/图注](experiments/report_assets/rviz-20261028/README.md)。默认软件渲染的三维/俯视/图层/五类查询、公开快照回放、实际服务/时钟失效与像素检查通过；旧Radar/IR占位链live收到32帧，新增9项/全仓638项通过；系统显卡路径有未解释启动异常，非真实模型/飞行验收；场景与传感器目标见SENS-VIS-01 |
| SENS-VIS-01 | 已完成（独立功能级场景） | 用户澄清需要场景与Radar点云、IR；[Gazebo + 标准RViz入口](docs/SENSOR_SCENE_VISUALIZATION.md)、[运行证据](experiments/2026-10-28-sensor-scene-visualization.md)和[报告素材](experiments/report_assets/sensor-scene-20261028/README.md)。1790回波/594占据cell、冷暖投影及热箱位移联动、无训练图、窗口像素与正常清理通过；既有state_adapter唯一TF职责保持，旧placeholder ROS及全仓649项通过；飞机固定，未接PX4联动或真实传感器物理模型 |
| M5-DESIGN-01 | 已完成（具体设计） | [TerrainPrior/DEM准入与兼容方案](docs/M5_TERRAIN_PRIOR_DESIGN_20261028.md)、[审查记录](experiments/2026-10-28-m5-design-review.md)：10条源码事实、4项现有边界探针/6个数字算例和40项既有定向通过；交付基准/no-data/时效/高度质量、独立地形层、原子版本、公共协议闸门及16组验收预期。未实现DEM、未改公共接口或启动ROS |
| M5-SW-01 | 已完成（私有离线输入/预期） | [冻结合同](docs/M5_SW01_CONTRACT_20261028.md)、[实验记录](experiments/2026-10-28-m5-fixture-contract.md)：45组JSON输入（4接收/41拒绝）、5个请求语法与16组/7事件独立预期保存，新增21项/全仓670项通过；未实现地形候选/安装查询、未接ROS或占据融合，m5_fixture选型仍拒绝 |
| M5-SW-02 | 已完成（离线合成地形候选） | [候选/API说明](docs/M5_SW02_TERRAIN_CANDIDATE_20261028.md)、[运行记录](experiments/2026-10-28-m5-terrain-candidate.md)：4样本/5边界/7事件/45输入共135项保存预期一致；整版替换、缺失质量、幂等/冲突/原子重试及占据隔离通过，新增24项/M5共45项/全仓694项通过；未接真实DEM、公共ROS或占据融合，后续完整时序/资源组合见SW-03 |
| M5-SW-03 | 已完成（私有离线合成软件组合） | [时序/资源说明](docs/M5_SW03_TIME_RESOURCES_20261028.md)、[运行记录](experiments/2026-10-28-m5-time-resources.md)：4组84事件/44查询/19拒绝，64版大载荷、五处故障重试及占据隔离通过；保存输入/结果重放逐值一致，提前拒绝超长文本；新增10项/M5共55项/全仓704项通过。保留项与临时载荷分开核对，非RSS/正式性能；真实DEM/公共地形交接/占据融合未开展 |
| M5-IFACE-DESIGN-01 | 已完成（具体提案） | [公共地形接口方案](docs/M5_IFACE_DESIGN_20261028.md)、[审查记录](experiments/2026-10-28-m5-interface-design.md)：14项源码事实/实际边界探针及74项既有定向通过；明确独立4消息/1服务、版本/实例/时钟/质量、记录与兼容恢复、16组未来验收。仅设计，未生成消息或实施新ROS/客户端；公共运行字段未变 |
| M5-IFACE-SW-01 | 已完成（消息/离线合同） | [公共合同](docs/M5_IFACE_SW01_CONTRACT_20261028.md)、[验证记录](experiments/2026-10-28-m5-interface-contract.md)：独立4.msg/1.srv已生成，公开逻辑对象/严格codec、dataset及三文件recording校验已实现；独立字节与真实genpy往返、29项新增定向及733项全仓轻量回归通过。旧类型与入口保持；无Provider/实际地形服务/客户端/RViz地形或公共回放执行 |
| M5-IFACE-SW-02 | 已完成（合成Provider/独立ROS） | [Provider/装配说明](docs/M5_IFACE_SW02_PROVIDER_20261028.md)、[实际记录](experiments/2026-10-28-m5-provider-ros.md)：默认关闭、clock来源/超时/reset、evaluation/版本/pin/状态及单启动安装已实现；实际ROS28查询/15状态/38检查、新run恢复与旧占据兼容/清理通过。新增20项，相关104项/全仓753项通过；无客户端/公共执行回放/RViz地形，非真实DEM或完整M5验收 |
| M5-IFACE-SW-03 | 已完成（公共合成软件交付） | [客户端/录制回放/RViz说明](docs/M5_IFACE_SW03_DELIVERY_20261029.md)、[实际记录](experiments/2026-10-29-m5-terrain-delivery.md)：单worker期限/迟到丢弃、状态存活/整组pin、有界录制与真实执行回放、独立live/recorded显示完成；实际23事件/8查询收据逐值重放、12项客户端与四图像素、旧Gazebo/Radar/IR/占据/RViz兼容/清理通过。新增21项，定向70项/全仓774项通过；v1无法表达的失败明确incomplete，非真实DEM/占据融合或完整M5/Phase 4 |
| P5-DESIGN-01 | 已完成（具体设计） | [组合场景/需求矩阵](docs/PHASE5_SOFTWARE_COMBINATION_DESIGN_20261029.md)、[审查记录](experiments/2026-10-29-phase5-combination-design.md)：15项源码事实、三类配置、九组待实施场景及REQ-01—14矩阵、SW-01—03分工；既有76项定向通过。只改文档，未实现或运行新组合，未重跑全仓；真实质量/融合/正式Phase 4/5门槛保持 |
| P5-SW-01 | 已完成（输入/预期/线格式） | [输入合同](docs/P5_SW01_INPUT_CONTRACT_20261029.md)、[验证记录](experiments/2026-10-29-phase5-input-contract.md)：九组37子例/253事件、95检查点/228项独立预期，143组采样/12逆观测/23公共样例共742次真实消息往返；新增31项定向及全仓805项通过。仅离线合同，未运行新组合ROS/Provider/地图累计或原生图验收 |
| P5-SW-02 | 已完成（A/B合成ROS组合） | [实际装配/回放](docs/P5_SW02_ROS_COMBINATION_20261029.md)、[实验记录](experiments/2026-10-29-phase5-ros-combination.md)：33/33独立Master子例、244事件/86检查点/216项独立比较；148占据/143快照/14查询逐值地图回放，S08正常/不完整/篡改地形记录按预期通过。旧默认入口与清理通过，新增8项、P5定向39项/全仓813项通过；S09/C与正式阶段门槛保持 |
| P5-SW-03 | 已完成（原生图与软件全矩阵交接） | [交付说明](docs/P5_SW03_NATIVE_DELIVERY_20261029.md)、[实际记录](experiments/2026-10-29-phase5-native-delivery.md)：S09/C四例、图错误/正常清理/哨兵保留、新run空地图与旧pin拒绝、原生Gazebo/标准RViz及独立地形四图通过；复核既有A/B收据后合计37例/253事件/95检查点/228项比较，A/B本轮未重跑。新增6项、P5定向45项/全仓819项通过，宿主36个受管命令无残留；仅关闭冻结软件工作包，完整阶段门槛保持 |
| DELIVERY-SW-01 | 已完成（仓内交付整理） | [统一交付清单](docs/SOFTWARE_DELIVERY_20261029.md)、[含八图报告](docs/REPORT_20261029.md)、[核验记录](experiments/2026-10-29-software-delivery-motion-design.md)：版本/dirty范围、启动/配置/查询/回放与未关闭门槛归并，57项核验/64项既有定向及22事件地形离线回放通过；未重跑全仓或ROS，未对外发布/归档 |
| SIM-MOTION-DESIGN-01 | 已完成（具体设计） | [JSBSim真值/受控Gazebo运动方案](docs/SIM_SCENE_MOTION_DESIGN_20261029.md)、上述核验记录：16项源码事实，单时钟/逐帧ACK、固定注册、杆臂速度及12组待实施验收、SW-01—03分工；未生成2.msg/1.srv或实现运行器，当前飞机仍固定 |
| SIM-MOTION-SW-01 | 已完成（离线输入/协议软件范围） | [合同说明](docs/SIM_MOTION_SW01_CONTRACT_20261029.md)、[实际记录](experiments/2026-10-29-sim-motion-contract.md)：独立2.msg/1.srv、严格嵌套codec/字节扫描、有界profile/FDM输入已实现；先冻结六组坐标/六时间点与20组独立字节，真实genpy往返、26项新增/全仓845项通过，17份旧定义不变。无推进状态机、FDM转换器/节点或飞行联动，下一项SW-02 |
| SIM-MOTION-SW-02 | 已完成（真实引擎/采样软件闸门） | [交接说明](docs/SIM_MOTION_SW02_ENGINE_20261029.md)、[实测/失败记录](experiments/2026-10-29-sim-motion-engine.md)：同一FDM、固定ENU转换、暂停Gazebo与实际Ray/Camera、单clock/state/TF、terminal已实现；250步/10对/20 ACK、运行期丢IR回执停于996ms、13,217回波Doppler及67,933 IR像素变化通过；37项定向/全仓856项、旧估计/静态原生入口回归通过。首采样故障时PX4启动中断255的两次失败保留；新模式端到端地图/原生窗口待SW-03，非受控飞行 |
| SIM-MOTION-SW-03 | 已完成（运动感知地图/原生窗口软件交接） | [交接说明](docs/SIM_MOTION_SW03_DELIVERY_20261029.md)、[实验记录](experiments/2026-10-29-sim-motion-delivery.md)：同tick精确位姿、10组Bundle/占据/快照、14条公开查询、独立回放、首采样/运行期ACK故障、第二clock拒绝、新run空地图恢复及原生Gazebo/RViz前后/History窗口通过；运动定向43/43、全仓862/862，旧estimated/静态入口回归通过。仅关闭单profile软件范围，不代表受控飞行、真实模型质量、DEM/资源或正式阶段退出 |
| SIM-MOTION-SW-04-DESIGN | 已完成（多场景具体设计） | [具体方案](docs/SIM_MOTION_SW04_MULTISCENE_DESIGN_20261029.md)、[核验记录](experiments/2026-10-29-sim-motion-multiscene-design.md)：12项源码事实、9核心/3兼容用例、独立几何/空图/TTL/故障预期及资源上界；54项既有定向、20组真实线格式/17旧定义、13只读探针通过。仅文档，未实现新清单或运行多场景，未重跑全仓；下一项SW-04A |
| SIM-MOTION-SW-04A | 已完成（多场景输入/预期离线合同） | [合同/文件清单](docs/SIM_MOTION_SW04A_CONTRACT_20261029.md)、[实验记录](experiments/2026-10-29-sim-motion-multiscene-contract.md)：独立9例清单/有界校验、7几何模板、IC/射线/空图/TTL/故障预期完成；77组真实场景协议字节、36组旧公共消息往返、18合成源转换通过，25份旧定义/7配置入口保持。新增23项、运动66/66及全仓885/885通过；未启新FDM/ROS/Gazebo场景，下一项SW-04B |
| SIM-MOTION-SW-04B | 已完成（显式装配/真实定向机制） | [交付/文件清单](docs/SIM_MOTION_SW04B_ENGINE_20261029.md)、[实验记录](experiments/2026-10-29-sim-motion-multiscene-engine.md)：S06真实空域10组/13查询、S07两次暂停几何切换/5空帧/返回/16查询、S08第125步Radar ACK故障clock496ms/4组，以及旧默认入口实际通过；独立原始FDM/逐射线/公开回放与清理通过。新增11项、运动77/77及全仓896/896；保留矩阵/visual/48边界假设失败，后续固定零豁免且不增物理容差。完整9核心/3兼容与原生交接留SW-04C |
| SIM-MOTION-SW-04C | 已完成（同源码多场景软件交接） | [交付/文件清单](docs/SIM_MOTION_SW04C_DELIVERY_20261029.md)、[实验记录](experiments/2026-10-29-sim-motion-multiscene-delivery.md)：423份冻结源码上9核心/3兼容通过；84组业务/121查询、75帧逐射线零豁免、独立回放、S08→S09实际旧身份拒绝及14阶段总图/12 viewport。四次失败保留；修正独立旋转估计、S04生成IC冲突、S05合法空帧断言及新视图IR范围。新增7项、运动84/84、全仓903/903；全部尝试364自有PID/端口清理通过。仅1秒无控制软件范围，非完整阶段退出 |
| SIM-FLIGHT-DESIGN-01 | 已完成（具体方案/只读审查） | [受控短窗方案](docs/SIM_FLIGHT_DESIGN_20261029.md)、[实验记录](experiments/2026-10-29-sim-flight-design.md)：19项源码事实、15项独立核验及84项既有运动定向/真实消息往返通过；明确执行器时序/属性收据、AGL/预热、独立v2、新有界profile、命令准入/停止及SW-01—04。仅文档，未发控制或启动新仿真；旧25份定义/423份生产源码保持，未重跑全仓 |
| SIM-FLIGHT-SW-01 | 已完成（私有离线合同范围） | [合同/文件清单](docs/SIM_FLIGHT_SW01_CONTRACT_20261030.md)、[实验记录](experiments/2026-10-30-sim-flight-contract.md)：具名ground IC/执行器收据、严格有界JSON/JSONL与先保存独立预期完成；8组私有字节往返、3映射探针、100个未来采样时刻、两条合成记录通过。新增25项、旧运动84项/全仓928项通过；旧25份定义/7入口/423份源码保持。绑定仍unverified且控制门固定false，无新运行或控制 |
| SIM-FLIGHT-SW-02 | 已完成（隔离诊断/短窗失效子范围） | [交付/十文件清单](docs/SIM_FLIGHT_SW02_DIAGNOSTICS_20261030.md)、[实验记录](experiments/2026-10-30-sim-flight-diagnostics.md)：同439份源码上正常250条/250次Run/1s、断连接126条/125次Run/停.5s及真实wire/IC核对通过；新增7项、飞行32项/旧运动84项/全仓935项通过。两例执行器0包、bootstrap_not_ready，正向属性施加与时间绑定未验证；无命令/新ROS/Gazebo/v2/长窗，控制门仍false |
| SIM-FLIGHT-DIAG-DESIGN-02 | 已完成（只读归因/补证设计） | [具体方案](docs/SIM_FLIGHT_DIAG_DESIGN_20261030.md)、[实验记录](experiments/2026-10-30-sim-flight-readiness-design.md)：32份源文本/30项源码核验、两组376个旧HIL_SENSOR离线解码及32项既有飞行定向通过。GPS非姿态初始化无条件前置；首瞬时输入范围样本428ms不代表EKF就绪。明确SW-02B本run 9类uORB/3参数、21次有界只读快照；本轮未实现/查询/启新运行，439份源码保持，未重跑全仓 |
| SIM-FLIGHT-DIAG-DESIGN-03 | 已完成（空实例具体设计） | [三态/显式补证方案](docs/SIM_FLIGHT_DIAG_DESIGN03_20261030.md)、[实验记录](experiments/2026-10-30-sim-flight-empty-instance-design.md)：九份源文本/16项核验、旧原文/严格拒绝与49项既有飞行测试通过；445源码保持。明确独立diagnostic事件、完整/未发布/无载荷三态、混合块/畸形停止、18组未来预期及SW-02C范围；只设计，无新分类器/模式运行，SW-02B原失败与控制门保持 |
| SIM-FLIGHT-DIAG-DESIGN-04 | 已完成（原生质量隔离具体设计） | [两字段条件隔离方案](docs/SIM_FLIGHT_DIAG_DESIGN04_20261030.md)、[实验记录](experiments/2026-10-30-sim-flight-native-quality-design.md)：九份源文本/20项核验、六实例12处nan及同载荷源位核对、16组独立掩码算例与69项既有定向通过；451源码保持。拟独立私有diagnostic v2/显式模式、质量不可用状态、20组未来验收；未实施或启新运行，旧两个合同/失败与控制门保持 |
| SIM-FLIGHT-SW-02D | 已完成（私有隔离软件/实际有界采集） | [交付/文件清单](docs/SIM_FLIGHT_SW02D_QUALITY_20261030.md)、[实验记录](experiments/2026-10-30-sim-flight-quality-collection.md)：先冻结20组预期/源基线，再实现两字段条件隔离、私有diagnostic.v2及显式模式；21次实际查询/事件与三参数、独立重读通过。六实例12处质量不可用明确记录；采集完整但正文/载荷不完整，已读flags样本tilt/yaw均未对齐、selected姿态缺失、执行器0包，控制门false。飞行92/运动84/全仓995项、旧实际入口/线格式及27自有PID清理通过；旧B/C失败保持 |

SIM-FLIGHT-INIT-DESIGN-01：已完成（具体设计），见[方案](docs/SIM_FLIGHT_INIT_DESIGN_20261030.md)与
[实验](experiments/2026-10-30-sim-flight-initialization-design.md)。24份源文本/32项核验、旧21条事件和250条wire重读、
92项既有飞行定向通过；设计时尚无新合同/宿主/准备运行。

SIM-FLIGHT-INIT-SW-01：已完成（私有离线软件），见[合同/八文件清单](docs/SIM_FLIGHT_INIT_SW01_CONTRACT_20261030.md)与
[实验](experiments/2026-10-30-sim-flight-initialization-contract.md)。先冻结独立预期，再实现新profile/step/query/事件/终态合同、
有界文件重读与四门合成判定；两组2500步/84查询和88次私有JSON往返、35项新增/飞行127/运动84/全仓1030项通过，
旧实际genpy/25定义/7入口与原458份源码保持。没有准备宿主/客户端或新运行，控制门false；下一项INIT-SW-02。

SIM-FLIGHT-INIT-SW-02：已完成（宿主/部分实际证据/故障兼容软件子范围），完整准备运行未通过；
见[十文件交付/失败说明](docs/SIM_FLIGHT_INIT_SW02_PREPARATION_20261030.md)、[实验](experiments/2026-10-30-sim-flight-initialization-preparation.md)。
新正常实际500步/2s、78全零执行器/属性读回、30查询原文/29合法事件，第30条selector未用槽位含nan严格停止；
未完成2500步/84查询，控制门false/绑定unverified。断连接/期限停止、飞行134/运动84/全仓1037项及旧实际入口/消息兼容通过；
原466源码保持，旧失败不回填。随后槽位具体设计见下项，原合同未放宽。

SIM-FLIGHT-INIT-SELECTOR-DESIGN-01：已完成（具体设计/只读审查），见
[方案](docs/SIM_FLIGHT_INIT_SELECTOR_DESIGN_20261030.md)、[实验](experiments/2026-10-30-sim-flight-initialization-selector-design.md)。
24项源事实、历史500步/78零包/29事件和8处nan重读、原严格拒绝及既有飞行134项通过，476份源码/配置保持。
拟独立selector观测合同、98项查询和前后IMU设备表关联；estimator高水位与四槽设备索引分开，
消费消息时间仍未知/不声称原子快照，选中槽有限/关联/原姿态门保持。仅文档，未实现新规则或启准备期；
下一项INIT-SELECTOR-SW-01仅独立离线合同/先行预期，SW-02才单独新运行装配。

SIM-FLIGHT-INIT-SELECTOR-SW-01：已完成（私有离线软件），见
[七文件/合同](docs/SIM_FLIGHT_INIT_SELECTOR_SW01_CONTRACT_20261030.md)、[实验](experiments/2026-10-30-sim-flight-initialization-selector-contract.md)。
先保存24组独立预期/源基线，再实现独立4种封套/严格codec、98计划、槽位隔离/设备关联和原四门纯判定。
两组合成2500步/98事件实际文件重读、101次新JSON往返、新28/飞行162/运动84/全仓1065项及旧真实genpy兼容通过。
原476源码/配置保持，消费消息时间未知/验证false、绑定unverified/控制false；未启daemon查询/准备或改旧失败。
下一项INIT-SELECTOR-SW-02单独98项实际装配、原wire/物理/关联与故障/兼容/清理交接。

SIM-FLIGHT-INIT-SELECTOR-SW-02：已完成（装配/部分实际证据/故障兼容软件子范围），完整准备未通过；
见[五新增/一修改及时间失败交接](docs/SIM_FLIGHT_INIT_SELECTOR_SW02_PREPARATION_20261030.md)、
[实验](experiments/2026-10-30-sim-flight-initialization-selector-preparation.md)。
唯一新正常1007 Run/4.028s、582真实全零执行器、59 raw/59合法查询，500/1000局部ready、primary4/IMU槽1；
1008条HIL原戳4027999us（网格4028000）Run前拒绝，旧桥接double截断来源已定位，未改戳或重跑。
断连/期限在126 raw/125 Run停止，新11/飞行173/运动84/全仓1076及旧实际/真实genpy兼容通过，控制false/绑定unverified。
下一项INIT-TIME-SW-01仅新增隔离的发送端整数时间适配与独立预期/验证，不再调整selector缺失表示或扩大窗口。

SIM-FLIGHT-INIT-TIME-SW-01：已完成（隔离时间生产修复/单profile 10s无控制准备软件范围），见
[十文件/交付](docs/SIM_FLIGHT_INIT_TIME_SW01_DELIVERY_20261030.md)、[实验](experiments/2026-10-30-sim-flight-initialization-time.md)。
先冻结16组预期，再新增纯C++/精确副本适配与显式入口；旧488源码/配置保持。
一次新正常2500 Run/10s、98 raw/合法事件、2500 HIL/9 GPS和2509源收据、2078真实零包；四门全true，2000/2500末检查点通过。
源double在原1ns内，旧失败位置实际发送4028000us，原4027999us失败不回填；主实例5/IMU槽2、绑定unverified/控制false。
C++5016包/新7/飞行180/运动84/全仓1083及实际故障/旧入口兼容通过。下一项SW-03A仅公共v2离线合同，不启长窗或控制。

SIM-01C/SIM-SPEED-01历史派生结果mtime偏差已于2026-09-17由用户明确接受并关闭；
原始事实与失败记录保留，处置见[ADR-P013及相关记录](docs/DECISION_LOG.md)。

## 计划

OPT-02第二轮修复已完成（软件与fixture ROS范围）：442项轻量回归及7组独立ROS短测，
证据见[EXP-20261027-003](experiments/2026-10-27-opt02-repair.md)。

按用户允许外部数据阻塞时提前进入下一阶段的要求，新增
[跨阶段软件推进计划](docs/STAGE_ADVANCE_PLAN_20261027.md)：
P3-SW-01/02/03、M1-SW-02与APP-SW-01已完成本批软件范围，
证据见[EXP-20261027-005](experiments/2026-10-27-p3-m1-app-handoff.md)。用户再次授权后
独立ROS实际通过，前轮自动权限审查超时事实保留于[初次记录](experiments/2026-10-27-p3-perception-engine-worker.md)。
M2概率更新[具体方案](docs/M2_SOFTWARE_TRIAL_PLAN_20261027.md)的合成数据软件试制已获用户确认。
M2-SW-01/02/03/04已完成合成输入、独立oracle、固定/滚动累计、时序/TTL及独立ROS交接。
当前关闭的是M2合成软件试制，真实输入/质量与正式M1/M2验收仍独立登记。
M3-DESIGN-01[具体方案](docs/M3_SOFTWARE_TRIAL_PLAN_20261027.md)已交付：拟用现有
Uncertainty字段进行默认关闭的合成概率区间传播，区分输入/累计来源，缺失贡献使
累计质量保持不可用，直到TTL重启或淘汰重建。不是方差、置信水平或真实校准结果。
用户后续“继续”确认按具体方案推进合成软件试制，M3-SW-01已完成显式合同/profile、
配置、输入和独立oracle；M3-SW-02随后完成固定累计，对保存的10场景/43输入预期一致。
M3-SW-03随后完成区间随窗口滚动、TTL/淘汰/新run及有界状态的离线组合验证；
M3-SW-04随后完成显式ROS选择、公开占据回放及应用质量检查交接，关闭M3合成软件工作包。
M4-DESIGN-01随后交付[Scene Map/有界子地图具体方案](docs/M4_SOFTWARE_TRIAL_PLAN_20261027.md)，
用户后续“继续”确认同一具体软件范围，M4-SW-01已完成显式注册合同、输入与独立预期；
M4-SW-02随后实现显式纯Python有界Scene候选，对保存的8场景41输入52查询预期一致；
M4-SW-03随后完成离线时序/TTL/目录淘汰/新run与资源、联合原子性组合；
M4-SW-04随后完成显式ROS、公开占据回放及独立应用map查询交接，关闭固定合成注册下的M4软件工作包。
按阶段顺序已完成M5-DESIGN-01具体方案：先规划独立地形高程层，明确TerrainPrior准入与兼容恢复，
不把DEM直接转成占据观测；当前未实现DEM，完整阶段门槛保持。
用户10-28追加“本周五前完成报告用ROS可视化界面”并明确必须RViz，优先完成APP-VIS-01。
原生RViz报告版本已于10-28实现和验证；[启动/回放说明](docs/ROS_VISUALIZATION.md)可复现。
用户随后明确需要三维场景与Radar/IR模拟，单独地图工作台不能满足完整可视化目标。
SENS-VIS-01现已完成独立Gazebo功能级场景及标准RViz传感器显示/截图，
见[专用入口](docs/SENSOR_SCENE_VISUALIZATION.md)；此前APP-VIS-01仅保留为地图工作台能力。
用户随后明确继续M5-DESIGN-01；已交付[具体设计](docs/M5_TERRAIN_PRIOR_DESIGN_20261028.md)，
用户继续授权后M5-SW-01已完成私有fixture合同/输入校验及独立预期；
M5-SW-02随后完成独立纯Python地形候选/私有回放，对SW-01保存预期一致；
M5-SW-03随后完成84事件/64版压力/五处故障和逻辑载荷组合，关闭私有离线合成软件子范围。
M5-IFACE-DESIGN-01随后交付独立公共地形查询/状态/记录及兼容恢复具体提案；
用户10-28明确授权后，M5-IFACE-SW-01已完成独立公共类型生成、逻辑合同/codec及记录schema离线验证。
用户随后“继续”后，M5-IFACE-SW-02已实现Provider与独立ROS节点/clock/查询/状态并通过实际拒绝/新run恢复，
用户10-29继续后，SW-03已完成客户端/公共录制与执行回放/可选RViz地形及旧场景兼容，
关闭M5公共合成接口三步软件范围；记录v1无法表达的失败仍明确incomplete，不将其算完整重放。
随后P5-DESIGN-01已交付[组合场景与需求矩阵](docs/PHASE5_SOFTWARE_COMBINATION_DESIGN_20261029.md)，
按真实链分开paired-M1、显式逆观测M4及原生场景显示，明确旧地图墙钟存活/调用期限与地形录制边界；
既有76项定向通过，未实现/运行新组合。用户继续后，P5-SW-01已完成
[九组37子例输入/独立预期及实际线格式](docs/P5_SW01_INPUT_CONTRACT_20261029.md)，742次序列化、31项定向及全仓805项通过；
owner/封存数仅独立声明，不冒充公共可观测字段。随后P5-SW-02已完成
[A/B实际ROS组合与独立回放](docs/P5_SW02_ROS_COMBINATION_20261029.md)：33例/216项、旧默认入口及全仓813项通过；
初次连接/关联/隔离设施失败与修复过程保留。随后P5-SW-03已完成
[S09/C及软件全矩阵交接](docs/P5_SW03_NATIVE_DELIVERY_20261029.md)：本轮四例实际运行，
复核A/B源码/冻结合同与收据后37例/228项通过，全仓819项通过；原生八图与清理证据已交付。
P5-SW-01—03冻结合成软件工作包完成，正式阶段门槛保持。
用户确认后，DELIVERY-SW-01已归并软件入口、八图报告与未关闭门槛；
SIM-MOTION-DESIGN-01已按真实链形成单JSBSim时间源/受控Gazebo采样具体方案，
57项只读/CLI/定向核验和64项既有测试通过，无新联动运行结论。
直接下一项SIM-MOTION-SW-01，先冻结独立输入/预期与场景推进承载，不恢复研究质量任务。
后续SW-01已完成[独立场景推进协议/输入与字节预期](docs/SIM_MOTION_SW01_CONTRACT_20261029.md)：
20组实际生成消息逐字节一致，新增26项/全仓845项通过；未改变旧公共字段或运行入口。
后续SW-02已通过[真实动力学/采样闸门](docs/SIM_MOTION_SW02_ENGINE_20261029.md)：250步/1s、
10对实际采样、20 ACK、唯一clock/state/TF及运行期故障停止；正常/故障最终清理通过，
首采样立即故障时的PX4启动中断255仍保留失败，不扩大为所有故障路径验收。
SIM-MOTION-SW-03已通过[运动感知地图/窗口交接](docs/SIM_MOTION_SW03_DELIVERY_20261029.md)：
同tick Context、公开查询/回放、故障停止、新run恢复和History显示均有实际证据。
随后SIM-MOTION-SW-04-DESIGN已完成[有界多场景具体设计](docs/SIM_MOTION_SW04_MULTISCENE_DESIGN_20261029.md)：
12项源码事实、9核心/3兼容用例、独立几何/空图/TTL预期与资源上界；54项既有定向及13探针通过。
本轮只改文档，新增多场景未实施；下一项SW-04A先冻结独立清单/预期并离线核验。
随后SW-04A已完成[独立清单/校验/预期与实际线格式](docs/SIM_MOTION_SW04A_CONTRACT_20261029.md)：
77组协议/36公共往返、18合成源转换、运动66项/全仓885项通过；仅离线输入范围，未运行新多场景。
直接下一项SW-04B显式装配/真实几何切换/场景化核验，SW-04C再完成最终矩阵及原生交接。
随后SW-04B已完成[真实定向机制门](docs/SIM_MOTION_SW04B_ENGINE_20261029.md)：
同FDM/实采S06空域、S07暂停切换/旧证据TTL/回波返回、S08中途故障及旧默认入口通过；
运动77项/全仓896项通过。原48近边缘数量假设失败保留，明确改为原物理误差界下逐射线零豁免，
不是调大误差或删边缘数据。下一项SW-04C最终9核心/3兼容及原生阶段图，完整阶段门槛保持。
不自动延长自由动力学窗口，不新增控制指令，不恢复真实数据/研究质量任务。
随后SW-04C已完成[最终同源码矩阵与原生交接](docs/SIM_MOTION_SW04C_DELIVERY_20261029.md)：
9核心/3兼容、84组业务/121查询、独立回放与S05/S07阶段图通过；运动84项/全仓903项通过。
四次失败分别记录姿态估计、IC冲突、合法空观测及RViz显示范围问题，修正后整套新run重跑；
原物理容差、时间/身份门禁与1秒上限保持。下一项只做受控飞行联动具体设计审查，不自动控制飞行。
随后SIM-FLIGHT-DESIGN-01已交付[具体方案](docs/SIM_FLIGHT_DESIGN_20261029.md)：
已有执行器通路缺少当前周期/超时的严格拒绝证据，旧1秒自由动力学不能直接当受控飞行。
先离线合同、再1秒只读诊断，后续才单独实施v2/长准备与受限命令；当前不改公共承载或运行默认值。
用户继续后，SIM-FLIGHT-SW-01已完成[私有离线合同](docs/SIM_FLIGHT_SW01_CONTRACT_20261030.md)：
固定AGL=.5m、显式缺包与float32执行器值、属性读回、FDM结果/时间及有界JSONL校验；
新25项/旧运动84项/全仓928项通过。40s及100组采样只为静态合同，未运行；
没有实际HIL包关联证明，binding_status仍unverified，control_gate_accepted固定false。
下一项SW-02隔离宿主≤250步/1s实际只读诊断；ground IC仅进私有诊断，不送旧Gazebo v1端点。
随后SW-02已完成[隔离诊断软件与实际短窗](docs/SIM_FLIGHT_SW02_DIAGNOSTICS_20261030.md)：
正常源时间1s、断连接在.5s停止，原始wire/高度/JSONL与935项回归通过。
实际无执行器回包，不能把初始属性零当作观测到disarmed或已施加零命令；当前周期对应关系仍无证据。
ASL初次419.7假设修正为本模型径向高度独立几何核对，原微米界不变；失败/5s停止全部保留。
下一项先SIM-FLIGHT-DIAG-DESIGN-02只读归因/最小补证方案，不直接放开SW-03长窗或SW-04控制。
随后DIAG-DESIGN-02已交付[有界uORB补证具体方案](docs/SIM_FLIGHT_DIAG_DESIGN_20261030.md)：
实际缺口收敛为PX4内部IMU/EKF/姿态选择/模式/混控/发送的当前run证据，尚无唯一根因。
直接下一项SW-02B保持1s/250步，于125/250步读九类topic并只show三个参数；
用现有listener现值分支，不安装ULog依赖、不重复无新增观察的短测，也不自动扩窗或发控制命令。
随后[SW-02B软件与实际未通过交付](docs/SIM_FLIGHT_SW02B_PROBE_20261030.md)已实现私有合同/严格解析/有界客户端。
实际第二次在125步读到三实例IMU，第二条estimator_status仅六实例标题，按原规则停止；21查询验收未通过。
飞行49项/运动84项/全仓952项与旧normal/disconnect、真实genpy兼容通过，11自有PID退出。
源码只能解释advertised不等于有载荷，不能据此判EKF字段值或唯一根因；下一项先空实例具体补证设计。
随后[DIAG-DESIGN-03](docs/SIM_FLIGHT_DIAG_DESIGN03_20261030.md)完成空实例三态/独立诊断事件的具体设计：
保留旧strict拒绝；拟显式新模式在完整/空实例混合时逐块保存，部分字段或异常仍停止。
采集完整、载荷完整与控制门分别报告，单实例无标签不猜编号；16项只读核验/49项既有定向通过。
下一项SW-02C先冻结18组独立预期再实现/运行补证；原1秒/250步、白名单/墙钟界保持，不自动控制。
随后[SW-02C软件/实际未通过交付](docs/SIM_FLIGHT_SW02C_DIAGNOSTICS_20261030.md)已实现独立三态事件和显式诊断。
125步九topic完成，250步第11次estimator_status含12处nan，按原有限数值规则停止；11查询/10合法事件，21次采集未完成。
同451源码飞行69/运动84/全仓972项与旧两诊断/真实消息兼容通过，17自有PID退出；实际执行器仍0包。
PX4原源存在主动NaN表达辅助源比值不可用的路径，不据此判数值崩溃或放宽合同；下一项先做该语义与隔离补证具体设计。
随后[DIAG-DESIGN-04](docs/SIM_FLIGHT_DIAG_DESIGN04_20261030.md)已交付原生质量隔离具体方案：
仅estimator_status两比值准确nan且同载荷源位符合固定条件时可显式标不可用，其他非有限仍停止。
六实例原文的源位均符合拟议条件；20项源核验、16组独立掩码算例/69项既有定向通过，451源码保持。
下一项SW-02D先冻结20组独立预期，再实施独立私有v2事件/显式采集；旧两个合同和失败不改，不自动控制。
随后[SW-02D](docs/SIM_FLIGHT_SW02D_QUALITY_20261030.md)已完成独立私有v2及实际21次采集/三参数核对：
六实例两比值共12处按同块固定源条件显式标不可用，其他非有限/畸形仍拒绝，旧两个合同不放宽。
采集完整，正文/载荷不完整；已读六flags样本tilt/yaw未对齐、selected姿态缺失、实际执行器仍0包。
飞行92/运动84/全仓995项与旧入口/消息兼容通过，458份源码运行期不变、27自有PID退出。
随后[INIT-DESIGN-01](docs/SIM_FLIGHT_INIT_DESIGN_20261030.md)已交付无控制初始化准备与SW-03衔接方案：
24份源文本/32项核验、旧21条事件重读与250条wire解码、92项既有飞行定向通过，458份源码保持。
区分首次初始化、倾角精对齐、选中姿态和输出链；不把143个原始范围合格样本当内部收敛。
下一项INIT-SW-01先做独立私有合同/字面量预期；新准备期、公共v2和命令尚未实施。
随后[INIT-SW-01](docs/SIM_FLIGHT_INIT_SW01_CONTRACT_20261030.md)已完成新私有离线合同/fixture，
源前后动力学/接触、整数时间/身份/四态质量和84项查询独立校验；合成ready也不产生控制许可。
飞行127/运动84/全仓1030项与旧消息兼容通过，原458源码保持；下一项INIT-SW-02仅私有无控制准备。
随后[INIT-SW-02](docs/SIM_FLIGHT_INIT_SW02_PREPARATION_20261030.md)实现独立宿主/运行器，
实际第423步起收到全零未armed执行器，78包原戳均早于本步HIL4ms，仍无严格周期绑定。
第500步前局部输入静稳可核对，但第30条selector原文含8处nan按原合同拒绝，完整准备未通过。
故障/兼容与134/84/1037项回归通过不开放SW-03运行或控制；下一项先做selector槽位具体设计，不重复正常run。
旧公共字段、默认M1/M2和研究后端状态保持；真实区间覆盖率/质量、真实DEM与占据融合未验收。

## 进行中

| 任务 | 主责任角色 | 下一交付 | 完成条件 |
| --- | --- | --- | --- |
| IFACE-01 / Phase 2 | sensor_engineer | 真实Radar/IR原始记录、安装外参、设备时钟映射与质量来源 | 独立记录回放与跨设备时间/坐标门禁通过；在线图无训练监督泄漏 |
| SENS-TRAIN-01 | sensor_engineer | 真实标定、规模与标签/训练质量证据 | 不以理想fixture覆盖率或无回波替代真实监督质量 |
| ALG-01 / Phase 3真实后端 | perception_engineer | 按用户要求暂不研究模型质量；工程软件按P3-SW计划先行 | 研究任务恢复且候选质量门通过后，分步验证权重/forward/适配；本仓不修改研究仓库 |
| M1 Local Map | mapping_engineer | [真实输入、资源与查询时延矩阵](docs/M1_INPUT_RESOURCE_GATE_20261015.md) | 正式M1→M2验收门槛保持；已确认的合成软件试制独立推进，不以cell上限推断机载RSS达标 |

SW-02B/C原实际验收未通过，失败与交付记录保留在上文链接；SW-02D是独立补证，
不回填旧验收，也不再将重复旧失败列为当前任务。

研究仓库现有候选已被质量审计标记为rejected_for_integration，依据保留在
[历史快照研究审计段落](docs/PROJECT_HISTORY_20261027.md)与[组件登记](algorithms/README.md)。
research模式继续明确不可用，不回退placeholder；本仓不修改同级研究仓库。

## 阻塞与风险

| 范围 | 状态 | 缺少输入或关闭条件 |
| --- | --- | --- |
| PERF-01 | 阻塞 | 正式目标平台、设备配置、20ms起止端点、采样时钟/跨钟映射、持续时长及资源功耗证据；门禁仍为reference_only |
| ENV-03 | 阻塞 | 第二份独立副本及恢复验收未完成；用户未授权外部归档，不执行复制或恢复 |
| 完整Phase 1退出 | 阻塞 | [10-15正式复核](docs/PHASE1_EXIT_REVIEW_20261015.md)未通过；[新日期/范围](docs/PHASE1_DATE_SCOPE_REVIEW_20261015.md)待输入与确认 |
| 完整Phase 2/3 | 进行中 | 真实设备、标定/时钟及真实Radar-IR后端质量；fixture子范围完成不关闭整阶段 |
| GPU与硬件资源 | 阻塞 | 既有NVML/CUDA可用性及机载资源证据仍需独立验证；不妨碍CPU fixture |
| 高速实时与地图资源 | 阻塞 | 35/50/70m/s只具功能级证据；默认异步40ms等待和正常场景一半Radar拒绝不构成20ms/低丢帧验收 |
| 受控飞行准入 | 阻塞 | [INIT-TIME-SW-01](docs/SIM_FLIGHT_INIT_TIME_SW01_DELIVERY_20261030.md)单profile准备与[SW-03A](docs/SIM_FLIGHT_SW03A_CONTRACT_20261102.md)公共v2离线合同已完成；长窗/插件采样属于SW-03B，严格执行器周期绑定/非零因果、命令/正常arming及真实离地仍未验收，控制false/绑定unverified；旧失败保留 |
| 真实地形集成 | 进行中 | [独立真实高程读取/查询/显示](docs/REPORT_IMPROVEMENTS_20261030.md)已完成；真实数据profile/公共服务、地形与Gazebo空间注册和占据融合继续分步实施 |

## 下一步任务

1. SIM-FLIGHT-SW-03B（计划；主责任integration_engineer）：按[SW-03A第7节](docs/SIM_FLIGHT_SW03A_CONTRACT_20261102.md#7-sw-03b交接条件与未验证能力)另行实施新profile原生两侧/三个独立端点、应用前服务错误/后段失败、整数源时间10000步适配、长窗无控制准备与100点真实采样屏障；同tick地图/公开回放、唯一TF/clock/state、预算/故障/迟到/新run/History/清理及旧默认兼容均需实际证据。不得从离线合同或旧10秒结果自动放行；不自动进入SW-04。
2. 报告改进已交付，真实高程服务与场景注册待独立具体方案；不重复已通过的演示、P3交接或客户端短测充作新任务。
3. 真实设备到位后恢复IFACE-01及标定/时钟验收；PERF-01与ENV-03独立跟踪。研究模型质量按用户要求暂不安排，research继续fail-closed。

各项范围、输入、交付、工时估计与验收见[详细计划](docs/STAGE_ADVANCE_PLAN_20261027.md)。
本轮用户已授权基线及SW-03A阶段提交，均逐文件核对；后续任务按其授权范围提交，不自动推送。软件提前开发不表示完整阶段已通过。

建议仍在原Phase 2结束日2026-11-10复查外部输入风险；这是管理检查点，不是新的退出日期。
自主控制、实飞和高真实性传感器物理仿真继续属于独立评审范围。

## 开发入口与证据

- 规则：[AGENTS](AGENTS.md) → [系统架构](docs/SYSTEM_ARCHITECTURE.md) → 涉及目录AGENTS。
- 契约：[DATA_FORMAT](docs/DATA_FORMAT.md)、[SENSOR_INTERFACE](docs/SENSOR_INTERFACE.md)、[COORDINATE_SYSTEM](docs/COORDINATE_SYSTEM.md)。
- 决策：[DECISION_LOG](docs/DECISION_LOG.md)；实验：[EXPERIMENT_LOG](docs/EXPERIMENT_LOG.md)；历史：[完整快照](docs/PROJECT_HISTORY_20261027.md)。
- 环境入口：`bash ros_ws/sim01_env.sh ...`，默认Radar-Diffusion Python；不修改原环境或终端ROS选择。
- 无观察器fixture：`bash ros_ws/sim01_env.sh python ros_ws/local_map_query_run.py --mode inference`；仅软件闭环。
- 配置与兼容：[运行配置说明](docs/RUNTIME_CONFIGURATION.md)。
- 原生RViz：[启动/接入/回放/导出](docs/ROS_VISUALIZATION.md)；[报告图片与图注](experiments/report_assets/rviz-20261028/README.md)。
- 场景/Radar/IR：[Gazebo + RViz启动与截图](docs/SENSOR_SCENE_VISUALIZATION.md)；[场景传感器报告素材](experiments/report_assets/sensor-scene-20261028/README.md)。

## 更新规则

这里只登记当前事实、阻塞和下一交付，完成必须链接证据；过程与失败进入实验记录。
按周复核计划，接口或架构变化进入DECISION_LOG；不因日期到达或fixture通过提高阶段状态。
