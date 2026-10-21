# IFACE-01 Radar值级闭环与SENS-TRAIN-01高度覆盖（EXP-20261016-002）

- 日期：2026-10-16；状态：软件fixture子范围已完成；责任角色：sensor_engineer。
- 目的：在无真实硬件、设备时钟和标定记录条件下，补齐 fake Radar 从原始 `RadarFrame`
  到采用 `SensorBundle` 的值级核对，并扩展训练监督的非水平射线/高度与无回波覆盖。
- 边界：不增加公共ROS消息字段，不改变配对、5 ms同步门限或20 ms目标；训练LiDAR仍只
  属于 `training_data_generation`，不进入在线SensorBundle、perception或mapping；不把
  fixture结果写成真实设备、模型质量或正式性能验收。

## 实施

1. `ros_ws/perf01a_async_run.py` 增加默认关闭的 `--verify-radar-values`，独立订阅并
   保存原始 RadarFrame，逐 adopted Bundle 核对 sample/run/clock、扫描起止与中点、点
   数、坐标、功率、Doppler/功率可用性、单位、质量和空回波语义。ROS float32 仅允许
   `1e-6`绝对误差；缺帧、重复、身份、时间和字段篡改均失败。
2. `tests/test_perf01a_radar_values.py` 增加7项纯函数正负例，覆盖空回波、float32量化、
   点坐标/功率/可用性/单位/质量/身份/扫描时间及发布覆盖。
3. `configs/sens_train_01_height_matrix.yaml` 与 `tests/test_sens_train_01_height.py`
   增加高/低障碍非水平射线及有效射线无回波场景；`tests/sens_train_01_scene_suite.py`
   仅扩展独立测试夹具的障碍高度、射线和FOV参数，不修改训练生成器规则。

## 命令与结果

```bash
bash ros_ws/sim01_env.sh python -B ros_ws/perf01a_async_run.py \
  --scenario ir_value_transport --duration-s 2 \
  --verify-ir-values --verify-radar-values --port 12522
bash ros_ws/sim01_env.sh python -B tests/sens_train_01_scene_suite.py \
  --matrix configs/sens_train_01_height_matrix.yaml
bash ros_ws/sim01_env.sh python -B -m unittest discover -s tests -p 'test_*.py' -q
```

- 联合ROS run：[perf-report.json](../.runtime/runs/perf01a-async-20261016T132610318324/perf-report.json)。
  `passed=true`、`errors=[]`；原始 Radar 40帧/采用 Bundle 20帧，IR原始100帧/采用20帧，
  两种值级核对错误均为空；Radar生产40/接收40/意外丢失0，IR生产100/接收100/意外丢失0；
  Bundle/occupancy/map各20；预期20次严格超时拒绝保持；端口关闭和清理通过。开发机
  P99=43.322513 ms，20 ms诊断未通过。
- 高度矩阵：[report.json](../.runtime/runs/sens-train-scenes-20261016T132005838102/report.json)。
  3个场景、9个样本通过；高/低障碍场景各6次回波，原始几何最大误差约
  `1.8311e-15 m`、运动补偿最大误差约`9.9302e-16 m`；垂直无回波场景15个射线槽全部
  unknown，`free=0`、`occupied=0`、`unknown=3840`。
- 定向测试及旧场景回归通过；全仓轻量测试 `Ran 370 tests ... OK`。

## 未关闭项与恢复

本次只证明软件fixture的字段/时间/身份守恒和标签规则。真实Radar/IR原始驱动、跨设备
时钟残差、真实外参/协方差、目标平台资源/功耗、研究模型质量、正式PERF-01和完整
Phase 2仍未验收。若回退，仅停用 `--verify-radar-values` 和新高度矩阵测试入口即可；
不删除历史run、不放宽阈值、不修改公共消息或同级研究仓库。
