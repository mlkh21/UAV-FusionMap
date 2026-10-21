# IFACE-01 / SENS-TRAIN-01：同场景训练监督具体方案（最小fixture已实施）

版本：v0.4；日期：2026-10-13；责任角色：sensor_engineer（SENS-TRAIN-01），
IFACE-01时空契约由system_architect负责。状态：2026-10-10用户确认此处的
最小训练fixture与时空子范围，功能级短测通过；完整IFACE-01/SENS-TRAIN-01未验收。

## 当前事实与边界

`simulation/ufm_simulation/perf01a_fixture.py`给出同run的状态；
`sensors/ufm_sensors/perf01a_fixture.py`的运动Radar读取固定`obstacles_odom`，
IR只按像素`hotspots`赋功能级强度，二者目前没有共同的场景对象或相机投影校验。
`ros_ws/launch/perf01a_async.launch`只有在线Radar/IR、匹配、占位感知和地图，
没有LiDAR生产者/训练标签消息。现有SensorBundle和模型输入只容纳Radar+IR，
此方案不改变消息定义、不修改研究仓库和正式PERF-01测量配置。

## 本次确认并实施的最小范围

1. 增加版本化、最小的已知场景fixture：带明确`scene_id`、同一run/clock域、
   `obstacles_odom`几何，以及由这些障碍物**显式配置**的IR像素热点投影/对应关系。
   首版只支持固定点/占据体和无噪声小图；IR值仍为`fixture_intensity`，不称为热物理。
   对应关系无配置或超出视场时失败，不猜测Radar、Camera、Body坐标重合。
2. IFACE-01在训练fixture配置中声明`T_body_training_lidar`、
   `T_body_radar`、`T_body_thermal_optical`的方向、单位、calibration_id、有效期，
   与`T_odom_body(t)`组合为`T_odom_training_lidar(t)`；只由sensors维护安装外参，
   唯一状态源仍为AircraftState。真实外参未得到之前仅能使用**具名仿真标定**，
   禁止用未说明的单位阵填充缺失项，training_lidar不广播在线TF。
3. Radar扫描中点、IR曝光中点、LiDAR扫描中点均记录为采样参考时刻；现有ROS训练
   入口仍使用零扫描时长/逐点同刻的明确fixture限制。样本绑定run_id、clock_id、
   scene_id、calibration_id、各sample_id与扫描起止，LiDAR监督与Radar参考时刻差
   暂按现有5ms门限提案；超限、时间域或外参不匹配时拒绝训练配对，不改变在线
   Radar/IR配对理由或10ms姿态年龄要求。非零扫描纯函数schema `0.2`已在2026-10-12
   补入并通过定向审计；2026-10-13接入训练专用ROS JSON记录路径，见下节。
4. 仅`training_data_generation`装配额外的`fake_lidar_node`和训练记录器；
   监督先保存独立版本化记录（点云、体素`target`与`observed_mask`），具体ROS
   消息/话题编码待实现方案确认，不向SensorBundle追加字段。`inference`装配
   沿用无LiDAR图，并通过节点、发布/订阅图与消息类型断言无监督入口；
   perception forward、定位和mapping均不订阅监督记录。

## 标签语义与可测试小场景

建议用有界体素网格和固定扫描射线：只有已声明有效、时空标定匹配的射线，
才将**首个有效命中**体素设为`target=occupied, observed_mask=true`；从扫描起点
到首次命中之间可证明穿越的体素可标`free, observed_mask=true`。被首个命中
遮挡的后方、FOV外、量程外、未命中但没有可验证全程回波语义的射线，以及
完全未被射线覆盖的体素，一律`observed_mask=false, target=unknown`。
不能从“无点”推断free；target与mask为训练监督，不是在线地图观测。

最小oracle至少覆盖：同一障碍物对应Radar测量、具名IR像素热点和LiDAR首次
命中；同一射线上命中前free、命中occupied、命中后遮挡unknown；FOV/量程外
和无回波unknown；非单位训练外参及运动两时刻在odom重合；时间/run/scene/
calibration不匹配拒绝；在线SensorBundle编码及`inference`启动图不含LiDAR、
target、mask；training图只向训练记录器发布监督。先用纯函数测试，再做独立
小图2秒真实ROS短测和图审计，失败run保留；不拿训练短测充当PERF-01或研究
模型质量验收。

