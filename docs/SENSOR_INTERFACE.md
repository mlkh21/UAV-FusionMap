# 传感器、状态与ROS连接接口

版本：v0.1；更新日期：2026-10-14；责任角色：sensor_engineer / integration_engineer。
状态：SIM-01A状态/时钟与PERF-01-A功能级fixture连接已实现；fake Radar/IR已支持可选
FOV、量程、噪声及扫描/曝光时长；真实设备接口仍为设计。
实际运行结果和限制见EXPERIMENT_LOG。

## 1. 生产者与消费者

| 生产者 | 输出 | 允许的业务消费者 | 职责 |
| --- | --- | --- | --- |
| simulation | AircraftState、SceneDescription、源时钟 | sensors | 提供场景、源状态和时间，不输出系统占据结果 |
| 设备驱动/fake采集节点 | PointCloud2、Image或设备消息 | sensors设备适配器 | 保留原始载荷，不把字段名当物理合同 |
| sensors设备适配器 | RadarFrame、InfraredFrame、ImuSample | sensors同步/状态适配节点 | 校验采集时间、单位、字段和原始坐标 |
| sensors同步/状态适配 | SensorBundle | perception | 绑定参考时刻、IR、标定、状态与同步质量 |
| fake LiDAR监督节点（仅训练配置） | 独立监督点云/标签记录 | 训练样本构建器 | 不进入SensorBundle、forward、定位或mapping |
| perception | OccupancyObservation | mapping | 输出统一占据与观测域，附时空上下文 |
| mapping | MapSnapshot、MapQueryResult | application | 输出地图、有效范围、新鲜度和质量 |

记录与诊断可以旁路订阅已公开数据，但不得把这些旁路变成业务融合入口。
独立评测可使用明确标识的真值，research感知不得读取真值目标。

## 2. 功能级传感器交付

第一阶段先验证已知几何场景与正确字段，不承诺完整电磁/热成像物理真实性。

| 传感器 | 功能级最小交付 | 参数化阶段 | 后期扩展 |
| --- | --- | --- | --- |
| Radar | 带坐标、Doppler/强度可用性和时间的点集 | FOV、range、frequency、噪声、丢帧 | 多径、虚警、环境影响 |
| IR | 带camera_info及时间的热图/功能级图像 | FOV、分辨率、频率、曝光、噪声 | 热辐射和复杂环境效应 |
| IMU | 明确比力/加速度语义的惯性数据 | 频率、偏置、噪声、时间延迟 | 更完整误差模型 |
| 状态适配 | 已有估计或真值位姿/速度，显式来源 | 时间插值、协方差、状态失效处理 | 后续独立定位需求 |
| LiDAR监督 | 与fake Radar/IR同步的点云、target及observed mask | FOV、range、扫描与噪声 | 仅训练质量扩展，不成为运行传感器 |

2026-10-03起，PERF-01-A异步配置中的`fake_radar`和`fake_infrared`可注入功能级参数：
Radar的`fov_deg`为[水平deg,垂直deg]、`max_range_m`为m、位置/强度噪声为各自fixture
单位标准差、`scan_duration_ns`为ns；IR的`background_value`和`noise_std`使用
`fixture_intensity`、`exposure_duration_ns`为ns。`sensor_noise_seed`使同一run/sequence
跨生产进程可重复。默认`null`/0保持历史固定载荷；无回波只表示没有观测返回，不表示自由空间。
这些参数用于接口、同步和故障测试，不是ARS548、Micro III Lite或任何真实设备的标定/性能结论。

`fake_infrared.hotspots`是二维功能级场景输入：每项使用`x_px`、`y_px`、`radius_px`（像素）
和`value`（`fixture_intensity`增量），按行优先布局在圆形区域内叠加；它不表示温度、K、DN
或辐射功率。默认空列表保持全背景图兼容。热点配置只供fixture和接口测试使用，不能作为
真实热成像标定或研究模型质量证据。

