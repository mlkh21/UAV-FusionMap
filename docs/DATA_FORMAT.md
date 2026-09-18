# 数据格式与接口语义

版本：v0.1；更新日期：2026-09-16；责任角色：system_architect。
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

available时数值必须有效且符合该物理量约束；unavailable时value为null。
概率、confidence与uncertainty含义不同，不定义通用的互相换算公式。
模型分数未经校准不得标为已校准占据概率误差或位置方差。

## 4. RadarFrame

Radar驱动的ROS原始传输可以使用`sensor_msgs/PointCloud2`，但PointCloud2只是载荷容器，
不是完整业务合同。设备适配器必须校验PointField名称、类型、单位、字节序、逐点时间、
Doppler符号/参考系及RCS/SNR/intensity含义，再形成RadarFrame；不允许只改字段名完成接入。

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

AircraftState包含header、position[3]、orientation_xyzw[4]、linear_velocity[3]、
body_frame_id、velocity_frame_id、state_source和quality。state_source区分ground_truth
与estimated。position/orientation表示Body在header.frame_id下的位姿；速度必须有明确
坐标系。位姿协方差按[x,y,z,rx,ry,rz]排列，缺失时标不可用。

后续可从同一权威状态派生`nav_msgs/Odometry`兼容镜像，用于通用ROS工具和TF承载；
Odometry不含run_id、clock_id、sample_id、source_type、state_source、status/reason和明确的
缺失质量语义，不能单独替代AircraftState。两者并存时必须保持同一采样时间、frame、
child frame和唯一odom→base_link发布责任，不能形成两套冲突状态源。

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
- pose_uncertainty：位姿Quality/协方差可用性。
- calibration_id与state_source：标定版本及估计/真值来源。

sensors生成状态与标定上下文，perception在改变网格参考系时组合对应变换并传给mapping。
变换不可用时不得空间融合；来源和时间必须保持可追踪。

### 7.1 训练监督记录（非运行时SensorBundle）

训练数据生成模式可记录独立的LiDAR监督点云及标签清单。记录至少包含run_id、sample_id、
clock_id、扫描起止与逐点时间可用性、frame_id、calibration_id、来源/模拟等级、与目标
Radar/IR样本的关联，以及由射线覆盖生成的occupancy target和observed mask版本。
未被射线覆盖、被遮挡、超量程或FOV外区域保持unknown；无点不得直接标为free。

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

## 10. TerrainPrior：后期接口预留

DEM输入至少包含terrain_id、版本/来源、时间及有效期、水平坐标参考、垂直高程基准、
grid、resolution、origin、height_unit、no_data_mask和height_uncertainty。
进入mapping前必须完成到地图坐标的注册；缺少基准时不得融合。
本节仅定义接入约束，详细栅格编码和融合方法在基础地图验收后确定。

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
