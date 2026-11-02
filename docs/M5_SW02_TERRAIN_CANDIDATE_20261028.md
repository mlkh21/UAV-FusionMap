# M5-SW-02：独立地形候选与私有回放

日期：2026-10-28；主责任：mapping_engineer；状态：已完成（离线合成候选范围）。
依据：[M5设计](M5_TERRAIN_PRIOR_DESIGN_20261028.md)、[SW-01私有合同](M5_SW01_CONTRACT_20261028.md)。
证据：[EXP-20261028-009](../experiments/2026-10-28-m5-terrain-candidate.md)。

## 1. 实际入口

[TerrainFixture](../mapping/ufm_mapping/terrain_fixture.py)为显式独立纯Python类，
不经地图工厂创建、不导入ROS/GIS/模型，不接收OccupancyObservation，也不生成占据观测。
构造函数校验SW-01输入并绑定run/clock；此时没有安装版本、高程或可用查询结果。
仅显式构造使用它；默认latest/M2/M3/M4与既有消息/应用/可视化原样保持，m5_fixture选型仍拒绝。

| 方法 | 已实现行为 |
| --- | --- |
| `observe_clock(timestamp)` | 独立接收非负int64运行时钟，回退后锁定实例，不能在同实例解锁；查询时间不推进/重置该时钟 |
| `install(spec,timestamp)` | timestamp须等于已观察时钟；新版本只在registration/eligibility有效时安装，成功True；相同活动版本完整内容重复返回False |
| `query(request)` | 私有map二维中心请求→高程/质量与valid/unknown/stale/unavailable；不等同MapQuery占据五状态 |
| `snapshot()` | 返回独立拷贝的私有诊断，包括已提交输入/样本、revision、安装时间、版本身份及运行状态；不是MapSnapshot |
| `disable()` | 本实例终止地形使用，不返回历史高程载荷；恢复另建实例，实际运行须按项目约定使用新run |

类按单线程调用设计；若后续加入并发包装，调用方必须串行化安装、时钟和查询。
没有后台线程、文件监视、模型/GPU、真实DEM或运行服务。

## 2. 采样、质量与输出

仅支持SW-01已冻结的单tile、north-up、同格距整格对齐与具名非零平移。
安装时按row-major计算像素中心和map样本；查询用反向固定平移定位唯一中心，禁止插值/旋转/重采样。
0/负源高度正常转换；no_data_mask=true保持height=null，查询unknown/no_data，覆盖外unknown/outside_coverage。
没有任何height→occupied/free规则，也不产生probability或observed字段。

私有结果schema为`m5_terrain_result.v1`，含请求域/时间/坐标、terrain_id、terrain_revision、
dataset_version、registration_id、height、源样本索引/坐标、height_quality、质量贡献元数据、
source_time、eligibility、registration_validity、installed_timestamp、fixture来源及DTM产品类型。
只有通过身份、开关、时钟/注册和激活时间检查后才携带安装版本/高程元数据；
unavailable不给高程、原采集时间或质量界。合法请求身份错配返回unavailable；非法语法、非中心请求抛ValueError。

完整高度区间为源绝对height_interval与注册绝对height_offset_interval逐端点相加，单位m；
任一质量缺失则height_quality=unavailable，名义高度可保留作未校准显示，两个贡献元数据分别保存。
使用输入十进制表示的Fraction计算和float64输出，区间端点必要时向外扩一个ULP，避免舍入缩窄区间。
名义值按最近float64表示；溢出/非有限或map中心丢失格点精度在安装提交前拒绝。
这是具名合成区间算术，不能推导真实误差覆盖率/置信水平或把它改作M3概率质量。

## 3. 版本、时间与恢复

同一实例固定terrain/tile/产品/来源引用、源/目标基准、map网格、注册（包括其质量/有效期）和采样几何。
新版本可整版替换样本/掩码/质量、source_time、eligibility及dataset_version；源采集/发布时间不能倒退。
注册、坐标或几何改变要求新实例；不得将旧高程重标到新注册。