参数表必须给出单位和适用场景。未建模power、confidence或uncertainty时保留字段并
标为不可用，不捏造高置信值。参数数值在开发计划中的性能基线任务确认。

## 3. 时间同步

1. 仿真时间表示仿真开始以来的纳秒，clock_id明确标识sim域；不与系统UTC混用。
2. 设备时钟若不是公共时钟，保留源timestamp并记录到公共域的转换、偏移/漂移估计及误差。
3. Radar默认参考时刻为扫描中点；IR为曝光中点；IMU和状态为各自采样时刻。
4. SensorBundle以Radar参考时刻为准，IR选取时间最近且在允许误差内的观测。
   同一个IR样本可关联不同Radar观测，但保留原sample_id和时间；重复Bundle不得重复更新地图。
5. 位姿在参考时刻插值，必须有有效时间覆盖；没有覆盖或超过允许外推范围时标为不可用。
6. 扫描内运动不可忽略时，使用逐点时间及状态进行补偿并记录状态；缺失信息时声明限制。
7. 暂停和倍速不能改变采集时间语义；重启或时钟回退进入新run_id。

同步参数需明确max_radar_ir_delta_ns、max_pose_age_ns、max_wait_ns、最大缓存长度和
时钟转换误差上界。当前不填未经验证的默认数值，见DEVELOPMENT_PLAN中的性能预算。

高速预算至少考虑平移近似`e_translation = v_max × delta_t`，以及角速度和距离造成的
角运动误差。示例：50m/s与20ms对应1m平移误差，仅用于说明，不能作为项目目标参数。

## 4. 标定与坐标责任

- 每份标定记录calibration_id、源/目标frame、T_target_source、单位、有效区间和质量。
- camera_info对应实际输出图像尺寸；裁剪/缩放/去畸变需同步改变内参或校正状态。
- 设备原生坐标经sensors适配为约定坐标，源定义仍保存在配置与记录中。
- Radar/IR到Body外参由sensors维护；Body运动来自已声明的状态源。
- perception若使用model_lidar参考系，显式组合并记录Radar到模型参考系的转换。
- mapping仅使用OccupancyObservation内的变换上下文，不自行读取外参文件或订阅原始状态。
- 当前PX4 AircraftState是唯一已实现定位权威状态；可选Odometry只作兼容镜像。
  mapping不得直接订阅最新Odometry，传感器同步节点必须在Radar参考时刻插值状态。

具体方向、发布责任与验证样例见[COORDINATE_SYSTEM](COORDINATE_SYSTEM.md)。

## 5. 输入异常和降级行为

| 情况 | 必须执行的行为 | 不允许的行为 |
| --- | --- | --- |
| Radar未到达/超时 | 有界等待后发健康状态；无有效观测时输出unavailable | 无限积压或合成全自由观测 |
| IR缺失或不同步 | 标degraded；仅允许已明确支持并验证的后端继续，否则unavailable | 把零图像伪装成真实IR继续推理 |
| 标定/位姿缺失 | 可记录原始数据；空间融合输出unavailable | 使用单位矩阵假装已对齐 |
| 格式或单位不兼容 | 拒绝该观测并记录reason | 只改字段名或静默截断通道 |
| 帧重复/乱序 | 根据run_id和sample_id去重；v0.1丢弃已处理参考时刻以前的迟到Bundle并记录 | 按到达顺序累积过期证据 |
| 模型超时/失败 | 清晰输出unavailable，保留输入身份与耗时记录 | 静默回退到未标注的占位模型 |
| 上游持续不可用 | 地图停止添加证据，维护老化和查询状态 | 不断刷新旧地图timestamp让其看似新鲜 |
| 仿真重置 | 新run_id，新运行记录及新地图 | 沿用旧地图累计证据 |

disabled模式仍应发送状态上下文与不可用占据消息，使地图能跟踪运行状态。
完全断流时，地图通过自身同域时钟/新鲜度检查返回stale或unavailable，不订阅越层数据。

## 6. ROS话题与服务候选

以下名称是设计预留，不代表现有接口。ROS1/ROS2和消息类型在环境验证后确定。

