# SIM-SPEED-01：JSBSim bridge 倍速最小修复与九次验收方案

版本：v0.1；日期：2026-09-16；状态更新：2026-09-17；主责任角色：simulation_engineer；
状态：**已实施并正式关闭；九次矩阵通过，证据保护偏差已由用户明确接受**。

依据：[项目状态](../PROJECT_STATUS.md)、[SIM-01C运行证据](../simulation/RUN_SIM01C.md)、
[本任务前置核查](../experiments/2026-09-16-sim-speed01-preflight.md)、
[实施记录](../experiments/2026-09-16-sim-speed01-implementation.md)。

## 1. 目标与当前问题

本任务只修复项目内JSBSim bridge副本的两个已证实倍速缺陷，并用独立候选二进制完成
预注册的0.5/1/2倍九次端到端矩阵：

1. `configuration_parser.h:62`把`float _realtime_factor`以`int`返回，导致`0.5`
   向零截断为`0`；
2. `jsbsim_bridge.cpp:213`用`step_start_time - step_stop_time`计算负耗时，随后
   `sleep = _dt / factor - elapsed`实际多加一次计算耗时。

当前证据不是推测：0.5倍已出现自由运行，带terminal的窗口测得`71.454319482`；2倍
三个干净窗口分别为`1.698206519`、`1.694531726`、`1.689637552`，均低于下界`1.7`。
修复前结果原样保留，不能被修复后结果覆盖或改写。

本任务是SIM-01C倍速子门禁，不降低PERF-01优先级，也不证明35—70 m/s飞行、感知或
地图更新性能。

## 2. 修改边界

### 2.1 唯一两处生产修改

| 文件 | 当前语句 | 计划语句 | 理由 |
| --- | --- | --- | --- |
| `.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/include/configuration_parser.h:62` | `int getRealtimeFactor()` | `float getRealtimeFactor()` | 与已有`float`成员一致，保留0.5，不改变类布局 |
| `.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/src/jsbsim_bridge.cpp:213` | `step_start_time - step_stop_time` | `step_stop_time - step_start_time` | elapsed恢复为正的单步处理耗时 |

不修改`configuration_parser.cpp`的解析方式、`_dt=0.004`、`factor <= 0`既有行为、
`JSBSimBridge::_realtime_factor`的`double`成员或sleep公式。getter是bridge内部C++方法，
全树唯一实际消费者为`jsbsim_bridge.cpp:92`；尽管不涉及ROS公共接口，返回类型改变后
仍必须完整重编译，禁止新旧目标文件混用。

### 2.2 验证工具与文档计划

确认后允许修改或新增以下项目侧文件：

| 文件 | 计划变化 |
| --- | --- |
| `tests/sim_speed_factor.cpp`（新） | 直接编译真实`ConfigurationParser`，检查getter为浮点类型且0.5/1/2不截断 |
| `configs/sim01c_scenarios.yaml` | 增加`SPEED_1`、5源秒固定warmup、九次固定顺序和1倍范围`[0.85,1.15]` |
| `ros_ws/sim01c_run.py` | 支持`SPEED_1`、显式`--bridge-binary`和一次性九次矩阵；保存候选身份、矩阵位置和运行环境 |
| `tests/check_sim01c_scenario.py` | 独立复算1倍结果，并核对候选二进制、完整矩阵、顺序、manifest和清理证据 |
| `tests/test_sim01c_contract.py` | 增加1倍边界、二进制身份漂移、缺项/乱序/挑选结果等反例 |
| `simulation/RUN_SIM01C.md`及管理/实验文档 | 只在实际执行后登记全部结果和仍未验收边界 |

Python与ROS进程仍必须通过`bash ros_ws/sim01_env.sh ...`使用Conda
`Radar-Diffusion`。工具扩展不改变AircraftState、MAVLink、话题、时间戳、坐标或业务
状态机。

### 2.3 本次明确禁止

