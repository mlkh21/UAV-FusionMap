# EXP-20261013-005：非零扫描训练ROS闭环

- 日期：2026-10-13；类型：单元/契约测试与实际ROS传输的仿真fixture短测。
- 主责任角色：sensor_engineer；Technical Lead负责薄ROS包装及集成验证。
- 关联：SENS-TRAIN-01、T-13；决定见ADR-019。
- 分支：`feature/engineering-initialization`；工作区原有大量未提交/未跟踪改动，
  本次仅在确认范围增量修改，未提交、推送、清理或修改研究仓库。
- 环境：Conda Radar-Diffusion，`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`；
  Noetic，沿用已有生成消息，通过`bash ros_ws/sim01_env.sh`启动；无GPU/模型/硬件依赖。

## 问题与实现范围

已有schema v0.2纯函数，但ROS节点只传入单帧状态，runner不接受`--fixture motion`。
本次将有限状态历史交给现有补偿函数，不修改公共消息、在线图或正式PERF配置：

1. 状态缓存最多64条，未来未被clock覆盖状态最多2条；state和clock同时覆盖扫描
   末端才发布。非零扫描缺首端/中点历史、乱序/重复身份、跨run/clock、无效状态和
   clock回退拒绝；未完成扫描且输入停滞5s墙钟后停止。
2. `motion`源输出0—2.1s共22条状态/clock；20个参考中点为0.1—2.0s，LiDAR扫描
   时长200ms，三条射线偏移0/100/200ms。两束首回波与中间一束无回波保留时间槽；
   Radar/IR仍为瞬时功能级fixture。场景、标定与配置快照逐run保留。
3. 保存五类ROS接收收据；核对源发布/训练接收计数、JSONL与监督话题全载荷、
   sample_id/顺序/时间/坐标、IR全部像素。已知直线0.1m/s场景使用独立解析oracle，
   核对原始点、补偿点、引用状态、occupied端点及声明的free/unknown探针。
4. 图审计确认唯一clock/state源及监督只由训练节点发布、记录器/runner接收；
   静态launch测试确认在线图不含训练节点，训练图不含SensorBundle/感知/地图。

坐标/像素绝对容差1e-6；纳秒时间、身份、顺序及监督JSON全载荷精确比较。

## RED与修复

- 原runner对`--fixture motion`返回argparse退出2，不创建运行目录。
- 新状态流/回读审计测试先因缺少入口失败，补入后通过。
- 初次ROS启动失败：[失败报告](../.runtime/runs/sens-train-01-20261013T184758556433/validation.json)，
  日志明确为`int exceeds XML-RPC limits`。ROS参数服务器不能承载配置中的2.2e9整数。
  此run退出1、端口释放；目录和原始日志保留，未覆盖失败证据。
- 添加实际roslaunch配置的XML-RPC序列化负例，复现OverflowError后改为三个节点
  直接读取同一配置文件，参数服务器仅传路径/run/count。原纳秒值不截断、不改单位。
- 仿真标定有效期为排他右端，旧2.1s不能覆盖最后扫描末端2.1s；调整至2.2s。
  这只是具名fixture配置，不声称取得实机标定。

## 执行与结果

```bash
bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_sens_train_01*.py' -v
bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_*.py'
bash ros_ws/sim01_env.sh python ros_ws/sens_train_01_run.py --fixture motion --port 11447
bash ros_ws/sim01_env.sh python ros_ws/sens_train_01_run.py --fixture single --port 11447
bash ros_ws/sim01_env.sh python ros_ws/sens_train_01_run.py --fixture multiray --port 11447
```

回环socket在默认沙箱中被禁止，取得本机网络执行权限后运行；每次先检查端口，
新建run目录，串行执行，仅清理本次启动的进程组。不存在硬件连接或外网采集。

| 场景 | 状态/clock收据 | Radar/IR/监督/落盘 | 核验及清理 | 报告 |
| --- | --- | --- | --- | --- |
| motion，schema 0.2 | 22/22 | 各20 | 全载荷/值/几何/图通过，子进程退出0，端口释放 | [报告](../.runtime/runs/sens-train-01-20261013T185006228533/validation.json) |
| single，schema 0.1 | 20/20 | 各20 | 原入口回归及文件/收据/值/图通过，子进程退出0，端口释放 | [报告](../.runtime/runs/sens-train-01-20261013T185106202484/validation.json) |
| multiray，schema 0.1 | 20/20 | 各20 | 原双射线/遮挡oracle、文件/收据/值/图通过，子进程退出0，端口释放 | [报告](../.runtime/runs/sens-train-01-20261013T185144954036/validation.json) |

每个通过目录保留配置快照、`training-records.jsonl`、五类`*-receipts.jsonl`、
`validation.json`与ROS日志。训练专项31/31、全仓300/300轻量测试通过。
三个run停机后，在独立新Python进程中重新读取配置、训练记录和五类收据调用
`validate_training_run`，全部通过且与原报告audit一致，没有重写报告或原始产物。
7个修改Python文件的`py_compile`、`git diff --check`及新增文件尾部空白检查通过；
运行日志中的训练节点PID已退出，子进程回收与端口释放均保留在运行证据中。
新增测试覆盖状态与clock先后顺序、无提前输出、缺历史、未排空、身份/时钟异常、
缓存边界，以及收据丢失/乱序、坐标/像素/时钟/原始点/补偿点/unknown标签篡改拒绝。

## 修改文件

- 业务与配置：`sensors/ufm_sensors/training_stream.py`、
  `configs/sens_train_01_motion_fixture.yaml`。
- ROS：`ros_ws/launch/sens_train_01.launch`、`ros_ws/sens_train_01_run.py`、
  `ros_ws/src/uav_fusionmap_simulation/scripts/sens_train_01_source_node.py`、
  `ros_ws/src/uav_fusionmap_sensors/scripts/sens_train_01_fake_lidar_node.py`、
  `ros_ws/src/uav_fusionmap_sensors/scripts/sens_train_01_recorder_node.py`。
- 测试：`tests/test_sens_train_01_stream.py`、`tests/test_sens_train_01_ros.py`。
- 配套：`PROJECT_STATUS.md`、`docs/DEVELOPMENT_PLAN.md`、`docs/DECISION_LOG.md`、
  `docs/EXPERIMENT_LOG.md`、`docs/SENS_TRAIN_01_IMPLEMENTATION_PLAN.md`、
  `docs/DATA_FORMAT.md`、`docs/SENSOR_INTERFACE.md`、`docs/COORDINATE_SYSTEM.md`及本记录。

## 结论、限制与恢复

**非零扫描ROS fixture子范围已完成；完整SENS-TRAIN-01仍进行中。**
LiDAR只在训练支路，不进入在线SensorBundle、forward、定位或mapping。当前ROS短测
是低速直线功能级场景，射线时刻恰好有状态样本；旋转/插值及异常历史由纯函数/流
测试覆盖，未开展ROS旋转或故障注入。未取得真实设备时间、外参、同步残差，未测
机载功耗/20ms性能，未训练或运行研究模型，未做大规模数据或科研对照试验。

缓存只面向有限短测，不能宣称具备长期流处理或高速扫描精度。失败时停止使用
`motion`入口并保留诊断，继续使用两个已验证零时长入口；不改写历史产物。
下一关口：评审更多几何/运动场景及覆盖率/补偿误差统计；硬件相关验收继续单列
阻塞，对照试验仍放在工程数据与接口门禁之后。
