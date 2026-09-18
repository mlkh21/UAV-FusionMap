# SIM-01C：时钟与异常实测方案

方案日期：2026-09-15；状态：具体方案已完成，运行代码与实际场景待确认；
主责任：integration_engineer。依据：[项目状态](../PROJECT_STATUS.md)、
[总验证方案](SIMULATION_VALIDATION_PLAN.md)、[SIM-01B基线](../simulation/RUN_SIM01B.md)。

## 1. 目标和边界

验证已经实现的状态/时钟链在启动等待、暂停恢复、单路断流、采样时间回退、估计器
reset、接收端时钟回退和0.5/2倍速下是否按契约停止或继续。每个场景使用新run_id、
新目录和独立ROS Master；预期故障被正确识别才算场景通过，不能用进程退出码1直接
代表通过。

本步不新增消息字段，不修改坐标/质量语义，不加载研究算法、GPU、地图或控制器，
不发送解锁/起飞命令。40分钟跨边界持续运行仍属SIM-01D；高速性能门槛属PERF-01。
本方案不修改PX4、bridge、simulation/sensors业务库或现有B运行产物。

## 2. 真实调用链与当前行为

```text
fixture / PX4 MAVLink
  → /mavlink/from
  → state_clock_node.decode_source_packet
  → SourceTimeline(PREPARING → ACTIVE → FAULT)
  → /clock + /uav/sim/state + /uav/diagnostics
  → state_adapter_node.adapt_state
  → StateClockGate
  → /uav/sensors/state + /uav/diagnostics
  → scenario observer / supervisor
```

- `SourceTimeline.poll_timeout`按单调墙钟分别检查IMU和ODOMETRY，阈值2秒；ACTIVE reset
  或IMU采样时间回退立即进入FAULT。FAULT清空pending，只产生一个独立terminal状态。
- `StateClockGate`收到terminal后清空pending并锁定run；本地/clock回退也会清空并锁定，
  但只发ERROR诊断，不自行构造上游terminal。
- 普通/clock暂停不会推进时间。若状态继续领先时钟，0.5墙秒后pending过期；若所有
  输入停止，sensors本身没有输入断流看门狗，必须由源terminal或系统监督器停止本run。
- 现有单元测试覆盖状态机函数，实际ROS fixture覆盖终止传播，但尚未实际证明故障事件
  触发监督器停止整个会话并只清理本次进程。

## 3. 场景矩阵

功能级异常使用真实`mavros_msgs/Mavlink`消息：由pymavlink编码HIGHRES_IMU/ODOMETRY，
再用`mavros.mavlink.convert_to_rosmsg`发布到本场景私有输入话题。它经过生产解码、两层
ROS节点和序列化链；标为fixture，不冒充PX4/JSBSim运行。

| 编号 | 注入方式 | 必需结果 | 时间/数据证据 |
| --- | --- | --- | --- |
| C-F0 | source已启动但不发送两路输入 | `terminal:startup_timeout`，sensors锁定，监督器按预期故障收尾 | 使用生产60秒配置；terminal在60.0秒阈值后、60.5秒观测上限内 |
| C-F1 | ACTIVE后停止IMU，ODOMETRY继续 | 允许先出现pending_timeout，最终唯一`terminal:imu_timeout` | 从最后有效IMU receipt到terminal为[2.0,2.5]墙秒；/clock不伪造前进 |
| C-F2 | ACTIVE后停止ODOMETRY，IMU继续 | 唯一`terminal:odometry_timeout`，clock可继续到故障时刻 | 从最后有效ODOMETRY receipt到terminal为[2.0,2.5]墙秒 |
| C-F3 | ACTIVE后两路暂停，terminal后恢复发送 | 唯一源terminal；恢复消息不产生valid输出，sensors保持锁定 | 暂停期间clock内容不变；恢复后valid计数不增 |
| C-F4 | ACTIVE后发送更小的IMU time_usec | `terminal:imu_regression_or_reordering`立即传播 | 注入到terminal receipt不超过0.5墙秒；terminal时间等于故障前最后clock |
| C-F5 | ACTIVE后改变ODOMETRY reset_counter | `terminal:estimator_reset`立即传播 | 不得发布该reset状态为valid；不超过0.5墙秒 |
| C-F6 | sensors-only链向前推进后发送更小/clock | gate锁定、pending清空、ERROR诊断；监督器停止本run | 回退clock不得发布适配状态；ERROR后不超过0.5墙秒开始清理 |
| C-F7 | C-F3后以新run_id启动正常fixture | 新run重新PREPARING/ACTIVE，旧身份/terminal不复活 | 两个manifest的run_id/clock_id不同，新run有valid且无旧sample_id |

时间下界来自代码中的`>= source_timeout_wall_s`；2.5秒是ROS调度和20ms轮询的观测
截止，不把业务阈值改为2.5秒。即时故障的0.5秒是场景观测截止，不替代0.5秒pending
规则。每个场景冻结注入前后的源clock、状态、诊断、terminal和单调receipt时间。

## 4. 预期故障的判定

