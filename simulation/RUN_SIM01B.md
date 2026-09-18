# SIM-01B：300秒静止记录与独立ROS回放

更新：2026-09-15；源运行审查：simulation_engineer；集成执行：Technical Lead。
状态：已完成SIM-01B范围验收，LIVE/B1/B2及各自关闭、清理均通过。
实施依据：[B方案](../docs/SIM01B_RECORDING_REPLAY_PLAN.md)、
[A运行基线](RUN_SIM01A.md)、[项目状态](../PROJECT_STATUS.md)。

## 1. 本步范围与环境

本步连续完成三个独立会话：LIVE静止记录、B1成品消息原样回放、B2重新计算sensors。
只有三个结果和各自关闭审计都通过，才可将SIM-01B标记完成。状态来自PX4估计，
位姿/速度协方差及confidence继续未知，不加载研究算法、GPU或地图。

所有新增Python经`bash ros_ws/sim01_env.sh python ...`使用Conda Radar-Diffusion；
解释器须为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。不修改原Conda、
系统Noetic/Foxy或终端版本菜单。SIM-00A/B历史命令维持原验证环境。
PX4/JSBSim沿用项目内已验收构建，不修改第三方源或执行旧`Tools/sitl_run.sh`。

## 2. 入口和前置检查

入口为`ros_ws/sim01b_record.py`与`ros_ws/sim01b_replay.py`，从项目根目录执行。
LIVE/B1/B2命令均已实际验证，结果以各自manifest/validation/cleanup-audit为准。
Technical Lead串行监督，不并行启动LIVE/B1/B2。

```bash
bash ros_ws/sim01_env.sh python ros_ws/sim01b_record.py
bash ros_ws/sim01_env.sh python ros_ws/sim01b_replay.py \
  .runtime/runs/sim01b-live-20260915T072715914616 B1
bash ros_ws/sim01_env.sh python ros_ws/sim01b_replay.py \
  .runtime/runs/sim01b-live-20260915T072715914616 B2
```

每次LIVE会生成新目录；回放参数须替换为本次已通过的LIVE，入口会重新验收归档。
独立数据检查，不启动Master或仿真：

```bash
bash ros_ws/sim01_env.sh python tests/check_sim01b_recording.py <LIVE目录>
bash ros_ws/sim01_env.sh python tests/check_sim01b_replay.py <LIVE目录> <回放目录> B1
```

尖括号为需替换参数，B2检查将末尾B1换为B2。离线checker只验数据，整run还需
最终manifest.exit=0、cleanup.passed及writer-closed.passed，不以result.json单独验收。

前置Conda解释器/9种参数边界、Noetic包发现/动态库、增量catkin、73项单元/契约及
11项实际ROS fixture通过；环境检查失败即停止，不静默换回系统Python。
每次创建新run/会话目录，复制实际配置，保留失败运行，不覆盖已有bag或审计文件。

| 会话 | 独立Master | 允许启动的业务链 | 唯一公共clock |
| --- | --- | --- | --- |
| LIVE | 11341 | PX4/JSBSim/MAVROS、simulation、sensors | simulation的有效HIGHRES_IMU采样时间 |
| B1 | 11342 | 无业务节点，仅播放器与比较器 | bag中的原Clock消息 |
| B2 | 11343 | 全新sensors实例，播放器与比较器 | bag中的原Clock消息 |

B1/B2不启动飞控、bridge、MAVROS或simulation；B2不发布历史适配结果，只将其作为
离线期望。禁止额外`--clock`、`--loop`、`--immediate`，首轮固定rate=1。
播放前确认选定话题订阅及唯一clock发布者就绪，不以进程存在替代ready。
仅原生player使用ROS_NAMESPACE=/sim01b_native，内部未启用的相对clock与bag绝对/clock
分开，防止Noetic TimePublisher先注册queue1而覆盖bag的配置队列。监控私有clock，
收到其任何消息即失败；原bag不改名或改时刻。播放器经Conda exec小入口启动，监督器
取得C++真实退出码，避免官方Python命令忽略子进程退出码。正常EOF允许话题先注销，
须在2墙秒内确认正常进程退出，再按5墙秒排空/完整序列检查，不能把注销单独判断流。

## 3. 有效窗口与时间

记录器在产生遥测前完成订阅及writer就绪，保存整个预热。T0为源发布台账首个valid
状态时间；记录器首valid必须与其相同，不能事后跳过缺失首帧挑选成功窗口。T1为
首个源状态满足T1−T0≥300秒的时间，闭区间内源/适配身份及次数必须完整匹配。
clock保留不晚于T0的最后样本及不早于T1的首样本，形成首尾覆盖。

