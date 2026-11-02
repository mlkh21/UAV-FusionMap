# EXP-20261026-001：Phase 2 传感器软件双图整合验收

- 日期：2026-10-26；主责任角色：sensor_engineer（integration_engineer配合ROS验证）。
- 范围：现有功能级fake Radar/IR在线图、训练专用LiDAR监督图及轻量回归。
- Python：`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`；ROS经`bash ros_ws/sim01_env.sh`。
- 工作区：`feature/engineering-initialization`，运行前已有未提交改动均保留；不修改研究仓库。

## 预期与执行

使用现有生产者、matcher、SensorBundle、placeholder和Local Map节点，独立核对
在线消息身份、时间、值、原由拒绝及运行时图隔离；另用训练yaw图核对Radar/IR、
训练LiDAR监督、扫描内插值和无回波unknown。两个在线run不得出现训练LiDAR，
训练监督不得进入SensorBundle、定位或mapping。所有run需有独立端口、目录和清理收据。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  -m unittest discover -s tests -p 'test_*.py' -q
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  ros_ws/perf01a_async_run.py --scenario parameterized_sensors --duration-s 2 \
  --verify-radar-values --audit-online-graph --port 12571
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  ros_ws/sens_train_01_run.py --fixture yaw --port 12572
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  ros_ws/perf01a_async_run.py --scenario ir_value_transport --duration-s 2 \
  --verify-ir-values --verify-radar-values --audit-online-graph --port 12573
```

首次在线运行在受限沙箱创建socket时被拒，未创建该run目录；获本机回环端口许可后
按同参数运行。运行器只写入`.runtime/runs/`下新的唯一目录，没有覆盖历史报告。

## 实际结果

| 独立run | 证据与实际结果 |
| --- | --- |
| [参数化在线](../.runtime/runs/perf01a-async-20261026T105311198727/perf-report.json) | `passed=true`、`errors=[]`；40 Radar、100 IR发送并收到，20 Bundle/占据/地图闭合，20次预期`radar_ir_timeout`拒绝、意外传输丢失0；40原始Radar与20采用Bundle逐点值核对`errors=[]`；7个在线节点齐全且训练/LiDAR话题和节点均为空。开发机回调到占据P99 `42.983652 ms`，20ms诊断未通过。 |
| [训练yaw](../.runtime/runs/sens-train-01-20261026T105349388288/validation.json) | `passed=true`、`errors=[]`；Radar/IR/监督各20，状态/clock各22；schema 0.2、20组记录全载荷及Radar/IR数值闭合，200ms扫描共100时间槽（80回波、20无回波），20回波完成插值，40次未知区域探针保留unknown。LiDAR仅由训练fake节点发布、仅训练runner/recorder订阅。 |
| [IR值级在线](../.runtime/runs/perf01a-async-20261026T105504513917/perf-report.json) | `passed=true`、`errors=[]`；40 Radar/100 IR、20 Bundle/占据/地图闭合，20次预期拒绝、意外传输丢失0；100原始IR与20采用Bundle全像素、40原始Radar与20采用Bundle逐点核对均`errors=[]`；在线训练/LiDAR节点及话题为空。开发机P99 `44.375068 ms`，20ms诊断未通过。 |

在线两run的`clock_publishers`均仅`/perf01a_source`；两run的master端口关闭、
子进程退出0、未强制结束且进程组无残留。训练run端口释放、子进程退出0。
全仓轻量测试`Ran 386 tests ... OK`。未修改业务代码、公共ROS消息或测试期望。

## 阶段分账与下一步

本次仅将Phase 2的**fake Radar/IR在线值级闭环、训练yaw监督及双图隔离软件子范围**
标为已验证；不重复宣称已有T-13A、SENS-TRAIN-COV-01/02的独立子项被新run关闭。
本run没有验证独立ImuSample生产与消费、真实Radar/IR驱动和原始记录、设备间
时钟映射与残差、真实安装外参或训练数据规模和真实性。Phase 2完整退出保持进行中，
Phase 1的PERF-01/ENV-03及Phase 3研究模型均不因此关闭。

下一步按Phase 2原交付先核对独立IMU功能级交付所需合同和现有状态链能力，
有可执行的软件子范围时另行具名验收；真实设备相关项仅在提供原始数据、
采集时钟和标定证据后启动，不以fixture代替。此记录位于当前忽略的experiments目录，
后续版本化需逐文件检查忽略/提交范围，不自动提交或改忽略规则。
