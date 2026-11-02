# M4-SW-02：离线Scene候选与冻结预期对账

编号：EXP-20261028-002；日期：2026-10-28；主责任：mapping_engineer。
状态：已完成（固定合成注册下的离线候选范围）。
依据：用户确认继续执行[M4具体方案](../docs/M4_SOFTWARE_TRIAL_PLAN_20261027.md)，
前置输入/预期为[SW-01交付](2026-10-28-m4-fixture-contract.md)。

## 前置审计与范围

先读取根/相关模块规则、PROJECT_STATUS、SYSTEM_ARCHITECTURE及数据/坐标合同，
检查真实M4 checker、M3更新/滚动、公开快照/查询、编解码及应用边界。
Git分支feature/engineering-initialization，保留全部既有未提交改动；
`.runtime/runs/m4-scene-probe`忽略检查通过，不提交/推送/清理任何历史结果。

已有能力为M3滚动累计与M4无状态输入checker，缺少Scene目录和公开Scene视图。
本轮新增显式纯Python候选和只读冻结预期对账工具，不改既有算法、M4输入合同/配置、
工厂/ROS包装、公共消息或应用实现，不修改同级研究仓库。
恢复为停止使用显式候选，以新run启动旧后端；不把Scene目录导入旧M3。

## 实现与代码证据

[SceneMap](../mapping/ufm_mapping/scene_map.py)组合一个RollingIntervalProbabilityMap，
只通过其公开update/snapshot取得估计。构造要求完整M4 spec及与注册匹配的run/clock。
Scene不直接接触Radar/IR、状态、TF、训练LiDAR、target、observed_mask或研究模型。

| 符号 | 实际行为 |
| --- | --- |
| SceneMap._scene_cells | 依据显式map←odom平移与局部/Scene origin计算整格offset，local index转Scene index，不重采样或改变概率/quality/原时间 |
| SceneMap._prepare_scene | 新活动视图接管同坐标封存owner；同时间不同载荷/旧版本拒绝；窗口移动前把旧活动剩余cell封存，空记录删除后执行FIFO |
| _State.cells | 索引引用活动/封存中的唯一载荷，不保留可回退的旧副本；同窗口M3容量淘汰的活动cell也从Scene消失 |
| SceneMap._validate_scene | 每个活动/封存记录不超过M3配置N，所有cell维持M3输出区间合同，不从旧记录补齐缺失质量 |
| SceneMap.update | 输入checker后deepcopy一个完整临时状态，包括活动M3身份/事件水位和Scene目录；活动更新、目录构造/质量校验成功后单引用整体提交 |
| SceneMap.snapshot | 固定map网格完整稀疏视图，cells按Scene index排序；独立Scene revision，header贡献时间仍来自活动M3公开快照 |
| SceneMap.query | 五类状态；错域/注册过期/早于最新贡献或结构时间无cell载荷；空洞unknown；年龄按min(max_age_ns,TTL)，stale保留历史quality |

空移动/封存/FIFO不刷新证据时间；重叠cell转移不再次累计。封存几何固定，但所有权接管
和资源淘汰可以删除记录中的cell；它不是全量档案。活动M3丢弃后返回的新贡献从其先验
开始，不使用Scene旧累计值初始化。新missing贡献可替换旧available，但不能向旧记录借范围。
目录查询不改变FIFO，最新owner消失不能回搜旧副本恢复旧值。

一个临时完整副本用于联合原子性，包含活动导出与所有权索引；最终索引引用载荷，
但事务、snapshot、query导出仍有有界临时拷贝。完整保留项/临时副本计数及长序列压力
属于SW-03，不能用本轮基础N/K限制测试宣称已完成资源或机载RSS验收。

## 冻结预期对账

[m4_scene_run.py](../tests/m4_scene_run.py)只读
[原SW-01保存输入](../.runtime/runs/m4-fixture-20261028T093615412726/fixtures.json)，
不导入m4_oracle/m4_fixture/m3_oracle、不重算答案；每case创建新候选。
保持接收顺序，比较每步fused/not_fused/rejected、完整snapshot与所有query、原证据/结构时间，
并以测试专用私有审计核对活动和FIFO封存所有权表。application不读取该目录。
运行器再做实际ROS消息serialize/deserialize，与保存预期的float32概率映像和float64区间比较。
纯累计/区间数值与独立分数答案使用绝对误差1e-12；身份、整型时间、状态/原因及来源精确匹配。

首轮运行直接通过，最终保存运行也通过：
[report.json](../.runtime/runs/m4-scene-20261028T102236314290/report.json)、
[结果](../.runtime/runs/m4-scene-20261028T102236314290/results.json)、
[输入/预期副本](../.runtime/runs/m4-scene-20261028T102236314290/fixtures.json)。
8场景、41输入、52查询、五类状态、全部快照/所有权/FIFO与消息承载一致。
源输入/预期未修改；首轮产物m4-scene-20261028T102108710603保留。

