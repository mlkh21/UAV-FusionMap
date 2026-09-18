# Phase 1候选版本与最小仿真验证方案

版本：v0.1；日期：2026-09-11；主责任角色：system_architect。
任务：ENV-02；状态：技术方案已完成，候选A进入准备顺序，安装/构建/运行尚未执行。
决定见[ADR-006](DECISION_LOG.md)，本轮证据见[EXP-20260911-003](../experiments/2026-09-11-simulation-plan-review.md)。

## 1. 本轮决定与验证目标

首先评估候选A：Ubuntu 20.04.6 + ROS 1 Noetic + PX4 v1.13.3 + JSBSim 1.1.13 +
现有提交的独立JSBSim桥接 + MAVROS 1.20.1。运行Rascal固定翼、HEADLESS模式，
先获得带来源和原始采样时间的状态，再验证ROS记录回放。具体版本见下一节。

这是首次验证的技术选择，兼容性需SIM-00/SIM-01验证后才能冻结为可运行基线。
用户授权继续ENV-02方案工作；本文件不将该授权扩大为安装软件、修改外部源码、
修复驱动、飞控控制或运行仿真。后续按已明确的具体任务授权执行。

本机事实以[ENV-01环境清单](../configs/ENVIRONMENT_INVENTORY.md)为2026-09-11快照。
保留交互终端Foxy(1)/Noetic(2)菜单。项目任务使用干净子进程、明确Noetic setup路径和
明确Python解释器，不修改菜单、不叠加两个ROS版本。
09-11/12的SIM-00A/B历史验证使用系统Python；09-14用户按ADR-009指定后，
后续所有Python默认Conda Radar-Diffusion（3.8.12），使用[SIM-01A入口](../simulation/RUN_SIM01A.md)，
不修改Conda原安装、不加载研究代码/模型。此更新替代本方案早期的系统Python默认值。

## 2. 路线比较与版本候选

| 路线 | 复用条件与代价 | 维护条件 | 决定 |
| --- | --- | --- | --- |
| A：现有Ubuntu 20.04 / Noetic / PX4 v1.13.3 | 本机已有ROS和PX4；桥接源码为ROS 1/catkin，历史CI配置包含Noetic；仍缺JSBSim/MAVROS | Noetic已结束官方支持，需要保存可复现资产并由项目承担维护 | 首选验证候选 |
| B：现有Ubuntu 20.04 / Foxy | ROS 2存在，但不能直接运行现有ROS 1桥接节点；需要新的通信适配路线 | Foxy也已结束支持，增加适配工作却没有支持周期收益 | 保留现有安装，本阶段不同时实现 |
| C：独立Ubuntu 22.04 / Humble | 需新增独立环境并验证ROS 2与PX4/JSBSim连接 | Humble支持至2027年5月，覆盖计划交付但缓冲较短 | 如有ROS 2依赖，作为替代路线比较 |
| D：独立Ubuntu 24.04 / Jazzy | 同样需要独立环境及新的桥接验证，不能假定旧PX4组合兼容 | Jazzy支持至2029年5月，适合更长维护需求 | 长期替代候选，不升级当前主机 |

