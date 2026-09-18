# EXP-20260915-002：SIM-01C真实调用链与倍速前置核查

日期：2026-09-15；状态：只读分析和具体方案完成，实施待确认；主责任：Technical Lead。
依据：[SIM-01C方案](../docs/SIM01C_FAULT_CLOCK_PLAN.md)。

## 1. 检查范围

读取根规范、项目状态、系统架构、simulation/sensors/ros_ws/tests/experiments/docs规则，
沿`/mavlink/from`到SourceTimeline、两层ROS节点、StateClockGate、观察器和监督清理路径
逐段检查。未修改运行代码，未启动ROS/PX4/JSBSim，未安装依赖或运行训练。

默认Python入口仍为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。当前分支
`feature/engineering-initialization`尚无首次提交；用户`.vscode`及历史运行保留。

## 2. 已有能力和缺口

| 项目 | 代码证据 | 结论 |
| --- | --- | --- |
| 独立源断流 | `source_timeline.py:66-82`按IMU/ODOMETRY最后有效receipt分别检查 | 2秒阈值已实现，只有函数测试，整run停止未实测 |
| 回退/reset | `source_timeline.py:121-149` | IMU回退任意阶段FAULT；ACTIVE reset FAULT，准备期reset重开预热 |
| 终止传播 | `source_timeline.py:50-64`、`clock_gate.py:116-131` | 独立terminal已实现；sensors清pending并锁run |
| sensors时钟回退 | `clock_gate.py:153-169` | 清pending并锁定后抛错；node发ERROR，但没有本地terminal |
| 监督停止 | `check_sim01_live.py:31-95`、`sim01_smoke.py:140-195` | 观察器会因terminal/ERROR退出，监督器再清理；尚无故障实际证据 |
| ROS fixture | `check_sim01_ros_fixture.py:56-99` | 已测等待/过期/terminal锁定；输入是AircraftState，未经过MAVLink/source |

关键差异：clock停止且状态继续会先在0.5秒产生pending_timeout，之后source在2秒进入
IMU timeout；所有输入停止时sensors本身不计断流，依赖源terminal或系统监督。C方案
因此不能把所有异常统一成同一种断流，也不能复用B记录器的“任一WARN计数立即结束”
策略来等待预期的最终terminal。

## 3. 倍速阻断证据

项目内bridge的`configuration_parser.cpp:50-52`用`std::stod`写入float字段，但
`configuration_parser.h:62/74`的getter返回int；0.5变成0，而`jsbsim_bridge.cpp:214`
把非正factor解释为不节流。另有`jsbsim_bridge.cpp:211-216`把elapsed写成start-stop，
使正factor的sleep多加一次计算时间。

这不是运行测量，不能把静态证据写成实际0.5速度结果。方案要求先保存当前二进制的
现状短测；预期失败也须按实际factor、时钟和清理证据登记。bridge当前已有
SIM00B-INIT-01的2文件5声明修改，Git状态与本轮前一致；本轮不叠加源码修改。

## 4. 产物与保护

实施前98份相关文件保存于`.runtime/logs/sim01c-plan-20260915/before/`，附
`source-files-before.json`。外部原PX4、研究仓库及项目bridge当前Git状态写入
`external-before.json`。这是本机精确快照，不等同Git提交或第二介质备份。

本轮仅新增方案和本记录，并更新PROJECT_STATUS、DEVELOPMENT_PLAN、DECISION_LOG与
EXPERIMENT_LOG。检查本地链接、12份AGENTS七项、修改清单、快照和外部状态；实际
ROS场景、倍速、catkin或回归测试均未执行，不能将方案状态标为运行通过。

## 5. 风险和下一步

故障测试的主要风险是把预期ERROR误当测试基础设施失败、用宽泛白名单掩盖额外异常，
或在暂停后沿用旧run恢复。方案以场景级唯一reason、事件计数、terminal后零valid和
新run恢复限制这些风险。

下一步须确认第6节具体实施范围。确认后先实现故障fixture的RED/GREEN和F0—F7，
再做当前bridge的0.5/2短测。倍速RED只形成独立修复提案，不自动修改bridge或R-10范围。

