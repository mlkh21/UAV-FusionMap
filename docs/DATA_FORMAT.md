# 数据格式与接口语义

2026-10-30补充：独立真实高程预览采用[ufm.elevation.preview.v1静态导出](REPORT_IMPROVEMENTS_20261030.md#2-工具安装与真实高程)，
包括声明来源/DSM/EGM2008/坐标与原点的metadata，以及同形状east/north/height/valid数组。
有效位与源no-data保持，位置查询输出valid/no_data/outside及高度或null；不复用或放宽m5_fixture_v1，旧公共消息字段不变。

版本：v0.1；更新日期：2026-10-14；责任角色：system_architect。
状态：逻辑数据契约已定义；SIM-01A AircraftState的ROS编码已确认并实现，
其余消息仍是逻辑设计。各项运行验收以EXPERIMENT_LOG为准。

## 1. 适用规则

字段名为逻辑接口名，类型表示语义约束；已经实现的ROS编码见下节，其余仍为设计。
ROS编码确定后必须保持单位、维度、空值、时间与坐标语义。标量空值在具体消息中
使用显式有效标志表达，不凭0猜测是否有效。

位置用m，速度用m/s，加速度用m/s²，角度用rad，角速度用rad/s。变换和姿态见
[COORDINATE_SYSTEM](COORDINATE_SYSTEM.md)。不同物理量的不确定性不能直接相加。

## 2. Header：所有观测、状态和地图共有

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| schema_version | string | 本契约版本，初始为0.1 |
| timestamp | int64 | 非负纳秒；观测为采集参考时刻，地图为纳入融合的最新参考时刻 |
| clock_id | string | 时钟域；同一run内跨设备须有明确的时间转换关系 |
| run_id | string | 一次运行标识；仿真重置或新采集运行必须更新 |
| sample_id | string | 同一run内唯一，包含生产者前缀；重复交付保持相同标识 |
| frame_id | string | 本对象空间量所属坐标系；变换有效性另行声明 |
| source_type | enum | simulation、measured、fixture、model、derived；组合数据为derived并保留输入来源，回放保留原始来源并在运行记录标记replay |
| status | enum | valid、degraded、unavailable |
| reason | string | degraded/unavailable时说明原因；valid时可为空 |

接收或发布时刻若记录，使用receive_timestamp/publish_timestamp并声明对应clock_id，
不得覆盖采集timestamp。性能计时可用单调时钟，不能与仿真时间直接相减。

## 3. Quality：质量与不确定性

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| confidence | float32或null | [0,1]的置信分数；记录来源，未提供不能默认为1 |
| uncertainty.status | enum | available或unavailable |
| uncertainty.kind | string | available时必须说明，如position_covariance、occupancy_variance、predictive_entropy、model_score |
| uncertainty.value | 标量/数组或null | 与kind匹配；逐体素量必须与体素索引逐项对应 |
| uncertainty.unit | string | 如m²、rad²、无量纲；协方差混合单位按维度说明 |
| uncertainty.source | string | 传感器规格、标定估计、模型输出或启发式规则 |

编码和业务入口都拒绝bool、NaN、Inf及越界confidence。`available` uncertainty必须有非空
kind/unit/source和有限非空value；`unavailable`的value逻辑值为null，ROS数组为空。
`occupancy_variance`在现有fixture语义下为单个非负值；其他kind不套用未经确认的统一维度
或阈值。输入质量错误不能被裁剪、补默认值或转成free。

available时数值必须有效且符合该物理量约束；unavailable时value为null。
概率、confidence与uncertainty含义不同，不定义通用的互相换算公式。
模型分数未经校准不得标为已校准占据概率误差或位置方差。

2026-10-27已交付[M3合成区间传播提案](M3_SOFTWARE_TRIAL_PLAN_20261027.md)，
复用上述字段定义显式fixture profile，区分单次输入范围与累计范围来源。
用户后续继续确认，SW-01已实现仅由测试工具显式调用的区间profile校验，
kind=`occupancy_probability_interval`、unit=dimensionless、value=[lower,upper]，
分别使用具名input/output source；不可用value仍为None。输入均值须先确定float32值，
范围严格包含该值；wire输出的包含关系按nearest-even承载检查，不修补字段。
这不改变现有通用kind接受范围或定义真实统计置信水平；M2累计质量仍unavailable，
输入/预期证据见[EXP-20261027-012](../experiments/2026-10-27-m3-fixture-oracle.md)。
SW-02已实现显式固定M3累计：公开区间对应所声明算术的累计范围，缺少任一有效贡献
范围则保持unavailable到TTL重启或cell淘汰重建，confidence始终None。
快照/查询只保留原字段；私有端点L不输出。固定证据见
[EXP-20261027-013](../experiments/2026-10-27-m3-fixed-map.md)。
SW-03显式滚动候选已验证范围/缺失状态和均值/原证据时间一起迁移、淘汰及重建；
空帧覆盖变化不刷新证据，过去覆盖查询不泄漏范围。只增加显式候选类，不新增字段或
改变默认M1/M2，M3实际ROS仍待SW-04，见
[EXP-20261027-014](../experiments/2026-10-27-m3-rolling-time.md)。
SW-04已完成显式M3 ROS与公开收据回放，既有字段承载区间来源、缺失锁存及历史质量。
应用对自定义transport独立检查confidence与通用uncertainty，识别本区间kind时核对
dimensionless、双端点、有序概率范围及均值包含关系；wire使用端点的nearest-even
float32映像，不修改原值、不重分类。非法质量响应返回unavailable；其他合法kind仍保真。
五类状态、旧入口及清理证据见
[EXP-20261027-015](../experiments/2026-10-27-m3-ros-handoff.md)，不表示真实覆盖率已校准。

2026-10-28 M4-SW-01在mapping内新增显式fixture注册/输入checker，仅复用现有
OccupancyObservation/SpatialContext/Uncertainty字段，不新增在线字段或消息。
注册为独立私有配置，声明方向、run/clock、来源和有效期，不能通过修改header.frame_id
把odom网格伪装成map。测试预期使用同一固定map网格的MapSnapshot/MapQueryResult，
SW-01时只验证合同与承载，尚未实现Scene候选；后续候选证据单列如下。
详见[M4方案](M4_SOFTWARE_TRIAL_PLAN_20261027.md)与
[EXP-20261028-001](../experiments/2026-10-28-m4-fixture-contract.md)。

M4-SW-02随后实现显式Scene候选，活动M3公开估计经具名固定map←odom注册重索引到
一套map网格，封存记录与活动视图同一Scene index只有一个owner。概率/质量/原时间
整条保留或由更新贡献接管，不把累计快照再次融合，不借旧区间填补新missing。
公开snapshot及query仍沿用本契约字段，index均为Scene格点；coverage是固定包围范围，
空洞或淘汰区域unknown。目录变化增加Scene revision/私有结构时刻，不刷新贡献时间；
早于最新贡献/结构的查询unavailable，过TTL stale保留历史quality，注册过期无cell载荷。
8场景41输入52查询冻结预期和消息序列化证据见
[EXP-20261028-002](../experiments/2026-10-28-m4-scene-candidate.md)；该轮非M4 ROS或真实注册验收。

M4-SW-04已在实际独立ROS中通过既有OccupancyObservation/MapSnapshot/MapQuery的
15观测9快照20查询及公开收据回放，Scene index/map身份、五类状态、原时间/历史质量及缺失
均保真；未新增submap/registration/epoch等公共字段。证据见
[EXP-20261028-004](../experiments/2026-10-28-m4-ros-handoff.md)，固定合成注册不代替真实坐标验收。

## 4. RadarFrame

Radar驱动的ROS原始传输可以使用`sensor_msgs/PointCloud2`，但PointCloud2只是载荷容器，
不是完整业务合同。设备适配器必须校验PointField名称、类型、单位、字节序、逐点时间、
Doppler符号/参考系及RCS/SNR/intensity含义，再形成RadarFrame；不允许只改字段名完成接入。
2026-10-10仅实现明确标记`fixture_only`的**零跨度**PointCloud2受限子集：
配置指定完整点字段集合，位置单位m、Doppler单位m/s与正号语义、
power_quantity/unit，扫描参考时刻中点且等于ROS header.stamp；逐点时间未进入
公共RadarPoint消息，含未声明/字节重叠字段或非零扫描一律拒绝，不能丢弃原始逐点时间
并假装已完成运动补偿。支持ROS标准大小端解码，但不表示兼容实际设备。
依据见[EXP-20261010-002](../experiments/2026-10-10-iface01-sens-train-multiray.md)。

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| header | Header | frame_id为Radar frame，timestamp为扫描参考时刻 |
| points | N条记录 | 每条至少含x、y、z、doppler、power、confidence |
| x / y / z | float32 | Radar坐标下的位置，单位m |
| doppler | float32或null | 径向速度，m/s；正方向约定为远离传感器 |
| power | float32或null | 回波强度字段；含义由power_quantity和power_unit明确 |
| confidence | float32或null | 本点置信分数，未提供时为null |
| point_time_offset_ns | int64[N]或null | 相对header.timestamp的采集偏移；扫描有明显时间跨度时必须提供或声明不可用 |
| scan_start / scan_end | int64 | 同一时钟域下扫描时间范围，覆盖所有点 |
| power_quantity / power_unit | string | 如received_power/W、signal_to_noise_ratio/dB、uncalibrated_intensity/arbitrary |
| doppler_reference | enum | sensor_relative或ego_motion_compensated；补偿算法与输入位姿须可追踪 |
| quality | Quality | 帧级质量及可用测量不确定性；可附逐点质量 |

字段存在不等于物理量已经测得；缺失值通过有效性表达。若旧算法要求SNR而输入仅有
未标定强度，必须报告不兼容，不能只改字段名。无回波不等于视野内全部自由。

### 4.1 型号特定设备时间字段审查（2026-10-13）

本审查针对项目已确定的Continental ARS548和Livox Mid-360，不表示已连接实机。
离线字段适配见[`device_time_adapter.py`](../sensors/ufm_sensors/device_time_adapter.py)，
不发布在线SensorBundle，也不估计跨设备时钟偏移。

- **ARS548**：公开`DetectionList`提供`timestamp_seconds`、
  `timestamp_nanoseconds`和`timestamp_syncstatus`，描述检测列表的设备时间；
  `Detection`包含距离、角度、径向速度、RCS等测量，但没有逐检测采集时间。
  因此只生成列表级`observation_timestamp_ns`，逐点时间和扫描起止保持不可用，
  不用ROS接收`header.stamp`替代设备采集时间。
- **Mid-360**：官方ROS `CustomMsg.timebase`是首点时间，
  `CustomPoint.offset_time`是相对首点的纳秒偏移；适配器生成训练监督点时间
  `point_time_ns=timebase+offset_time`并保留扫描起止。原始UDP包另有`time_type`，
  区分设备启动时间、PTP/gPTP和GPS；`CustomMsg`本身不携带它，只有`CustomMsg`时
  不得宣称同步来源已确认。Mid-360结果仍标记为`lidar_training_supervision_only`，
  不能进入在线Radar/IR SensorBundle、定位、mapping或模型forward。

资料依据：[Mid-360协议](https://livox-wiki-en.readthedocs.io/en/latest/tutorials/new_product/mid360/livox_eth_protocol_mid360.html)、
[Livox CustomMsg](https://github.com/Livox-SDK/livox_ros_driver2/blob/master/msg/CustomMsg.msg)、
[Livox CustomPoint](https://github.com/Livox-SDK/livox_ros_driver2/blob/master/msg/CustomPoint.msg)、
[ARS548 DetectionList](https://raw.githubusercontent.com/robotics-upo/ars548_ros/noetic/ars548_messages/msg/DetectionList.msg)
和[ARS548 Detection](https://github.com/robotics-upo/ars548_ros/blob/noetic/ars548_messages/msg/Detection.msg)。
尚未取得实机记录，因此不能证明设备与AircraftState之间的时钟偏移、漂移或同步误差，
也不改变正式PERF-01门禁。

### 4.2 设备时间审计记录（`device_time_record_v1`）

设备记录器在解码设备消息后，使用[`device_time_record.py`](../sensors/ufm_sensors/device_time_record.py)
生成JSON-ready记录。记录必须同时保留：

| 字段 | 语义 |
| --- | --- |
| `device_timestamp_ns` | 由设备字段组合/展开的采集时间；ARS548为检测列表时间，Mid-360为首点或扫描参考时间 |
| `receive_timestamp_ns` / `receive_clock_id` | 主机收到该消息的时间和时钟域，不能覆盖设备时间 |
| `time_mapping_status` | 当前只能为`unmapped`；没有实机公共时钟证据不得填写offset/drift/error |
| `time_sync_verified` | 当前只能为false；Mid-360的`time_type`只说明同步来源类别，不等于残差验收 |
| `payload` | `device_time_v1`解码结果，保留run/clock/sample/frame身份和型号字段 |

ARS548记录必须保持列表级时间且逐点时间为null；Mid-360记录必须校验
`point_time_ns = observation_timestamp_ns + offset_time_ns`、扫描首尾和偏移顺序。
若Mid-360记录含原始包`time_type`，`transport`必须声明原始包元数据来源；只有
`CustomMsg`时同步来源保持未提供。记录流只允许一个型号、一个设备时钟/接收时钟组合，
`sample_id`重复或身份混用必须拒绝。该记录是审计/回放输入，不是在线ROS公共消息。
2026-10-15离线审计补充：同一设备流的`frame_id`必须稳定，允许收件顺序乱序；
`time_source`、`time_sync_source_present`与逐点时间语义必须与原设备时间类型/
来源一致，不能通过篡改record的payload伪造PTP或逐检测时间。
已解码的单设备JSONL可用只读
`bash ros_ws/sim01_env.sh python -B tests/iface01_device_record_replay.py --input FILE`
逐行回放验证：空/坏行、重复sample或混合run/clock/frame拒绝；收件乱序允许，
只输出设备/接收时间各自的边界，不计算跨钟偏移。JSONL和审计报告均不是
原始设备记录真实性、同步残差或真实驱动/ROS在线接入的验收证据。

## 5. InfraredFrame

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| header | Header | frame_id为thermal_optical，timestamp为曝光中点 |
| image | H×W或H×W×C数组 | encoding声明数据类型与通道，原始值必须保留其含义 |
| encoding / value_unit | string | 如mono16/DN或32FC1/K；不能将DN直接解释为温度 |
| exposure_start / exposure_end | int64 | 曝光区间，同header时钟；无法提供时显式标不可用 |
| camera_info | object | width、height、K[3,3]、畸变模型D、校正状态、calibration_id |
| quality | Quality | 图像质量及辐射/标定不确定性可用性 |

缩放、裁剪、去畸变必须同步维护camera_info并记录变换。三通道模型适配不能改变
原始热图的物理含义；模型归一化由perception负责。

## 6. ImuSample、AircraftState与SceneDescription

ImuSample包含header、linear_acceleration[3]、angular_velocity[3]及各自3×3协方差。
必须声明加速度是比力还是已去重力线加速度；姿态若提供，注明有效性和来源。

2026-10-26可选仿真IMU编码为`uav_fusionmap_msgs/ImuSample`：使用现有
`ObservationHeader`保留采样纳秒、run/clock/sample身份及来源/状态；
`acceleration_type=SPECIFIC_FORCE`（0）或`GRAVITY_REMOVED`（1）；
`linear_acceleration`单位m/s²，`angular_velocity`单位rad/s，协方差均为
9元素行优先数组并配独立`*_available`标志。本子范围没有可信协方差，逻辑值
为`None`，编码时`available=false`、数组仅为无效槽位，解码时恢复`None`；
不得把该槽位解释为零噪声。`calibration_id`标识坐标适配依据；源端为空表示
尚未适配，适配端仅允许明确的虚拟`sim_pilot_virtual_flu_v1`。当前只验证
`specific_force`仿真源，未验证真实安装、真实设备时钟/协方差和去重力输出。
这条IMU旁路不改变SensorBundle字段，也不成为定位或地图业务输入。

AircraftState包含header、position[3]、orientation_xyzw[4]、linear_velocity[3]、
body_frame_id、velocity_frame_id、state_source和quality。state_source区分ground_truth
与estimated。position/orientation表示Body在header.frame_id下的位姿；速度必须有明确
坐标系。位姿协方差按[x,y,z,rx,ry,rz]排列，缺失时标不可用。

当前可从同一权威状态派生`nav_msgs/Odometry`兼容镜像，用于通用ROS工具和TF承载；
Odometry不含run_id、clock_id、sample_id、source_type、state_source、status/reason和明确的
缺失质量语义，不能单独替代AircraftState。两者并存时必须保持同一采样时间、frame、
child frame和唯一odom→base_link发布责任，不能形成两套冲突状态源。

T-14实现由`state_adapter_node`可选发布`/uav/localization/odom`和动态
`odom -> base_link` TF；两者默认关闭，必须由同一适配状态、同一采样纳秒时间派生。
状态为`unavailable`或terminal时只保留AircraftState状态语义，不发布几何镜像。当前
质量未知时Odometry协方差使用兼容消息的未知标记，不填造测量方差；实现与fixture证据
见[EXP-20261014-008](../experiments/2026-10-14-t14-odom-tf.md)。

### 6.1 SIM-01A AircraftState ROS编码（09-14用户确认）

`uav_fusionmap_msgs`包含ObservationHeader、Uncertainty、Quality、AircraftState。
Header的timestamp编码为int64非负纳秒，其余标识和reason为string；不重复添加
std_msgs/Header。position/velocity编码为float64[3]，orientation_xyzw为float64[4]。

| 枚举 | 固定ROS uint8值 |
| --- | --- |
| source_type | simulation=0、measured=1、fixture=2、model=3、derived=4 |
| status | valid=0、degraded=1、unavailable=2 |
| state_source | ground_truth=0、estimated=1 |
| uncertainty.status | unavailable=0、available=1 |

confidence=null对应confidence_available=false，数值槽不构成观测；
uncertainty.value=null对应unavailable和float64[]空数组。kind/unit/source仍保留来源。

2026-10-27契约修复：Header统一检查0.1版本、非负int64采样时间和已定义枚举；
SpatialContext变换状态和uncertainty状态只接受0/1，其他数值拒绝，不能按非零解释为可用。
纯业务地图也在修改实例前拒绝不支持的Header，字段与消息版本不变。
本步拒绝available uncertainty：现有PX4缺完整姿态协方差和速度协方差轴转换，
缺失量不得补零。有效几何及单位四元数容差0.001均须校验；未知枚举/空身份拒绝。

源header使用clock_id=sim:<run_id>、sample_id=sim.odometry:<sysid>:<compid>:<source_us>；
采样timestamp严格整数us×1000。sensors输出sample_id=sensors.state:<源sample_id>，
时间/run/state_source保持，source_type=derived。重复身份不产生新观测，内容冲突拒绝。
终止状态status=unavailable、reason=terminal:<code>，独立ID为
sim.terminal:<code>:<last_clock_us>，无已知时钟取0；终止几何槽不能解释为观测。
消费者完成基本身份/当前run校验后优先清缓存并锁run，适配后继续传播终止。
预热和时钟门控详见[SENSOR_INTERFACE](SENSOR_INTERFACE.md)。

SceneDescription由simulation提供给sensors：包含header、scene_id、revision、
几何/障碍物资产引用、物体位姿与有效时间、热属性来源及单位。几何采用m，热属性
未建模时必须标明功能级占位。资产格式在Phase 1确定，不能推定JSBSim自动提供所有资产。

### 6.2 场景运动推进独立协议（2026-10-29）

SIM-MOTION-SW-01新增独立`uav_fusionmap_sim_scene_msgs`的SceneFrame、SceneCaptureAck及SceneStep，
当时只冻结并验证离线合同/真实消息线格式；后续[SW-02](SIM_MOTION_SW02_ENGINE_20261029.md)
已在独立入口实现服务、发布者及推进状态机，旧默认launch不装配这些接口。
完整字段、逻辑None与规范空槽见[SW-01合同](SIM_MOTION_SW01_CONTRACT_20261029.md)。
SceneFrame嵌入原AircraftState，但仅在此profile接受scene_world/simulation/ground_truth/valid、
base_link速度与质心FLU、缺失质量；协议版本1与旧Header 0.1独立，旧字段/codec均保持。
timestamp严格为step_index×4000000整数纳秒，注册固定jsbsim_cg_to_scene_enu_v1。
step 0只初始化，正step每25步为采样tick；ACK与成功响应的采样时间精确匹配，失败不得推进。
响应的has_applied_frame、radar_captured、infrared_captured承载缺失语义，数值0/负z不充当缺失标志。
单线格式≤4096字节、文本身份≤128 UTF-8字节、reason≤256字节；坏枚举/版本、非有限、
非规范bool/空槽、错身份、超限和训练监督字段拒绝。没有在旧占据/地形消息中附加这些字段。
SW-02真实raw测量戳不改写，失败不提交业务clock/state；terminal仍使用旧AircraftState的
unavailable/terminal:<reason>，不作为SceneFrame几何目标，也不发布TF或恢复已锁定stream。

后续[SW-04A](SIM_MOTION_SW04A_CONTRACT_20261029.md)新增独立测试清单
`sim_motion_multiscene_fixture.v1`，由simulation离线逻辑校验与tests显式消费。
它固定9例IC/几何/epoch/故障/预算，沿用上述场景公共协议，不新增公共消息字段，
不进入SensorBundle/感知forward/mapping；几何oracle仅用于独立评测。
77组既有场景消息真实字节及36组旧公共消息空观测/查询往返通过，非新增场景运行。

后续[SW-04B](SIM_MOTION_SW04B_ENGINE_20261029.md)在不改上述公共字段下实际装配新case。
S07几何端点复用标准SetModelState，status_message中的scene_geometry_epoch.v1只记录
run/epoch/step、整数world前后纳秒、paused、model/collision位置与visual局部位置/box尺寸等基础设施读回。
在线Radar/IR与占据/查询不携带这些几何诊断或测试oracle。有效零点观测仍不生成free，旧cell证据时间保持。

随后[SW-04C](SIM_MOTION_SW04C_DELIVERY_20261029.md)在同一最终源码上完成9核心/3兼容，
25份旧定义逐值保持，77组实际场景字节/36组旧公共往返通过。
S05视场离开产生的合法空帧同样不能刷新旧cell；不强制每个合法运动帧有回波或IR纹理。
empty阶段、窗口归一化与截图角色属于测试/显示收据，不写入在线业务消息。

[SIM-FLIGHT具体提案](SIM_FLIGHT_DESIGN_20261029.md)仅拟议私有flight/执行器记录合同和
后续protocol_version=2的独立codec/端点；本轮没有新增/修改公共字段、类型、schema或运行消费方。
私有执行器mode/armed/16路值缺失须显式不可用，不能以零值冒充已观测disarmed；
HIL微秒原值、FDM纳秒网格及单调墙钟分开保存，控制诊断不得进入在线SensorBundle/占据消息。
2026-10-30 [SW-01](SIM_FLIGHT_SW01_CONTRACT_20261030.md#3-私有记录与缺失语义)已实现私有
sim_flight_fixture.v1、sim_flight_actuator_record.v1及sim_flight_recording.v1的严格JSON/JSONL合同。
每层精确键集，拒绝训练监督字段；has_actuator=false时载荷/requested及中间墙钟显式null，
16路保留float32原值，HIL微秒为uint64整数，FDM前后时间与4ms步长各受1ns界。
记录头含固定observation_only profile/peer/初始属性；连续step、接收序号、属性与终止状态逐流核对。
绑定仅unverified且控制门固定false，armed记录在observe流中拒绝；无新增公共消息或运行消费方。
完整字段/资源边界与合成验证见合同，未验证真实MAVLink wire或因果关联。
随后[SW-02](SIM_FLIGHT_SW02_DIAGNOSTICS_20261030.md)已实际写入同一私有记录schema，
另保存wire.jsonl原始TCP块的direction/step/wall/length/sent/hex及initial.json/terminal.json诊断。
这些不是公开dataset或业务消息；只有严格校验通过才生成recording.jsonl，坏/不可表达记录保留并明确失败。
实际正常250条与断连接126条均has_actuator=false、actuator/requested=null，0不是执行器观测值。
真实HIL_SENSOR时间逐字节核对，binding_status仍unverified；正向执行器wire/属性链尚无当前run证据。
后续[DIAG-DESIGN-02](SIM_FLIGHT_DIAG_DESIGN_20261030.md#42-身份时序与预算)拟私有
sim_flight_uorb_snapshot.v1：本次PX4/daemon身份、检查点/查询序号、原始topic时间/实例、
单调查询区间、退出码和原始输出/缺失状态分别保存；未实现或新增公共字段。
native的never published、exit0但无字段和数值0必须分开；打印浮点不替代MAVLink float32位模式，
逐份查询不具原子同tick含义，绑定和控制门仍不开放。
随后[SW-02B私有合同](SIM_FLIGHT_SW02B_PROBE_20261030.md#3-私有合同与预算)已实现query/snapshot v1，
精确键集及完整原生msg字段/实例/整数时间、身份/预算和JSON投影类型校验，未改公共协议。
唯一有效实际快照三组IMU均492000us；第二条estimator_status空标题仍拒绝，不编码成未发布或0。
21条流验收未通过；尚无三态诊断事件合同，后续须先设计，旧严格缺失语义保持。
随后[三态具体设计](SIM_FLIGHT_DIAG_DESIGN03_20261030.md#4-拟议私有事件与校验)已定义拟议
sim_flight_uorb_diagnostic.v1的精确键集及payload/not_published/payload_unavailable；
空块fields=null、完整块全字段、单实例无标签编号null，混合块顶层不可用；部分字段仍失败。
尚未实现/生成新合同或公共字段；与旧snapshot schema交叉拒绝，不回填旧失败或将空块赋零。
随后[SW-02C](SIM_FLIGHT_SW02C_DIAGNOSTICS_20261030.md#3-独立合同与停止规则)已实现独立私有事件和JSONL，
新旧schema交叉拒绝；10条实际合法事件为3 payload/6 unavailable/1 not_published。
第11次原文nan仍按非有限拒绝，不编码为合法浮点、0/null或空块；21条流未完成，公共消息不变。
显式原生非有限质量的未来表示尚未设计/实现，不能由源码的NaN默认值推定本run全部状态。
随后[DIAG-DESIGN-04](SIM_FLIGHT_DIAG_DESIGN04_20261030.md#4-新私有事件表示)已定义拟议私有diagnostic.v2：
新增payload_quality_unavailable及每实例unavailable_fields，只对两白名单比值的准确nan与同块固定源条件合格时，
以明确原因/原token及对应null隔离；其他非有限仍拒绝。不能只填null或把质量不可用当空正文。
尚未实现此新codec/公共字段；新旧schema交叉拒绝，原SW-02B/C失败与有限数值合同保持。
随后[SW-02D合同/实际记录](SIM_FLIGHT_SW02D_QUALITY_20261030.md#3-合同源语义与预算)已实现上述私有v2及严格codec：
完整同块uint32标志与32位标注一致，vel仅flags & 0x0100000c == 0、pos仅flags & 0x1004 == 0时，
准确nan可编码对应null和有序unavailable_fields；记录field/native_token/reason三键，原因固定native_ratio_source_not_selected。
其他字段/变体/错条件非有限仍拒绝；部分字段、坏类型/身份/时间/超限和新旧schema交叉均拒绝。
21条实际事件逐原文重读通过，8 payload/2 not_published/10 payload_unavailable/1 payload_quality_unavailable；
12处质量缺失显式记录，diagnostic_collection_complete=true而body_complete/payload_complete=false。
两个旧v1对旧NaN继续拒绝，公共消息/在线业务合同不变，binding仍unverified且control_gate_accepted=false。
随后[INIT-DESIGN-01](SIM_FLIGHT_INIT_DESIGN_20261030.md#5-独立合同与观测计划)拟独立私有初始化schema，
保存FDM前后动力学、AGL/速度/Euler/PQR、pilot比力、支柱WOW/压缩力和原HIL时间，缺包显式null。
新84项查询不借旧21项封套；地面接触、初始化、姿态与输出链分别判断，不把零属性当执行器观测。
本轮只有具体设计，未实现新codec/profile或公共消息，在线合同保持。
随后[INIT-SW-01完整合同](SIM_FLIGHT_INIT_SW01_CONTRACT_20261030.md#3-精确合同)已实现独立fixture/recording/step/
query/observation/terminal v1及有界JSON/JSONL。fdm.hil_sensor精确保存原time_usec/accel_mps2/gyro_radps，
与前后动力学/支柱接触及原始HIL时间分开；缺包slot为null，零属性不冒充已观测执行器。
新84查询使用独立封套，完整原文投影/类型一致、同块两字段准确nan条件隔离，原生未来/倒退时间拒绝。
私有JSON实际重读通过，公共消息/在线合同及旧v1/quality-v2保持；合成四门通过也只产生unverified/控制false。
随后[INIT-SW-02实际记录](SIM_FLIGHT_INIT_SW02_PREPARATION_20261030.md)已产生该私有step/wire/原文事件：
500 step含78真实零包及原四属性，原始float32/整数时间逐包独立核对，绑定仍unverified。
第30条selector四数组共8处nan不在两比值条件隔离白名单内，严格拒绝、raw保存，合法事件仅29。
不新增schema或把此nan填null/0/1；期限失败末条超1s仅作为raw失败证据，不当合法正常step。
随后[selector具体设计](SIM_FLIGHT_INIT_SELECTOR_DESIGN_20261030.md#3-拟议解析规则与缺失表示)拟独立fixture/recording/query/observation：
9槽比值未见尾部与4槽IMU误差准确nan按field/index/token/reason显式隔离，原84 codec仍严格拒绝。
拟98项观测与原物理header/step/terminal按同run固定文件组合；原消费IMU时间保持null，非选中槽缺失不填0或改成健康。
本轮未实施任何新schema/解析规则，下一项只离线合同，历史失败不迁移成合法事件。
随后[selector SW-01合同](SIM_FLIGHT_INIT_SELECTOR_SW01_CONTRACT_20261030.md#3-精确合同与源检查)已实现上述独立4种私有封套，
逐槽null/说明与原文投影一一对应；98计划与原物理v1按固定同run文件组合，旧84 codec不改。
101次新私有JSON往返/两组合成文件通过，非ROS新线格式/实际采集；原消费时间null/控制false，历史失败不回填。
随后[selector SW-02](SIM_FLIGHT_INIT_SELECTOR_SW02_PREPARATION_20261030.md)实际写59个独立封套，32处selector缺失显式隔离。
私有组合现允许物理2500成功终态后的末组查询；仅固定PX4 rootfs/etc运行资源链接不作记录输入，其他链接拒绝。
1008条4027999us原始wire/失败raw保留，网格应4028000而未接纳；不改原物理schema/时间界或历史记录。
随后[INIT-TIME-SW-01](SIM_FLIGHT_INIT_TIME_SW01_DELIVERY_20261030.md#3-时间生产与拒绝规则)新增私有time-grid.jsonl来源收据，
精确sensor_kind/source_step/source_time_s/time_usec四键，原double与发送前生成的整数分别保存；不改既有schema/接收包或历史原戳。
实际2509条收据与2500 HIL/9 GPS发送字节一一对应；单profile完整准备通过，控制false/绑定unverified。

## 7. SensorBundle与SpatialContext

SensorBundle包含header、radar、infrared、可选IMU时间段、state、calibration_id、
SpatialContext及同步记录。header.timestamp为选定参考时刻，默认Radar扫描参考时刻；
header.frame_id默认radar，各子观测保留自身timestamp和frame_id。
SensorBundle不包含LiDAR点云、LiDAR体素、occupancy target或observed mask监督标签；
该限制对仿真、回放和实物推理一致，防止训练监督泄漏到Radar+IR forward输入。

同步记录至少包括各观测与参考时刻差值、时钟转换来源、误差上界、插值/运动补偿状态。
超限或缺失时按[SENSOR_INTERFACE](SENSOR_INTERFACE.md)声明降级或不可用。

SpatialContext至少包含：

- reference_timestamp、clock_id：与外层观测参考时刻一致。
- mapping_frame_id：初始Local Map为odom；明确转换后的Scene Map可为map。
- source_frame_id：当前观测网格参考系，与占据header.frame_id一致。
- T_mapping_source[4,4]：source到mapping坐标的变换及available标志。
- T_mapping_body[4,4]：参考时刻Body位姿，用于地图中心更新，附available标志。
- pose_uncertainty：位姿Uncertainty（status/kind/value/unit/source）及协方差可用性。
- calibration_id与state_source：标定版本及估计/真值来源。

sensors生成状态与标定上下文，perception在改变网格参考系时组合对应变换并传给mapping。
变换不可用时不得空间融合；来源和时间必须保持可追踪。

### 7.1 训练监督记录（非运行时SensorBundle）

训练数据生成模式可记录独立的LiDAR监督点云及标签清单。记录至少包含run_id、sample_id、
clock_id、扫描起止与逐点时间可用性、frame_id、calibration_id、来源/模拟等级、与目标
Radar/IR样本的关联，以及由射线覆盖生成的occupancy target和observed mask版本。
SENS-TRAIN-01功能级记录schema `0.2`在扫描时长大于零时还必须记录每条射线相对
`scan_start`的整数纳秒偏移、采集时刻的原始传感器坐标、扫描中点坐标中的补偿点，
以及插值所使用的AircraftState sample_id。扫描时长必须为偶数纳秒，`coordinate_frame_timestamp_ns`
指向精确扫描中点；位置使用线性插值，姿态使用最短弧SLERP。只有逐点时间覆盖
`[scan_start, scan_end]`且状态属于同一run/clock、有效估计状态历史完整时才可生成记录。
`lidar.ray_time_offsets_ns`必须保留全部配置射线的时间槽，包括没有回波的射线；
有回波点通过`ray_index`引用对应槽，不能用“点记录不存在”代替“采集时间未知”。
同一`ray_index`最多允许一条回波点，偏移列表与配置不一致时记录无效。历史schema `0.1`
的零时长记录可按兼容规则将缺失偏移解释为全零，但新写入记录仍显式保存该列表。
这只是训练fixture记录合同，不改变运行时SensorBundle或公共RadarPoint消息。
未被射线覆盖、被遮挡、超量程或FOV外区域保持unknown；无点不得直接标为free。

2026-10-13训练标签索引补充数值规则：`scaled=(position-origin)/resolution`距整数
不超过`8*float64_epsilon*max(1,abs(scaled))`时先吸附到该整数再floor，避免同一
补偿表面被浮点舍入分裂到相邻体素；其余位置保持floor。该规则只用于训练标签
体素索引，不是几何擦边、物理噪声或占据置信度容差，schema和observed语义不变。
证据见[EXP-20261013-006](../experiments/2026-10-13-sens-train-scene-statistics.md)。

监督记录只供训练target构造和离线质量审计，不是perception运行输入、定位来源或地图
更新输入。fake LiDAR消息的具体ROS编码在实现任务中确认，本契约不把接口设计写成已有消息。

## 8. OccupancyObservation

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| header | Header | timestamp为观测参考时刻，frame_id为网格参考系 |
| voxel | int32[N,3] | 非负XYZ整数索引，不是米制坐标 |
| probability | float32[N] | [0,1]占据概率；只在observed_mask=true且状态有效时作为可融合证据 |
| observed_mask | bool[N] | 对应体素具有本接口声明的有效观测域；来源须记录，不能从概率大小推定 |
| confidence | float32[N]或null | 对应体素置信分数；缺失必须保留不可用语义 |
| uncertainty | Quality中的不确定性对象 | 数组与voxel同序，类型/单位/来源必须声明 |
| resolution | float64[3] | XYZ三轴体素尺寸，m且均大于0 |
| shape | int32[3] | XYZ网格大小，索引必须在范围内 |
| origin | Pose | 网格最小角在header.frame_id中的位置和orientation_xyzw |
| context | SpatialContext | 同观测时刻的状态、变换、质量和标定信息 |
| observed_domain_source | string | 如传感器可见性、Radar射线模型、fixture；必须说明假设 |

体素中心为`origin.position + R_origin × ((voxel + 0.5) ⊙ resolution)`。
同一消息内索引不得重复。未列出的网格单元以及observed_mask=false的单元均为unknown。
unknown单元如保留概率槽，使用0.5占位且不得参与自由/占据融合；概率0.5本身不表示已观测。

数据类型转换到稠密数组时逻辑顺序为[X,Y,Z]，Z索引变化最快；模型C,Z,X,Y必须显式
转换并用已知单体素位置验证。数组转换不得改变origin、resolution与坐标系。

disabled模式可发N=0且status=unavailable的观测并保留状态上下文。valid的空消息也
不代表整个网格自由。同一run内sample_id重复交付不得重复累积概率证据。

2026-10-27 M2-SW-01仅复用现有字段生成测试占据：source_type=fixture且
observed_domain_source=`m2_explicit_inverse_fixture_v1`，显式声明合成逆观测算术语义。
该domain不是对原placeholder或研究概率的自动转换/校准；缺失/无回波不产生free。
固定单位变换与calibration_id只是具名合成场景，不是实物外参。SW-01验证输入和
独立数值预期，记录见
[EXP-20261027-007](../experiments/2026-10-27-m2-fixture-oracle.md)。
后续SW-02已实现固定合成网格累计/查询，沿用MapSnapshot/MapQueryResult字段，
probability为具名试制累计结果、confidence/uncertainty仍不可用；未观测/失效/中性输入
不刷新证据时间，查询超过min(max_age_ns,配置TTL)为stale。
这只适用于显式M2候选，不改变M1默认查询行为或声明真实概率校准，见
[EXP-20261027-008](../experiments/2026-10-27-m2-fixed-map.md)。
SW-03的显式滚动候选沿用相同字段，重叠cell保留累计概率与原证据时间，移出整体丢弃。
合法空帧移动窗口可增加revision，header.timestamp仍为最新贡献证据时间；
内部另记最新覆盖变化时刻，早于该时刻的查询返回unavailable，不以未来窗口回答历史查询。
上述语义仅在显式M2候选生效，未改M1默认入口；离线验证见
[EXP-20261027-009](../experiments/2026-10-27-m2-rolling-time.md)。
SW-04已用现有ROS占据/快照/查询消息通过独立合成运行及公开收据回放，
应用保持occupied/free/unknown/stale/unavailable与不可用质量语义。
没有增加公共字段，普通placeholder概率不能自动转成M2逆观测证据，见
[EXP-20261027-010](../experiments/2026-10-27-m2-ros-handoff.md)。

## 9. MapSnapshot与MapQuery

MapSnapshot包含header、map_id、revision、grid、resolution、shape、origin及
coverage、source_types（所融合观测的来源集合），状态原因统一使用header.reason。地图source_type为derived，
必须保留fixture/model等输入来源。初始采用完整快照语义，增量协议留待实际性能需求评审。

grid沿用XYZ索引表示，每条包含index、probability、observed、last_observed_timestamp、
confidence和uncertainty。未列出的单元为unknown。地图header.timestamp表示最新融合
观测时刻；publish_timestamp表示输出时刻，不得以重新发布掩盖地图老化。

coverage说明可查询的空间范围；新鲜度根据查询时间与各单元最后观测时间计算。
融合停止时保留last_observed_timestamp，按策略标记stale；新run_id使用新地图。

MapQueryRequest包含map_id、frame_id、clock_id、run_id、query_timestamp、查询点或
区域及max_age_ns；坐标必须与目标地图一致，否则明确拒绝，不能自动猜测变换。
MapQueryResult返回revision、占据概率、质量、最后观测时间及以下状态：

| 状态 | 含义 |
| --- | --- |
| occupied | 有效、新鲜观测满足已确认的占据阈值 |
| free | 有效、新鲜观测满足已确认的自由阈值 |
| unknown | 无观测、阈值中间区或查询越出coverage；reason说明原因 |
| stale | 有历史观测，但超过max_age_ns |
| unavailable | 地图、时钟或请求条件不可用/不匹配 |

占据/自由阈值与老化时限需通过任务确定，当前没有已验收默认值。

### 9.1 固定Local Map单点查询子集（2026-10-14）

`SparseLocalMap.query()`已实现上述五类状态的纯业务查询。当前只支持固定、轴对齐
odom网格中的单点；不支持区域查询、历史地图或自动坐标转换。请求时间早于最新地图
时间时返回`unavailable/query_before_latest_map_time`，不会用未来地图回答历史查询。
年龄等于`max_age_ns`仍新鲜，严格大于才为stale；查询不刷新地图revision或观测时间。
显式配置满足`0 <= free_threshold < occupied_threshold <= 1`的一对阈值后，概率
小于等于自由阈值或大于等于占据阈值才分类；阈值之间或未配置阈值均为unknown，
但仍保留有效历史概率。测试中的0.3/0.7仅为fixture规则，不是已验收飞行默认值。
纯业务验证记录见[EXP-20261014-009](../experiments/2026-10-14-local-map-query.md)。

用户确认的ROS扩展为新增`uav_fusionmap_msgs/MapQuery.srv`与`MapQueryResult.msg`，
沿用v0.1逻辑语义，不改变现有MapSnapshot消息。服务名为`/uav/map/query`，由已有
地图节点可选提供，`enable_query`默认false；更新和查询共用同一地图实例与锁。

| 请求字段 | ROS编码与语义 |
| --- | --- |
| map_id / frame_id / run_id / clock_id | string，目标地图和请求身份，均必须非空 |
| query_timestamp / max_age_ns | int64非负纳秒；时钟域由clock_id声明，由请求方提供同域查询时刻 |
| point | float64[3]，目标地图坐标系下的米制XYZ点，必须有限 |

响应包含单个`MapQueryResult result`：map_id为服务地图ID，revision为该地图版本；
run_id/clock_id/frame_id/query_timestamp/point回显请求域，不表示为错误域做了转换。
身份不匹配时不返回地图单元载荷。响应status固定为occupied=0、free=1、unknown=2、
stale=3、unavailable=4，reason说明未知/失效原因。index为int32[3]且有
index_available；probability与confidence为float32且各有availability；
last_observed_timestamp为int64且有availability；observed独立保留观测域语义，
uncertainty沿用现有Uncertainty的status/kind/value/unit/source。
缺失数值槽仅用于承载，不构成概率0或时间0的观测；未知quality保持unavailable。
空身份、负时间/年龄或非有限点为非法请求，明确以ROS service error拒绝；合法请求的
地图/域不匹配返回unavailable。该子集不推断物理时钟质量，也不使用接收墙钟替代请求时间。

服务实现和实际ROS验收见[EXP-20261014-010](../experiments/2026-10-14-local-map-query-ros.md)。
启用、默认关闭及未配置分类阈值三种fixture模式均已通过；另有一轮连接图检查失败
因ROS仿真时间基础设施自动订阅`/clock`，失败目录保留，修正后的图规则仍禁止传感器、
状态、Odometry、Radar和训练LiDAR订阅。该结果只关闭固定网格单点查询的软件子范围，
不代表滚动地图、概率累计、实时性能、正式设备输入或对照试验通过。

### 9.2 基础滚动Local Map软件子范围（2026-10-14）

上述§9.1记录的是当时固定网格查询验收；本节是在用户确认后新增的可选实现，
`SparseLocalMap(rolling_enabled=False)`、感知`rolling_grid=False`均保持旧默认。
滚动模式仍使用原有OccupancyObservation、MapSnapshot和MapQuery消息及五类状态，
没有新增公共字段、TF查询或状态订阅。当前仅接收轴对齐odom格网；有效观测的
`SpatialContext`必须是观测时间、同一clock、`source_frame_id=odom`、
`mapping_frame_id=odom`、可用且为单位阵的`T_mapping_source`、可用且为有效刚体
变换的`T_mapping_body`。Body仅用于读取观测时刻odom位置；偏航不旋转地图轴。

原始配置`origin`作为固定格点锚，中心为`origin + shape * resolution / 2`。每轴
`shift = floor((body_position - initial_center) / resolution + 0.5)`，窗口新原点为
`anchor_origin + shift * resolution`；半格恰好落点向正方向取整。观测格网的
`origin`可与当前地图不同，但必须落在同一锚点/分辨率整格格点，分辨率和形状
必须匹配；先由观测origin+体素index确定odom物理位置，再按新地图origin重算
index。任意倾斜观测网格、任意TF变换和历史版本查询不在此子范围内。

每次有效观测整格移动时，重叠区域重映射且保留原概率、质量、最后观测时刻；
移出coverage的单元被丢弃，新进入区域无单元且返回unknown，不以无回波或
未观测推断free。大位移无重叠时自然清空历史。即便有效观测不含已观测体素，
地图仍可移动并推进revision/最新有效观测时间，但不刷新旧单元观测时刻；
degraded/unavailable输入不移动地图、不发布新快照。旧时间、冲突身份或不匹配
run/clock拒绝；同一最近样本原样重放忽略。断流后查询按请求的同域时间和
max_age_ns对保留单元老化，恢复仅更新显式observed单元；新run/clock必须新建实例。
更新与查询沿用同一实例及锁，snapshot中的origin、coverage、cell index、revision
与单点query的当前版本一致。有限shape、max_active_cells继续约束活跃稀疏单元数；
这不是RSS/高航速性能验收，也不实现概率累计。独立软件验证见
[EXP-20261014-011](../experiments/2026-10-14-local-map-rolling.md)。

## 10. TerrainPrior：后期接口预留

DEM输入至少包含terrain_id、版本/来源、时间及有效期、水平坐标参考、垂直高程基准、
grid、resolution、origin、height_unit、no_data_mask和height_uncertainty。
进入mapping前必须完成到地图坐标的注册；缺少基准时不得融合。
本节仅定义接入约束，详细栅格编码和融合方法在基础地图验收后确定。

2026-10-28已形成[M5-DESIGN-01具体方案](M5_TERRAIN_PRIOR_DESIGN_20261028.md)：
后续先评审mapping内部私有离线fixture合同，独立保留高度、no-data、采集时间/运行有效期、
注册及米制高度质量，不把它们装入占据概率、observed或last_observed_timestamp。
此处仍为公共接口预留，未冻结新消息/字段。公共ROS/应用地形协议的生产消费、兼容迁移与恢复
须按方案第7节另审；本轮没有TerrainPrior运行实现或DEM占据融合。

后续M5-SW-01已冻结私有schema `m5_terrain_fixture.v1`，定义row-major中心高程、严格布尔
no_data_mask、源/目标水平和垂直fixture基准、独立采集/运行时钟、逐样本米制绝对高程区间及注册z平移区间。
仅内部JSON输入与请求语法校验，无地形查询结果/缓存、公共消息或占据融合。
精确字段/单位与限制见[SW-01合同](M5_SW01_CONTRACT_20261028.md)；公共TerrainPrior仍为预留。

SW-02已在独立离线候选内部实现`m5_terrain_result.v1`：独立terrain_revision/版本/注册身份、
米制高程/区间、原采集时间/运行授权/安装时间和valid/unknown/stale/unavailable；
这不是公共MapQueryResult扩展，原probability/observed/观测时间与ROS字段均不变。
完整私有字段、有效性和恢复见[SW-02说明](M5_SW02_TERRAIN_CANDIDATE_20261028.md)。

后续M5-IFACE-DESIGN-01已交付[公共合同具体提案](M5_IFACE_DESIGN_20261028.md#3-类型与字段提案)：
拟新增独立TerrainHeightQuality/Context/QueryResult/Status及TerrainQuery，float64高程/区间、
明确availability flags、源dataset时间/运行授权/安装/evaluation时间、实例+revision绑定；
另定义结构化公共dataset/recording提案，不在reason/source字段塞JSON。
这只是待确认的具体设计，尚未生成.msg/.srv或冻结公共运行字段；旧占据/传感器合同保持。

用户后续明确授权M5-IFACE-SW-01，现已实现独立`uav_fusionmap_terrain_msgs`的4.msg/1.srv，
其v1字段以源码及[公共合同](M5_IFACE_SW01_CONTRACT_20261028.md)冻结，不扩展任何旧消息。
公开逻辑对象严格字段/枚举，以None表示缺失；codec验证availability flag及规范空槽、
float64质量角色/界、int64时间、实例/revision和请求绑定，实际genpy与独立字节往返通过。
`ufm.terrain.dataset.v1`及`ufm.terrain.recording.v1`已有有界校验/三文件读取，
记录结构校验不等同执行回放；Provider/ROS服务、客户端与地形显示未实现。
验证范围与限额见[EXP-20261028-012](../experiments/2026-10-28-m5-interface-contract.md)。

SW-02后续已实际生产/查询上述冻结协议，Provider将已提交dataset元数据投影为Context，
源采集、安装、请求和evaluation时间分开保留；时钟/域/注册不可用清载荷，no-data或到期不解释为free。
旧消息字段及私有候选不变，实际ROS与兼容/新run恢复见
[EXP-20261028-013](../experiments/2026-10-28-m5-provider-ros.md)；记录仍只具结构校验，执行回放/客户端待SW-03。

2026-10-29 SW-03已实际录制并执行`ufm.terrain.recording.v1`，三文件/schema字段不变，
回放逐事件调用Provider并比对；对外原实例标recorded并另带playback_session_id，不向live流发布。
应用单组≤16结果固定实例/revision/Context，跨到期状态整组拒绝；本地传输失败为空实例unavailable封套，
只在应用内部使用，不冒充服务端正式响应。v1只有clock_transport.online，不能表达的来源错误、非法无结果query/
并发busy标录制incomplete；严格回放拒绝，不加隐藏字段。
详见[交付合同与边界](M5_IFACE_SW03_DELIVERY_20261029.md)、[实际记录](../experiments/2026-10-29-m5-terrain-delivery.md)。

## 11. 研究组件映射与兼容性

| 研究实现 | 系统适配要求 |
| --- | --- |
| 原始[x,y,z,intensity,doppler] | 明确intensity的实际物理量；独立保留系统confidence及时间 |
| Radar四通道体素与归一化 | 按checkpoint对应协议准备；不能以系统字段顺序替代模型通道定义 |
| LiDAR训练监督 | 独立于SensorBundle和forward输入记录target/observed mask；在线不需要LiDAR |
| model_lidar逻辑参考系、C,Z,X,Y张量 | 显式记录frame_id、转换XYZ索引及Body/Radar变换；名称不代表在线硬件 |
| 预测通道0 | 转为probability，保留观测域与输出版本 |
| 预测通道1/2/3 | 为辅助重建结果，不映射成系统confidence/uncertainty |
| 独立uncertainty输出 | 标记类型、空间分辨率、来源和可用性；未验证不得称为已校准 |
| 文件名/帧号 | 关联真实时间和状态；不得当作timestamp或假设固定帧率 |

当前证据见[algorithms/README](../algorithms/README.md)。
新增可选字段可做兼容扩展；改变单位、坐标、通道、有效性或必需字段必须升级契约并
在DECISION_LOG记录迁移、生产者和消费者验证。

## 12. PERF-01-A ROS功能级子集（2026-09-20）

本次新增10条消息，使用本文件v0.1语义的受限fixture编码；既有4条SIM状态消息保持兼容。
新消息此前没有已验收历史bag；消费方需重新构建生成消息，不能把本子集当作完整设备驱动合同。

| 消息 | 已实现编码与限制 |
| --- | --- |
| RadarPoint/RadarFrame | xyz/doppler/power和availability，scan_start/end、Doppler参考系与强度量纲、Quality；fixture扫描无跨度，没有逐点时间扩展 |
| InfraredFrame | width/height、32FC1 float数组、曝光区间和标定ID、Quality；支持2×2和640×512测试图，未实现完整camera_info内参或Image驱动适配 |
| SpatialContext/SensorBundle | Radar/IR/state、参考时刻和变换、calibration_id、同步偏差/pose年龄、pose Uncertainty；不包含LiDAR或训练标签 |
| OccupancyVoxel/OccupancyObservation | 稀疏XYZ索引、概率/observed、confidence可用性及Uncertainty，odom网格/context；origin暂限三元平移，不支持旋转网格 |
| MapCell/MapSnapshot | 最近观测时间、稀疏cell质量、map_id/revision/coverage/source_types；未列出cell为unknown，stale须按观测时间和查询同域时间判断 |
| PerfEvent | 单调墙钟和业务timestamp分别记录；parent_sample_id在本fixture中关联bundle根样本，sample_id标识独立事件，stage/status/reason记录阶段及拒绝 |

placeholder占据sample_id为`perception.occupancy:<bundle_id>`；当前map节点按此已定义fixture
命名恢复旁路关联，未来research适配需明确迁移，不能假定任意模型的sample_id具有该前缀。
报告内资源为observer进程自身。五个最小事件为radar_receive、infrared_receive、
sensor_bundle_ready、occupancy_ready、map_snapshot_publish；真实设备采样到接收年龄仍待实施。
此子集运行证据见[EXP-20260920-001](../experiments/2026-09-20-perf01a-integration.md)。

2026-09-20分段计时扩展沿用PerfEvent字段，通过`--segmented-timing`启用：
`timing.<stage>`的monotonic_ns为区间结束，metric_value_ns为时长，二者相减为开始；
callback标记时长为0。全部关联同一bundle根身份和Radar参考业务时间，即使IR时间有偏移
也不拿IR采样时间替代分段身份。新增事件在对应业务发布后批量发出，旧五事件语义保留。

- sensors：fixture_generation、infrared_generation、infrared_encode、infrared_publish、
  pairing、radar_encode、radar_publish、bundle_encode、bundle_publish。
- perception：bundle_callback、bundle_decode、perception、occupancy_encode、occupancy_publish。
- mapping：occupancy_callback、occupancy_decode、map_update、map_snapshot、map_encode、map_publish。

encode/decode测量业务字典与ROS对象转换；publish测量实际publish调用，包含其同步序列化
及入队。发送至回调使用publish开始与下游回调入口之差，仍含序列化、调度、队列、传输及
反序列化，不能称为纯网络时延。publish区间可能与下游处理重叠，不能与发送至回调相加。
infrared_generation嵌套于fixture_generation，也不能重复累计。报告以逐样本连续边界
分解关键路径，独立分位数不相加。完整与轻量观察保持相同订阅和反序列化，轻量仅省略
像素min/max扫描，不提供像素内容校验通过的结论。

2026-09-20线格式成本诊断进一步增加本机旁路产物（不改变ROS消息字段）：
`--wire-profile`在实际生成消息serialize/deserialize调用周围记录monotonic start/end、
thread_cpu_ns、wire_bytes和身份；成功调用区间与发布/回调标记按bundle身份关联。
sensor/perception/observer分别在退出时写入独立wire.json，仅供实验核查，不作为业务输入。
报告连续分解publish至serialize、serialize、传输/排队/调度混合项、deserialize、
deserialize至回调；不可用混合项推导纯网络时延。

`metadata`观察模式取消观察器IR/bundle订阅，必须启用wire-profile，由生产端publish
记录及感知端deserialize/callback记录核对身份/数量/时间/尺寸。当前独立IR话题没有其他
消费者，metadata模式该路只可声明发布尝试，不能声称有独立IR线格式接收；实际图像仍
随bundle到感知端。完整像素校验仍只由full模式提供。资源新增为本次进程树采样CPU/RSS，
明确采样窗口、采样耗时及代表CPU频率，不能替代机载功耗/持续性验收。

2026-09-20独立异步入口沿用上述ROS编码，未新增字段。Radar/IR各自保留原采样
timestamp/sample_id；Bundle中的两个序号无需相同。独立生产与接收元数据记录于
各自audit.json，PerfEvent中radar_receive改为此入口的真实Radar回调时刻，已选择IR
的infrared_receive关联其原接收时刻。新入口另外报告生成至接收/占据的耗时，不能
与旧成对fixture生成起点混用。配对等待使用单调墙钟，data_age使用当前公共clock
减Radar采样时间。详细边界见[异步规则](PERF01A_ASYNC.md)。

## 2026-10-10训练fixture私有记录（非公共ROS消息）

`configs/sens_train_01_fixture.yaml`的`mode=training_data_generation`仅供独立训练
launch使用。ROS `/uav/training/lidar_supervision`是`std_msgs/String`，载荷为
JSON序列化的`schema_version=0.1`记录；记录器按run、clock、scene、calibration
逐条验证，exclusive-create写成JSONL。`radar`和`infrared`分别遵守现有ROS消息
编码，`lidar`包含`header.frame_id=training_lidar`、`scan_start/scan_end`、
`points[x,y,z,point_time_ns]`及仅诊断用的`first_hit_odom`。`supervision`独立保存
`frame_id=training_lidar`、`grid_origin_m`、`grid_resolution_m`、`grid_shape`及扁平
`target/observed_mask`，扁平索引为`(x*shape_y+y)*shape_z+z`；
`target`只取`free/occupied/unknown`，仅前两者可使mask=true。
`observed_mask`逐元素必须是JSON布尔值，不接受数值1/0作为同义代替；
顶层记录还包含`state_sample_id/run_id/clock_id/scene_id/calibration_id`。
无回波、遮挡后方和未扫过的网格均unknown、mask=false；记录不注入在线
SensorBundle、研究forward、定位或地图。私有JSON不表示已冻结公共LiDAR消息；
详细验证见[EXP-20261010-001](../experiments/2026-10-10-sens-train-01-fixture.md)。

2026-10-13同一私有JSON话题已通过schema `0.2`的非零扫描ROS传输与落盘验证，
未改变公共消息字段。`--fixture motion`保存200ms扫描和全部三条射线时间槽，
两个首回波带`raw_xyz/time_offset_ns/ray_index/pose_sample_ids`及扫描中点补偿坐标；
无回波槽保留但不生成free证据。Radar/IR仍使用瞬时fixture载荷。独立runner将
落盘JSON与监督ROS接收全载荷精确对账，并核对状态/clock身份及Radar/IR数值，
见[EXP-20261013-005](../experiments/2026-10-13-sens-train-motion-ros.md)。
配置中的int64纳秒值通过节点本地YAML读取，不经过ROS1参数服务器的32位整数槽；
仅路径与小整数运行参数通过ROS参数传输。真实设备时间记录仍是独立的
`device_time_record_v1`，不因仿真schema `0.2`通过而获得真实同步状态。

2026-10-28 SENS-VIS-01独立Gazebo场景复用既有公共字段：Radar原始PointCloud2包含
`x/y/z/doppler/power`，单位为m、m/s与任意未标定强度；IR Image为320×240的32FC1，
业务InfraredFrame仍声明`value_unit=fixture_intensity`，不是Kelvin温度。
场景源AircraftState为`frame_id=scene_world/source_type=simulation/state_source=ground_truth`，
显式注册后由既有state_adapter转换为odom/derived，state_source不变；默认PX4状态路径不变。
`calibration_id=gazebo_sensor_scene_mount_v1`仅表示合成安装配置，SensorBundle没有训练监督字段。
地图仍为fixture占位输出，不把相机热强度或几何真值当成模型质量；详见
[场景数据链与单位](SENSOR_SCENE_VISUALIZATION.md)。公共ROS消息版本/字段保持不变。

2026-10-29 [SIM-MOTION-SW-03](SIM_MOTION_SW03_DELIVERY_20261029.md)在相同公共字段下
交接同FDM真值/真实Radar/IR→Bundle→placeholder→M1→公开query/replay。
新运动模式pose_age_ns=0及radar_ir_delta_ns=0经实际10帧核对；概率仍为fixture占位、质量缺失，
不因真实动力学/真实渲染而改成model或measured质量证据。失败时未提交tick的raw不生成新占据。

## 公共flight v2离线合同（2026-11-02）

[SIM-FLIGHT-SW-03A](SIM_FLIGHT_SW03A_CONTRACT_20261102.md)新增独立ufm_flight_contract，
复用现有SceneFrame/SceneStep/SceneCaptureAck真实生成类型，显式protocol_version=2；旧25定义及v1编码不改。
SceneFrame严格限定0..10000步、timestamp=step×4000000ns、scene_world/ground_truth、
注册jsbsim_cg_to_flight_enu_v1；ground初始锚点[0,0,.5]、z>.2m、距锚点≤250m。
仅step>7500且step%25=0允许采样，共100点/30.1..40秒，原时间不裁剪。
准备期response两采样时间均None，没有raw/ACK/Bundle不解释为空观测、free或地图可用。
ACK成功/失败均只接受采样步，measurement_timestamp必须为本步原采集时间；没有实际采集时间时
不能补造失败ACK，运行端须按未收到回执/事务失败处理。失败响应可以保留本步真实部分收据。
所有嵌套对象精确键集，拒绝额外训练监督字段；confidence/uncertainty保持不可用，禁止补造质量。
现有SceneStepResponse外层无版本，因此v2强制真实已应用v2帧，无帧失败在v2拒绝；
应用前失败留SW-03B走服务错误，不能伪造applied_frame。旧v1无帧失败仍保持。
固定profile/端点和严格wire扫描、真实genpy/交叉拒绝已验证；没有运行端点/插件或长窗执行。
