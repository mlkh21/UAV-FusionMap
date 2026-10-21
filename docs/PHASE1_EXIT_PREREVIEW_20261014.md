# Phase 1退出门禁预复核表（2026-10-14）

版本：v0.1；状态：预复核，2026-10-15正式复核尚未执行；主责任角色：Technical Lead
（协调Phase 1主责任simulation_engineer、PERF-01和ENV-03责任角色）。
依据：[开发计划§2/§4.1](DEVELOPMENT_PLAN.md)、[项目状态](../PROJECT_STATUS.md)、
[系统架构](SYSTEM_ARCHITECTURE.md)。本表不修改已确认阈值或计划日期，
不使用开题计划时间。

## 范围与判定口径

截至2026-10-14，只读核对既有记录、现存SIM-01D报告，并复跑
`bash ros_ws/sim01_env.sh python -B ros_ws/perf01_budget_gate.py configs/perf01_budget.yaml`；
使用的解释器为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。
没有新硬件接入、目标机性能运行、外部归档或10-15当日复核。
下表“已完成”只表示对应子任务及其证据边界；
“阻塞”不等于性能未达标，也不等于可跳过该门禁。

| 关口/计划责任角色 | 10-14已有证据 | 缺失输入或验收条件 | 10-14预复核判定 / 10-15动作 |
| --- | --- | --- | --- |
| SIM-01A/B/C状态/时钟、回放与异常；simulation_engineer（C由integration_engineer） | [A](../experiments/2026-09-14-sim01a-implementation.md)、[B](../experiments/2026-09-15-sim01b-implementation.md)、[C](../experiments/2026-09-16-sim01c-implementation.md)及[倍速记录](../experiments/2026-09-16-sim-speed01-implementation.md)；[PROJECT_STATUS](../PROJECT_STATUS.md#当前完成)登记后续正式关闭和历史偏差处置 | 不将短窗倍速等同持续性、机载性能或实飞 | 对应软件/仿真子任务已有归档结论；本次未重跑A/B/C，10-15复核既有证据范围 |
| SIM-01D跨边界持续性；simulation_engineer | [实际validation](../.runtime/runs/sim01d-live-20261005T231430430819/validation.json)、[writer-closed](../.runtime/runs/sim01d-live-20261005T231430430819/writer-closed.json)、[cleanup-audit](../.runtime/runs/sim01d-live-20261005T231430430819/cleanup-audit.json)现存且均`passed=true`；有效跨度`2400004000000 ns`，已跨32位微秒边界，[原记录](../experiments/2026-10-05-sim01d-continuity.md)含bag回读收据 | 本项无新增输入；不可代替PERF-01 | SIM-01D已完成；10-15仅核对产物索引和边界 |
| PERF-01正式输入及性能预算；Technical Lead | 本次只读门禁实际输出`mode=reference_only`、`ready=false`、`errors=[]`、10项阻塞；[预算门禁](PERF01_BUDGET.md#61-预算门禁预检2026-10-05)和[正式预检](../experiments/2026-10-06-perf01-formal-preflight.md)已定义拒绝条件 | 确认目标平台唯一ID/功耗模式，真实Radar/IR型号、频率/触发/时间误差、正式20 ms起止点、设备采样时钟与跨域映射、连续时长；随后取得同run、同速度的真实资源/功耗/温度/丢帧及逐样本时延证据 | **正式输入阻塞，不能给出正式达标/不达标结论**；10-15审查新增外部证据，缺失即保留阻塞 |
| ENV-03第二份独立副本与恢复；project_manager | 首次Git基线与保存规则已登记；[保存政策§4](VERSION_AND_ARTIFACT_POLICY.md#4-恢复与长期保存)明确未获独立归档授权 | 用户明确授权目标介质/路径及范围、实际第二份副本、新目录恢复和依赖/最小验证收据 | **未完成，单副本风险开放**；10-15评审风险与授权状态，无授权不复制、不写恢复通过 |
| Phase 1整体退出与计划日期；simulation_engineer主责，Technical Lead协调 | 仿真状态/异常和SIM-01D子项通过；PERF-01、ENV-03仍阻塞 | 按[原退出条件](DEVELOPMENT_PLAN.md#2-阶段与时间)核对版本、状态/时钟连续输出及暂停/重置/坐标；同时不得跳过计划登记的性能和保存关口 | **截至10-14不具备完整退出依据**；10-15复核才登记当日结论，未通过则单独评审范围/日期，不自动顺延或宣布完成 |

证据口径：[保存政策§1](VERSION_AND_ARTIFACT_POLICY.md#1-工程文件与版本边界)
仍保留制定时“尚无首次提交”的历史表述；本次只读`git log -1 --oneline`
为`4bd0c33 feat: establish engineering baseline`，与PROJECT_STATUS的首次提交记录相符。
ENV-03据此仅将首次基线列为已存在，未以Git提交代替该政策§4要求的独立副本/恢复。
该历史措辞留待管理文档勘误，不篡改当时授权或归档记录。

同日独立只读续审核对现存SIM-01报告：A归档605对状态/2302条clock和
30.196秒有效跨度；B的LIVE、B1、B2各自`validation.json`通过，
各有6003对状态/15794条clock；C的F0—F7及后续倍速九run为已归档
子范围，F6**仅**覆盖sensors本地`/clock`回退，F7是新run恢复，
不能写成整条源状态链的公共时钟回退；D归档有效跨度和关闭审计见上表。
本次未重读全部原始bag/账本、未复跑SIM进程和PID/端口清理检查，
历史SIM-01C修复前RED派生文件的mtime偏差按既有用户接受记录保留。
这是证据范围细化，不是新增SIM场景或10-15最终退出判定；
详见[A记录](../experiments/2026-09-14-sim01a-implementation.md)、
[B记录](../experiments/2026-09-15-sim01b-implementation.md)、
[C记录](../experiments/2026-09-16-sim01c-implementation.md)。

## PERF-01正式输入交接清单

当前[正式配置](../configs/perf01_budget.yaml)仍是工程参考。此次门禁返回的10项
阻塞按原样归类，不能用fixture、`/clock`或占位配置补齐：

| 输入项（10-15检查） | 现有状态 | 责任角色与解除条件 |
| --- | --- | --- |
| 目标平台选定及`formal_measurement.target_platform_id` | 未确认/缺失 | Technical Lead：提供唯一设备ID、功耗模式和测量来源 |
| `formal_measurement`正式测量状态 | 未确认 | Technical Lead：与实测方案及平台绑定，禁止纯手改开关伪造就绪 |
| `start_endpoint`及`end_endpoint` | 两项均缺失 | Technical Lead：确认物理采样、占据就绪等候选节点中的正式起止点及单调计时方法 |
| `sampling_clock_source`及`clock_domain_mapping` | 两项均缺失 | system_architect：提供设备时钟映射offset/drift/误差界及持续窗口计时依据 |
| `continuous_duration_s` | 缺失 | Technical Lead：确认正式连续时长，不能用SIM-01D或仿真钟替代 |
| Radar频率与timestamp误差的实物配置来源 | 未绑定 | sensor_engineer：提交选定ARS548配置及实际采样时刻/误差记录 |
| IR型号及时间配置 | 未确认 | sensor_engineer：提交选定Micro III Lite变体/镜头、帧率/触发与时间误差来源 |

以上七行合并展示预算门禁实际返回的10条阻塞：平台、正式状态、平台ID、
两个端点、采样时钟、映射、时长、Radar配置、IR配置。目标平台/传感器
正式证据具备后，先运行`--require-formal`预算检查，再执行同一run的manifest
与数值预检；`formal_ready`仅表示证据合同齐备。正式三航速35/50/70 m/s、
Radar—IR同步≤5 ms、P99≤20 ms、逐样本年龄与丢帧/超时/功耗预算
须以目标平台真实输入分别判定，不能以开发机ROS短测或合成正例宣布达标。
本次未运行`--require-formal`、正式manifest或正式性能测试。

## 10-15复核决策与恢复

1. Technical Lead收集上述输入及ENV-03新授权（如有），simulation_engineer
   对照原Phase 1退出条件核对版本、状态/时钟和异常/回放边界；逐项登记证据路径、
   观察日期、通过/阻塞/失败，不从`passed=true`推导未检查的指标。
2. 若外部输入仍缺：记录PERF-01正式输入阻塞、ENV-03单副本风险和Phase 1
   不满足完整退出条件；评审新目标日期/范围须另获确认，不能私自改写10-15。
   不申请或执行此前明确未授权的外部归档。
3. 不让阻塞事项卡住无依赖软件子范围：按原计划从2026-10-16的Phase 2
   继续IFACE-01/训练监督的具名fixture和记录合同；LiDAR仅作训练监督，
   未观测/无回波保持unknown，已观测超龄应保留stale，均不伪造free；
   训练LiDAR不进入在线SensorBundle或mapping。
   Phase 4滚动地图fixture不构成概率融合或真实内存性能验收，科研对照试验最后开展。

恢复方式：本次仅新建预复核文档并在PROJECT_STATUS加链接；若复核依据变化，
保留本次10-14快照并追加10-15实际证据/勘误，不覆盖旧实验或改动业务代码。
