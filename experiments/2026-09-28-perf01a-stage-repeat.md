# EXP-20260928-002: PERF-01-A 大图分段重复诊断（预登记）

日期：2026-09-28；主责任：integration_engineer。目的：复核
[EXP-20260928-001](2026-09-28-perf01a-stage-trace.md) 的单次长尾能否
重复，决定是否有理由选择一个后续 A/B 候选。本轮不改业务代码、默认策略、
5ms 同步门限、40ms 截止、严格双时钟理由 oracle 或 20ms 性能目标。

## 运行和判定（执行前登记）

- 串行运行三次独立 2 秒 ROS 短测，`normal`、70m/s、640x512 IR、
  `exact`、`--wire-profile --match-trace`；配置 `perf01a_async.yaml`
  seed=17，不设置 `--ir-tcp-nodelay`；端口依次 12062、12063、12064。
  每次自动创建 `.runtime/runs/perf01a-async-*`，不复用旧目录；记录
  真实 run_id 和返回码。核对解释器为 Conda Radar-Diffusion。
- 每次预计 40 Radar、20 采用/20 拒绝；严格理由、线格式、地图运动/
  老化、状态/clock 排空、资源和进程/端口清理全部按 runner 原规则判断。
  任一失败即整 run 失败，保留原始产物与失败原因，不把其耗时纳入
  “功能通过 run”的性能样本。若进程/资源错误阻止安全继续，记录中止原因。
- 对所有通过 run 用只读 `perf01a_critical_path.py --match-trace`
  校验接受样本/锁/stage 身份，逐样本报告 Radar 回调至占据的 P99
  和长尾对应 stage 墙钟及同线程 CPU。`decision.emit`包含子阶段，
  不叠加；不同样本的阶段 P99 不叠加；`matcher.finish`不是在线延迟。
- 只有至少两条严格通过的 run，且**同一命名 stage**在至少两条通过
  run 各自的最慢三个采用样本中至少一次耗时 >=10ms 墙钟、
  同阶段 CPU >=10ms，并在该样本的决定前相关锁路径上，才称为
  “重复候选”。若多种阶段满足，只列并列候选，不称唯一瓶颈；
  这只是选择后续单点 A/B 的必要条件，短 run 不证明性能收益。
  长锁未被阶段覆盖、锁争用、调度和 ROS 接收之前的区间单独列为
  未归因，不把 CPU/墙钟之差直接命名为网络时间。

运行入口（每次换端口）：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01a_async_run.py --scenario normal --speed-mps 70 \
  --pairing-policy exact --full-ir --wire-profile --match-trace \
  --duration-s 2 --port 12062
```

验证方式：保留三份独立报告与原始账本，报告真实通过/失败与耗时，
文档链接和 `git diff --check` 核对。无生产代码改动，不靠放宽阈值
恢复；SIM-01D 长测、机载资源和研究模型质量不在本实验范围。

## 实际结果

Conda解释器核对为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。
沙箱内第一次尝试端口12062在创建socket时得到`PermissionError`，
未创建run；获授权后用上述命令依次换端口12062/12063/12064
运行，三次返回码均为0，互不覆盖。原始报告/审计分别为：

| 端口 | 新run目录（相对仓库根） | 严格功能 | Radar回调至占据P99 | 最慢三个采用样本中墙钟与CPU均>=10ms的阶段（尚须满足决定前条件） |
| --- | --- | --- | ---: | --- |
| 12062 | `.runtime/runs/perf01a-async-20260928T104305656559/` | 通过 | 59.749ms | Radar4 `decision.emit`墙钟11.596ms/CPU11.204ms（含Bundle发布子段） |
| 12063 | `.runtime/runs/perf01a-async-20260928T104330190068/` | 通过 | 49.122ms | Radar6 `matcher.advance`墙钟22.755ms/CPU16.964ms |
| 12064 | `.runtime/runs/perf01a-async-20260928T104357039257/` | 通过 | 53.014ms | 无 |

每个run原始`perf-report.json`都为`passed=true`、`errors=[]`，
40 Radar均生成/接收，20采用/20拒绝；IR均100条生成/接收、
无意外传输丢失，wire无错；clock均收到2201条（0..2200ms），
状态各221条收到并发布、pending=0，20个地图运动点核对通过、
地图老化/恢复检查通过。节点/master均退出码0、未强制终止，
进程组已清空且端口关闭。三条P99**全部超过20ms**。

只读调用（三条各执行一次并按原始`matcher-audit.json`同锁关联）：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01a_critical_path.py --match-trace --top 3 \
  .runtime/runs/perf01a-async-20260928T104305656559
```

其余两条将末尾run目录替换。20个采用样本/每run的匹配身份及stage
锁边界验证通过。12063的Radar22 `decision.flush_events`墙钟
15.084ms但线程CPU仅0.225ms，不能归因为计算；12064在拒绝样本
Radar17出现`decision.ready_event`墙钟13.302ms/CPU12.956ms，
不属于采用样本尾部。`matcher.finish`只在EOF后，不能算在线阶段。
尾部仍包含最后输入回调前IR传输/解码、锁外等待、调度和Bundle
接收等混合成本；上表的stage只说明局部CPU/墙钟区间。

**预登记判定：无重复候选。**三条均功能通过，但数值条件下
`decision.emit`与`matcher.advance`各只出现在一条run的最慢三个
采用样本中；且`decision.emit`包括决定后的发布，本身不满足
“决定前”条件。第三条没有数值符合项。大图承载与20ms实时门槛仍未验收，
这三次短测不能推出机载表现或单点优化有效性。本轮不实施性能
A/B，保持默认代码和阈值；后续若定位候选，须另外预登记可逆
改动、同探针对照和功能回归。SIM-01D、研究模型质量继续独立待验。