| 候选名称 | 契约 | 发布/服务方 → 消费/请求方 |
| --- | --- | --- |
| /uav/sim/state | AircraftState | simulation → sensors |
| /uav/sensors/state | AircraftState | sensors内部状态适配 → 后续内部同步及记录 |
| /uav/sim/scene | SceneDescription | simulation → sensors |
| /uav/sensors/radar/raw | PointCloud2或设备消息 | Radar驱动/fake采集 → Radar设备适配 |
| /uav/sensors/radar | RadarFrame | sensors采集 → sensors同步及记录 |
| /uav/sensors/infrared/raw | Image或设备消息 | IR驱动/fake采集 → IR设备适配 |
| /uav/sensors/infrared | InfraredFrame | sensors采集 → sensors同步及记录 |
| /uav/sensors/imu | ImuSample | sensors采集 → sensors状态适配及记录 |
| /uav/sensors/bundle | SensorBundle | sensors → perception |
| /uav/perception/occupancy | OccupancyObservation | perception → mapping |
| /uav/map/snapshot | MapSnapshot | mapping → application |
| /uav/map/query | `uav_fusionmap_msgs/MapQuery` / `MapQueryResult`（可选单点服务） | application请求 → mapping响应 |
| /uav/diagnostics | 模块状态与原因 | 各模块 → 记录/诊断 |
| /uav/localization/odom | nav_msgs/Odometry（默认关闭的可选镜像） | state_adapter → ROS兼容工具；非mapping业务输入 |
| /uav/training/lidar_supervision | 待实现任务确认 | fake LiDAR → 训练记录器；仅training配置 |
| /uav/training/occupancy_target | 待实现任务确认 | 标签构建器 → 训练记录器；仅training配置 |

节点包装只负责消息转换与调用所属业务模块。ROS传输中的有效标志必须保持逻辑契约
中的null/unavailable含义。/clock（若所选ROS方案使用）仅承载公共仿真时间。

### T-14状态兼容镜像（2026-10-14）

`state_adapter_node`仍是`/uav/sensors/state`的唯一状态适配发布者；开启
`publish_odom`时由同一条适配状态发布`/uav/localization/odom`，开启`broadcast_tf`时
由同一节点发布唯一动态`odom -> base_link`。两个开关默认`false`，避免在旧启动图中
无意增加第二套状态来源。Odometry的header时间直接由AircraftState非负纳秒转换，
`header.frame_id=odom`、`child_frame_id=base_link`，twist使用base_link坐标；质量未知
时不填造协方差。terminal/unavailable状态不发布Odometry或TF，地图仍不得订阅该镜像，
继续只消费OccupancyObservation中的观测时刻SpatialContext。

已在独立`sim01_smoke.py --fixture --t14-compat`中验证有效状态镜像、TF时间/帧、未知
协方差、terminal后的停止发布、Conda解释器和清理；该验证不是实机定位质量验收。

## 7. 运行连接与后续验收

### SIM-01A已确认连接

Noetic下`/mavlink/from`由simulation入口读取：仅接受sysid/compid=1/1、正确CRC与帧，
HIGHRES_IMU推动唯一`/clock`；LOCAL_NED/BODY_FRD、AUTOPILOT ODOMETRY形成源状态。
`/uav/sim/state`及`/uav/sensors/state`均使用uav_fusionmap_msgs/AircraftState；
`/uav/diagnostics`为diagnostic_msgs/DiagnosticArray。内部适配状态不供mapping越层订阅。

PREPARING在有效状态采样时间有时钟覆盖且稳定10秒后进入ACTIVE，准备期reset变化
清缓存重启观察；不补发预热旧状态。ACTIVE后reset变化或任意阶段IMU同源回退进入
FAULT，发布终止并停止本run的有效输出；监督器收到终止后结束本次联调。新运行须新run_id。
IMU回退理由注明源回退或乱序，不能仅凭单包断言真实重启。

