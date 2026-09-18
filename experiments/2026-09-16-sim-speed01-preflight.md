# EXP-20260916-002：SIM-SPEED-01真实调用链与实施前核查

日期：2026-09-16；主责任：simulation_engineer；
状态：**只读核查完成，具体方案待用户确认，未实施**。
方案：[SIM-SPEED-01实施方案](../docs/SIM_SPEED_01_IMPLEMENTATION_PLAN.md)。

## 1. 核查范围和方法

本轮由bridge调用链、C++测试路径、端到端验收和保护/恢复四个只读审查方向交叉核对，
并由Technical Lead整合。读取根规范、项目状态、系统架构、相关目录规则、真实源码、
当前二进制和SIM-01C产物；没有修改运行代码、外部PX4、历史实验、消息或状态机，没有
启动ROS/PX4/JSBSim，也没有构建候选二进制。

本文区分：源码静态证明、现有二进制身份、既有运行结果和后续计划。计划值不能写成
实测值，文档创建也不表示SIM-SPEED-01已经实施。

## 2. 当前基线

| 对象 | 只读核查结果 |
| --- | --- |
| UAV-FusionMap根仓 | `feature/engineering-initialization`，尚无首次提交，现有项目文件均须按工作资产保护 |
| 外部PX4 | `/home/zxj/PX4-Autopilot`为`1c8ab2a0d7db2d14a6f320ebd8766b5ffaea28fa`，工作树干净 |
| 项目内bridge副本 | commit `68de2cc63ded9a0d6641d45e9eb3ed2b43454cba` |
| bridge既有差异 | 仅`include/mavlink_interface.h`、`src/mavlink_interface.cpp`中的SIM00B-INIT-01五处初始化修改 |
| 本任务目标文件 | `configuration_parser.h`和`jsbsim_bridge.cpp`均与外部干净子模块逐字节一致 |
| 当前运行二进制 | `.runtime/build/jsbsim-bridge-init01/jsbsim_bridge`，71,059,128字节，SHA-256为`e775a33234fd885ec406f7586a19c63745484f166633811a8ccbf47f0846d3f6` |
| 现有测试基础设施 | bridge CMake只有生产可执行target，无CTest；项目根已有直接编译真实bridge对象的C++测试模式 |

根仓没有可用于安全回退的已提交HEAD，因此后续实施不能依赖普通Git复原。必须在写入
前保存精确前副本/反向补丁；既有两个dirty文件和旧init01二进制不得被重建或覆盖。

## 3. 真实调用链

| 顺序 | 源码证据 | 已确认行为 |
| ---: | --- | --- |
| 1 | `ros_ws/sim01c_run.py:660-671` | 从冻结场景读取0.5/2并转成`PX4_SIM_SPEED_FACTOR`字符串 |
| 2 | `ros_ws/sim01b_runtime.py:160-169` | `Processes.spawn`把覆盖环境交给实际子进程并记录命令 |
| 3 | `ros_ws/sim01c_run.py:710-712` | 当前写死启动`.runtime/build/jsbsim-bridge-init01/jsbsim_bridge`，不是ROS timer包装入口 |
| 4 | bridge `src/main.cpp:46,66` | 构造`ConfigurationParser`并调用`ParseEnvironmentVariables()` |
| 5 | bridge `src/configuration_parser.cpp:50-52` | `std::stod`解析环境字符串并赋给float成员 |
| 6 | bridge `include/configuration_parser.h:62,74` | getter返回`int`，成员为`float`，小数在getter处向零截断 |
| 7 | bridge `src/jsbsim_bridge.cpp:92` | 截断后的值再赋给`double _realtime_factor`，精度无法恢复 |
| 8 | bridge `src/main.cpp:73-75` | 独立可执行无限调用`JSBSimBridge::Run()` |
| 9 | bridge `include/jsbsim_bridge.h:83`、`src/jsbsim_bridge.cpp:51` | `_dt`为0.004秒并传给JSBSim |
| 10 | bridge `src/jsbsim_bridge.cpp:169-216` | 用墙钟测一步、推进FDM，并按`dt/factor-elapsed`休眠 |

