# Phase 2 IMU 独立交付门禁与接口待决

日期：2026-10-26；主责任角色：sensor_engineer。状态：源数据已核对；独立 IMU
接口待确认，不计入 Phase 2 完整验收。记录：[EXP-20261026-002](../experiments/2026-10-26-phase2-imu-gate.md)。

## 已有代码与源证据

- 桥接副本的 `sensor_imu_plugin.cpp:getData` 从 JSBSim 读取 pilot 点加速度和机体
  角速率，加入模拟噪声；`mavlink_interface.cpp` 写入 HIL_SENSOR。PX4 本机源码
  `HIGHRES_IMU.hpp:send` 从选定 `vehicle_imu` 的增量除采样周期、减估计偏置后
  写入六轴值，时间来自 `timestamp_sample`。这是可追踪的代码路径，不是外参
  或实机标定证据；pilot 点与 `base_link` / 实物 IMU 安装点不能默认为同点。
- `simulation/ufm_simulation/mavlink_source.py:decode_source_packet` 验证目标源、CRC、
  六轴有限数和更新掩码，然后仅返回 `type=imu,time_usec`；
  `source_timeline.py:consume` 只将它转换为 `/clock` 时刻，失效/乱序有拒绝/故障门控。
  `state_clock_node.py` 只发布 `/clock`、`/uav/sim/state`、诊断。
- `sensors/ufm_sensors/state_adapter.py` 转换估计的 ODOMETRY 位姿/速度，既无六轴
  输入也不生成 IMU。ROS 消息包无 `ImuSample.msg`；`SensorBundle.msg` 无 IMU 字段。
  `docs/DATA_FORMAT.md` 的 ImuSample 是逻辑约定，`docs/SENSOR_INTERFACE.md` 的
  `/uav/sensors/imu` 是候选话题，尚不是已实现的发布链。

## 本轮可执行与不执行

已有 SIM-00B 静止遥测归档可只读核对源记录；本轮增加纯单元门禁，证明六轴即使
有效也没有从 `decode_source_packet` 冒充业务样本，非有限数不会推进时钟。
保留现有线上行为、ROS 图及原始数据。不从估计的 `AircraftState` 反推 IMU，
不将归档的源数据或无校准 fixture 称作独立 `ImuSample`。未增加公共 ROS 消息、
没有修改 `SensorBundle`、没有接入规划/地图/研究模型。

## 待确认的接口方案（未实施）

1. 生产者：simulation 在已有 MAVLink 入口仅对通过筛选和采样门控的
   `HIGHRES_IMU` 保留六轴原值、原始采样时间、源坐标、run/clock/sample 身份；
   通过与 sensors 相邻的原始 IMU 承载接口输出，不将 MAVLink 接收标记当采样时间。
   原始承载选用标准 `sensor_msgs/Imu` 还是具身份的消息，须先确定跨层身份与
   不可用质量的无损编码；不能仅靠 `header.stamp` 猜测 run 身份。
2. 消费者：仅 sensors IMU 适配及诊断/记录；sensors 在明确源为机体 FRD、
   比力（不是去重力加速度）、单位、偏置应用位置和安装外参后，转换到约定的
   `imu` 前左上坐标，并携带未知协方差/安装来源；不接入 `SensorBundle`、
   perception、mapping、定位权威或训练 LiDAR 支路。`ImuSample` 公共编码
   必须给出字段、质量缺失方式、生产者/消费者转换及回放版本。
3. 兼容和恢复：IMU 输出默认关闭，旧 `/clock`、AircraftState、fake Radar/IR、
   placeholder、训练图保持原样。若接入未过源身份、采样时间、轴向、比力和
   unknown 质量门禁，保持 IMU unavailable 并关闭可选新出口，不回退成虚构样本；
   旧图不增加必需依赖。任何消息定义变更先核对所有生产/消费端与序列化回放。
4. 验证：六轴原始值到最终业务值逐轴/单位对照，已知静止与转动样本、
   同源时钟与时间回退、无效掩码/NaN/重复/断流、标定方向及缺失、ROS 消息
   往返、默认关闭旧入口回归；独立记录运行图、退出/恢复与质量边界。真实
   标定与设备时钟另设实测验收，不能用仿真结果关闭。

**停止点**：上述方案涉及新增公共 ROS IMU 编码及生产/消费链，按根目录
`AGENTS.md` 必须先明确消息定义、兼容与恢复并获得用户对该接口的确认。
当前只提交审计、测试和提案；不预先新建消息、节点或启动图。

## 2026-10-26后续实施状态

用户随后指示“继续”，在此已提出的生产/消费、兼容与恢复范围内确认实施
可选IMU公共承载和虚拟pilot点适配。原“停止点”保留作为实施前的门禁历史，
实际变更、短时ROS图证据及未验证物理语义见
[EXP-20261026-003](../experiments/2026-10-26-phase2-imu-optional-ros.md)。
此决定不确认真实IMU安装外参、跨设备时钟或Phase 2完整退出。
