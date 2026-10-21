# EXP-20260929-001：PERF-01 20ms计时边界与目标平台待决清单

日期：2026-09-29；主责任：Technical Lead；状态：只读核查已完成，验收边界待确认。
目的：承接[逐样本成本表](2026-09-28-perf01a-20ms-feasibility.md)，确认
现有20ms诊断到底测量哪一段，以及建立机载验收前还缺哪些时钟和负载证据。
本轮不启动ROS、不修改原始产物、业务代码、配置或公共接口，也不选择单点A/B。

## 来源和方法

只读核对`configs/perf01_budget.yaml`、`docs/PERF01_BUDGET.md`、
`docs/DATA_FORMAT.md`、异步生产/匹配/感知节点、`ros_ws/perf01a_metrics.py`、
`ros_ws/perf01a_async_report.py`及`ros_ws/perf01a_async_run.py`；再检查
`.runtime/runs/perf01a-async-20260928T151320506499/`、
`.runtime/runs/perf01a-async-20260928T151403349988/`、
`.runtime/runs/perf01a-async-20260928T151431140984/`各自的`perf-report.json`。
三条原始run均为70m/s、640x512 IR、normal/exact、seed=17、2秒、
同探针短测；仅复核已有聚合字段，未重跑门禁或生成新运行报告。

## 实际测到的边界

| 量 | 当前实际定义 | 能说明什么 / 不能说明什么 |
| --- | --- | --- |
| 异步`timing_budget_diagnostic` | 每个完整采用样本的`occupancy_ready.monotonic_ns - radar_receive.monotonic_ns`，各run分别求P99，与20ms比较 | Radar**ROS回调入口**到占据**就绪**，包括IR等待与Bundle链路；不含Radar ROS反序列化前、设备采样前/后链路，也不含占据消息发布/感知下游接收。诊断失败不改`report.passed`的严格功能结果。 |
| `generation_to_receive_ns`、`generation_to_occupancy_ns` | fixture生产线程生成开始的单调墙钟，到Radar回调/占据就绪 | 可作同主机fixture额外成本参考；生成开始不是Radar实际采样/曝光，也不等于设备时间戳。 |
| `data_age_ns` | matcher决定时`sim:/run_id`公共clock与Radar业务采样timestamp之差，截断为非负 | 仿真时钟域年龄；不含决定后到占据就绪/消费的墙钟经过，不能直接与上述墙钟延迟相加或代入70m/s位移作为实际观测年龄。 |
| 预算文件 | `max_end_to_end_age_ms: 20`及`max_p99_latency_ms: 20`，另有`max_radar_ir_delta_ms: 5` | 20ms与5ms目标已存在，预算文档要求双时钟及全链采点；但尚未指定两项20ms分别从哪个物理采样参考点到哪个对外可用事件，亦未给跨设备时钟换算误差界。 |

调用链证据：`perf01a_async_producer_node.py:95-118,130-136`在fixture生成时
打墙钟、在消息发布前再打墙钟；`perf01a_async_matcher_node.py:177-209`于
Radar回调入口取墙钟（ROS线反序列化已先发生）；`:216-249`打配对决定、
Bundle编码/发布事件；`perf01a_placeholder_node.py:31-44`在Bundle回调
执行解码和占位，于占据编码/发布**之前**标记`occupancy_ready`。
`perf01a_metrics.py:100-128`按同根身份计算两端差，
`perf01a_async_run.py:329-332`以固定20ms作为开发机诊断，
`perf01a_async_report.py:134-150`额外列fixture生成口径；
`ufm_sensors/perf01a_async.py:233-268`说明`data_age_ns`的时钟域。
历史成对入口另从预算YAML读取阈值，起点也不同，不与异步run混算。

三条原报告的`report.passed=true`、`timing_budget_diagnostic.passed=false`；
异步Radar回调至占据就绪P99各为90.011、47.413、53.940ms，
fixture生成至Radar回调P99各为1.454、0.546、17.239ms。
这些是**各自样本集的独立分位数**，不得互加；同一样本分段结果见
[EXP-20260928-005](2026-09-28-perf01a-20ms-feasibility.md)。
三条run均只支持当前带探针的开发机占位链路，不是机载实测。

## 缺失段与责任边界

| 位置 | 已有证据 | 仍缺的分界 / 可控范围 |
| --- | --- | --- |
| 采样参考点 -> Radar/IR真实回调 | fixture计划业务时间、生成/发布墙钟、IR线序列化/反序列化和回调；Radar回调有收据 | 设备曝光/扫描起止、驱动采样时刻与同一单调时基映射没有实测；fixture生成不能代替物理采样。IR到达混合段含发布、队列/复制/传输/调度及反序列化；仅编码/解码、订阅与生产调度等已命名边界可作为将来候选，未能证明纯网络/调度可控。 |
| 配对就绪 -> Bundle感知回调 | IR、状态/clock、worker锁和CPU账本、Bundle双端线编码/解码；逐样本互斥成本见原表 | 状态/clock需求与严格拒绝理由不能随意取消；Bundle发送后的队列/传输/调度仍混合，线序列化与反序列化可观测但未证明在目标机上的收益；不能按不同样本P99归因或选匹配器单点。 |
| 占据就绪 -> 发布 -> 消费 | 当前有占据编码/发布和地图订阅/更新事件，可单列观测 | 目前20ms诊断终点在**发布之前**。若把“可用”定义成消息被消费或地图发布，必须另列同样本增量并按新口径重测，不能将旧P99当作新口径成绩。 |

## 待确认的验收定义和后续门禁（未执行）

1. **Technical Lead确认两个20ms指标的起止点**：分别指定延迟P99与
   `max_end_to_end_age_ms`的数据年龄基准（Radar扫描/IR曝光的哪一时刻）、
   终点（占据就绪、发布或订阅者收到），以及同步时钟转换/误差界。
   此处只列需确认的选择，**不主张**用较晚起点或较早终点规避目标。
   地图更新20Hz/年龄<=100ms单独计量，不替代感知20ms。
2. **Technical Lead确认实际目标平台与负载**：目前Jetson Orin NX 16GB/25W是
   工程参考估计，不是已定型或实测；Radar频率/点率/时间误差为空，IR镜头、
   触发/时间误差及场景约束仍待绑定。异步fixture是Radar 20Hz、IR 50Hz、
   640x512大图；预算配置中`fixture_frequency_hz: 20`是较早功能级参考，
   不能拿来覆盖本次异步run的IR 50Hz配置。
3. 确认口径和平台后，先预登记跨设备采样时钟对齐、端点标量探针、
   同根样本统计及新目录短测的完整方案，保留原始对照；凡涉及网络或
   Bundle候选优化，须另行预登记**可逆单点**A/B、同探针对照、
   严格oracle/资源/清理门禁及同口径端到端P99采纳阈值。
   未补齐证据前不启动新试验，不改匹配器。

严格拒绝理由、Radar-IR 5ms同步和20ms目标均不放宽。
SIM-01D至少40分钟持续性、目标机资源/功耗和研究模型质量仍分别验收。

验证：核对三条既有`perf-report.json`的字段与生产者/消费者调用链；
检查本记录相对链接和`git diff --check`。未执行新ROS、硬件时钟标定、
机载资源测量、研究模型或SIM-01D长测；上述都是开放风险，不能标成通过。
