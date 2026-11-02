# 运行配置与兼容入口

日期：2026-10-28；责任角色：integration_engineer；状态：软件配置与显式fixture范围。

## 配置来源

报告用原生RViz入口为`ros_ws/report_rviz_run.py`，布局为`configs/report_rviz.rviz`；
默认独立demo明确使用M4 fixture完整配置，live须显式master/clock/TTL，replay须公开收据。
阈值不配置时视图保持unknown，不为着色补算法参数。GUI专用系统Qt/TIFF选择仅在子进程，
配置/缓存隔离到新run，不修改原Conda或旧ROS入口。实际命令、图层/查询/导出及报告素材见
[ROS_VISUALIZATION](ROS_VISUALIZATION.md)，验收范围为工程可视化。

| 配置 | 消费者 | 规则 |
| --- | --- | --- |
| `configs/perf01a_async.yaml` | 业务场景测试、异步runner与其节点 | 同一个`load_profile()`执行defaults → 场景 → 显式CLI覆盖的深合并；runner保存有效profile到新run的scenario.json |
| `configs/local_map_fixture.yaml` | 感知与地图ROS节点 | 同一个`runtime_config.map_settings()`读取；`/ufm_local_map_config`可选定文件，显式节点私有参数覆盖同名字段 |
| `configs/m2_fixture.yaml` | M2-SW-01/02/03/04测试专用合成输入、oracle和固定/滚动候选参数 | 明确fixture_only且默认关闭；仅显式离线运行器或私有m2_fixture ROS选择启用，旧launch仍为latest |
| `configs/m3_fixture.yaml` | M3显式区间profile、完整M2算术子配置与示例输入范围 | fixture_only且默认关闭；显式工具、固定/滚动M3类及私有ROS选择读取 |
| `configs/m4_fixture.yaml` | M4测试工具、checker、Scene候选与显式ROS/回放 | 完整M3子配置、固定合成map←odom注册、单网格Scene几何与K上限；默认关闭，显式选型且完整配置/run/clock/rolling必需 |
| `configs/sim01_state.yaml` | SIM-01源与状态适配 | pending及墙钟等待按原配置；`identity_history_limit=1000`限制各接收流身份历史 |
| `configs/sens_train_01_*.yaml` | 训练专用启动图 | 独立保存监督配置；不进入在线启动图 |
| `configs/perf01_budget.yaml` | 性能预算与正式门禁 | 工程参考预算；不作为已经达标的机载默认参数 |

共享地图配置明确XYZ分辨率、shape、odom origin、map_id、老化时限和cell上限；
感知输出和地图实例均接收这些显式值。disabled/research失效输出使用同一几何，
不会退回另一个默认网格。两个节点将最终配置写入各自`~resolved_map_config`；
独立入口验收把两者写入validation.json并检查一致。
直接调用纯业务API时仍保留原函数默认值，兼容已有离线测试；ROS运行由共享文件装配。
旧性能/运动实验oracle仍针对其具名网格，不能改网格后直接沿用旧验收结论。

异步CLI未传入speed/pairing时保留场景配置；显式`--speed-mps 0`仍覆盖场景航速。
旧`--full-ir`、探针和候选选项保持兼容，新入口不依赖这些选项。
共享地图文件拒绝未知字段和不支持版本；几何有效性继续由对应业务入口检查。

## 启动与验证

独立软件fixture（1秒采样、公共查询、关闭诊断、不需要实验观察订阅者）：

```bash
bash ros_ws/sim01_env.sh python ros_ws/local_map_query_run.py --mode inference --port 11591
```

其启动装配为`ros_ws/launch/inference_fixture.launch`，运行时只有Radar/IR输入、
状态、感知和地图链路；不启动训练LiDAR、PX4或研究forward。运行器创建独立Master、
新run目录，源结束后通过公开服务验证地图，并清理本次进程和端口。
查询消费者缺席时地图节点也能ready；关闭的诊断话题不作为启动依赖。
本入口是paired软件fixture，不代表独立设备频率、感知质量或20ms实时验收。

旧`perf01a_run.py`、`perf01a_async_run.py`、查询/滚动fixture和训练入口保留。
旧实验图默认启用诊断及观察者就绪检查，保证已有采样/计时口径可复现；
新入口显式设置`/ufm_diagnostics_enabled=false`、`/perf01a_require_observers=false`。
`ros_ws/perf01a_ros.py`只转发契约包中的事件函数，不再维护第二份实现。
静态源状态fixture统一归simulation，tests可调用公开fixture，sensors不反向导入simulation。

