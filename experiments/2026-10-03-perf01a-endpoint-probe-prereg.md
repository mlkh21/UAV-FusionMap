# EXP-20261003-001：PERF-01端点与时钟桥接探针预登记

日期：2026-10-03；主责任：integration_engineer；状态：预登记已执行，结果见[实测记录](2026-10-03-perf01a-endpoint-probe.md)。
依据：[大图端到端等待归因表](2026-09-28-perf01a-end-to-end-wait.md)、
[20ms可达性表](2026-09-28-perf01a-20ms-feasibility.md)和
[计时边界核查](2026-09-29-perf01a-budget-boundary.md)。

## 1. 目的和不变项

现有60个采用样本的互斥账本已闭合，但IR实际到达前、状态/clock到决定、
Bundle发送到感知回调等区间仍含队列、复制、调度或未覆盖工作；三次重复短测
也没有跨run重复的单一主导stage。因此补测只增加观察能力，回答“时间发生在
哪个边界”，不预注册优化，不修改匹配器、消息字段、默认参数或验收门槛。

严格拒绝理由、5ms Radar-IR同步门限、40ms决定截止和20ms目标保持不变；
SIM-01D 40分钟持续性、目标机资源/功耗及研究模型质量不属于本试验。

## 2. 预登记探针

所有探针默认关闭，仅在独立新run中启用；只记录小型标量、身份和时钟元数据，
不保存大图，不改变发布顺序和匹配决定。

### P1：输入端点与时钟域标记

- 保留已有Radar/IR `publish`、线序列化、接收反序列化和回调入口事件。
- 对每个输入记录`sample_id`、业务`timestamp`、`clock_id`、生产/发布/回调
  `monotonic_ns`及线程CPU；若生产者没有真实设备采样时刻，明确记录
  `capture_monotonic_ns=null`和`capture_clock_status=unavailable`。
- fixture的`timestamp_ns`、`generated_monotonic_ns`不得被命名为设备曝光或
  物理采样时刻。没有经外部触发或设备协议证明的时钟映射，不计算设备采样到
  回调的数据年龄。
- 若未来输入适配器能提供采样时刻，仅允许在具有来源、偏移和误差界时写入；
  本试验不自行估计跨设备时钟偏移。

### P2：决定端点和混合区间

- 保留Radar回调、采用IR回调、所需state/clock输入完成、
  `sensor_bundle_ready`、worker请求锁/获锁/决定、Bundle编码开始/结束和
  `bundle.publish`调用边界。
- 对现有“就绪到入锁”区间，补齐worker轮询睡眠开始/醒来、请求锁和获锁；
  对state/clock锁内已有stage之外的区间，补齐进入/退出和同线程CPU。
- 输出互斥逐样本表：`R->I`、`I->ready`、`ready->lock_request`、
  `lock_request->lock_acquired`、`lock_acquired->decision`、
  `decision->bundle_encode_start`。跨线程空档保留为`unattributed`，不从CPU差
  反推调度或网络原因。

### P3：下游可用端点

- 保留`bundle_callback`、Bundle解码、`occupancy_ready`、occupancy发布调用、
  `occupancy_callback`、地图更新、`map_snapshot_publish`。
- 同一样本分别报告：
  `Radar callback -> occupancy_ready`（当前开发诊断）；
  `Radar callback -> occupancy publish call`；
  `Radar callback -> occupancy callback`；
  `Radar callback -> map update end`；
  `Radar callback -> map snapshot publish`。
- 不把较早终点替代20ms机载验收终点。上述多端点仅用于并列诊断；真正验收
  端点仍待Technical Lead确认。

## 3. 运行矩阵和门禁

仅在计时边界和运行范围获确认后执行，拟使用未占用端口12065/12066/12067，
每条独立2秒、70m/s、640x512 IR、normal/exact、seed=17，保留
`--wire-profile --match-trace`及当前资源采样。运行前重新检查解释器、端口、
输出目录和进程清理；不覆盖2026-09-28任何目录。

每条run必须同时通过：40 Radar计划、20采用/20严格拒绝；IR/Bundle身份与wire
账本；状态/clock排空；地图事件闭合；资源、端口和进程清理。任一门禁失败，
保留产物但不用于跨run候选判断。

本轮不比较候选收益，不做A/B，不改变默认`tcp_nodelay`、读缓冲、匹配窗口或
Bundle格式。探针完整性要求是：所有采用样本的新增边界可关联、顺序非回退、
互斥分段可重建；P1若没有真实设备采样时钟，只能报告缺失，不能以fixture字段
填补。

## 4. 结果判定

预期输出是逐样本端点表、P1/P2/P3各自缺口计数、wall/CPU对照和未归因区间。
该试验不产生“20ms通过”结论，也不产生“纯网络”“纯调度”或“匹配器瓶颈”
结论。只有在至少两条严格通过run中，同一命名决定前stage在各run最慢三个
采用样本均达到预先约定的墙钟和线程CPU门槛时，才允许另行预登记单点可逆A/B；
若重复的只是混合等待或未覆盖空档，继续补边界证据，不改业务。

若Technical Lead尚未确认实际设备采样时钟和20ms终点，本登记仍只能执行
开发机端点诊断，不能转写为机载验收或数据年龄验收。

验证状态：本记录保存预登记范围；实测结果见[EXP-20261003-001实测记录](2026-10-03-perf01a-endpoint-probe.md)。
探针实现为默认关闭，未修改历史产物；本轮不包含A/B或默认行为变更。
