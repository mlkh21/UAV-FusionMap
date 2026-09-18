# 传感器、状态与ROS连接接口

版本：v0.1；更新日期：2026-09-16；责任角色：sensor_engineer / integration_engineer。
状态：SIM-01A状态/时钟连接已确认并实现；其余传感器/业务接口仍为设计。
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
| /uav/map/query | MapQueryRequest/Result | application请求 → mapping响应 |
| /uav/diagnostics | 模块状态与原因 | 各模块 → 记录/诊断 |
| /uav/localization/odom | nav_msgs/Odometry（可选镜像） | 状态适配 → ROS兼容工具；非mapping业务输入 |
| /uav/training/lidar_supervision | 待实现任务确认 | fake LiDAR → 训练记录器；仅training配置 |
| /uav/training/occupancy_target | 待实现任务确认 | 标签构建器 → 训练记录器；仅training配置 |

节点包装只负责消息转换与调用所属业务模块。ROS传输中的有效标志必须保持逻辑契约
中的null/unavailable含义。/clock（若所选ROS方案使用）仅承载公共仿真时间。

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

上述`/uav/localization/odom`、raw传感器和training话题均为设计候选，当前不存在；
不得据表格声称已实现独立Localization、PointCloud2适配或fake LiDAR监督节点。

### 后续阶段

建议启动依赖顺序：公共时钟/仿真 → 传感器及状态适配 → 选定感知模式 → 地图 → 应用。
各节点可以先启动并报告等待输入；业务ready需要其必需接口有效，不能仅依据进程存在。

Phase 1验证仿真状态到ROS及回放；Phase 2验证传感器到SensorBundle；占位模式可
帮助后续地图联调；Phase 3独立验证真实研究后端；Phase 4验证地图到应用接口。
Phase 2另设training_data_generation启动图，同步生成fake Radar/IR输入与fake LiDAR
监督记录；inference启动图必须证明无LiDAR生产者、订阅者和标签泄漏。

验收记录包含实际消息、频率、队列/QoS、同步残差、端到端数据年龄、丢帧和异常状态。
记录回放保留原始时间、frame、run来源和标定版本；换机器不能依赖原绝对路径。
