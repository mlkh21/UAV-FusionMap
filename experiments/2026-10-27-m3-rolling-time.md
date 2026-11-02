# EXP-20261027-014：M3-SW-03区间滚动、TTL与有界状态组合

日期：2026-10-27；主责任：mapping_engineer；状态：已完成（离线合成滚动范围）。
依据：[已确认M3方案](../docs/M3_SOFTWARE_TRIAL_PLAN_20261027.md)、SW-02交付及用户“继续”。
分支`feature/engineering-initialization`；先检查Git状态/忽略规则及真实固定/滚动调用链，
保留全部既有未提交改动，不提交/推送。

## 实现与数据边界

既有M2滚动准备会按格点迁移/淘汰cell及同键累计状态，固定M3已经把均值和端点L
保存在同一有界状态项中。本轮新增
[RollingIntervalProbabilityMap](../mapping/ufm_mapping/rolling_interval_probability_map.py)：
继承固定M3累计，输入显式开启rolling合同检查，窗口准备调用同模块
RollingProbabilityMap._prepare_grid，不复制或重写几何算法。

重叠cell保留累计范围/缺失状态、名义概率和原贡献时刻，移出同步淘汰；返回原位置
从unknown重新开始，不能复活旧范围。合法空帧可改变覆盖revision，不刷新证据；
缺失/失效变换不能移动窗口。早于最新覆盖变化的查询返回unavailable且不携带历史范围。
缺失范围仍锁存到TTL重启或淘汰重建；范围不按空间协方差旋转，confidence仍None。

没有修改M1、M2、固定M3、输入合同、oracle、默认factory或ROS/应用源码，
没有新增公共字段。只有显式Python类调用启用滚动M3，ROS的m3_fixture仍未接入。
输入仅为标明来源的OccupancyObservation及观测时刻SpatialContext；
不读取传感器/研究数据、LiDAR、target或训练mask，不隐式查询TF或最新状态。

## 独立场景与实际结果

新增[m3_motion_fixture.py](../tests/m3_motion_fixture.py)，复用测试专用世界点占据构造，
按具名合成body变换和观测origin生成输入；不调用地图格点辅助计算预期。
[m3_rolling_scenarios.py](../tests/m3_rolling_scenarios.py)中的范围由独立Fraction oracle
给定，窗口origin、revision、淘汰后unknown和贡献时间由显式场景表给定。

| 场景 | 输入数（不含探针） | 验证结果 |
| --- | --- | --- |
| overlap_missing_ttl | 7 | 偏航及不同source格点origin仍累计同一世界cell；known→missing→known跨移动保持质量不可用；TTL恰边界新鲜，超界stale；新显式free贡献从先验恢复范围；空帧移动不刷证据；过去窗口查询无范围载荷 |
| eviction_return | 5 | missing状态随重叠移动保留；远移同时清空均值/范围状态，返回不复活；新known贡献从先验得到0.75及[0.7,0.8] |
| invalid_transform_gap | 4 | 首帧空移动仍无证据；失效body变换及占位矩阵不移动、不刷新；断流超TTL后新贡献重启 |
| bounded_mixed_80 | 80 | 3个世界cell持续输入，仅保留2个cell/状态项和至多3条身份；一个cell持续known，一个周期性缺范围并保持不可用，第三个因容量淘汰保持unknown；每帧窗口交替移动 |

共96条观测、257次查询，包含occupied/free/unknown/stale/unavailable五类状态；
另4条探针为最近同内容重投递、同ID改范围、身份淘汰后的旧时刻、外run输入。
重投递不融合，其余拒绝；快照、累计项、身份水位和窗口不改变。
96条计数不包含上述4条探针，不以样本数声称RSS或运行时延达标。

名义probability/status/observed/index/时间/revision逐值等于同配置M2滚动实例；
范围按独立预期绝对容差1e-12对比，不将输入confidence或观测次数当校准质量。
实际serialize/deserialize占据、快照和查询消息：float32名义值精确等于协议量化结果，
float64范围及元数据保真，包含关系按SW-01 nearest-even承载合同检查，不改写字段。

## 保存、重放与反例

