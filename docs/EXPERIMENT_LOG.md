# 验证与实验记录索引

版本：v0.1；更新日期：2026-10-21；维护角色：experiment_manager。
状态：初始化、环境、构建及SIM-01A/B/C有验收记录；SIM-SPEED-01九run技术矩阵通过，
已披露的证据保全偏差于2026-09-17获用户接受，SIM-SPEED-01与SIM-01C已正式
关闭；35/50/70m/s功能级小图运动短测及SIM-01D独立持续性已通过；PERF-01及完整Phase 1、
真实传感器/研究模型、高速实时飞行和正式地图能力未验收。

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
| EXP-20260918-002 | 2026-09-18 | bridge时间类型修复/边界C++测试/独立构建/运行器与checker/契约回归 | SIM-01D 32位微秒边界前置 | HIL_SENSOR/HIL_GPS四点边界测试RED/GREEN链通过；新候选构建和ldd通过；初始化、倍速getter及正式SIM-01 Python 97/97通过；新增独立连续配置、运行器、checker并通过2项契约单测；未执行ENV-03归档和40分钟长测，端口检查受沙箱限制 | [详细记录](../experiments/2026-09-18-sim01d-preflight.md)、[SIM-01D候选](../.runtime/build/jsbsim-bridge-sim01d/jsbsim_bridge) |
| EXP-20260920-001 | 2026-09-20 | ROS占位闭环/契约回归/前置修补 | PERF-01-A及SIM-01D前置 | 两次160样本技术通过，最终800事件闭合、清理通过；122项契约通过；SIM-01D长测未执行。旧零事件报告重建偏差已披露，尚无用户处置 | [详细记录](../experiments/2026-09-20-perf01a-integration.md) |
| EXP-20260920-002 | 2026-09-20 | 大图载荷/同步失效/恢复/RED-GREEN | PERF-01-A后续负载与故障 | 128项契约、六个ROS场景功能检查通过；大图40/40更新，P99感知30.376ms仍超20ms目标；首个39/40失败run保留 | [详细记录](../experiments/2026-09-20-perf01a-load-faults.md) |
| EXP-20260920-003 | 2026-09-20 | 分段计时/AB-BA观察器对照/读缓冲候选/关闭探针控制 | PERF-01-A耗时分解 | 134项契约、18个大图正式对照及冒烟/3故障回归通过；基线full/light汇总P99=32.376/33.965ms，18个20ms诊断全部失败；观察器CPU下降未稳定改善尾延迟，4MiB候选未采纳为默认 | [详细记录](../experiments/2026-09-20-perf01a-segmented-timing.md) |
| EXP-20260920-004 | 2026-09-20 | 实际线格式探针/metadata拓扑/进程树资源/单候选复测 | PERF-01-A成本归因 | 141项契约与33个短run功能检查通过；正式full/light/metadata P99=33.257/31.377/27.546ms；NumPy解码降幅中位数0.950%未达预登记条件，默认不变；15个正式20ms诊断均失败，采样开销与探索结果完整保留 | [详细记录](../experiments/2026-09-20-perf01a-wire-cost.md) |
| EXP-20260922-001 | 2026-09-22 | 独立发布/有界匹配/实际ROS场景 | PERF-01-A异步Radar/IR链路 | 83项异步相关契约通过；7/7异步场景及640×512 IR正常场景通过；生成/接收/采用/未采用/预期拒绝/意外丢失分账闭合，20ms诊断仍失败 | [详细记录](../experiments/2026-09-22-perf01a-async.md)、[套件产物](../.runtime/runs/perf01a-async-suite-20260922T105608857271) |
| EXP-20260923-001 | 2026-09-23 | 35/50/70m/s功能级运动/异步ROS小图与大图/老化恢复 | 高速运动时空一致性基线 | 全仓194项契约通过；小图三档运动和故障恢复短run功能通过，50m/s格网边界失败、大图恢复oracle理由失败均保留；大图normal功能通过但P99=69.328ms超20ms，PERF-01实时与机载验收未完成 | [详细记录](../experiments/2026-09-23-perf01a-motion.md)、[大图失败产物](../.runtime/runs/perf01a-async-20260923T153845822987/perf-report.json) |
| EXP-20260923-002 | 2026-09-23 | 运动格网边界与实际ROS异步大图线格式 | 独立oracle/占据/地图格子核对及大图承载分段 | 196项契约通过；边界小图及大图normal短run部分通过，recovery理由失败、重复deadline状态排空失败均保留；大图20ms诊断全部失败 | [详细记录](../experiments/2026-09-23-perf01a-boundary-wire.md) |
| EXP-20260923-003 | 2026-09-23 | 状态/clock排空与双时钟理由 | 完成状态排空门禁，诊断但不豁免oracle差异 | 198项契约通过；大图deadline修后功能短测通过、recovery严格oracle仍失败，20ms未达标；两次参数编码失败run均保留 | [详细记录](../experiments/2026-09-23-perf01a-clock-drain.md) |
| EXP-20260924-001 | 2026-09-24 | 大图AB/BA和双时钟边界复核 | 预登记exact/deadline/recovery 5条2秒run | 200项契约通过；5/5严格功能通过，但P99均超20ms；本次IR24在Radar19决定前过期，不抵消09-23旧失败；双时钟理由规则仍待确认 | [详细记录](../experiments/2026-09-24-perf01a-dual-clock-preflight.md) |
| EXP-20260924-002 | 2026-09-24 | 逐样本尾延迟归因及IR TCP传输单候选A/B/B/A | 默认关闭的IR订阅`tcp_nodelay`开关，70m/s大图normal/exact 4条2秒run | 201项契约及4/4严格功能通过、每run 20/20采用/拒绝；P99=48.384/53.779/46.431/50.356ms均未达20ms；候选未达预登记双组10%下降条件，默认关闭；严格双时钟理由oracle不变 | [预登记与结果](../experiments/2026-09-24-perf01a-ir-transport.md) |
| EXP-20260924-003 | 2026-09-24 | 四条既有大图run逐样本关键路径只读复核 | 关联真实IR/Bundle线格式、Radar和IR收据及决定时刻；下一轮锁/状态/clock定位预登记，尚未运行 | 各20个采用样本身份闭合；尾部样本主因不一致，发现25-30ms回调后待决定与约27ms Bundle混合排队区间，不能直接归因网络或matcher计算；严格oracle及20ms门槛不变 | [分析与预登记](../experiments/2026-09-24-perf01a-critical-path.md) |
| EXP-20260926-001 | 2026-09-26 | matcher状态/clock/worker锁追踪与逐样本归因 | 默认关闭标量追踪；70m/s大图normal/exact、wire-profile、四条独立2秒run | 首条Radar34实际IR迟到、严格失败保留；后三条严格功能通过但P99=60.528/59.226/57.276ms均超20ms；终版样本关联发现状态回调持锁与worker墙钟长尾，尚未区分CPU/调度 | [预登记与结果](../experiments/2026-09-26-perf01a-match-trace.md) |
| EXP-20260928-001 | 2026-09-28 | 状态回调和worker内部阶段墙钟/线程CPU | 默认关闭的`--match-trace`追加锁内标量stage；独立70m/s大图normal/exact 2秒run | 20/20采用/拒绝，严格功能、排空、wire和清理通过；P99=56.002ms超20ms；单次长段涉及matcher、编码、发布等不同阶段，未选择优化候选 | [预登记与结果](../experiments/2026-09-28-perf01a-stage-trace.md) |
| EXP-20260928-002 | 2026-09-28 | 大图内部分段重复诊断 | 同配置70m/s normal/exact大图、默认关闭的探针仅实验开启、三条独立2秒run | 3/3严格功能通过，P99=59.749/49.122/53.014ms均超20ms；最慢采用样本未出现跨run同一CPU/墙钟>=10ms阶段，未选优化候选；旧失败保留 | [预登记与结果](../experiments/2026-09-28-perf01a-stage-repeat.md) |
| EXP-20260928-003 | 2026-09-28 | 既有大图产物只读逐样本等待归因 | 三条已通过run的IR/状态-clock/worker/Bundle/感知原始账本对齐，补测条件登记 | 60/60采用样本闭合；确认不同长尾原因和关键未归因区间，不选单点优化；仅登记后续探针，不运行新ROS或A/B，20ms仍失败 | [大图端到端等待归因表](../experiments/2026-09-28-perf01a-end-to-end-wait.md) |
| EXP-20260928-004 | 2026-09-28 | 可选worker等待/锁内CPU探针与三次独立大图短测 | 锁/线程CPU缺口标量和只读校验，70m/s normal/exact相同探针三次短测 | 全仓210项轻量测试、3/3严格功能与资源清理通过；P99=90.011/47.413/53.940ms均未达20ms；无跨run重复决定前候选，不实施A/B | [预登记与实测](../experiments/2026-09-28-perf01a-wait-probe.md) |
| EXP-20260928-005 | 2026-09-28 | 三条既有run全部采用样本的20ms常态成本与可达性核算 | 只读同根时间分段、预算算术与混合区间边界 | 60/60逐样本闭合，60/60端到端超20ms，其中43/60仅IR到达偏移与Bundle到感知两段已超20ms；无新运行、不改变20ms目标或选单点A/B | [逐样本成本表](../experiments/2026-09-28-perf01a-20ms-feasibility.md) |
| EXP-20260929-001 | 2026-09-29 | 只读预算/计时边界核查 | 对齐20ms异步诊断、fixture生成/仿真数据年龄与待确认的机载验收端点 | 异步诊断仅覆盖Radar回调至占据就绪；设备采样、占据对外消费与跨设备时钟仍缺证据，目标平台未确认；不启动新试验、不放宽20ms/5ms或选择A/B | [边界与待决清单](../experiments/2026-09-29-perf01a-budget-boundary.md) |
| EXP-20261003-001 | 2026-10-03 | 端点/时钟桥接探针预登记 | 补齐输入采样可用性、worker混合等待及occupancy/map下游端点 | 仅预登记，尚未运行；不改变代码默认行为、匹配器、Bundle、5ms同步或20ms目标；无真实设备采样时钟时不计算物理数据年龄 | [探针预登记](../experiments/2026-10-03-perf01a-endpoint-probe-prereg.md) |
| EXP-20261003-001-R | 2026-10-03 | 端点/时钟桥接探针三次短测 | 验证下游端点增量、采样时钟可用性和决定前/Bundle长尾重复性 | 3/3严格功能、wire、状态-clock、地图、资源和清理通过；P99=58.745/78.635/53.507ms；下游快照增量P99=2.085/3.314/2.049ms；采样时钟均不可用，未选A/B，20ms/5ms边界不变 | [实测结果](../experiments/2026-10-03-perf01a-endpoint-probe.md) |
| EXP-20261003-002 | 2026-10-03 | fake Radar/IR功能级参数化与契约回归 | 增加FOV、量程、可重复噪声及扫描/曝光时长入口，保持默认fixture兼容 | 已完成；新增5项fake传感器测试及相关motion/contract/scenario/async/wrapper/wire回归通过；未启动性能短测，不改变5ms/20ms门槛或LiDAR在线边界 | [详细记录](../experiments/2026-10-03-fake-sensor-parameterization.md) |
| EXP-20261003-003 | 2026-10-03 | 参数化fake Radar/IR真实ROS短链路 | 启用FOV、量程、强度/IR噪声及扫描/曝光时长，验证发布器→匹配→Bundle→placeholder→地图 | 首轮位置噪声导致固定地图oracle失败并保留；关闭该场景位置噪声后第二次2秒run通过，20个有效样本闭合；不产生20ms性能结论 | [详细记录](../experiments/2026-10-03-fake-sensor-ros-parameterized.md) |
| EXP-20261003-004 | 2026-10-03 | fake Radar位置噪声动态地图oracle | 以Bundle Radar点和变换独立计算连续坐标/体素，核对累计地图cell而非复用固定静态格 | `parameterized_position_noise` 2秒ROS run通过，位置噪声0.01m开启，20个有效样本及地图累计cell闭合；不产生真实性或20ms结论 | [详细记录](../experiments/2026-10-03-fake-sensor-position-noise-oracle.md) |
| EXP-20261004-001 | 2026-10-04 | fake IR空间热点与ROS短链路 | 增加可重复像素热点/圆形覆盖和叠加，验证热点经ROS、Bundle和placeholder链路 | 新增7项热点单测、旧场景/wire/wrapper回归通过；`parameterized_sensors` 2秒ROS run通过；不产生热物理、模型质量或20ms结论 | [详细记录](../experiments/2026-10-04-fake-ir-hotspots.md) |
| EXP-20261005-001 | 2026-10-05 | 真实ROS小图/同帧IR值守恒 | 独立订阅原始IR，按sample_id对照每个采用它的Bundle的全图像素、热点/背景及曝光时间 | 先保留null配置失败run；修正后2秒run通过，100帧原始IR、20 Bundle的同帧值级核对及严格配对/清理通过；226项轻量测试通过；20ms诊断不通过，SIM-01D/训练LiDAR未验收 | [详细记录](../experiments/2026-10-05-sens-ir-value-transport.md)、[通过报告](../.runtime/runs/perf01a-async-20261005T153338134262/perf-report.json) |
| EXP-20261005-002 | 2026-10-05 | PERF-01预算门禁预检 | 固化从工程参考预算进入正式性能验收所需的平台、端点、采样时钟和配置条件 | 当前配置正确保持`reference_only`，10项正式输入阻塞；5/20ms阈值漂移负例和正式输入ready正例通过；未启动ROS或长测，不产生性能结论 | [详细记录](../experiments/2026-10-05-perf01-budget-gate.md)、[预算配置](../configs/perf01_budget.yaml) |
| EXP-20261005-003 | 2026-10-05 | 真实PX4-JSBSim-MAVROS连续仿真/边界checker/bag回读/清理审计 | SIM-01D跨32位微秒边界持续性 | 专用候选和独立端口运行约41分钟；有效跨度`2400004000000 ns`，跨越`2147483647000 ns`；clock/source/sensor约50/20/20Hz，源与适配各48002条；实时记录、bag回读、writer排空、边界checker及端口/PID清理全部通过。未验证PERF-01、研究模型或训练监督LiDAR | [详细记录](../experiments/2026-10-05-sim01d-continuity.md)、[运行目录](../.runtime/runs/sim01d-live-20261005T231430430819)、[validation](../.runtime/runs/sim01d-live-20261005T231430430819/validation.json) |
| EXP-20261006-001 | 2026-10-06 | PERF-01平台/设备只读审计、正式证据契约测试 | 确认正式20 ms测量是否具备平台、真实传感器、采样时钟和证据入口 | 当前x86开发机不是参考Jetson目标平台，未发现ARS548/Micro III Lite物理输入、外部功耗或设备时钟证据；预算门禁保持`reference_only`并阻塞10项；新增manifest预检拒绝fixture频率、仿真时间和`/clock`替代物理测量；未启动正式ROS性能运行 | [详细记录](../experiments/2026-10-06-perf01-formal-preflight.md)、[预算配置](../configs/perf01_budget.yaml)、[预算门禁](../ros_ws/perf01_budget_gate.py)、[正式预检](../ros_ws/perf01_formal_preflight.py) |
| EXP-20261008-001 | 2026-10-08 | PERF-01证据内容RED/GREEN与只读数值预检 | 空文件/单一通过标志不得绕过正式门禁，逐样本重算P99并验证同步、年龄、丢帧/超时、资源与连续性 | 先复现旧预检7组反例失败；修复后14项正式预检、140项PERF-01相关及全仓243项轻量测试通过；预算门禁仍`reference_only`、10项阻塞，`--require-formal`退出1。未启动ROS或采集设备性能 | [详细记录](../experiments/2026-10-08-perf01-metric-preflight.md)、[预算说明](PERF01_BUDGET.md)、[只读预检](../ros_ws/perf01_formal_preflight.py) |
| EXP-20261008-002 | 2026-10-08 | 实际ROS fake Radar/IR 35/50/70m/s大图开发机短测 | 核对预登记严格配对、身份/地图闭合、资源采样与清理 | 三档各40 Radar/100 IR均收到，但各40 Radar全部严格拒绝、0 Bundle/占据/地图；P99不可计算，三档均失败。首次35m/s参数`null`无法写入ROS并保留失败目录，修复仅省略参数服务器副本可选空字段。门限与oracle不变；非正式机载测量 | [预登记及失败记录](../experiments/2026-10-08-perf01a-three-speed-fixture.md) |
| EXP-20261008-003 | 2026-10-08 | 预登记零噪声IR生成候选/三航速实际ROS大图复测 | 跳过无数值作用的零噪声逐像素随机采样，不改消息、时钟和严格配对；验证旧失败是否来自fixture生成 | RED/GREEN及245项轻量测试通过；三档各40 Radar/100 IR收据、20严格采用/20原理由拒绝及20个Bundle/占据/地图闭合，资源、时钟与清理通过。回调→占据P99为49.703/49.834/60.720ms，均未达20ms；仅证明开发机功能闭合恢复，旧失败run保留，正式门禁仍reference_only | [预登记及逐run结果](../experiments/2026-10-08-perf01a-zero-noise-candidate.md) |
| EXP-20261008-004 | 2026-10-08 | PERF-01正式证据预检追加只读审阅/拒绝规则 | 拒绝缺失设备采样时钟身份、NaN/无穷误差及伪装连续性的聚集/倒序样本 | 合成负例RED 7个，修后定向17/17、全仓248/248；原配置`--require-formal`仍reference_only、10项阻塞。自报证据不能证明平台/设备/外部功率计物理来源；未运行机载实测 | [审阅和测试](../experiments/2026-10-08-perf01-evidence-audit.md) |
| EXP-20261008-005 | 2026-10-08 | 70m/s大图ROS可选match-trace/线格式探针 | 在已闭合fixture链上按同帧核对IR生产/传输与matcher锁时间 | 2秒插桩run严格20采用/20拒绝、地图闭合/资源/清理及离线联接通过；回调→占据P99 44.872ms仍超标。最慢帧IR序列化6.184ms、队列/传输/调度混合区间11.618ms、反序列化6.830ms；无探针run的ready-to-encode长尾未复现，不可作A/B性能比较或物理设备结论 | [预登记及同帧记录](../experiments/2026-10-08-perf01a-probe-after-fastpath.md) |
| EXP-20261009-001 | 2026-10-09 | 真实ROS 70m/s 大图 A-B-B-A 与 250 项轻量回归 | IR 回调省去临时列表复制，保持匹配缓存独立所有权与严格 oracle | 四条2秒 run 全部20采用/20原由拒绝并完成地图闭合；A/B 的 P99 中位数54.700/50.416ms，下降7.83%未达预登记10%采纳门槛；默认保持关闭，四次仍超20ms，正式证据reference_only | [预登记及逐run记录](../experiments/2026-10-09-perf01a-ir-decode-copy.md) |
| EXP-20261010-001 | 2026-10-10 | 训练fixture纯函数/ROS编解码与独立2秒功能短测 | 同场景Radar/IR输入和训练专用LiDAR首回波target/mask、运动/外参、图隔离 | 首轮仿真时钟等待互等失败并保留；修后20/20/20 Radar/IR/训练监督实收、20条记录身份对账、端口释放；最终run明确标为fixture来源；定向6项、全仓256项轻量回归通过。不代表真实标定、算法质量或PERF-01验收 | [完整记录](../experiments/2026-10-10-sens-train-01-fixture.md)、[通过证据](../.runtime/runs/sens-train-01-20261010T153539744378/validation.json) |
| EXP-20261010-002 | 2026-10-10 | 双射线训练监督ROS短测与原始PointCloud2受限适配 | 扩展两个障碍/IR热点与遮挡审计；强制fixture字段、采集时钟、单位和Doppler方向显式 | 共面擦边、多射线occupied覆盖和未声明逐点时间字段RED→GREEN；双射线实际ROS各20帧、20条标签逐项oracle、图隔离/清理通过；全仓265项通过。仅受限fixture适配，不是设备驱动或正式PERF验收 | [详细记录](../experiments/2026-10-10-iface01-sens-train-multiray.md)、[最新短测](../.runtime/runs/sens-train-01-20261010T161508228655/validation.json) |
| EXP-20261012-001 | 2026-10-12 | 非零扫描训练fixture纯函数与定向回归 | 确认逐点时间、扫描中点运动补偿、状态插值、无回波unknown及fail-closed边界 | `sens_train_01_motion_fixture.yaml`的两束回波经补偿后占据676/684，一束无回波不改变标签；缺历史、乱序/不完整历史、非法偏移、v0.1非零扫描均拒绝；12项定向测试通过。仅离线功能级fixture，ROS入口仍零时长v0.1，不代表真实时钟/标定、实时性能或对照试验 | [详细记录](../experiments/2026-10-12-sens-train-motion-deskew.md)、[配置](../configs/sens_train_01_motion_fixture.yaml) |
| EXP-20261013-001 | 2026-10-13 | 非零扫描边界与场景矩阵纯函数回归 | 审计运动扫描遮挡、量程、FOV和单/双障碍场景标签合同 | 遮挡后方unknown、量程外无点无free、超FOV射线拒绝；单障碍/双障碍零时长与非零扫描矩阵通过；定向16项、全仓274项通过。仍仅fixture纯函数，ROS入口保持v0.1零时长，不代表真实设备或PERF-01 | [详细记录](../experiments/2026-10-13-sens-train-boundary-audit.md) |
| EXP-20261013-002 | 2026-10-13 | 非零扫描训练记录合同与验证器回归 | 确认无回波射线的时间槽可追溯，并拒绝缺失/不一致偏移、重复射线和畸形点记录 | 新写入样本保存完整`ray_time_offsets_ns`；混合及整帧无回波槽保留但不生成free；定向18项、ROS编解码2项、全仓轻量回归276项通过，旧v0.1零时长记录兼容；未运行ROS v0.2、真实设备或PERF-01 | [详细记录](../experiments/2026-10-13-sens-train-record-audit.md) |
| EXP-20261013-003 | 2026-10-13 | ARS548/Mid-360型号特定设备时间字段合同 | 按已确定型号核对列表级/逐点时间、同步类型来源和训练LiDAR边界；不依赖硬件 | ARS548列表时间组合、逐点时间不可用和Mid-360 `timebase+offset_time`展开通过；仅CustomMsg时同步状态保持未确认；定向8项通过，含genpy常见`__slots__`消息对象。未连接设备、未测跨设备时钟误差、未启动PERF-01或对照试验 | [详细记录](../experiments/2026-10-13-device-time-contract.md) |
| EXP-20261013-004 | 2026-10-13 | 设备时间落盘记录与输入审计纯函数回归 | 固定设备时间/接收时间分离、未映射状态、Mid-360原始包来源和单设备流身份规则 | ARS548与Mid-360记录封装、JSON往返、uint64边界、时间篡改/伪造映射/缺失接收时钟/原始来源缺失/重复样本/混合身份均按预期拒绝；定向13项通过。未连接设备、未运行ROS记录器、未测真实时钟残差或PERF-01 | [详细记录](../experiments/2026-10-13-device-time-record-audit.md) |
| EXP-20261013-005 | 2026-10-13 | 非零扫描训练ROS闭环及零时长入口回归 | 200ms扫描状态/clock双覆盖、逐点补偿、私有JSON落盘/收据/解析几何与图隔离 | 首轮XML-RPC整型超限失败保留；修后motion 22条状态/clock与20组schema v0.2记录闭合，single/multiray各20组回归通过、端口释放；31项定向、300项全仓轻量测试通过。无硬件/实测时钟或模型/性能结论 | [详细记录](../experiments/2026-10-13-sens-train-motion-ros.md) |
| EXP-20261013-006 | 2026-10-13 | 训练几何/运动离线矩阵、覆盖/补偿统计与标签边界修复 | 12场景含35/50/70m/s及偏航、插值、遮挡、无回波；独立几何与Radar/IR输入oracle、落盘回读 | 首轮同表面体素分裂失败保留；修后36记录/102回波（30插值）通过，observed=1.09375%，最大数值补偿残差3.08461e-7m；定向40、全仓309及三个实际ROS入口回归通过。非ROS偏航、实机精度、模型或对照试验 | [详细统计与边界](../experiments/2026-10-13-sens-train-scene-statistics.md) |
| EXP-20261013-007 | 2026-10-13 | ROS训练fixture偏航与扫描内插值 | 新yaw配置；200ms扫描、5个时间槽、20组记录；源状态/clock、ROS Radar/IR、监督JSON、独立几何与标签oracle、图隔离 | 通过：20组schema 0.2记录、22条状态/clock；80回波含20个插值回波，20个无回波槽；补偿最大误差2.72e-15m；source/clock唯一、LiDAR监督仅连接记录器/观察器、进程退出与端口释放通过。失败注入测试覆盖姿态/速度/位置/时钟/尾帧、原始点/补偿点/pose ID/unknown/occupied/图像/Radar篡改。运动学fixture，不是实机时钟、动力学固定翼、模型质量或PERF-01验收；下一步T-14 | [详细记录](../experiments/2026-10-13-sens-train-yaw-ros.md) |
| EXP-20261014-008 | 2026-10-14 | T-14 AircraftState兼容Odometry与唯一TF | state_adapter可选publish_odom/broadcast_tf；有效状态、terminal状态、时间/帧/坐标/未知协方差与清理回归 | 通过：有效状态收到1条`/uav/localization/odom`和1条`odom -> base_link` TF，均为2s采样时间；Odometry pose/twist未知协方差标记保持；terminal后无新增几何镜像；T-14定向5项、旧SIM-01 103项和实际ROS fixture通过，catkin重新配置/构建通过。无实机定位质量、设备时钟、真实协方差或正式PERF-01结论；下一步基础Local Map契约 | [详细记录](../experiments/2026-10-14-t14-odom-tf.md) |
| EXP-20261014-009 | 2026-10-14 | Local Map纯业务单点查询RED/GREEN与全仓复核 | 显式阈值、五类状态、身份/坐标/时间、覆盖范围和只读语义 | 通过：新增6项查询测试先RED后GREEN，127项PERF-01-A回归通过；随后复核全仓326项通过。上一轮320项是在新增6项之前，不作为包含查询测试的计数。尚无ROS查询服务验收，不代表滚动地图或概率融合 | [详细记录](../experiments/2026-10-14-local-map-query.md) |
| EXP-20261014-010 | 2026-10-14 | Local Map ROS单点查询服务RED/GREEN与三模式短测 | 新增MapQuery/MapQueryResult、默认关闭、共享地图实例/锁、五类状态、身份/时间/年龄/未知质量和图隔离 | 通过：消息定向6项、节点定向4项、ROS启用模式30次查询/5条观测/2次快照，关闭模式0次查询仍更新快照，未配置阈值模式不猜分类；338项全仓通过，catkin消息构建通过，旧PERF-01-A真实ROS入口40样本通过。首轮图检查失败因ROS自动公共`/clock`订阅已保留，修正后通过；无硬件、实测设备时钟、功耗、滚动地图、模型质量或对照试验结论 | [详细记录](../experiments/2026-10-14-local-map-query-ros.md) |
| EXP-20261014-011 | 2026-10-14 | 可选基础滚动Local Map单元、独立ROS fixture及旧入口回归 | 观测时刻body定位、整格窗口、重叠/新unknown/移出淘汰、偏航/大位移/边界/断流和查询一致性 | 通过：10项滚动定向、348项全仓轻量测试；滚动ROS 5快照/7观测/20查询与清理、连接图通过，旧三种查询模式和PERF-01-A旧入口通过。首轮ROS样本身份复用失败保留；仅软件fixture，不代表真实资源/设备时钟/功耗、概率累计、正式PERF-01或对照试验 | [详细记录](../experiments/2026-10-14-local-map-rolling.md) |
| EXP-20261014-012 | 2026-10-14 | PERF-01现有70m/s短测同帧尾延迟只读复核 | 既有A-B-B-A四run各自20条闭合样本与最慢root的配对等待/Bundle发送→回调核对 | 4 run各20/20开发机样本高于20ms诊断线；最慢同帧配对23.027—44.439ms、Bundle发送→回调9.390—20.157ms；未运行新ROS或优化，无目标平台/实测时钟/功耗，正式PERF-01和Phase 1仍阻塞 | [详细记录](../experiments/2026-10-14-perf01-phase1-readonly.md) |
| EXP-20261015-001 | 2026-10-15 | IFACE-01设备记录/训练标签离线契约 | 时间来源、逐点语义、同frame流及缺失/越界free、布尔mask拒绝负例；12场景新目录回归 | RED后GREEN：15项设备、49项训练、353项全仓轻量测试，12场景/36记录离线矩阵通过；无真实驱动、设备时钟/功耗、机载性能或模型质量结论 | [详细记录](../experiments/2026-10-15-iface01-sens-train-audit.md)、[新矩阵报告](../.runtime/runs/sens-train-scenes-20261015T094041549226/report.json) |
| EXP-20261015-002 | 2026-10-15 | 已解码设备JSONL回放、训练离轴标签负例与地图RSS软件观察 | 读记录拒绝空/伪造/混用，几何射线裁剪拒绝包围盒内假free，默认关闭的地图进程采样与旧查询回归 | RED后359项全仓测试、12场景/36记录、新滚动ROS(5快照/7占据/20查询、11次地图RSS采样)和旧服务启用/关闭/不猜阈值三模式通过；无目标平台、真实设备、功耗或正式时延结论 | [详细记录](../experiments/2026-10-15-iface-replay-training-ray-m1-resource.md) |
| EXP-20261016-001 | 2026-10-16 | Phase 2 fake Radar/IR 在线软件 fixture 双run及回归 | 无硬件条件下独立复核全像素IR、参数化Radar/IR、严格配对、占位地图与训练LiDAR图隔离 | 两次2秒ROS run各40 Radar/100 IR、20 Bundle/占据/地图，预期20次严格拒绝，功能通过；359项全仓测试通过。开发机P99=47.280481/44.385750 ms，20 ms诊断均未通过；无真实设备/正式PERF-01或完整阶段结论 | [详细记录](../experiments/2026-10-16-fake-radar-ir-phase2.md)、[IR报告](../.runtime/runs/perf01a-async-20261016T103401785264/perf-report.json)、[参数化报告](../.runtime/runs/perf01a-async-20261016T103419004714/perf-report.json) |
| EXP-20261016-002 | 2026-10-16 | IFACE-01 fake Radar值级闭环与SENS-TRAIN-01高度/无回波矩阵 | 原始RadarFrame→采用SensorBundle逐点字段核对；高/低障碍非水平射线与无回波unknown | 联合ROS run通过：40 Radar原始/20采用、100 IR原始/20采用，值级错误为空，预期20次严格拒绝；高度矩阵3场景/9样本通过，垂直无回波3840格全unknown；全仓370项通过。开发机P99=43.322513 ms未达20 ms诊断；无真实设备、模型质量或正式PERF-01结论 | [详细记录](../experiments/2026-10-16-iface-radar-height.md)、[ROS报告](../.runtime/runs/perf01a-async-20261016T132610318324/perf-report.json)、[高度报告](../.runtime/runs/sens-train-scenes-20261016T132005838102/report.json) |

