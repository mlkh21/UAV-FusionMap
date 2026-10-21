# EXP-20261014-012：无硬件条件下PERF-01同帧尾延迟只读复核

- 日期：2026-10-14；主责任角色：Technical Lead；关联：[Phase 1预复核](../docs/PHASE1_EXIT_PREREVIEW_20261014.md)、[开发计划§4.1](../docs/DEVELOPMENT_PLAN.md)。
- 类型：既有开发机ROS fixture报告的离线只读归因；**未启动新ROS、未采集硬件、未修改业务实现**。
- 问题：正式PERF-01因目标机、真实设备时钟和功耗证据缺失而阻塞；计划允许独立分析已闭合样本中的匹配等待/消息承载长尾，不能把此分析写成正式20 ms通过。
- 输入：2026-10-09预登记的70m/s、640×512 IR、2秒、`exact`、同端点探针A-B-B-A四个独立run；A为默认配置，B仅开启`ir_borrow_image`。既有[对照记录](2026-10-09-perf01a-ir-decode-copy.md)已判定B相对改善未达到10%采纳门槛，默认仍关闭。

## 方法和复现

以`bash ros_ws/sim01_env.sh python -B`及`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`只读解析每个run的`perf-report.json`。
逐个核对`passed=true`、`errors=[]`、`segmented.errors=[]`、20条闭合
`segmented.samples`、20个预期拒绝、0意外传输丢失；对**各run自身**
的20条已闭合样本按`sensor_to_occupancy_ns`选最大样本，并从**同一root**
取`segments_ns`中的`pairing_wait_and_build`、`ready_to_encode`及
`bundle_send_to_callback`；单独计数该run超过20ms的样本。
没有合并run计算P99，也没有把不同样本的阶段P99相加。

| 独立run（证据） | 候选 | 最慢Radar root尾号 | 同帧回调→占据 ms | 同帧配对等待/构建 ms | 同帧ready→encode ms | 同帧bundle发送→回调 ms | 该run超过20ms样本 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| [135340693290](../.runtime/runs/perf01a-async-20261009T135340693290/perf-report.json) | A | 34 | 56.068 | 41.591 | 0.085 | 12.782 | 20/20 |
| [135500111920](../.runtime/runs/perf01a-async-20261009T135500111920/perf-report.json) | B | 4 | 45.438 | 23.027 | 0.060 | 20.157 | 20/20 |
| [135643446881](../.runtime/runs/perf01a-async-20261009T135643446881/perf-report.json) | B | 34 | 55.394 | 44.439 | 0.050 | 9.390 | 20/20 |
| [140058588949](../.runtime/runs/perf01a-async-20261009T140058588949/perf-report.json) | A | 20 | 53.332 | 41.912 | 0.104 | 9.852 | 20/20 |

四条短测各自的20个有效样本均超开发机20ms诊断线；此处仅作计数，不把
80条汇总为正式样本或估计置信区间。四个最慢**同帧**的配对等待为
23.027—44.439ms，bundle发送→回调为9.390—20.157ms；该混合区间含排队、
传输、反序列化和调度等候选来源，不可直接归咎某个模块或CPU。最慢帧上的
ready→encode仅0.050—0.104ms；先前另一70m/s run中29.964ms异常未由
这些最慢帧重现，不能宣布其根因已解决。读数为同机、各自原有收据，
原失败/成功目录未覆盖。

补充只读频数（顺序依次为表内A、B、B、A，各run分开统计）：
配对等待大于20ms分别为`4/20、3/20、4/20、4/20`，Bundle发送→回调
大于10ms为`19/20、17/20、19/20、16/20`，回调→占据大于40ms
为`4/20、1/20、5/20、3/20`。这些10/20/40ms分段仅用于
观察频率，并非新增验收阈值；不能推断回调混合区间的网络/CPU归因。

## 下一软件动作和正式门禁

下一次如需开展**新的**短窗软件诊断，应先锁定一个可复现的单一假设和
同口径收据：逐Radar/IR sample_id联接最后必需输入、worker获取锁、
IR及Bundle ROS serialize/deserialize/回调时间，并保持35/50/70m/s单run
分别核账、40 Radar/100 IR传输、20接受/20按原理由拒绝、clock唯一和清理。
有探针与无探针只能各自分析，不能直接作为A/B因果结论；实验方案先确认
后再执行。当前只读结果优先定位同帧等待和Bundle承载，**不是已实施的优化**。

正式PERF-01仍需唯一目标平台、真实Radar/IR配置及设备采样时钟映射、
20ms正式起止点、功耗/温度/内存/丢帧实测和确认的连续窗口。
5ms同步、10ms位姿年龄、40ms严格截止及20ms目标未更动。
`reference_only`仍为预算门禁状态；Phase 1不得因本只读分析关闭。
本次未更改研究仓库或历史记录；恢复无需回退运行产物。
当前未提交的`.gitignore`整目录忽略`experiments/`，本新记录虽存在，
普通`git status`不会列出；本次不更改忽略策略或Git索引，后续版本化
需逐文件审核并另行确认。
