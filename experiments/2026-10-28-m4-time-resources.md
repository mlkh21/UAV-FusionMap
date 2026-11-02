# M4-SW-03：离线时序、资源与联合原子性组合

编号：EXP-20261028-003；日期：2026-10-28；主责任：mapping_engineer。
状态：已完成（固定合成注册下的离线组合范围）；依据：用户确认继续执行
[M4方案](../docs/M4_SOFTWARE_TRIAL_PLAN_20261027.md)，前置为
[SW-02显式候选](2026-10-28-m4-scene-candidate.md)。

## 审计、问题与范围

先读取根/模块规则、PROJECT_STATUS、SYSTEM_ARCHITECTURE及数据/坐标约定，
复核SceneMap→公开M3更新/快照→Scene所有权/查询的实际调用链、独立预期和消息承载。
Git分支feature/engineering-initialization，保留全部已有未提交改动；
忽略规则核对.runtime/runs/m4-time-probe命中，不提交/推送或覆盖历史实验。

SW-02已有基础目录/TTL/失败样例，本轮缺口是多cell年龄、反复封存/淘汰/返回、
提交后段故障组合和资源项/副本分别计数。只新增测试侧场景、审计及运行器，
未发现需要修复的业务错误，未修改Scene/M3/M4 checker、配置、工厂、ROS或公共字段。
恢复为停止使用测试工具，旧入口继续原配置；无需迁移运行状态。
没有修改同级研究仓库或原Conda环境，不启动ROS Master、GPU、模型或训练。

## 独立场景与冻结预期

[m4_time_scenarios.py](../tests/m4_time_scenarios.py)先建立3组显式时序/所有权状态表，
再建立120帧周期轨迹。预期只使用测试专用分数坐标/已有M3算例，
不调用候选目录、格点辅助函数或从候选查询反推答案。
周期轨迹为0/40/80m三个互不重叠窗口重复访问，每次访问先两个occupied，再对其中一个
给free；当前访问与前一次访问的owner直接由周期编号给定，是闭式轨迹表，
没有重写一个任意Scene融合/淘汰状态机。

生成运行先保存完整case配置/输入/答案，再执行候选；源产物为
[m4-time-20261028T104242817551/fixtures.json](../.runtime/runs/m4-time-20261028T104242817551/fixtures.json)。
后续独立重放只读保存答案，不导入m4_oracle或重新计算预期。
最终报告明确saved_expectations_recomputed=false：
[report.json](../.runtime/runs/m4-time-20261028T104715297331/report.json)、
[fixtures副本](../.runtime/runs/m4-time-20261028T104715297331/fixtures.json)、
[results.json](../.runtime/runs/m4-time-20261028T104715297331/results.json)。
全部4场景、140帧、323查询、五类状态及实际消息序列化对账通过。
沿用SW-02的1e-12数值比较和精确身份/时间/元数据检查，未扩大容差或改写原预期。

| 场景 | 帧数 | 已验证结果 |
| --- | --- | --- |
| different_cell_ages_and_missing_restart | 7 | K=2保留不同贡献年龄的P/Q，同一查询时刻P可stale而Q仍新鲜；空移动结构时间单列，历史查询拒绝；新missing接管、known不借旧范围，TTL后free重启恢复范围 |
| no_stale_owner_resurrection | 7 | K=1连续窗口切换/空移动，FIFO淘汰P后返回空窗口仍unknown；新free为0.25，空目录不占额，后续封存不复活旧概率/范围 |
| rejected_future_does_not_poison_time | 6 | 越界未来帧、坏末尾quality、错run、迟到全部拒绝，原状态/水位不变；随后较早的合法Q可提交 |
| periodic_120_steps | 120 | K=1/N=2/H=3，60次三窗口循环访问；每次从活动先验开始，交替known/missing；封存只留前一访问，两次以前访问unknown，原时间/quality不借用 |