## 身份历史与失效

State/IMU时钟门控共用有界身份历史。窗口内保留完整内容以检测重复和冲突；
超过上限按采样时间淘汰最旧条目，淘汰水位及更旧时间的输入一律拒绝，
已丢弃或超时样本不能因历史淘汰重新进入等待队列。终止消息独立保留并优先传播。
窗口外不承诺识别“旧sample_id改成未来时间”的全部冲突；生产者仍须遵守run内身份唯一。
这验证数据结构上限，不是机载RSS、功耗或长期飞行验收。

业务消息沿用0.1及原字段；未知版本/枚举拒绝，不能用非零值代替available判断。
同格Radar点聚合为单个fixture体素，概率仍为0.9，不累计为更高置信度。
已成功解码的输入遇到后端异常，输出保留身份/时刻的空unavailable占据；
不能可信解码的消息仅诊断拒绝，不能用其无效上下文制造业务观测。

## 兼容与恢复

P3-SW-01/02新增统一`PerceptionEngine`，ROS回调只解码、调用并编码发布，
可信输入失败输出明确unavailable；不可信身份/上下文仅诊断拒绝。
同输入绑定的后端输出必须通过身份、时空、几何、体素及质量合同校验。

`~worker_enabled`默认false；开启时必须显式提供正数`~worker_deadline_s`。
该CPU执行器1个活动任务、0等待任务，deadline使用单调墙钟且包括spawn启动成本；
忙碌新帧返回`perception_backend_busy`，较旧活动结果丢弃；超时终止子进程并返回
`perception_backend_timeout`，崩溃返回`perception_worker_exited`。关闭节点时清理worker。
该选项不提供GPU取消承诺，也不能替换既有同步/正式性能指标。
CPU进程/节点回调及独立ROS故障恢复图已通过，旧入口和三模式兼容通过，详见
[软件交接](../experiments/2026-10-27-p3-m1-app-handoff.md)。GPU中断和真实模型仍未验证。

## 占据回放与应用查询

M2-SW-01可用`bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m2_fixture_run.py`
生成独立输入/预期产物。运行器校验配置及固定单位变换的合成占据、执行现有ROS消息
编解码往返，并保存分数oracle预期；不启动ROS Master或概率地图。
默认9场景/31消息已通过，配置、合同及独立预期见
[EXP-20261027-007](../experiments/2026-10-27-m2-fixture-oracle.md)。

M2-SW-02的`FixedProbabilityMap(spec, run_id, clock_id)`是独立显式候选，复用M1公开
快照/查询而不调用覆盖更新；SW-04后ROS可显式选择。固定网格log-odds逐观测累计，
质量保持不可用，query年龄取min(客户端max_age, evidence_ttl_ns)。
可用冻结产物执行离线对账：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m2_fixed_run.py --input .runtime/runs/m2-fixture-20261027T144245043459/fixtures.json
```

该命令实际执行固定合成累计，直接比较保存的oracle预期，不重算期望；不启动ROS。
9场景/31观测已通过，详见[EXP-20261027-008](../experiments/2026-10-27-m2-fixed-map.md)。
基本去重、水位和TTL重启已实现。

M2-SW-03的`RollingProbabilityMap(spec, run_id, clock_id)`复用固定候选累计与查询，
仅显式调用才启用整格odom滚动。body位姿使用观测时刻的有效刚体变换；观测网格origin
必须与配置同格点。重叠cell与内部累计值一起迁移，移出一起淘汰。空帧移动只更新覆盖
revision，不刷新证据时间；早于最新窗口移动时间的查询返回unavailable。
固定候选仍要求原固定origin和单位body变换，默认ROS配置仍使用M1 latest。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m2_rolling_run.py
```

此命令新建独立run，保存配置、3组运动场景/15条观测的预期与逐帧查询/快照，
并检查40条序列的cell/L/身份限额；只执行ROS消息编解码，不启动ROS Master。
已通过证据见[EXP-20261027-009](../experiments/2026-10-27-m2-rolling-time.md)。
SW-04实际ROS候选图、公开占据回放及应用兼容交接已通过，旧M1回放入口仍默认latest。

