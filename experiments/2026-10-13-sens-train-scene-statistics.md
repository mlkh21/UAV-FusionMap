# EXP-20261013-006：训练场景矩阵与标签统计

- 日期：2026-10-13；主责任角色：sensor_engineer；类型：离线功能级验收及旧ROS入口回归。
- 关联任务：SENS-TRAIN-01/T-13；决定：ADR-020；完整SENS-TRAIN-01仍进行中。
- 分支：`feature/engineering-initialization`；原有未提交改动保留，未提交/推送。
- Python：`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，经入口核对。
- 无GPU、硬件、实测记录、研究权重或外网采集依赖；不修改研究仓库/在线接口。

## 方案与验证

配置：[12场景矩阵](../configs/sens_train_01_scene_matrix.yaml)，每场景3个中点
1.0/1.01/1.02s，200ms扫描含5束射线，时槽0/50/100/150/200ms。源状态覆盖所有
扫描首尾和中点，但50/150ms时刻需要插值。源为北向平移与独立偏航运动学fixture，
不是动力学一致的固定翼转弯；状态保留simulation来源，不冒充真实PX4估计。

调用链：simulation状态 → sensors状态适配 → TrainingScanBuffer → 训练生成函数
→ 独立JSONL → 回读审计。脚本属于tests，不增加业务层间旁路或在线LiDAR。
每个场景保存完整配置、源状态与训练记录；新输出目录拒绝覆盖，run_id用目录名
与case_id区分。不存在哈希、研究训练或覆盖旧数据操作。

审计不调用生产私有射线/插值函数：以面平面交点检查首个进入障碍内部的命中，
解析偏航/平移检查采样坐标和中点补偿世界坐标；同时核对点时间、状态sample_id、
occupied端点、遮挡unknown、全无回波unknown、Radar坐标与IR全部像素。
几何数值容差1e-6m，不是物理测量精度阈值；误差报告count/mean/最近秩P95/max，
无回波时误差为null，不填零。

## RED/GREEN

新专项测试先因缺少矩阵入口失败。首轮实际矩阵在speed_35发现同一世界表面的
两次回波补偿y约为`3.9e-16`与`-7.8e-16`，位于网格整数边界两侧；标签出现
occupied 828/836两个单元，正确同一表面应只占836。
[原失败报告](../.runtime/runs/sens-train-scenes-20261013T194939381595/report.json)
与speed_35输入/记录均保留。其cases数组有前5个已通过场景；首版未写汇总count，
控制台默认显示0，不能据此说没有部分产物。后续补入增量count，没有重写旧报告。

针对性回归复现`[828,836] != [836]`后，仅修复训练体素取整：缩放网格坐标距整数
不超过`8*float64_epsilon*max(1,abs(scaled))`时先吸附再floor。加入±1e-9m边界位移
回归，证明真实边界两侧仍不同；没有改变射线擦边、同步、FOV、量程门限。
新增Radar坐标/IR像素篡改负例先失败，再补独立输入oracle。原始/补偿点、引用状态、
缺回波或给无回波区域伪造free等篡改均拒绝。

## 执行与统计

```bash
bash ros_ws/sim01_env.sh python tests/sens_train_01_scene_suite.py
bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_sens_train_01*.py'
bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_*.py'
bash ros_ws/sim01_env.sh python ros_ws/sens_train_01_run.py --fixture motion --port 11447
bash ros_ws/sim01_env.sh python ros_ws/sens_train_01_run.py --fixture single --port 11447
bash ros_ws/sim01_env.sh python ros_ws/sens_train_01_run.py --fixture multiray --port 11447
```

最终[矩阵报告](../.runtime/runs/sens-train-scenes-20261013T195717087251/report.json)
通过12场景/36记录；另以新Python进程从磁盘重新读取矩阵、各场景配置、源状态和
训练记录，重新审计结果逐项等于报告。中间通过版本195146/195452保留，最终版本
还检查Radar/IR并使用每个输出run独立身份，不覆盖中间版本。

| 场景 | 回波/15时槽 | 插值回波 | observed比例 | 最大补偿残差(m) |
| --- | --- | --- | --- | --- |
| 单障碍静止 | 9 | 3 | 0.8594% | 8.882e-16 |
| 双障碍静止 | 12 | 3 | 1.3281% | 8.882e-16 |
| 1m/s平移 | 12 | 3 | 1.3281% | 1.831e-15 |
| 平移+20deg/s偏航 | 12 | 3 | 2.1875% | 3.085e-7 |
| -20deg/s偏航 | 11 | 3 | 2.0313% | 3.058e-7 |
| 35m/s平移 | 9 | 3 | 1.2240% | 1.939e-15 |
| 50m/s平移 | 7 | 3 | 1.1719% | 1.422e-15 |
| 70m/s平移 | 6 | 3 | 0.9635% | 1.237e-15 |
| 近距离双障碍 | 12 | 3 | 0.7031% | 8.951e-16 |
| 后方遮挡障碍 | 12 | 3 | 1.3281% | 1.831e-15 |
| 量程截断2m | 0 | 0 | 0 | 不计算 |
| 空场景 | 0 | 0 | 0 | 不计算 |

总计180个射线时间槽，102回波（30插值）、78无回波。36×1280=46080个逐帧网格
标签：free 442、occupied 62、unknown 45576，observed=504/46080=1.09375%。
这不是唯一世界体素覆盖、感知召回或训练充分性；重复扫描的网格独立计数。
现有`_slerp`小角度分支采用归一化线性插值，推断约3.09e-7m偏航残差可由该近似
解释；此轮没有更换插值实现或开展算法比较，残差只是无噪声理想模型的数值一致性。

标签共享函数改动后，旧ROS入口实际回归：

| 入口 | 记录/收据 | 结果 | 运行报告 |
| --- | --- | --- | --- |
| motion | 22状态/clock、20组Radar/IR/监督/落盘 | 核验通过、退出0、端口释放 | [报告](../.runtime/runs/sens-train-01-20261013T195231263965/validation.json) |
| single | 20状态/clock、20组记录 | 同上 | [报告](../.runtime/runs/sens-train-01-20261013T195503433819/validation.json) |
| multiray | 20状态/clock、20组记录 | 同上 | [报告](../.runtime/runs/sens-train-01-20261013T195713504519/validation.json) |

ROS回归经本机回环权限执行；仅启动隔离fixture、新run目录与本次进程。
定向40/40、全仓309/309轻量测试通过。
5个修改Python文件的`py_compile`、`git diff --check`、新增文件尾部空白及7份配套
文档链接检查通过；三个ROS回归日志中的9个训练节点PID已退出，端口均释放。

## 修改清单

- `simulation/ufm_simulation/perf01a_fixture.py`：增加具名运动学扫描状态。
- `sensors/ufm_sensors/training_supervision.py`：稳定训练标签的浮点边界索引。
- `configs/sens_train_01_scene_matrix.yaml`：12场景、时槽、数值检查配置。
- `tests/sens_train_01_scene_suite.py`：记录、回读、独立oracle及统计入口。
- `tests/test_sens_train_01_scene_suite.py`：场景、篡改、隔离身份/拒绝覆盖测试。
- `tests/test_sens_train_01.py`：同表面索引及真实边界两侧RED/GREEN。
- `PROJECT_STATUS.md`、`docs/DEVELOPMENT_PLAN.md`、`docs/DECISION_LOG.md`、
  `docs/EXPERIMENT_LOG.md`、`docs/DATA_FORMAT.md`、
  `docs/SENS_TRAIN_01_IMPLEMENTATION_PLAN.md`及本记录。

## 限制与下一步

**离线场景统计子范围已完成，ROS偏航/插值、完整SENS-TRAIN-01仍待验。**
每帧仅5束射线、3个密集中点，稀疏且无噪声，不可用于证明真实传感器/长期流处理、
固定翼飞行动力学、统计数据集或模型质量。高航速只是运动扫描几何，不是20ms
实时通过；本次未测实机功耗、设备时钟或运行模型。LiDAR仍只在训练支路。
停止使用新矩阵入口即可停用该新增验收工具，原三个ROS入口已回归；全部旧产物
保持不变。下一步评审将偏航/插值接入ROS训练短测，随后推进T-14状态兼容镜像和
唯一TF；正式PERF-01外部输入仍阻塞，对照试验继续最后。
