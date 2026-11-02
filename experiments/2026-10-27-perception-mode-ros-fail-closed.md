# EXP-20261027-001：在线感知失效模式 ROS 链路验收

- 日期：2026-10-27
- 主责任角色：perception_engineer；tester 验证
- 范围：现有 fake Radar/IR -> SensorBundle -> disabled/research -> Local Map；
  独立验证旧 placeholder 入口。不调用研究模型、不使用硬件或训练监督 LiDAR。

## 问题、方案与恢复

原有 `modes.py` 已定义不可用占据，但先前在线 ROS 验收只覆盖 placeholder；
地图查询工具中的 `disabled` 是关闭查询服务，不是感知模式。
沿 `perf01a_placeholder.launch` 原连接，用独立观察者核对有效 Bundle 到不可用
OccupancyObservation、地图拒绝事件和空地图查询；只增加运行器与测试，
不改变业务实现、公共消息、默认模式或研究仓库。恢复方式为停止新运行器，
既有 launch 和 placeholder 入口保持原样；历史 run 不清理。

## 预期与实际

- 每个模式在独立 1 秒、20 Hz run 中接收 20 个有效 Bundle、20 个有对应身份、
  时间、状态、来源和原因的不可用占据，均无体素，observed domain 为
  `unavailable_no_observation`；20 个 `observation_not_fused` 地图事件，
  地图快照 0 个，查询 `unavailable/map_unavailable`、revision 0、概率不可用。
- 运行时图含 source/sensor/perception/mapping/observer，训练与 LiDAR 节点和话题
  为空；两次 run 的进程和端口清理通过。
- `disabled` 输出 `source_type=derived`、`reason=perception_disabled`；
  当前 `research` 前置阻塞，输出 `source_type=model`、明确
  `research_preflight_blocked:...`，无 placeholder fixture 回退。
- 定向纯函数测试还覆盖错误 fallback、free 体素/训练字段泄漏、缺失拒绝事件，
  及已有地图收到不可用观测后 revision、cell 和最新有效时间均不刷新。

执行命令（Conda Python，经 SIM-01 ROS 环境）：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/perception_mode_run.py --mode disabled --port 11487
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/perception_mode_run.py --mode research --port 11488
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/perf01a_run.py --duration-s 2 --scenario small --port 11489
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test*.py' -q
```

通过收据：

- [disabled ROS run](../.runtime/runs/perception-mode-disabled-20261027T091553498045/validation.json)
  及 [清理](../.runtime/runs/perception-mode-disabled-20261027T091553498045/cleanup-audit.json)。
- [research 阻塞 ROS run](../.runtime/runs/perception-mode-research-20261027T091615616057/validation.json)
  及 [清理](../.runtime/runs/perception-mode-research-20261027T091615616057/cleanup-audit.json)。
- [原 placeholder run](../.runtime/runs/perf01a-20261027T091641465568/perf-report.json)
  收到 40 组完整闭合；4 项新定向与全仓 408 项轻量测试通过，
  `git diff --check` 通过。

首轮新 observer 未订阅既有 sensor 节点要求的 IR 原始话题，节点就绪超时；
[失败目录](../.runtime/runs/perception-mode-disabled-20261027T091450238685/manifest.json)
保留，补齐订阅并让 observer 中断显式报告失败后独立重跑通过。
沙箱内 socket 预检受限，本次 ROS run 按权限审批在沙箱外执行。

## 边界

本轮只验证空地图上的真实 ROS 失效传递；已有地图不刷新由纯业务测试保证，
尚未作同 run ROS 模式热切换或地图旧证据老化的组合场景。研究后端仍不可调用；
没有 checkpoint 加载、模型 forward、真实 Radar/IR、外参、设备时钟、目标机资源、
正式 PERF-01 或完整 Phase 2/3 验收。`experiments/` 和 `tests/` 受既有忽略规则
影响，后续人工提交需显式核对这些文件，不自动改变忽略规则或提交。