`perf01a_map_node.py`私有参数`map_backend`默认`latest`，该分支不导入M2候选。
显式`m2_fixture`必须提供`m2_fixture_config`路径及`clock_id`；`rolling_enabled`
选择固定/滚动候选，其余地图/阈值参数只取该配置，不允许节点私有散布覆盖。
未知后端、缺配置/clock或仅给M2配置却仍选latest均失败，不自动fallback。
`m2_fixture.launch`仅为显式合成入口，不接研究模型或原placeholder概率。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/m2_stage_run.py --port 11641
```

该命令新建隔离Master、map和fixture检查器，保存配置、输入/快照/查询、图及清理收据，
随后用独立CLI按原顺序回放实际占据收据，完整比较快照/查询与接受/拒绝结果。
独立回放需显式追加`--map-backend m2_fixture --m2-fixture-config FILE --clock-id CLOCK`，
滚动候选还需`--rolling`；ROS运行器已记录可复现命令。15观测/9快照/14查询、五类状态
和旧固定/滚动/placeholder入口通过，见
[EXP-20261027-010](../experiments/2026-10-27-m2-ros-handoff.md)。
这里是软件fixture，不是研究概率校准、设备质量或正式性能证据。

M3-SW-01可显式生成合成输入与独立分数预期：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m3_fixture_run.py
```

10个具名默认场景/43条观测已通过真实消息序列化往返；保存config.json、fixtures.json
及report.json，明确`map_accumulation_executed=false`。候选contract只在测试工具显式
调用，不加入默认包入口或现有ROS节点。M3输入来源为bounded_inverse，累计预期来源为
bounded_accumulator；均不表示真实概率校准。float32名义概率与float64区间的舍入检查
按profile约定执行，未扩展公共字段。证据见
[EXP-20261027-012](../experiments/2026-10-27-m3-fixture-oracle.md)。
SW-02已实现`FixedIntervalProbabilityMap(spec, run_id, clock_id)`，只有显式调用才创建，
名义累计复用M2暂存构造路径，端点L与均值L按cell一起暂存/淘汰，缺失质量锁存。
SW-02当时只支持显式类调用；SW-04已增加共享factory和ROS私有m3_fixture选择，默认仍latest。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m3_fixed_run.py --input .runtime/runs/m3-fixture-20261027T163801864738/fixtures.json
```

该离线运行器直接读取SW-01保存的输入、旁置config.json和预期，不导入或重算oracle；
新run保存结果，对比名义概率/区间/质量可用性/状态/时间/revision，并检查实际快照/查询
消息序列化。10场景43输入及与M2名义值逐值对比通过，见
[EXP-20261027-013](../experiments/2026-10-27-m3-fixed-map.md)。
SW-03已新增`RollingIntervalProbabilityMap(spec, run_id, clock_id)`，共享M2滚动准备和
固定M3累计构造，只有显式创建才启用；ROS装配见后述SW-04入口。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m3_rolling_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m3_rolling_run.py --input .runtime/runs/m3-rolling-20261027T174748991457/fixtures.json
```

