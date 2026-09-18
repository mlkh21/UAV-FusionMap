# 本机环境与资产清单

版本：v0.1；核查日期：2026-09-11；主责任角色：simulation_engineer。
关联任务：ENV-01；状态：只读核查已完成，运行版本组合尚未选定或验收。
详细过程见[EXP-20260911-002](../experiments/2026-09-11-environment-inventory.md)。

## 1. 核查结论与适用范围

本机已有Ubuntu 20.04、ROS Noetic/Foxy、PX4 v1.13.3源码与SITL二进制、JSBSim桥接源码。
这些资产可用于制定最小验证方案，但尚不能据此声明PX4—JSBSim—ROS链路可运行。
当前主要缺项是JSBSim开发安装和MAVROS；GPU另有已复现的驱动/库版本不一致。

本清单区分安装元数据、文件存在、环境加载检查和实际运行。核查没有启动ROS节点、
飞行仿真、模型或训练，也没有构建现有catkin工作区、安装依赖或修改系统配置。
硬件为当前开发机事实，不代表无人机机载硬件或性能预算。

路径均为本机绝对路径，其他机器需要重新登记。软件包、提交及资源容量为当日快照，
不能直接作为未来安装锁定文件；正式选择记录到[ADR-P001](../docs/DECISION_LOG.md)。

## 2. ROS双版本与终端选择

用户确认每次启动交互终端手动选择ROS，启动菜单与`/home/zxj/.bashrc`行174—180一致：

| 启动菜单输入 | 加载文件 | 系统 |
| --- | --- | --- |
| 1 | /opt/ros/foxy/setup.bash | ROS 2 Foxy |
| 2 | /opt/ros/noetic/setup.bash | ROS 1 Noetic |

本次工具会话为非交互环境，未选中ROS，ROS_DISTRO等变量未设置；`.bashrc`行6—9
也会在非交互调用时提前返回。这不构成ROS未安装或交互选择机制故障的证据。
保留用户现有选择方式，不修改`.bashrc`、默认版本或Conda初始化。

分别在独立的`bash --noprofile --norc`子进程中去掉继承的ROS/Conda/Python搜索路径，
使用系统PATH、`/usr/bin/python3 -B`及对应的setup.bash进行检查，结果如下：

| 项目 | Noetic子进程 | Foxy子进程 |
| --- | --- | --- |
| setup.bash加载 | 退出码0 | 退出码0 |
| ROS_DISTRO / ROS_VERSION | noetic / 1 | foxy / 2 |
| 系统Python | 3.8.10 | 3.8.10 |
| 命令发现 | roscore、roslaunch、rospack、catkin_make | ros2 |
| Python模块路径发现 | rospy、roslaunch | rclpy |
| 代表组件版本 | roscpp/roslaunch/rosbag 1.17.4 | rclpy 1.0.13、rosbag2 0.3.11 |

模块检查使用路径发现和包元数据，没有启动ROS master、DDS通信或订阅发布。
两个子进程分别加载一个版本，未在同一进程叠加两个ROS环境；结果不等于通信验收。

另有一个与启动菜单不同的旧`switch_ros`函数（`.bashrc`行148—169）：它的数字别名
写为`1=noetic、2=foxy`，当前分支仅打印提示、没有source对应setup文件，并会清除部分
ROS变量。因此本项目的复核说明使用明确发行版名称与setup路径，不把该函数当作
已经验证的切换入口。本次只登记事实，不修复用户的shell配置。

## 3. 操作系统、工具与Python环境

| 项目 | 当前事实 | 证据/边界 |
| --- | --- | --- |
| OS / 内核 | Ubuntu 20.04.6 LTS Focal；Linux 5.15.0-191-generic；x86_64 | /etc/os-release、uname |
| ROS 1安装 | ros-noetic-desktop-full 1.5.0-1focal.20250521.014741 | dpkg及/opt/ros/noetic |
| ROS 2安装 | ros-foxy-desktop 0.9.2-1focal.20230606.053518 | dpkg及/opt/ros/foxy |
| 编译/构建工具 | GCC/G++ 9.3.0、CMake 3.16.3、Ninja 1.10.0 | 软件包元数据；未构建 |
| ROS构建工具 | catkin-tools 0.9.4、colcon-core 0.21.1 | 已安装；不代表已选项目构建体系 |
| 当前工具Python | /home/zxj/anaconda3/bin/python3，3.13.5，Conda base | 当前会话；与系统ROS用的Python分开记录 |
| 系统Python包 | rospkg 1.6.2、catkin-pkg 1.1.1、pymavlink 2.4.49 | /usr/bin/python3元数据；未进行MAVLink连接 |