| EXP-20261020-001 | 2026-10-20 | SENS-TRAIN-01完整体素覆盖与短弦标签验收 | 独立正长度线段—体素oracle、正/负斜率短弦fixture、DDA生成和旧ROS入口回归 | 固定步长RED漏掉(9,5,4)后修复；既有12场景/36记录及新增2场景/6记录通过，全仓372项通过；motion/yaw ROS各20条记录且进程/端口清理通过。仅软件fixture，不代表真实LiDAR、模型质量、硬件性能或正式PERF-01 | [详细记录](../experiments/2026-10-20-sens-train-voxel-coverage.md)、[12场景报告](../.runtime/runs/sens-train-scenes-20261020T112741687164/report.json)、[短弦报告](../.runtime/runs/sens-train-scenes-20261020T112742162982/report.json) |
| EXP-20261020-002 | 2026-10-20 | SENS-TRAIN-COV-02体素边界与有限网格裁剪 | 19个固定线段与独立AABB oracle核对；退化线段RED/GREEN；旧矩阵与ROS回归 | 新增2项定向测试涵盖19个边界输入；原遍历器把网格内部零长度线段标为1个cell，入口最小保护后通过；12+2场景/42记录、全仓374项、motion/yaw ROS各20条通过且清理完成。仅软件fixture，正式设备/性能/模型质量仍阻塞 | [详细记录](../experiments/2026-10-20-sens-train-dda-boundaries.md)、[12场景报告](../.runtime/runs/sens-train-scenes-20261020T161515307378/report.json)、[短弦报告](../.runtime/runs/sens-train-scenes-20261020T161515340020/report.json) |
| EXP-20261021-001 | 2026-10-21 | T-13A在线ROS图运行时隔离 | 在线fake Radar/IR占位链路采样运行时ROS图，拒绝空图、缺节点、训练/LiDAR话题或节点；训练图独立回归 | 39项图审计定向测试、在线2秒ROS run和训练图20条记录回归通过；在线7个预期节点齐全、训练/LiDAR话题和节点为空，20 Bundle/Occupancy/Map闭合；全仓379项通过。开发机P99=42.988710 ms仍未达20 ms诊断；T-13完整、真实设备、模型质量和正式PERF-01未关闭 | [详细记录](../experiments/2026-10-21-t13a-online-graph-audit.md)、[在线报告](../.runtime/runs/perf01a-async-20261021T141204023509/perf-report.json)、[训练报告](../.runtime/runs/sens-train-01-20261021T141306656832/validation.json) |

## 3. EXP-20260911-000：研究基础只读检查

2026-09-20 EXP-20260920-002只读分析补充：重算原始事件并运行40次内存微基准，
未改历史文件或启动新ROS试验。结果与测量边界见[PERF-01预算](PERF01_BUDGET.md)。
两次计时代码写入因权限审查超时未执行，本补充只登记定位证据，不增加验收结论。

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
