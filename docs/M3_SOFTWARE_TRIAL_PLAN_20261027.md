# M3不确定性来源、表达与合成区间传播方案

日期：2026-10-27；主责任：mapping_engineer。
状态：M3合成软件试制已获用户后续“继续”确认；DESIGN-01、SW-01/02/03/04均已完成软件范围。
依据：用户确认继续执行M3-DESIGN-01；M2-SW-01—04合成软件交接已完成，
见[EXP-20261027-010](../experiments/2026-10-27-m2-ros-handoff.md)。
本方案不恢复研究模型质量任务，不改变正式M1/M2/M3、设备或性能退出门槛。
SW-01输入合同、配置和独立预期见
[EXP-20261027-012](../experiments/2026-10-27-m3-fixture-oracle.md)：
10场景/43输入、19项定向及534项全仓通过。
SW-02固定候选随后对保存预期全部通过，名义值逐值等于M2；新增12项定向、M3共31项
及全仓546项通过，受影响M2实际ROS/回放回归与清理通过，见
[EXP-20261027-013](../experiments/2026-10-27-m3-fixed-map.md)。
SW-03离线滚动组合随后通过：96帧/257查询/4探针、15项新增/M3共46项及561项全仓，
见[EXP-20261027-014](../experiments/2026-10-27-m3-rolling-time.md)。
SW-04实际ROS/应用交接随后通过19观测/13快照/19查询、155项运行检查，公开回放、
旧M1/M2/placeholder及清理通过；新增9项、全仓570项通过，见
[EXP-20261027-015](../experiments/2026-10-27-m3-ros-handoff.md)。

## 1. DESIGN-01时调用链与证据边界

