# PERF-01 高速感知—地图时空预算

版本：v0.1；更新日期：2026-10-08；责任角色：Technical Lead。
状态：工程估计基线已建立；航速点、参考传感器、暂定平台和低空场景已填入，仍待用户确认与实测。

## 1. 目的与边界

PERF-01用于把高速固定翼无人机的航速、传感器时序、感知处理、地图更新和运行资源
转成可测量的预算。本文只冻结输入和预算方法，不把设计参数、开发机规格或一次运行
结果写成机载实时能力。

本任务不关闭以下事项：SIM-01D跨35.8分钟时间边界、真实Radar—IR感知质量、地图算法
质量、机载部署、HIL或实飞。SIM-01C/SIM-SPEED-01的短窗倍速结果也不替代本任务。

## 2. 已确认输入

| 项目 | 当前值 | 状态与含义 |
| --- | --- | --- |
| 验收航速点 | 35、50、70 m/s | 已确认；分别代表低/中/高工作点，不等同于已通过验收 |
| 4D Radar参考 | ARS548；FOV 120°×30°；有效距离300 m | 用户已确认的参考参数；频率、点率、时间误差和目标相关有效探测条件仍须以选定配置/数据表及项目测试绑定 |
| LiDAR参考 | mid360 | 仅作为`training_data_generation`的监督覆盖参考；不得进入在线SensorBundle、感知forward、定位或mapping |
| 机载计算平台 | Jetson Orin NX 16GB，25 W参考模式 | 工程估计；不是已采购或已部署平台 |
| 热红外规格 | Micro III Lite 640；640×512；50 Hz；9.1 mm临时镜头约48.1°×38.4° | 核心型号已暂定；FOV、时间误差和外触发仍需实测/定型 |
| 低空场景 | AGL 50 m；2 m障碍物；名义距离200 m；前视300 m；转弯半径250 m | 常用工程估计；不是飞行安全边界 |

ARS548的120°×30°和300 m在本任务中是用户确认的参考参数，不代表仓库已有对应驱动、
标定、逐目标实测数据或在线接入。有效距离还需说明目标类型、反射条件、姿态和环境。
mid360仍遵守项目的训练监督LiDAR隔离规则。

Jetson Orin NX 16GB的25 W模式、Micro III Lite 640的640×512/50 Hz和0.50 W量级参数用于
建立工程预算；平台型号、功耗模式、镜头、同步误差和温度条件确认前，不能写成机载通过。

## 3. 航速到时间误差的可计算预算

平移误差的一阶上界使用：

```text
e_translation = v_mps × delta_t_s
```

下表是预算换算，不是已经接受的目标阈值。最终允许误差必须结合障碍物尺寸、前视距离、
地图分辨率、姿态/角速度和固定翼转弯场景确认。

| 端到端数据年龄 Δt | 35 m/s | 50 m/s | 70 m/s |
| ---: | ---: | ---: | ---: |
| 5 ms | 0.175 m | 0.250 m | 0.350 m |
| 10 ms | 0.350 m | 0.500 m | 0.700 m |
| 20 ms | 0.700 m | 1.000 m | 1.400 m |
| 50 ms | 1.750 m | 2.500 m | 3.500 m |

角运动不能由上表覆盖。传感器扫描时间、曝光区间、姿态插值年龄和雷达参考时刻必须
单独记录；若扫描内运动不可忽略，还需使用逐点时间或明确声明限制。

## 4. 必须采集的计时点

所有计时均保留仿真/设备业务时间和独立单调墙钟时间，不能用两者直接相减。最小链路为：

```text
Radar/IR receive
  → timestamp conversion and synchronization
  → SensorBundle ready
  → perception start/end
  → OccupancyObservation ready
  → mapping update start/end
  → MapSnapshot publish
```

每个航速点至少报告：

- 端到端延迟和数据年龄的 P50/P95/P99；
- Radar—IR时间差、姿态年龄、缓存等待和超时率；
- 每路输入、SensorBundle、感知输出和地图更新的频率、丢帧率、重复/乱序率；
- CPU/GPU/NPU占用、峰值内存、功耗（若平台可测）和持续运行时长；
- 地图更新周期、覆盖范围、分辨率、内存增量和过期观测比例。

## 5. 验收矩阵（待补齐阈值）

