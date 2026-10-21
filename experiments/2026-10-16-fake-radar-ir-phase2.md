# Phase 2 fake Radar/IR 软件链路复核（EXP-20261016-001）

- 日期：2026-10-16；状态：已完成软件 fixture 短测，正式门禁阻塞；责任角色：sensor_engineer。
- 问题：目标平台、真实 Radar/IR、设备时钟和功耗记录暂不可用；需要在不关闭正式门禁的前提下继续核对 fake Radar/IR 在线软件链路。
- 范围：沿现有独立 fake Radar/IR 发布、严格配对、占位感知及局部地图的 ROS fixture 重跑；不改生产代码、消息接口、5 ms 严格匹配门限、20 ms 目标或既有失败记录。LiDAR 仅供训练监督，不进入在线图；未知、无回波或过期不得视为 free。
- 方法：使用 `bash ros_ws/sim01_env.sh` 和 Conda `Radar-Diffusion` Python；先运行 `ir_value_transport` 的 2 秒全像素核对，再独立运行 `parameterized_sensors` 的 2 秒参数化 fake Radar/IR 链路；核对收发身份、run/clock、图隔离、拒绝/清理和报告，随后跑相关及全仓轻量测试。新运行使用独立端口、独立目录，保存原始产物。
- 通过边界：仅软件 fixture 功能与数值/身份核对；不得据此宣布真实传感器数据、正式 PERF-01、真实机载资源/功耗、完整 Phase 1/2、研究模型质量、滚动地图正式 M1 或科研对照试验通过。
- 恢复：若新试验失败，原始报告和失败原因保留；停止新进程并核对端口与 PID 清理，不改阈值拼凑通过。文档可按原有记录恢复；不触碰历史实验、研究仓库或未提交代码。

## 运行记录

使用现有 `ros_ws/launch/perf01a_async.launch`：独立 fake Radar/IR 生产者 ->
`perf01a_async_matcher_node.py` -> 占位感知 -> 局部地图。配置为
`configs/perf01a_async.yaml`，`ir_value_transport` 为 4x3 无噪声图像，
`parameterized_sensors` 使用 Radar FOV 120°x30°/6 m/功率噪声标准差 0.05、
IR 背景值 0.4/噪声标准差 0.01，固定随机种子 23；均非物理传感器标定。
环境检查所得 Python 是 `/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。

```bash
bash ros_ws/sim01_env.sh python -B ros_ws/perf01a_async_run.py --scenario ir_value_transport --duration-s 2 --verify-ir-values --port 12489
bash ros_ws/sim01_env.sh python -B ros_ws/perf01a_async_run.py --scenario parameterized_sensors --duration-s 2 --port 12490
bash ros_ws/sim01_env.sh python -B -m unittest discover -s tests -p 'test_*.py' -q
```

首轮运行在沙箱创建 socket 时被拒（`PermissionError: Operation not permitted`），
未生成 ROS run；获本机回环 socket 执行授权后按原参数分别完成，不修改阈值或代码。

| 场景 / 实际产物 | 功能结果 | 独立核对和局限 |
| --- | --- | --- |
| `ir_value_transport`：[报告](../.runtime/runs/perf01a-async-20261016T103401785264/perf-report.json)、[Radar发布审计](../.runtime/runs/perf01a-async-20261016T103401785264/radar-audit.json) | `passed=true`、`errors=[]`；40 Radar/100 IR 发布、20 Bundle/20 占据/20 地图；20 次预期 `radar_ir_timeout` 与 20 次严格拒绝相符，无意外传输丢失 | 原始 IR 100 帧与采用的 20 帧对应、同帧全部 4x3 像素核对、误差列表空；单 `/clock` 发布者；P99=47.280481 ms，开发机 20 ms 诊断**未通过** |
| `parameterized_sensors`：[报告](../.runtime/runs/perf01a-async-20261016T103419004714/perf-report.json)、[Radar发布审计](../.runtime/runs/perf01a-async-20261016T103419004714/radar-audit.json) | `passed=true`、`errors=[]`；40 Radar/100 IR 发布、20 Bundle/20 占据/20 地图；20 次预期拒绝；生产者无溢出、无审计错误、无意外传输丢失 | 确认参数化 fake 输入沿链路可用；没有独立原始 Radar 点逐值端到端 oracle；P99=44.385750 ms，开发机 20 ms 诊断**未通过** |

两个 run 均独立身份，重复/乱序为 0；状态/clock 对账、ROS master 端口释放、
节点退出和进程组清理通过；资源角色无缺项，但这里不是机载资源验收。
全仓轻量测试 `Ran 359 tests ... OK`；其中
`tests/test_sens_train_01_ros.py` 静态核对在线 launch 无训练 LiDAR 节点，训练
LiDAR 仅供监督；`tests/test_sens_train_01.py` 覆盖无回波/遮挡 unknown，不推导 free。

后续可在此 fake 数据源上继续 IFACE-01/SENS-TRAIN-01 软件契约与覆盖检查；
真正设备输入到位后须独立重做时钟残差、标定、逐点值、功耗及目标机载连续性能验收。
PERF-01 仍为 `reference_only`，ENV-03 独立恢复与 Phase 1 退出状态均未改变。