业务采样timestamp、原run_id/clock_id/sample_id保持不变。bag索引明确采用记录经过
时间：`receipt_monotonic_ns - record_start_monotonic_ns`；它不是业务仿真时间。
统一接收入口分配record_seq，串行保存bag/sidecar，回放按记录经过时间调度，禁止
将ROS接收时间或bag索引写回消息。B2用原run_id但全新进程、缓存和身份账本。

| 检查 | 门槛 |
| --- | --- |
| 连续valid采样跨度 | 至少300秒，不含预热 |
| clock | 请求50Hz，实际至少40Hz |
| 源/适配有效状态 | 请求ODOMETRY 20Hz，两种状态各至少10Hz |
| 最大有效采样间隔 | 三类序列各不超过0.5源秒 |
| 身份和时间 | 回退、重复、冲突及未解释缺失为0 |
| 几何与元数据 | 位置/速度/实际旋转误差≤1e−6；q/-q等价；完整质量与非几何字段精确保留 |
| 发布与落盘 | 发布审计、接收、bag重读及回放逐话题序列/身份次数一致 |

频率按`(N−1)/(t_last−t_first)`计算。原始MAVLink只核对记录接收/落盘/重读，不对
未插桩的MAVROS原始发布端声称无丢失。所有门槛均为工程冒烟值，PERF-01高速预算另定。

## 4. 运行与关闭保护

- 保留PREPARING的10源秒稳定观察；准备期估计器reset重计窗口，不发布valid。
  ACTIVE后的reset、任何IMU回退、两路有效源各2墙秒断流均不可恢复旧run继续运行。
- LIVE整run绝对源时间上限600秒，含预热/尾部，同时观察有效原始IMU与clock。
  LIVE/B1/B2各900墙秒上限，启动60墙秒；任一上限先达到即失败停止。
- 不发送解锁、起飞或控制指令；目标源心跳出现armed即失败。端口占用或已有PX4时
  保留占用者并停止本次任务；bridge TCP4560实际绑定INADDR_ANY，不宣称只绑定回环。
- 终止状态、ERROR、队列等待过期/溢出、审计或writer失败、必需子进程意外退出均
  失败停止。节点留活不代表链路有效；不能等看门狗制造terminal来宣布正常完成。

正常关闭分阶段执行：先停止source并封存源/clock审计，sensors、Master和记录器
保持运行；确认源尾部及窗口适配完整、clock覆盖、队列处理后，再停止sensors并
封存审计；随后停止剩余本次仿真输入，记录器排空、封存sidecar、关闭bag并重读。
只有closed/complete及对账通过，才停止记录器和Master。不得同时停两层截断尾部。

排空检查上限5墙秒，不改变业务0.5墙秒等待限制，不以固定sleep替代完成条件。
回放EOF同样等待期望身份/计数、最终clock覆盖及写入完成；缺失则失败，不补造clock。
所有清理只使用本次记录的PID/进程组，禁用按进程名pkill；记录退出码、强制信号与
端口复查，强制kill或未封存审计不能豁免为通过。

## 5. 证据与未验收边界

实际结果及失败记录见[EXP-20260915-001](../experiments/2026-09-15-sim01b-implementation.md)。
LIVE=sim01b-live-20260915T072715914616：300008001000ns窗口、6003对状态、15794 clock，
clock/source/sensor频率约50/20/20Hz，最大采样间隔24/60/60ms；关闭、落盘重读和清理通过。
B1=sim01b-b1-20260915T074556979050，全部27800条业务消息逐字节一致；
B2=sim01b-b2-20260915T075203206120，全新sensors的6003条输出按几何容差、
完整元数据/质量精确验收通过。两项均保留原15794 clock，私有clock计数0。
三个会话均manifest.exit=0，validation、writer-closed及cleanup-audit通过。
B1原生queue1故障两次复现、EOF交接误报一次；项目入口修复后完整复验通过，失败记录保留。
已验收A的参考值为首valid16.059999源秒、clock约0.9076源秒/墙秒；据此估算LIVE
窗口结束约316源秒、采样推进约348墙秒。此估算不代替B运行证据，也不用于放宽截止。

R-10的约35.8分钟微秒边界与节奏疑点保持开放；300秒不等于40分钟持续性验收。
ENV-03第二副本、恢复和版本提交仍有独立工作；项目内产物不等于异机备份。
odom及base_link原点仍为已确认仿真虚拟约定，不证明实机安装外参或场景注册。
暂停/倍速/主动断流整run停止属于SIM-01C，真实飞行、模型质量和机载实时能力均未验收。
