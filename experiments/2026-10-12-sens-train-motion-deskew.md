# EXP-20261012-001：非零扫描训练fixture运动补偿审计

日期：2026-10-12；责任角色：sensor_engineer；类型：纯函数/定向回归。
状态：非零扫描的功能级fixture子范围通过；SENS-TRAIN-01和IFACE-01整体仍进行中。

## 目的与边界

正式平台、传感器物理采样时钟和功耗输入暂缺。本次不启动正式PERF-01、不修改真实
设备接口、不启动长训练，也不提前进行对照试验。目标是先把非零扫描的逐点时间和
运动补偿合同固定下来，并在没有设备输入时验证标签语义与拒绝边界。

输入为[`sens_train_01_motion_fixture.yaml`](../configs/sens_train_01_motion_fixture.yaml)：
schema `0.2`、200ms扫描、三条水平射线、同一odom场景中的两个障碍和具名仿真外参。
两条射线在扫描起点/终点产生回波，第三条射线在扫描中点时刻有效但无回波；状态历史
覆盖900ms、1000ms、1100ms，沿odom匀速运动。该配置是功能级几何fixture，不是设备
标定、物理功率、真实热成像或真实传感器时钟。

## 合同与实现

`build_training_sample`在非零扫描时要求：

- schema为`0.2`，扫描时长为偶数纳秒；逐点偏移有序，并从0覆盖到扫描总时长；
- AircraftState历史属于同一run/clock、`odom`/`base_link`身份有效、来源为估计状态，
  按时间严格递增并完整覆盖`[scan_start, scan_end]`；
- 每条回波保存原始传感器坐标、`point_time_ns`、`time_offset_ns`、`ray_index`和
  状态sample_id，并将命中点变换至扫描中点的`training_lidar`坐标；
- 位置使用线性插值，姿态使用最短弧SLERP；无回波不推导free，遮挡后方保持unknown。

实现文件为[`training_supervision.py`](../sensors/ufm_sensors/training_supervision.py)，
测试为[`test_sens_train_01.py`](../tests/test_sens_train_01.py)。该变化没有接入ROS
逐点时间字段；现有`sens_train_01.launch`仍使用零时长v0.1合同，在线SensorBundle、
perception、定位和mapping没有LiDAR监督输入。

## 执行与结果

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  tests/test_sens_train_01.py -q
```

结果：12/12通过。检查包括：

- 两束回波补偿到扫描中点后占据体素索引`676`和`684`，逐点时间为900ms和1100ms；
- 第三束无回波不增加点，也不改变两束回波的target/observed_mask；
- 缺失、未覆盖、乱序或跨身份状态历史，以及未覆盖扫描首尾的逐点偏移均拒绝；
- v0.1记录承载非零扫描拒绝；90度姿态历史的中点采用最短弧四元数插值；
- 已有零时长单障碍、多射线、擦边、遮挡、量程和身份反例继续通过。

## 结论与限制

本次只证明确定性纯函数在给定仿真状态历史和几何场景下能够保存逐点时间、完成到
扫描中点的坐标补偿并保持unknown语义。它不证明真实设备逐点时钟可获得、时间误差
满足阈值、标定有效、ROS记录器能承载schema `0.2`、模型质量、实时性能或飞行安全。

下一步是取得真实驱动字段/逐点时钟方案后，单独设计ROS记录路径和图审计，再扩充运动、
遮挡、量程和多场景标签统计；正式PERF-01和对照试验继续放在这些工程输入和可复现
数据门禁之后。