| 真实位置/符号 | 已有行为 | 尚不能据此声称的能力 |
| --- | --- | --- |
| [placeholder_infer](../perception/ufm_perception/placeholder.py#L74) | fixture概率0.9，confidence=None、uncertainty unavailable | 没有真实模型质量、方差或校准结果 |
| [validate_output / _quality](../perception/ufm_perception/output_contract.py#L21) | 核对状态、元数据、有限数值；occupancy_variance仅约束单非负值 | 没有完整kind→形状/单位/来源语义注册或统计有效性验证 |
| [SparseLocalMap.update](../mapping/ufm_mapping/local_map.py#L197) | 最新有效cell覆盖概率，深拷贝同一帧quality；滚动保留cell | 质量复制不等于融合、位姿误差传播或独立证据累计 |
| [SparseLocalMap.query](../mapping/ufm_mapping/local_map.py#L305) | 返回cell的历史quality；超龄改status=stale，不刷新时间 | stale历史质量不能当作当前空间的可信保证 |
| [FixedProbabilityMap._updated_cell](../mapping/ufm_mapping/fixed_probability_map.py#L51) | M2默认累计后明确confidence=None、uncertainty unavailable；仅提取暂存构造扩展点 | M2分支不将输入质量冒充累计质量；M3独立候选另列 |
| [FixedIntervalProbabilityMap._updated_cell](../mapping/ufm_mapping/fixed_interval_probability_map.py#L17) | 显式固定M3候选暂存均值与端点累计，缺失锁存/TTL重启 | 已有固定合成算术证据，不是统计覆盖率或真实校准 |
| [RollingIntervalProbabilityMap](../mapping/ufm_mapping/rolling_interval_probability_map.py#L7) | 复用同模块M2滚动准备，M3质量构造沿用固定候选；均值、范围/缺失状态共同迁移与淘汰 | 已有离线滚动组合证据，尚无M3实际ROS或真实质量验收 |
| [codec._uncertainty_fields](../ros_ws/src/uav_fusionmap_msgs/src/ufm_ros_contract/codec.py#L53) | available必须有文本元数据、有限非空数组；不可用value=None；现有variance规则同上 | generic序列化不是物理单位、协方差维数/正定或校准验证 |
| [query_codec](../ros_ws/src/uav_fusionmap_msgs/src/ufm_ros_contract/query_codec.py#L17) | 现有Uncertainty字段往返，confidence可用性保留 | 不计算融合质量或自动变换质量坐标 |
| [MapQueryClient.query](../application/ufm_application/query_client.py#L36) | 保真返回五类状态与完整字典，拒绝坏身份/概率/时间 | 自定义字典transport绕过codec时，尚未独立验证confidence/uncertainty |

`Uncertainty.msg`已有status/kind/value/unit/source，Quality另有confidence。
SpatialContext的pose_uncertainty与voxel uncertainty不是同一个对象；M1存cell时没有
把位姿协方差传播成占据质量。source是描述文本，不是已验证校准证书或完整证据链。
单个Uncertainty对象也不能无约定地混装位置、姿态、模型分数和概率误差。

本轮9项只读探针及3组有理数算例见
[审查产物](../.runtime/runs/m3-design-20261027T161433188266/report.json)。
探针包括当前允许通用unit/形状、应用自定义transport质量检查不足，
`passed`只表示审计事实符合源码预期，**不表示M3或这些质量载荷已获语义验收**。
既有ROS查询7项、应用4项、编解码6项定向回归通过，未新增运行算法。

## 2. 首版范围选择

选择默认关闭的**合成占据概率区间传播**，验证有明确输入范围时，M2具名算术累计的
输出范围如何随输入、缺失、TTL和窗口一起变化。区间是算术输入范围，
不是统计置信区间，也不提供置信水平、真实误差覆盖率或实际碰撞风险保证。
未提供真实校准并不妨碍这组确定性软件试制；真实质量仍另验。

不从p、p*(1-p)、熵、观测次数、研究辅助通道或confidence自动生成区间/方差。
不在首版传播位姿/标定协方差，不把模型分数换算成m²，不开展DEM/Scene Map或规划控制。
不更改已有M1 latest或M2 m2_fixture的质量语义，后者仍明确不可用。

## 3. 候选合同与来源

下列输入profile检查已由SW-01的`mapping/ufm_mapping/m3_contract.py`实现，
仅由显式工具及SW-02/03固定/滚动候选调用；M3实际ROS仍待SW-04，不能据此声称在线M3已支持。
复用OccupancyObservation/MapSnapshot/MapQueryResult及Uncertainty原字段，不新增ROS消息，
也不收紧现有默认通用codec的kind范围。

| 项目 | 首版显式fixture要求 |
| --- | --- |
| 输入来源 | source_type=fixture，observed_domain_source仍为`m2_explicit_inverse_fixture_v1`，沿用M2显式逆观测算术含义 |
| 候选隔离 | 已有显式FixedIntervalProbabilityMap、RollingIntervalProbabilityMap及checker；私有ROS `m3_fixture`选择尚未接入，配置map_id为m3-fixture，每次新实例绑定run/clock，默认latest与旧m2_fixture不启用 |
| available kind | 仅`occupancy_probability_interval`，明确为概率输入的上下界，不解释为occupancy_variance |
| value | float64逻辑数组[lower,upper]，必须恰为2个有限非bool数；输入满足0<lower≤p_z≤upper<1 |
| unit | 严格为`dimensionless`；不自动更名或转换m²、m2、rad²或概率百分数 |
| 输入source | 严格匹配具名fixture profile `m3_fixture_bounded_inverse_v1`，只证明该合成算术配置被选中，不证明物理校准 |
| 累计输出source | 使用不同标识`m3_fixture_bounded_accumulator_v1`；不得把累计输出再次当作单次逆观测输入 |
| unavailable | value=None；元数据保留文本说明，不能用[0,0]或空数组冒充已知零宽区间 |
| confidence | 仍按现有[0,1]/None检查；不参与区间计算，累计输出始终None |
| 位姿/坐标 | 沿用M2具名odom格点与观测时刻刚体变换；首版pose_uncertainty声明unavailable，数值试制条件化于显式合成变换，不宣称覆盖位姿误差 |

已知零宽[p_z,p_z]与质量不可用不同，必须分别验收。
单体素间均值不同，quality.value始终绑定该voxel/cell，不能借相邻体素的区间填补。
available但kind/source/unit不支持、区间倒序、未包含p_z、形状或数值非法时整帧拒绝；
合法unavailable质量不拒绝有效占据，但不能因此宣称累计质量可用。

SW-01配置为`configs/m3_fixture.yaml`（`m3_fixture.v1`），含fixture_only=true、enabled_by_default=false、
显式完整的M2算术子配置和上述interval profile。算术子配置的map_id使用m3-fixture，
先验/概率界/TTL/cell与身份限额继续显式给定，不在业务代码散布另一份默认值。
profile还明确不可用来源`m3_fixture_missing_range_v1`及精度约定
`float32_nearest_even_v1`；occupied/free示例区间由evidence_intervals给定。
M3不能接受未经适配的真实模型后验，也不把旧placeholder 0.9自动转为该输入。

## 4. 一步传播与独立数值预期

沿用M2已定义的逐帧算术：
`F(p,z) = sigmoid(clip(logit(p)+logit(z)-logit(p0), L_min,L_max))`。
初始累计均值和上下界均为p0；有完整范围时分别计算
`p_new=F(p_old,p_z)`、`lower_new=F(lower_old,lower_z)`、
`upper_new=F(upper_old,upper_z)`。F在两个概率输入上单调不减，
同一组有序逐帧clip规则因此保持lower_new≤p_new≤upper_new。
这界定的是所选M2算术的结果；不据此证明实际多帧测量独立或概率模型正确。

沿用fixture先验0.5及输出clip范围[0.1,0.9]，预期由独立分数odds运算给出，
不调用候选更新器产生oracle，也不能先求总增量再只clip一次。

| 步骤 | 输入p_z / [lower_z,upper_z] | 输出p / [lower,upper]（精确分数） |
| --- | --- | --- |
| 1 | 3/4 / [7/10,4/5] | 3/4 / [7/10,4/5] |
| 2 | 3/4 / [7/10,4/5] | 9/10 / [49/58,9/10] |
| 3 | 1/4 / [1/5,3/10] | 3/4 / [49/85,27/34] |

禁止平均输入方差或取最后一个输入区间冒充累计范围；区间宽度也不必随观测数减少。
初版查询分类仍依据原显式概率阈值，区间不改五类status；occupied不能解读为整个区间
均跨过占据阈值。若将来需要区间门限驱动保守分类/规划，须另给消费者策略和验收，
不能夹带改变现有分类行为。

数值承载已在SW-01单独验收：现有probability是ROS float32，uncertainty.value是float64数组。
输入区间必须围绕实际接收的float32还原p_z构造；fixture应先确定可传输均值，
零宽上下界使用同一还原值，不在接收端epsilon裁剪或悄悄外扩区间。
内部双精度累计严格保持包含关系；输出均值经float32承载后，可能因舍入略越过
双精度区间端点。应用包含关系检查须使用具名float32舍入预算（至多对应半个ULP；
边界按相邻可表示值约定），不使用任意大容差或改写质量字段来掩盖差异。
SW-01已冻结此约定：输入均值及配置中的occupied/free均值必须先为float32还原值；
不能用未量化的0.7直接构造零宽输入。输出pure/internal检查严格包含，wire输出则要求
`round32(lower) ≤ received_float32_mean ≤ round32(upper)`，精确应用nearest-even，
不用任意epsilon，也不改写字段。覆盖0.1/0.7/0.9、零宽、相邻float32、偶数舍入tie和
0.5两侧不对称间距。SW-02/03还检查固定/滚动累计快照/查询的真实消息序列化承载，应用接入仍留SW-04。
配置clip界也必须可编码为非0/1的float32；默认内部界0.1/0.9保持双精度算术含义。

## 5. 缺失、时序、坐标与资源

| 情况 | 均值/质量行为 |
| --- | --- |
| 首次有效贡献、区间available | 从先验同时更新均值和范围 |
| 首次有效贡献、区间unavailable | 更新均值，质量unavailable |
| 本周期已有available范围，新有效贡献缺少范围 | 更新均值，累计质量转unavailable；不能只跳过缺失贡献的质量 |
| 本周期质量已unavailable，后续贡献有范围 | 更新均值但累计质量仍unavailable，直到该cell TTL重启或被淘汰后重建 |
| 超TTL后新的有效贡献 | 均值与范围一起从先验重启；该次有范围才能恢复available |
| 空、无回波、observed=false、非valid | 不贡献概率/质量、不刷新旧证据时间；不解释为free |
| p_z=0.5中性 | 沿用M2不贡献规则；available区间只允许[0.5,0.5]，非零宽中性输入首版拒绝，避免静默丢掉范围变化 |
| 查询/重发/长期断流 | 不更新质量或时间；stale保留历史范围及原证据时刻，不输出当前可信保证 |
| 重叠滚动/移出/容量淘汰 | 均值、范围/缺失状态及原时间一起迁移或淘汰；没有额外无界quality账本 |
| 重复/冲突/坏帧/错run/clock | 沿用M2去重、严格事件时间与整帧原子拒绝；范围错误也不能推进水位或窗口 |

未知新区域和身份不匹配的查询不泄漏旧范围。若空帧只移动窗口，revision可变化，
证据时间不变；早于覆盖变化时间的查询仍unavailable。
输入范围只针对标量概率，不是空间协方差；body转向不会把它按m²旋转。
当前cell/身份限额继续有效，增加两个标量不能替代RSS、延迟或功耗实测。

## 6. 实施边界、兼容与恢复

生产者为tests专用合成占据工具；消费方为显式M3地图候选，再经既有ROS字段提供给
现有查询/应用。新增kind的语义在上述profile中明确；通用codec继续允许其他已合法kind，
不能把M3白名单无差别加到旧M1/感知/状态路径。

SW-01完成纯合同检查，SW-02在M2逐cell暂存构造处提取最小`_updated_cell`扩展点，
默认实现仍返回原M2不可用质量。M3候选在提交cell、身份/水位和窗口前完成范围构造，
不调用M2.update提交后再补写质量。名义与端点L放在同一按cell限额的私有不可变状态项，
避免从公开概率反算L积累舍入误差；不存在额外无界质量账本，也不泄漏进公共消息。
固定候选先过数值验收，SW-03新增显式滚动子类共用同模块M2的`_prepare_grid`，
固定M3负责质量构造，来源合同显式开启rolling校验；未修改M1/M2/固定M3源码，
不跨层导入perception或application，也未注册默认ROS入口。

应用只消费公开结果，不读取地图私有L或账本。SW-04同时补齐自定义transport的基础
confidence/uncertainty验证，与现有公开合同对齐；有效历史载荷和未知kind不能被随意重标。
识别本区间kind时核对形状、有序性和与公开概率的关系；坏响应返回unavailable，
不得把坏uncertainty悄悄改为available零值或free。应用侧不做概率/范围累计。

默认旧入口不切换，ROS显式M3配置错误直接失败，不回退M1/M2/placeholder。
恢复使用停止候选、新run启动latest或m2_fixture，不续接候选缓存。
若发现需要同时公开多类质量、置信水平、逐cell证据链或空间协方差的新字段，
先给生产者/消费者/兼容/恢复方案并单独确认，不能把新字段藏进value或source字符串。

## 7. 工作包与验收

以下具体合成软件试制范围已获用户后续“继续”确认，按工作包推进；
当前DESIGN-01/SW-01/02/03/04完成合成软件范围，估计为原开发工作量，非退出日期承诺。

| 顺序 | 唯一主责任 | 交付与完成条件 | 原估计/状态 |
| --- | --- | --- | --- |
| M3-DESIGN-01 | mapping_engineer | 本方案、真实调用链、语义/资源限制、独立算例与工作包 | 已完成（方案交付） |
| M3-SW-01 | mapping_engineer | 显式profile/config、合成输入及独立分数oracle；上述非法kind/unit/来源/形状拒绝，缺失和零宽分开 | 原估计0.5—1工作日；已完成：10场景43输入、19项定向/534项全仓，仅输入/预期 |
| M3-SW-02 | mapping_engineer | 默认关闭的固定M3累计候选；名义概率与M2逐帧一致，区间与冻结oracle一致；原子提交和缺失锁存通过 | 原估计1—2工作日；已完成：10场景43输入、12项新增定向/M3共31项/546项全仓；受影响M2 ROS回归通过 |
| M3-SW-03 | mapping_engineer | 滚动/TTL/淘汰/新run组合；区间随cell迁移、缺失后TTL恢复、读不刷新、限额确定性通过 | 原估计1工作日；已完成（离线）：96帧257查询4探针，15项新增/M3共46项/561项全仓，实际ROS待SW-04 |
| M3-SW-04 | tester | 私有ROS选择、公开占据回放、应用质量检查；五类状态、失效/乱序/恢复、旧M1/M2/placeholder回归与清理通过 | 原估计1—2工作日；已完成：19观测/13快照/19查询、155项运行检查，新增9项/全仓570项通过；公开回放及五组ROS清理通过 |

| 验收组 | 必须覆盖的独立预期 |
| --- | --- |
| A 类型 | available/unavailable、零宽、未知kind、错单位/来源、bool/NaN/Inf、倒序/漏均值/错长度；坏末尾体素整帧拒绝 |
| B 算术 | 上表3步、正负饱和/反证、不同输入顺序逐次clip；内部点区间退化时仍为点区间，包含名义概率；float32均值/float64端点的具名舍入预算与反例 |
| C 缺失 | known→missing→known仍不可用，TTL重启后恢复；missing不伪造0范围；多cell互不借用质量 |
| D 时间 | 重投递、同ID改区间、旧/同时间、坏未来帧后恢复；恰TTL边界新鲜，超界stale；query/replay不刷证据 |
| E 覆盖 | 平移/偏航/多轴格点、重叠保留、远移/返回、空帧覆盖变化；范围与概率/时间同生命周期 |
| F 工程 | 默认不导入候选，缺配置无fallback；五类状态/历史quality保真、坏自定义transport响应拒绝、公开字段回放一致及进程/端口清理 |

执行环境仍为指定Conda Python及sim01_env.sh。只在运行实现/ROS发生改变时执行相应
定向、全仓及受影响ROS回归；不为本次文档交付重复全部已关闭M2场景。
完成上述工作包只能称“合成范围传播软件通过”，不能称“真实不确定性已校准”。
