# EXP-20261014-011：基础滚动Local Map软件子范围

- 日期：2026-10-14；主责任：mapping_engineer；分支：`feature/engineering-initialization`（原有未提交改动保留）。
- 目的：在用户确认的范围内让Local Map随观测时刻body位置移动；只做软件fixture，不验证概率累计、DEM、模型接入和自主控制。
- 前置：本仓库原固定odom网格单点查询[EXP-20261014-010](2026-10-14-local-map-query-ros.md)；其338项测试和三种ROS模式是历史基线，不直接继承为本次结果。

## 实施与契约

固定窗口原先仅限制稀疏cell数，即使缓存按最旧时间淘汰，coverage和原点不变；
持续前飞最终使所有新点落在coverage外。现在仅在`rolling_enabled=True`时滚动，
初始origin为固定锚，以shape与resolution定大小，以OccupancyObservation携带的
观测时刻`SpatialContext.T_mapping_body`的odom平移计算每轴整格位移。
观测`T_mapping_source`必须是可用的odom单位阵，body是可用的有限合法刚体
变换；输入格网形状/分辨率相同，观测origin与锚点整格对齐。滚动时
先映射输入体素所处odom物理位置，再相对新地图原点求index；重叠历史cell
重排index但保留probability/confidence/uncertainty/last_observed_timestamp；
移出coverage直接淘汰，新进入区域保持无cell/unknown。无回波不等于free。
有效空体素帧允许移动且不更新历史cell时间；失效帧不移动。旧时间/身份
不一致拒绝；最近样本同内容重复忽略，冲突重复拒绝；run/clock改变必须
新建实例，不偷偷复用旧地图。查历史版本不支持，query只读当前revision。

仅在占位感知fixture启用`rolling_grid=True`时，生产者依据同一观测context
计算odom对齐移动观测格网和Radar点投影；转弯不旋转地图格轴。ROS默认
`enable_query=false`、`rolling_grid=false`、`rolling_enabled=false`保持旧入口；
专用`local_map_rolling_fixture.launch`明确开启两个滚动开关，分类0.3/0.7
仅属fixture。公共消息、服务及字段不变，mapping仍仅消费occupancy业务话题。

## 复现与结果

Python解释器为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，入口使用
`bash ros_ws/sim01_env.sh`；独立ROS入口需本地Noetic运行条件和空闲端口。

```bash
bash ros_ws/sim01_env.sh python -B -m unittest discover -s tests -p 'test_local_map_rolling.py'
bash ros_ws/sim01_env.sh python -B -m unittest discover -s tests -p 'test_*.py'
bash ros_ws/sim01_env.sh python ros_ws/local_map_query_run.py --mode rolling --port 11455
```

新增滚动单元测试先RED（构造器无`rolling_enabled`参数），实现后10项GREEN。
最终代码全仓轻量单元测试348项通过。滚动ROS成功run：
[validation.json](../.runtime/runs/local-map-query-rolling-20261014T174637917798/validation.json)、
[manifest.json](../.runtime/runs/local-map-query-rolling-20261014T174637917798/manifest.json)、
[cleanup-audit.json](../.runtime/runs/local-map-query-rolling-20261014T174637917798/cleanup-audit.json)：
13项检查通过，5次快照、7条occupancy、20次查询，Conda解释器、连接图隔离、
并发查询同版本和端口/进程清理通过。

第一轮实际ROS观察器复用了样本身份，`snapshot receipt`超时并以失败结束；
[失败validation](../.runtime/runs/local-map-query-rolling-20261014T165629906907/validation.json)
及[清理审计](../.runtime/runs/local-map-query-rolling-20261014T165629906907/cleanup-audit.json)
保留，修正fixture每帧sample_id后复跑成功。沙箱端口限制下的尝试未作为业务
失败或成功证据，不删除产物。

旧查询模式实际ROS重跑均通过：
[启用](../.runtime/runs/local-map-query-enabled-20261014T165807164611/validation.json)、
[关闭](../.runtime/runs/local-map-query-disabled-20261014T165809744997/validation.json)、
[未配置分类阈值](../.runtime/runs/local-map-query-unclassified-20261014T165812201199/validation.json)；
旧[PERF-01-A ROS入口](../.runtime/runs/perf01a-20261014T165848371533/perf-report.json)
40样本完整闭合。此次未改公共消息，不重新生成catkin消息；既有消息构建
通过是历史记录而非本次构建结论。

## 基础验收矩阵

| 场景 | 可核查条件 | 本次结果 |
| --- | --- | --- |
| 直线正负平移及半格 | 单元世界位置不变；恰半格偏正方向；origin/index同步 | 单元通过 |
| 偏航转弯 | Radar观测投影到odom、格轴不跟航向转、同世界cell更新 | 单元及ROS通过 |
| 部分重叠/移出/进入 | 保留重叠cell时间与质量；移出不可查，新区unknown | 单元及ROS通过 |
| 大位移及恢复 | 无重叠清空；恢复只填显式observed，不造free | 单元及ROS通过 |
| 边界及畸形几何 | coverage半开区间；错位origin、坏body、越界voxel拒绝且不部分移动 | 单元通过 |
| 去重、乱序、run/clock | 同样本重复无更新，旧时间/变域拒绝；新run需新实例 | 单元及ROS旧时间通过 |
| 断流老化 | 无效帧不滚动/不刷新历史时间；查询超龄为stale | 单元及ROS通过 |
| 容量与旧服务 | 活跃cell数不超配置上限；旧三模式和40样本入口不变 | 单元及实际ROS通过 |
| 正式资源/时钟/飞行 | 真设备数据、内存RSS上限、高速时延、功耗与正式PERF-01 | 未执行：外部输入阻塞 |

## 边界、恢复与文件

本次改动：`mapping/ufm_mapping/local_map.py`、
`perception/ufm_perception/placeholder.py`、上述两个模块已有ROS节点、
`ros_ws/local_map_query_run.py`、新增`ros_ws/launch/local_map_rolling_fixture.launch`、
`tests/test_local_map_rolling.py`及`tests/check_local_map_rolling_ros.py`；
同步`docs/DATA_FORMAT.md`、`docs/COORDINATE_SYSTEM.md`、`docs/SENSOR_INTERFACE.md`、
`docs/SYSTEM_ARCHITECTURE.md`、`docs/DEVELOPMENT_PLAN.md`、`docs/DECISION_LOG.md`、
`docs/EXPERIMENT_LOG.md`和`PROJECT_STATUS.md`。不改同级研究仓库或历史实验。
当前`.gitignore`按目录忽略`tests/`及`experiments/`：上述新增两个测试和本记录
存在于工作区，但普通`git status`不会列出。保留原忽略规则，不修改Git索引；
后续如需版本化，应经确认后仅对这三个明确文件单独处理。

可立即关闭两个滚动参数恢复原固定入口；若撤销此次实现，应仅回退本次
文件中的滚动增量和新增fixture，不覆盖原有未提交工作。风险：同run内
定位跳变与真实高速大位移无法仅凭本模块区分，须由上游保证连续odom
并在reset时提供新run；极大坐标/有限精度和任意旋转网格未作正式覆盖；
限制活跃cell数不等于验证进程RSS或机载吞吐。概率累计、DEM、模型质量、
设备时钟、功耗、正式PERF-01及对照试验保持未验证，按项目计划时间推进，
对照试验最后开展。