首条命令在创建地图前保存独立算术及显式几何预期；第二条只读保存输入/预期重放，
不导入oracle。各case完整配置、输入、预期及探针在fixtures.json，bounded场景的
cell=2、identity=3覆盖参数也保存其中。96帧257查询4探针及五类查询状态通过，
证据见[EXP-20261027-014](../experiments/2026-10-27-m3-rolling-time.md)。
上述SW-01—03命令均为离线消息序列化，不启动ROS Master或模型。
SW-04显式M3合成ROS运行及公开回放入口已验证：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/m3_stage_run.py --port 11651
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/local_map_replay.py --input .runtime/runs/m3-stage-20261027T183857889507/receipts.json --run-id m3-stage-20261027T183857889507 --clock-id sim:m3-stage-20261027T183857889507 --map-backend m3_fixture --m3-fixture-config .runtime/runs/m3-stage-20261027T183857889507/m3-config.yaml --rolling
```

监督器先检查端口空闲，保存配置/launch副本，新建独立Master及run，验证后清理自身进程。
私有`~map_backend`默认latest；显式m3_fixture必须提供`~m3_fixture_config`和`~clock_id`，
`~rolling_enabled`仍须boolean。M2/M3配置不可混用，候选参数只能来自完整配置，
不能靠私有threshold/map几何参数覆盖；选型/配置/输入失败不fallback。
回放CLI增加`--m3-fixture-config`，同样拒绝混用及未选择后端的配置；保留输入顺序和
完整区间元数据，核对快照/查询与拒绝结果，不刷新证据或改写原收据。
应用增加独立质量检查，保留合法未知kind及历史载荷；区间按精确包含或float32舍入映像
核对，非法响应为unavailable。五类状态/缺失传播/TTL恢复与旧入口证据见
[EXP-20261027-015](../experiments/2026-10-27-m3-ros-handoff.md)。
M3合成软件工作包完成；后续M4设计/输入工作包见文末，真实质量和资源验收仍独立。

`ros_ws/local_map_replay.py --input FILE --run-id RUN`只读既有占据receipts，
使用共享fixture地图配置；`--rolling`显式启用滚动，分类阈值需成对显式提供。
每次新建地图及独立输出目录，保留接收顺序，不能用一个实例自动跨run继承。
查询按记录revision重建版本，核对完整响应，不复现墙钟线程交错。

`ros_ws/map_query_client.py`是应用独立CLI，消费既有`/uav/map/query`，请求必须提供
run/clock、同域纳秒时刻、XYZ点及最大年龄。连接已有隔离Master的示例：

```bash
bash ros_ws/sim01_env.sh env ROS_MASTER_URI=http://127.0.0.1:11625 /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/map_query_client.py --run-id RUN --clock-id sim:RUN --timestamp-ns 200000000 --max-age-ns 50000000 --point 8.25 .25 .25
```

上例需把RUN替换为当前服务运行身份，Master与地图服务必须仍在运行；
程序原样保留五类状态/质量，服务缺失输出unavailable且退出码1，不等同free。
服务发现墙钟等待2秒，尚不提供对已连接却持续无响应服务的端到端deadline。
`local_map_query_run.py --mode enabled --application-client`可独立启动软件验收图，
包含公开查询五状态和CLI/缺失服务检查；该选项默认关闭。

NumPy接收、TCP_NODELAY、IR借用继续作为默认关闭的历史实验候选，相关命令和结果保留。
不把它们加入独立入口或将其未达采纳门槛的结果写成性能收益。
40ms deadline、5ms同步及20ms正式目标不变；端点和配对预算仍待独立确认。
需要恢复旧实验运行图时使用原runner；不删除旧run、不修改研究仓库或环境。

M4-DESIGN-01已交付[固定合成注册/有界子地图方案](M4_SOFTWARE_TRIAL_PLAN_20261027.md)，
用户后续确认具体软件范围，SW-01已创建configs/m4_fixture.yaml与纯输入checker，
SW-01时只由显式测试工具读取；SW-04后共享工厂/ROS/回放可显式选择m4_fixture，见文末。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m4_fixture_run.py
```

该命令保存完整配置和8场景/41输入/52查询预期；无Scene/累计/ROS Master执行。
根配置的registration绑定具名fixture run/clock，工具复制并为每case显式重绑定，
每case完整配置保存在fixtures.json。valid_from_ns/valid_until_ns为左闭右开纳秒区间；
T_map_odom声明从odom到map的非零整格平移，缺注册、错域、超时、旋转/非整格拒绝。
有效观测检查body导出的完整活动窗口，不只检查非空voxel；nonvalid不使用占位变换移动窗口。
checker无状态，不检查事件去重/迟到或实现目录；这些仍由SW-02/03候选对保存预期验收。
测试专用轨迹有具名固定算术/几何前提，--config不能静默改变问题后继续套用旧预期；
不满足表前提的合法配置也明确报错，修改场景需另写独立预期。
真实消息序列化检查仅验证输入与预期载荷的承载，不能算M4算法通过。
证据见[EXP-20261028-001](../experiments/2026-10-28-m4-fixture-contract.md)。

SW-02已新增显式`mapping.ufm_mapping.scene_map.SceneMap(spec, run_id, clock_id)`业务候选
（按当前PYTHONPATH导入为`ufm_mapping.scene_map.SceneMap`），SW-02时不在factory或ROS注册；默认包入口不导入候选。
直接读取保存输入/预期的独立运行器已验证：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m4_scene_run.py --input .runtime/runs/m4-fixture-20261028T093615412726/fixtures.json
```

该命令不导入oracle/轨迹生成器，创建新输出目录，按接收顺序核对所有快照/查询与预期
fused/not_fused/rejected、Scene所有权/FIFO及原证据/结构时刻；再检查实际消息序列化。
浮点累计与独立分数答案的绝对容差为1e-12；wire概率/confidence先按float32映像比较，
身份/时间/来源保持精确。候选只用活动M3公开update/snapshot，封存目录不反灌旧累计值，
新missing不能借旧quality；临时完整状态验证后一次提交，不续接跨run缓存。
8场景41输入52查询和15项新增/M4共39项/609项全仓通过，见
[EXP-20261028-002](../experiments/2026-10-28-m4-scene-candidate.md)。
SW-02未启动ROS Master；后续SW-03组合与SW-04实际ROS证据分别列在下文。

SW-03已完成离线组合与测试侧资源探针，不改Scene/M3源码、工厂或ROS：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m4_time_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m4_time_run.py --input .runtime/runs/m4-time-20261028T104242817551/fixtures.json
```