## 待确认与恢复

2026-10-10已按用户“按你说的做”确认最小场景、具名仿真外参、独立JSONL记录与
训练/推理分图；具体结果见[EXP-20261010-001](../experiments/2026-10-10-sens-train-01-fixture.md)。
此确认不延伸到真实标定、公共ROS消息新增或研究模型改动。若需新增公共消息，
先审查字段合同、消息生成及消费者清单。既有在线launch/消息保持不变，
新实现失败时停止使用训练专用入口并保留诊断目录，不回写历史运行证据。

2026-10-10补充：[第二版已知场景](../configs/sens_train_01_multiray_fixture.yaml)
的两障碍、双像素投影、双LiDAR射线已通过独立ROS短测；数值擦边不得当命中，
两射线标签重叠时首回波occupied优先。局部PointCloud2→RadarFrame fixture适配
不改变此训练launch的输入图，也不解除非零扫描时逐点时间/运动补偿前置。
见[EXP-20261010-002](../experiments/2026-10-10-iface01-sens-train-multiray.md)。

## 2026-10-12非零扫描纯函数子范围

在正式平台、传感器物理时钟和功耗输入缺失期间，先完成不依赖设备的训练记录合同，
不扩展ROS公共消息和现有在线图。新增配置
[`sens_train_01_motion_fixture.yaml`](../configs/sens_train_01_motion_fixture.yaml)使用
schema `0.2`和200ms扫描：逐点时间偏移必须有序、首尾覆盖扫描区间且扫描时长为偶数
纳秒；状态历史必须属于同一run/clock、状态有效、按时间严格递增并覆盖完整扫描。

实现将每条射线在采集时刻的命中从`training_lidar(t_ray)`变换到odom，再变换到
`training_lidar(t_scan_mid)`。点记录同时保存`raw_xyz`、补偿后的`x/y/z`、
`point_time_ns`、`time_offset_ns`、`ray_index`和`pose_sample_ids`；位置采用线性插值，
姿态采用最短弧SLERP。记录另保存全部射线的`ray_time_offsets_ns`，无回波射线也保留
时间槽；没有回波的射线不产生free或occupied标签，重复射线或畸形点记录拒绝。当前已覆盖两束回波、
一束无回波、遮挡后方unknown、量程截断、FOV拒绝、单/双障碍场景矩阵、缺失/乱序/
不完整历史、逐点时间非法、重复/畸形点、整帧无回波、v0.1非零扫描拒绝和旋转插值。

该纯函数子范围随后已接入训练专用ROS短测；ROS记录仍使用私有schema `0.2` JSON，
不扩展公共RadarPoint消息，也不把仿真时间当作设备时钟。下一步顺序为：真实记录到位后
接入Mid-360型号字段/逐点时钟合同的回放审计 → T-14状态镜像/唯一TF → 基础地图；正式
PERF-01和对照试验不因fixture通过而提前启动。

## 2026-10-13非零扫描ROS训练闭环

用户在说明没有硬件或实测记录后，以“继续”确认独立软件子范围：沿用训练JSON
schema `0.2`及既有三个节点，不扩展公共ROS消息、在线SensorBundle或研究模型。

1. 仿真源保持唯一`/clock`和状态发布者；`motion`生成0—2.1s的22条状态/时钟，
   20个采样中点为0.1—2.0s，每个训练LiDAR扫描200ms。首尾状态用于完整扫描覆盖；
   Radar/IR仍是与中点同刻的零时长fixture，不宣称ARS548非零扫描已接入。
2. sensors的`TrainingScanBuffer`缓存至多64条适配状态，最多2条未被时钟覆盖的
   状态；只有状态历史和`/clock`均覆盖扫描末端才生成样本。缺中点或首端历史、
   重复/乱序、跨run/clock、无效状态或时钟回退拒绝；未完成扫描且输入停滞5s墙钟
   后节点停止。此缓存只服务有限短测，不是可持续大规模流处理器。
