# 执行器未就绪归因与最小补证方案

日期：2026-10-30；版本：v0.1；任务：SIM-FLIGHT-DIAG-DESIGN-02；主责任：simulation_engineer。
状态：已完成（只读归因、具体补证设计）；SW-02B尚未实现或运行。
依据：[SW-02诊断交付](SIM_FLIGHT_SW02_DIAGNOSTICS_20261030.md)、ADR-044、
[EXP-20261030-003](../experiments/2026-10-30-sim-flight-readiness-design.md)。

## 1. 当前结论

现有证据只能确认当前1s诊断没有执行器回包，不能确认链路具体停在哪个PX4内部环节。
已排除“宿主完全未发送HIL”与“缺失被填成执行器零包”：保存字节中正常250个、断连接126个HIL_SENSOR，
CRC与原始时间可解码，0个HIL_ACTUATOR_CONTROLS；收据has_actuator=false/requested=null。
这不能证明PX4内部每条IMU均已积分或控制器已更新。

本轮进一步确认两个约束：GPS不是倾角/姿态初始化的无条件前置；1s窗口也不是完整初始化验收。
EKF初始化先累积磁场/气压和积分IMU，倾角初始化检查滤波后的加速度/角速度，
姿态有效还要求tilt_align；多实例选择器另作旧样本拒绝。
后续固定翼控制、PWM、HIL发送各有自己的更新/模式/等待条件，需补当前run内部证据。

## 2. 当前运行的离线证据

本轮不启动新FDM/PX4/ROS/Gazebo，只重新解码原SW-02最终两组wire。
原始数据及完整统计见[wire-audit.json](../.runtime/runs/flight-diag-design02-20261030T011728825531/wire-audit.json)。

| 量 | normal | disconnect | 可解释范围 |
| --- | --- | --- | --- |
| HIL_SENSOR | 250，0..996000us | 126，0..500000us | 发送端原始wire，非PX4内部积分记录 |
| HIL_GPS / HIL执行器 | 0 / 0 | 0 / 0 | 该窗内缺失，不代表零值或armed=false |
| RX | 各1条COMMAND_LONG与HEARTBEAT | 同左 | COMMAND_LONG是PX4请求115消息的511命令，非本仓控制下发 |
| 瞬时加速度模长 | 约0..52.2385m/s² | 同左 | 只描述输入，不能把瞬时值代替EKF低通状态 |
| 瞬时角速度最大值 | .893392rad/s | 同左 | 不是内部gyro_lpf或稳定飞行结论 |
| 同时落入.8g..1.2g、≤15°/s的瞬时样本 | 143个，首428000us | 19个，首428000us | 比较源码数值范围，不是倾角门已通过；后续窗口分别仅568/72ms |
| 既有ULog | 127176字节 | 96011字节 | 文件存在；本轮未解码，不由文件名/大小推断topic已发布 |

PX4日志中首time_usec=0对应timestamp_sample=0错误保留，不改戳。
未安装pyulog；本地PX4自带工具依赖该库，并会在输入旁写分析产物，故本轮不直接运行它。
logger存在降采样、optional topic、较晚启动等限制；日志缺topic即使未来解码也不能独自证明“从未发布”。

## 3. 真实链路与30项源码核验

本轮冻结[32份源文本](../.runtime/runs/flight-diag-design02-20261030T011728825531/source-evidence.json)，
[30项逐条核验](../.runtime/runs/flight-diag-design02-20261030T011728825531/source-checks.json)记录准确行号。
下表按链路归并，源码条件与本次运行事实严格分开。