第一条在候选执行前保存3组显式时序状态表与120帧周期轨迹的独立预期；第二条只读保存
答案，不导入oracle或重算答案，仍新建输出目录。两者均验证140帧323查询、4个后段故障点、
1个新run/clock/注册期限隔离探针及逻辑资源上界，非真实设备或PERF-01。
resource-audit.json区分稳定保留项与mapping Python行/返回边界可达对象，
记录活动/封存、身份消息及其voxel数、所有权引用、局部区间账本、临时查找表和输出列表。
H限制输入消息条数，实际载荷为H*V；V可能大于活动cell上限N，测试另以V=3/N=2验证。
采样排除调用方主动保留的输入/结果，不测分配器内部瞬时峰值、字节大小或进程RSS；
结构计数不能当作机载内存/20ms/功耗达标。
140帧/323查询及保存重放、13项新增/M4共52项/全仓622项通过，见
[EXP-20261028-003](../experiments/2026-10-28-m4-time-resources.md)。

SW-04已通过显式M4 ROS/公开占据回放及独立应用map查询：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/m4_stage_run.py --port 11661
```

入口创建独立master，仅装配既有mapping节点与测试观测/clock生产者；没有感知模型或传感器节点。
复制完整配置到新run，显式绑定registration.run_id/clock_id，设置K=1以验证FIFO淘汰。
`m4_fixture.launch`把私有map_backend=m4_fixture、rolling_enabled=true、m4_fixture_config、
run_id/clock_id与既有enable_query显式传给节点；默认latest及旧launch保持。
工厂`create_map('m4_fixture', {'rolling_enabled': True}, run_id=..., clock_id=..., fixture_spec=...)`
惰性导入SceneMap；缺配置、混M2/M3/M4配置、rolling未启用、注册/身份错误或节点几何/阈值覆盖
直接失败，不fallback。配置的完整fixture域/同轴整格注册限制仍由m4_contract验证。
节点记录Scene几何和(K+1)N的结构上限，不将该值声称为机载预算。
默认关闭的老化诊断从公开snapshot与解析TTL读取，不依赖Local Map专属属性。

监督器自动将保存的receipts.json交给同一factory重放，等价的独立命令为：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/local_map_replay.py --input .runtime/runs/m4-stage-20261028T123353707205/receipts.json --run-id m4-stage-20261028T123353707205 --clock-id sim:m4-stage-20261028T123353707205 --map-backend m4_fixture --m4-fixture-config .runtime/runs/m4-stage-20261028T123353707205/m4-config.yaml --rolling
```

15观测9快照20查询/174项检查及4条拒绝、五类状态和质量/原时间保真通过；独立应用CLI
必须指定`--frame-id map --map-id m4-scene-fixture`，原odom请求返回unavailable。
Python/图隔离、公开回放、五组旧ROS回归与清理及全仓629项通过，见
[EXP-20261028-004](../experiments/2026-10-28-m4-ros-handoff.md)。
恢复为停止候选，显式选择旧后端并建立新run/实例，不续接私有Scene目录。
M4仅关闭固定合成软件范围；M5-DESIGN-01已交付
[TerrainPrior准入/兼容设计](M5_TERRAIN_PRIOR_DESIGN_20261028.md)，DEM尚未实现。
不存在可启动的m5_fixture、TerrainPrior ROS输入或地形配置开关；当前工厂仍拒绝M5后端。
M5-SW-01已完成[私有离线fixture合同/输入校验与独立预期](M5_SW01_CONTRACT_20261028.md)，
不要求GIS库、真实DEM文件或新ROS节点。configs/m5_terrain_fixture.yaml只由测试fixture构建器读取；
mapping内部load_fixture入口严格读取有界JSON，不将该YAML作为ROS/后端启动参数。
公共协议和默认关闭的地形运行装配须另行确认，不因设计完成改变旧latest/M2/M3/M4入口。

M5-SW-02已有显式独立纯Python地形候选与私有回放，仍无m5_fixture工厂选型或ROS入口。
只读已有SW-01运行产物复现的[命令与API说明](M5_SW02_TERRAIN_CANDIDATE_20261028.md)不重建历史预期，
每次新建m5-candidate输出目录。注册/geometry/run变更要求新实例，坏安装保留旧版，reset锁定，
真实运行恢复按项目约定新run重建；不迁移旧私有缓存到新注册，不向应用直接提供私有文件。