- 不修改外部`/home/zxj/PX4-Autopilot`、PX4源码或重新构建PX4；
- 不修改`mavlink_interface.h/.cpp`、`SendSensorMessages(int)`、GPS时间类型、MAVLink
  `time_usec`或`jsbsim_bridge.cpp:193`；约35.8分钟的32位微秒边界仍归SIM-01D/R-10；
- 不修改公共消息、simulation/sensors业务状态机、故障阈值或±15%验收容差；
- 不覆盖`.runtime/build/jsbsim-bridge-init01/jsbsim_bridge`，不删除旧构建和失败run；
- 不通过延长/人工挑选窗口、四舍五入、增加重复直到凑齐GREEN来改变结果。

## 3. `steady_clock`与纯helper的评审选择

两项改进有技术价值，但**不属于本次默认生产补丁**：

| 候选 | 价值 | 本次不直接纳入的原因 | 触发后续评审条件 |
| --- | --- | --- | --- |
| `system_clock`改为`steady_clock` | 避免系统墙钟跳变污染单步耗时 | 超出已确认的精确两行根因修复；需单独证明目标环境时钟和调度影响 | 两行修复后矩阵仍漂移，或捕获到墙钟跳变 |
| 抽取header-only纯节奏helper | 可对`dt/factor-elapsed`做确定性C++单测 | 会新增第三个生产头文件并重构`Run()`；不是恢复0.5和elapsed方向的必要条件 | 端到端GREEN仍不足以防止公式回归，且用户确认扩展范围 |

因此首轮直接解析器测试负责getter的确定性RED/GREEN；elapsed方向以已保存的三次2倍
端到端RED和修后九次矩阵作为权威GREEN。若两行修复后仍不通过，停止验收并提交新的
测量/调度提案，不在失败现场自行加入上述候选。

## 4. RED→GREEN实施顺序

### 4.1 实施前封存

1. 重读根及涉及目录AGENTS，核对工作树、真实入口和进程；保存根仓、外部PX4和项目内
   bridge三方状态。
2. 保存既有`mavlink_interface.h/.cpp`的SIM00B-INIT-01精确diff、两个目标文件前副本、
   旧二进制身份及当前配置；确认目标文件仍与外部干净子模块逐字节一致。
3. 检查磁盘、TCP 4560、计划ROS Master端口及PX4/MAVROS/bridge进程；发现既有会话即
   拒绝启动，不接管或清理。
4. 冻结矩阵配置、候选路径和验收字段。封存目录新建于
   `.runtime/logs/sim-speed01-<timestamp>/`，不得覆盖SIM-01C历史证据。

### 4.2 RED

1. 先新增项目层`tests/sim_speed_factor.cpp`，通过真实
   `configuration_parser.cpp`编译，不引入gtest或ROS。测试以运行时类型检查和数值检查
   要求0.5/1/2均保留；当前源码应正常编译但测试退出非零，并明确报告0.5实际为0。
2. 保存当前init01二进制的既有系统RED：三次2倍均低于1.7；0.5运行带terminal，只作
   缺陷证据而不是干净倍率样本。禁止为了再现而重写旧run。
3. 工具契约先增加失败反例：缺`SPEED_1`、九次少一项、顺序改变、二进制身份不一致、
   manifest缺字段、窗口被选择或清理失败均必须RED。

### 4.3 GREEN与独立构建

1. 只改getter为`float`，重跑C++测试；0.5/1/2和返回类型全部GREEN后继续。
2. 只改elapsed相减方向；用`git diff --check`及精确diff确认没有第三处生产变化。
3. 在全新`.runtime/build/jsbsim-bridge-speed01/`完整配置和构建`jsbsim_bridge`；继续使用
   现有`.runtime/build/px4-v1.13.3/bin/px4`，不重建PX4。
4. 检查候选可执行、`ldd`无缺失；把解析后的候选路径、文件大小、mtime和SHA-256写入
   suite及每个run manifest。二进制哈希用于证明九次使用同一候选，不用于替代测试。
5. 先通过工具单元/契约，再一次性执行第5节冻结矩阵。任何源码、配置、二进制或测量
   工具变化都使整批九次失效，必须以新matrix_id从第一项重跑。