通过Conda登记文件、conda-meta及site-packages元数据发现以下现有环境，没有导入torch：

| 环境绝对路径 | Python | 相关包快照 | 结论 |
| --- | --- | --- | --- |
| /home/zxj/anaconda3 | 3.13.5 | numpy 2.3.4、scipy 1.16.3；未发现torch/jsbsim元数据 | 当前工具环境；不能据此推断研究依赖缺失 |
| /home/zxj/anaconda3/envs/Radar-Diffusion | 3.8.12 | torch 2.4.1、numpy 1.24.4、rospkg 1.6.0 | 现有研究环境；模型加载与CUDA可用性未验证 |
| /home/zxj/anaconda3/envs/sam2 | 3.10.20 | torch 2.5.1+cu124、numpy 2.2.6 | 独立环境，未纳入系统版本选择 |
| /home/zxj/anaconda3/envs/wifi | 3.10.20 | 未发现本轮选查的torch/jsbsim等包元数据 | 未纳入系统版本选择 |

系统Python及上述环境中未发现本轮查询的jsbsim包元数据。Python包是否存在与C++桥接
所需的JSBSim头文件/库是否存在是两项检查，不能相互替代。

## 4. 已有ROS工作区

`/home/zxj/catkin_ws`已有src、build、devel。其src/CMakeLists.txt链接到
`/opt/ros/noetic/share/catkin/cmake/toplevel.cmake`；build/CMakeCache.txt记录：

- catkin_DIR=/opt/ros/noetic/share/catkin/cmake。
- PYTHON_EXECUTABLE=/usr/bin/python3。
- CATKIN_DEVEL_PREFIX=/home/zxj/catkin_ws/devel。

这证明既有工作区采用过Noetic/catkin配置，未证明当前所有包可以构建或运行。
src包含研究仓库、livox_ros_driver、wpr_simulation等已有项目；本次不构建这个共享
工作区，也不覆盖其build/devel。UAV-FusionMap的ros_ws/src仍是目录占位。
ENV-02需明确项目独立构建和输出位置，再选择可复用的依赖。

## 5. PX4、JSBSim桥接与飞行资产

| 资产 | 位置/版本 | 已证实与未证实 |
| --- | --- | --- |
| PX4源码 | /home/zxj/PX4-Autopilot；v1.13.3 | detached HEAD，工作区干净；未运行 |
| PX4提交 | 1c8ab2a0d7db2d14a6f320ebd8766b5ffaea28fa | Git现场核查 |
| SITL二进制 | /home/zxj/PX4-Autopilot/build/px4_sitl_default/bin/px4 | 47,119,272字节的x86_64 ELF；未证明与当前源码对应或可启动 |
| JSBSim桥接源码 | /home/zxj/PX4-Autopilot/Tools/jsbsim_bridge | 已初始化子模块，干净；提交68de2cc63ded9a0d6641d45e9eb3ed2b43454cba |
| 桥接构建目录 | /home/zxj/PX4-Autopilot/build/px4_sitl_default/build_jsbsim_bridge | 空目录；无本轮可核对的桥接二进制或CMakeCache |
| Rascal固定翼模型 | Tools/jsbsim_bridge/models/Rascal/Rascal110-JSBSim.xml，相对PX4根 | 模型文件存在；模型子模块d0d1db1961549e557885002cf9c3cff40cc27be2 |
| 场景与飞机配置 | scene/LSZH.xml、configs/rascal.xml，均相对桥接根 | 文件存在；未验证飞行行为或Radar/IR场景资产 |

上一表最后一行中两个文件的完整路径分别为
`/home/zxj/PX4-Autopilot/Tools/jsbsim_bridge/scene/LSZH.xml`和
`/home/zxj/PX4-Autopilot/Tools/jsbsim_bridge/configs/rascal.xml`。

桥接源码证据（行号为本次提交快照）：

- [CMakeLists.txt](/home/zxj/PX4-Autopilot/Tools/jsbsim_bridge/CMakeLists.txt)行13—40要求
  FGFDMExec.h及JSBSim库；找不到会报`Could not find JSBSIM`。
