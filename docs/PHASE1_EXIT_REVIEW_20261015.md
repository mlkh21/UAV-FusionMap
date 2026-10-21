# Phase 1退出门禁正式复核（2026-10-15）

版本：v0.1；状态：正式复核已执行，完整Phase 1退出阻塞；主责任角色：
simulation_engineer（阶段）；Technical Lead协调PERF-01，project_manager负责ENV-03。
依据：[工程计划§2/§4.1](DEVELOPMENT_PLAN.md)、[项目状态](../PROJECT_STATUS.md)、
[10-14预复核](PHASE1_EXIT_PREREVIEW_20261014.md)及
[保存政策§4](VERSION_AND_ARTIFACT_POLICY.md#4-恢复与长期保存)。仅按项目计划的
2026-10-15节点复核，不使用开题计划时间；未更改原目标日期、指标或责任。

## 当日核查范围

- 复跑 `bash ros_ws/sim01_env.sh python -B ros_ws/perf01_budget_gate.py configs/perf01_budget.yaml`；
  入口解释器经同环境检查为
  `/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。返回
  `mode=reference_only`、`ready=false`、`errors=[]`和10项外部输入阻塞；
  退出码0只表示参考模式检查本身正常，**不是**正式性能通过。
- 当日又以相同环境运行上述命令并追加 `--require-formal`：返回同样的
  `reference_only/ready=false` 和10项阻塞，退出码为1；这是缺正式输入时
  预期的拒绝结果，不是已完成目标机测量后的性能不达标结论。
- 核对[SIM-01D validation](../.runtime/runs/sim01d-live-20261005T231430430819/validation.json)、
  [writer-closed](../.runtime/runs/sim01d-live-20261005T231430430819/writer-closed.json)、
  [cleanup-audit](../.runtime/runs/sim01d-live-20261005T231430430819/cleanup-audit.json)：
  三份报告现存且 `passed=true`；validation的 `errors=[]`、
  `valid_span_ns=2400004000000`、`boundary_crossed=true`；对应 `live.bag` 文件现存。
  [10-05原记录](../experiments/2026-10-05-sim01d-continuity.md)记载bag回读；
  本次**未重新回读bag/原始账本，也未重跑40分钟仿真**。
- 核对[A/B/C记录](../experiments/2026-09-16-sim01c-implementation.md)、
  [倍速验收](../experiments/2026-09-16-sim-speed01-implementation.md)及
  [10-14独立证据边界](PHASE1_EXIT_PREREVIEW_20261014.md)：
  不重新运行历史A/B/C或九run。F6仅为sensors本地时钟回退，
  F7为新run恢复；历史RED派生文件mtime偏差按已接受处置保留。
- `git log -1 --oneline` 显示首次提交
  `4bd0c33 feat: establish engineering baseline`；它不是 `.runtime` 的独立备份。
  查阅现存政策与项目记录，仍无新外部归档授权、第二份独立副本及新目录恢复收据；
  不推断外部世界绝对不存在副本。当前 `experiments/`、`tests/` 被
  `.gitignore` 整目录忽略，新文件默认不会出现在普通 `git status`。

## 逐项判定

| 关口 | 2026-10-15证据边界 | 判定 | 后续解除条件 |
| --- | --- | --- | --- |
| SIM-01A/B/C、SIM-SPEED-01；simulation_engineer / integration_engineer | 既有记录覆盖状态/时钟记录回放、坐标适配、暂停/故障/新run及短窗0.5/1/2倍；本日仅审查归档记录 | **相应软件/仿真子范围已完成**，非机载或持续性能验收 | 保留历史边界；如需扩大场景，独立设计和验证 |
| SIM-01D；simulation_engineer | 10-05持续性报告与bag文件现存，三份通过标志及跨边界有效跨度如上 | **已有持续性子项通过记录**；本日未新增实测 | 不用旧报告代替新硬件性能或其他run的连续性 |
| PERF-01正式输入及预算；Technical Lead | 当日预算门禁为 `reference_only/ready=false`，10项阻塞；开发机短测P99诊断不能代替正式平台实测 | **阻塞，尚无正式达标或未达标判定** | 唯一目标平台及功耗模式、Radar/IR实物配置和采样时间误差、正式起止端点与设备时钟映射、连续时长；随后同run三航速逐样本时延、资源/功耗/温度/丢帧证据通过正式预检 |
| ENV-03资产恢复；project_manager | 保存规则与首次Git基线已有；没有经确认的独立副本/新目录恢复收据，原用户明确不授权外部归档 | **阻塞，单副本风险开放** | 单独取得目标介质/范围授权，完成第二份独立副本、新目录恢复、依赖与最小验证收据；未授权不复制 |
| Phase 1整体退出；simulation_engineer，Technical Lead协调 | 原计划的仿真/时钟/异常交付有归档子项通过；计划同时登记PERF-01及ENV-03待办，本日仍无解除证据 | **2026-10-15正式复核：完整Phase 1不通过退出，状态阻塞** | 两项分别按正式证据关闭，再复核整体；新日期/范围须另行审议，不自动延期或放宽门槛 |

## 待输入与执行边界

预算门禁的10条阻塞原文归类详见[预复核交接清单](PHASE1_EXIT_PREREVIEW_20261014.md#perf-01正式输入交接清单)。
获真实外部输入后先运行预算门禁 `--require-formal`，再核对同run的manifest与数值预检；
通过合同检查本身仍非P99≤20 ms、Radar—IR同步≤5 ms或目标平台功耗的实测通过。
设备采样时钟、跨域误差和物理输入不可由仿真 `/clock` 或fixture代替。

本次不开展对照试验、不接入真实设备、不创建备份、不运行正式性能任务、不修改
模型/地图代码，也不改动同级研究仓库或历史实验。无依赖的Phase 2软件fixture
可按2026-10-16原计划继续，不能倒填Phase 1完成；训练LiDAR只用于监督，
未知/过期/无回波不得解释为free。需由阶段负责人和Technical Lead另行评审
**新日期与范围**；在决策前保留2026-10-15原门槛及本次阻塞结论。

风险：单机运行产物及未跟踪/被忽略文件仍有保存缺口；归档报告并非今日新的
端到端测试，无法证明目标机载平台资源、设备时钟、概率地图或实际飞行表现。
本次恢复方式为追加注明新证据的后续复核记录，不覆盖本次判定或旧产物。
