# SIM-01C：时钟、异常和短窗倍速运行手册

更新日期：2026-09-17；主责任：integration_engineer；当前状态：**已完成；F0—F7
故障链与0.5/1/2倍短窗矩阵通过，历史证据偏差经用户接受后正式关闭**。

本文是[SIM-01C实测方案](../docs/SIM01C_FAULT_CLOCK_PLAN.md)的运行和结果记录。
场景定义以[`configs/sim01c_scenarios.yaml`](../configs/sim01c_scenarios.yaml)为准，
入口是[`ros_ws/sim01c_run.py`](../ros_ws/sim01c_run.py)。本文记录的是功能级fixture
和未解锁静止仿真的证据，不是PX4实飞、高速固定翼飞行或PERF-01性能验收。倍速修复
详情见[SIM-SPEED-01实验记录](../experiments/2026-09-16-sim-speed01-implementation.md)。

## 1. 当前结论

- F0—F7已经分别取得`phase=COMPLETE`、`exit=0`和离线
  `scenario-result.json: passed=true`的证据。它们跨两个最终suite组成，不得把其中任一
  suite误写成“单次F0—F7全通过”。
- SIM-SPEED-01只修复bridge两行：getter由`int`改为`float`，elapsed由
  `step_start_time - step_stop_time`改为`step_stop_time - step_start_time`。独立候选
  SHA-256为`d846038cddbd64859e1d48e414d994248c70c408ec3552d39cb472e2beb63ddf`。
- 预注册矩阵`sim-speed01-matrix-20260916T143604603286`按固定九次顺序完整执行；九个
  run均`COMPLETE/exit=0`、倍率在±15%范围、terminal为0、未解锁且清理通过。
- 修复前三次2倍RED和两次0.5失败仍保留为历史证据，与新候选矩阵不是同一批
  统计。但checker开发期间误重写其中一份派生`scenario-result.json`，结论/数值不变而
  mtime变化；详见EXP-20260916-003的证据偏差记录。
- 用户于2026-09-17明确接受上述已披露偏差，要求保留完整记录、不伪造原时间且不尝试
  恢复；因此SIM-SPEED-01与SIM-01C正式关闭。偏差事实和技术结果均不变。SIM-01D至少
  40分钟跨边界测试、PERF-01和高速地图测试仍未完成，本结果不证明35—70 m/s地图更新、
  感知或LiDAR能力。

## 2. 环境和安全边界

所有Python工具、测试、ROS Python节点均通过项目入口使用Conda `Radar-Diffusion`：

```bash
bash ros_ws/sim01_env.sh python -c 'import sys; print(sys.executable)'
```

预期输出为：

```text
/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python
```

运行前还必须满足：

1. 从仓库根目录`/home/zxj/catkin_ws/src/UAV-FusionMap`执行；
2. F0—F7使用私有ROS Master端口`11351`—`11358`，0.5/2倍速使用`11359`、
   `11360`，1倍控制组使用`11361`，端口必须空闲；
3. 倍速场景发现既有PX4进程时会拒绝启动，不能清理或接管用户已有会话；
4. 不发送解锁、起飞或控制命令，倍速场景必须保持未解锁静止；
5. 每次执行创建新的`.runtime/runs/sim01c-suite-*`，不得覆盖或改写失败证据。

## 3. 运行命令

先运行SIM-01C契约测试：

```bash
bash ros_ws/sim01_env.sh python -m unittest discover \
  -s tests -p 'test_sim01c_contract.py' -v
```

按一个连续suite运行F0—F7。F0使用生产`60.0 s`启动超时，命令不是即时完成：

```bash
bash ros_ws/sim01_env.sh python ros_ws/sim01c_run.py \
  --scenario F0 --scenario F1 --scenario F2 --scenario F3 \
  --scenario F4 --scenario F5 --scenario F6 --scenario F7
```

同一命令中F7自动引用本次F3的run。单独重跑F7时必须显式指定一个已通过的F3目录：

