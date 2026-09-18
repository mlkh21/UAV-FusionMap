# SIM-00B：独立静止遥测短测

日期：2026-09-12；主责任角色：simulation_engineer。
本入口用于PX4/JSBSim/MAVROS连接与原始遥测检查，不发布AircraftState或项目/clock。
实际结果与失败记录见[EXP-20260912-003](../experiments/2026-09-12-sim00b-init-and-smoke.md)。
当前已通过本机120.056秒静止遥测；长期运行及系统状态/时钟接口尚未验收。

## 1. 前置条件与版本

先完成[SIM-00A](BUILD_SIM00A.md)。用户已确认SIM00B-INIT-01：仅将
[初始化补丁](patches/SIM00B-INIT-01.patch)应用到.runtime/src中的桥接副本。
PX4源提交保持1c8ab2a0d7db2d14a6f320ebd8766b5ffaea28fa；桥接基于
68de2cc63ded9a0d6641d45e9eb3ed2b43454cba加上述补丁，原外部仓库保留。

桥接新构建目录为`.runtime/build/jsbsim-bridge-init01/`，沿用BUILD_SIM00A全部
桥接CMake参数，仅替换-B位置。旧SIM-00A二进制保留，不能再将新副本称为未修改上游。
正式应用与构建日志在`.runtime/logs/sim00b-init01/`，两文件应用前副本在其before目录。

解包式ROS前缀需要空的`.runtime/deps/ros-noetic/opt/ros/noetic/.catkin`标记。
catkin.workspace.get_workspaces依据该标记识别CMAKE_PREFIX_PATH；仅rospack能找到
package.xml不足以证明roslaunch能找到lib/mavros/mavros_node。初始化标记的实际命令：

```bash
touch .runtime/deps/ros-noetic/opt/ros/noetic/.catkin
bash simulation/sim00a_env.sh /usr/bin/python3 -c \
  "import roslib.packages; print(roslib.packages.find_node('mavros', 'mavros_node'))"
```

此标记只写入项目依赖前缀，不改系统/opt/ros或研究环境。完整构建与消息回归通过后
才进入下面运行步骤；不能只创建标记就认为仿真前置条件全部满足。

## 2. 回归检查

[tests/sim00b_initialization.cpp](../tests/sim00b_initialization.cpp)链接真实桥接对象文件，
测试两种内存预填下的构造初态、全传感器到仅IMU更新的有效掩码、消息CRC/解码及
缺失GPS yaw=0。poll/sendto仅在测试链接边界包装，不建立网络连接。
完整编译参数见`.runtime/logs/sim00b-init01/test.json`；已构建的测试可重复执行：

```bash
.runtime/logs/sim00b-init01/initialization_test
```

已验证两个文件5处声明修改、新桥接完整构建和该回归；不包含时间参数类型或节奏修复。

## 3. 运行与产物

从本仓库根，在具备本地socket权限的环境执行：

```bash
bash simulation/sim00a_env.sh /usr/bin/python3 ros_ws/sim00b_smoke.py
```

[装配](../ros_ws/sim00b_smoke.py)每次创建新的`.runtime/runs/sim00b-<日期时间>/`，
保存rootfs、ROS缓存/日志、MAVROS配置快照、各进程stdout/stderr及manifest。
使用ROS master端口11321、桥接TCP4560、MAVROS UDP14540/PX4 UDP14580；其他PX4
默认UDP绑定也做预检。实际端口占用时拒绝启动，不终止已有进程。
TCP预检使用SO_REUSEADDR允许已关闭连接的TIME_WAIT，不用SO_REUSEPORT共享现有监听。

启动过程是ROS master → 原始消息观察器 → HEADLESS Rascal桥接 → PX4 instance 0 →
MAVROS；PX4报告启动完成后配置HIGHRES_IMU 50Hz与ODOMETRY 20Hz流。MAVROS只加载
sys_status、sys_time、command、imu、local_position；command用于内部版本查询，装配
没有解锁、起飞、航点或offboard命令。

桥接仍监听INADDR_ANY，当前运行不是独立网络命名空间。ROS连接配置为127.0.0.1，
PX4日志报告MAVLink仅localhost；不能将此说成所有进程仅绑定回环或可直接部署到机载网。

[观察器](check_sim00b_telemetry.py)动态发现mavros_msgs/Mavlink的from话题，保存原始
报文字节及接收标记，按1/1源系统/组件解析HEARTBEAT与HIGHRES_IMU。采样时间直接
来自协议time_usec，ROS header只作接收记录；这里没有生产系统的时间/坐标适配。

首次有效遥测等待上限60秒墙上时间；取得心跳后记录至少120秒仿真IMU数据。
检查有限数值、源时间不回退、未解锁，额外记录IMU最大采样间隔并要求≤0.5秒。
原始日志用于收尾复核心跳持续性及接收/落盘数量；这不是SIM-01的完整记录回放验收。
收尾由[记录复核脚本](../tests/check_sim00b_recording.py)按线格式核对消息数量与心跳
连续性；以运行目录为参数，首次生成recording-audit.json，存在旧结果时拒绝覆盖。
本机Python common尚未覆盖ID8和411，保留原始字节及MAVROS framing结果，不声称这些
消息已独立解码。目标HEARTBEAT、HIGHRES_IMU和ODOMETRY均已独立检查。

观察器在源仿真时间600秒前停止；监督循环上限890秒墙上时间，留出进程清理时间。
仅向本次进程组发送退出信号，先观察器再其余进程，保留退出码；不使用pkill。
进程提前退出、端口冲突或数据不满足条件时返回失败并保留目录。

## 4. 验证边界与恢复

短测成功只证明本机这一固定版本与配置可完成静止遥测。数据丢失/重置/暂停、长期
运行、坐标转换、地图、真实感知、GPU和高速飞行仍需各自验收。32位微秒参数约35.8
分钟范围及节奏计算R-10仍开放；本脚本不是通过该边界的持续性测试。

恢复使用保留的源提交、补丁、依赖包和原构建；需要撤回候选时选用旧构建并保留失败
记录，不删除本次产物。副本备份与异机重建仍按ENV-03执行。
