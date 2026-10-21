# EXP-20261010-002：双射线监督与受限PointCloud2适配

日期：2026-10-10；责任角色：sensor_engineer（监督）、system_architect（接口合同）；
类型：纯函数/真实ROS消息契约、2秒独立ROS功能级短测。
状态：两个无设备子范围验证通过；IFACE-01、SENS-TRAIN-01整体仍进行中。

## 目的与输入

正式PERF-01目标平台、设备采样时钟和功耗数据暂缺。本轮不启动正式测量、训练或
对照试验，沿已确认工程顺序推进可独立完成的监督标签质量与原始载荷合同。

- [双射线配置](../configs/sens_train_01_multiray_fixture.yaml)：同一odom世界两个独立
  障碍及两个显式IR像素，具名非单位仿真外参，5×3图、两束零时长射线，沿用上轮
  `training_data_generation`隔离图。不是实物安装外参或完整传感器模型。
- [原始Radar字段配置](../configs/iface01_radar_fixture.yaml)：`PointCloud2`的局部xyz
  单位m、Doppler单位m/s及正方向、SNR单位dB、同run仿真时钟身份都必须由调用者明示。
  仅支持完整声明的**零扫描时长fixture**，真实设备来源、任意扩展字段、逐点时间和
  非零扫描一律拒绝；无真实硬件时不填造设备时钟映射或测速/功率物理标定。

预期：首回波前才有可证实的free，首命中occupied，擦边、遮挡与量程外unknown；
两束射线在同体素冲突时occupied不能被后续free清除。Radar/IR仍是模型输入、
LiDAR只进入训练记录器。点云转换仅做字段/类型/字节序/符号和身份核对，
不发布在线话题或改变RadarFrame/SensorBundle消息。

## 执行与结果

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  -m unittest discover -s tests -p 'test_*.py' -q
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  ros_ws/sens_train_01_run.py --fixture multiray --port 11449
```

新增反例先复现RED：共面擦边误判为LiDAR命中、第二射线将occupied误标free，
以及PointCloud2额外逐点时间字段被静默丢弃、速度字段复用坐标字节区间；
分别修复几何数值边界、occupied优先级、未声明字段及字节重叠拒绝后转GREEN。
类型、单位、frame、时钟、
sign和大端/小端真实ROS消息往返在`test_iface01_radar_raw.py`验证；
无回波不推出自由。完整轻量回归**265/265**通过。

[最新成功run](../.runtime/runs/sens-train-01-20261010T161508228655/validation.json)：
`passed=true`、`errors=[]`，Radar/IR/训练监督各20/20，20条
[独立JSONL](../.runtime/runs/sens-train-01-20261010T161508228655/training-records.jsonl)
逐条验证双点回波、双IR热点、两个occupied以及后方unknown；实际图中
LiDAR监督仅由训练fixture发布、训练记录器和本次监督器订阅，两个子进程退出0，
master端口11449释放。首次双射线通过run
`sens-train-01-20261010T160711295655`也独立保留，不覆写任何已有目录。

## 限制与下一步

PointCloud2适配只是离线fixture接口，无驱动ROS节点、设备字段规格、物理采样时间域
映射、真实雷达Doppler/功率标定、逐点时间或非零扫描补偿；不接入在线默认图。
训练仅有两个小型静态场景和10Hz的低速运动fixture，尚无多场景质量统计、
真实Radar/IR模型输入适配、研究模型推理/训练与机载性能证据。
IFACE-01继续保留原始设备接入、可选Odometry镜像/TF唯一责任和状态插值待办；
SENS-TRAIN-01下一关口是逐点时间及运动补偿的接口方案和多场景标签审计。
PERF-01正式平台、物理时钟、功耗仍阻塞；对照试验保持最后。
