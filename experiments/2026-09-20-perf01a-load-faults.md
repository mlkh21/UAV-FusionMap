# EXP-20260920-002：完整IR载荷与同步失效场景

日期：2026-09-20；主责任：Technical Lead。
状态：六个短时ROS场景功能检查已完成；完整IR载荷20ms时延目标未达到，PERF-01进行中。

## 范围与修改

按用户“继续”实施完整图像负载与时序故障验证；仍在`4bd0c33`之后的工作区开发。
不归档、不修改研究仓库、不启动40分钟SIM-01D或训练。本次为paired fixture，
Radar/IR仍每个源状态生成一对、均20Hz；未实现独立Radar20Hz/IR50Hz异步配对。

- `configs/perf01a_scenarios.yaml`预注册六场景，故障窗口固定序号[10,20)，之后恢复。
- `sensors/ufm_sensors/perf01a_scenarios.py`生成完整尺寸测试图、时间偏移、缺帧及过旧位姿，
  不修改传入state对象，不重写采样时间以掩盖同步错误。
- sensor薄节点复用StateClockGate的100条pending/0.5秒墙钟超时，替代单一latest状态槽。
- `sensors/ufm_sensors/perf01a_fixture.py`对32FC1不可变数值像素独立复制list容器，
  元数据仍深拷贝，避免逐像素递归且保持源图与bundle独立所有权。
- `ros_ws/perf01a_validation.py`、统一run入口按配置独立计算预期样本，校验时间、身份、
  图像尺寸/数量/像素范围、地图revision、拒绝原因与恢复；场景通过和20ms诊断分开报告。
- `ufm_ros_contract/perf01a_ros.py`支持已捕获monotonic起点，纳入IR构造/配对开销；
  不能与EXP-001旧起点直接比较。ROS消息字段未改变，无需重新生成消息。
- 新增`tests/test_perf01a_scenarios.py`与`tests/test_perf01a_clock_buffer.py`，覆盖完整图像
  ROS往返/所有权、5ms边界、失效时地图不更新/老化/恢复，以及两条future状态都能释放。

## RED与修复

首次全尺寸ROS运行
[perf01a-20260920T110419091842](../.runtime/runs/perf01a-20260920T110419091842/perf-report.json)
失败：source40条，下游各39条，丢失参考时间1500000000ns，感知P99=85.654ms。
失败run的events、receipts、报告与日志保留。

单一state槽在状态领先clock且连续到达时覆盖旧状态。定向回归先复现50ms、100ms两条
状态到达后，clock到100ms只释放100ms状态；复用StateClockGate后按顺序释放两条。
大图原先深拷贝327680个float，改为独立容器复制，并验证源图/bundle修改互不影响。

首批复用11421端口的小图运行通过，随后五个命令在bind预检被拒绝，未启动新场景；
复核时无监听或节点残留。批次改为分别使用不同端口，不关闭预检或结束其他进程。

## 最终运行结果

每个场景2秒任务、20Hz、40个源状态，业务timestamp从0至1.95秒。
full_ir每帧640×512共327680个32FC1像素，其余场景2×2；像素均为0.5功能级强度。

| 场景 | 状态/Radar/IR/bundle/occupancy/map | 预期拒绝 | 感知P99 | 功能检查 |
| --- | --- | --- | --- | --- |
| small | 40/40/40/40/40/40 | 0 | 2.532ms | 通过 |
| full_ir | 40/40/40/40/40/40 | 0 | 30.376ms | 通过；20ms诊断失败 |
| sync_boundary：IR落后5ms | 40/40/40/40/40/40 | 0 | 2.776ms | 边界接受，时间保留 |
| sync_timeout：IR落后6ms | 40/40/40/30/30/30 | 10 | 2.314ms | 精确拒绝与恢复 |
| ir_missing | 40/40/30/30/30/30 | 10 | 2.207ms | 精确拒绝与恢复 |
| pose_stale：位姿落后11ms | 40/40/40/30/30/30 | 10 | 2.279ms | 精确拒绝与恢复 |

三类失效分别给出radar_ir_timeout、infrared_unavailable、pose_age_exceeded；
同根样本的多次拒绝只计一次。故障场景drop_rate=0.25是主动注入的10/40，
unexpected_missing_maps=0，不改写成零丢帧。窗口内无新增bundle/occupancy/map证据，
之后恢复至39号样本；六run均无强杀和本次进程组残留，独立master端口关闭。

最终产物（目录均含scenario.json、budget.json、events.json、receipts.json及日志）：

- [small报告](../.runtime/runs/perf01a-20260920T111920432755/perf-report.json)
- [full_ir报告](../.runtime/runs/perf01a-20260920T111925126408/perf-report.json)
- [sync_boundary报告](../.runtime/runs/perf01a-20260920T111930296867/perf-report.json)
- [sync_timeout报告](../.runtime/runs/perf01a-20260920T111935403923/perf-report.json)
- [ir_missing报告](../.runtime/runs/perf01a-20260920T111940540850/perf-report.json)
- [pose_stale报告](../.runtime/runs/perf01a-20260920T111945726297/perf-report.json)

## 复现与限制

```bash
bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_*.py' -q
bash ros_ws/sim01_env.sh python ros_ws/perf01a_run.py --duration-s 2 --scenario full_ir --port 11432
bash ros_ws/sim01_env.sh python ros_ws/perf01a_run.py --duration-s 2 --scenario sync_timeout --port 11434
```

全仓128/128项通过；六run最终功能检查通过。场景短于故障窗口且没有恢复样本时CLI拒绝。
每次新建run、排他创建报告；EXP-001披露的旧报告重建偏差仍保留，未覆盖历史证据。

full_ir感知P99=30.376ms、地图发布P99=31.631ms，仍未达到20ms工程目标。
40样本nearest-rank P99等于最慢样本，不能推断长期尾延迟；该结果包含图像生成、同步、
ROS传输及占位处理，不含真实感知网络。observer逐图检查也占用开发机CPU。
资源仍仅observer自身；整链功耗、机载平台、独立传感器时序和35/50/70m/s未验收。
下一步先细分大图处理/传输耗时，再推进独立Radar/IR发布和匹配缓存、整链资源采样。
