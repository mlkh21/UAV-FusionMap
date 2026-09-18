# EXP-20260912-002：SIM-00B启动前核查与初始化修复提案

日期：2026-09-12；类型：静态调用链检查、无网络构造测试、补丁审查编译。
主责任角色：simulation_engineer；状态：前置核查已完成，SIM-00B遥测阻塞。
用户在SIM-00A收尾后继续任务；本次完成启动条件核查，未启动仿真或ROS节点。

## 1. 结论与边界

构建成功尚不能直接进入有效遥测验收。已确认桥接存在未初始化模式开关和发送消息
结构；原构造函数的对象表示测试失败，拟议初始化补丁在独立审查副本通过。
原PX4、研究仓库及.runtime/src中的构建源码均未改动，SIM-00A二进制保持原样。

可审查补丁：[SIM00B-INIT-01.patch](../simulation/patches/SIM00B-INIT-01.patch)。
状态为proposed；尚未应用到正式构建副本，不把候选测试通过写成修复已部署。

## 2. 源码证据与15条警告分类

基于桥接提交68de2cc63ded9a0d6641d45e9eb3ed2b43454cba、PX4提交
1c8ab2a0d7db2d14a6f320ebd8766b5ffaea28fa和SIM-00A的MAVLink 2025.5.5头文件。
下列桥接路径相对`.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/`。

| 项目 | 实际调用链/证据 | 判断 |
| --- | --- | --- |
| HIL模式开关 | include/mavlink_interface.h:234—235未提供默认值；构造函数未赋值；src/mavlink_interface.cpp:77的Load首先读取hil_mode_，274/300行也用于发送条件 | 已确认初始化缺陷；本机源码内仅有setter定义，独立入口没有调用setter |
| IMU更新标志 | 同一header:240未初始化；JSBSimBridge::Run:174—177在发送前调用UpdateIMU，后者设置true | 当前主循环先赋值，不能把它写成当前路径必然错误；接口初始状态仍应明确 |
| 6个IMU字段警告 | SendSensorMessages:233—243有条件赋值；主循环仅在IMU更新时调用 | 当前入口保证这6字段赋值，编译器独立分析函数时不能推导入口约束 |
| 7个低频字段警告 | mag、baro、差压仅在对应updated时赋值；MAVLink编码读取整个消息结构 | 即使PX4按fields_updated掩码消费，也不应将未初始化的存储传入编码器 |
| HIL_SENSOR.id警告 | sensor_msg声明在src/mavlink_interface.cpp:229，没有为id赋值；协议定义零索引传感器ID | 单传感器候选应明确为0；本版PX4的update_sensors未读取此id，不夸大成已观测的估计器错误 |
| HIL_GPS.yaw警告 | hil_gps_msg声明在:283；随后赋值含id但不含yaw；协议规定yaw=0表示不可用 | 应明确不可用；本版PX4的handle_message_hil_gps未读取yaw，尚无实际错误遥测证据 |

15条警告为6+7+1+1；HIL模式初始化缺陷另由调用链和构造复现确认，不声称警告
本身已涵盖所有缺陷。检查范围是当前独立SITL入口，未完成桥接所有串口/HIL路径审计。
32位微秒范围、节奏计算仍属R-10，修复本初始化问题不会关闭它们。

## 3. 无仿真的RED/GREEN证据

产物目录为`.runtime/logs/sim00b-preflight/`，测试未调用Load、网络发送、飞控或ROS。

构造探针对齐分配对象存储，分别预填0x00和0xA5，再调用实际MavlinkInterface构造
函数。通过unsigned char读取3个bool成员的对象表示，避免将未初始化bool转换为值。
测试使用GCC的-fno-access-control访问私有成员；不修改生产header的访问权限。
探针在独立短进程中退出，没有调用会关闭文件描述符的生产析构函数。

原始对象来自SIM-00A实际编译的mavlink_interface.cpp.o，实际结果：

```text
prefill=00 hil_mode=00 hil_state_level=00 imu_updated=00
prefill=a5 hil_mode=a5 hil_state_level=a5 imu_updated=a5
exit=1
```

候选补丁仅应用到日志目录中的review审查副本，重新编译该翻译单元后重跑同一探针：

```text
prefill=00 hil_mode=00 hil_state_level=00 imu_updated=00
prefill=a5 hil_mode=00 hil_state_level=00 imu_updated=00
exit=0
```

