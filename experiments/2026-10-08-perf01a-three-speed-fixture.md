# EXP-20261008-002：三航速大图ROS功能级回归

- 日期：2026-10-08；任务：PERF-01-A功能级回归；主责任角色：integration_engineer。
- 状态：已执行，三档均未通过严格配对；本文件只记录新run，不修改历史产物。

## 范围与判定

在当前开发机已有的`perf01a_async_run.py`和`normal`场景，使用
`--full-ir --pairing-policy exact`，分别以35/50/70 m/s运行2秒，
各自选择空闲Master端口并产生全新目录。Radar/IR继续来自fake fixture，
没有设备采样时钟、目标机载平台或外部功耗。`--endpoint-probe`用于显式记录
设备采样时钟不可用；不打开IR像素额外订阅或默认关闭的锁追踪。

预期每条run：40个Radar计划，20采用/20按原规则严格拒绝；
状态/clock完成排空、Bundle到MapSnapshot身份与地图oracle闭合，资源角色齐备，
ROS端口/PID清理成功。逐run记录report路径、`passed/errors`、采用/拒绝数、
radar回调到占据就绪P99和`capture_clock_status`。任何失败均保留原目录，
不能改写oracle或略去失败run。20ms只做开发机诊断，不作为机载验收结果。

## 预登记命令

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01a_async_run.py --scenario normal --full-ir --duration-s 2 \
  --speed-mps 35 --pairing-policy exact --endpoint-probe --port 12145
# 同样参数分别改为 --speed-mps 50 --port 12146、--speed-mps 70 --port 12147。
```

运行前检查解释器、端口监听和现有ROS进程；新run正常结束后逐run核对
`perf-report.json`，不把SIM-01D长测、fake传感器短测或纯Python单测互相替代。

## 实际结果

在隔离端口依预登记命令顺序运行；解释器均为
`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。沙箱内socket创建遭
`PermissionError`，获得独立授权后在沙箱外执行真实ROS短测，不改变配置和验收门限。

首次35m/s运行目录`perf01a-async-20261008T144232603511`：ROS参数服务器不能
封送`normal`场景可选Radar门控配置中的YAML `null`，启动阶段
`TypeError: cannot marshal None unless allow_none is enabled`；资源覆盖及地图aging
随之缺失，原目录保留。新增`ros_param_profile()`只对写入ROS参数服务器的副本
省略可选空字段，磁盘配置及原始profile不变；新增单测先RED（函数缺失），后GREEN
（真实normal配置可由XML-RPC封送）。未修改sync/timeout/oracle。

| 速度及端口 | run目录（均位于`.runtime/runs/`） | 收据、闭合与拒绝 | 资源/清理 | 回调到占据P99 |
| --- | --- | --- | --- | --- |
| 35m/s 12145 | `perf01a-async-20261008T144440443192` | Radar 40/40、IR 100/100；Bundle/Occupancy/Map均0；40拒绝（1 infrared_unavailable，39 radar_ir_timeout）；预登记20采用/20拒绝，失败 | 角色齐全、无采样错误；进程组和端口清理通过 | 无有效样本，null |
| 50m/s 12146 | `perf01a-async-20261008T144544783005` | Radar 40/40、IR 100/100；Bundle/Occupancy/Map均0；40拒绝（1 infrared_unavailable，39 radar_ir_timeout）；预登记20采用/20拒绝，失败 | 角色齐全、无采样错误；进程组和端口清理通过 | 无有效样本，null |
| 70m/s 12147 | `perf01a-async-20261008T144617303467` | Radar 40/40、IR 100/100；Bundle/Occupancy/Map均0；40拒绝（1 infrared_unavailable，39 radar_ir_timeout）；预登记20采用/20拒绝，失败 | 角色齐全、无采样错误；进程组和端口清理通过 | 无有效样本，null |

35m/s第一条Radar在仿真时钟41ms被拒；同刻IR的匹配器收据显示到达时仿真时钟
已到86ms，比拒绝事件晚约49ms。其余样本同样因严格等待超限拒绝；这是
ROS大图传输/调度相对仿真时钟过慢的观测，尚未归因到单一阶段。
各run`perf-report.json`、`matcher-audit.json`、收据、事件、资源等原始证据保留。
端点探针仅说明开发机fixture没有物理设备采样时钟；本次没有可计算的P99，不能将
三条失败转换为速度可用、20ms达标或正式`formal_ready`。下一步在原始收据和分段审计
约束下预登记一个可控候选，保持5ms同步、严格拒绝、20ms目标和原失败run不变。
