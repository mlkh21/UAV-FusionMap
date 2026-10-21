# EXP-20261021-001：T-13A在线推理图训练监督隔离复核

日期：2026-10-21  
责任角色：sensor_engineer（ROS集成由integration_engineer协作）  
状态：已完成软件子范围；T-13、完整Phase 2、PERF-01和真实设备验收仍未完成。

## 1. 目的与边界

本项只核验在线 fake Radar/IR → SensorBundle → placeholder perception → Local Map
运行时ROS图不存在训练监督LiDAR的生产者或消费者，并保持训练数据生成图独立。
不改变公共消息、模型forward、在线业务接口、性能门槛或训练标签算法。

## 2. 实现

- `ros_ws/online_graph_audit.py`：新增纯函数图校验器，拒绝空图、缺失预期在线节点、
  训练/LiDAR话题及训练/LiDAR节点；结构化消费`getSystemState`结果，不发布或订阅话题。
- `ros_ws/perf01a_async_run.py`：新增默认关闭的`--audit-online-graph`选项，在在线节点
  已就绪且仍存活时采样图；默认运行路径不改变。
- `tests/test_perf01a_async.py`：新增正常图、空图、缺节点、训练话题和伪装LiDAR节点
  五类定向反例/正例。

## 3. 验证命令与结果

Python解释器核对为：
`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。

### 3.1 定向与语法

```text
python -m unittest discover -s tests -p 'test_perf01a_async.py' -v
Ran 39 tests ... OK
python -m py_compile ros_ws/online_graph_audit.py ros_ws/perf01a_async_run.py tests/test_perf01a_async.py
通过
```

### 3.2 在线运行时图

```text
bash ros_ws/sim01_env.sh python -B ros_ws/perf01a_async_run.py \
  --scenario parameterized_sensors --duration-s 2 --port 11581 \
  --audit-online-graph
```

结果：通过；7个预期在线节点齐全；训练/LiDAR话题为空；训练/LiDAR节点为空；
20个Bundle、20个Occupancy、20个Map收据闭合；ROS master端口和子进程清理通过。
报告：[perf-report.json](../.runtime/runs/perf01a-async-20261021T141204023509/perf-report.json)。

随后不带新开关复跑既有入口：`parameterized_sensors` 2秒ROS run通过，20个Bundle、
20个Occupancy、20个Map收据闭合，`audit_online_graph=false`且报告没有写入
`online_graph`字段，端口清理通过。报告：[默认入口报告](../.runtime/runs/perf01a-async-20261021T143742325828/perf-report.json)。

该run的开发机`sensor_to_occupancy` P99为42.988710 ms，20 ms诊断未通过；这是既有
开发机性能事实，不属于本项图隔离判定，也不构成正式PERF-01结论。

### 3.3 训练图回归

```text
bash ros_ws/sim01_env.sh python -B ros_ws/sens_train_01_run.py \
  --fixture single --port 11582
```

结果：通过；Radar、IR、训练监督、状态和clock均为20条；LiDAR监督发布者仅为
`/sens_train_01_fake_lidar`，订阅者仅为`/sens_train_01_runner`和
`/sens_train_01_recorder`；端口释放通过。
报告：[validation.json](../.runtime/runs/sens-train-01-20261021T141306656832/validation.json)。

### 3.4 全仓回归

```text
bash ros_ws/sim01_env.sh python -B -m unittest discover -s tests -p 'test_*.py' -q
Ran 379 tests ... OK
```

## 4. 结论与限制

- T-13A“当前在线占位图的运行时训练监督隔离”通过。
- 当前仓库没有可供本项验证的研究后端实际forward运行，因此不能以此关闭T-13完整
  的模型输入/forward隔离质量范围。
- 本项不验证真实Radar/IR驱动、设备时钟、标定、功耗、机载资源、模型质量或20 ms
  正式性能；PERF-01和ENV-03保持原阻塞状态。
- fake LiDAR仍只用于训练监督；无回波、未知或过期数据不解释为free。
- 新诊断选项默认关闭；已有在线入口和公共ROS消息保持兼容。