Humble/Jazzy的目标OS和支持期来源于[ROS REP-2000](https://raw.githubusercontent.com/ros-infrastructure/rep/master/rep-2000.rst)。
Noetic/Foxy结束支持的来源已登记于ENV-01。历史CI文件仅证明配置中包含Noetic，不代表
本机或当前依赖已经构建通过。上述复用成本与排序属于本次工程判断。

| 项目 | 候选版本/来源 | 当前证据与锁定条件 |
| --- | --- | --- |
| OS / ROS / Python | Ubuntu 20.04.6；Noetic；09-14起Conda Radar-Diffusion Python 3.8.12 | 用户默认；catkin/消息/ROS轻量链路已测，历史SIM-00用系统3.8.10；完整环境恢复另验 |
| PX4 | v1.13.3，1c8ab2a0d7db2d14a6f320ebd8766b5ffaea28fa | 现场源码提交；新构建须记录子模块，不将旧二进制默认绑定该源码 |
| JSBSim桥接 | 68de2cc63ded9a0d6641d45e9eb3ed2b43454cba | 复用独立CMake可执行程序；不选其ROS定时器包装作为动力学主循环 |
| JSBSim引擎 | v1.1.13，官方release页面短提交a09715f | 首个试验候选；官方提供Focal amd64发布说明，未证明与桥接兼容 |
| MAVROS | ros-noetic-mavros 1.20.1-1focal.20250520.005419 | 本机APT缓存候选；软件尚未安装 |
| MAVLink头文件 | ros-noetic-mavlink 2025.5.5-1focal.20250505.181801 | 与上述MAVROS解析出的候选；桥接编译时记录实际include位置 |
| 其余编译依赖 | 现有GCC 9.3.0、CMake 3.16.3、Boost 1.71、Eigen 3.3.7、TinyXML 2.6.2 | 本机元数据；链接和ABI仍需构建核查 |

JSBSim候选依据：[官方v1.1.13发布](https://github.com/JSBSim-Team/jsbsim/releases/tag/v1.1.13)
明确列出Ubuntu Focal；本轮没有取得具体开发包的完整文件清单，SIM-00须确认资产
名称、架构、依赖及FGFDMExec.h/libJSBSim位置。不能拿Python wheel替代C++开发库。
若候选不兼容，登记编译错误后逐项调整版本，不自动追随master或rolling release。

## 3. 依赖补齐范围与现有资产保护

本轮已实际执行APT模拟解析，未刷新软件源、下载包或安装：

```bash
apt-get --simulate --no-install-recommends install ros-noetic-mavros=1.20.1-1focal.20250520.005419
```

退出码0，计划新增7个包、升级0个、移除0个。以下是本次缓存解析快照，不保证未来仓库
仍提供同一文件；实际下载前重新检查可取得性和变更范围：

| 包 | 解析版本 |
| --- | --- |
| libgeographic19 | 1.50.1-1build1 |
| geographiclib-tools | 1.50.1-1build1 |
| libgeographic-dev | 1.50.1-1build1 |
| ros-noetic-mavlink | 2025.5.5-1focal.20250505.181801 |
| ros-noetic-libmavconn | 1.20.1-1focal.20250505.183037 |
| ros-noetic-mavros-msgs | 1.20.1-1focal.20250520.005026 |
| ros-noetic-mavros | 1.20.1-1focal.20250520.005419 |

初步也模拟过含mavros-extras的组合，共8个新增包；最小路线只需要核心MAVROS传输，
因此不将extras列为必需。今后若采用extras的odometry插件，单独说明用途并更新清单。

还需处理两项独立资产：

- JSBSim开发包：先读取官方Focal资产控制信息/文件清单，再优先解包到项目运行前缀。
  显式设置JSBSim头文件、库及运行库搜索路径；如必须系统安装，先列出具体事务影响。
- GeographicLib的egm96-5 geoid数据：两个标准share路径本轮均未发现该文件。
  [MAVROS 1.20.1说明](https://raw.githubusercontent.com/mavlink/mavros/1.20.1/mavros/README.md)
  指出该数据缺失会导致节点退出；APT依赖解析不等于数据已经安装。SIM-00登记数据
  来源、保存位置及GEOGRAPHICLIB_GEOID_PATH或实际默认搜索路径，再验证节点加载。

SIM-00不包括GPU驱动修复、FlightGear/Gazebo新安装、研究Python依赖或算法数据。
退出时保存下载来源、包控制信息、环境清单和安装前后差异，不执行autoremove、
系统整体升级或共享catkin工作区构建。失败时保留日志，恢复只针对本次事务。

## 4. 构建与运行目录设计

以下路径均为计划，尚未创建。UFM_ROOT指本仓库根；机器路径由运行配置提供。

| 计划位置（相对UFM_ROOT） | 用途 |
| --- | --- |
| .runtime/src/px4-v1.13.3/ | 独立的PX4及固定子模块副本；不改/home/zxj/PX4-Autopilot |
| .runtime/deps/jsbsim-1.1.13/ | 经检查的JSBSim开发包解包/安装前缀 |
| .runtime/build/px4-v1.13.3/ | 新的PX4构建与对应etc资源 |
| .runtime/build/jsbsim-bridge/ | 独立桥接CMake构建；记录实际JSBSim和MAVLink路径 |
| ros_ws/src/ | 后续工程消息和薄节点源码，仅从本工作区构建 |
| .runtime/ros/{build,devel,logs}/ | 本项目catkin构建输出，不覆盖外层catkin_ws/build或devel |
| .runtime/runs/<run_id>/ | 本次rootfs、ROS日志、PX4日志、stdout/stderr、bag与manifest |
| experiments/<日期>-<编号>.md | 可长期追踪的结果和产物索引 |

运行目录填充前，ENV-03/SIM-00需建立精确忽略规则及`.runtime/CATKIN_IGNORE`，防止
下载源码、嵌套ROS包和大型产物进入外层catkin发现范围或Git提交。仅有.gitignore
不能保护已跟踪文件；当前不删除任何文件，也不执行Git提交。
临时运行目录不代替备份：包与源码归档、可恢复环境及代表性bag需要另有保存副本，
保存位置和恢复检查由ENV-03登记，实验记录保留索引。

新构建先核对CMake缓存的源目录、CONFIG=px4_sitl_default和工具链，再构建PX4目标与
桥接可执行目标。不要直接执行会同时启动仿真的make目标；桥接的实际库解析由缓存和
动态链接检查证明。源码内资源路径会影响运行，源码副本必须随基线保留。

## 5. 启动连接与进程责任

```text
JSBSim独立桥接（Rascal，HEADLESS）
    ↕ HIL_SENSOR / HIL_ACTUATOR_CONTROLS，TCP 4560
PX4 SITL（instance 0，估计状态）
    ↕ MAVLink 2，PX4 UDP 14580 → MAVROS UDP 14540
MAVROS（ROS 1传输、原始消息与诊断）
    → simulation状态/时钟接入（后续实现）
    → /uav/sim/state → sensors状态适配（后续实现）
    → /clock及独立记录器
```

候选MAVROS fcu_url为`udp://127.0.0.1:14540@127.0.0.1:14580`，gcs_url为空，协议v2.0。
这是由本机px4-rc.mavlink的instance 0端口推导，需运行时验证双向端点。旧桥接launch
中写的14557不直接沿用。TCP 4560由桥接监听；存在其他占用时停止本次启动，不终止
别人的进程。旧桥接监听地址为INADDR_ANY，本方案不声称仅绑定回环；SIM-00运行前
核对网络范围和是否需独立网络环境，不在文档阶段修改防火墙或外部源码。

启动顺序：独立ROS master与记录准备 → 原始消息接收/时钟接入 → 独立JSBSim桥接 →
PX4 → MAVROS连接与所需消息流 → 状态消费。各进程可先等待，但ready必须基于数据。
设置use_sim_time的节点不得靠ROS仿真定时器启动时钟生产链；启动/超时管理用墙上
单调时钟，原始接收使用网络回调。MAVROS时间设置见下一节。

运行装配需由后续ros_ws薄启动包装跟踪本次PID/进程组、退出码及输出目录。
停止时只结束本次进程；记录器先正常关闭bag。原Tools/sitl_run.sh行85—90含按名称
pkill，桥接stderr还被重定向到/dev/null，因此不直接作为本项目常规启动器。
下列为已追踪源入口的参数形状，尚非可直接运行的命令：

- 桥接：`<独立桥接二进制> rascal -s <固定源码中的scene/LSZH.xml>`，HEADLESS=1。
- PX4：在`<run_id>/rootfs`内启动`<新px4二进制> <对应build>/etc -s etc/init.d-posix/rcS`，
  以PX4_SIM_MODEL=rascal选择机型；保留其启动所需资源与环境，实际完整命令在SIM-00登记。
- 初次只验证静止初始化和遥测；没有解锁、起飞、航点或offboard指令。

## 6. 状态、时钟与坐标接入方案

### 6.1 先保留源语义，再经过sensors转换

MAVROS作为simulation接入的传输组件。其原始`mavlink/from`承载消息供simulation
接入和独立记录器读取；最终话题名由后续launch显式命名，不能假定等于/mavros/mavlink/from。
业务下游仍只读相邻层公开契约，mapping不订阅此原始通道。

| 来源 | 用途和转换责任 | 有效性要求 |
| --- | --- | --- |
| PX4 ODOMETRY | simulation解码为AircraftState；position在world_ned，Body及速度为body_frd；q从[w,x,y,z]重排为[x,y,z,w] | 只接受AUTOPILOT估计、LOCAL_NED/BODY_FRD组合；保留timestamp_sample、reset_counter及协方差来源 |
| PX4 HIGHRES_IMU | 原始IMU记录；采样time_usec作为本次采样型仿真时钟的候选来源 | 检查消息身份、有效字段和原始微秒时间；惯性数据的比力/坐标语义在sensors接入时验证 |
| sensors状态适配 | 将AircraftState的NED/FRD转换为约定odom/FLU，维护同采样时刻变换与质量 | 标明odom原点关系；只发布一份权威变换，不重复转换已是ENU的诊断数据 |

这里的AircraftState沿用DATA_FORMAT，不新增另一套公共字段。state_source=estimated，
source_type=simulation；不是JSBSim真值。后续场景/传感器模拟所需真值需独立来源与验收。
ODOMETRY携带同一状态样本的位姿和速度，可避免将最近姿态直接拼到另一时间的位置上。
MAVROS的local_position/odom会读取缓存姿态，故本方案把它作为诊断参考，不作为
同采样时刻状态的证明。对应证据见第9节。

协方差只有来源、排列、单位与转换均明确时才标available；旧PX4 ODOMETRY流中的
速度协方差旋转仍有TODO，未验证部分保持unavailable，不能把全0当作确定无误差。
估计器reset_counter变化时暂停连续odom有效输出；SIM-01的最小策略是停止本次联调，
重新启动完整仿真并建立新run_id，保留原记录，避免把跳变融合进旧地图。

### 6.2 仿真时钟来源与初始化

本机源调用链为GetSimTime → HIL_SENSOR.time_usec → PX4仿真CLOCK_MONOTONIC；
PX4 HIGHRES_IMU/ODOMETRY各自发送timestamp_sample。后续simulation时钟接入从原始
HIGHRES_IMU.time_usec取样，乘1000表示纳秒，clock_id=sim:<run_id>，不减去第一帧
接收时间、也不把墙上时间当作采样时间。与JSBSim时间的关系须通过首段日志验证。

该/clock是最近可验证采样时刻的代理，精度和更新间隔需实测，不声称连续准确真值。
仅在新有效样本到达时前进；等待中的状态若时间晚于/clock，按有界队列等待时钟覆盖，
超时则声明不可用，不回写消息时间。断流/暂停时停止前进，用独立墙上单调时钟报告
超时；进程重启或源时间回退必须启动新run_id及新记录。

MAVROS候选参数：time/timesync_mode=PASSTHROUGH、time/publish_sim_time=false、
conn/system_time_rate=0、conn/timesync_rate=0。每次用新进程，验证offset为0以及输出
时间等于对应原始采样时间；原始消息外层ROS header只作接收标记，不能用来生成/clock。
MAVROS内置publish_sim_time从SYSTEM_TIME.time_unix_usec生成/clock，不符合本项目
运行经过时间语义；不用它替代上述接入。

### 6.3 记录与回放

每个run先建立manifest：版本、源目录、场景、参数、端口、time/frames约定及来源，
随后记录/clock、原始MAVLink、AircraftState、诊断与已明确的静态变换。原始包的CRC/
framing、system/component ID、采样时间和估计器重置需可复核。
后续记录器必须保存各接收者的计数与落盘计数，不能把ROS bag正常关闭等同于无丢帧。

回放在独立ROS master和空消费状态下进行，保留原run_id/sample_id与采样时间，在
manifest中另记replay会话。原始重建时由时钟接入生成/clock并排除bag中的/clock；
成品消息回放时仅重放已记录/clock，关闭时钟接入。两种方式不得同时产生两个时钟，
成品回放不再给rosbag play添加会额外生成/clock的选项。每次循环回放重建消费状态。

## 7. 最小验证任务与门槛

以下数值是首次工程冒烟检查的设计门槛，不是高速飞行性能指标，尚未实测。
PERF-01仍需确定目标航速、机载硬件、同步/时延和稳定性预算。

| 任务 | 实施内容 | 退出条件/证据 |
| --- | --- | --- |
| SIM-00A 依赖与隔离构建 | 核对包来源和精确事务，准备JSBSim/MAVROS/geoid、独立源码及输出目录 | 包/库可解析、构建成功；源码和CMake缓存/链接证据对应；原环境保留 |
| SIM-00B 无界面遥测冒烟 | Rascal静止初始化；PX4与桥接独立运行，MAVROS接收 | 等待上限60秒墙上时间；连接后连续120秒仿真时间有HEARTBEAT和有效采样遥测；保留原始日志 |
| SIM-01A 消息与接入 | 按现有契约实现simulation状态/时钟接入、ros_ws薄包装及sensors时空适配 | 字段有效性、消息往返、帧方向与原始时间对应；未实现的接口不能用现有话题冒充 |
| SIM-01B 记录与回放 | 预热后连续300秒仿真时间记录并回放 | /clock请求50Hz、ODOMETRY请求20Hz；实际有效频率分别至少40/10Hz，同域连续数据间隔不超过0.5秒；时间倒退/重复融合0次 |
| SIM-01C 时钟与异常 | 启动等待、断流、暂停/恢复、0.5与2倍速、新run重启、估计器重置 | 暂停/断流不伪造时钟进展；墙上时间2秒内报异常；每种重置隔离run，记录实际倍速与时间差 |
| SIM-01D 阶段持续性 | 先处理下节时间范围风险，再验证更长运行 | 修复后跨35.8分钟边界的至少40分钟仿真测试；性能/稳定性阈值按PERF-01补全后才能关闭Phase 1 |

ODOMETRY和HIGHRES_IMU的流速由本次PX4实例的MAVLink流配置明确设置，不能只设置
ROS订阅频率。以下为后续PX4控制台中的设计命令，尚未执行，不是在Bash中直接运行：

```text
mavlink stream -u 14580 -s ODOMETRY -r 20
mavlink stream -u 14580 -s HIGHRES_IMU -r 50
```

执行前确认该实例确实使用14580；记录配置后实际接收到的消息ID、来源和采样频率。

坐标单元检查至少覆盖NED北向→ENU北向、NED下向→ENU负Z、FRD右向→FLU负Y、
组合姿态及逆变换；浮点往返误差≤1e-6（m/无量纲），不作为实机定位精度。
记录回放要求字段、身份及时间戳精确保留，浮点按序列化精度比较；报告发布、接收和
落盘数量及不一致原因，任何无法解释的缺失都不能记为完整回放通过。

首次SIM-00B在桥接进程累计仿真时间600秒或墙上时间900秒前停止，较早者生效；
SIM-01B/C每个独立run也受该临时上限约束。不能通过把长测试切成短测试关闭持续性问题。
超时、端口冲突、依赖不符或无有效状态时保留结果并停止该任务，不自动放宽门槛。

## 8. 已知限制及维护到2027年3月的安排

| 问题 | 本次证据及影响 | 处理节点 |
| --- | --- | --- |
| 旧脚本会终止同名进程 | sitl_run.sh含pkill且丢弃桥接stderr | SIM-00B前以本项目装配管理独立PID和日志 |
| 微秒时间被窄化为int | 桥接SendSensorMessages(int)接收GetSimTime×1e6；本机int为32位，约2147.483647秒后超范围 | 限制短测；2026-10-05前提出独立修复方案，SIM-01D前验证；不擅自修改外部桥接 |
| 实时节奏计算待验证 | jsbsim_bridge.cpp行213为step_start_time减step_stop_time | 不保证PX4_SIM_SPEED_FACTOR等于实测倍速；记录实际节奏，必要修复独立评审 |
| 时间/状态接入尚无代码 | 原ROS状态回调TODO，内置时钟语义不符；本方案的新接入待实现 | SIM-01A，T-02/T-03/T-04；R-08在运行通过前保持开放 |
| geoid及其他安装尚缺 | APT模拟不包含GeographicLib数据和JSBSim开发资产验证 | SIM-00A，完成具体安装/解包核查后再启动 |
| 版本结束支持及发布资产消失 | Noetic/Foxy已结束官方支持；下载资产可取得性未验证 | ENV-03保存源码、包、配置及恢复步骤；每月复核，2026-10-15做恢复验证 |

时间参数范围与节奏计算是不同问题；后续每项单独复现、修复和验证，不合并为一次
无依据的桥接重写。外部源码修复不属于当前文档任务。

Technical Lead暂代维护责任，至2027年3月保持一套经测试的主组合；所有升级在独立
目录验证后再替换。每月检查关键依赖可取得性、上游相关修复和版本恢复能力。
2026-10-15 Phase 1出口及2027-01-15交付前复审是否继续保留候选A或切换独立ROS 2路线。
若候选A不能满足时钟、持续性或恢复要求，应在Phase 2扩大开发前评审替代路线及日期
影响，不以“冻结旧版本”替代维护。GPU问题另由R-07处理，不作为无模型仿真准备前提。

## 9. 源码与外部依据

本机PX4源证据均按上述固定提交核对；行号会随版本变化，未来同时按符号核查。

- [桥接CI](/home/zxj/PX4-Autopilot/Tools/jsbsim_bridge/.github/workflows/catkin_build_test.yml)：包含Noetic矩阵。
- [桥接CMake](/home/zxj/PX4-Autopilot/Tools/jsbsim_bridge/CMakeLists.txt)：独立可执行程序、JSBSim库及catkin条件。
- [桥接主循环](/home/zxj/PX4-Autopilot/Tools/jsbsim_bridge/src/jsbsim_bridge.cpp)：Run行169—216，HIL采样时间与节奏计算。
- [微秒参数](/home/zxj/PX4-Autopilot/Tools/jsbsim_bridge/src/mavlink_interface.cpp)：SendSensorMessages行228及TCP监听路径。
- [旧启动器](/home/zxj/PX4-Autopilot/Tools/sitl_run.sh)：行85—90、203—232，清理方式与实际程序入口。
- [PX4遥测端口](/home/zxj/PX4-Autopilot/ROMFS/px4fmu_common/init.d-posix/px4-rc.mavlink)：行4—5、26。
- [仿真时间接入](/home/zxj/PX4-Autopilot/src/modules/simulator/simulator_mavlink.cpp)：handle_message_hil_sensor行483起。
- [ODOMETRY流](/home/zxj/PX4-Autopilot/src/modules/mavlink/streams/ODOMETRY.hpp)：send的来源、timestamp_sample、NED/FRD、协方差及reset_counter。
- [HIGHRES_IMU流](/home/zxj/PX4-Autopilot/src/modules/mavlink/streams/HIGHRES_IMU.hpp)：time_usec来自timestamp_sample。
- [MAVROS传输源](https://raw.githubusercontent.com/mavlink/mavros/1.20.1/mavros/src/lib/mavros.cpp)：原始from消息、命名空间和接收header。
- [MAVROS时间转换](https://raw.githubusercontent.com/mavlink/mavros/1.20.1/mavros/src/lib/uas_timesync.cpp)：PASSTHROUGH与offset行为。
- [MAVROS时钟源](https://raw.githubusercontent.com/mavlink/mavros/1.20.1/mavros/src/plugins/sys_time.cpp)：handle_system_time发布Unix时间，相关参数默认值。
- [MAVROS位置拼接](https://raw.githubusercontent.com/mavlink/mavros/1.20.1/mavros/src/plugins/local_position.cpp)：handle_local_position_ned读取缓存姿态。

上游源码本轮只作在线静态核对，未安装MAVROS；将来需核对实际包与上游对应关系。

## 10. 执行补充：2026-09-12 SIM-00A

上述09-11缺项与限制保留为方案时点记录。SIM-00A现已完成依赖准备和独立构建，
具体版本、命令及资产见[BUILD_SIM00A](../simulation/BUILD_SIM00A.md)，
验证见[EXP-20260912-001](../experiments/2026-09-12-sim00a-build.md)。

JSBSim开发包与7个APT包解包到.runtime/deps，EGM96-5也使用项目前缀；系统dpkg
安装状态保持原样。独立PX4及桥接构建成功，实际编译器为GCC/G++ 9.4.0；JSBSim
使用libJSBSim.a，桥接显式使用ROS包内include/mavlink/v2.0头文件。
两项程序和MAVROS三项二进制/库依赖解析、rospack发现与GeoidEval读取通过。

尚有15条HIL_SENSOR/HIL_GPS字段可能未初始化警告，SIM-00B前审查实际赋值/发送
路径；新增R-11不代替原有时间边界、节奏和旧启动器风险。没有启动仿真或ROS节点，
第7节运行门槛与正式组合冻结条件保持不变。ENV-03保存规则已落地，第二份副本及
完整恢复仍待完成，不能将依赖保存在同一磁盘视为长期备份。

## 11. 执行补充：2026-09-12 SIM-00B前置核查

已沿实际入口分类15条警告，并确认HIL模式开关和消息结构的初始化缺陷。
原构造探针失败，拟议补丁在单独审查副本编译与构造测试通过；详见
[EXP-20260912-002](../experiments/2026-09-12-sim00b-preflight.md)。
SIM00B-INIT-01正式应用范围待确认，原构建副本未变，SIM-00B遥测登记阻塞。
修复后仍需完整重建、消息有效掩码/序列化回归、独立PID/日志/网络装配及120秒
静止遥测。源文件和瞬时端口检查不代替实际资源加载、连接或停止能力验收。

## 12. 执行补充：2026-09-12 SIM-00B完成

用户确认初始化补丁后，项目内副本已按ADR-008修复，新构建/消息回归及实际静止
遥测通过。有效采样窗口120.056秒，IMU 50Hz/6051条、心跳121条，ODOMETRY 2407条
的LOCAL_NED/BODY_FRD来源得到实测。未解锁，本次PID和端口清理通过。
运行入口见[RUN_SIM00B](../simulation/RUN_SIM00B.md)，失败过程与完整边界见
[EXP-20260912-003](../experiments/2026-09-12-sim00b-init-and-smoke.md)。

实际采用ROS master11321、项目依赖前缀.catkin标记及含command的精简MAVROS插件
列表；解析到PX4版本信息。Python common不覆盖的ID8/411仅保留原始报文及MAVROS
framing证据。初步ODOMETRY有限值/帧检查不替代坐标转换、协方差和时间语义验收。
SIM-01、R-10及环境恢复仍未完成，正式Phase 1组合尚未冻结。