- 同文件行87—130以catkin条件构建ROS节点，依赖roscpp、rospy及mavlink。
- [package.xml](/home/zxj/PX4-Autopilot/Tools/jsbsim_bridge/package.xml)行16—26声明catkin和mavros等依赖。
- [px4_jsbsim_bridge.launch](/home/zxj/PX4-Autopilot/Tools/jsbsim_bridge/launch/px4_jsbsim_bridge.launch)
  行17引入MAVROS，行35启动PX4，行38启动jsbsim_bridge_node；文件存在不代表启动可用。
- [JSBSimBridgeRos::statusloopCallback](/home/zxj/PX4-Autopilot/Tools/jsbsim_bridge/src/jsbsim_bridge_ros.cpp)
  行79—80仍为发布仿真状态的TODO。ENV-02必须明确AircraftState来自PX4估计、仿真真值
  或对应协议适配，不能假定此回调已经提供系统状态接口。

本轮未找到的前置条件：

| 项目 | 检查范围与结果 | 影响 |
| --- | --- | --- |
| JSBSim开发安装 | 标准include/lib目录未找到FGFDMExec.h或libJSBSim；ldconfig无记录；JSBSIM_ROOT_DIR未设置；PATH与包元数据未发现JSBSim | 当前桥接C++构建前置条件未满足或位置未登记 |
| MAVROS / ROS mavlink包 | dpkg中ros-*-mavros*与ros-*-mavlink无匹配；两个/opt/ros/share及所查catkin源码包清单未发现 | 现有ROS launch与catkin桥接依赖尚不完整 |

系统已有pymavlink包，PX4也有`src/modules/mavlink/mavlink`头文件子模块，提交
`3b52eac09c2e37325e4bc49cd2667ea37bf1d7d2`。不能把“未发现ROS mavlink包”写成
“完全没有MAVLink”，也不能把这些文件等同于MAVROS安装完成。

缺项结论限于标准安装路径、包元数据、已登记Conda环境和本轮有界目录搜索。
没有穷尽全部磁盘、自定义安装位置或容器环境；找到其他安装时补充位置并复核。

## 6. 开发机算力与GPU问题