所有场景都通过已有公开OccupancyObservation输入，训练LiDAR/target/observed_mask没有旁路。
未知、空/无回波、失效和过期数据保持unknown/unavailable/stale，不解释为free。

## 联合原子恢复与域隔离

[m4_time_validation.py](../tests/m4_time_validation.py)用测试专用fingerprint保存完整原始字典，
比较公开快照、活动/封存/所有权、序号、结构时间，以及M3私有区间账本、身份历史、
输入/几何水位和原观测；不是Hash，也不生成新协议字段。
4个故障点均发生在临时活动M3更新之后：

| 故障点 | 已到达的临时状态 | 结果 |
| --- | --- | --- |
| export_after_local | 活动M3已更新，Scene导出结束 | 故障向外报告，完整已提交状态等于原值；同身份/时刻重试成功 |
| takeover_after_delete | P已在临时目录从旧封存owner删除，并由新missing接管 | 原目录/质量/账本未部分提交；重试成功且不借旧范围 |
| after_fifo | 临时目录已FIFO淘汰旧P，保留Q/R | 原P/Q状态未改变；重试可正常完成FIFO |
| after_validation | 临时Scene所有权/载荷已完成校验，但尚未提交 | 原Scene revision与M3水位不变；重试成功 |

4个故障恢复后，重复同一输入均not_fused，完整状态不再变化。
另1个域探针覆盖错run/clock、注册到期不污染旧实例，新run空实例不继承历史，
首个free重新得到0.25。独立定向还覆盖去重历史被H淘汰后旧时间仍拒绝，
多cell年龄与更严格请求max_age、偏航+双轴重叠移动的Scene index/质量保真。
完整探针结果见
[probes.json](../.runtime/runs/m4-time-20261028T104715297331/probes.json)。
这验证的是显式run/clock/固定注册域隔离，未声明同run定位跳变仍不能可靠识别。

## 保留项、导出与临时副本

[m4_resource_audit.py](../tests/m4_resource_audit.py)是测试工具，不加入运行接口。
提交后核对M3 cell与区间账本键一致、Scene owner唯一及index引用的对象是原owner载荷，
不能以拷贝旧值或隐藏版本充数。另有反例测试，故意复制index载荷或清空区间账本时审计明确失败。

120帧轨迹的最终保留峰值如下；N=2、K=1、H=3，输入V≤2：

| 项目 | 观察峰值 | 结构上界 |
| --- | --- | --- |
| 活动M3 cells / 私有区间项 | 2 / 2 | N / N |
| 活动Scene导出载荷 | 2 | N |
| 封存子地图 / 封存cell载荷 | 1 / 2 | K / K*N |
| Scene所有权索引引用 / 唯一owned载荷 | 4 / 4 | (K+1)*N / (K+1)*N |
| 去重身份记录 / 其中voxel载荷 | 3 / 5 | H / H*V=6 |
| 独立全量快照输出 / 单点查询载荷 | 4 / 1 | (K+1)*N / 1 |

H约束消息条数，V是输入消息voxel数，不能把V直接当作N。
独立测试用N=2/V=3连续输入，保留3条身份时实际有9个voxel载荷而仍只有2个活动cell；
按H*N错误计算会被反例查出。完整公开输入的V受shape乘积限制，文本长度/字节开销未在本轮冻结。

临时副本用sys.settrace在mapping Python代码行与返回边界采样可达对象，
同一对象按id去重计数，索引引用与载荷分开。包含已提交/暂存状态、M3账本、
封存记录、临时owner查找表、前后快照和部分/返回输出列表；不遍历测试调用方的历史case/结果。
探针用6次有效更新覆盖容量淘汰、重叠移动、missing、FIFO和返回，每次还调用snapshot/query。