场景监督器先声明唯一预期reason及允许的前置诊断，再启动节点。只有下列条件同时满足
才将预期故障场景标为通过：

1. source恰好发布一个符合run/clock/schema的terminal，sensors恰好传播一个派生terminal；
2. 原因、终止身份和故障前最后clock一致，terminal几何槽不作为观测；
3. terminal后source和sensors均不再发布valid；pending清空、sensors locked=true；
4. ERROR/terminal确实被监督器观察后触发本次会话停止，而非等墙钟安全截止；
5. 发布审计、接收记录和实际重读计数一致，预期外WARN/ERROR为0；
6. 所有Python后代使用Conda `Radar-Diffusion`，无强制kill、无审计PID残留，端口释放。

F1中clock停滞导致的`pending_timeout`是因果链内允许事件，但仍须精确计数；其他场景
不得用宽泛白名单忽略诊断。输入损坏、未知消息或非目标sysid/compid不在本轮故障矩阵，
它们当前是拒绝/忽略语义，不能临时升级为terminal。

## 5. 0.5和2倍速实测

倍速测试使用实际PX4/JSBSim/MAVROS、未解锁静止场景和新run，不用rosbag rate替代。
每项在ACTIVE后取不少于20源秒的共同窗口，记录：

```text
actual_factor = (last_clock_ns - first_clock_ns) / monotonic_wall_elapsed_ns
```

同时要求源/适配身份完整、clock严格递增、原采样timestamp不被缩放重写、无terminal，
并记录clock/state频率、最大源间隔、CPU环境和完整清理。首次工程容差拟为目标因子的
±15%；这是仿真节奏冒烟范围，不是PERF-01实时性能承诺。

现状存在确定的RED前置：bridge配置将环境值解析到`float _realtime_factor`，但
`getRealtimeFactor()`返回`int`，0.5会截断为0；单步耗时又计算为start-stop。实施时先用
当前二进制各运行一个短测并保存实际factor，预计0.5不能通过。不得为得到GREEN修改
期望值、环境变量或统计公式。

当前C授权提案不包含bridge源码修复。若RED复现，停止倍速子任务，基于实际结果另交
`SIM-SPEED-01`最小修复方案：候选仅涉及项目内bridge的
`include/configuration_parser.h`返回类型和`src/jsbsim_bridge.cpp`耗时方向、对应C++反例、
独立重建及0.5/1/2实测。R-10的32位微秒边界仍另行处理，短倍速测试不能关闭R-10。

## 6. 实施文件与所有权

| 主责任 | 计划文件 | 用途 |
| --- | --- | --- |
| integration_engineer | 新`ros_ws/sim01c_run.py` | 新目录/Master、场景状态机、预期故障判定、只清理本次PID |
| tester | 新`tests/sim01c_mavlink_fault_driver.py` | 真实MAVLink fixture、注入时刻和发送台账 |
| tester | 新`tests/check_sim01c_scenario.py`、`tests/test_sim01c_contract.py` | terminal/诊断/时间/锁定/清理及错误反例 |
| system_architect | 新`configs/sim01c_scenarios.yaml` | 固定场景、独立端口、安全截止和验收容差 |
| simulation_engineer | 新`simulation/RUN_SIM01C.md` | 实际命令、场景结果及未验收边界 |
| experiment_manager | 新实际实验记录及公共状态/决策/索引更新 | 失败和成功运行均保留 |

复用现有`sim01b_source.launch`、`sim01b_sensors.launch`和已验证的进程/审计基础设施；
不复制业务状态机。若必须改现有node、公共消息、B工具或纯业务库，视为范围扩大，先
补生产者/消费者影响再确认。本方案阶段只新增本文和管理记录。

## 7. 实施顺序和恢复

1. 保存实施前源码及外部仓库状态；对监督器/driver做预期失败的契约反例。
2. 完成F0—F7的短fixture场景；每个场景新Master，失败证据不覆盖。
3. 用当前bridge分别做0.5/2现状短测；得到GREEN才验收，得到RED则按第5节停止并提案。
4. 复跑现有73项单元/契约、11项ROS fixture及SIM-01B离线归档检查，防止破坏基线。
5. 核对Conda解释器、进程/端口、文档链接及受保护源码；更新状态和实验记录。

恢复方式是停止本次记录PID/进程组并保留新run目录；新文件可按精确清单回退。禁止
`pkill`、`git clean/reset`、覆盖历史bag或修改用户终端ROS菜单。原研究仓库、数据、
checkpoint、原Conda和外部PX4保持不动。

## 8. 完成条件与待确认范围

F0—F7须全部通过，且0.5/2倍速均达到实际factor门槛后，SIM-01C才可标完成。若倍速
被当前bridge缺陷阻塞，则只标“故障链路通过、倍速阻塞”，不能关闭C或Phase 1。

待确认的第一批实施范围为第6节六类项目文件、F0—F7实际ROS fixture及两个现状倍速
短测。它不授权修改bridge、PX4、消息、业务状态机、研究仓库或执行SIM-01D长测。

