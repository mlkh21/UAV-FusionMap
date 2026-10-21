# EXP-20260928-001: PERF-01-A 状态回调与 worker 内部分段（预登记）

日期：2026-09-28；责任：integration_engineer。依据 EXP-20260926-001：
状态111回调锁约20.298ms，Radar32 worker 锁内至决定约18.228ms；
这些是墙钟时间，不等于线程 CPU 或业务计算。本轮不改 matcher、
消息格式、配对策略、5ms 同步门限、40ms 采样截止或严格 oracle。

在现有显式 `--match-trace` 下记录标量 stage：状态适配、gate 消费、
状态编码/发布、matcher 方法、单条决定的事件与 Bundle 发布，worker 的
gate.poll_timeout 和 status 发布。每条 stage 记录 lock_id、可得的
sample_id、单调墙钟开始/结束和线程 CPU 纳秒；禁用时不附加 stage 账本。
阶段只是同一调用上下文的执行区间，线程 CPU 不可与其他线程的墙钟
直接相减；未覆盖的区间不得猜测为 ROS 传输或算法计算。

先进行纯内存 wrapper/离线契约测试和全仓轻量回归；通过后在新目录
运行一条 70m/s、640x512 IR、normal/exact、seed=17、2 秒、
`--wire-profile --match-trace`，端口 12061。独立原始产物存入
`.runtime/runs/perf01a-async-*`，不重写旧文件。按原预登记逐样本
严格 oracle 预计 40 Radar、20 采用/20 拒绝；wire 身份、状态/clock
排空、地图、资源和进程/端口清理任一失败则整 run 失败并保留。
20ms Radar 回调至占据 P99 独立报告，追踪开销导致的长尾不能与
2026-09-24 无追踪 run 做性能收益比较。

结果分析先核对各 stage 均处于相应锁内、起止和 CPU 不倒退、
原始事件身份不缺失，再说明能否复现状态持锁/worker 长尾。
仅当单一阶段出现可复现主导耗时，后续才另行预登记可逆优化与
A/B 采纳门槛；本轮不启用优化或改动双时钟拒绝理由验收政策。

## 实测与结论

沙箱内回环socket权限不足、未产生run；授权后按登记命令执行。
新产物：`.runtime/runs/perf01a-async-20260928T100834586215/`。
完整调用：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01a_async_run.py --scenario normal --speed-mps 70 \
  --pairing-policy exact --full-ir --wire-profile --match-trace \
  --duration-s 2 --port 12061
```

`perf-report.json`严格功能通过、零错误；40 Radar中20采用/20拒绝，
没有意外传输损失，IR/Bundle线格式及分段检查无错误；2201条clock
覆盖0至2200ms，221条状态接收/发布且pending=0，进程正常退出、
端口关闭。Radar实际回调至占据就绪P99=56.002ms，**20ms未通过**。
只读调用`ros_ws/perf01a_critical_path.py --match-trace --top 6 <run目录>`
关联20条采用样本、6726条stage记录，所有stage落在有释放时间的
对应锁内。stage中`decision.emit`包含其内部编码/发布子段，
不得与子段相加，独立P99也不得相加。

| 同run样本 | 原始连续边界/锁 | 阶段墙钟 | 同阶段线程CPU |
| --- | --- | ---: | ---: |
| Radar4 | worker获锁至决定12.037ms | `matcher.advance` 12.020ms | 11.653ms |
| Radar2 | worker锁26.820ms（决定后也持锁） | `bundle.publish` 12.109ms；`worker.publish_counts` 9.579ms | 11.339ms；1.562ms |
| Radar20 | worker锁26.276ms（决定后也持锁） | `bundle.encode` 21.586ms | 21.222ms |
| State11 | state锁11.744ms | `matcher.add_state` 11.533ms | 10.191ms |
| State198 | state锁11.729ms | `state.adapt` 11.654ms | 11.624ms |

`worker.publish_counts`的墙钟与CPU差距不能单独证明是网络等待：
它包含ROS参数服务与调度；`bundle.publish`包含序列化与ROS队列操作。
`matcher.finish`在全部输入结束后的锁中单次27.628ms，不处于上表
在线接受样本的关键路径。大图尾部还有回调前反序列化/排队成本，
不能从单个阶段推断完整20ms性能瓶颈。

**结论：**本次归因把09-26观察到的长锁划分为matcher、编码、发布、
统计与调度混合区间，但没有出现唯一且已重复验证的主导阶段。
不选性能候选、不修改默认行为和验收阈值。下一轮先同配置重复
诊断（运行前登记数量与接受规则），再针对可复现阶段预登记
单点A/B。SIM-01D、机载算力与模型质量继续独立待验。
全仓`test_*.py` 209项通过，`git diff --check`通过；没有运行
长时间SIM-01D或目标机载平台测试。