| 维度 | 35 m/s | 50 m/s | 70 m/s | 当前状态 |
| --- | --- | --- | --- | --- |
| 直线飞行 | 估计基线 | 估计基线 | 估计基线 | AGL 50 m、2 m障碍、200 m名义距离 |
| 转弯/角运动 | 0.14 rad/s | 0.20 rad/s | 0.28 rad/s | 250 m转弯半径的一阶估计 |
| Radar—IR同步 | ≤5 ms | ≤5 ms | ≤5 ms | 工程目标，需外触发实测 |
| 感知端到端P99 | ≤20 ms | ≤20 ms | ≤20 ms | 目标平台25 W模式下测量 |
| 地图更新周期/年龄 | 20 Hz / ≤100 ms | 20 Hz / ≤100 ms | 20 Hz / ≤100 ms | 0.5 m分辨率，300×120×60 m参考覆盖 |
| 资源与稳定性 | ≤25 W模块功耗 | ≤25 W模块功耗 | ≤25 W模块功耗 | 16 GB内存；连续时长待确定 |

## 6. 关闭条件与下一步

PERF-01只有在以下信息具备来源并进入配置后，才能从“工程估计基线”转为“可执行
验收”：

1. 确认Jetson Orin NX 16GB/25 W是否作为目标平台，或替换为实际平台；
2. 确认Micro III Lite镜头、外触发链路和时间误差；
3. 通过低空场景评审确认50 m AGL、2 m障碍物、200/300 m距离等估计；
4. 实测最大空间误差、Radar—IR偏差、姿态年龄、端到端P50/P95/P99、丢帧/超时率；
5. 实测地图分辨率、覆盖范围、更新频率、内存上限和老化时限。

在这些条件确定前，下一步是冻结配置并做计时接口/观测点设计，而不是启动长时间
高速仿真或宣称机载实时通过。

### 6.1 预算门禁预检（2026-10-05）

已增加只读预检[`perf01_budget_gate.py`](../ros_ws/perf01_budget_gate.py)，其输入为
[`configs/perf01_budget.yaml`](../configs/perf01_budget.yaml)，不启动ROS、不修改配置或
运行产物。当前配置的结果必须是`mode=reference_only`，直到以下字段有明确来源并完成
评审：

- 目标机载平台已选定，且功耗测量方法固定；
- 正式测量的`start_endpoint`、`end_endpoint`、设备采样时钟源和跨时钟映射；
- Radar频率/时间误差与IR型号、镜头、外触发和时间误差；
- 连续运行时长及正式平台身份。

复现命令：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01_budget_gate.py configs/perf01_budget.yaml
```

当前预检输出`reference_only`，没有错误，但列出10项正式输入阻塞；这不是PERF-01失败
或通过。`--require-formal`仅用于在正式测量入口中确认配置已解除阻塞，不能用来把参考
估计强制变成正式配置。5 ms Radar—IR同步门限、严格拒绝理由和20 ms P99目标由预检锁定，
不会因开发机短测结果自动放宽。

### 6.2 正式证据manifest预检（2026-10-06）

新增只读[`perf01_formal_preflight.py`](../ros_ws/perf01_formal_preflight.py)，用于正式
运行完成后的证据契约检查。它复用§6.1预算门禁，不启动ROS、不采集硬件、不修改运行产物，
要求manifest绑定同一运行目录，并检查平台身份、Radar/IR物理采样频率来源、正式起止点、
采样时钟、跨时钟映射、连续时长和必需证据文件。

预检明确拒绝以下替代关系：

- fake/fixture频率不能替代真实设备采样频率；
- 仿真时间或`/clock`不能替代设备采样时钟和持续时长时钟；
- 运行目录外的证据不能作为该次正式运行的证据；
- `formal_ready`只表示manifest满足证据契约，不表示20 ms性能通过。

2026-10-06平台审计确认当前主机为x86笔记本，未发现参考Jetson、ARS548或Micro III Lite
物理输入，也没有外部功耗和设备时钟证据。因此当前配置继续保持`reference_only`，不启动
正式PERF-01运行。详细结果见[EXP-20261006-001](../experiments/2026-10-06-perf01-formal-preflight.md)。

### 6.3 证据内容数值预检（2026-10-08）

§6.2的六类必需证据现在必须是可解析的JSON对象；空文件、`{}`和只有
`{"passed": true}`均拒绝。每个文件统一包含`run_id`、`speed_mps`、
`source_type: measured`、`clock_source`（与manifest声明相同）及`data`对象。
一个manifest只对应一个航速、一次连续运行；35/50/70 m/s全矩阵必须分别有记录。
合成正例仅用于验证检查器，不是正式运行产物。

| 证据键（JSON文件） | `data`最小字段与核验 |
| --- | --- |
| `monotonic_stage_timestamps` | `start_endpoint`、`end_endpoint`与预算一致；`samples`逐项给`sample_id`、`start_monotonic_ns`、`end_monotonic_ns`，唯一、严格按采样起点递增，依据确认频率和声明丢帧数限制相邻间隔并覆盖连续窗口；单样本年龄不超过`max_end_to_end_age_ms` |
| `p50_p95_p99_latency` | `sample_count`和`percentiles_ms.{p50,p95,p99}`；用同一次运行原始逐样本时差按nearest-rank重算，P99不超过20 ms |
| `sensor_sync_and_pose_age` | 同一批`sample_id`的`radar_ir_delta_ms`、`pose_age_ms`逐项检查，分别不超过5/10 ms |
| `input_output_drop_duplicate_out_of_order_rates` | `input_count`、`output_count`、`drop_count`、`timeout_count`、`duplicate_count`、`out_of_order_count`；输出数与样本数相同，输入=输出+丢失，丢失/超时率各不超过1%，输入数量至少达到已确认频率×持续时长扣除允许丢失后的下限 |
| `resource_and_power_measurement` | `samples`至少含首尾资源样本，每项有`monotonic_ns`、`power_w`、`rss_mb`、`cpu_percent`、`gpu_percent`、`npu_percent`、`temperature_c`；与目标平台确认的功耗/内存上限比较，采样覆盖连续窗口 |
| `continuous_run_stability` | `start_monotonic_ns`、`end_monotonic_ns`覆盖正式时长，`restart_count`、`unexpected_terminal_count`均为0 |

CLI仍为只读：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01_formal_preflight.py /absolute/path/to/formal-run/formal-manifest.json \
  --config configs/perf01_budget.yaml
```

