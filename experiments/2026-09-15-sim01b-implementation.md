# EXP-20260915-001：SIM-01B记录与独立回放实施

日期：2026-09-15；主责任：Technical Lead / integration_engineer。
状态：已完成SIM-01B范围验收，LIVE/B1/B2及关闭/清理分别通过；依据：用户确认[SIM-01B方案](../docs/SIM01B_RECORDING_REPLAY_PLAN.md)。
分工：system_architect完成环境与B配置；integration_engineer完成记录/回放工具；
sensor_engineer完成离线验收与反例；simulation_engineer提供运行说明初稿；
Technical Lead完成发布审计、分层launch、缺口修复、实际实验及记录，另由reviewer只读复核。

## 1. 范围与版本

功能分支feature/engineering-initialization，尚无首次提交；未提交/推送。
默认解释器为/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python，Python 3.8.12。
Noetic、PX4 v1.13.3、JSBSim 1.1.13、MAVROS 1.20.1沿用项目内已验收资产。
PX4 commit=1c8ab2a0d7db2d14a6f320ebd8766b5ffaea28fa；
bridge commit=68de2cc63ded9a0d6641d45e9eb3ed2b43454cba，保留既有SIM00B-INIT-01。
本轮不修改研究组件、飞控/bridge、四消息或simulation/sensors纯业务库；未安装依赖。

## 2. 改动及原因

| 文件 | 原因 |
| --- | --- |
| ros_ws/sim01_env.sh、configs/sim01_environment.bash | 隔离任务argv，显式Noetic环境，避免系统Python setup helper |
| configs/sim01b_recording.yaml | 独立记录窗口、安全期限、队列、采样与Master配置 |
| ros_ws/src/uav_fusionmap_msgs/src/ufm_ros_contract/audit.py | 默认关闭的publish调用字节/身份台账、就绪与封存 |
| ros_ws/src/uav_fusionmap_simulation/scripts/state_clock_node.py | 包装层审计与正常关闭锁，源先停且不制造terminal |
| ros_ws/src/uav_fusionmap_sensors/scripts/state_adapter_node.py | 包装层审计、关闭锁和pending_count封存 |
| ros_ws/launch/sim01b_source.launch、sim01b_sensors.launch | 分开两层，LIVE排空和B2仅重算sensors |
| ros_ws/sim01b_runtime.py | 有界串行bag/sidecar、连接监督、独立PID及关闭重读 |
| ros_ws/sim01b_record.py、sim01b_replay.py、sim01b_native_player.py | 独立LIVE/B1/B2、原生真实退出码及EOF/关闭/数据与清理联合验收 |
| tests/sim01b_validation.py、check_sim01b_recording.py、check_sim01b_replay.py | 实际bag重读、身份/字节/真实旋转/全部质量与EOF验收 |
| tests/test_sim01b_recording.py、test_sim01b_publication_audit.py、test_sim01b_runtime.py | 有意义的缺失/错误/落盘/台账/诊断反例 |
| simulation/RUN_SIM01B.md | 复现入口、时间域、关闭流程及验收边界 |
| PROJECT_STATUS.md、README.md、docs/SYSTEM_ARCHITECTURE.md、DEVELOPMENT_PLAN.md、DECISION_LOG.md、EXPERIMENT_LOG.md、SIM01B_RECORDING_REPLAY_PLAN.md及本记录 | 确认、阶段状态、决策与证据索引 |

审计证明publish已返回或入队，不能解释为网络ACK。审计默认关闭，A原参数不启用；
bag记录t为接收单调经过整数纳秒，原timestamp、run、clock、sample、frame及quality保持。

## 3. 前置与RED/GREEN

- 环境help：旧入口实际exit127、usage:: command not found；修复后标准rosbag play --help退出0。
- 9种argv边界（help、空格、空参数、字面特殊字符等）原样传递；禁用user site。
  Conda解释器、5个ROS元变量、5包发现、消息/rosbag/加密模块和播放器动态库通过。
- 增量catkin构建通过，输出只在.runtime/ros；消息生成仍指定Conda解释器。
- 44项既有单元/契约、4项发布审计及21项B验收反例通过。
- reviewer发现WARN中丢帧/身份计数未立即失败：真实DiagnosticArray驱动记录器的
  test_warn_drop_counters_fail_before_end_of_live先RED（4个subtest失败），补即时监督后GREEN。
  PREPARING且无丢帧的WARN仍可等待；共71项单元/契约通过。