3. 节点读取同一配置快照，参数服务器只承载路径、run和小整数count，避免ROS1
   XML-RPC的32位整数上限；纳秒字段继续保留原整数。运动标定有效期右端从2.1s
   调整至2.2s，以覆盖最后一个结束于2.1s的扫描，仍为具名仿真标定。
4. runner保存五类收据，核对JSONL与监督话题全载荷、顺序、身份、Radar坐标和IR
   全像素，以及源发布/节点接收计数。独立解析几何oracle检查原始点、补偿点、
   引用状态、occupied端点、命中前free、无回波与遮挡后unknown；图审计检查唯一
   clock/state源和无在线消费者。数值绝对容差1e-6，时间与身份精确比较。

运行：`bash ros_ws/sim01_env.sh python ros_ws/sens_train_01_run.py --fixture motion`。
原`--fixture single`和`--fixture multiray`保持零时长schema `0.1`。
启动时先检查独立端口；使用新run目录、exclusive-create记录，结束仅清理本次进程。
失败时停止使用`motion`入口，保留产物并继续使用已验证的零时长入口，不回写旧实验。

已完成：直线ROS短测、偏航/插值ROS短测及两个零时长入口回归，各20组训练样本；
偏航run为22条状态/clock、80回波、20个插值回波和20个无回波槽；定向偏航测试、
全仓315项轻量测试通过，XML-RPC启动失败run保留，详见
[EXP-20261013-005](../experiments/2026-10-13-sens-train-motion-ros.md)和
[EXP-20261013-007](../experiments/2026-10-13-sens-train-yaw-ros.md)。真实设备、
标定、时钟误差、统计数据集和模型质量未验收；下一步推进T-14，不以硬件缺失阻塞独立
软件任务，对照试验继续最后。

## 2026-10-13几何/运动矩阵与统计

用户“继续”确认更多场景与标签覆盖/补偿误差统计，独立新增
[`sens_train_01_scene_matrix.yaml`](../configs/sens_train_01_scene_matrix.yaml)及
[`sens_train_01_scene_suite.py`](../tests/sens_train_01_scene_suite.py)离线验收入口。
不改变现有ROS图、公共消息、研究模型和正式PERF配置。

矩阵包含单/双障碍、近距离、遮挡、空场景、量程截断、1m/s平移、正负偏航和
35/50/70m/s平移，共12场景、每场景3组记录。中点为1.0/1.01/1.02s，200ms扫描
含5束射线；50/150ms槽没有直接状态样本，以有界历史进行插值。源为具名运动学
fixture：北向匀速平移叠加独立偏航，不是动力学一致的固定翼转弯或真实PX4估计。

验收工具保存矩阵、各场景完整配置、源状态、训练JSONL及报告；按新输出目录名
区分各run身份，目录已存在则拒绝覆盖，失败报告和已生成样本保留。独立面平面
交点oracle核对首次命中、原始点、补偿世界坐标、引用状态、occupied端点、全无
回波unknown及遮挡探针；解析相机/Radar几何核对输入坐标和IR全像素。统计原始
坐标/补偿残差的mean、最近秩P95与max，以及回波、插值回波、free/occupied/unknown
计数和observed比例；空回波场景误差为null，不填零。

新矩阵复现35/50m/s同一表面因float64边界误差分裂成相邻occupied单元。已按
RED/GREEN修复训练体素索引：归一化网格坐标距整数不超过
`8 * float64_epsilon * max(1, abs(scaled))`时先吸附，再floor；真实1e-9m边界两侧
仍保持不同体素。此数值规则不放宽射线擦边、同步、量程或FOV门限。

已完成该离线子范围：36记录、102回波（30插值回波），observed=1.09375%，最大
补偿残差3.08461e-7m；定向40项、全仓309项
轻量测试及三个旧ROS入口回归通过，首轮失败保留，详见
[EXP-20261013-006](../experiments/2026-10-13-sens-train-scene-statistics.md)。
此占比仅为36个稀疏小网格的标签统计，不是质量充分性或识别召回；真实设备/统计数据集/模型质量仍未验收。
ROS偏航/插值已通过独立训练短测，详见[EXP-20261013-007](../experiments/2026-10-13-sens-train-yaw-ros.md)。
下一项推进T-14状态镜像/唯一TF，不提前科研对照试验。