目前仍无已确认目标平台及物理设备输入，实际配置继续被§6.1门禁拒绝。
该工具只能检查文件内部数值、自报身份及一致性；不能鉴定其确实来自设备、时钟转换
offset/drift与误差上界真实可信、资源采样覆盖中间峰值或正式航速场景的质量。
`formal_ready`始终仅为单次预检状态，不等于20 ms实测通过或PERF-01关闭。
详细RED/GREEN见[EXP-20261008-001](../experiments/2026-10-08-perf01-metric-preflight.md)。
当日[追加审阅](../experiments/2026-10-08-perf01-evidence-audit.md)又补齐两路设备
时钟身份、非有限时间误差和聚集/倒序采样行的拒绝测试。按标称Radar周期和已声明
丢帧限制帧间隔目前是保守门禁，实际设备允许的采样抖动与丢帧定义尚待确认；
不能据合成正例或JSON自报内容证明物理采样时钟/外部功率计存在。

## 7. PERF-01-A实施进度（2026-09-20）

短时占位链路技术验证已完成，见[EXP-20260920-001](../experiments/2026-09-20-perf01a-integration.md)。
统一运行器已贯通状态→fake Radar/IR→SensorBundle→占位Occupancy→稀疏MapSnapshot，
固定160样本全链身份/计数与800条事件闭合，P99 fixture事件到地图发布约3.56ms。

实际使用20Hz、单Radar点、2×2 IR和32×16×8m小格网；硬件频率仍按§2保留未确认状态。
该实测用于验证消息、时间记录和地图闭环，不验证§5的机载性能矩阵。
仅测observer自身资源；尚无全链CPU/GPU/NPU/功耗、独立Radar/IR时序、640×512负载、
观测年龄/同步故障统计及35/50/70m/s运动场景。下一步优先补齐这些可执行负载与观测指标。

复现：`bash ros_ws/sim01_env.sh python ros_ws/perf01a_run.py --duration-s 8`。
每次新建run和结果文件；无需手工分开启动observer与ROS节点。

### 完整IR负载与失效验证（2026-09-20）

已增加640×512×32FC1载荷、5ms边界、6ms超限、IR缺帧、11ms过旧位姿场景。
六个两秒ROS场景功能检查通过，128项契约通过；full_ir完成40/40地图更新，
三类失效各准确拒绝10帧并恢复，未额外丢失。见
[EXP-20260920-002](../experiments/2026-09-20-perf01a-load-faults.md)。

完整IR感知P99=30.376ms，高于20ms目标；地图发布P99=31.631ms。
本次计时包含fixture图像构造/配对，不能与上面旧3.56ms小图起点直接比较。
运行仍为paired 20Hz功能级输入，未实现独立Radar/IR频率；整链功耗、机载平台和
35/50/70m/s仍待验证。下一步优先细分大图处理/传输耗时，再细化异步匹配与资源采样。

