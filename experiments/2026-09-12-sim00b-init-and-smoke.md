# EXP-20260912-003：初始化修复与静止遥测

日期：2026-09-12；主责任角色：simulation_engineer。
类型：已批准补丁应用、源码构建、消息回归、实际仿真联调。
状态：初始化修复、消息回归和SIM-00B静止遥测已通过；SIM-01及Phase 1整体未验收。

## 1. 授权与实施

用户明确“确认”，同意SIM00B-INIT-01应用到本项目桥接副本，重建/回归后继续
120秒静止遥测。修复严格保持2个文件5处初始化声明；原/home/zxj/PX4-Autopilot、
4D-Radar-Diffusion和旧SIM-00A二进制保留，不修改时间参数、运行节奏或算法。

新桥接在.runtime/build/jsbsim-bridge-init01完整构建，配置/构建退出0，warning计数0。
动态库解析无缺失。构造与真实消息编码回归通过：初始标志确定，完整传感器掩码8191，
下一帧仅IMU掩码63；未更新字段不会被标为有效，GPS yaw=0明确不可用，CRC/解码通过。
基线RED及候选GREEN仍见[前置核查](2026-09-12-sim00b-preflight.md)，未覆盖或删去失败证据。

## 2. 运行配置与失败记录

环境和命令见[RUN_SIM00B](../simulation/RUN_SIM00B.md)。独立ROS master11321，
HEADLESS Rascal，PX4 instance 0，MAVROS 1.20.1；原始消息记录到新run目录。
使用固定场景LSZH.xml，不解锁、不起飞；无训练、GPU或研究数据参与。

| run目录（均在.runtime/runs/） | 实际结果 |
| --- | --- |
| sim00b-20260912T123449 | 沙箱socket绑定被拒绝，未启动子进程；随后获准在沙箱外执行同一范围 |
| sim00b-20260912T123503 | PX4与模型启动，MAVROS节点查找失败；确认解包前缀缺少.catkin标记后补齐，真实二进制查找通过 |
| sim00b-20260912T123554 | TCP预检遇Address already in use；只读监听核查无残留监听，为TIME_WAIT处理补充TCP SO_REUSEADDR |
| sim00b-20260912T123621 | 收到连续遥测；精简列表缺command插件导致内部版本查询错误，主动停止本次进程后修正配置 |
| sim00b-20260912T123736 | 上一轮仍在运行，端口11321检查正确拒绝；没有终止其他进程 |
| sim00b-20260912T123817 | 最终配置的完整短测，结果见下一节 |

停止123621时，沙箱内/proc没有看到沙箱外监督进程，因此首次精确匹配未发出信号。
获准在沙箱外匹配本项目唯一监督进程后发送SIGINT，由其清理本次子进程；未使用
按进程名称批量终止。所有失败/中断运行保留manifest及日志，最终配置含command插件。

## 3. 最终结果与验证边界

最终run为sim00b-20260912T123817，telemetry-result.json和manifest.json均报告成功，
recording-audit.json复核通过，cleanup-audit.json确认本次PID退出和已知端口可重新绑定。

| 检查 | 实际结果 |
| --- | --- |
| 有效采样窗口 | 120.056秒仿真时间；观察器135.793秒墙上时间，含清理总计137.739秒 |
| HIGHRES_IMU | 6051条，原始窗口50.0Hz，最大源采样间隔24ms，无重复或回退 |
| HEARTBEAT | 121条，按最近IMU时间复核最大间隔1.004秒，解锁状态0次 |
| ODOMETRY | 2407条，frame_id=1/child_frame_id=12，即LOCAL_NED/BODY_FRD；位置/速度/四元数均有限 |
| 记录完整性 | 线格式消息计数与观察器计数逐ID相同；已知消息独立CRC/解码通过 |
| 未覆盖方言 | 本机Python common不认识ID8的121条及ID411的40条；原字节保留，MAVROS framing通过，未声明独立解码通过 |
| 清理 | 观察器/MAVROS/PX4/roscore退出0，桥接由本次SIGINT停止；已知端口释放，无本次PID残留 |

第一次离线核对误用了bytes而解码器要求bytearray，随后又发现未知消息对象不保留
通常的源ID访问结果；复核脚本改为按实际线格式计数并明确未知方言范围。
早期offline-audit.json保留为未通过的诊断，最终结论以recording-audit.json为准。
此修正只涉及验证器，没有改写原始遥测或观察器计数。

最终MAVROS仍有一条CMD: Unexpected command 520, result 0警告；版本信息已实际返回。
本轮未审查其全部ACK匹配语义，不能声明启动日志无警告。原始MAVLink消息同时记录
接收时刻和协议字节，源时间保持不变；消息计数相符也不证明PX4发送端从未丢帧。
本记录不把静止遥测等同于AircraftState、项目/clock、记录回放或高速飞行验收。

## 4. 文件与产物

本批新增：tests/sim00b_initialization.cpp、tests/check_sim00b_recording.py、simulation/check_sim00b_telemetry.py、
ros_ws/sim00b_smoke.py、ros_ws/launch/sim00b_mavros.launch、simulation/RUN_SIM00B.md
及本实验记录。更新PROJECT_STATUS、README、DEVELOPMENT_PLAN、DECISION_LOG、
EXPERIMENT_LOG、SIMULATION_VALIDATION_PLAN和configs/ENVIRONMENT_INVENTORY，登记实际授权、结果及下一步。
项目依赖前缀新增空.catkin标记；第三方副本两个文件按已批准补丁修改，均在.runtime内。

.runtime/logs/sim00b-init01保存应用前两文件、applied.diff、构建命令/日志及test.json；
各run保存进程命令/PID/退出码、MAVROS配置、原始日志和PX4 ulog。旧实验不覆盖。
收尾检查记录在.runtime/logs/sim00b-init01/final-check.json。

R-10时间范围/节奏、ENV-03异机备份恢复、GPU及真实感知风险仍开放。