[m3_rolling_run.py](../tests/m3_rolling_run.py)在创建地图前保存fixtures.json并重新读入
比较；`--input`模式只读保存的配置/输入/预期，不导入oracle或重算场景。
每个case含完整配置，bounded场景的cell=2/identity=3覆盖值也明确保存在该文件，
config.json是默认配置快照，不替代各case覆盖参数。

首次组合run `m3-rolling-20261027T174400706357`通过，保留原位；补充显式free恢复、
保存预期反例和完整wire检查后，最终源为
[m3-rolling-20261027T174748991457/fixtures.json](../.runtime/runs/m3-rolling-20261027T174748991457/fixtures.json)。
最后独立重放为：

- [report.json](../.runtime/runs/m3-rolling-20261027T174924291380/report.json)：通过，4场景/96帧/257查询/4探针，map_accumulation_executed=true、nominal_exactly_matches_m2=true。
- [fixtures.json](../.runtime/runs/m3-rolling-20261027T174924291380/fixtures.json)：保存的完整参数、输入、几何/算术预期与探针；不改原业务run/clock/timestamp。
- [config.json](../.runtime/runs/m3-rolling-20261027T174924291380/config.json)：默认参数快照。
- [results.json](../.runtime/runs/m3-rolling-20261027T174924291380/results.json)：逐帧快照、查询、wire结果、状态/身份计数及探针拒绝原因。
- [定向日志](../.runtime/runs/m3-rolling-20261027T174924291380/ufm-m3-sw03-targeted.log)、[全仓日志](../.runtime/runs/m3-rolling-20261027T174924291380/ufm-m3-sw03-full.log)。

新增[test_m3_rolling_map.py](../tests/test_m3_rolling_map.py)15项，最初因模块缺失RED，
实现后通过。除上述场景外，覆盖正负平移/半格边界、不等距分辨率和三轴运动、
多cell隔离、确定性容量淘汰、错clock及新实例不继承状态、公开复制隔离和默认不导入候选。
坏变换/非格点/末尾坏范围，以及“窗口已暂存移动、第二个cell构造抛错”时，
整个状态不变，后续较早合法帧仍能恢复；不只看快照忽略水位。

保存预期的负例分别修改区间下界和窗口origin，重放必须退出1；测试屏蔽
m3_oracle及m3_rolling_scenarios导入，不能重算期望来消解错误。
负例只写临时副本，源产物和所有旧run保持。

## 复现与阶段状态

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m3_rolling_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m3_rolling_run.py --input .runtime/runs/m3-rolling-20261027T174748991457/fixtures.json
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_m3*.py' -v
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

新增15项、M3共46/46项定向、全仓561/561项轻量回归通过，`git diff --check`及文档链接通过。
原固定M3还对SW-01的10场景43输入重放通过，
[报告](../.runtime/runs/m3-fixed-20261027T174924271047/report.json)。
解释器为指定Radar-Diffusion，工具核对sys.executable。没有修改旧运行调用链，
本轮未重复启动ROS，离线消息序列化不等于ROS运行验收。

新增文件5个：mapping/ufm_mapping/rolling_interval_probability_map.py、
tests/m3_motion_fixture.py、tests/m3_rolling_scenarios.py、tests/m3_rolling_run.py、
tests/test_m3_rolling_map.py。同步PROJECT_STATUS、M3方案、开发/跨阶段计划、
DATA_FORMAT、COORDINATE_SYSTEM、RUNTIME_CONFIGURATION、DECISION_LOG、EXPERIMENT_LOG及本记录。

已有固定M3能力保持，本轮实现并验证离线区间滚动/TTL/有界状态组合。
M3实际ROS选择、公开占据回放/应用质量检查交接仍未完成；真实质量/校准、
位姿误差传播、目标平台资源/功耗和正式性能仍未验收。未启动训练、模型/GPU，
未修改同级研究仓库，不关闭正式M1/M2/M3。

下一步M3-SW-04：默认关闭的私有ROS选择、正常/失效/乱序/老化/恢复、公开占据回放、
应用质量检查、旧M1/M2/placeholder兼容和进程/端口清理。恢复仍是停止显式候选，
用新run启动原M1/M2；不迁移公共消息或继承旧候选缓存，未自动提交或推送。
