# Phase 5软件组合场景与需求矩阵

版本：v1；日期：2026-10-29；主责任：integration_engineer；任务：P5-DESIGN-01。
设计交付时状态：已完成（具体设计）；当时P5-SW-01—03均为计划，本文场景尚未执行。
10-29后续实施更新：用户继续后，SW-01已交付[37子例输入/独立预期与实际消息往返](P5_SW01_INPUT_CONTRACT_20261029.md)，
31项新增/全仓805项通过；原设计时点叙述保留，实际组合运行与原生交接仍待SW-02/03。
再后续SW-02已完成[33个A/B实际ROS子例及公开回放](P5_SW02_ROS_COMBINATION_20261029.md)，
216项比较/旧默认入口/全仓813项通过；下一项SW-03实施S09/C，未关闭正式Phase 5。
后续SW-03已完成[S09/C及软件全矩阵交接](P5_SW03_NATIVE_DELIVERY_20261029.md)：
本轮四例与既有A/B收据复核后37例/253事件/95检查点/228项通过，原生八图/清理及全仓819项通过。
C聚合显示另用260s外层安全预算（含两个原生入口），普通子例仍45s；不作为性能结论。
下文保留设计时的计划表述，当前已完成冻结合成软件范围，完整阶段门槛保持。
依据：[总体阶段安排](STAGE_ADVANCE_PLAN_20261027.md)、[需求矩阵](DEVELOPMENT_PLAN.md#7-需求与测试对应)、
[M5公共软件交付](M5_IFACE_SW03_DELIVERY_20261029.md)。
审查与本轮76项既有定向结果见[EXP-20261029-002](../experiments/2026-10-29-phase5-combination-design.md)。

## 1. 问题、范围与交付边界

现有证据主要按模块验收，尚无统一的场景账本证明：同一运行中，传感器断流或感知失效后，
应用能保留占据证据的原时刻、识别过期，同时独立地形层不被错误清除或拿来填充自由空间。
已有M4累计入口与placeholder输出的观测域也不相容，不能把启动文件拼接当作完整融合链。

本批新增对象是测试场景、独立预期、公开接口观察器及测试装配。五层职责、公共消息、
旧入口和默认配置保持；禁止测试预期流入业务节点。设计中的新文件名均为拟新增，
不表示已有命令。实施遇到需要改变公共合同、运行默认行为或跨层依赖时，先补具体方案。

恢复方法为终止该独立测试进程组、保存失败收据、换新run重新启动；不修改原运行会话，
不删除历史目录，不自动重试覆盖失败。真实设备/DEM、模型质量、占据融合、控制闭环、
机载资源和正式PERF-01继续单列；正式Phase 5日期与退出条件不因软件设计完成而改变。

## 2. 真实入口及消费链审计

以下均为本轮源码事实，不能用计划替代。

| 编号 | 源码入口/符号 | 当前事实及组合约束 |
| --- | --- | --- |
| F01 | [inference_fixture.launch](../ros_ws/launch/inference_fixture.launch) | 装配paired感知与M1/query；没有地形，不能宣称现成组合入口 |
| F02 | [perf01a_source_node.main](../ros_ws/src/uav_fusionmap_simulation/scripts/perf01a_source_node.py) | 发布AircraftState/clock，默认20Hz；启动只等sensor/perception/mapping，未等待地形订阅就绪 |
| F03 | [perf01a_sensor_node](../ros_ws/src/uav_fusionmap_sensors/scripts/perf01a_sensor_node.py) | 经状态适配、时钟门控及build_sensor_bundle；IR缺失时无Bundle，不会自动生成感知unavailable |
| F04 | [StateClockGate.consume_clock](../sensors/ufm_sensors/clock_gate.py) | clock回退锁定并清pending；重新增长不能解除锁定 |
| F05 | [PerceptionEngine.process](../perception/ufm_perception/engine.py) | 不可信上下文先拒绝；可信后端/输出错误才转换为unavailable，二者不能合并计数 |
| F06 | [placeholder_infer](../perception/ufm_perception/placeholder.py) | 只把Radar点转成fixture_radar_point占据；无逆观测free域、无真实IR融合质量 |
| F07 | [create_map](../mapping/ufm_mapping/factory.py)、[validate_fixture_observation](../mapping/ufm_mapping/m2_contract.py) | M2/M3/M4显式选择；要求m2_explicit_inverse_fixture_v1，不直接接placeholder |
| F08 | [SparseLocalMap.update/query](../mapping/ufm_mapping/local_map.py) | unavailable不提交；query按调用方时间/max_age判断，未配置阈值则unknown；不验证调用方时间是否超过实际clock |
| F09 | [perf01a_map_node](../ros_ws/src/uav_fusionmap_mapping/scripts/perf01a_map_node.py) | query直接调用地图业务；clock回调主要用于可选诊断，不提供与TerrainProvider等价的服务存活门控 |
| F10 | [MapQueryClient](../application/ufm_application/query_client.py) | 校验回显/质量并转换传输异常；transport同步调用，本身没有墙钟调用期限 |
| F11 | [TerrainProvider._gate/query](../mapping/ufm_mapping/terrain_provider.py) | 独立clock来源/1s墙钟超时/注册/请求时间门控；ROS只启动安装一版，无公开更新服务 |
| F12 | [TerrainClient](../application/ufm_application/terrain_client.py)、[TerrainQueryTransport](../ros_ws/terrain_query_transport.py) | 1.5s状态存活、实例/revision整组pin、至多16中心；一个未结束worker，发现2s/调用1s期限；超时不等于取消 |
| F13 | [TerrainRecorder/replay_recording](../mapping/ufm_mapping/terrain_recording.py) | 每个接收clock计事件，总64事件；来源细错/无返回query等v1不可表达则incomplete；回放真正执行Provider |
| F14 | [sensor_scene_run](../ros_ws/sensor_scene_run.py) | 独立Gazebo静态飞机/功能级Radar/IR与标准RViz；未接PX4飞行或地形地理注册 |
| F15 | [运动测试](../tests/test_perf01a_motion.py)、[Scene测试](../tests/test_m4_scene_map.py) | 已有非单位姿态/35、50、70m/s及非零map←odom合成样例，可复用输入语义，不能借其通过宣称新组合已执行 |

`SENSOR_INTERFACE`关于断流后stale/unavailable的系统目标仍成立；现有M1服务仅在请求时间
推进时老化，不能推导它已在墙钟停流时主动失效。组合观察器必须分别记录业务新鲜度和传输存活。

## 3. 三种显式配置

| 配置 | 实际业务链及拟新增测试装配 | 可作结论 |
| --- | --- | --- |
| A / paired-M1-terrain | simulation fixture状态/clock → sensors真实fixture构造/适配 → 既有perception → M1 → 公开应用查询；TerrainProvider并行只接同一个clock；拟新增测试源时序控制/观察器 | 功能级全层传递与独立失败传播；无真实模型、飞行动力学或累计地图结论 |
| B / inverse-M4-terrain | 测试专用显式逆观测生产者 → 既有M4 → map查询；地形并行。独立master/run，禁止同时启动A的地图/占据生产者 | 累计、历史所有权、地形隔离；未经过Radar/IR感知，不能列为完整传感器链 |
| C / native-view | 既有Gazebo/RViz场景作为兼容基线；独立地形窗口使用自身fixture基准或单独recorded窗口 | 场景、Radar/IR、地图及地形可查看；没有共同地理注册时禁止叠在同一场景当真实高程 |

A默认paired，异步matcher不混入本批确定性输入预期；以后扩展异步必须另列配对/等待/迟到预期。
每次仅一个clock发布者、一个状态权威、一个地图服务所有者；run/clock在启动前显式绑定。
同名map frame和相同run/clock不证明地形、Scene Map与Gazebo共享水平/垂直基准。
本批不增加TF权威、不用单位变换补未知注册。

新测试源先等待订阅者与地形节点的配置就绪，再发第一个clock；不能等待CURRENT才开始发clock，
否则启动安装互相等待。发布后由只读观察器确认相关样本/状态，再推进下一业务时刻。
ACK仅供测试源调度，不进入生产业务；不得为赶超时而删除必需订阅关系。

## 4. 输入与独立预期先冻结

P5-SW-01拟新增`tests/fixtures/p5_combination_inputs.json`及
`p5_combination_expectations.json`；场景ID、单位、事件序号、run模板、注入位置、合法域、
逐阶段预期身份/状态/证据时刻/版本变化与可观测缺口分开保存。运行器只读inputs，
比较器只读expectations及实际公开收据；禁止生产类、codec或待测输出反向生成expected。
样本生成工具可复用公开合同，但预期坐标/时间/分数由独立算式产生并先持久化。
实施时对新保存的公开消息输入/收据做实际生成类型序列化往返，不以mock代替线格式。

以下数值是本设计的独立预期种子，不是本轮运行结果：

| 对象 | 冻结输入/算式 | 预期 |
| --- | --- | --- |
| A网格 | origin=(-16,-8,-4)，resolution=(0.5,0.5,0.5)，shape=(64,32,16)；固定odom点(1.25,4.25,0.25) | floor((point-origin)/resolution)=(34,24,8)；中心与原点方向逐轴核对 |
| A分类 | 显式free=0.3、occupied=0.7；placeholder有点概率0.9 | occupied；无证据cell为unknown。A不制造free；五类含free的检查放B |
| A年龄 | 最后合法观测150,000,000ns；query max_age=100,000,000ns | t=250,000,000仍fresh，250,000,001为stale；查询不增加revision或刷新证据时刻 |
| 位姿误差 | v=35/50/70m/s；年龄5ms/10ms | 距离预算分别0.175/0.35、0.25/0.5、0.35/0.7m；不能强求同一cell |
| 同步门限 | Radar/IR差5,000,000ns与5,000,001ns；pose_age 10,000,000ns与10,000,001ns | 边界内可接受，超界拒绝；缺IR不变成空free观测 |
| B注册 | 沿用M4显式T_map_odom平移(32,0,0)，odom点(8.25,0.25,0.25)，Scene origin=(0,-16,-4)，resolution=0.5 | map点(40.25,0.25,0.25)，Scene index=(80,32,8)，不能套A索引 |
| B概率 | 独立先验1/2，occupied似然3/4，free似然1/4，单元未触发限幅/TTL | 两次occupied名义9/10；再一次free回3/4；重复sample不再累计；本行不代替M3区间oracle |
| 地形空间 | 沿用M5的2×2 affine与平移(10,-20,3)，不与A/B配准 | map中心(111,179)、(113,179)、(111,177)、(113,177)；高度13、14、no-data、1m |
| 地形质量 | 源高度界[9.75,10.25]加注册偏移界[2.9,3.1] | 第一高度绝对界[12.65,13.35]m；编码向外包络，按既有float64规则比较；不是概率/置信水平 |
| 地形时间 | 为新组合输入显式声明eligibility=[100,000,000,1,500,000,000)，registration=[0,3,000,000,000)ns | 首个安装时刻100ms；evaluation=1.5s时stale，3s时unavailable且无高度；绝不在运行中自动延期 |

地形source acquisition=10、publication=20ns继续属于dataset:m5-fixture域，不能乘倍数当run时间；
只在新副本中改注册/run授权区间和对应身份，原纳秒级M5样例、历史记录均保留。
质量缺失、零高/负高及no-data沿公共flags区分，任何缺失不得补0或借用占据概率。
M3区间/Scene生命周期采用已保存分数案例独立选取并在SW-01列出逐事件预期，不能只比名义概率。

## 5. 组合场景、故障与证据矩阵

所有S01—S09当前状态均为计划。每个子例独立run，失败不靠自动换种子重试掩盖；
同一场景内需要连续历史的事件不得拆run。下列“保持”均须由前后公开收据逐值证明。

| ID / 配置 | 调度与注入 | 独立预期与新增联合证据 |
| --- | --- | --- |
| S01 / A | 正常状态/clock/Radar/IR，先完成100ms地形安装，再确认150ms占据种子 | 同run时钟身份可追溯；M1 occupied和地形13m各自正确；域外占据unknown/no-data无高度；查询任一层不改变另一层revision/证据时间 |
| S02 / A | 150ms种子后停IR，状态/clock继续，到250ms及+1ns查询；400ms恢复IR | 原始Radar继续、无新Bundle/occupancy；地图原revision/150ms时刻保持并越界stale；地形仍current；400ms新合法观测恢复，不能补发gap自由空间 |
| S03 / A变体 | 在可信Bundle后的测试后端注入坏输出、异常、慢任务；另例注入不可信身份；使用既有测试worker政策，不启用research | 可信失败产生空载荷unavailable，不可信输入无业务输出；M1不提交且地形不受影响；慢任务busy/超时/迟到不覆盖恢复帧。须保留传感器链，不能直接复跑P3手工Bundle脚本冒充S03 |
| S04 / A | 子例一：停clock包并等待墙钟；子例二：持续发送相同时间；子例三：clock回退，再恢复增长；子例四：业务clock跨1.5s/3s时效边界 | 停包≥1s地形unavailable；相同时间包仍有传输存活但不推进业务年龄；回退锁住状态门控/地形直到新run；到期按第4节分别stale/无高度。旧M1对旧查询时间可仍fresh，必须如实记录，不声称它自动清图或reset |
| S05 / A运动变体 | 测试源选既有make_motion_state/make_motion_radar语义；35/50/70m/s精确pose与5ms旧pose，另测5ms/10ms及+1ns门限 | 实际链携带变换、采样时刻与索引对独立数值；地形与运动不建立伪配准；超界拒绝只影响相应Bundle/占据，地形不依赖pose。非飞行轨迹/20ms性能验收 |
| S06 / B | 显式逆观测占据/重复/滚动封存/重入free/TTL；期间停止地形服务 | M4唯一所有权、原质量/证据时间/淘汰按冻结事件表；非零注册map查询含五类状态；地形失败不改Scene概率或所有权。逆观测生产者必须标测试来源 |
| S07 / A及B分例 | 独立停地图服务、停地形服务；地形测试服务延迟返回/进程重启，与占据正常输入交错 | 应用无free fallback；地形期限与单worker/旧实例迟到丢弃、整组pin对公开收据；地图调用由测试子进程隔离设外部期限，阻塞则报告能力缺口，不宣称旧客户端已有deadline |
| S08 / A短记录 | 20Hz有限窗口，只录完整支持的地形事件；并行收占据回放记录；另一子例故意超过64或注入v1不可表达故障 | 两种协议分别真正执行并逐值比较；共享外层场景索引，不拼成单一协议；篡改合法外形expected必须失败；超限/不可表达保持incomplete，不能截尾变complete |
| S09 / C及装配 | 启动前冲突clock发布者/缺订阅者/坏身份；正常与注入失败后统一退出；新run重开并查看原生窗口 | 图审计阻止错误装配；失败证据保留、仅本run进程组清理；新run不继承旧map/实例pin；Gazebo/RViz Radar/IR/占据及独立地形/recorded画面可辨，禁止未注册叠加 |

S02按paired的“无Bundle”判定；若未来采用异步配置，应按其真实matcher决定账本重新冻结，
不能拿paired的事件计数当异步预期。S03/S07测试替身只在tests注册，使用真实生成消息与ROS传输，
不变成可部署research后端。S06的地形故障只用停服务，不调用不存在的安装服务；
全部M4业务/查询安排在既有[0,1s)注册窗口内，地形到期边界另在S04验证，避免同时失效混淆原因。

## 6. REQ-01—14覆盖与未关闭项

| 需求 / 原测试标识 | 本批场景 | 软件验收对象 | 仍未覆盖/暂缓 |
| --- | --- | --- | --- |
| REQ-01 / T-01 | S01、S03、S09 | placeholder/disabled工程失效、无权重/GPU依赖；research不可用且无fallback | 真实模型运行 |
| REQ-02 / T-02 | S01、S03、S07、S08 | 实际线格式、flags/质量/身份、坏输出与跨层隔离 | 真实设备字段/质量来源 |
| REQ-03 / T-03 | S05、S06、S09 | 非单位姿态、具名非零注册、不同基准不可混用 | 实机外参、Gazebo/DEM共同注册 |
| REQ-04 / T-04 | S02、S04、S05 | 采样/请求/evaluation/墙钟分别保存，严格边界与reset | 跨设备时钟映射、真实扫描补偿 |
| REQ-05 / T-05 | S01—S08 | 未知/no-data/无输出/不可用不转free；旧证据不刷新 | 真实遮挡/无回波检测质量 |
| REQ-06 / T-06 | S03仅工程失效子项 | 失效原因与恢复可追踪 | 真实融合质量与模态贡献按用户要求暂缓 |
| REQ-07 / T-07 | S01、S06、S09 | 实际节点/话题/导入边界，无业务旁路 | 无新增跨层许可 |
| REQ-08 / T-08 | S02、S04、S06 | latest与累计分开，去重/老化/封存/淘汰联合证据 | 实际输入、RSS/机载上限与动态重注册 |
| REQ-09 / T-09 | S01、S06、S07 | 五类占据状态、独立地形状态与实例pin；传输缺口披露 | 规划避障/控制闭环 |
| REQ-10 / T-10 | S08、S09 | 先冻结输入/预期，收据重放、失败/清理可追溯 | 外部独立备份/恢复验收ENV-03 |
| REQ-11 / T-11 | S04、S05、S09仅功能子项 | 速度下坐标/年龄与失败隔离、有界调度/清理 | 正式PERF-01、持续运行/功耗/硬件实时性 |
| REQ-12 / T-12 | S01、S02、S04、S06、S08仅独立地形子项 | no-data、到期、基准与占据互不改写 | 真实DEM、占据辅助更新及更新效果 |
| REQ-13 / T-13 | S01、S03、S06、S09 | 在线图无LiDAR/target/observed_mask订阅或forward字段 | 训练质量另验，不启动训练 |
| REQ-14 / T-14 | S04、S05、S09 | AircraftState权威/观测时刻SpatialContext，唯一动态TF职责 | 实机定位质量、同run独立epoch/reset能力 |

该矩阵是提前推进的软件验收设计，不关闭原T-01—14完整需求；原正式Phase 5的高速转弯、
复杂环境/遮挡和感知质量场景仍待相应输入，不列入本轮重试队列。

## 7. 有界证据、时序与失败处置

拟用新目录`.runtime/runs/p5-combination-<时间戳>/`，每个场景子目录保存输入副本、
独立预期副本、实际环境/参数/命令、图连接、公开输入输出收据、故障请求/确认时刻、
逐条比较、日志与清理结果。记录代码分支及dirty清单，不计算无消费者Hash，不覆盖旧产物。
测试控制台可以观察原始话题供核对，application进程仍只消费公开地图/地形合同。

每个普通子例业务时长≤3s、外层墙钟≤45s、启动就绪≤15s、排空≤5s、清理≤5s，
超时即失败；这些是测试调度预算，不是设备性能指标。clock/故障/查询均带事件ID和
相对单调接收时间，业务时间保持整数纳秒。1ns边界以离散消息事件驱动，不依赖sleep精度。
同一时刻跨进程回调顺序不能假设；涉及提交或安装时由观察器确认，再查询。

测试层每话题最多256条公开收据、合计16MiB，超限停止并标场景证据不完整；
不把此上限写成公共协议或RSS上限。子例实际发包数先在SW-01计算，不能运行时静默抽样。
地形公共记录继续64事件/4MiB/单条64KiB，所有clock与状态变化也计入；
S08选20Hz、0.5s窗口，预留最多10 clock、1来源操作、1安装、4查询、16状态变化及1停用，
总预算33事件，实施按实际首尾事件规则冻结并核对≤64。不能把2s/100Hz完整记录塞入此协议。
需要更长记录时另审schema，不能切段拼接生命周期或丢clock后仍报complete。

地形实例ID运行时产生：预期使用具名符号绑定首个实际实例，后续逐值固定并检查切换；
不得无条件忽略实例字段。原revision与质量/time保持，playback_session_id仅标回放会话。
注入顺序与响应乱序分别记录；迟到结果不得“修复”当时失败收据。
收据、比较、图审计、清理任何一项失败，场景即失败；窗口截图通过只代表显示检查。

## 8. 后续实施工作包

| 次序 | 主责任 | 拟修改范围 | 进入下一项前的交付 |
| --- | --- | --- | --- |
| P5-SW-01 | tester | tests的小型输入/独立预期/schema校验与真实消息往返；不新增业务节点 | 冻结九场景全部子例/事件/预算、独立数字及反例；生成消息往返；无运行器也能核查expected不依赖生产输出 |
| P5-SW-02 | integration_engineer | tests专用源/故障装配与观察器、ros_ws显式测试运行器/launch；复用生产公开入口 | A/B的S01—S08实际ROS联合收据/比较、占据与地形分别执行回放；阻塞调用只在测试子进程期限内隔离；默认入口保持 |
| P5-SW-03 | tester | 图/清理/新run与原生窗口验收脚本、中文交付与报告素材 | S09与全矩阵交接、Gazebo/标准RViz像素检查、受影响旧入口及全仓轻量回归；逐项披露未执行/失败 |

SW-01先实施，不在缺真实数据时回到质量研究；各步先读涉及目录AGENTS并核对真实入口。
本轮只有本设计、实验记录、ADR及状态/索引更新；未新增上述JSON/运行器/launch，
未启动ROS、Gazebo、训练或模型。实际验证仅为既有76项定向和文档一致性检查，
上轮774项全仓及ROS/RViz属于历史基线，本轮不重新标记为新组合验收。
