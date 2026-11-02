# EXP-20261027-009：M2-SW-03时序/TTL与滚动集成

日期：2026-10-27；主责任：mapping_engineer；状态：已完成（离线合成软件范围）。
依据：[已确认M2方案](../docs/M2_SOFTWARE_TRIAL_PLAN_20261027.md)及用户“继续”。
分支`feature/engineering-initialization`，开发前检查Git状态及忽略规则，保留全部既有改动；
未自动提交/推送。`.runtime/runs/`为忽略产物目录，历史run未覆盖。

## 问题与实现

已有SW-02固定候选具备有界log-odds、身份/时间水位、原子拒绝和基础TTL。
此前没有候选滚动窗口、移动时证据时间保护及完整H—K组合证据。本轮按SW-03补齐，
未接入实际ROS地图节点。只读检查沿`update→合同校验→暂存累计→snapshot/query`追踪，
并对照M1的整格odom滚动与已有覆盖/查询合同。

新增[RollingProbabilityMap](../mapping/ufm_mapping/rolling_probability_map.py)，继承固定
候选的累计与查询；在[固定累计器](../mapping/ufm_mapping/fixed_probability_map.py)加入
最小校验/网格准备扩展点。仍独立于M1覆盖更新，不调用M1.update后回改cell。
本轮未修改M1的local_map.py、默认包入口、ROS节点或公共消息字段。

[候选合同](../mapping/ufm_mapping/m2_contract.py)仅在显式滚动校验时允许有效刚体
`T_mapping_body`与同格点的观测origin；固定候选仍要求固定origin、单位body变换。
观测已显式处于odom，`T_mapping_source`须声明单位阵；body位姿来自观测时刻，
用其平移确定窗口，偏航不旋转odom轴。没有默认Radar=Camera=Body的假设。
非valid消息可声明变换unavailable，不读取其占位矩阵、不移动窗口且不能携带证据。

窗口重叠cell的索引、累计L、概率和原证据时间一起迁移，移出全部淘汰；
再次返回同一区域从unknown开始，新贡献从先验累计。合法空帧可改变覆盖revision，
不刷新地图header或cell证据时间。内部另记最新窗口移动时刻，早于该时刻的查询返回
unavailable，清除响应中的概率/索引等，避免用未来覆盖回答过去查询；不新增公共字段。
没有证据时地图仍unavailable，无回波、中性、过期、移入区域均不解释为free。

TTL严格大于配置才失效；query年龄仍取min(客户端max_age,配置TTL)。移动不复活旧证据，
超过TTL后的第一次有效非中性贡献从先验重启。整帧合同通过且临时状态构造完毕才提交，
坏变换/坏末尾体素不推进时间水位，合法后续可恢复；合法失效帧可推进输入水位但不刷新证据。
cell/L和身份账本均按显式限额保存，错run/clock拒绝，新run必须创建新实例。

## 验证与产物

新增13项[滚动/时序测试](../tests/test_m2_rolling_map.py)；最初候选模块缺失时RED，
实现后GREEN。覆盖正负/半格移动、偏航、重叠累计、远移/返回、无证据覆盖变化、
过去查询拒绝、失效变换/恢复、原子拒绝、TTL与客户端边界、40帧身份/容量限额、
确定性淘汰、错run/clock和新实例，以及不等距分辨率下三轴移动、观测完全在新窗口外。

[独立分数oracle](../tests/m2_oracle.py)扩展定时序列，不导入候选地图；新增
[2项测试](../tests/test_m2_timed_oracle.py)以手算分数检查TTL边界/重启及非法时间顺序。
原SW-01冻结oracle不修改。新增合成位姿工具
[m2_motion_fixture.py](../tests/m2_motion_fixture.py)和具名
[运动场景](../tests/m2_rolling_scenarios.py)；几何预期显式给定，不调用候选的格点辅助。
这些只是具名合成位姿，不是真实外参或传感器质量证据。

[离线运行器](../tests/m2_rolling_run.py)执行3组场景共15条公开占据：
重叠累计/TTL、移出/返回、失效/恢复。逐帧核对概率、observed、最后证据时间、
revision、窗口origin及地图证据时刻，同时执行现有ROS消息编解码往返；
额外40条序列检查cells≤2、L≤2、身份≤3。概率双精度容差1e-12。
拒绝/半格/新run等负例由定向测试覆盖，不声称均由这3组运行器场景验证。

首次通过run `m2-rolling-20261027T151819352444`保留。
随后补充限额子场景的实际配置与40条原始输入收据，最终run：

- [report.json](../.runtime/runs/m2-rolling-20261027T152322213048/report.json)：通过，解释器与离线范围。
- [config.json](../.runtime/runs/m2-rolling-20261027T152322213048/config.json)：具名默认参数。
- [fixtures.json](../.runtime/runs/m2-rolling-20261027T152322213048/fixtures.json)：15条运动输入及独立预期。
- [results.json](../.runtime/runs/m2-rolling-20261027T152322213048/results.json)：逐帧查询/快照；40条限额输入、覆盖参数、计数和最终快照。
- [固定回归报告](../.runtime/runs/m2-fixed-20261027T151819364202/report.json)：直接读取SW-01保存预期，9场景/31观测全部一致。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_m2*.py' -q
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m2_rolling_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m2_fixed_run.py --input .runtime/runs/m2-fixture-20261027T144245043459/fixtures.json
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

结果：新增15项测试，M2共37/37项定向、全仓506/506项轻量回归通过。
测试进程通过指定环境入口执行；运行器核对sys.executable为指定Conda解释器。
`git diff --check`通过。没有启动ROS Master、后台节点、模型/GPU、训练或完整forward。
测试日志与同run证据一起保存，未删除历史实验。

## 变更清单、限制与下一步

业务文件为fixed_probability_map.py、m2_contract.py及新增rolling_probability_map.py。
测试/工具为m2_oracle.py及新增m2_motion_fixture.py、m2_rolling_scenarios.py、
m2_rolling_run.py、test_m2_rolling_map.py、test_m2_timed_oracle.py。
同步PROJECT_STATUS、M2方案、开发/跨阶段计划、运行配置、数据/坐标说明、
正式M1矩阵补充、决策和实验索引。

已验证H—K的离线合成软件行为，不是概率校准或真实多帧相关性结论。
限额只证明条目数有界，不证明目标机RSS、更新/查询时延、温度或功耗达标。
身份缓存淘汰后旧时刻仍拒绝，但不承诺识别“旧ID篡改成未来时间”的全部冲突。
候选只消费fixture OccupancyObservation，不读取SensorBundle、LiDAR、target或训练mask；
输出confidence/uncertainty仍不可用，不开展M3/DEM。

下一步SW-04：默认latest兼容的显式私有候选选择，独立ROS正常/失效/乱序/老化/恢复，
公开占据回放与应用五类状态交接、原入口回归及进程/端口清理。实际ROS累计、真实输入、
研究模型质量/forward/权重加载、真实标定及正式PERF-01本轮均未验证。
正式M1/M2门禁保持。恢复直接使用既有M1入口，不加载M2缓存到M1；
当前候选尚未加入默认启动，因此无需修改任何现场运行配置即可继续旧链路。
