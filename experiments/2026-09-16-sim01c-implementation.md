# EXP-20260916-001：SIM-01C故障链与倍速现状实测

日期：2026-09-16；主责任：Technical Lead / integration_engineer；
状态：F0—F7故障链已通过，0.5/2倍速门禁阻塞，SIM-01C未完成。
依据：用户确认[SIM-01C方案](../docs/SIM01C_FAULT_CLOCK_PLAN.md)并要求调用对应子agent实施。

## 1. 范围、版本和边界

本轮在`feature/engineering-initialization`未提交工作树内新增场景配置、真实MAVLink故障
driver、在线/离线checker和会话监督器，并执行实际ROS故障fixture与PX4/JSBSim/MAVROS
倍速短测。默认解释器为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`；PX4
commit=`1c8ab2a0d7db2d14a6f320ebd8766b5ffaea28fa`，bridge
commit=`68de2cc63ded9a0d6641d45e9eb3ed2b43454cba`，沿用SIM00B-INIT-01。

实施文件为`configs/sim01c_scenarios.yaml`、`ros_ws/sim01c_run.py`、
`tests/sim01c_mavlink_fault_driver.py`、`tests/check_sim01c_scenario.py`、
`tests/test_sim01c_contract.py`及配套运行/状态文档。没有修改bridge、PX4、公共消息、
simulation/sensors业务状态机、研究仓库、模型、数据或checkpoint，也未发送解锁/起飞命令。

F1—F5和F7由pymavlink编码真实HIGHRES_IMU/ODOMETRY，再经
`mavros.mavlink.convert_to_rosmsg`发布至`/mavlink/from`，覆盖生产source与sensors链。
F0验证启动后零输入超时，因此不存在输入MAVLink包；F6按方案是sensors-only本地
`/clock`回退，预期没有源或适配terminal。不得把F0/F6写成全部消息经过完整MAVLink链。

## 2. 方法和验收门槛

- 每个F场景使用新run_id、独立ROS Master（11351—11358）、精确诊断白名单、发布/接收
  台账、在线触发及封存后离线重验；监督器只在观察到预期故障或新run有效输出后收尾。
- 启动超时保持生产配置60秒；双路独立断流保持2秒，外部可观测代理窗口为2.0—2.5秒；
  回退/reset即时故障观测上限0.5秒。terminal计数、身份、末时钟、锁定、pending清空和
  terminal后零valid同时验收，F3还实际注入terminal后的恢复消息。
- 倍速使用实际PX4/JSBSim/MAVROS未解锁静止链，ACTIVE后在不少于20源秒共同窗口内按
  `actual_factor = Δclock / Δmonotonic_wall`计算；0.5允许[0.425, 0.575]，2倍允许
  [1.7, 2.3]。同时要求身份一一对应、clock严格递增、原时间戳不重写、零terminal。
- 所有会话保留manifest、观察记录、driver/audit、结果及`cleanup-audit.json`；预期故障
  被正确识别才算F场景通过，进程退出码1或倍速RED本身不算通过。

## 3. F0—F7实际结果

最终证据由两次修正后会话组成，不能用同一suite中已失败的旧manifest替代：

| 场景 | 最终运行目录 | 结果和边界 |
| --- | --- | --- |
| F0 | `.runtime/runs/sim01c-suite-20260916T085205867969/f0` | 通过；启动零输入后唯一`startup_timeout`，源/适配terminal各1，123条观察；节点发现代理到故障观察为60.012678墙秒 |
| F1 | `.runtime/runs/sim01c-suite-20260916T085502587649/f1` | 通过；停IMU、ODOMETRY继续，唯一`imu_timeout`，源/适配terminal各1，56条观察 |
| F2 | `.runtime/runs/sim01c-suite-20260916T085502587649/f2` | 通过；停ODOMETRY、IMU继续，唯一`odometry_timeout`，源/适配terminal各1，66条观察 |
| F3 | `.runtime/runs/sim01c-suite-20260916T085502587649/f3` | 通过；双路暂停触发唯一`imu_timeout`；terminal后再发8组恢复输入仍零valid，26条观察 |
| F4 | `.runtime/runs/sim01c-suite-20260916T085205867969/f4` | 通过；IMU采样时间回退触发唯一`imu_regression_or_reordering`，源/适配terminal各1，21条观察 |
| F5 | `.runtime/runs/sim01c-suite-20260916T085205867969/f5` | 通过；ODOMETRY reset_counter变化触发唯一`estimator_reset`，reset样本不成为valid，源/适配terminal各1，21条观察 |
| F6 | `.runtime/runs/sim01c-suite-20260916T085205867969/f6` | 通过；本地`clock_regression`锁定gate并清pending，按契约源/适配terminal均为0，7条观察 |
| F7 | `.runtime/runs/sim01c-suite-20260916T085502587649/f7` | 通过；以F3为前序的新run产生valid，run_id/clock_id独立，旧terminal不复活，零terminal，41条观察 |

上述目录的`scenario-result.json.passed=true`、manifest `phase=COMPLETE/exit=0`、在线
supervisor触发及离线checker退出0同时成立。F0/F4/F5/F6来自第一组最终有效目录；该组
F1/F2/F3/F7虽场景数据验收为真，但因driver封存等待竞态使manifest失败，不能记为通过，
修正工具的等待/收尾顺序后在`20260916T085502587649`重新运行并通过。

实施中的失败证据均保留：首个F4因Conda解释器符号链接与解析后路径比较不一致而RED；
首轮F0的首个周期诊断代理窗口过紧，F6首个发布回调存在订阅握手竞态；后续分别增加
F0节点发现时间代理、F6在audit/诊断通道就绪后发送唯一样本并以封存counter证明
pending因果。修改只落在测试与监督工具，没有放宽
60秒、2秒、0.5秒生产阈值，也没有修改业务状态机。

## 4. 倍速实际RED

2倍速在同一硬件环境连续三次完成20源秒共同窗口，但均低于±15%下界1.7：

| 运行目录 | actual_factor | measurement_complete | terminal | 结论 |
| --- | ---: | --- | ---: | --- |
| `.runtime/runs/sim01c-suite-20260916T085038422389/speed-2` | 1.698206519 | true | 0 | RED |
| `.runtime/runs/sim01c-suite-20260916T085205867969/speed-2` | 1.694531726 | true | 0 | RED |
| `.runtime/runs/sim01c-suite-20260916T085553794733/speed-2` | 1.689637552 | true | 0 | RED |

三次均完成身份窗口、clock递增、未解锁和原时间戳不重写检查；结果接近但没有达到门槛，
不得四舍五入为通过，也不能据此作PERF-01高速实时性能结论。

0.5倍速复现前置核查所述`0.5 -> int 0`自由运行问题，未得到合格共同窗口：

- `.runtime/runs/sim01c-suite-20260915T184438701028/speed-05`曾完成窗口，实际factor为
  71.454319482，随后出现`estimator_reset` terminal，结果FAILED。
- `.runtime/runs/sim01c-suite-20260916T085038422389/speed-05`在共同窗口完成前即出现
  `estimator_reset`、上下游terminal及gate锁定，`measurement_complete=false`，结果FAILED。

因此当前结论是“故障链通过、倍速阻塞”，SIM-01C整体和Phase 1门禁均不能关闭。
bridge修复须另立`SIM-SPEED-01`评审，不能在本授权下更改返回类型、耗时方向或验收门槛。

## 5. 回归、清理和基线保护

本轮最终检查结果：

- `test_sim01c_contract.py`共17项通过；全仓`test_*.py`共90项通过。
- 增量catkin构建目标进度100%，输出仍限定于`.runtime/ros`，未写入系统ROS。
- 既有11项实际ROS fixture通过：
  `.runtime/runs/sim01a-fixture-20260916T085746927018`，manifest exit=0、result passed=true。
- 对既有SIM-01B归档只读重验通过：LIVE
  `.runtime/runs/sim01b-live-20260915T072715914616`、B1
  `.runtime/runs/sim01b-b1-20260915T074556979050`、B2
  `.runtime/runs/sim01b-b2-20260915T075203206120`；三份validation均`passed=true`，没有
  重放、改写或覆盖历史bag。
- F0—F7最终有效会话、三次2倍RED及上述两次0.5失败的`cleanup-audit.passed=true`；
  `forced=[]`、审计Python PID无残留，场景Master及倍速所用7个端口均释放。bridge
  `exit=-2`是监督器的正常SIGINT清理记录，不是强制升级；失败结果仍原样保留。

主要复验入口为：

```bash
bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_sim01c_contract.py' -v
bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_*.py' -v
bash ros_ws/sim01_env.sh python ros_ws/sim01_smoke.py --fixture
```

SIM-01B本轮直接调用`sim01b_validation.validate_live/validate_replay`做只读重验，未运行
会重写归档`result.json`的检查CLI；归档路径仍为上述LIVE/B1/B2三组证据。

## 6. 限制、风险和下一步

本实验只证明固定场景中的故障语义、监督停止、清理和当前静止仿真节奏；不证明地图
更新、35—70m/s飞行、复杂场景、传感器质量、机载资源或长时间稳定性。F0用零输入，F6
只测接收时钟门，不能替代真实飞行链。当前2倍因轻微低于门槛连续RED，0.5因bridge缺陷
严重失真；两者都属于必须解决的工程门禁，不应通过调整统计窗口或容差消除。

下一步先提交`SIM-SPEED-01`最小bridge修复方案并单独确认，修复后独立重建，执行
0.5/1/2三档重复实测；两项目标倍速均GREEN后才能关闭SIM-01C。40分钟边界仍属于
SIM-01D，35—70m/s状态/感知/地图端到端预算及丢帧、时延、空间误差验收仍属于PERF-01。
