# EXP-20260918-002：SIM-01D 32位微秒边界修复前置验证

日期：2026-09-18；主责任：simulation_engineer；状态：**前置修复与短测试完成，长测未启动**。

## 1. 范围与授权边界

本次按用户已确认的SIM-01D前置修复范围执行：核对HIL_SENSOR/HIL_GPS时间调用链，修复
bridge内部32位微秒窄化，新增确定性边界测试，在独立目录构建候选并执行短回归。

本次明确未执行：

- ENV-03外部磁盘、另一台主机或对象存储归档；
- 删除、覆盖或重建既有init01/speed01二进制；
- 修改外部`/home/zxj/PX4-Autopilot`、PX4、MAVLink公共协议或研究仓库；
- 启动40分钟SIM-01D连续仿真；
- 修改SIM-01B/C冻结的600秒/900秒/120秒配置上限以绕过门禁。

根仓当前已有用户授权建立的Git提交，但本机仍只有一份工作资产；ENV-03第二副本和恢复
验收保持未完成。本次使用既有`.runtime/logs/sim-speed01-20260916T141935-before/`
中的bridge-existing.diff、speed-source.diff及历史构建证据，不另行复制大型资产。

## 2. 真实调用链与修复

### HIL_SENSOR

`JSBSimBridge::Run()`从`GetSimTime()`取得秒值，在
`.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/src/jsbsim_bridge.cpp`中转换为微秒后
传给`MavlinkInterface::SendSensorMessages`。修复前参数为`int`，在进入MAVLink结构体前
发生32位窄化；MAVLink的HIL_SENSOR字段本身是`uint64_t`。

### HIL_GPS

`SensorGpsPlugin::getGpsFromJSBSim()`将秒值写入`SensorData::Gps::time_utc_usec`。修复前
该中间字段为`int`，随后才写入`mavlink_hil_gps_t.time_usec`，因此HIL_GPS存在独立的
32位窄化链。

本机`INT_MAX=2147483647`，边界为`2147.483647 s`，即约35分47.48秒。

## 3. 修改文件

项目内bridge源码修改：

| 文件 | 修改 |
| --- | --- |
| `.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/include/mavlink_interface.h` | GPS中间时间和`SendSensorMessages`参数改为`uint64_t` |
| `.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/src/mavlink_interface.cpp` | 同步修改函数定义 |
| `.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/src/jsbsim_bridge.cpp` | HIL_SENSOR秒到微秒转换显式为`uint64_t` |
| `.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/src/sensor_gps_plugin.cpp` | HIL_GPS秒到微秒转换显式为`uint64_t` |
| `tests/sim01d_time_boundary.cpp` | 新增HIL_SENSOR/HIL_GPS边界编解码测试 |

当前bridge dirty文件因此为5个：上述4个SIM-01D相关文件中的前3个与已有SIM00B/
SIM-SPEED差异重叠，`sensor_gps_plugin.cpp`为本任务新增差异；既有初始化和倍速修改未被
删除或覆盖。精确历史差异仍在既有SIM-SPEED封存目录，未执行ENV-03归档。

## 4. RED/GREEN测试

边界测试覆盖以下微秒值：

```text
2147483646
2147483647
2147483648
2400000000
```

每个值分别经HIL_SENSOR和HIL_GPS MAVLink编码/解码，要求`time_usec`逐值相等。

### RED

将同一边界测试与旧init01的`mavlink_interface.cpp.o`链接，因旧API仍为`int`而退出1，
形成预期RED；日志：

`.runtime/build/jsbsim-bridge-sim01d/sim01d_time_boundary-red-old-init01.log`

### GREEN

新候选边界测试通过：

`PASS: HIL_SENSOR/HIL_GPS preserve 64-bit boundary timestamps`

SIM00B初始化回归通过：

`PASS: constructor patterns; full/IMU-only masks; payload CRC/decode; GPS unavailable yaw`

SIM-SPEED-01 getter回归通过，0.5/1/2均保持原值。

## 5. 独立构建与依赖

候选输出目录：`.runtime/build/jsbsim-bridge-sim01d/`。

- `jsbsim_bridge`：71,058,920 bytes；配置和13步构建退出0；
- `ldd`：未发现`not found`；
- 既有`.runtime/build/jsbsim-bridge-init01/jsbsim_bridge`和
  `.runtime/build/jsbsim-bridge-speed01/jsbsim_bridge`未覆盖；
- 外部PX4未修改；
- `git diff --check`通过。

正式入口`bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_*.py' -v`
运行全仓Python契约测试，结果为97/97通过。直接调用Conda解释器的首次尝试出现ROS/PYTHONPATH
缺失导入错误，未作为代码结果；正式SIM-01入口重跑已通过。

## 6. 长测启动条件评估

当前**未达到启动SIM-01D长测条件**，原因不是64位修复或短回归失败，而是：

1. 已创建隔离的 `configs/sim01d_continuity.yaml`、`ros_ws/sim01d_record.py` 和
   `tests/check_sim01d_continuity.py`，并通过 `tests/test_sim01d_contract.py` 的2项契约单测；
   真实40分钟连续运行尚未执行，SIM-01B/C的冻结上限不能直接复用或修改绕过；
2. 当前沙箱禁止`ss`和Python socket访问网络命名空间，无法独立确认TCP 4560、PX4/MAVROS
   UDP及ROS Master端口空闲；`ps`未发现相关进程，但不足以替代端口检查；
3. ENV-03独立副本与恢复验收仍未完成，本次按用户要求不执行外部归档；
4. 长测仍需使用上述专用连续性配置、运行器和checker，至少覆盖边界前后窗口、唯一clock、
   源/适配状态跨边界、terminal/armed/reset、重复/回退/超时/溢出和分层清理。

建议后续顺序：在用户确认的单副本风险下，先在具有端口检查能力的正式运行环境中重新核对
进程、端口和候选身份；专用入口短冒烟通过后，才启动一次连续不少于2400源秒、跨越
`2147483647000 ns`并至少延续120源秒的40分钟级测试。

本记录不把源码存在、C++边界GREEN、候选构建或97项Python通过写成SIM-01D长测通过。