候选完整构建沿用[SIM-00A已验证参数](../simulation/BUILD_SIM00A.md)，只改变输出目录：

```bash
bash simulation/sim00a_env.sh /usr/bin/cmake \
  -S .runtime/src/px4-v1.13.3/Tools/jsbsim_bridge \
  -B .runtime/build/jsbsim-bridge-speed01 -G Ninja \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_C_COMPILER=/usr/bin/gcc -DCMAKE_CXX_COMPILER=/usr/bin/g++ \
  -DJSBSIM_INCLUDE_DIR="$PWD/.runtime/deps/jsbsim-1.1.13/usr/include/JSBSim" \
  -DJSBSIM_LIBRARY="$PWD/.runtime/deps/jsbsim-1.1.13/usr/lib/libJSBSim.a" \
  -D_MAVLINK_INCLUDE_DIR="$PWD/.runtime/deps/ros-noetic/opt/ros/noetic/include/mavlink/v2.0"
bash simulation/sim00a_env.sh /usr/bin/cmake \
  --build .runtime/build/jsbsim-bridge-speed01 --target jsbsim_bridge --parallel 4
```

## 5. 预注册九次矩阵

矩阵使用实际PX4/JSBSim/MAVROS、未解锁静止Rascal、同一候选二进制和同一冻结配置。
每次使用新run_id、独立run目录；同一时刻只运行一项。顺序固定如下：

| 全局序号 | 批次 | 批内序号 | 场景 | 目标 | 允许范围 |
| ---: | --- | ---: | --- | ---: | ---: |
| 1 | A | 1 | SPEED_05 | 0.5 | 0.425—0.575 |
| 2 | A | 2 | SPEED_1 | 1.0 | 0.85—1.15 |
| 3 | A | 3 | SPEED_2 | 2.0 | 1.7—2.3 |
| 4 | B | 1 | SPEED_2 | 2.0 | 1.7—2.3 |
| 5 | B | 2 | SPEED_1 | 1.0 | 0.85—1.15 |
| 6 | B | 3 | SPEED_05 | 0.5 | 0.425—0.575 |
| 7 | C | 1 | SPEED_1 | 1.0 | 0.85—1.15 |
| 8 | C | 2 | SPEED_05 | 0.5 | 0.425—0.575 |
| 9 | C | 3 | SPEED_2 | 2.0 | 1.7—2.3 |

每次在首个valid source状态后固定预热5源秒，再取其后的首个不少于20源秒共同窗口；
端点由规则自动选取，不能人工调整。矩阵命令必须显式传入：

```bash
bash ros_ws/sim01_env.sh python ros_ws/sim01c_run.py \
  --speed-matrix \
  --bridge-binary .runtime/build/jsbsim-bridge-speed01/jsbsim_bridge
```

矩阵开始后不得改变顺序或只重跑失败项来替换结果。基础设施失败也保留在总manifest中；
修复原因后另起完整九次批次。额外诊断运行可执行，但不能计入该批验收。

## 6. 验收字段与完成门禁

### 6.1 单run必须全部满足

- `measurement_complete=true`，源时间窗口不少于20秒，warmup和自动端点符合冻结配置；
- `actual_factor = Δclock / Δreceipt_monotonic`由离线checker独立复算，且落入本档范围；
- `/clock`严格递增、terminal为0、预期外WARN/ERROR为0；
- 源/适配状态在窗口内`sample_id/timestamp`顺序一一对应，有真实MAVLink ODOMETRY
  timestamp交集，未发生源timestamp重写；
- 心跳证明全程未解锁，manifest证明未发送解锁、起飞或控制命令；
- HIGHRES_IMU/ODOMETRY流配置成功，observer、source、sensors均使用指定Conda；
- 候选解析路径、SHA-256、大小和mtime与suite冻结值完全相同；PX4和bridge commit、
  SIM00B-INIT-01及两处speed diff均有记录；
- 保存clock/state频率、最大源间隔、各受管进程affinity/CPU时间/上下文切换/I/O、系统
  load、governor/frequency及可用的温度/throttle。硬件不提供的字段明确记
  `available=false`，不能伪造0；
