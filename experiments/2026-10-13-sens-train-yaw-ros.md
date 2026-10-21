# EXP-20261013-007：ROS训练fixture偏航与扫描内插值

## 1. 基本信息

- 日期：2026-10-13
- 类型：训练专用ROS功能短测
- 分支：`feature/engineering-initialization`，工作区保留既有未提交改动
- 责任角色：sensor_engineer / tester
- 关联：SENS-TRAIN-01、REQ-04、REQ-05、REQ-13、ADR-021

## 2. 目的与边界

将已通过离线矩阵的非零偏航和扫描内状态插值接入实际ROS训练图，核对源状态、
`/clock`、Radar/IR收据、训练监督JSON、逐点状态身份、运动补偿和未知区域语义。
这是具名运动学fixture，不是ARS548或Mid-360实测，不是固定翼动力学转弯，不是
跨设备时钟校准、功耗、正式PERF-01或研究模型质量验收。

## 3. 修改与配置

- `configs/sens_train_01_yaw_fixture.yaml`：200ms扫描、5个有序时间槽，50/150ms
  槽用于插值；速度0.1m/s，偏航率1deg/s，仿真标定明确标为fixture。
- `simulation/ufm_simulation/perf01a_fixture.py`：增加训练fixture profile选择器；
  无profile时保留历史直线源，推理模式拒绝使用训练profile。
- `ros_ws/src/uav_fusionmap_simulation/scripts/sens_train_01_source_node.py`：按同一
  配置生成偏航状态，仍由该节点唯一发布`/clock`和`/uav/sim/state`。
- `ros_ws/sens_train_01_run.py`：新增yaw入口和独立几何/标签oracle，区分直线与偏航
  统计，并核对未覆盖区域仍为unknown。
- `tests/test_sens_train_01_yaw_ros.py`：成功路径、旧profile保持、插值/无回波时间槽
  和篡改失败回归。

没有修改公共ROS消息、在线SensorBundle、inference launch、研究仓库或PERF-01配置。
训练LiDAR监督仍只出现在训练专用JSON/话题，不进入在线感知、定位或地图。

## 4. 实际命令

```bash
bash ros_ws/sim01_env.sh python ros_ws/sens_train_01_run.py --fixture yaw --port 11447
bash ros_ws/sim01_env.sh python ros_ws/sens_train_01_run.py --fixture single --port 11447
bash ros_ws/sim01_env.sh python ros_ws/sens_train_01_run.py --fixture multiray --port 11447
bash ros_ws/sim01_env.sh python ros_ws/sens_train_01_run.py --fixture motion --port 11447
bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_sens_train_01*.py'
bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_*.py'
```

Python均由`Radar-Diffusion`环境执行；测试过程中未启动研究模型、长训练或正式性能运行。

## 5. 结果

最终偏航run：`.runtime/runs/sens-train-01-20261013T205621081660/validation.json`。

- ROS训练记录：20组schema `0.2`；Radar、IR、监督各20条。
- 源状态与clock：各22条，时间范围覆盖0至2.1s；发布/接收计数闭合。
- 扫描槽：100个；80个回波、20个无回波槽；20个回波使用两状态sample_id插值。
- 独立几何/补偿核验最大误差：`2.72e-15 m`，为理想fixture数值一致性，不是实测精度。
- 标签计数：free 500、occupied 60、unknown 25040；未覆盖探针40次均保持unknown。
- 图审计：`/clock`和状态各只有source一个发布者；LiDAR监督只有fake节点发布，
  仅runner和recorder订阅；training节点和master退出码均为0，端口释放为true。
- 回归：偏航定向测试通过；旧single/multiray/motion ROS入口均通过；全仓轻量测试
  `315/315`通过。

## 6. 限制与下一步

偏航源是北向平移叠加独立姿态变化，不能替代PX4固定翼动力学状态。真实设备采集时钟、
ARS548检测列表时间、Mid-360逐点时间、外参、功耗和目标平台仍未提供，保持外部输入阻塞。

下一步按项目顺序进入T-14：设计并测试`nav_msgs/Odometry`兼容镜像与唯一TF发布边界，
确保AircraftState仍是状态权威、地图只消费观测时刻SpatialContext。基础地图和研究
后端接入继续后置；对照试验最后进行。