同一环境变量也传给PX4，但`ROMFS/.../rcS:158-165`只用它缩放失联超时，不控制JSBSim
主循环节奏。本任务不修改该脚本或PX4。可选`jsbsim_bridge_ros`入口还有固定4毫秒ROS
timer，但当前SIM-01C不走该入口，不能把它的潜在行为混入当前修复。

## 4. 两个直接缺陷

### 4.1 0.5倍截断

`std::stod("0.5")`的结果存入`float _realtime_factor`，但类内getter返回`int`。构造函数
取值时0.5已经变为0；`Run()`的`_realtime_factor > 0`不成立，bridge不休眠。由同一
规则可知，`[1,2)`会量化为1、`[2,3)`会量化为2，所有非整数倍率均丢失小数。

这条因果同时有源码、当前二进制反汇编中的`cvttss2si`和0.5实际自由运行现象支持。
最小修复是只把getter返回类型由`int`改为`float`；不需要改变成员布局或消费者double。

### 4.2 elapsed方向错误

当前源码为：

```text
elapsed = step_start_time - step_stop_time
sleep = dt / factor - elapsed
```

若真实单步处理耗时为`w > 0`，则`elapsed = -w`，实际sleep约为`dt/factor + w`，整步
墙钟时间约为`dt/factor + 2w`。这会系统性拖慢正倍率，与三次2倍约1.69的结果相容。

但现有数据不能把全部1.69偏差单因果归于这一行：observer在共同锁内做事件编码、写盘
和MAVLink解码，主机负载、调度及跨重启环境也会影响墙钟分母。因此最小修复只更正
`step_stop_time - step_start_time`，再由冻结九次矩阵给出系统结论；不得把静态公式直接
写成端到端GREEN。

## 5. 既有运行证据

### 5.1 2倍是可信端到端RED

| 证据目录 | 实际倍率 | 现有结论 |
| --- | ---: | --- |
| `.runtime/runs/sim01c-suite-20260916T085038422389/speed-2` | 1.698206519 | 完整窗口、零terminal、低于1.7 |
| `.runtime/runs/sim01c-suite-20260916T085205867969/speed-2` | 1.694531726 | 完整窗口、零terminal、低于1.7 |
| `.runtime/runs/sim01c-suite-20260916T085553794733/speed-2` | 1.689637552 | 完整窗口、零terminal、低于1.7 |

三次均有clock/source/raw ODOMETRY独立复算、身份窗口、未解锁、原timestamp和清理证据，
可作为修复前RED。它们不能因接近1.7而四舍五入成通过。

### 5.2 0.5只有缺陷证据，没有干净RED窗口

`.runtime/runs/sim01c-suite-20260915T184438701028/speed-05`曾取得20源秒并计算
`71.454319482`，但随后发生`estimator_reset`和terminal；另一run在窗口完成前失败。
所以0.5现象与截断缺陷一致，却不满足干净倍率样本前提。修后必须新跑，不能用这个数字
作统计基线或GREEN比较。

## 6. C++测试与构建可行性

bridge的`CMakeLists.txt:66-79`只有`jsbsim_bridge`生产target，当前两个Ninja目录也无
CTest。为两行修复引入CTest或修改第三方CMake会扩大范围。项目根已有
`tests/sim00b_initialization.cpp`直接编译真实bridge对象的模式，因此建议新建
`tests/sim_speed_factor.cpp`：

- 使用真实`ConfigurationParser`和`configuration_parser.cpp`；
- 运行时检查getter的返回类型为浮点；
- 分别设置0.5、1和2，确认数值没有截断；
- 当前源码应正常编译、运行退出非零形成RED，改getter后退出0形成GREEN。

拟用独立测试输出目录`.runtime/build/jsbsim-speed01-test/`。生产候选再按SIM-00A相同
CMake参数完整构建到`.runtime/build/jsbsim-bridge-speed01/`。getter定义在类内、只有
一个消费者且不改变类布局，但返回约定改变仍禁止部分链接；必须完整重编译。

elapsed若不抽纯helper，很难在不构造完整JSBSim/MAVLink依赖的条件下做真实函数单测。
本方案选择用现有2倍RED和九次实际链路做RED/GREEN，不为测试新增生产helper。该取舍
避免第三个生产文件；代价是公式回归主要靠端到端测试防护，已在方案风险中明确。

