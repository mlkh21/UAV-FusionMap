# M4-SW-01：显式注册、输入合同与独立生命周期预期

编号：EXP-20261028-001；日期：2026-10-28；主责任：mapping_engineer。
状态：已完成（输入/预期软件范围）；依据：用户在
[M4具体方案](../docs/M4_SOFTWARE_TRIAL_PLAN_20261027.md)交付后继续确认执行。

## 前置审计、问题和修改边界

先核对Git状态、feature/engineering-initialization分支与忽略规则，保留全部既有未提交
改动；.runtime/runs仍被忽略，未提交、推送或清理历史产物。读取根/模块规则、状态、
架构、接口与坐标规范，复核m2/m3_contract、M3测试输入/独立分数oracle、当前工厂及
占据/快照/查询编解码真实调用链。没有修改同级研究仓库或原Conda环境。

已有能力为M3显式滚动累计、公开消息和回放；M4此前只有设计与承载审计。
当前缺口为M4显式注册合同、完整输入门禁及未来候选的独立固定答案。
本轮仅新增纯checker、fixture配置和测试专用轨迹/预期/冻结工具，不修改M1/M2/M3算法、
工厂、ROS节点、公共消息、SensorBundle或OccupancyObservation字段。
恢复可停止使用本轮显式工具，旧入口仍按原配置；没有候选状态需要迁移。

## 实现与生产消费链

- [m4_contract.py](../mapping/ufm_mapping/m4_contract.py)：复用M3输入质量/时空合同，
  新增m4_fixture.v1、单map网格、具名固定合成map←odom注册、run/clock与半开有效期检查。
  同轴同分辨率、非零整格平移；缺注册、旋转、非整格、错来源/域或超期拒绝。
  有效输入按现有M3实际浮点取整规则检查整个活动窗口是否在Scene envelope内，
  不是只检查有点的位置；nonvalid不使用不可用占位变换推断新窗口。
  顶层/header/context/voxel均限制为已有公开字段，LiDAR/target/observed_mask注入拒绝。
- [m4_fixture.yaml](../configs/m4_fixture.yaml)：完整内嵌M3配置，固定map网格和
  T_map_odom=[I,(32,0,0)m;0,1]，fixture_only=true、enabled_by_default=false；
  注册显式绑定m4-fixture/sim:m4-fixture及[0,1000000000)ns。只供checker和测试读取，
  没有m4_fixture工厂或ROS入口。
- [m4_fixture.py](../tests/m4_fixture.py)：测试生产者复用M3公开占据构造，
  用显式表声明活动/封存cell版本、revision、证据/结构时刻和期望拒绝结果。
  每case独立run/clock及完整配置，目录限额/容量场景覆盖值一起保存。
- [m4_oracle.py](../tests/m4_oracle.py)：仅依赖stdlib，使用Fraction坐标和显式所有权表
  物化预期Scene snapshot/查询，不导入mapping或读取候选状态，不自动推演封存/淘汰。
  质量版本使用已知M3分数算例；3条关键算术序列另对既有独立M3 oracle核对。
- [m4_fixture_run.py](../tests/m4_fixture_run.py)：先保存配置、输入和完整预期，再运行
  stateless checker与真实消息serialize/deserialize；概率/confidence按精确float32承载值比较，
  区间float64、来源、身份和时间精确保真，不修改原预期。
  检查未导入累计类；scene_map_executed/map_accumulation_executed/ros_master_started均为false。

checker无状态，不能验收去重、迟到、目录所有权或联合原子性。它接受重复/迟到但结构合法
输入是预期行为；未来候选仍须根据历史拒绝相应输入，不能把checker结果当作融合结果。
Scene全量预期载荷只是待对账答案，不是已运行的Scene Map输出。
测试表有明确算术/几何前提；合法但不同参数的问题不能静默套用原表，生成工具会明确拒绝。

## 冻结场景与结果

最终产物：
[report.json](../.runtime/runs/m4-fixture-20261028T093615412726/report.json)、
[config.json](../.runtime/runs/m4-fixture-20261028T093615412726/config.json)、
[fixtures.json](../.runtime/runs/m4-fixture-20261028T093615412726/fixtures.json)。
8个场景、41条输入及52条查询预期已保存；38条输入通过合同、3条被拒绝，原始/反序列化
输入判定一致。查询预期覆盖五类状态，尚未调用Scene Map回答这些查询。

| 场景 | 输入数 | 显式预期范围 |
| --- | --- | --- |
| overlap_no_double_count | 3 | 非零map←odom注册；平移后Scene index保持[80,32,8]，空移动不二次累计；原贡献TTL边界/超界、错frame及Scene半开外界 |
| fifo_eviction_and_fresh_return | 4 | K=1，P→Q→R跨窗口封存/FIFO，P淘汰unknown；返回P的新free从先验得到0.25，不与历史0.75再累计 |
| missing_takeover_ttl | 6 | 新missing贡献接管旧available全部载荷；后续known不借旧范围，封存不刷新原时间，超TTL新贡献恢复范围 |
| capacity_then_seal | 4 | N=2/H=3/K=1，同窗口容量淘汰不在Scene恢复旧cell；保留cell封存，返回新贡献独立接管 |
| no_evidence_and_empty_motion | 8 | unavailable/empty/unobserved/neutral不产生证据；失效占位变换不移动窗口，合法空移动只改结构，旧证据stale及TTL重启 |
| refusal_and_recovery | 9 | 重投递、同ID改quality、迟到、未来越界、坏末尾单位、错run；先前状态保持的预期与随后合法free恢复 |
| empty_seals_do_not_evict | 5 | 空封存不占K，不因连续空移动淘汰原历史；返回新missing不借旧范围 |
| fresh_run_and_registration_time | 2 | 独立run空实例无继承，首个free；注册右界不可用、错clock及负Scene坐标unknown |