- XML-RPC监督查询设置独立1墙秒socket超时，不改变ROS业务socket。正常清理除直接
  子进程外，核对已审计Python PID及start_ticks，避免把PID复用者误认为本次进程。
- 实际ROS fixture：11项通过，run=sim01a-fixture-20260915T065447237521，清理通过。
  首次沙箱socket报Operation not permitted，失败目录与ros-fixture.log保留；权限审查
  通过后用相同项目隔离入口运行，ros-fixture-retry.log留证。没有停止既有进程。

验证日志：.runtime/logs/sim01b-20260915-verification/，含environment.json、catkin-build.log、
existing-44-tests.log、publication-audit-tests.log、all-tests-final.log、runtime-warn-red/green.log、
ros-fixture.log、ros-fixture-retry.log及标准CLI帮助。
源码保护快照在.runtime/logs/sim01b-implementation-20260914T200706416355/；
首次快照探针因隔离PATH找不到rg而失败，后改用os.walk成功，失败目录保留。

## 4. 实际三个会话

| 会话 | 运行目录 | 当前结果 |
| --- | --- | --- |
| LIVE | .runtime/runs/sim01b-live-20260915T072715914616 | 通过；300008001000ns、6003对状态、15794 clock；关闭、重读和清理通过 |
| B1 | .runtime/runs/sim01b-b1-20260915T074556979050 | 通过；全部27800条业务消息逐字节一致，真实退出码/关闭/清理通过，私有clock计数0 |
| B2 | .runtime/runs/sim01b-b2-20260915T075203206120 | 通过；原clock/source完整，全新sensors输出6003条，几何/完整质量通过，关闭重读/清理通过 |

LIVE在产生遥测前完成订阅和真实连接ready，两个审计ready marker均就绪；未发送解锁命令。
只运行一项会话；LIVE记录预热、原MAVLink、clock、两种状态和诊断。B1只播三类业务topic，
B2只播clock与源状态，新sensors使用原run_id，分别用11342/11343新Master。
rate=1，不生成额外clock，不使用暂停/循环/立即/倍速；首消息不得早于真实TCP就绪闸门。

LIVE启动后、任何后续源码修改前补保存54份相关源码/配置/消息/launch及rosmaster入口
至source-snapshot，附文件索引；本地源码快照不等同独立备份或首次Git提交。
最终已分别核对manifest.exit=0、cleanup-audit.passed、writer封存、实际bag重读及validation.passed。
离线checker只证明数据通过，不能单独作为整run成功依据。

LIVE详细结果：窗口T0=15955999000ns、T1=315964000000ns，频率clock=49.999999833Hz、
source/sensor=19.999466614Hz；最大采样间隔24ms/60ms/60ms。记录148608条，其中
raw=120143、clock=15794、source/sensor各6003、diagnostic=665；接收/写入/实际重读一致。
8个被审计Python进程均为Conda，正常清理无强制信号、审计PID无残留、7个已知端口释放。
整会话346.486墙秒，全程没有armed心跳。raw接收15886条IMU与clock15794并不表示无损
语义计数相同；预热及输入关闭尾段有差异，业务发布与接收clock台账逐条一致。

### B1密集clock丢失的根因与修复

首次B1-01=sim01b-b1-20260915T073358229706失败，首10条clock缺308/328ms样本；
失败后正常清理，bag/sidecar/manifest保留。B1-02=sim01b-b1-20260915T073614434948
再次复现，connections-ready证明Python impl及实际TCP协议queue均为1000。
原bag首10条clock在约1.2ms接收经过时间内推进约180ms源钟，形成真实开头burst。