源/接收端分别门控timestamp≤本端最新有效/clock，领先状态按源时刻排序等待；
两端缓存上限100、等待0.5秒墙钟。IMU/ODOMETRY分别2秒单调墙钟断流看门狗，
初次启动最多等待60秒。/clock不依墙钟推进，重复/停流不生成新时刻。
参数见[sim01_state.yaml](../configs/sim01_state.yaml)，仅为首轮接口冒烟参数。
ROS订阅/发布队列为源入口1000、状态/clock各100、诊断20；跨话题不假设到达顺序。
本步不发布TF或ImuSample，不更改MAVROS PASSTHROUGH配置，不涉及控制指令。

上述是SIM-01A时的候选列表，不可按当时的“当前不存在”推定后续状态。
截至2026-10-10，`/uav/training/*`已有隔离fixture图，PointCloud2仅有
离线fixture解码/适配函数；`/uav/sensors/radar/raw`采集节点、真实设备
PointCloud2适配、`/uav/localization/odom`和独立Localization仍未实现。

### 后续阶段

建议启动依赖顺序：公共时钟/仿真 → 传感器及状态适配 → 选定感知模式 → 地图 → 应用。
各节点可以先启动并报告等待输入；业务ready需要其必需接口有效，不能仅依据进程存在。

Phase 1验证仿真状态到ROS及回放；Phase 2验证传感器到SensorBundle；占位模式可
帮助后续地图联调；Phase 3独立验证真实研究后端；Phase 4验证地图到应用接口。
Phase 2另设training_data_generation启动图，同步生成fake Radar/IR输入与fake LiDAR
监督记录；inference启动图必须证明无LiDAR生产者、订阅者和标签泄漏。

### Local Map单点查询软件子范围（2026-10-14）

`/uav/map/query`由既有mapping节点可选提供，启动参数`enable_query`默认`false`。
启用后服务回调与OccupancyObservation更新共用同一`SparseLocalMap`实例和`RLock`，
不建立旁路地图缓存。请求必须携带非空map/frame/run/clock身份、非负同域纳秒时间和
有限地图坐标；错误请求返回service error，合法但身份或覆盖不匹配返回
`unavailable`/`unknown`，不猜测自由空间。

free/occupied分类只有在`free_threshold`与`occupied_threshold`成对配置且满足合同约束时
启用；fixture的0.3/0.7仅用于软件验证，未成为飞行默认参数。空地图、五类状态、
年龄边界、断流恢复、重复输入、并发只读和图隔离已由独立ROS短测覆盖；运行证据见
[EXP-20261014-010](../experiments/2026-10-14-local-map-query-ros.md)。该子范围不包含
滚动窗口、概率累计、TF查询、真实传感器输入、机载性能或对照试验。

### 可选滚动Local Map fixture（2026-10-14）

新增`bash ros_ws/sim01_env.sh python ros_ws/local_map_query_run.py --mode rolling`
独立ROS短测入口（Python进程需为Radar-Diffusion）。专用
`ros_ws/launch/local_map_rolling_fixture.launch`将感知节点`rolling_grid`和地图节点
`rolling_enabled`明确设为true；既有启动入口和类参数均默认false，故旧固定网格
模式不变。fixture注入含观测时刻SpatialContext的SensorBundle，上游感知计算
轴对齐odom格网，mapping仍仅消费OccupancyObservation并可选提供同实例查询。
允许的公共`/clock`是ROS仿真时间基础设施，不是mapping新增的定位/传感器
业务输入。输入失效不能移动地图或刷新旧单元；恢复只增加显式观测的单元。
详见[EXP-20261014-011](../experiments/2026-10-14-local-map-rolling.md)。
仅验证fixture基础平移/偏航/断流，不包含真实状态源、设备时间、正式性能
和对照试验。

验收记录包含实际消息、频率、队列/QoS、同步残差、端到端数据年龄、丢帧和异常状态。
记录回放保留原始时间、frame、run来源和标定版本；换机器不能依赖原绝对路径。

### PERF-01-A短时入口（2026-09-20）

