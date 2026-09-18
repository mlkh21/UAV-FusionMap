# EXP-20260916-003：SIM-SPEED-01两行修复与九次倍速矩阵

日期：2026-09-16；主责任：simulation_engineer；
状态：**已完成；用户已接受历史证据偏差，SIM-SPEED-01与SIM-01C正式关闭**。关联：
[实施方案](../docs/SIM_SPEED_01_IMPLEMENTATION_PLAN.md)、
[实施前核查](2026-09-16-sim-speed01-preflight.md)、
[SIM-01C运行说明](../simulation/RUN_SIM01C.md)。

## 1. 目的、范围和验收边界

本实验在用户确认的SIM-SPEED-01范围内，修复项目内JSBSim bridge的两个已测根因，
以独立候选二进制执行预注册0.5/1/2倍九次矩阵，并复验SIM-01A/B/C既有契约。
Python及ROS Python进程使用Conda `Radar-Diffusion`，解释器为
`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。

本实验只验收未解锁静止Rascal、每次5源秒预热后的首个不少于20源秒共同窗口。九次
矩阵及既有F0—F7的技术验收项均通过；一份历史RED派生结果发生同语义重写，违反方案
“历史run未改写”的正式门禁。用户于2026-09-17明确接受该已披露偏差，要求保留完整
记录、不伪造原时间且不尝试恢复；据此SIM-SPEED-01与SIM-01C正式关闭。该处置不改变
偏差事实或技术结果，也不证明至少40分钟跨32位微秒边界的SIM-01D，不完成PERF-01，
不证明35—70 m/s地图更新、Radar—IR感知、传感器质量、LiDAR监督生成、HIL或实飞能力。

## 2. 实施前封存和版本

实施前封存目录为`.runtime/logs/sim-speed01-20260916T141935-before/`。其中保存两个
speed目标文件、两个既有SIM00B-INIT-01文件、项目侧配置/运行器/checker前副本、
`bridge-existing.diff`和恢复说明。封存时：

- 根仓位于`feature/engineering-initialization`且尚无首次提交；
- 项目内bridge commit为`68de2cc63ded9a0d6641d45e9eb3ed2b43454cba`；
- 外部`/home/zxj/PX4-Autopilot`为
  `1c8ab2a0d7db2d14a6f320ebd8766b5ffaea28fa`且工作树干净；
- 旧init01二进制为71,059,128字节，SHA-256为
  `e775a33234fd885ec406f7586a19c63745484f166633811a8ccbf47f0846d3f6`；
- 未发现相关运行进程，计划端口均空闲。

旧init01二进制、失败run和修复前RED均保留；没有使用`git reset/clean/checkout`、
宽泛`pkill`或覆盖旧候选。去掉`--bridge-binary`仍回到旧init01运行基线；源码如需
恢复，只能使用封存的两个目标文件或`speed-source.diff`的反向补丁。

## 3. RED、两行生产修复和候选构建

新增的`tests/sim_speed_factor.cpp`直接编译真实`ConfigurationParser`。修复前测试正常
编译但退出非零，记录为：返回类型不是浮点，0.5被读成0，1和2保持不变；日志位于
`.runtime/logs/sim-speed01-20260916T141935-before/red-test.log`。修复后同一测试确认返回
类型为浮点且0.5/1/2逐项保持，日志位于同目录`green-test.log`。

生产源码只改两行，完整差异保存在同目录`speed-source.diff`：

| 文件 | 修复前 | 修复后 | 作用 |
| --- | --- | --- | --- |
| `.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/include/configuration_parser.h:62` | `int getRealtimeFactor()` | `float getRealtimeFactor()` | 保留0.5，不再在getter处向零截断 |
| `.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/src/jsbsim_bridge.cpp:213` | `step_start_time - step_stop_time` | `step_stop_time - step_start_time` | elapsed恢复为正的单步处理耗时 |

没有修改`configuration_parser.cpp`、`_dt=0.004`、sleep公式、`steady_clock`、PX4、
MAVLink时间类型、公共消息或simulation/sensors业务状态机。候选在全新
`.runtime/build/jsbsim-bridge-speed01/`按已验证的SIM-00A参数完整构建，未重建PX4。
候选`jsbsim_bridge`为71,059,096字节，SHA-256为：

```text
d846038cddbd64859e1d48e414d994248c70c408ec3552d39cb472e2beb63ddf
```

## 4. 固定九次矩阵和测量方法

执行命令为：

```bash
bash ros_ws/sim01_env.sh python ros_ws/sim01c_run.py \
  --speed-matrix \
  --bridge-binary .runtime/build/jsbsim-bridge-speed01/jsbsim_bridge