完整校验、大小检查、样本/质量准备和新版本目录均在临时状态中完成，最后只替换一次已提交状态引用。
失败不改变revision/安装时间/样本/版本身份；已观察时钟是独立运行事实，不随安装失败回滚。
更换版本整体替换样本，不向旧版借no-data高度或质量；同身份异内容拒绝；退役版本即使载荷相同也不复活。
重复活动版本不刷新采集时间、eligibility、安装时间或revision，过期后重复也不会恢复有效性。

有效性按请求同域query_timestamp判断；既有观察时钟仅作为安装时序和reset门控。
查询可检查安装后的过去时刻或未来eligibility边界，但不能查询当前版本安装前的历史，
不提供历史版本目录查询；查询自身不会推进时钟或改变任何状态。

| 条件（身份/语法合法后） | 结果 |
| --- | --- |
| 未观察时钟/未安装/disabled/reset锁定 | unavailable，明确reason，无高程 |
| 注册区间外，包括恰好valid_until | unavailable/registration_unavailable，无高程 |
| 早于max(安装时刻,eligibility开始) | unavailable/query_before_terrain_activation |
| eligibility区间内 | 对应中心valid、no-data或覆盖外unknown |
| eligibility结束后但注册仍有效 | stale/terrain_expired；有历史样本可保留原高程/质量/时间；无样本仍无高程 |

reset锁定不能因后来时间增长恢复；不以坏候选、0高程、Gazebo地面或placeholder进行fallback。
源dataset时钟与sim时钟不相减，不使用文件mtime、加载时间或查询时间冒充采集时间。

## 4. 有界身份与私有回放

输入仍最多16样本、每轴4；直接对象安装另限制规范JSON编码≤16KiB。
版本冲突检测保存规范JSON原载荷，使用排序key/保留数字编码比较，不计算Hash；
1与1.0等不同数值编码可能判为同版本内容冲突，调用方应重放原载荷。
最多保存64个版本身份，不淘汰后遗忘旧身份。身份载荷逻辑上限为64×16KiB，
另有模板、绑定、活动/候选spec、样本、返回拷贝；不能把“16样本”写成总内存上限。
本轮只验证基本限额/拒绝行为，完整临时峰值组合与RSS仍由SW-03/正式性能分别处理。

[terrain_replay.py](../mapping/ufm_mapping/terrain_replay.py)仅接受≤64条私有事件，序号必须从0连续，
query/reset事件时刻须与其请求一致；每条事件显式观察时钟后调用安装、查询、disable。
同版本原样、同身份冲突等事件名只是操作记录，是否接收由候选决定，不读取expected或expected_revision。
安装错误记录拒绝reason并核对状态不变；非法事件、查询或不支持操作明确失败，不改为fixture成功。
每次回放创建全新实例，返回独立收据与最终私有快照，不借用占据回放协议。

## 5. 复现与验证范围

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m5_candidate_run.py --fixture-run .runtime/runs/m5-fixture-20261028T182933778256
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_m5*.py' -v
```

runner只读已有SW-01配置、输入/预期、5个请求与7条完整事件，不调用fixture重建器或oracle生成新期望。
每次新建m5-candidate运行目录；4样本、5边界、7事件、45输入共135项保存预期检查通过，重复回放一致。
新增24项、M5合计45项与全仓694项通过；包括成功替换、旧版不复活、缺失质量、准备/提交前失败与重试、
返回拷贝隔离、输出溢出、64身份/字节上限和既有占据快照不变。公共字段/默认入口未变，本轮未启ROS。

下一项M5-SW-03：补齐多版本/更长时序/到期/重试/限额与联合失败组合，明确稳定项和临时副本预算，
形成独立软件关闭证据。真实DEM/地理转换、公共地形ROS与占据辅助融合仍未实现，需分别准入/确认。

后续M5-SW-03已完成[时序/资源组合](M5_SW03_TIME_RESOURCES_20261028.md)：84事件、64版大载荷、
五处故障/临时副本及占据隔离通过；修补超长文本编码前门控，新增10项/全仓704项通过。
上述SW-02时点的待办保留为历史；当前下一项是公共地形合同具体设计，尚无公共协议实施。