官方ros_comm 1.17.4 [player.cpp](https://raw.githubusercontent.com/ros/ros_comm/1.17.4/tools/rosbag/src/player.cpp)
432及714-717行显示：TimePublisher先无条件注册相对clock、queue=1，不传--clock仅关闭
实际时钟生成；随后bag advertise queue=1000。
[topic_manager.cpp](https://raw.githubusercontent.com/ros/ros_comm/1.17.4/clients/roscpp/src/libros/topic_manager.cpp)
314-332行显示同topic复用第一次Publication；
[transport_subscriber_link.cpp](https://raw.githubusercontent.com/ros/ros_comm/1.17.4/clients/roscpp/src/libros/transport_subscriber_link.cpp)
176-202行显示发送outbox满则丢最旧消息。这解释了首burst丢中间消息，不能通过改rate或删帧豁免。

最小修复只对player子进程设置ROS_NAMESPACE=/sim01b_native：内部相对clock移到私有
名称，bag绝对/clock及其他绝对业务话题保持，并首次采用queue1000。
名称解析见官方[node_handle.cpp](https://raw.githubusercontent.com/ros/ros_comm/1.17.4/clients/roscpp/src/libros/node_handle.cpp)
251-258行。私有clock不启用生成，额外监控若收到其消息即失败；最终须确认计数0。
没有修改系统ROS、消息、历史bag、rate1、采样时间或记录接收时间。B1-03首12条完整
包含308/328ms且字节匹配；整个回放通过与否由最终计数、序列、EOF及重读决定。

另修配置贯通缺口：质量/窗口验收当前使用冻结常量，原load_settings曾接受更严格但
未传至消费者的自定义门槛。针对反例RED后限制该4项必须匹配300秒/40Hz/10Hz/0.5秒，
GREEN通过；更严格未贯通值在启动ROS前拒绝。安全截止仍可提前，端口/namespace可配置。

B1-03完整27800条业务数据的离线复核通过（15794 clock和两种状态各6003），原生log
含正常Done，但整run因EOF期间话题注销先于Python包装进程退出而误报，manifest.exit=1
保留。新增post-failure-data-review.json只记录数据复核，不将历史失败改为成功。
修复后允许已就绪播放器在clock注销时有最多2墙秒完成正常EOF，再核对全部序列和落盘。
另查官方rosbag_main.py的play_cmd仅wait子进程却不传播其退出码，新增Conda exec
入口启动同一原生player，监督器取得真实C++退出码。helper --help退出0，非法option退出1。
B1-04=sim01b-b1-20260915T074556979050完整通过，343.752墙秒；manifest.exit=0、
validation.passed、writer-closed.passed和cleanup-audit.passed均通过，私有clock计数0。
配置反例与最终全部单元/契约73项通过，日志all-tests-final-73.log；纯业务库和A默认行为保持。
B1-04及B2启动后补保存各55份相关源码至source-snapshot，含新增原生exec入口，附索引。

### B2及最终验收

B2=sim01b-b2-20260915T075203206120，345.466墙秒，manifest.exit=0、errors为空。
原15794 clock与6003条source输入精确匹配；全新sensors输出6003条，几何容差、
完整身份/时间/坐标标记和quality均通过。sensors审计正常封存，pending_count=0，
终止锁未触发；writer接收/落盘/实际重读逐话题一致，私有clock计数0。
player、sensors与roscore退出码均为0，未使用强制信号，11343端口释放。

最终检查日志final-validation.json：LIVE/B1/B2联合验收通过，已审计Python PID及
start_ticks复查无本次非僵尸残留；41份Markdown、244处本地链接、12份AGENTS七项
规则及七份必需设计文档检查通过。79份实施前文件无缺失；六份simulation/sensors
业务文件、四份消息及codec共11份受保护文件逐字节不变。原PX4和研究仓库Git状态
与实施前一致。79份快照保存时环境前置已实施，环境入口两文件的原始版本另在
.runtime/logs/sim01b-plan-20260914/before/保留；不能将该快照误说成所有环境修改前基线。

检查方式为既有单元/契约、实际ROS fixture、实际三个会话及封存重读、保护范围
逐字节比较和文档链接检查。状态、ADR-010、计划、架构入口及实验索引已同步。
SIM-01B仅此范围完成；下一项先形成SIM-01C具体故障用例和影响方案，C/D尚未实际运行。

## 5. 风险与边界

异步尾部、跨话题时钟到达差异、队列过期、审计IO及EOF不完整由发布/接收/落盘/回放
逐话题序列、多重身份和字段验收。不能只按总数、集合或bag可打开判成功。
现场源→适配采用独立旋转矩阵，B2保留q/-q等价容差1e-6；完整元数据与quality精确。
没有在MAVROS原始发布端插桩，只核对raw接收/落盘/重读，不声明整原总线无丢失。
当前冻结门槛300秒、40/10Hz和0.5源秒；未贯通的自定义质量/窗口门槛会提前拒绝。
R-10的32位微秒/节奏、ENV-03第二副本与恢复、未知协方差、实机原点、PERF-01和GPU
仍开放。SIM-01C故障整run停止、暂停/倍速、40分钟和高速飞行不属本次验收。