### 大图耗时只读定位（2026-09-20）

从`perf01a-20260920T111925126408/events.json`逐样本重算，最慢样本29号的
30.376ms约由三部分组成：生成至bundle就绪10.753ms、bundle就绪至感知回调
18.806ms、回调内处理0.817ms。第二项由occupancy事件时间减去其回调处理duration
推导，仍含事件发布间隙、消息转换、序列化、排队、传输和反序列化，不能称为纯网络延迟。

同一Conda环境40次内存微基准（不启动ROS、不写运行产物）的P50为：IR序列化2.811ms、
bundle序列化2.816ms、bundle反序列化3.189ms、占位计算0.060ms；观察器对完整图像
执行min/max检查5.185ms/次，且当前对IR与bundle各检查一次。该观察开销可能干扰
同机尾延迟，尚未用对照运行证明因果；微基准结果不能替代ROS端到端验收。

后续应增加可选分段计时，将完整像素校验与低干扰计时分开运行，并保持原有校验覆盖。
本轮两次源码写入申请均因自动权限审查超时而未执行，分段计时补丁未落地。

### 分段计时与观察器对照已完成（2026-09-20后续）

上述只读定位之后，已按用户本轮授权落地20个可选分段事件和full/light观察模式。
复现矩阵与逐样本耗时见[EXP-20260920-003](../experiments/2026-09-20-perf01a-segmented-timing.md)。
18个正式大图run均10秒/200样本，完整与轻量观察各按AB/BA重复3次，另测4MiB读缓冲
候选和关闭新增分段事件的控制组；全部身份/计数闭合、零意外丢帧、清理通过。

64KiB基线各600样本汇总感知P99：full=32.376ms、light=33.965ms；最大分段为bundle
发送至感知回调，P50/P95/P99分别10.847/16.902/19.339ms（full），仍包含序列化、
队列、调度、传输和反序列化。占位感知P99=0.119ms，地图更新P99=0.165ms。
full像素回调P50约3.7ms/次，light约0.008ms/次；省略扫描降低观察器CPU，但没有稳定
改善业务尾延迟。关闭新增计时后汇总P99仍为full=33.006ms、light=32.447ms。

4MiB读缓冲未显示稳定收益，默认仍64KiB。三矩阵的18个20ms诊断全部失败，完整原始
数据和失败结论保留；134项契约及3项故障回归通过。本轮完成测量与对照，不关闭PERF-01。
下一步继续细分最大消息承载区间，再推进独立Radar/IR时序、匹配缓存及整链资源采样，
之后进入35/50/70m/s场景。40分钟SIM-01D仍独立待验，外部归档未执行。

### 线格式归因与旁路订阅成本（2026-09-20后续）

已完成实际ROS serialize/deserialize测量、两端轻量收发记录和本次进程树CPU/RSS采样，
报告及命令见[EXP-20260920-004](../experiments/2026-09-20-perf01a-wire-cost.md)。
正式三拓扑各600样本汇总感知P99：full=33.257ms、light=31.377ms、metadata=27.546ms。
metadata取消观察器IR/bundle订阅；实际图像仍随bundle进入感知，两端身份/计数核查保留。
独立IR因无订阅而跳过序列化，不能把该路发布尝试称为接收成功或与full视作同拓扑负载。

full的实际bundle serialize P50/P95/P99=4.603/6.775/7.655ms，deserialize为
2.981/5.134/6.920ms，二者线程CPU时间与墙钟接近。中间传输/排队/调度混合项为
2.111/3.549/4.475ms；另有发布前及接收后框架工作。原19ms段不能整体归因为网络。

单个NumPy接收解码候选保持线格式和业务Python容器，三对完整观察复测降幅中位数仅
0.950%，未达测试前登记的10%筛选条件，保留standard默认。15个正式run均未达20ms，
所有失败诊断保留。全仓141项契约和本轮33个短run功能检查通过，不关闭PERF-01。

资源采样覆盖source/sensor/perception/mapping/observer及本次ROS基础设施；报告标明
100%=一个逻辑核、活动窗口、采样RSS峰值及自身CPU/墙钟开销。温度只采启动值，频率
只采四个代表CPU，不足以作节点降频因果结论；GPU/NPU、功耗、机载平台仍未验收。
下一步推进独立Radar/IR发布与有界匹配缓存，沿用现有审计与基础资源采样，之后进入
35/50/70m/s。SIM-01D的40分钟持续性继续独立验收，外部归档未执行。