三条checker拒绝输入分别是完整窗口越界、坏末尾单位、错run；其余有状态拒绝留给后续候选。
目录所有权表显式给定，不复刻一个Scene状态机来证明自己。

## 反例、修复与测试

新增[test_m4_fixture_contract.py](../tests/test_m4_fixture_contract.py)共24项，覆盖缺/坏配置、
注册方向/状态/来源/有限矩阵、几何与限额类型、有效期边界、完整空窗口越界、
nonvalid变换、各层训练字段隔离、坏末尾quality不改输入、真实序列化保真、
独立坐标/所有权/缺失/时间算例、非法预期表、参数前提与默认入口隔离。

补充审查发现新checker最初用Fraction推算活动窗口，而既有M3先做浮点中间运算，
三轴近半格tie时可能不同。Y=8.249999999999998和Z=0.24999999999999997应因M3实际
选出的窗口越界而拒绝，Z=-0.25000000000000006则应按M3实际窗口接受。
先新增测试复现2条FAIL/1条ERROR，原日志保留于
[window-before-fix.log](../.runtime/runs/m4-fixture-20261028T093253285035/window-before-fix.log)。
随后只修正新checker，按M3既有浮点顺序选择窗口，再用精确格点/envelope合同检查；
独立Scene预期继续使用Fraction，不修改既有M3或放宽边界。修复后24项和全仓均通过。
审查辅助命令首次使用Python 3.8没有的math.nextafter未执行成功，随后用stdlib struct
构造相邻float64完成探针；最终测试不依赖该缺失API，也未改变环境。

最终定向24/24、全仓594/594通过；日志及命令收据：
[m4-tests.log](../.runtime/runs/m4-fixture-20261028T093615412726/m4-tests.log)、
[lightweight-tests.log](../.runtime/runs/m4-fixture-20261028T093615412726/lightweight-tests.log)、
[lightweight-tests.json](../.runtime/runs/m4-fixture-20261028T093615412726/lightweight-tests.json)。
前两次输入冻结及修复前591/593项的中间运行保留原位，不覆盖；最终结论使用本段产物。
没有改共享运行实现，因此本轮不启动旧ROS或重复M3累计运行；默认不导入M4 checker、
M4选型仍明确失败已由定向测试验证。git diff --check、文档相对链接/符号与状态检查通过。

复现命令（经指定环境，进程内已核对sys.executable）：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m4_fixture_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_m4*.py' -v
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

## 文件清单、限制与下一步

新增实现/配置/测试共6个文件：mapping/ufm_mapping/m4_contract.py、configs/m4_fixture.yaml、
tests/m4_fixture.py、tests/m4_oracle.py、tests/m4_fixture_run.py、tests/test_m4_fixture_contract.py。
新增本中文记录；更新PROJECT_STATUS.md、docs/M4_SOFTWARE_TRIAL_PLAN_20261027.md、
docs/DEVELOPMENT_PLAN.md、docs/STAGE_ADVANCE_PLAN_20261027.md、docs/RUNTIME_CONFIGURATION.md、
docs/DATA_FORMAT.md、docs/COORDINATE_SYSTEM.md、docs/SYSTEM_ARCHITECTURE.md、
docs/DECISION_LOG.md及docs/EXPERIMENT_LOG.md，登记具体实施状态和证据。

已有能力为M3/公共承载；本轮实现M4注册/输入checker与独立预期工具；已验证合同、
输入/预期消息序列化及轻量回归。没有Scene候选、Scene目录/查询运行、M4 ROS、
真实注册/定位reset、模型质量/forward/checkpoint或机载资源/正式PERF-01证据。
现有上下文缺独立epoch，未声明同run跳变不能可靠识别；固定合成注册不解决该正式缺项。
LiDAR/target/observed_mask不进入在线边界，未知、无回波、过期和不可用不作为free。
未启动训练、模型推理、研究对照、DEM或自主控制；研究仓库保持只读。

下一项M4-SW-02（计划，mapping_engineer）：按已确认方案实现显式纯Python有界Scene候选，
直接读取本次保存配置/输入/预期对账，不导入oracle重新生成答案；核对非零坐标注册、
封存/所有权/FIFO、整条quality/原时间、公开单网格快照和查询，先不注册默认或ROS入口。
其后SW-03验证联合原子性/事件时间/资源组合，SW-04再做ROS/公开回放/应用及旧入口交接。
正式M1/M2/M3/M4及完整Phase 4仍未关闭；不因合成软件完成省略真实质量/注册/性能门禁。
