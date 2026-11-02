# SIM-FLIGHT-SW-02隔离只读诊断与未就绪交接

编号：EXP-20261030-002；日期：2026-10-30；主责任：simulation_engineer。
状态：已完成（诊断软件/实际短窗/断连接子范围）；实际执行器正向关联未就绪，控制门未通过。
文件清单、边界及复现见[交付说明](../docs/SIM_FLIGHT_SW02_DIAGNOSTICS_20261030.md)。

## 1. 范围、环境与独立预期

用户“继续”授权SW-02，沿真实JSBSimBridge::Run→MavlinkInterface→ActuatorPlugin→同FDM Run核对。
缺口是旧poll超时可沿用旧值、没有实际wire/属性/Run结果收据；本轮只加入隔离诊断，不作飞行控制。
分支feature/engineering-initialization，HEAD=d96d4439da1007489c80e7f21b132abff16505bf；
既有大量dirty/未跟踪文件完整保留，没有提交、推送、Hash、安装依赖或修改同级研究仓库。
解释器实际核对为/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python，所有运行经bash ros_ws/sim01_env.sh。
新增十份源码/配置/测试，旧公共消息和入口不改；构建只在.runtime/ros/sim-flight-build/<run>。

新增独立预期先冻结250步/1s、IC、允许TX ID、缺包/终止与控制门关闭，实际运行前保存源码/预期。
最初将ASL误写成419.7m的预期保留在早期run；后按本版本径向定义修正为独立几何检查，
新增geodetic_altitude_m=419.7m作为大地高期望，没有覆盖旧预期或放宽原1微米界。
只复制第三方源并施加唯一上下文适配，原源及旧构建保持；不使用private/public宏。
停用新入口即可退出本次功能，不删除历史目录或修改原Conda环境。