```bash
bash ros_ws/sim01_env.sh python ros_ws/sim01c_run.py \
  --scenario F7 --previous-run .runtime/runs/<suite>/f3
```

使用默认旧init01二进制单独运行倍速场景，仅用于诊断或复现历史基线：

```bash
bash ros_ws/sim01_env.sh python ros_ws/sim01c_run.py --scenario SPEED_2
bash ros_ws/sim01_env.sh python ros_ws/sim01c_run.py --scenario SPEED_05
bash ros_ws/sim01_env.sh python ros_ws/sim01c_run.py --scenario SPEED_1
```

SIM-SPEED-01验收必须显式选择候选并一次执行固定九run，不得以单run拼接矩阵：

```bash
bash ros_ws/sim01_env.sh python ros_ws/sim01c_run.py \
  --speed-matrix \
  --bridge-binary .runtime/build/jsbsim-bridge-speed01/jsbsim_bridge
```

`--scenario all`仍按普通场景顺序运行，不替代`--speed-matrix`的候选身份、固定顺序、
同一boot周期和整批离线checker门禁。任何命令的进程退出码也不能替代各run及矩阵证据。

## 4. F0—F7语义和通过条件

F1—F5和F7由pymavlink编码真实MAVLink2 `HIGHRES_IMU`/`ODOMETRY`，转换成
`mavros_msgs/Mavlink`后进入`/mavlink/from`，再通过生产解码、source、sensors和监督器
链。F0是不发送输入的source启动超时；F6是直接验证`StateClockGate`的sensors-only
场景。不得把F0或F6描述成完整MAVLink链实测，也不得把fixture描述成PX4实飞。

| 场景 | 注入与必需语义 | 主要判定 |
| --- | --- | --- |
| F0 | source启动后不发两路输入 | 生产60秒阈值触发唯一`terminal:startup_timeout`，sensors传播并锁定 |
| F1 | ACTIVE后停IMU、继续ODOMETRY | 最后有效IMU发布后`[2.0,2.5] s`内唯一`terminal:imu_timeout`；允许因果链内`pending_timeout` |
| F2 | ACTIVE后停ODOMETRY、继续IMU | 最后有效ODOMETRY发布后`[2.0,2.5] s`内唯一`terminal:odometry_timeout` |
| F3 | ACTIVE后两路暂停，terminal后恢复发送 | clock暂停；唯一源/适配terminal；恢复发送不再产生valid |
| F4 | 注入更小的IMU `time_usec` | `0.5 s`内唯一`terminal:imu_regression_or_reordering`，terminal时间等于故障前最后clock |
| F5 | 改变ODOMETRY `reset_counter` | reset样本不得成为valid；`0.5 s`内唯一`terminal:estimator_reset` |
| F6 | sensors-only先推进状态，再发送回退`/clock` | `clock_regression` ERROR，gate锁定、pending清零；source/sensors terminal都必须为0 |
| F7 | F3后用新run_id启动正常fixture | run_id和clock_id均不同，新run有valid、无terminal，旧run身份不复活 |

每个故障场景只有同时满足以下条件才算通过：

- `manifest.json`为`phase=COMPLETE`、`exit=0`且`errors=[]`；
- `scenario-result.json`为`passed=true`；
- terminal或本地ERROR的原因、数量、身份、时间窗与冻结配置一致；
- terminal/ERROR之后valid不再增长，gate最终锁定并清空pending；F7则必须保持未锁定；
- 预期外WARN/ERROR为0，Conda后代审计通过；
- `cleanup-audit.json`为通过、无强制kill、无审计PID残留且端口均释放。

诊断话题会周期发布累计计数，不能把诊断行数直接当作故障事件数。监督器和离线checker
使用明确的原因、审计计数、身份及单调receipt时间共同判定。

## 5. F0—F7实际证据

最终证据由下列suite组合：