`bash ros_ws/sim01_env.sh python ros_ws/perf01a_run.py --duration-s 8`统一管理独立master、
旁路接收器和四个薄节点。运行器先订阅，sensor/perception/mapping确认其发布端连接建立后
设置当前run的ready，source才开始固定20Hz样本；source发布完保持运行，运行器排空后统一停止。

已实现话题：`/uav/sim/state`、`/uav/sensors/state`、`/uav/sensors/radar`、
`/uav/sensors/infrared`、`/uav/sensors/bundle`、`/uav/perception/occupancy`、
`/uav/map/snapshot`与旁路`/uav/perf/events`。业务发布队列100、事件发布队列500，
runner业务接收队列1000、事件2000。source是本入口唯一clock发布者。
sensor只在状态被clock覆盖时生成同一时刻的Radar/IR，每个状态时刻只发送一次。
参数取自预算中的fixture频率、同步/pose阈值和老化时限；真实传感器时序与故障场景另验。
这是静止功能级测试，非PX4状态链集成验收；raw驱动、训练支路、TF、查询及research仍待实现。

后续场景入口支持`--scenario full_ir|sync_boundary|sync_timeout|ir_missing|pose_stale`，
配置见[perf01a_scenarios.yaml](../configs/perf01a_scenarios.yaml)。sensor现复用StateClockGate
的100条pending/0.5秒墙钟超时，防止future状态被最新槽覆盖；源频率仍20Hz。
IR缺失或时空门限超限时不发布SensorBundle及新增地图证据，通过PerfEvent显式记录拒绝；
固定注入窗口结束后处理正常样本。本次故障模拟不是独立设备消息队列的匹配/丢包实现。

分段/观察器对照：运行器支持`--segmented-timing`、`--observer-mode full|light`和
`--image-buff-size`。默认full、不开新增分段、读块65536字节；light仍订阅完整消息，
只省略像素扫描，身份/计数/时间/丢帧检查保留。大图读块参数同时作用于感知bundle
与观察器IR/bundle订阅，队列深度不变；4MiB候选未显示稳定收益，不修改默认值。
`perf01a_compare.py`按预登记AB/BA串行执行同负载对照，默认启用分段；
`--no-segmented-timing`用于原五事件控制。结果见
[EXP-20260920-003](../experiments/2026-09-20-perf01a-segmented-timing.md)。

后续成本诊断支持`--wire-profile --sample-resources`以及`--observer-mode metadata`。
metadata取消观察器的大图订阅，同时强制启用两端轻量记录；full/light中IR/bundle连接
分别为1/2，metadata为0/1，启动就绪与审计共同核查该拓扑。消息类型、业务队列和数据内容
保持；metadata独立IR无接收者，其publish跳过实际序列化，不能把该路记作交付成功。
`--receive-backend standard|numpy`仅选择感知bundle接收解码，numpy在边界恢复原Python
容器并保持相同线格式。候选未达到预登记收益条件，默认保留standard。
三模式轮换对照及单候选复测见
[EXP-20260920-004](../experiments/2026-09-20-perf01a-wire-cost.md)。

### PERF-01-A独立异步入口（2026-09-22）

新增`perf01a_async_run.py`，独立Radar与IR进程向原话题发布，sensors匹配节点实际
接收后构建Bundle；原成对入口保留作历史对照。消息字段不变，source仍是唯一clock
发布者。默认Radar20Hz、IR50Hz零相位，100Hz静止状态与1ms clock；40ms仿真匹配
截止、0.5秒墙钟等待上限，5ms同步门限和10ms历史位姿年龄保持。

匹配按参考时间有序输出，IR最近采样优先、等距较早采样、允许复用；已超过截止
的输入不能补救旧窗口，未匹配不发布有效Bundle或自由证据。固定输入的预期在启动前
由独立oracle登记，零相位整秒窗口只应配对一半Radar。统计生成、发布、实际接收、
采用/未采用、超时、淘汰和意外损失，未采用IR不计为传输丢帧。