| 保存场景 | 本轮已验证结果 |
| --- | --- |
| overlap_no_double_count | 注册非零平移后index=[80,32,8]；空重叠滚动不二次累计/刷新，后续贡献得到原M3名义值及区间 |
| fifo_eviction_and_fresh_return | K=1封存淘汰顺序正确，淘汰P为unknown；返回新free得到0.25，未与旧0.75再累计 |
| missing_takeover_ttl | 新missing接管、known贡献仍保持unavailable，封存保留原时间，TTL重启恢复范围 |
| capacity_then_seal | N=2同窗口容量淘汰不从旧Scene副本复活；剩余owner封存，返回新cell独立接管 |
| no_evidence_and_empty_motion | 无证据/不可用不产生free，失效变换不移动；空移动只改结构，stale后新贡献恢复 |
| refusal_and_recovery | 重复不融合、同ID改quality/迟到/越界未来/坏末尾单位/错run拒绝，合法后续free恢复 |
| empty_seals_do_not_evict | 连续空移动不制造封存记录占额，不提早淘汰原历史，返回missing不借旧范围 |
| fresh_run_and_registration_time | 新run不继承，首个free保持新值，注册右界/错clock无载荷，Scene外unknown |

## 定向与全仓回归

新增[test_m4_scene_map.py](../tests/test_m4_scene_map.py)15项，覆盖显式构造/域隔离、
非零坐标、历史/FIFO、返回先验、质量接管/TTL、查询只读/深拷贝、坏未来帧恢复、
Scene构造后段故障与同刻冲突的原子性、新run/坏查询、默认工厂隔离及篡改预期反例。
其中Scene校验故障发生于临时活动M3已更新之后；公开状态保持原样，同一身份/时间重试可成功，
说明基础事务路径没有先提交局部水位。完整多点组合故障/资源压力仍待SW-03。

单元测试在临时目录构造自己的输入/预期，便于无历史.runtime目录时独立运行；
正式对账命令始终读取上述历史冻结文件。篡改预期quality.source或所有权表时运行器明确失败，
不悄悄改写答案/容差。新增测试首轮15/15通过，没有通过修改既有预期或算法掩盖失败。

最终M4共39/39、全仓609/609通过，证据：
[m4-tests.log](../.runtime/runs/m4-scene-20261028T102236314290/m4-tests.log)、
[lightweight-tests.log](../.runtime/runs/m4-scene-20261028T102236314290/lightweight-tests.log)、
[命令收据](../.runtime/runs/m4-scene-20261028T102236314290/lightweight-tests.json)。
运行前核对sys.executable为指定Conda Python；命令均通过sim01_env.sh。
没有修改共享工厂/ROS或既有M3，因此本轮不重复启动旧ROS；全仓回归包含旧契约检查，
实际M4 ROS/公开回放/应用交接留SW-04，不能用本轮消息序列化冒充运行图验证。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m4_scene_run.py --input .runtime/runs/m4-fixture-20261028T093615412726/fixtures.json
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_m4*.py' -q
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

git diff --check、新文件空白和配套文档相对链接核对通过；无自动提交/推送。

## 文件与未验证范围

新增源码3个：mapping/ufm_mapping/scene_map.py、tests/m4_scene_run.py、tests/test_m4_scene_map.py。
新增本中文记录；更新PROJECT_STATUS.md、docs/M4_SOFTWARE_TRIAL_PLAN_20261027.md、
docs/DEVELOPMENT_PLAN.md、docs/STAGE_ADVANCE_PLAN_20261027.md、docs/RUNTIME_CONFIGURATION.md、
docs/DATA_FORMAT.md、docs/COORDINATE_SYSTEM.md、docs/SYSTEM_ARCHITECTURE.md、
docs/DECISION_LOG.md、docs/EXPERIMENT_LOG.md，登记真实代码/运行范围和下一任务。

已有能力是M3/注册checker及冻结预期；本轮实现Scene候选；已验证固定合成注册条件下
的离线输入→活动M3→Scene视图与目录/查询保真。未注册m4_fixture后端，默认入口不导入候选，
没有M4 ROS、动态注册、真实设备/标定/定位reset、统计质量、机载RSS/功耗或正式PERF-01证据。
同run未声明定位跳变仍无法可靠识别；不能据此关闭正式M4或完整Phase 4。
不运行模型/checkpoint/训练，不推进DEM、科研对照或自主控制；研究仓库未修改。

下一项M4-SW-03（计划，mapping_engineer）：离线扩展时序/TTL/所有权淘汰/返回/新run组合，
覆盖坏未来帧和Scene提交后段故障；在K=1/N=2/H=3长序列中核对联合原子恢复并细分
活动/封存/所有权索引/导出/临时事务副本的上界。基本TTL/容量样例不能代替完整组合。
之后SW-04再接显式ROS、公开占据回放与独立应用查询及旧入口兼容/清理。