| 场景 | 最终证据目录 | 结果 |
| --- | --- | --- |
| F0 | `.runtime/runs/sim01c-suite-20260916T085205867969/f0` | COMPLETE |
| F1 | `.runtime/runs/sim01c-suite-20260916T085502587649/f1` | COMPLETE |
| F2 | `.runtime/runs/sim01c-suite-20260916T085502587649/f2` | COMPLETE |
| F3 | `.runtime/runs/sim01c-suite-20260916T085502587649/f3` | COMPLETE |
| F4 | `.runtime/runs/sim01c-suite-20260916T085205867969/f4` | COMPLETE |
| F5 | `.runtime/runs/sim01c-suite-20260916T085205867969/f5` | COMPLETE |
| F6 | `.runtime/runs/sim01c-suite-20260916T085205867969/f6` | COMPLETE |
| F7 | `.runtime/runs/sim01c-suite-20260916T085502587649/f7` | COMPLETE |

F6的counter补强还由
`.runtime/runs/sim01c-suite-20260916T085038422389/f6`独立取得COMPLETE证据。

完整保留的失败证据也属于结果的一部分：
`.runtime/runs/sim01c-suite-20260916T085205867969`中F1、F2、F3和F7因旧driver退出/
封存等待竞态而FAILED；同一suite中的F0、F4、F5、F6通过。修复测试工具竞态后，
`.runtime/runs/sim01c-suite-20260916T085502587649`重跑F1、F2、F3、F7全部通过。
前一suite不能被改写或宣称为全绿，后一suite也只覆盖列出的四个场景。

每个功能场景目录至少应核对：

- `manifest.json`、`scenario-result.json`和`supervisor-trigger.json`；
- `source-audit.jsonl`、`sensor-audit.jsonl`和`scenario-observations.jsonl`；
- `driver-events.jsonl`、`driver-result.json`（F6为sensors-only，不依赖driver）；
- `cleanup-audit.json`、`checker.log`和`offline-checker.log`。

## 6. 倍速实测结果

倍率按共同窗口计算：

```text
actual_factor = (C1_clock_ns - C0_clock_ns) /
                (C1_receipt_monotonic_ns - C0_receipt_monotonic_ns)
```

共同窗口要求不少于20源秒，修复后矩阵还固定在首个valid source后预热5源秒，再由
冻结规则自动选端点。目标容差为±15%。这只是仿真节奏冒烟门槛，不是35—70 m/s高速
飞行性能结论。

### 6.1 RED语义与原始观测保留；派生结果同义重写已披露

旧init01二进制的三次2倍完整窗口均低于1.7下界：

| 证据目录 | actual_factor | 门槛 | 历史结果 |
| --- | ---: | ---: | --- |
| `.runtime/runs/sim01c-suite-20260916T085038422389/speed-2` | 1.698206519 | 1.7—2.3 | RED |
| `.runtime/runs/sim01c-suite-20260916T085205867969/speed-2` | 1.694531726 | 1.7—2.3 | RED |
| `.runtime/runs/sim01c-suite-20260916T085553794733/speed-2` | 1.689637552 | 1.7—2.3 | RED |

`.runtime/runs/sim01c-suite-20260915T184438701028/speed-05`曾计算
`actual_factor=71.454319482`，但随后出现`estimator_reset`和terminal；
`.runtime/runs/sim01c-suite-20260916T085038422389/speed-05`则在共同窗口完成前发生同类
故障。两者均为FAILED而非干净倍率样本。历史`manifest.json`、`speed-result.json`和
原始观测保持原有RED/FAILED语义，不能因新候选通过而改写为GREEN；但第三个2倍RED
目录的派生`scenario-result.json`曾被checker CLI以相同RED结论重写并改变mtime，正式
门禁偏差已在EXP-20260916-003披露。

用户于2026-09-17已接受该偏差。历史文件及当前mtime保持现状，不伪造重写前的原时间，
也不尝试恢复；完整记录继续保留，不能把该事件追溯表述为“从未发生”。

### 6.2 两行bridge修复和候选身份

SIM-SPEED-01只修改项目内bridge副本两行：

1. `configuration_parser.h`中的`getRealtimeFactor()`返回类型由`int`改为`float`；
2. `jsbsim_bridge.cpp`中的elapsed由`step_start_time - step_stop_time`改为
   `step_stop_time - step_start_time`。

