# EXP-20261028-007：M5 TerrainPrior/DEM设计审查

日期：2026-10-28；主责任：mapping_engineer；任务：M5-DESIGN-01。
状态：已完成（设计与既有接口审查），未实现DEM或变更公共接口。
交付：[M5具体方案](../docs/M5_TERRAIN_PRIOR_DESIGN_20261028.md)。

## 目的与保护范围

用户明确要求继续完成已安排的M5-DESIGN-01，即基准、no-data、质量及兼容恢复方案。
沿Local Map→Probability→Uncertainty→Scene Map→DEM的总体顺序推进设计，
不恢复暂缓的研究模型质量、不以真实数据缺失为由重复旧fake验收。

先读根规范/当前状态/架构和mapping、application、docs、experiments规则，核对
TerrainPrior预留、工厂、M4注册/更新/快照/查询、ROS节点/消息/编解码、应用/显示及占据回放。
分支feature/engineering-initialization已有大量未提交改动，全部保留；.runtime忽略规则命中。
本轮只修改中文设计/审查与状态索引；审计脚本/结果写入独立.runtime目录。
未修改业务/测试源码、运行配置、公共消息、研究仓库或Conda环境，没有Git提交或推送。

## 源码结论与设计选择

方案第1节逐项给出10条实际代码/合同证据，主要事实是：

- TerrainPrior仍仅为DATA_FORMAT §10预留，缺可运行生产者/消费者、ROS类型及M5选型。
- M4具名整格平移不等于地理基准注册；Scene只接占据且保留M3无量纲概率区间。
- MapCell/MapQueryResult没有height、terrain_id、逐cell先验角色或双时间域；
  泛型Uncertainty能放数组，不代表能把高度质量当作概率质量。
- application、RViz地图视图及回放都沿现有公开占据链；不能让应用直接读取DEM文件旁路接入。

据此，首个软件子范围拟为独立地形高程层，先做私有离线fixture合同与独立预期，
不把地形以下当occupied或以上当free，不改SensorBundle/OccupancyObservation/MapSnapshot/MapQuery。
真实DEM转换、ROS地形接口及占据辅助融合分别经过后续准入/协议/融合评审，不在本次实现范围。

具体方案已明确：水平/垂直CRS、axis/unit/affine/像素中心与行方向、具名map注册、
正高/椭球高/局部高度区别、必须网格缺失时失败、产品DTM/DSM区别、no-data/null与有效零高、
源采集时间和运行eligibility分离、到期与注册失效的优先级、米制高度界及缺失质量、
原子版本/有界缓存/冲突/恢复，以及新公共协议的生产者/消费者、兼容、迁移与回退闸门。

GIS约定只查阅GDAL、PROJ、NOAA官方材料，原始链接保留在方案第4节；
没有安装或调用GIS库，没有真实数据、校正网格、实际地理转换或独立控制点证据。

## 已执行验证

解释器实际核对为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，所有命令经sim01_env.sh。
独立审计：[audit.py](../.runtime/runs/m5-design-20261028T175543/audit.py)、
[report.json](../.runtime/runs/m5-design-20261028T175543/report.json)。
首次结果已保存；复现脚本只输出stdout，不覆盖该历史报告。

| 检查 | 实际结果 |
| --- | --- |
| M5选型探针 | create_map('m5_fixture')仍报unknown map backend，不宣称候选存在 |
| 默认GIS隔离 | 默认create_map()未导入pyproj/osgeo |
| 两组消息槽核对 | MapCell/MapQueryResult均没有地形高程/身份合同 |
| 像素中心 | GT=[100,2,0,200,0,-2]的首样本中心为[101,199] |
| 具名平移算例 | 源高度10、平移[10,-20,3]得到map样本[111,179,13] |
| 行方向算例 | 下一行中心为[101,197] |
| 正/负N算例 | H=100,N=20,h0=95时z=25；N=-20时z=-15 |
| 区间算例 | H∈[99,101],N∈[19,21],h0∈[94,96]得到z∈[22,28]m |

共10项通过，包含4项现有边界探针和6项独立有理数/高度算例；没有运行地形适配器。
report明确`dem_implementation_executed=false`、`real_dem_loaded=false`、`ros_master_started=false`。

既有定向回归40/40通过（0.884s）：test_m4_scene_map、test_m4_selection、
test_application_query_client、test_snapshot_visualization、test_map_query_ros。
日志：[m5-design-baseline-20261028.log](../.runtime/m5-design-baseline-20261028.log)。
覆盖当前Scene/选型/回放、概率质量和五类查询/显示；不是M5测试，不为纯文档新增业务测试。
之前SENS-VIS-01的全仓649项与Gazebo/RViz证据仅作为已有基线，本轮没有重复运行全仓或ROS。
本轮未发生失败探针；文档相对链接、代码引用与状态一致性检查、git diff --check通过。

复现命令：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B .runtime/runs/m5-design-20261028T175543/audit.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -c 'import sys,unittest; sys.path.insert(0,"tests"); suite=unittest.defaultTestLoader.loadTestsFromNames(["test_m4_scene_map","test_m4_selection","test_application_query_client","test_snapshot_visualization","test_map_query_ros"]); result=unittest.TextTestRunner().run(suite); sys.exit(not result.wasSuccessful())'
```

## 修改清单与下一交付

新增：docs/M5_TERRAIN_PRIOR_DESIGN_20261028.md、本审查记录。
更新：PROJECT_STATUS.md，以及docs中的DEVELOPMENT_PLAN、STAGE_ADVANCE_PLAN、SYSTEM_ARCHITECTURE、
DATA_FORMAT、COORDINATE_SYSTEM、RUNTIME_CONFIGURATION、DECISION_LOG、EXPERIMENT_LOG。
原因是将M5设计从“计划”推进为可评审交付，清晰区分已有接口和未来地形层，保留正式阶段门槛。

已有能力：M4合成Scene、公开占据/查询/回放与应用显示。
本轮交付：M5准入/兼容方案及16组拟议独立验收预期。
已验证：10项边界/算例、40项既有定向回归与文档检查。
未验证：DEM解析/注册/地形层实现、M5 ROS/应用交接、真实DEM/控制点、融合质量、资源和正式性能。

下一建议M5-SW-01（计划，mapping_engineer）：按方案确认后冻结私有fixture合同、
小型输入/限额及独立预期，仅实现离线输入校验，不创建地形候选、不扩公共接口或启ROS。
后续M5-SW-02/03分别验证候选及组合生命周期；任何公共协议扩展或DEM占据融合另行评审。