候选编译使用GCC 9.4.0、原构建的C++14/O2及相同依赖头文件，额外将
maybe-uninitialized升级为错误；退出0，warning计数0。packed-member警告开关沿用
原构建，未用关闭未初始化警告的方法通过。git apply --check对正式副本通过。

这证明候选构造初态确定且相关翻译单元可编译，尚未验证完整桥接重建、运行消息
编码/解码、MAVROS连接或120秒有效遥测。补丁获准后需要这些检查。

| 持久工作证据（相对本仓库根） | 内容 |
| --- | --- |
| .runtime/logs/sim00b-preflight/constructor_probe.cpp | 构造测试源文件 |
| .runtime/logs/sim00b-preflight/constructor-original.json | 原始对象测试输出与退出码 |
| .runtime/logs/sim00b-preflight/constructor-candidate.json | 候选探针编译命令、输出与退出码 |
| .runtime/logs/sim00b-preflight/candidate-compile-command.json、candidate-compile.log | 候选翻译单元命令与编译结果 |
| .runtime/logs/sim00b-preflight/review/ | 仅用于提案验证的两个源码文件及对象文件 |
| .runtime/logs/sim00b-preflight/final-check.json | 最终文档、补丁和原源码保护核查 |

## 4. 其他启动条件

- 独立入口main.cpp按rascal查找configs/rascal.xml，-s指定scene/LSZH.xml，HEADLESS=1
  关闭FlightGear输出。配置和场景XML存在，场景初始速度vt=0。
- Rascal110-JSBSim.xml引用的电机和18x8螺旋桨文件存在于模型自身Engines目录。
  桥接根没有Engines目录不是充分的资源缺失证据；实际JSBSim加载仍待运行验证。
- PX4存在1033_rascal配置，新build/etc存在；instance 0的模拟器TCP4560、MAVROS
  UDP14540/14580及其他默认UDP端口已按启动脚本核对。
- 沙箱内ss因netlink权限失败；获准在沙箱外只读ss -lntu核查，当时未见TCP4560、
  TCP11311或UDP14540/14580/18570/14280/13030监听。此结果是瞬时清单，正式启动前
  必须重查并在本次bind失败时停止，不能保证未来无竞争。
- 桥接仍绑定INADDR_ANY；独立网络范围、ROS master隔离、按本次PID管理、完整日志
  和停止上限需在启动装配中落实。尚未建立或运行装配，不沿用旧pkill启动器。

## 5. 拟议修复范围与验证顺序

SIM00B-INIT-01仅修改桥接副本两个文件的5处声明：

1. header中hil_mode_、hil_state_level_、imu_updated_默认false。
2. cpp中sensor_msg和hil_gps_msg使用值初始化；单传感器id=0、缺失GPS yaw=0；
   未更新字段不设置有效掩码，不把填零解释为真实测量。

正式应用目标仅为本仓库.runtime/src下的桥接副本；不修改/home/zxj/PX4-Autopilot或
4D-Radar-Diffusion。保留原固定提交、补丁文件及原SIM-00A构建，在新的
.runtime/build/jsbsim-bridge-init01目录构建候选；恢复时重新选择保留的旧构建，不删除产物。

获准后顺序为：应用已核对补丁 → 完整重建及链接检查 → 构造与消息有效掩码/序列化
回归 → 准备独立PID/日志与端口装配 → 120秒静止遥测。任一步失败保留证据，不放宽
门槛；不解锁、不起飞，600秒仿真或900秒墙上时间上限仍有效。
时间参数类型、运行节奏、其他HIL/串口行为不混入这份初始化补丁。

这一步从启动核查扩大到第三方依赖源码修复，依据根AGENTS第11.3条第5项，先提交
本方案与可审查补丁再确认；未将用户对SIM-00A构建或SIM-00B核查的授权自动扩展为
修复已完成。SIM-00B登记阻塞，等待本补丁正式应用范围确认。

## 6. 工程变更

本批新增本实验记录和simulation/patches/SIM00B-INIT-01.patch；更新PROJECT_STATUS、
README、DEVELOPMENT_PLAN、DECISION_LOG、EXPERIMENT_LOG及SIMULATION_VALIDATION_PLAN，
分别登记阻塞原因、具体补丁、验证边界和后续任务。未改业务算法或正式第三方副本。