独立候选位于`.runtime/build/jsbsim-bridge-speed01/jsbsim_bridge`，大小71,059,096字节，
SHA-256为`d846038cddbd64859e1d48e414d994248c70c408ec3552d39cb472e2beb63ddf`。
修复前/后的C++ getter测试分别RED/GREEN；没有修改PX4、MAVLink时间字段、公共消息、
业务状态机、±15%容差或修复前run。

### 6.3 修复后固定九run：全部GREEN

最终suite为`.runtime/runs/sim01c-suite-20260916T143604636221`，其中
`speed-matrix-manifest.json`冻结矩阵ID
`sim-speed01-matrix-20260916T143604603286`。计划和实际顺序完全一致：

| 序号 | 批次 | run | 目标/允许范围 | actual_factor | 结果 |
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

九个run均`phase=COMPLETE`、`exit=0`、`errors=[]`，单run离线
`scenario-result.json: passed=true`且矩阵离线checker为`passed=true`。每次clock严格
递增，源/适配窗口身份完整，原始ODOMETRY timestamp未重写，`terminal_count=0`、
`static_unarmed=true`；`cleanup-audit.json`均通过、无强制kill、无审计PID残留，端口
均释放。倍速目录应核对`speed-result.json`、`speed-measurement.json`、
`speed-observations.jsonl`、`manifest.json`、`scenario-result.json`和
`cleanup-audit.json`，不能只看单个倍率字段。

## 7. 清理、异常中断和恢复

监督器只记录并停止当前suite创建的子进程，不使用`pkill`，不接管其他ROS/PX4会话。
每个run结束后检查受管子进程、Python后代和场景端口，并将结果写入
`cleanup-audit.json`；运行产物全部保留。

若命令被终端中断：

1. 保留该suite，不手工把`RUNNING`、`CLEANING`或`FAILED`改成COMPLETE；
2. 根据该run的`manifest.json`、`cleanup-audit.json`和进程日志核对本次PID及端口；
3. 不使用宽泛`pkill`、`git clean/reset`或删除历史run；
4. 确认无本次残留且端口释放后，以新suite重跑目标场景。

## 8. 回归、正式关闭边界和下一步

SIM-SPEED-01收口回归包括：`test_sim01c_contract.py` 24/24、全仓`test_*.py` 97/97、
getter C++ GREEN、既有SIM00B初始化C++ GREEN、独立catkin增量构建100%、11项实际ROS
fixture，以及SIM-01B LIVE/B1/B2归档纯函数只读重验。fixture产物为
`.runtime/runs/sim01a-fixture-20260916T144539446051`，exit=0且result passed=true。
SIM-01B三份归档仍为6003源/适配、15794 clock、300.008001秒；没有运行会改写归档
`result.json`的CLI。

当前可以得出“F0—F7故障链路技术结果通过、修复后0.5/1/2倍预注册短窗矩阵技术结果
通过”。一份历史RED派生结果发生同语义重写，违反方案的历史run未改写要求；用户于
2026-09-17在保留完整记录、不伪造原时间且不尝试恢复的前提下明确接受该偏差，故
SIM-SPEED-01与SIM-01C正式关闭。该接受不改变偏差事实、历史RED语义或技术结果。
此外，以下结论仍未成立：

- SIM-01D至少40分钟跨约35.8分钟32位微秒边界的持续运行通过；
- PERF-01的35—70 m/s状态、感知、地图更新及时空预算通过；
- 高速地图测试通过；
- Radar—IR感知质量、传感器真实性、训练监督LiDAR或在线LiDAR能力通过；
- 完整Phase 1、机载实时部署、PX4实飞或HIL验收通过。

下一步保持SIM-01D和PERF-01为独立门禁，高速地图测试也保持独立未完成项。若后续需要
把`system_clock`改为`steady_clock`、抽取纯节奏helper或修复32位时间路径，应重新提交
范围和验证方案，不能用本次短窗GREEN隐含授权或关闭这些风险。
