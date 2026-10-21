# PERF-01-A 独立采样与有界匹配

2026-09-24诊断补充：`perf01a_async_run.py --ir-tcp-nodelay`仅让
IR订阅请求TCPROS `TCP_NODELAY`，默认关闭；A/B/B/A短测未达到
预登记收益门槛，不作为PERF-01验收或默认传输策略。原始数据及
逐样本依据见[EXP-20260924-002](../experiments/2026-09-24-perf01a-ir-transport.md)。

2026-09-26诊断补充：`--match-trace`仅在独立短测启用，向新run的
`matcher-audit.json`附加状态/IR/Radar输入时间、clock及worker锁
记录和决定触发身份；`perf01a_critical_path.py --match-trace`只读关联。
结果及首次严格失败记录见[EXP-20260926-001](../experiments/2026-09-26-perf01a-match-trace.md)。
追踪默认关闭，墙钟持锁不等于CPU耗时，不改变匹配与验收门限。

2026-09-28在同一可选追踪中细分状态、worker和决定发布的墙钟/
线程CPU stage；仅新run附加标量`stages`字段，离线校验锁边界。
短测与限制见[EXP-20260928-001](../experiments/2026-09-28-perf01a-stage-trace.md)；
采样开销未知，不据此宣称性能收益或稳定实时。

2026-09-28追加同一默认关闭追踪的worker睡眠/醒来和锁内同线程CPU
标量，`perf01a_critical_path.py --match-trace`校验锁内非嵌套stage
覆盖与缺口，旧run无此字段时保持原关联方式。三次独立短测功能
通过、P99均超20ms且无跨run重复决定前候选；睡眠与其他线程
持锁可重叠，混合区间不等于纯网络/调度。证据见
[EXP-20260928-004](../experiments/2026-09-28-perf01a-wait-probe.md)。

日期：2026-09-23；主责任：integration_engineer，由Technical Lead集成；
实现协作：sensor_engineer；独立检查：reviewer/tester。
状态：异步链路与运动fixture短场景已验证；20 ms性能及大图恢复仍未达标。

## 1. 运行范围

默认入口为静止功能级Radar/IR与placeholder地图闭环；`--speed-mps 35|50|70`启用
直线运动fixture。独立source只发布唯一`/clock`
及100Hz状态；Radar与IR由两个独立进程生成、延迟发布，sensors匹配节点实际订阅
两路消息和源状态。perception只接收SensorBundle，mapping只接收OccupancyObservation。
消息编码保持既有v0.1，未增加LiDAR、研究模型、PX4控制或新的定位来源。

旧的`perf01a_run.py`保持成对输入对照；新增`perf01a_async_run.py`和
`perf01a_async_suite.py`负责本次异步实验。所有产物使用新的run目录，打开文件使用
排他创建；修改代码和重新运行不重建历史派生报告。

## 2. 时间与选择

参数唯一来源为[perf01a_async.yaml](../configs/perf01a_async.yaml)。采样时间和计划
到达时间为本run仿真纳秒；实际生成、发布、接收和处理时刻为本机monotonic纳秒。
禁止两类时钟直接相减。source每1ms发布clock，不由传感器自行发布或推进公共时间。

- Radar基准20Hz，IR基准50Hz，频率、相位与非负延迟分别配置；注入场景保留其原始采样时间。
- Bundle参考时间保持Radar timestamp。IR可跨Radar复用，身份不变；最近采样优先，
  等距选较早采样，再按sample_id排序。绝对差必须小于等于5ms。
- 匹配窗口截止为Radar采样时间加40ms。截止之后首次收到的Radar和迟到IR不能补救
  已关闭窗口；轮询和发送可能晚于截止，实际数据年龄如实记录，不伪装为40ms。
- 0.5秒单调墙钟等待上限覆盖clock未到、暂停和断流；不通过假造clock推进排空。
- 位姿按原Radar参考时刻选不晚于它的最近有效历史状态，年龄小于等于10ms。
  运动fixture也使用这一历史选择，未实现插值或扫描去畸变；对应平移误差预算为
  35/50/70m/s下0.35/0.50/0.70m。
- `--pairing-policy exact`仅供各流采样时刻唯一的fixture：同刻有效IR和同刻位姿均已
  收到、且排在Radar队首时可立即决定；其他帧仍等40ms，5ms门限和墙钟上限均不变。
  默认`deadline`保留对照。传感器设备流的重复采样时间、未知未来到达需另行评审。
- 正常决定按Radar时间顺序；已处理参考时间之前的迟到Radar明确拒绝，不能倒序更新地图。
  EOF关闭缓存并记录未采用原因，不制造补帧或自由空间。

20Hz的采样时间为`0,50,100,... ms`，零相位50Hz IR为`0,20,40,60,... ms`。
偶数Radar恰有同刻IR，奇数Radar距最近IR为10ms。因此整秒窗口正常配对一半，
另一半按同步门限拒绝。IR相位改为5ms时，各Radar最近距离恰为5ms，可以达到边界匹配。
这两种预期在启动前计算，门限始终为5ms。

## 3. 容量与核账