- `manifest`、`speed-result.json`、离线`scenario-result.json`和
  `cleanup-audit.json`共同通过；无强制kill、无本次PID或端口残留。

### 6.2 整批必须全部满足

- suite manifest中的计划和实际序列严格等于上述九项，每项身份唯一且正好出现一次；
- 九次均为GREEN，不能用历史run、诊断run或同倍率第四次结果替换；
- 九次期间候选二进制、源码差异、配置、观察器和主机启动周期不变；若机器重启则整批
  作废重跑；
- 0.5、1、2倍各三次均通过；1倍作为控制组，不降低0.5/2原门禁；
- 全部失败、清理和环境记录进入实验总索引。

只有上述条件和第7节回归均通过，SIM-SPEED-01才可标“已完成”，并据此关闭SIM-01C
的倍速阻塞。任一项不通过时状态保持“阻塞”，不得修改容差或结论。

## 7. 回归与保护检查

矩阵前后至少执行：

1. 新C++测试、`test_sim01c_contract.py`及全仓`test_*.py`；
2. 在`jsbsim-bridge-speed01`目录完整构建并增量复验候选、检查`ldd`，以及既有
   `sim00b_initialization.cpp`回归；
3. 11项实际ROS fixture；
4. SIM-01B LIVE/B1/B2归档的纯函数只读校验，不运行会重写历史`result.json`的CLI；
5. 外部PX4仍干净；项目bridge差异精确等于既有两个初始化文件加本任务两个speed文件；
6. 旧init01二进制身份未变，所有本次进程和端口已释放，历史run未改写。

## 8. 候选隔离、恢复与停止条件

当前回退基线为
`.runtime/build/jsbsim-bridge-init01/jsbsim_bridge`，大小`71,059,128`字节，SHA-256
`e775a33234fd885ec406f7586a19c63745484f166633811a8ccbf47f0846d3f6`。它不得被重建、
替换或删除。

- 运行恢复：去掉`--bridge-binary`即回到默认init01；禁止临时覆盖后再改回。
- 源码恢复：只使用实施前保存的两个目标文件副本或反向补丁撤销speed差异；不得
  `git reset/clean/checkout`，不得触碰两个既有SIM00B-INIT-01 dirty文件。
- 产物恢复：失败候选、构建日志和run继续保留，不以删除掩盖失败；停止本次记录的PID/
  进程组并核对端口，不用宽泛`pkill`。
- 停止条件：C++ GREEN失败、diff越界、旧二进制漂移、候选依赖缺失、已有PX4会话、
  未解锁条件破坏、terminal/ERROR、矩阵环境漂移或清理失败时立即停止后续验收。

## 9. 实施结果

用户确认后，实施严格保持本文锁定的两行生产改动。独立候选二进制SHA-256为
`d846038cddbd64859e1d48e414d994248c70c408ec3552d39cb472e2beb63ddf`；预注册九次矩阵
全部`COMPLETE`，三档实测范围分别为0.492476—0.492647、0.971738—0.972527和
1.899797—1.909010，逐run零terminal且清理通过。完整证据见
[实施记录](../experiments/2026-09-16-sim-speed01-implementation.md)。

`steady_clock`、纯helper及32位时间边界仍未随本次实施纳入；其中约35.8分钟边界继续
由SIM-01D/R-10验收。本结果不证明35—70m/s飞行、感知、地图更新或训练监督LiDAR。
实施期间曾有一份历史RED派生`scenario-result.json`被checker CLI以相同失败语义
重写、mtime改变；原始观测、manifest与`speed-result.json`未改。这是本方案“历史run
未改写”保护检查的已披露偏差，技术矩阵结论不变。2026-09-17，用户明确
接受该非符合项，并要求保留完整记录、不伪造原mtime、不尝试恢复。该明确决定
作为门禁例外接受依据，SIM-SPEED-01及SIM-01C据此正式关闭；详见实施记录与
ADR-P013。SIM-01D、PERF-01及高速地图验收不随之关闭。