## 2. 实际命令与最终结果

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_flight_stage_run.py --full
```

最终[stage报告](../.runtime/runs/sim-flight-sw02-stage-20261030T005946343885/report.json)在439份相同源码上：

| 用例 | 实际结果 | 判定含义 |
| --- | --- | --- |
| [normal](../.runtime/runs/sim-flight-sw02-normal-20261030T005946760382/manifest.json) | 250条/250次Run成功、1s；250个HIL_SENSOR，RX仅COMMAND_LONG/HEARTBEAT，0个执行器；wire18563字节 | 诊断记录完整，readiness=bootstrap_not_ready，不代表disarmed或控制已接通 |
| [disconnect](../.runtime/runs/sim-flight-sw02-disconnect-20261030T010008127477/manifest.json) | 第125步关闭本次已启动完成的PX4，第126条peer_closed/ran=false，FDM停.5s；wire9387字节 | 实际连接关闭没有被解释为继续bootstrap；不冒充首次执行器之后的真实断流 |
| 私有合同/实际字节 | pymavlink独立CRC/字段核对、原始微秒/16路缺失、JSONL重新读取及初始IC几何通过 | 缺失不填零，不生成matched；没有可供冻结的回包对应关系 |
| 定向 | 新增7项；飞行32/32、旧运动84/84通过 | 合成真实MAVLink字节反例不代替实际PX4正向包 |
| [旧线格式/全仓](../.runtime/runs/sim-motion-sw04a-20261030T010027175743/report.json) | 77组Scene真实genpy、36公共往返/18源转换；935/935全仓通过，41.694s | 未重跑旧ROS/Gazebo完整矩阵、模型或正式PERF |
| 清理 | 两例各宿主/PX4退出码0/0及20/0，四个自有PID清理、无forced、相关端口释放 | exit20是断连接宿主的预期终止，不当作控制成功 |

初始实际AGL=.499999998872m、地面419.200000634628m、大地高419.700000636056m、
JSBSim径向ASL=419.702351354286m；独立椭球射线半径检查误差保持1微米界。
原8m坐标注册/旧v1 z>.5门禁不变，没有把ground值送旧Gazebo或发布任何新TF。
发送路径真实解码只有HIL_SENSOR；本仓无主动heartbeat/arm/manual/模式/参数写。
PX4原有启动脚本和收到的PX4启动消息不改，也不把启动成功当作控制器就绪。

## 3. 失败与修正全部保留

| 目录/记录 | 原始失败 | 修正与范围 |
| --- | --- | --- |
| [004540869095构建](../.runtime/runs/sim-flight-sw02-normal-20261030T004540869095/build.log) | 构建成功后，build-only收尾调用socket端口探针被沙箱拒绝；finally中异常导致无manifest | build-only不再探测端口，运行收尾探针异常写manifest；实际socket运行通过工具权限审查，未要求用户重复授权 |
| [初次定向日志](../.runtime/runs/sim-flight-sw02-normal-20261030T004540869095/initial-targeted.log) | 30项中重复适配拒绝测试失败 | 加入已适配标志明确拒绝；未改第三方源或删测试 |
| [004734308706](../.runtime/runs/sim-flight-sw02-normal-20261030T004734308706/manifest.json) | 首实际宿主bind错误、退出-6 | loopback地址被原链二次字节序转换；改为最终sockaddr直接htonl(INADDR_LOOPBACK) |
| [004844811894](../.runtime/runs/sim-flight-sw02-normal-20261030T004844811894/manifest.json) | 已实际完成250步但独立ASL419.7假设失败 | 保存实际ASL/大地高/ECEF/半轴，按径向定义计算；原数值容差不放宽 |
| [005253181298](../.runtime/runs/sim-flight-sw02-normal-20261030T005253181298/manifest.json) | 16ms监督等待叠加轮询超过5s bootstrap，第188条终止、只完成187次Run | 保留实际停止证据；正常观察等待改6ms，5s硬界不变，不放大源窗口 |
| [005509862615](../.runtime/runs/sim-flight-sw02-normal-20261030T005509862615/manifest.json)、[005636442258](../.runtime/runs/sim-flight-sw02-disconnect-20261030T005636442258/manifest.json) | 中间正常/断连接均通过 | 随后补SIGPIPE明确失败处理与统一stage；结论使用最终两例，不混合旧源码收据 |

所有早期实际进程均由本次Processes清理；bind失败宿主自然abort的事实保留，不称全部尝试均为正常退出。
测试中CRC/错误高度/伪控制门反例同时发现检查器文件未关闭的ResourceWarning，已用with关闭，最终定向无该警告。
bootstrap失败是当前限额的有效停止证据，但该早期normal用例判定仍为失败，不追改为通过。

## 4. 未就绪事实、风险与后续

两组最终数据均无真实执行器包，故正向属性写入、mode/armed/flags及当前周期时间关联仍未验证。
收据中初始/前后四属性为真实读回零，requested=null；不是执行器零向量观测或已应用零命令。
正常recording是合法250条前缀，外部terminal记录diagnostic_window_complete，不冒充完整40s录制。
HIL首包原始time_usec=0导致本轮PX4日志出现timestamp_sample=0错误，后续原值仍保留；未通过改戳抹去。
原始HIL字节未发现非有限数。GPS插件默认1Hz且dt>1才首次更新，因此本次窗口没有HIL_GPS；
固定翼控制需新姿态/控制模式，PWM发布需控制更新，HIL发送还需输出与lockstep组件，均为源码条件。
没有当前run内部uORB逐帧证据，尚不能确定唯一未就绪原因；pyulog未安装，本轮不安装或自造ULog解析器。

没有ROS/v2/Gazebo/RViz飞行链、新40s运行、命令、离地/稳定飞行、机载RSS/正式PERF或研究质量结论。
真实DEM与占据融合仍未验收，LiDAR/target/observed_mask不进入在线链，research继续fail-closed。
下一项SIM-FLIGHT-DIAG-DESIGN-02先沿现存收据和源链只读归因、形成最小补证具体方案；
不重复相同短测、不自动扩大窗口或进入SW-03长窗/SW-04控制，也不回到缺真实数据的暂缓任务。