业务载荷缓存分别有Radar、IR、state容量，状态clock门控继续使用既有有界缓存。
IR和状态按最旧采样时间淘汰；Radar超容量显式拒绝最旧待处理帧。独立生产者的延迟
载荷队列也有容量，避免模拟延迟或调度落后引入无限大图积压。
短run审计账本仅留标量身份、时间和处置，禁止保存图像或bundle载荷；账本另有总容量。

每路分别核对：计划生成、实际生成、发布、实际接收、唯一采用、采用引用次数、未采用、
超时、容量淘汰、主动省略、意外损失。IR复用使引用次数可能大于唯一采用数；多余IR
未采用是正常业务选择，不能归入传输丢帧。

传输损失由发布端sample_id集合与匹配器接收集合之差得出；额外、重复或改写timestamp
都报错。Radar匹配决定再与预登记独立oracle比较；bundle/occupancy/map与采用Radar
身份、时间、数量、顺序对应，地图revision只因成功输入增加。未列出的格子仍unknown。

## 4. 计时与证据

复用PerfEvent/PerfTrace和ResourceSampler：生成至实际接收、配对等待、实际业务数据
年龄、缓存高水位、bundle编码/发送至回调/解码、占位感知、occupancy传输、地图更新及
快照发布。保留逐样本连续分段，独立分位数不相加，发布耗时不重复计入传输混合区间。
CPU以100%=一个逻辑核报告，RSS为活动窗口采样峰值，同时记录采样开销与覆盖进程。

异步入口的`sensor_to_occupancy_ns`从真实Radar回调开始，另列生成至占据时延；历史
成对入口的起点为fixture生成开始，不能直接宣称同口径优化。40ms选择窗口自身增加
等待，本轮为验证异步匹配确定性，20ms诊断独立保留，功能通过不等于性能达标。

每个run保存配置、完整计划、预登记oracle、两路生产审计、匹配器接收/处置/高水位、
事件、下游收据、clock记录、CPU/RSS和最终报告。suite预登记执行顺序并保存所有返回码。
固定随机种子；覆盖正常、相位、抖动、乱序、缺帧、容量溢出和恢复。
静止结果见[EXP-20260922-001](../experiments/2026-09-22-perf01a-async.md)，运动结果见
[EXP-20260923-001](../experiments/2026-09-23-perf01a-motion.md)。运动fixture沿
`world_ned`北向匀速，适配后沿`odom`北向；Radar各采样时刻由两个固定世界障碍物
逆投影生成测量。当前仅命名fixture单位安装外参；无FOV、物理雷达或真实飞行轨迹。
报告按收据点、携带历史变换、地图格子和clock域查询重算；断流期间地图不发新快照，
审计由节点查询`stale_cells()`记录，不是公开stale地图服务。

匹配节点额外记录ROS回调进入到锁获取、回调内业务解码和缓存/发布耗时。
`--wire-profile`可选审计独立IR发布端、匹配端和Bundle感知接收端的ROS实际
serialize/deserialize及回调入口；序列化结束至反序列化开始仍是队列、复制、
传输和调度混合项，不是纯网络。探针本身有成本，只能与相同探针口径对照。
边界格网按实际携带变换后的连续坐标量化，理想世界坐标单独核对运动误差，
不得用容差把邻格当成同格。实测见
[EXP-20260923-002](../experiments/2026-09-23-perf01a-boundary-wire.md)；
大图恢复的拒绝理由严格oracle仍失败，20ms门槛不变。

`finish`前runner还需核对独立话题上真实source clock已覆盖终点、状态全数
发布及门控pending清空；无真实clock覆盖时不得人工排空状态。实际wall/clock
理由差异仅出现在额外诊断中，仍按原预登记oracle标整run失败。验证见
[EXP-20260923-003](../experiments/2026-09-23-perf01a-clock-drain.md)。

2026-10-03增加默认关闭的`--endpoint-probe`诊断开关。启用后，生产审计明确写出
`capture_monotonic_ns=null`、`capture_timestamp_ns=null`和
`capture_clock_status=unavailable`，表示当前fixture没有真实设备采样时钟；不得用
fixture业务timestamp或生成时刻冒充曝光/采样时刻。报告按同一Radar根身份额外列出
Radar回调至occupancy publish调用结束、occupancy回调入口、map update调用结束和
MapSnapshot事件的延迟分位数。四组分位数仅作并列端点诊断，不能互相相加，也不能
替代Technical Lead尚未确认的20ms机载验收起止点。该开关不改变匹配决定、消息字段、
严格拒绝理由、5ms同步门限或20ms目标。

真实传感器物理模拟、运动插值、机载资源、研究模型质量、SIM-01D持续性与完整
PERF-01门槛仍各自待验。

2026-10-16增加默认关闭的`--verify-radar-values` fixture观察器：它从独立原始
`/uav/sensors/radar`收据和`SensorBundle.radar`采用收据按`sample_id`对齐，核对
RadarFrame字段、扫描起止/中点、逐点坐标/功率、Doppler/功率可用性、单位和质量；
仅允许ROS float32的1e-6绝对误差。该观察器不改变生产节点、配对决定或消息合同，
也不把fake Radar的arbitrary power写成物理功率。
