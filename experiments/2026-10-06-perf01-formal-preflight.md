# EXP-20261006-001：PERF-01正式输入与证据预检

- 日期：2026-10-06；任务：PERF-01；主责任角色：Technical Lead。
- 类型：平台/设备只读审计、配置门禁、正式证据契约测试；未启动ROS或长测。
- 目的：在继续正式20 ms测量前确认当前主机、真实传感器、采样时钟和证据入口是否满足
  PERF-01前置条件；不把fake/fixture短测或当前开发机资源写成机载验收。

## 1. 输入与范围

本轮复用[`configs/perf01_budget.yaml`](../configs/perf01_budget.yaml)和只读预算门禁
[`ros_ws/perf01_budget_gate.py`](../ros_ws/perf01_budget_gate.py)，新增正式证据预检
[`ros_ws/perf01_formal_preflight.py`](../ros_ws/perf01_formal_preflight.py)。预检只读取预算
和一份已完成运行的manifest，检查平台、Radar/IR物理采样依据、正式起止端点、跨时钟映射、
连续时长、运行目录及必需证据文件；不采集硬件、不启动ROS、不验证证据内容的物理真实性。

5 ms Radar—IR同步门限、严格拒绝理由和20 ms端到端P99目标保持不变。

## 2. 平台与设备审计

当前主机事实：

- Intel Core i9-14900HX，32逻辑CPU，内存约31 GiB；
- NVIDIA RTX 4070 Laptop GPU，驱动580.178.04；本次抽样显存685 MiB、功耗5.62 W、
  温度39°C、GPU利用率38%；
- ROS Noetic和Conda环境有效，Python为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，
  版本3.8.12；
- 仅发现`/dev/video0`、`/dev/video1`、`/dev/media0`集成摄像头设备；未发现ARS548、
  Micro III Lite、串口设备或对应物理传感器输入；当前无ROS Master或在线传感器节点；
- CPU仅有RAPL长期上限约140 W，`energy_uj`不可读，未取得外部功耗仪证据。

因此当前主机不是预算中参考的Jetson Orin NX 16GB/25 W目标平台；RTX 4070遥测不能替代
Jetson GPU/NVDLA、整机功耗或持续热状态证据。

## 3. 门禁结果

预算门禁命令：

```bash
bash ros_ws/sim01_env.sh \
  /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01_budget_gate.py configs/perf01_budget.yaml
```

结果：`mode=reference_only`、`ready=false`、`errors=[]`，正式输入阻塞10项；
`--require-formal`退出码为1。阻塞包括目标平台、formal_measurement状态及平台ID、
正式起止点、设备采样时钟、跨时钟映射、连续时长、Radar实际频率/时间误差和IR选定配置。

正式证据预检新增以下拒绝条件：

- manifest必须绑定同一运行目录，且状态为`COMPLETE`、退出码为0并声明测量完成；
- Radar/IR必须提供物理采样频率来源，不接受`fixture_frequency_hz`、仿真时间或`/clock`；
- 测量持续时长必须使用与采样时钟相同的非仿真时钟；
- 必需证据必须存在于运行目录内并标记通过；
- `formal_ready`只表示证据契约完整，不表示性能通过。

## 4. 验证

使用Conda解释器执行：

```bash
bash ros_ws/sim01_env.sh \
  /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  -m unittest discover -s tests -p 'test_perf01*.py' -q
```

结果：预算门禁和正式证据预检相关测试通过；新增预检覆盖合成正式配置正例、当前参考配置、
fixture频率替代、仿真时间替代、证据缺失/目录错绑、嵌套输入错误和非mapping配置错误。
纯Python测试不代表ROS实时性能或目标平台验收。

## 5. 结论与恢复条件

PERF-01仍为“进行中，正式输入阻塞”，不是性能通过，也不是性能失败。当前开发机fake/fixture
结果和最新IR值守恒短测的约45.144 ms P99均不能解除门禁；SIM-01D的独立持续性结果也不替代
PERF-01。

解除阻塞前必须提供并审查：目标平台唯一ID和功耗模式、ARS548实际配置与物理采样时间、
Micro III Lite确切变体/镜头/触发与帧率、20 ms正式起止点、设备时钟到统一单调时钟的
offset/drift/误差界、连续运行时长、资源/功耗/温度证据及真实设备丢帧账本。获得这些外部
输入后，先填入正式配置并通过`--require-formal`和manifest预检，再按35/50/70 m/s矩阵
执行目标平台短预检及连续正式测量。

本轮未修改研究仓库、未修改历史实验产物、未启动长训练或正式ROS性能运行。