时序、缓存、计时起点和运行范围见[异步规则](PERF01A_ASYNC.md)，实际结果见
[EXP-20260922-001](../experiments/2026-09-22-perf01a-async.md)。2026-09-23增设
`--speed-mps 35|50|70`功能级直线fixture和`--pairing-policy exact`候选；源状态在
采样时刻运动，Radar根据固定世界障碍物生成相对测量。老化查询、运动精度和大图失败
边界见[EXP-20260923-001](../experiments/2026-09-23-perf01a-motion.md)；不将其写成
PX4在线状态闭环、物理传感器或高速实时验收。
2026-10-09异步入口增设仅供诊断的`--ir-borrow-image`，默认关闭；
开启时 matcher IR 回调暂借 ROS 图像列表，缓存立即复制为独立所有权。
通用`from_ros_infrared`默认仍返回独立列表。70m/s大图A-B-B-A虽减少
局部解码耗时，但端到端P99中位数仅下降7.83%，未达预登记采纳门槛；
不作为线上默认优化、数值守恒替代证据或PERF-01达标依据。详见
[EXP-20261009-001](../experiments/2026-10-09-perf01a-ir-decode-copy.md)。

### SENS-TRAIN-01训练专用入口（2026-10-10）

`sens_train_01.launch`是独立功能级ROS图：单`/clock`源发布`/uav/sim/state`，
训练fixture节点使用估计AircraftState及具名仿真外参构造
`/uav/training/radar`（RadarFrame）和`/uav/training/infrared`（InfraredFrame），
额外发布`/uav/training/lidar_supervision`（std_msgs/String内版本化JSON）；
仅训练记录器和短测观察器订阅监督话题。首版ROS fixture的采集参考时间为中点、
与状态样本同刻且仅零扫描时长；配对偏差上限5ms、历史位姿年龄上限10ms，
不修改在线PERF-01-A规则。独立runner按唯一run记录JSONL、20帧收据和实际
发布订阅图；[实测证据](../experiments/2026-10-10-sens-train-01-fixture.md)。
既有`perf01a_async.launch`无训练节点、无监督订阅；训练launch无
SensorBundle/perception/mapping。新记录为仅训练副路，并非通用LiDAR设备驱动
或正式公共消息；其他推理启动配置仍须在启用前各自检查。

2026-10-10增加[第二已知场景](../configs/sens_train_01_multiray_fixture.yaml)，
双障碍对应两个明确投影的IR热点及两束前向/离轴LiDAR射线；运行器以
`--fixture multiray`验证每一帧两个首回波和两处占据、遮挡后方unknown。
仅穿过障碍内部才确认命中，擦边未知；另一束射线不得将已命中体素改为free。
最新[实际ROS短测](../experiments/2026-10-10-iface01-sens-train-multiray.md)已通过，
但不承诺非零扫描或多场景数据集质量。

2026-10-12增加非零扫描的**纯函数训练fixture**：
[`sens_train_01_motion_fixture.yaml`](../configs/sens_train_01_motion_fixture.yaml)使用
schema `0.2`声明200ms扫描、三条有序逐点时间偏移和同run的AircraftState历史。每条有
效回波同时记录传感器坐标原始点、采集时刻、射线索引、状态sample_id，并补偿到扫描
中点坐标；位置线性插值、姿态最短弧SLERP，缺历史、乱序、跨run/clock或未覆盖扫描
区间即拒绝。无回波射线保持unknown，不能由无点推导free。截至该轮该实现只验证
`sensors/ufm_sensors/training_supervision.py`的离线函数，现有`sens_train_01.launch`
仍为零时长ROS v0.1图，未新增ROS逐点时间字段、真实驱动、真实时钟或在线LiDAR输入。
记录验证器同时要求保存全部射线的`ray_time_offsets_ns`，并拒绝重复`ray_index`、
畸形点记录或与配置不一致的时间槽；因此无回波射线仍有可审计的采集时间，即使不会
产生LiDAR点记录。该校验不改变现有ROS v0.1消息和发布订阅图。

