# EXP-20261014-009：基础Local Map纯业务单点查询

- 日期：2026-10-14
- 主责任角色：mapping_engineer；Technical Lead执行，tester验证
- 分支：`feature/engineering-initialization`，已有大量未提交实现与实验记录，均保留
- 范围：`mapping/ufm_mapping/local_map.py`、`tests/test_local_map_query.py`

## 目的与实现

既有PERF-01-A固定odom稀疏地图只有更新、快照和内部过期索引列表。本项增加公开
纯业务`query()`，按地图/坐标/run/clock/时间、覆盖范围、观测时间及显式分类阈值
返回occupied/free/unknown/stale/unavailable。查询不修改地图，不刷新旧观测时间。
未配置分类阈值时保留概率，返回unknown；0.3/0.7只作为测试fixture。

本项不改变地图的最新观测覆盖更新规则，不实现多帧概率累计、滚动窗口或ROS服务。
地图只消费OccupancyObservation，未读取训练监督LiDAR、AircraftState或原始Radar/IR。

## 验证

```bash
bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_local_map_query.py'
bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_perf01a*.py'
bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_*.py'
```

RED：实现前6组查询测试因无`query()`及阈值参数按预期失败；实现后6项通过。
PERF-01-A相关127项通过。后续全仓复核326项通过，实际Python为
`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。此前报告的320项来自加入6项
查询测试之前，本记录澄清计数，不修改历史产物。

覆盖：occupied/free、无阈值unknown、无观测/越界unknown、年龄等于/超过边界、
查询早于地图时间、空地图及地图/帧/run/clock不匹配、非法请求与输入不变。

## 结论与下一步

纯业务查询子范围已完成；ROS查询服务、application客户端、滚动地图、概率融合和
实际高速场景未验收。用户已确认下一项为ROS单点查询服务与独立fixture短测，记录
另见EXP-20261014-010；正式平台、设备时钟、功耗与研究模型对照试验继续后置。