```

实际suite为`.runtime/runs/sim01c-suite-20260916T143604636221`；矩阵ID为
`sim-speed01-matrix-20260916T143604603286`，其原始manifest位于suite内
`speed-matrix-manifest.json`。候选、工具、配置和boot ID在矩阵开始时冻结，并在每个
run中复核。固定规则是在首个valid source后预热5源秒，再自动选取首个不少于20源秒的
共同窗口；倍率为`Δclock / Δreceipt_monotonic`，不允许人工挑选端点。

| 全局序号 | 批次/批内序号 | run | 目标/允许范围 | 实测倍率 | 结果 |
| ---: | --- | --- | --- | ---: | --- |
| 1 | A/1 | `speed-05-m01` | 0.5 / [0.425, 0.575] | 0.49247648158810575 | GREEN |
| 2 | A/2 | `speed-1-m02` | 1.0 / [0.85, 1.15] | 0.9717383694510837 | GREEN |
| 3 | A/3 | `speed-2-m03` | 2.0 / [1.7, 2.3] | 1.9040578118469238 | GREEN |
| 4 | B/1 | `speed-2-m04` | 2.0 / [1.7, 2.3] | 1.9090099868353632 | GREEN |
| 5 | B/2 | `speed-1-m05` | 1.0 / [0.85, 1.15] | 0.9724669448458889 | GREEN |
| 6 | B/3 | `speed-05-m06` | 0.5 / [0.425, 0.575] | 0.4926471243170552 | GREEN |
| 7 | C/1 | `speed-1-m07` | 1.0 / [0.85, 1.15] | 0.9725265117190325 | GREEN |
| 8 | C/2 | `speed-05-m08` | 0.5 / [0.425, 0.575] | 0.49251706081883884 | GREEN |
| 9 | C/3 | `speed-2-m09` | 2.0 / [1.7, 2.3] | 1.8997974897479353 | GREEN |

计划与实际顺序逐项一致；九个run均为`phase=COMPLETE`、`exit=0`、`errors=[]`，各自
`scenario-result.json: passed=true`且`factor_passed=true`。矩阵离线checker也为
`passed=true`，计划9次、实际9次。

## 5. 安全、身份和清理结果

九个run的源时间窗口均超过20秒，`window_identity_complete=true`、clock严格递增，
原始ODOMETRY时间戳有共同证据且未检测到timestamp重写。每个run均满足：

- `terminal_count=0`，无验收外ERROR；
- `static_unarmed=true`，没有发送解锁、起飞或控制命令；
- candidate SHA、大小和mtime与矩阵冻结值一致；
- `cleanup-audit.json: passed=true`、`forced=[]`、无审计Python PID残留；
- 对应ROS Master端口11359/11360/11361及4560、14540、14580等端口已释放。

bridge退出码`-2`是监督器对本次受管进程的正常SIGINT收尾，不是强制升级。矩阵完成后
未发现本次进程/端口残留；外部PX4仍干净，旧init01二进制SHA保持不变。

## 6. 回归验证

本轮实际验证如下：

| 检查 | 命令或产物 | 结果 |
| --- | --- | --- |
| getter C++ RED/GREEN | `.runtime/build/jsbsim-speed01-test/sim_speed_factor`及封存日志 | 修前RED、修后GREEN |
| 既有初始化C++ | `.runtime/logs/sim00b-init01/initialization_test` | GREEN |
| SIM-01C定向契约 | `python -m unittest discover -s tests -p 'test_sim01c_contract.py' -v` | 24/24通过 |
| 全仓单元/契约 | `python -m unittest discover -s tests -p 'test_*.py' -v` | 97/97通过 |
| 独立catkin | 按[RUN_SIM01A](../simulation/RUN_SIM01A.md)参数增量构建到`.runtime/ros` | 100%完成 |
| 实际ROS fixture | `bash ros_ws/sim01_env.sh python ros_ws/sim01_smoke.py --fixture` | `.runtime/runs/sim01a-fixture-20260916T144539446051`，exit=0、result passed=true |
| SIM-01B只读重验 | 直接调用纯函数校验LIVE/B1/B2归档 | 三者passed=true；6003源/适配、15794 clock、300.008001秒 |

SIM-01B重验对象分别为
`.runtime/runs/sim01b-live-20260915T072715914616`、
`.runtime/runs/sim01b-b1-20260915T074556979050`和
`.runtime/runs/sim01b-b2-20260915T075203206120`。没有运行会改写归档`result.json`的
CLI，也没有重放或覆盖历史bag。

## 7. 历史RED保留、证据偏差和最终结论

修复前三次2倍完整窗口分别为1.698206519、1.694531726、
1.689637552，均低于1.7；0.5倍一次71.454319482后发生`estimator_reset`，另一次在
窗口完成前失败。它们继续作为旧init01行为和本次RED→GREEN因果链的一部分，不能改写
为通过，也不能与新候选九次结果混成同一批统计。

证据保护有一项已记录偏差：checker兼容性复核时曾误对历史目录
`.runtime/runs/sim01c-suite-20260916T085553794733/speed-2`调用会写结果的CLI，
使`scenario-result.json`以相同的RED结论重写并改变mtime。当前内容仍为
`passed=false`、`actual_factor=1.6896375522589038`和同一倍率超界原因；
`manifest.json`、`speed-result.json`及原始观测未改。因此技术RED语义和九次新矩阵
不受影响，但不将该历史文件声明为字节/mtime未改；后续复核已改用纯函数和新run。

用户于2026-09-17明确接受上述偏差，并要求保留完整记录、不伪造该文件的原时间、
不尝试恢复。现有历史文件及其当前mtime原样保留；本记录不推测、补写或声称恢复其
重写前mtime。该处置是对已披露证据偏差的正式接受，不把偏差追溯改写为“从未发生”。

最终结论分两层：两行修复及预注册九次矩阵技术结果通过，既有F0—F7故障链技术结果
也保持通过；历史RED的一份派生`scenario-result.json`被同语义重写且mtime变化，仍是
完整记录中的已知偏差，并未满足方案原定的历史run未改写要求。用户接受该偏差后，
SIM-SPEED-01与SIM-01C于2026-09-17正式关闭。SIM-01D至少40分钟跨边界持续性、PERF-01
及高速地图测试仍未完成；本实验没有运行地图、感知网络或训练监督LiDAR，不能据此
声明35—70 m/s地图更新、感知质量、LiDAR能力、机载实时部署或飞行验收通过。
