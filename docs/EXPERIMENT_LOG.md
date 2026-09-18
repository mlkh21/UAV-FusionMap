# 验证与实验记录索引

版本：v0.1；更新日期：2026-09-18；维护角色：experiment_manager。
状态：初始化、环境、构建及SIM-01A/B/C有验收记录；SIM-SPEED-01九run技术矩阵通过，
已披露的证据保全偏差于2026-09-17获用户接受，SIM-SPEED-01与SIM-01C已正式
关闭；SIM-01D、PERF-01及完整Phase 1、训练、高速飞行和地图更新未验收。

## 1. 记录规则

编号格式为EXP-YYYYMMDD-NNN。区分文档检查、静态代码检查、单元/契约测试、离线回放、
仿真、训练和真实飞行。预期结果与实际结果分开，未执行或阻塞明确记录。
详细记录放experiments，索引保留目的、类型、结果和证据链接；大型产物仅登记位置。
历史记录不覆盖，勘误增加日期和原因。

## 2. 索引

| 编号 | 日期 | 类型 | 目的 | 状态与结论 | 证据 |
| --- | --- | --- | --- | --- | --- |
| EXP-20260911-000 | 2026-09-11 | 静态源码/路径检查 | 确认研究基础与工程接入边界 | 已完成静态检查；正式CLI存在缺失，运行未验收 | 本文记录与[组件登记](../algorithms/README.md) |
| EXP-20260911-001 | 2026-09-11 | 工程文档检查 | 验证初始化文件与约定一致性 | 已通过文档与范围检查；运行未验证 | [详细记录](../experiments/2026-09-11-engineering-initialization.md) |
| EXP-20260911-002 | 2026-09-11 | 环境/文件/源码检查 | ENV-01安装事实、资产和缺项核查 | 已完成清单；双ROS加载检查通过，JSBSim/MAVROS有缺项，NVML查询失败；运行未验收 | [详细记录](../experiments/2026-09-11-environment-inventory.md)、[环境清单](../configs/ENVIRONMENT_INVENTORY.md) |
| EXP-20260911-003 | 2026-09-11 | 静态源码/依赖模拟/文档检查 | ENV-02候选组合与最小仿真方案 | 方案已交付；核心MAVROS模拟新增7包，未安装/运行；时间及启动风险开放 | [详细记录](../experiments/2026-09-11-simulation-plan-review.md)、[执行方案](SIMULATION_VALIDATION_PLAN.md) |
| EXP-20260912-001 | 2026-09-12 | 依赖获取/构建/环境检查 | SIM-00A及ENV-03产物规则前置项 | 依赖解包、独立构建与解析检查通过；桥接15条警告，未启动仿真；备份/恢复待办 | [详细记录](../experiments/2026-09-12-sim00a-build.md)、[构建说明](../simulation/BUILD_SIM00A.md) |
| EXP-20260912-002 | 2026-09-12 | 调用链/构造测试/提案编译 | SIM-00B启动前核查与最小修复提案 | 前置核查完成；原构造失败，审查副本通过；正式补丁待确认，遥测阻塞 | [详细记录](../experiments/2026-09-12-sim00b-preflight.md)、[待应用补丁](../simulation/patches/SIM00B-INIT-01.patch) |
| EXP-20260912-003 | 2026-09-12 | 补丁/构建/消息回归/静止仿真 | SIM00B-INIT-01及SIM-00B | 已批准修复、独立重建和120.056秒静止遥测通过；未解锁，完整系统接口仍未验收 | [详细记录](../experiments/2026-09-12-sim00b-init-and-smoke.md)、[运行说明](../simulation/RUN_SIM00B.md) |
| EXP-20260914-001 | 2026-09-14 | 多agent只读分析/历史数据审计/文档评审 | SIM-01A具体实施方案 | 方案已交付；公共细化与代码实施待确认，未进行新运行验收 | [详细记录](../experiments/2026-09-14-sim01a-agent-review.md)、[实施提案](SIM01A_IMPLEMENTATION_PLAN.md) |
| EXP-20260914-002 | 2026-09-14 | 分层实现/Conda构建/契约/历史/ROS/静止仿真 | SIM-01A状态与时钟 | 已完成44项单元/契约、11项ROS fixture、605对状态及30.196秒valid静止联调；全部本次清理通过，完整Phase 1另验 | [详细记录](../experiments/2026-09-14-sim01a-implementation.md)、[运行说明](../simulation/RUN_SIM01A.md) |
| EXP-20260914-003 | 2026-09-14 | 多agent只读分析/Conda离线bag探针/方案评审 | SIM-01B具体范围及前置 | 方案完成待确认；3消息字节/索引往返通过，环境入口help泄漏未修复；未启动Master/300秒仿真或真实播放 | [详细记录](../experiments/2026-09-14-sim01b-agent-review.md)、[具体方案](SIM01B_RECORDING_REPLAY_PLAN.md) |
| EXP-20260915-001 | 2026-09-15 | 分层记录/实际ROS回放/反例/根因修复 | SIM-01B LIVE/B1/B2 | 已完成；LIVE 300.008001秒、B1逐字节/B2全新sensors复算均通过，各6003对状态/15794 clock；关闭重读/清理通过，三次失败B1保留 | [详细记录](../experiments/2026-09-15-sim01b-implementation.md)、[运行说明](../simulation/RUN_SIM01B.md) |
| EXP-20260915-002 | 2026-09-15 | 真实异常调用链/监督停止/倍速代码前置核查 | SIM-01C具体实施范围 | 只读方案完成、实施待确认；F0—F7已定义，发现0.5 factor截断及耗时方向问题；未启动ROS/仿真或修改bridge | [详细记录](../experiments/2026-09-15-sim01c-preflight.md)、[具体方案](SIM01C_FAULT_CLOCK_PLAN.md) |
| EXP-20260916-001 | 2026-09-16 | 真实MAVLink故障fixture/PX4倍速/回归 | SIM-01C故障链与倍速现状 | 部分通过：F0—F7通过；2倍连续1.6982/1.6945/1.6896低于1.7，0.5自由运行并reset，倍速阻塞，C未完成；清理均通过，未改bridge/PX4/业务状态机 | [详细记录](../experiments/2026-09-16-sim01c-implementation.md)、[运行说明](../simulation/RUN_SIM01C.md) |
| EXP-20260916-002 | 2026-09-16 | 源码调用链/失败证据复核/方案评审 | SIM-SPEED-01最小修复与验收边界 | 已完成只读核查：确认getter类型截断和elapsed方向两个根因；独立候选二进制及0.5/1/2倍九run方案待用户确认，未修改bridge、构建候选或执行运行 | [详细记录](../experiments/2026-09-16-sim-speed01-preflight.md)、[具体方案](SIM_SPEED_01_IMPLEMENTATION_PLAN.md) |
| EXP-20260916-003 | 2026-09-16 | 两行修复/独立构建/真实PX4-JSBSim-MAVROS九run | SIM-SPEED-01最小修复与预注册矩阵 | 技术通过：候选SHA-256 `d846038cddbd64859e1d48e414d994248c70c408ec3552d39cb472e2beb63ddf`；九run全部COMPLETE，三档实测范围为0.492476—0.492647、0.971738—0.972527、1.899797—1.909010，零terminal且清理通过；历史RED目录`sim01c-suite-20260916T085553794733/speed-2`的派生`scenario-result.json`被同语义重写、mtime改变，违反方案§6/§7证据保全门禁；该偏差于09-17获用户接受，原记录保留且不尝试恢复；不含SIM-01D、35—70m/s地图更新、感知或LiDAR验证 | [详细记录](../experiments/2026-09-16-sim-speed01-implementation.md)、[matrix manifest](../.runtime/runs/sim01c-suite-20260916T143604636221/speed-matrix-manifest.json)、[matrix结果](../.runtime/runs/sim01c-suite-20260916T143604636221/speed-matrix-result.json) |
| EXP-20260917-001 | 2026-09-17 | 证据治理/验收处置（未新增运行） | SIM-SPEED-01与SIM-01C正式关闭 | 用户明确接受历史RED派生`scenario-result.json`同语义重写及mtime变化的已披露偏差；保留完整记录，不伪造原时间，不尝试恢复；SIM-SPEED-01与SIM-01C正式关闭，R-13关闭。SIM-01D、PERF-01、高速地图测试、感知及LiDAR验收仍未完成 | [ADR-P013](DECISION_LOG.md#adr-p013-sim-speed-01最小修复与九run验收)、[实施记录](../experiments/2026-09-16-sim-speed01-implementation.md) |
| EXP-20260918-001 | 2026-09-18 | 参数确认/预算设计（未运行） | PERF-01航速与参考传感器冻结 | 已确认35/50/70 m/s、ARS548参考Radar、mid360训练监督参考；目标机载平台、IR规格、场景与阈值未定，未启动仿真或性能测量 | [详细记录](../experiments/2026-09-18-perf01-parameter-freeze.md)、[预算](PERF01_BUDGET.md)、[配置](../configs/perf01_budget.yaml) |

## 3. EXP-20260911-000：研究基础只读检查

- 责任角色：Technical Lead。
- 记录依据：2026-09-11本会话中实际工具输出；本记录为只读分析的追溯登记。
- 范围：两仓Git/目录、研究预处理、融合、生成器、预测契约和地图关键调用链。
- 方法：目录及路径检查、Git状态、按符号和行号阅读源文件；对7个关键Python文件
  使用ast.parse进行语法解析，不导入模块、不执行模型。
- 实际：确认同级独立仓库；7个文件语法解析通过；正式启动器引用的
  diffusion_consistency_radar/scripts/diagnose_checkpoint_chain.py不存在。
- 文件范围：预处理主程序、dataset_loader.py、multimodal_fusion.py、inference.py、
  prediction_artifact_protocol.py、probabilistic_mapping.py、streaming_map_update.py。
- 结论：已有研究实现，尚需系统适配与运行验证；离线地图循环不能证明ROS实时闭环。
- 未执行：依赖安装、权重加载、训练、完整预处理、模型生成、ROS/PX4/JSBSim运行。
- 数据/产物：未创建运行产物，未修改研究仓库；不能据语法结果声明功能或质量通过。

## 4. 后续实验模板

```text
编号 / 日期 / 类型 / 责任角色：
目的及关联需求/任务：
代码版本、分支和未提交状态：
环境、场景、输入数据、标定和模型版本：
配置快照、随机种子、实际命令：
预期结果及阈值来源：
实际结果（含失败与未执行项）：
输出目录和产物索引：
结论、限制、风险和下一步：
```