| 项目 | 当前事实 | 验证边界 |
| --- | --- | --- |
| CPU | Intel Core i9-14900HX，32个逻辑CPU | lscpu；未跑基准 |
| 内存 | 总计约31 GiB；核查时可用约24 GiB | free -h瞬时值 |
| 磁盘 | 项目所在卷总计约938G，可用约276G，使用率70% | df -h瞬时值；不代表允许占用全部空间 |
| GPU型号 | NVIDIA GeForce RTX 4070 Laptop GPU | /proc/driver/nvidia/gpus/*/information的Model字段；显存未取得 |
| 已加载NVIDIA内核模块 | 580.173.02 | /proc/driver/nvidia/version |
| 已安装驱动包 | nvidia-driver-580 580.178.04-0ubuntu0.20.04.1 | dpkg；安装版本与已加载模块不同 |
| CUDA Toolkit目录 | 11.3、11.6、12.1、12.8 | /usr/local目录及version.json元数据 |
| 当前CUDA目录链接 | /usr/local/cuda → cuda-12.1；nvcc 12.1.105 | 显式执行/usr/local/cuda/bin/nvcc --version；当前PATH未找到nvcc |

实际GPU探测命令：

```bash
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
```

沙箱内退出码9，报告不能与驱动通信；随后获准在沙箱外重复同一只读查询，退出码18：

```text
Failed to initialize NVML: Driver/library version mismatch
NVML library version: 580.178
```

因此GPU当前不可被本轮NVML查询验证，版本不一致已有沙箱外证据，不能只归因于沙箱。
尚未导入torch、测试CUDA计算或测量显存；CUDA目录和nvcc可执行不能证明GPU运行正常。
未执行驱动修复、卸载、升级或重启。此问题阻塞GPU运行验收；CPU上的环境设计和
无模型仿真方案可以继续推进。

## 7. 维护周期与下一项任务

Noetic和Foxy都已结束官方支持，二者并存不解决维护到2027年3月的问题：
Noetic结束日期为2025-05-31，见[ROS官方仓库说明](https://github.com/ros/ros_comm/blob/noetic-devel/README.md)；
Foxy结束日期为2023-06-20，见[ROS官方维护者最终发布公告](https://discourse.ros.org/t/new-packages-for-foxy-fitzroy-2023-06-20/32039)。
来源核查日期：2026-09-11。

现有桥接源代码采用ROS 1/catkin；[PX4 v1.13 JSBSim官方文档](https://docs.px4.io/v1.13/en/simulation/jsbsim)
也要求JSBSim及ROS桥接的MAVROS依赖，并说明其示例测试环境为Ubuntu 18.04。
因此Noetic是值得优先评估的现有资产复用候选，但本轮不将其冻结为最终选型。
Foxy需要另行论证对应桥接路线，不能仅切换终端选项就假定ROS 1节点可用。

ENV-02交付应明确候选组合、支持结束后的保存/维护方式、独立构建位置、缺项处理范围、
状态和时钟来源、最小运行步骤、输出位置及验收条件。ENV-01完成表示事实清单完成，
不关闭ADR-P001，也不表示SIM-01或Phase 1运行验收通过。

## 8. 项目依赖补充：2026-09-12 SIM-00A

以上保留为09-11只读核查快照。09-12已按ADR-007在UAV-FusionMap的.runtime中准备
JSBSim 1.1.13开发包、MAVROS 1.20.1及相关7个APT包、EGM96-5数据；仅解包使用，
这些包仍未在系统dpkg中安装。原/opt/ros、Conda、终端选择和共享catkin构建目录保留。

新PX4位于.runtime/build/px4-v1.13.3/bin/px4，新桥接位于
.runtime/build/jsbsim-bridge/jsbsim_bridge，路径均相对UAV-FusionMap根；实际独立
构建通过。原有PX4二进制未替换；新版MAVLink包头文件仅显式提供给新桥接构建。

实际编译器`/usr/bin/gcc`及`g++`均报告9.4.0；前文gcc元包9.3.0信息不是实际
编译器二进制版本，本轮未执行系统升级。系统Python 3.8.10和已有用户目录依赖
版本已登记，完整环境快照/恢复尚未验收。

独立命令入口将ROS包、库、geoid及缓存指向项目目录，并在子进程中选择Noetic；
Foxy父环境/Conda变量隔离、包发现、动态库解析及geoid读取检查通过。MAVROS插件
加载、ROS连接、仿真启动及GPU问题均未验证或修复；桥接15条编译警告仍需审查。
详情见[构建说明](../simulation/BUILD_SIM00A.md)及
[EXP-20260912-001](../experiments/2026-09-12-sim00a-build.md)。

## 9. 实际运行补充：2026-09-12 SIM-00B

用户确认后，项目内桥接副本应用SIM00B-INIT-01，在新目录jsbsim-bridge-init01完整
重建并通过消息回归。新增项目ROS前缀.catkin标记后，roslaunch可发现mavros_node；
含command插件的配置完成内部版本查询。原系统ROS/Conda、原PX4及研究仓库保持原样。
独立ROS master11321下通过120.056秒未解锁静止遥测，所有本次进程退出、已知端口释放。
详见[运行说明](../simulation/RUN_SIM00B.md)及[实测记录](../experiments/2026-09-12-sim00b-init-and-smoke.md)。
这关闭本轮启动依赖核查，不关闭GPU、完整系统接口、长期运行或异机恢复风险。

## 10. 默认Python与状态接口补充：2026-09-14 SIM-01A

用户确认后，后续Python默认Conda Radar-Diffusion，实际解释器为
/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python，3.8.12；Noetic为ROS库来源。
Conda提供empy 3.3.4、catkin_pkg 1.1.0、rospkg 1.6.0、PyYAML 6.0.2、numpy 1.24.4；
pymavlink 2.4.49与netifaces 0.10.4从现有安装复制到.runtime/deps/python-radar，
来源/ABI有清单，未改动原环境，未安装系统软件。rosmaster由项目入口显式使用Conda。

已完成独立catkin、消息往返、44项单元/契约及11项ROS fixture；本机静止联调
605对状态/2302 clock/30.196秒valid通过。实测抽查8个本次Python进程全部使用
Conda环境，正常结束端口/PID清理通过。版本组合正式冻结与异机恢复仍另验。
命令与限制见[RUN_SIM01A](../simulation/RUN_SIM01A.md)，结果见
[EXP-20260914-002](../experiments/2026-09-14-sim01a-implementation.md)。
