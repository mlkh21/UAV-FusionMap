# SENS-TRAIN-COV-01：完整体素覆盖与短弦标签验收

- 日期：2026-10-20；状态：软件fixture子范围通过；主责任角色：sensor_engineer。
- 目的：检查fake LiDAR首回波射线在斜穿体素和短弦边界下是否完整写入observed/free，
  同时保留occupied端点、unknown区域和训练/在线隔离。
- 范围：只修改训练监督标签生成和独立离线场景验收；不改变公共接口、ROS消息、训练记录
  schema、ROS启动图或感知/地图调用链。不训练模型、不接入真实LiDAR、不推进概率地图。

## RED与修复

原生成器以`min(grid_resolution)/8`固定距离采样射线。新增独立线段—AABB区间oracle后，
短弦fixture在固定采样基线上RED：每条正斜率样本均漏掉正长度被射线穿越的体素`(9, 5, 4)`；
该体素穿越长度约0.0005m，小于0.0625m采样间隔，其他体素无额外observed。原12场景的
候选free采样无法保证覆盖这种短弦。

将监督生成改为线性复杂度3D DDA遍历：裁剪到有限网格，按体素边界推进并同时处理角点轴，
仅写入具有正长度交段的cell；固定网格面沿用`floor`上侧归属，浮点静止轴使用1e-12m数值
容差。射线终点继续独立映射为occupied并置observed，未回波射线不创建segment，因此仍不
生成free。生产数据契约和标签状态未改变。

独立oracle逐个枚举地图体素，对线段作区间裁剪并要求完整observed/free集合完全一致；
既有12场景矩阵及新增正/负斜率短弦矩阵均启用此检查。删去一个应观测free体素的注入负例
必须失败。完整检查覆盖斜穿、负向边界运动、扫描补偿产生的浮点平行轴、遮挡/无回波及
现有35/50/70m/s、偏航场景。

## 执行与结果

运行环境为Conda `Radar-Diffusion`，所有入口经`bash ros_ws/sim01_env.sh`执行。

```bash
bash ros_ws/sim01_env.sh python -B tests/sens_train_01_scene_suite.py \
  --matrix configs/sens_train_01_scene_matrix.yaml
bash ros_ws/sim01_env.sh python -B tests/sens_train_01_scene_suite.py \
  --matrix configs/sens_train_01_voxel_coverage_matrix.yaml
bash ros_ws/sim01_env.sh python -B -m unittest discover -s tests -p 'test_*.py' -q
bash ros_ws/sim01_env.sh python ros_ws/sens_train_01_run.py --fixture motion --port 11461
bash ros_ws/sim01_env.sh python ros_ws/sens_train_01_run.py --fixture yaw --port 11462
```

- 原12场景：[报告](../.runtime/runs/sens-train-scenes-20261020T112741687164/report.json)，
  12场景/36记录、完整正长度oracle通过。
- 短弦矩阵：[报告](../.runtime/runs/sens-train-scenes-20261020T112742162982/report.json)，
  正/负斜率2场景/6记录通过；每场景free=36、occupied=3、unknown=3801，数值几何误差
  最大`8.95e-16 m`。报告明确`hardware_validated=false`、`model_quality_validated=false`、
  `formal_perf_validated=false`。
- 定向场景测试13项、基础训练20项、高度4项、流审计10项及全仓372项轻量测试通过。
- 实际motion ROS：[报告](../.runtime/runs/sens-train-01-20261020T112428043819/validation.json)；
  实际yaw ROS：[报告](../.runtime/runs/sens-train-01-20261020T112430377554/validation.json)。
  两run均为Radar/IR/训练记录20条、状态/clock各22条，训练记录与收据及标签几何核验通过，
  训练LiDAR仅连接训练记录器/观察器；子进程退出码0、端口释放。ROS运动fixture不代表实机。

## 限制与恢复

本结果只验证确定性仿真标签几何覆盖，不能证明真实传感器射线、标定精度、训练数据充分性、
模型召回/质量、设备时钟、功耗或性能。未执行全量训练、PERF-01、概率累计、DEM、模型接入
或科研对照试验；Phase 2整体仍进行中，硬件输入仍是外部门禁。

若发现DDA边界语义错误，可恢复`training_supervision.py`的线段遍历实现并保留独立oracle和
失败fixture用于定位；不得删改已有run或将漏标体素从oracle中排除。`tests/`与`experiments/`
目前被工作区忽略规则覆盖，本记录与新增测试按用户要求保留，不修改`.gitignore`、不自动暂存、
提交或推送。
