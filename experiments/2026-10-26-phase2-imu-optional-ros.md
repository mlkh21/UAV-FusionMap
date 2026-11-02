# EXP-20261026-003：Phase 2 可选仿真IMU独立ROS旁路

- 日期：2026-10-26；责任角色：sensor_engineer，integration_engineer配合ROS。
- 范围：上一轮[源链门禁](2026-10-26-phase2-imu-gate.md)之后用户指示继续，
  按[接口方案](../docs/PHASE2_IMU_GATE_20261026.md)仅实施可选IMU公共承载和
  虚拟pilot点FRD→FLU轴适配；保持旧图默认关闭，不改SensorBundle。
- Python：`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`；ROS入口统一经
  `bash ros_ws/sim01_env.sh`。工作区既有未提交修改保留，不提交、不改研究仓库。

## 变更与复现

- 新增`ImuSample.msg`及双向codec。`ObservationHeader`保存采样时刻、run/clock、
  source/sample/status；六轴单位为m/s²和rad/s，比力明确标识；未知协方差的
  9个ROS槽位用`available=false`标记无效，不能读成零噪声。
- simulation现有解码默认只给时间；显式开关启用后保存校验后的六轴，
  SourceTimeline仅接受新时刻并发布/clock与原始IMU，源回退/同身份冲突终止。
  sensors仅在`sim_pilot_virtual_flu_v1`显式配置下转换虚拟pilot点坐标，
  依据同域clock有界门控发布独立IMU；不发布安装TF，不接入状态估计、
  SensorBundle、训练监督、感知或地图。

复现（各run创建新目录、独立ROS端口且仅清理本次进程）：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  /opt/ros/noetic/bin/catkin_make --source "$PWD/ros_ws/src" \
  --build "$PWD/.runtime/ros/build" \
  -DCATKIN_DEVEL_PREFIX="$PWD/.runtime/ros/devel" \
  -DCMAKE_INSTALL_PREFIX="$PWD/.runtime/ros/install" \
  -DPYTHON_EXECUTABLE=/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -j4
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  -m unittest discover -s tests -p 'test_*.py' -q
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  ros_ws/sim01_imu_run.py --enabled --port 12581
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  ros_ws/sim01_imu_run.py --port 12582
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  ros_ws/sim01_smoke.py --fixture
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  ros_ws/perf01a_async_run.py --scenario parameterized_sensors --duration-s 2 \
  --audit-online-graph --port 12583
```

## 实际结果与失败历史

消息构建通过（16种消息）；全仓轻量单元/契约`394/394`通过。
[最终开启图](../.runtime/runs/sim01-imu-enabled-20261026T190831940226/imu-result.json)
实际收到22条有效源/适配IMU，并在回退注入后各收到1条unavailable终止；
clock 22、状态13。逐条比对同run、采样时间、源身份、比力、加速度/角速率
轴翻转及unknown协方差，回退未推进时钟，`passed=true`，端口和进程清理通过。
[最终关闭图](../.runtime/runs/sim01-imu-off-20261026T190827341379/imu-result.json)
收到IMU 0、clock 20、状态13；无IMU发布话题，回退未推进时钟，
`passed=true`且已清理。
[既有SIM-01 fixture](../.runtime/runs/sim01a-fixture-20261026T190121338814/result.json)
有效/终止状态、时钟门控和Conda检查通过；
[旧在线占位图](../.runtime/runs/perf01a-async-20261026T190402633872/perf-report.json)
2秒`passed=true`、`errors=[]`，没有训练LiDAR节点或话题。

首次开启图失败是启动参数归属错误（标定传给源节点而非适配节点）；后续两次
观察器字段路径失败及一次MAVLink fixture未pack失败，各原始run不覆盖。
一次关闭图因订阅建立竞态只收到13次clock，被原观察器“必须15次”误判；
修正为22次输入、按采样身份对照且至少收到15次clock，关闭时检查实际ROS
发布话题无IMU。上述失败均保留在各自`.runtime/runs/sim01-imu-*`目录；
未更改生产时钟回退/输入拒绝阈值来消除失败。

## 边界、恢复和后续

新增公共`ImuSample`消息是可选旁路，不改变旧公共消息字段；默认关掉
`publish_imu`即可恢复旧节点行为，已由独立关闭图及既有SIM-01 fixture核对。
本次未运行真实PX4/JSBSim IMU在线源，只用真实MAVLink格式fixture验证ROS数据
传输和原有归档静止源记录；虚拟pilot点安装位置、比力物理解释/重力约定、
偏置与协方差、真实设备时钟及跨传感器标定需独立核对，不能由轴翻转单测证明。
未运行训练、research forward、正式PERF-01、机载资源或模型质量试验；完整
Phase 2、真实IMU接入和高真实性传感器验收仍未关闭。实验目录按现有规则被忽略，
后续版本化需逐文件检查，不能自动更改忽略规则或提交。