## 7. 测量可信度与预注册矩阵

当前工具只有0.5/2两个case，且bridge路径写死。单次补跑会面临顺序、主机环境和选择
结果偏差。前置审查因此建议在修改生产源码前先冻结：

- 新增1倍控制组；
- 采用`0.5→1→2`、`2→1→0.5`、`1→0.5→2`三批，共固定九次；
- 每次首个valid后固定5源秒warmup，再自动取首个20源秒窗口；
- 用`--bridge-binary`显式选择候选，默认仍保留旧init01；
- suite manifest封存完整计划、实际顺序和唯一候选身份；
- 任一代码、配置、二进制或主机启动周期变化后，整批九次作废重跑；不能运行到凑齐
  三个GREEN。

0.5/1/2的±15%范围分别为`[0.425,0.575]`、`[0.85,1.15]`、`[1.7,2.3]`。这仍是静止
仿真节奏冒烟，不是PERF-01性能门禁。

现有observer在同一锁内记录事件和解码原始MAVLink，可能扰动墙钟测量。首轮不重构
observer，而是保留自动端点、增加per-process CPU/调度/I/O和主机频率/负载证据，并用
三种顺序暴露顺序效应。若两行修复后的九次仍不稳定，停止并单独评审“计时回调只写
预分配内存、raw/diagnostic分锁或分进程、bridge内部steady_clock双证据”，不能现场
修改测量方法后继续计数。

## 8. 范围排除与风险

### 8.1 `steady_clock`和纯helper

`steady_clock`能避免系统墙钟跳变，纯helper能对节奏公式做确定性测试；两项都合理。
但前者改变计时源，后者增加生产头文件并重构`Run()`，都超出已锁定的两处最小修复。
它们保留为修后矩阵仍失败时的独立评审候选，本次确认不得默认为已授权。

### 8.2 32位微秒边界

`mavlink_interface.h:135`的`SendSensorMessages(int)`、`jsbsim_bridge.cpp:193`的
`simtime * 1e6`隐式转换和GPS链仍有32位时间问题；MAVLink HIL_SENSOR字段本身是
`uint64_t`。`INT_MAX`微秒约35.8分钟。修复它会跨入既有dirty文件和多条消息路径，且
20源秒矩阵无法验收，因此继续由SIM-01D/R-10至少40分钟测试处理，不得混入本任务。

### 8.3 仍需实际验证的风险

- 两行修改能否使九次都落入±15%，只能由实际矩阵决定；
- 1.69可能同时包含observer和主机调度影响，不能保证更正方向后必然GREEN；
- 0.5运行墙钟最长，仍可能暴露与getter无关的PX4 estimator reset；
- 系统温度/throttle接口可能不存在，必须记录不可用，不能伪造环境稳定；
- 根仓无提交，若不先保存前副本，普通Git无法安全恢复项目工作资产。

## 9. 保护与恢复结论

建议实施时采用以下硬边界：

1. 旧`.runtime/build/jsbsim-bridge-init01/`只读保留；候选仅放
   `.runtime/build/jsbsim-bridge-speed01/`；
2. 运行器默认仍使用旧二进制，只有显式`--bridge-binary`才运行候选，并由离线checker
   核对解析路径和身份；
3. 源码diff最终只能是既有两个SIM00B文件加本任务两个speed文件；外部PX4保持干净；
4. 失败运行、构建日志和候选不删除；恢复时去掉候选参数，并只对两个speed目标文件
   使用前副本/反向补丁；
5. 不用`git reset/clean/checkout`或宽泛`pkill`，只停止本次记录的PID/进程组并核对端口。

## 10. 核查结论和下一步

两个直接根因、唯一消费者、构建边界和候选隔离方式已经明确，可以按
[实施方案](../docs/SIM_SPEED_01_IMPLEMENTATION_PLAN.md)进行小范围修复；但当前状态仍是
“具体方案待用户确认，未实施”。

用户确认后才按“封存→C++ RED→两行生产修复→独立完整构建→工具契约→预注册九次矩阵
→全量回归→状态文档”执行。确认SIM-SPEED-01不等于授权`steady_clock`、纯helper、
32位时间修改、PX4改动或PERF-01地图性能结论；任何扩大范围须重新提交方案并确认。