| 可达对象项 | 采样峰值 | 保守结构上界（该探针N=2/K=1/H=3/V=2） |
| --- | --- | --- |
| 独立cell字典载荷（含副本） | 18 | (2K+12)N+2V+4=36 |
| 输入voxel字典载荷（含身份副本） | 10 | 2HV+2V=16 |
| Scene状态 / 活动M3对象 | 2 / 2 | 2 / 2 |
| 两状态所有权索引引用合计 | 8 | 2(K+1)N=8 |
| 两状态封存记录合计 | 3 | 2K+1=3（包含淘汰前临时K+1） |
| 两活动M3区间账本项合计 | 4 | 2N=4 |
| 两活动M3身份记录合计 | 7 | 2H+1=7（包含临时H+1） |
| 临时封存owner查找表 | 2 | K*N=2 |
| 活跃快照/输出列表中的cell项合计 | 6 | (2K+8)N=20 |

上界依据一个已提交状态、一个完整临时状态、前后快照、局部/Scene构造及导出逐项保守分配，
不是按观察到的峰值倒定阈值。采样不覆盖deepcopy/解释器/分配器内部瞬时未暴露的分配，
不测字节数、allocator峰值、进程RSS、GPU、延迟或功耗；调用方持续保存输出也不属于候选保留。
因此只能关闭本合成范围的逻辑有界检查，不能据此关闭机载资源或正式PERF-01。
数据见[resource-audit.json](../.runtime/runs/m4-time-20261028T104715297331/resource-audit.json)。

## 回归与文件清单

新增[test_m4_time_resources.py](../tests/test_m4_time_resources.py)13项，首轮通过；
最终M4共52/52、全仓622/622通过，日志与命令收据：
[m4-tests.log](../.runtime/runs/m4-time-20261028T104715297331/m4-tests.log)、
[lightweight-tests.log](../.runtime/runs/m4-time-20261028T104715297331/lightweight-tests.log)、
[lightweight-tests.json](../.runtime/runs/m4-time-20261028T104715297331/lightweight-tests.json)。
实际解释器为指定Radar-Diffusion/bin/python，所有Python通过sim01_env.sh运行。
扩展临时索引/列表计数后重新完成最终保存重放与定向/全仓回归；此前源输入和中间产物均保留。
未修改业务运行源码，因此不重复启动旧ROS；M4实际ROS图、公开回放和应用交接留SW-04。
文档相对链接/新文件空白及git diff --check通过，没有自动提交/推送。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m4_time_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m4_time_run.py --input .runtime/runs/m4-time-20261028T104242817551/fixtures.json
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_m4*.py' -q
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

新增5个测试文件：tests/m4_time_scenarios.py、tests/m4_resource_audit.py、
tests/m4_time_validation.py、tests/m4_time_run.py、tests/test_m4_time_resources.py。
新增本记录；更新PROJECT_STATUS.md、docs/M4_SOFTWARE_TRIAL_PLAN_20261027.md、
docs/DEVELOPMENT_PLAN.md、docs/STAGE_ADVANCE_PLAN_20261027.md、docs/RUNTIME_CONFIGURATION.md、
docs/SYSTEM_ARCHITECTURE.md、docs/DECISION_LOG.md、docs/EXPERIMENT_LOG.md，登记本轮证据与下一交付。

已有能力为显式Scene候选；本轮实现的是组合场景/探针/资源审计工具；
已验证固定合成注册下的离线时序、故障恢复及逻辑上界，未增加公共接口或运行后端。
未验证M4 ROS、真实标定/定位连续性/动态注册、模型质量、机载资源或正式性能。
研究模型质量仍暂缓，research fail-closed；不跑模型/训练/科研对照，不推进DEM或自主控制。

下一项M4-SW-04（计划，tester）：显式私有M4工厂/ROS/公开占据回放接入，
独立应用map查询、五类状态/历史quality/失效恢复和旧M1/M2/M3/placeholder回归，
核对Python、图隔离与进程/端口清理。离线通过不替代运行图证据，正式M4与完整阶段门槛保持。
