# EXP-20261026-002：Phase 2 IMU 源证据与独立交付门禁

- 日期：2026-10-26；责任角色：sensor_engineer；类型：调用链审计、归档原始记录只读核对、单元门禁。
- 工作区：`feature/engineering-initialization`；已有未提交改动保留；不修改研究仓库或仿真源副本。
- 解释器：`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`；Python 检查经
  `bash ros_ws/sim01_env.sh`，实测 `sys.executable` 与指定环境一致。

## 预期与证据

原 Phase 2 要求独立功能级 IMU。首先检查现有原始来源能否完整到达业务接口，
验证时间、坐标、比力与质量合同；不得将 `AircraftState` 的速度或静止试验
推断为真实六轴 IMU，也不得在未确认公共消息时改变 ROS 接口。

代码路径：桥接副本 `Tools/jsbsim_bridge/src/sensor_imu_plugin.cpp:getData` 读取
JSBSim pilot 点加速度/机体角速率并加模拟噪声，`mavlink_interface.cpp`
产生 HIL_SENSOR；PX4 `src/modules/mavlink/streams/HIGHRES_IMU.hpp:send`
使用 `vehicle_imu` 增量、采样周期和估计偏置写六轴及采样时间。项目
`simulation/ufm_simulation/mavlink_source.py:decode_source_packet` 验证报文
及六轴却只返回时间；`source_timeline.py:consume` 仅发时钟，
`ros_ws/src/uav_fusionmap_simulation/scripts/state_clock_node.py` 不发 IMU；
`sensors/ufm_sensors/state_adapter.py` 只处理估计的 ODOMETRY；现有
`ros_ws/src/uav_fusionmap_msgs/msg/` 无 ImuSample。文档中的逻辑
`ImuSample` 与候选 `/uav/sensors/imu` 尚未形成可运行链路。

只读归档 `.runtime/runs/sim00b-20260912T123817/mavlink.jsonl`：以独立
pymavlink 解码源 1/1 的 ID 105，共 6051 条；六轴低六位更新掩码全部为 63，
六轴非有限值 0，样本时间从 200000 到 121200000 us，连续采样间隔
16–24 ms；六轴范围 xacc=1.01759..1.37522、yacc=-0.30946..0.03183、
zacc=-9.91913..-9.47745 m/s²，角速率各轴绝对值小于 0.014 rad/s。
这是已归档静止仿真的源数据有效性检查，**不证明**比力物理解释、pilot 点安装
外参、设备时钟、协方差、在线 IMU 发布或实际机载数据质量。

## 本轮实施与结果

- `tests/test_sim01_source.py` 增加两项门禁：有效六轴仍只有时钟事件；六分量
  分别注入 NaN 时解码拒绝且时钟不前进。源入口、状态和现有 ROS 图不变。
- 定向 `test_sim01_source.py`：13/13 通过；全仓 `unittest discover -s tests
  -p 'test_*.py' -q`：388/388 通过；没有重新运行既已验收的 ROS 短测，
  因本轮未修改任何生产节点、消息定义或启动图。
- 待确认接口、生产者/消费者、兼容与恢复见
  [IMU 门禁提案](../docs/PHASE2_IMU_GATE_20261026.md)。新增公共 ROS 消息
  需用户确认，本轮在此停止，不将代码门禁写成独立 IMU 已交付。

未执行：新 IMU 节点/消息、仿真新运行、真实设备/标定与设备时钟、模型推理、
正式 PERF-01 和性能验收。恢复：测试及门禁文档均独立，可仅撤销本轮增量；
现有未提交文件、归档数据及历史实验不回退或覆盖。本记录位于被忽略的
`experiments/`；后续版本化需逐文件确认，不自动提交或更改忽略规则。
