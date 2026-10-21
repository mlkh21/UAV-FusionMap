# EXP-20260920-003：分段计时与观察器同负载对照

日期：2026-09-20；主责任：Technical Lead。
状态：分段计时、观察器对照与候选复测已完成；20ms目标未达到，PERF-01保持进行中。

## 目的与范围

定位EXP-002中30.376ms感知P99，区分业务处理、消息承载和测试工具开销。
20ms目标保持；完整Phase 1、SIM-01D的40分钟长测、独立Radar/IR时序、机载平台、
35/50/70m/s场景和外部归档均不由本次试验关闭。原失败结果及已披露证据偏差保留。

分支为`feature/engineering-initialization`，在原有未提交PERF-01-A实现上增量修改，
不自动提交。Python通过正式SIM-01入口核对为
`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。

## 方法与观测边界

所有正式run使用full_ir：640×512、327680个32FC1像素、全部0.5；单Radar点，
paired 20Hz，10秒任务/200样本；固定odom稀疏地图、占位感知。每组3次重复，顺序为
full/light、light/full、full/light。无预热排除、无离群样本剔除；P50/P95/P99为nearest-rank。
每run先登记预期计数，排空后校验和清理，仅占用各自独立master端口。

full与light订阅完全相同的六个业务话题和事件话题，接收同样的完整图像并反序列化。
full在IR和bundle各做一次min/max扫描；light只省略扫描，保留图像尺寸/数量，以及
全链身份、run/clock、业务时间、顺序/去重、地图revision/observed、丢帧与拒绝检查。
light不是零开销观察器，也不能提供像素内容校验通过的结论。

使用现有PerfEvent兼容扩展20个可选分段/回调标记；每个正常样本含5个原事件加20个
分段事件。先捕获时间戳，对应业务发布后再批量发送。完整分段集合与故障分支事件数量
独立计算，缺少/重复/倒退/错业务时间均失败。业务时间不参与墙钟差值。

- `infrared_generation`是实际图像生成调用，嵌套在`fixture_generation`内。
- `pairing`是build_sensor_bundle调用，包含其容器复制与上下文构建。
- `*_encode/decode`是业务字典与ROS对象转换，不是独立测量的线格式序列化。
- `*_publish`是实际publish调用，包含同步序列化/入队；其返回不证明接收完成。
- `bundle_send_to_callback`从bundle publish入口到感知回调入口，含序列化、调度、
  队列、传输与反序列化；`occupancy_send_to_callback`同理。不能称为纯网络延迟。
- `perception`与`map_update`分别包围真正的placeholder_infer与local_map.update。

报告另给连续、不重叠的逐样本关键路径和同一P99样本分解。嵌套区间、并行publish与
传输区间不能再次相加，各段独立P99也不能相加。observer回调记录锁等待与锁内工作；
资源仍只测observer进程CPU/RSS，整链资源采样留待后续。

## 基线对照

预登记矩阵：
[manifest](../.runtime/runs/perf01a-compare-20260920T151807230331/manifest.json)、
[结果](../.runtime/runs/perf01a-compare-20260920T151807230331/comparison.json)。

| 重复 | full感知P99 ms | light感知P99 ms | full减light ms |
| --- | ---: | ---: | ---: |
| 1 | 31.640 | 33.895 | -2.255 |
| 2 | 29.179 | 33.297 | -4.117 |
| 3 | 34.084 | 33.965 | +0.119 |

六run均200/200闭合，5000事件，零意外缺图，进程组及master端口清理通过。
每种模式汇总600个样本：

| 模式 | 感知P50/P95/P99 ms | 地图P50/P95/P99 ms | 三run observer CPU秒 |
| --- | --- | --- | --- |
| full | 22.255 / 29.278 / 32.376 | 23.458 / 30.857 / 33.903 | 6.307 / 6.617 / 5.921 |
| light | 23.857 / 31.180 / 33.965 | 25.181 / 32.665 / 35.881 | 4.201 / 4.705 / 4.392 |

full图像回调锁内P50约3.6—3.8ms/次，light约0.007—0.009ms/次。
因此可确认像素扫描消耗观察器CPU，但三组P99差值方向不一致，未证明省略扫描可稳定
降低业务尾延迟；不据此声称统计显著改善。20ms诊断六run均未通过。

完整模式平均关键路径：发送至感知回调11.509ms，图像生成后至配对前7.454ms，
bundle编码0.933ms、解码0.789ms、配对0.767ms、fixture生成0.293ms、感知0.066ms。
轻量模式最大两段分别11.922ms、8.317ms。仅凭这个结果不能把前者全部归因于网络。

以下为64KiB基线各模式600样本的分段P50/P95/P99，单位ms。publish与发送至回调有
重叠，表中分位数不能相加；每行样本数均为600。

| 测量区间 | full P50/P95/P99 | light P50/P95/P99 |
| --- | --- | --- |
| 图像生成 | 0.257 / 0.482 / 0.616 | 0.300 / 0.592 / 0.628 |
| 配对/复制/上下文 | 0.785 / 1.232 / 1.334 | 0.913 / 1.286 / 1.413 |
| IR消息编码 | 0.897 / 1.816 / 2.183 | 1.042 / 2.044 / 2.738 |
| IR publish调用 | 6.904 / 9.010 / 9.623 | 7.494 / 9.219 / 9.925 |
| bundle消息编码 | 0.850 / 1.491 / 2.539 | 0.958 / 1.590 / 2.736 |
| bundle publish调用 | 4.686 / 7.348 / 8.561 | 5.090 / 7.614 / 8.255 |
| bundle发送至感知回调 | 10.847 / 16.902 / 19.339 | 11.166 / 17.341 / 19.789 |
| bundle消息解码 | 0.727 / 1.169 / 1.364 | 0.749 / 1.217 / 1.406 |
| 占位感知 | 0.052 / 0.108 / 0.119 | 0.054 / 0.113 / 0.119 |
| occupancy发送至地图回调 | 1.069 / 1.495 / 1.831 | 1.087 / 1.659 / 1.974 |
| 地图更新 | 0.065 / 0.134 / 0.165 | 0.082 / 0.162 / 0.174 |

例如第一组full的同一个P99样本94，31.640ms由以下连续区间构成：
fixture生成0.209ms、生成后至配对前9.115ms、配对0.912ms、配对后至编码前0.114ms、
bundle编码1.478ms、发送至回调18.517ms、bundle解码1.157ms、感知0.114ms，
其余边界开销合计约0.024ms；完整精度保存在该run的segmented.occupancy_p99_sample。
发送至回调占该尾样本约58.5%；此比例只描述该样本，不是全样本均值或独立分位数之和。

## 最大分段的单变量试调

本机Noetic的`rospy/impl/tcpros_base.py`在接收循环中以buff_size调用socket.recv，
原默认读块为65536字节；一幅IR的纯像素载荷为1310720字节。
仅给大图订阅增加可选`--image-buff-size`，作用于感知bundle订阅及观察器IR/bundle订阅，
队列深度、数据内容和业务算法保持。候选为4194304字节，默认仍65536。
这是对最大混合区间的可逆试调，不表示已证明读块大小是根因。

候选预登记矩阵：
[manifest](../.runtime/runs/perf01a-compare-20260920T152046308668/manifest.json)、
[结果](../.runtime/runs/perf01a-compare-20260920T152046308668/comparison.json)。

| 重复 | full感知P99 ms | light感知P99 ms |
| --- | ---: | ---: |
| 1 | 31.132 | 33.594 |
| 2 | 31.287 | 32.708 |
| 3 | 32.274 | 31.788 |

六run均200/200、5000事件、零意外缺图且清理通过；全部20ms诊断失败。
每模式600样本汇总感知P99：full=32.187ms、light=32.905ms；地图P99分别34.022ms、
34.553ms。对比64KiB基线，改善量仅约0.19ms和1.06ms，低于run间变化，且full第二次
重复由29.179ms变为31.287ms。未证明稳定收益，保留64KiB默认，不把候选标为优化完成。
原有失败诊断、候选和基线均保留，未进一步调整算法或阈值。

## 新增计时探针对照

保持64KiB，关闭20个新增分段，仅保留原五事件、相同回调时间记录和六路业务校验。
预登记[manifest](../.runtime/runs/perf01a-compare-20260920T152340807997/manifest.json)与
[结果](../.runtime/runs/perf01a-compare-20260920T152340807997/comparison.json)。

| 重复 | full感知P99 ms | light感知P99 ms |
| --- | ---: | ---: |
| 1 | 33.006 | 32.447 |
| 2 | 31.835 | 33.161 |
| 3 | 32.368 | 31.787 |

六run均200/200、1000事件、零意外丢失且清理通过，20ms诊断全部失败。
full汇总感知P50/P95/P99=21.641/28.906/33.006ms，light=23.518/29.362/32.447ms；
地图P99分别34.214ms、33.941ms。每run observer CPU秒：full=5.440/6.176/5.537，
light=3.647/4.480/4.079。新增事件会增加观察器CPU工作，不能宣称计时无开销。
关闭新增事件后尾延迟仍处于相同范围，未观察到稳定下降。

限制：三个矩阵顺序执行，各矩阵内AB/BA交替；未控制CPU频率、温度、调度或整机其他负载。
每配置仅3个run，不能把600个帧当作600次独立试验或宣称统计显著。
两类观察器均保留完整反序列化和原事件，尚未隔离零旁路观察条件；结论仅针对增量像素
扫描和分段事件，不能声称已排除测试工具的全部影响。

## 验证与复现

```bash
bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_*.py' -q
bash ros_ws/sim01_env.sh python ros_ws/perf01a_compare.py --duration-s 10 --pairs 3 --port 11500 --label segmented-baseline
bash ros_ws/sim01_env.sh python ros_ws/perf01a_compare.py --duration-s 10 --pairs 3 --port 11510 --label segmented-buffer-candidate --image-buff-size 4194304
bash ros_ws/sim01_env.sh python ros_ws/perf01a_compare.py --duration-s 10 --pairs 3 --port 11520 --label five-event-control --no-segmented-timing
bash ros_ws/sim01_env.sh python ros_ws/perf01a_run.py --duration-s 2 --scenario sync_timeout --observer-mode light --segmented-timing --port 11530
bash ros_ws/sim01_env.sh python ros_ws/perf01a_run.py --duration-s 2 --scenario ir_missing --observer-mode light --segmented-timing --port 11531
bash ros_ws/sim01_env.sh python ros_ws/perf01a_run.py --duration-s 2 --scenario pose_stale --observer-mode light --segmented-timing --port 11532
```

端口必须空闲；上述矩阵串行执行，避免互相制造负载。每次自动创建全新目录，不重建旧
报告。manifest保留运行顺序、命令、平台和解释器；各run包含budget/scenario快照、
events、receipts、perf-report及日志。`perf-report.segmented.samples`可重算每个样本。

最终134/134单元/契约通过，覆盖分段求和、不重复累计publish、缺失/重复/倒退拒绝、
关闭探针的同起点比较、延迟发送和light模式保留身份/数量/时间/图像尺寸检查。
2秒大图轻量计时冒烟40/40、1000事件通过，
[冒烟结果](../.runtime/runs/perf01a-20260920T151744433324/perf-report.json)。
首次沙箱内ROS命令在socket创建处被禁止，未创建run；获沙箱外执行许可后运行上述试验。

三项2秒故障回归都在light+分段模式通过：
[sync_timeout](../.runtime/runs/perf01a-20260920T152515942466/perf-report.json)、
[ir_missing](../.runtime/runs/perf01a-20260920T152520372013/perf-report.json)、
[pose_stale](../.runtime/runs/perf01a-20260920T152525248708/perf-report.json)。
各有40源样本、10个明确拒绝、30次地图更新，事件分别850/820/850，
drop_rate=0.25、unexpected_missing_maps=0，恢复到最后样本且清理通过。
本轮总计22个ROS run：18个正式大图对照、1个冒烟、3个故障回归。
收尾只读重读22份报告和原始事件，事件计数、逐样本关键路径求和及清理记录均一致；
7份涉及文档的135处本地链接通过，`git diff --check`通过。未重写历史运行产物。

## 修改清单与后续

- `ros_ws/src/uav_fusionmap_msgs/src/ufm_ros_contract/perf01a_ros.py`：可关闭、延迟发送的PerfTrace。
- `sensors/ufm_sensors/perf01a_scenarios.py`：可选图像生成调用计时，默认业务行为兼容。
- `ros_ws/src/uav_fusionmap_sensors/scripts/perf01a_sensor_node.py`：生成、配对、编码/发布计时。
- `ros_ws/src/uav_fusionmap_perception/scripts/perf01a_placeholder_node.py`：回调、解码、感知、输出计时及读缓冲参数。
- `ros_ws/src/uav_fusionmap_mapping/scripts/perf01a_map_node.py`：回调、解码、地图更新/快照/编码/发布计时。
- `ros_ws/perf01a_timing.py`：新增逐样本完整性核查、连续关键路径与分位数报告。
- `ros_ws/perf01a_run.py`、`ros_ws/perf01a_validation.py`：full/light、回调开销、读缓冲、分段排空与校验。
- `ros_ws/perf01a_compare.py`：新增预登记AB/BA矩阵、关闭探针控制、所有run与失败诊断保留。
- `tests/test_perf01a_timing.py`：新增6项针对观测语义的回归。
- `docs/DATA_FORMAT.md`、`docs/SENSOR_INTERFACE.md`、`docs/DECISION_LOG.md`：兼容计时语义和运行参数。
- `PROJECT_STATUS.md`、`docs/PERF01_BUDGET.md`、`docs/EXPERIMENT_LOG.md`与本文：状态、结论和证据索引。

恢复/使用旧观测方式无需删除产物：不传`--segmented-timing`，保留默认`--observer-mode full`
和`--image-buff-size 65536`即可使用原五事件和完整像素校验。
后续优先在最大消息承载区间进一步区分真实序列化、反序列化与调度成本，取得明确证据后
才作下一处优化；独立Radar/IR发布、匹配缓存和整链资源采样仍待实施，之后再进入
35/50/70m/s场景。SIM-01D长测及归档边界不变。