2026-10-13 `--fixture motion`已接入非零扫描训练ROS记录路径：源补首尾状态，
状态和clock均覆盖200ms扫描末端才发布中点对应的Radar/IR与独立监督JSON。历史
缓存上限64、未来状态上限2；未完成样本且输入停滞5s墙钟后停止。配置在各节点
本地读取，不再整体上传ROS参数服务器；不改变纳秒值或现有Radar/IR消息。
runner记录状态、clock、Radar、IR、监督收据，核对源发布/消费计数、全载荷、几何
oracle与唯一clock/state源。`single/multiray`零时长入口回归通过；
[验证记录](../experiments/2026-10-13-sens-train-motion-ros.md)。此处逐点时间仅在训练
JSON中，不是公共RadarPoint时间扩展或设备时钟验证；在线launch不变。

### IFACE-01 PointCloud2受限离线fixture（2026-10-10）

`ros_ws/radar_raw_bridge.py`通过ROS标准PointCloud2解析器读取完整声明字段，
`sensors/ufm_sensors/radar_raw_adapter.py`核对run/clock/sample、Radar局部frame、
扫描中点及单位/方向，转换为既有RadarFrame dict，可由原codec进行ROS消息往返。
示例配置仅为[无设备fixture](../configs/iface01_radar_fixture.yaml)，要求同域零跨度
扫描、position=m、Doppler=m/s且显式标明toward/away方向，强度声明quantity/unit；
拒绝未知原始PointField（包括可能的逐点时间）、无语义字段、非零扫描、真实设备
mode、错误frame/时钟和非有限数值。无回波保留空点集，不产生自由占据。
本入口尚无raw ROS订阅节点，未启用线上生产者/消费者或时钟转换；设备协议、
逐点时间和质量来源取得并独立审查之前不得声称真实驱动已接入。

### 型号特定设备时间合同（2026-10-13）

已按项目型号完成字段级审查并增加离线适配器：ARS548只接受检测列表级设备时间，
Mid-360接受`timebase`与`offset_time`展开的训练点逐点时间。Mid-360的同步类型必须
来自原始包或设备状态；仅有官方`CustomMsg`时标记为未提供，不把ROS接收时间当成
采集时间。ARS548检测项没有逐点时间，适配器不得为检测点均摊或复制列表时间。

该合同由[`device_time_adapter.py`](../sensors/ufm_sensors/device_time_adapter.py)
和[`test_device_time_adapter.py`](../tests/test_device_time_adapter.py)验证，尚未
连接真实驱动、写入ROS公共消息或测量跨设备时钟残差。Mid-360输出仅用于训练监督，
不进入在线SensorBundle、perception、定位或mapping。

### 设备时间记录器输入审计（2026-10-13）

[`device_time_record.py`](../sensors/ufm_sensors/device_time_record.py)定义
`device_time_record_v1`落盘合同：每条记录同时保存设备采集时间、主机接收时间、各自
`clock_id`、设备身份和原始解码payload。`time_mapping_status`固定为`unmapped`，
未取得同一公共时钟的偏移/漂移/误差证据前禁止填充映射字段。该模块可接受已解码的
ROS `__slots__`消息转换结果，但不订阅ROS、不导入驱动、不改公共消息。

ARS548的记录只保留检测列表时间；Mid-360的逐点时间必须能回算，原始`time_type`
必须有原始包传输来源。记录流拒绝重复`sample_id`、混合型号/时钟、篡改设备时间和
虚构时钟映射。该审计仍是设备到位前的离线合同，不代表真实设备回放或PERF-01。
2026-10-15软件审计进一步拒绝同一设备流混用`frame_id`、篡改
`time_source`/同步来源和逐点时间语义，保留已有收件乱序兼容；独立训练
矩阵增加命中前保守free覆盖及回波线段包围盒外假free拒绝检查，私有JSON的`observed_mask`只接受
布尔值。见[EXP-20261015-001](../experiments/2026-10-15-iface01-sens-train-audit.md)；
不声明设备时钟已映射或真实硬件已接入。
