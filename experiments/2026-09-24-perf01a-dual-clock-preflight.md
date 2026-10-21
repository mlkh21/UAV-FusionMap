# EXP-20260924-001：大图双时钟诊断与负载重复（预登记）

日期：2026-09-24；主责任：integration_engineer；当前分支`feature/engineering-initialization`，
工作区有未提交改动。以下计划在运行前登记；结果在完成后追加，不重建历史失败报告。

## 前置与假设

按现有`configs/perf01a_async.yaml`：5ms Radar/IR同步、10ms位姿年龄、
40ms仿真采样截止、500ms单调墙钟缓存；70m/s直线固定世界障碍物，
640×512 IR，2秒采样及200ms排空，seed=17，启用同一个线格式探针。
`exact`仅同刻配对，`deadline`仍等截止。每run在启动前生成独立expected.json，
runner的严格预登记oracle、地图与资源/清理门禁都维持原状；20ms诊断继续单列。

顺序为normal `exact`→`deadline`→`deadline`→`exact`（端口12031-12034），
再跑recovery `exact`（端口12035）。调用模板：

```text
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01a_async_run.py --scenario normal --speed-mps 70 \
  --pairing-policy exact --full-ir --wire-profile --duration-s 2 --port 12031
```

仅依次替换上述场景、配对策略及端口；输出只能进入新建的
`.runtime/runs/perf01a-async-*`，不得覆盖旧目录。预计normal按计划40个Radar
中20采用/20拒绝；recovery理想1x为12采用/28拒绝。拒绝数量相同但理由不同
仍算整run失败。接收、拒绝、地图、状态/clock排空、线程/进程清理及wire身份
任一缺证也算失败。`wall_clock_carryover`仅在同run/clock的IR有真实收据、
选择时仍在500ms墙钟窗口内、最终确为wall_timeout且理想1x已过期时解释
**拒绝理由差异**；不能豁免严格oracle或将意外迟到解释成相同原因。

短run AB/BA仅观察性能波动，不设采纳阈值、不推断稳定收益或机载实时验收。
风险：进程调度、真实回调排队、样本数较少均影响P99；若无法打开回环ROS端口，
保留未执行状态并说明原因。性能、SIM-01D、机载资源、研究模型质量分别待验。

## 实际结果

无权限的沙箱入口在创建回环socket时失败（未产生run）；经权限审批，
五条ROS run按登记顺序串行执行。下表后缀均补前缀`.runtime/runs/perf01a-async-`；
每条`perf-report.json`及source/producer/matcher/wire、地图老化和清理记录均独立保存。

| 顺序/端口 | 目录后缀 | 严格功能 | Radar接收/采用/拒绝 | 感知P99 / 20ms |
| --- | --- | --- | --- | --- |
| exact / 12031 | `20260924T130040630590` | 通过 | 40/20/20 | 45.000ms / 失败 |
| deadline / 12032 | `20260924T130127477310` | 通过 | 40/20/20 | 83.911ms / 失败 |
| deadline / 12033 | `20260924T130208174405` | 通过 | 40/20/20 | 89.454ms / 失败 |
| exact / 12034 | `20260924T130243771690` | 通过 | 40/20/20 | 50.042ms / 失败 |
| recovery exact / 12035 | `20260924T130326207745` | 通过 | 40/12/28 | 40.870ms / 失败 |

五条run的IR/Bundle线格式身份、源码状态/时钟排空均通过（221状态接收/发布，
末端clock=2200ms），无强制清理或端口残留。normal逐run的IR反序列化
P99按表顺序为9.322/9.092/7.807/9.424ms；IR序列化结束至反序列化开始
的混合区间P99为26.337/19.420/22.916/21.328ms，不能称为纯网络或与
独立P99求和。exact与deadline的两次对照趋势一致，但仅两个2秒run/模式，
既非足够的稳定性检验也未在目标机载平台测量。

recovery的Radar19本次实际为`infrared_unavailable`，与预登记理想1x理由一致；
旧IR24虽按计划到达，但其`wall_timeout`终态发生于Radar19决定**之前**约
1.904ms（单次时序差，不是可保证的调度裕量）。2026-09-23保留的失败run
`20260923T164514378192`中，IR24终态发生于该Radar决定**之后**约2.442ms，
诊断仍为`wall_clock_carryover`且原run仍失败。故双时钟调度可在固定配置下
改变拒绝理由；本次通过不能倒推旧run通过，也不支持把所有理由差异统一豁免。

诊断负例在修改前RED：伪造淘汰原因、run/clock身份、终态或遗漏/重复Radar决策
仍能误报解释/通过；修后缺少有效候选只报`unexplained`，缺失或重复决策不再
显示`strict_oracle_passed`。全仓`test_*.py` 200项通过，`git diff --check`通过。
本次无物理传感器、PX4高速状态、研究模型、机载功耗或SIM-01D长测。

## 决策边界

暂不更改严格预登记oracle、5ms同步门限或20ms性能目标。
后续**提案**需在运行前确认规则：仅对同run/clock、真实接收、决策时墙钟未过期且
最终以wall_timeout淘汰的远距IR，允许单独说明因1x理想模型过期而导致的
`infrared_unavailable`/`radar_ir_timeout`理由差异；采用身份、数量、消息顺序、
数据年龄、地图与丢帧账不得变化。该提案尚不是已接受的验收规则，实际ROS回调
竞争与wall超时还应增加独立验证；任何不满足条件的差异继续失败。
