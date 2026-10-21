# EXP-20261005-003：SIM-01D跨边界连续性验收

## 基本信息

- 日期：2026-10-05
- 责任角色：simulation_engineer
- 关联任务：SIM-01D、R-10、REQ-04、REQ-11
- 类型：真实PX4-JSBSim-MAVROS连续仿真、边界checker、bag回读、清理审计
- 运行目录：`.runtime/runs/sim01d-live-20261005T231430430819`
- Python：`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`
- bridge：`.runtime/build/jsbsim-bridge-sim01d/jsbsim_bridge`
- 变更范围：未修改桥接、PX4、公共消息或业务状态机；仅执行既有专用运行器

## 目的与门槛

验证修复后的JSBSim bridge能在真实ROS短测环境中连续运行，跨越32位微秒边界
`2147483647000 ns`，并保持至少`2400000000000 ns`有效源状态跨度。该验收独立于
SENS-IR-01和PERF-01；不把传感器短测、开发机P99或短窗倍速结果替代为SIM-01D证据。

## 前置检查

- `test_sim01d_contract.py`：6项通过。
- 独立端口/PID前检：通过；11371、4560、14540、14580、18570、14280、13030均空闲。
- 候选bridge动态库检查：`ldd`返回码0，无`not found`。
- 运行前未发现残留的SIM-01D、bridge、PX4、MAVROS或ROS Master进程。

## 实际命令

```bash
bash ros_ws/sim01_env.sh \
  /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/sim01d_record.py \
  --bridge-binary \
  /home/zxj/catkin_ws/src/UAV-FusionMap/.runtime/build/jsbsim-bridge-sim01d/jsbsim_bridge
```

## 结果

运行器于`2026-10-05 23:14:30 +0800`启动并正常收尾，主命令返回`exit=0`，
`errors=[]`、`cleanup=true`。有效窗口为：

- `t0_ns=15947999000`
- `t1_ns=2415951999000`
- `valid_span_ns=2400004000000`，超过门槛`2400000000000`
- `boundary_ns=2147483647000`，`boundary_crossed=true`
- clock：120786条，约49.9999 Hz，最大间隔24001000 ns
- source state：48002条，约19.99997 Hz，最大间隔60000000 ns
- sensor state：48002条，约19.99997 Hz，最大间隔60000000 ns
- 实时记录总计1137675条；bag回读各主题计数与记录器收据一致，队列为空

`validation.json`、`writer-closed.json`和`cleanup-audit.json`均为`passed=true`。
收尾审计中bridge以受控SIGINT退出，未列入`forced`，其余子进程正常退出；端口
和受审计Python进程均清理完成。这是运行器的受控收尾，不是业务故障。

## 证据

- [manifest.json](../.runtime/runs/sim01d-live-20261005T231430430819/manifest.json)
- [validation.json](../.runtime/runs/sim01d-live-20261005T231430430819/validation.json)
- [window.json](../.runtime/runs/sim01d-live-20261005T231430430819/window.json)
- [writer-closed.json](../.runtime/runs/sim01d-live-20261005T231430430819/writer-closed.json)
- [cleanup-audit.json](../.runtime/runs/sim01d-live-20261005T231430430819/cleanup-audit.json)
- [live.bag](../.runtime/runs/sim01d-live-20261005T231430430819/live.bag)
- [source-audit.jsonl](../.runtime/runs/sim01d-live-20261005T231430430819/source-audit.jsonl)
- [sensor-audit.jsonl](../.runtime/runs/sim01d-live-20261005T231430430819/sensor-audit.jsonl)

## 结论与边界

SIM-01D通过，R-10关闭。该结果证明本候选版本在本次独立Noetic/Conda运行环境中
跨越指定32位微秒边界并完成连续状态/时钟记录和清理对账。它不证明PERF-01的目标
机载资源、5 ms同步/20 ms性能预算、真实Radar/IR质量、研究模型质量、训练监督LiDAR
隔离或完整Phase 1退出；这些仍按各自任务独立验收。