| 环节/源码 | 已核对事实 | 仍缺的当前run证据 |
| --- | --- | --- |
| [HIL接收](../.runtime/src/px4-v1.13.3/src/modules/simulator/simulator_mavlink.cpp#L489) | 原HIL微秒设置CLOCK_MONOTONIC，再update_sensors并推进lockstep组件 | 内部积分IMU的实际时间/设备及积分周期 |
| [EKF输入/输出](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF2.cpp#L505) | IMU更新时setIMUData；PublishAttitude只在attitude_valid时发布 | 各estimator实例有无更新/实际时间 |
| [attitude_valid](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/estimator_interface.h#L123) | 四元数有限且tilt_align；不是要求首GPS已收到 | tilt_align真实值，不能由源码直接填false |
| [initialiseFilter](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/ekf.cpp#L125) | 积分dt有效，磁场/气压计数足够，再initialiseTilt；初始使用baro | delayed/filtered数据、缓冲状态及有效高度来源 |
| [initialiseTilt](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/ekf.cpp#L227) | 滤波加速度.8g..1.2g、角速度≤15°/s；g=9.80665 | 当前低通值，wire瞬时检查不能替代 |
| [tilt_align](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF/control.cpp#L52) | 滚转/俯仰误差方差和降到3°对应界才置位 | 当前收敛状态与故障标志 |
| [EKF选择器](../.runtime/src/px4-v1.13.3/src/modules/ekf2/EKF2Selector.cpp#L366) | 选中estimator_attitude再发布vehicle_attitude；重复sample或超过10ms的旧姿态不发布 | 实际primary、各实例更新时间及selected姿态 |
| [固定翼控制](../.runtime/src/px4-v1.13.3/src/modules/fw_att_control/FixedwingAttitudeControl.cpp#L284) | 只有新姿态才Run主体，至少rates/attitude/manual模式之一才发布controls_0 | 当前模式/controls时间；不能凭启动完成推断 |
| [PWM/混控](../.runtime/src/px4-v1.13.3/src/drivers/pwm_out_sim/PWMSim.cpp#L93)及[输出](../.runtime/src/px4-v1.13.3/src/lib/mixer_module/mixer_module.cpp#L1009) | 需控制组更新才返回true；随后发布实际actuator_outputs | runtime SYS_CTRL_ALLOC及输出topic实例0 |
| [发送线程](../.runtime/src/px4-v1.13.3/src/modules/simulator/simulator_mavlink.cpp#L721) | legacy订actuator_outputs实例0，dynamic订actuator_outputs_sim；需输出更新、lockstep等待及timestamp>0 | 输出已产生时发送是否被等待阻断 |
| [GPS](../.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/src/sensor_gps_plugin.cpp#L49)及[updated](../.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/src/sensor_plugin.cpp#L56) | 默认1Hz、dt>1/rate；最后发送源状态.996s，窗口内无首GPS符合源码 | 该事实不证明无GPS是唯一/必要阻塞 |
| [listener](../.runtime/src/px4-v1.13.3/src/systemcmds/topic_listener/listener_main.cpp#L60) | instance未指定且n=1走现值快照，遍历已有实例；无实例打印never published | 当前run实际stdout/返回码，不能拿历史示例代替 |
| [listener_copy](../.runtime/src/px4-v1.13.3/src/systemcmds/topic_listener/topic_listener.hpp#L56) | 复制上限512字节；当前快照分支未统一检查copy返回值 | 有TOPIC标题但无字段应判parse_error，不能判正常或全零 |
| [POSIX客户端](../.runtime/src/px4-v1.13.3/platforms/posix/src/px4/common/main.cpp#L143)及[传输](../.runtime/src/px4-v1.13.3/platforms/posix/src/px4/common/px4_daemon/client.cpp#L65) | px4-前缀程序通过AF_UNIX连指定instance，--instance参数须在前 | 本次进程与daemon socket所有权；路径存在不够 |
| [socket命名](../.runtime/src/px4-v1.13.3/platforms/posix/src/px4/common/px4_daemon/sock_protocol.cpp#L44) | instance0使用/tmp/px4-sock-0 | 禁止向其他会话daemon发送查询 |
| [logger](../.runtime/src/px4-v1.13.3/src/modules/logger/logged_topics.cpp#L50)及[已有ULog工具](../.runtime/src/px4-v1.13.3/Tools/ecl_ekf/process_logdata_ekf.py#L11) | 默认topic可能降采样/optional；官方仓内工具用pyulog | 不能绕过缺依赖自行造解析器或覆盖旧日志 |

固定翼主链因此为：HIL→内部IMU→EKF/选择器→vehicle_attitude→controls_0→PWM/outputs实例0→lockstep/send→实际回包。
这是依赖图，不等于已经定位到单一故障点。现有wire没有足够信息继续把原因缩小到具体节点。

## 4. 直接下一工作包：SIM-FLIGHT-SW-02B

状态：计划；主责任simulation_engineer；目标是补当前run的内部观测，不改变控制/采样能力。
保持新身份、同一FDM、ground IC、≤250步/1s、bootstrap5s墙钟和所有原停止界。
只允许显式--uorb-probe正常用例；不得与disconnect混用。默认旧入口/阶段runner行为保持。
不新增依赖、修改PX4源码/构建/参数或增加v2/40s运行；不发heartbeat/arm/manual/模式/参数写。

拟改动：simulation内新增私有flight_probe_contract作固定查询/观测校验；
ros_ws内新增sim_flight_uorb_probe薄包装，调用现有px4-listener/px4-param；
sim_flight_diagnostic_run仅显式接入检查点；tests新增字面量预期、坏输入/超时/隔离及实际收据审计。
旧消息、profile、C++宿主/桥接和地图/应用模块不改。构建仍在.runtime/ros；无新ROS节点/接口。

### 4.1 固定查询与字段

现有bin/px4-listener、bin/px4-param均为同目录px4的已有符号链接，本轮只核对存在，未执行查询。
计划命令形状固定为以下argv，禁止自由命令、shell字符串、-i/-r或n>1：

```text
<existing-bin>/px4-listener --instance 0 <whitelisted-topic> -n 1
<existing-bin>/px4-param --instance 0 show <whitelisted-parameter>
```

listener不传-i是必要条件：显式instance即使n=1也走等待更新分支，在暂停源时可能耗尽2s等待。
不传-i的快照保留所有现存实例；不能把某个secondary实例误当primary或无条件只读实例0。

| topic（125/250各一次） | 至少保留/解析字段 | 用途与限制 |
| --- | --- | --- |
| vehicle_imu | timestamp/sample、设备ID、delta_angle/velocity[3]、两个积分dt(us) | 计算积分均值仅作诊断，非EKF低通状态 |
| estimator_status | 时间、control_mode_flags、filter_fault_flags、设备ID | 各实例状态来源，未收到不能填0 |
| estimator_status_flags | 时间、cs_tilt_align/cs_yaw_align/cs_baro_hgt/cs_gps | 判断已报告的初始化状态，不以wire推测 |
| estimator_attitude | 时间/sample、q[4] | 各实例姿态，float文本有打印精度限制 |
| estimator_selector_status | primary_instance、instances_available、设备ID、healthy[9] | primary关联及观测状态，不据健康直接准入控制 |
| vehicle_attitude | 时间/sample、q[4] | 实际被固定翼控制消费的姿态 |
| vehicle_control_mode | 时间、flag_armed、manual/rates/attitude/auto/offboard | 模式只读；flag_armed=true立即停止该observe用例 |
| actuator_controls_0 | 时间/sample、control[8] | 与更新时间核对，不能套作桥接16路 |
| actuator_outputs | 时间、noutputs、output[16]及实例 | 当前profile声明legacy；自然单位/PWM不能直接等同归一化HIL值 |

最后只读SYS_AUTOSTART、SYS_CTRL_ALLOC、SENS_IMU_MODE三项参数：冻结期望1033/0/0，
不符时拒绝该profile，不能静默换用dynamic或单估计器解释。命令严格只有show，禁止set/import/reset。
后续若需要更多参数或锁步内部状态，先依据本包实际缺口提出定向补证，不能预先放开任意命令。

### 4.2 身份、时序与预算

1. 新会话起始保留既有进程/端口冲突拒绝。只跟踪本次spawn的PX4 PID、start_ticks、exe和rootfs。
2. 查询前后核对/tmp/px4-sock-0仍对应/proc/net/unix中的同一socket，内核socket inode在本次PX4 fd中，
   文件身份未换、本次进程仍存活。任何身份冲突先停，不尝试查询别的instance或清理其他会话。
3. 正常完成step125/250后停止发送next，分别读9个topic。125组预算≤400ms；每个客户端≤200ms，
   同时受组剩余时间约束，实际stdout/stderr合计≤32KiB。超时/超限/身份错误停止，不追加下一步。
4. step250宿主按旧硬界自然结束，PX4仍暂存本次会话；读取最终组及三项param后清理。
   最终topic组≤400ms、参数组≤400ms，查询总数固定21次、观测事件≤32、查询文件总量≤8MiB。
5. 组查询计入既有session和bootstrap墙钟；不增加5s容限、隐藏暂停或把等待时间换成源时间。
   250之后无任何Run/新HIL；125时若耗尽既有限额，明确失败，不赶步或改戳。

probe模式明确省略正常诊断的额外6ms监督sleep，保留既有FDM 4ms节拍和10ms读取轮询，
为有界查询留出墙钟预算；默认normal仍保持原等待。实际墙钟必须记录，不承诺实时倍率或放宽期限。

查询过程用私有sim_flight_uorb_snapshot.v1记录run/clock、checkpoint、query序号/argv、
本次PX4身份/daemon文件证据、最后实际HIL微秒/FDM源时间、开始/结束单调墙钟、返回码与原始输出。
每份≤256KiB、头/配置≤256KiB、身份≤128 UTF-8字节、reason≤256字节、深度≤8、节点≤8192、
列表≤512项；extra/训练监督字段、非有限、坏整数/身份/实例及缺失标志拒绝。
native文本原样保存；只解析固定topic的已知字段，重复/坏数组/缺字段/尺寸错误不当作成功。
stdout打印浮点有精度损失，不能凭其恢复float32位模式；严格执行器对账仍以原MAVLink wire为准。

快照组是先后读取的观察，不是原子同tick事务。逐份保留原始topic时间，不统一改成checkpoint时间；
可识别旧样本但不据此创造当前周期绑定。bind仍unverified、control_gate_accepted仍false。

### 4.3 缺失与验收

| 输入/情况 | 预期行为 |
| --- | --- |
| native明确never published且无矛盾数据 | 保留observed=false及原文，值null；不表示字段0、disarmed或free |
| 有TOPIC标题但无完整字段/尺寸错误 | parse_error/incomplete；禁止把exit0当成功 |
| timestamp=0/回退、未知或重复实例、primary无对应样本 | 不作为fresh输入；保留证据并标出缺口 |
| 私有字段/类型/超限/训练标签或命令越白名单 | 编码前拒绝，不调用客户端 |
| 超时/daemon身份变更/PX4死亡/armed=true | 停止next并清理本次所有进程；只杀客户端不等于停止daemon内任务 |
| 看到全部topic但仍无实际执行器包 | 诊断通过不等于控制通过；按下述链路分类交接 |

先保存独立命令/时刻/状态预期，后做严格合同/字节与文本反例测试，再运行一次新normal probe。
实际要求21份有界查询收据（预期缺失允许，不强制每topic都已发布）、wire/同FDM收据及最终清理一致。
查询组若不完整，则该次补证不通过；不以只保存部分有值topic作为完整证据。
受影响飞行/旧运动与全仓轻量回归按影响执行，不重跑无改动的整个旧ROS矩阵充作新能力。

分类规则：积分IMU无有效数据先定位输入；有IMU而tilt/姿态缺失定位初始化段；
已有selected姿态而模式门全关定位模式段；controls有更新但outputs缺失定位PWM/混控段；
outputs实例0已更新而wire无回包定位发送/lockstep段。缺失或不同步时只报告范围，不能宣称唯一根因。
若该1s窗仍不足，先根据实际观测提交新方案，不能自动扩窗或开启SW-03/04。

## 5. 本轮验证与未执行

30项源事实及两组376个HIL_SENSOR离线解码通过；32项既有飞行定向通过，439份源码/配置保持。
只改本方案、中文实验及管理/接口索引；未新增私有snapshot合同代码、客户端或采集入口。
未解码ULog、调用上述PX4客户端、启动新SITL/ROS、重跑全仓935项或实际验证SW-02B。
全仓935项仍是上一轮SW-02结果；本轮的源文本复核不替代运行验收。

## 6. 2026-10-30实施后续

[SW-02B交付](SIM_FLIGHT_SW02B_PROBE_20261030.md)已实现本方案私有合同/有界客户端与显式入口，
但实际21查询未通过：第二次step125读到三组积分IMU，第二条estimator_status只有六个实例标题。
按4.3节原规则严格拒绝，保留原文并停止清理；没有将其当never published、全零或有效状态。
49飞行/84运动/952全仓及旧两诊断/真实线格式兼容通过，只证明软件回归子范围。
下一项DIAG-DESIGN-03先针对实际空实例设计独立诊断事件和三态/停止规则；
本方案原验收与失败事实保留，不自动继续同一probe、扩窗或开启控制。
