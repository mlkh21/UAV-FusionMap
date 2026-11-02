# EXP-20261028-008：M5-SW-01私有输入与独立预期

日期：2026-10-28；主责任：mapping_engineer；状态：已完成（离线输入/预期软件范围）。
用户“继续下一步”确认[设计后续SW-01范围](../docs/M5_TERRAIN_PRIOR_DESIGN_20261028.md)。
交付：[冻结合同说明](../docs/M5_SW01_CONTRACT_20261028.md)。

## 目的与环境

沿总体阶段安排完成M5私有fixture合同、输入校验和独立预期；不实现地形层或DEM占据融合。
先核对根规范、状态、架构、接口与mapping/configs/tests/docs/experiments规则及真实工厂/消息链。
工作分支feature/engineering-initialization；大量既有未提交修改原样保留，不提交或推送。
Python经sim01_env.sh使用Radar-Diffusion指定解释器；未启ROS Master、Gazebo、训练、GPU或GIS依赖，
未改同级4D-Radar-Diffusion、原Conda环境或终端ROS选择。

## 文件与调用链

| 文件 | 改动原因 |
| --- | --- |
| configs/m5_terrain_fixture.yaml | 冻结合成DTM、源/目标水平与垂直基准、row-major高程/掩码/质量、显式运行授权和限额 |
| mapping/ufm_mapping/m5_contract.py | 独立无状态字段/单位/几何/时间/质量校验，16KiB有界JSON加载，私有中心请求校验 |
| tests/fixtures/m5_expectations.json | 在地形候选之前保存4样本/16组预期/7条未来事件，独立于候选源码 |
| tests/m5_fixture.py、tests/m5_oracle.py | 明确构造45组输入与未来事件载荷，只读独立预期 |
| tests/m5_fixture_run.py | 新run保存完整输入/预期/请求/未来事件，执行JSON实际加载与接收/拒绝检查 |
| tests/test_m5_fixture_contract.py | 21项契约、资源、精度/缺失、默认隔离及现有占据无修改回归 |
| docs/M5_SW01_CONTRACT_20261028.md、本记录 | 精确说明当前接口、模拟子集与尚未执行的候选行为 |

同步更新PROJECT_STATUS、DEVELOPMENT_PLAN、STAGE_ADVANCE_PLAN、SYSTEM_ARCHITECTURE、DATA_FORMAT、
COORDINATE_SYSTEM、RUNTIME_CONFIGURATION、原M5设计后续状态、DECISION_LOG及EXPERIMENT_LOG。
未修改已有地图/工厂/回放/感知业务、ROS节点/消息/生成配置、应用或可视化。

测试构建器读YAML→保存单个私有JSON→load_fixture有界读取→validate_spec；
`validate_request`只判断请求语法/域/中心格点，不返回地形结果。
不产生OccupancyObservation或MapSnapshot，不向默认地图装配新后端；m5_fixture仍报unknown backend。
高度界与M3无量纲概率区间严格分开，训练监督字段在各结构边界拒绝。

## 预期与实际

最终独立会话：[m5-fixture-20261028T182933778256/report.json](../.runtime/runs/m5-fixture-20261028T182933778256/report.json)。
输入：[inputs.json](../.runtime/runs/m5-fixture-20261028T182933778256/inputs.json)；
预期：[expectations.json](../.runtime/runs/m5-fixture-20261028T182933778256/expectations.json)；
完整后续事件：[future-events.json](../.runtime/runs/m5-fixture-20261028T182933778256/future-events.json)。

| 核对 | 实际 |
| --- | --- |
| 实际JSON加载/静态合同 | 45组：4接收（正常、有效零高、样本质量缺失、注册质量缺失），41拒绝，与独立声明一致 |
| 高程/坐标预期 | 4样本保存：首源中心[101,199]→map[111,179]、height10→13、界[12.65,13.35]；第二行y减小；负高程有效；no-data保持null |
| 请求 | 99/100/199/200/300共5个时刻语法均合法；未来应答状态只保存预期，没有运行候选 |
| 后续时序 | 16组预期与7条具完整输入/请求的事件已保存，含同身份不同内容；未运行去重/事务/到期/reset |
| 资源与反例 | 16KiB整边界成功，超1字节在JSON解码前拒绝；样本轴上限/掩码bool、非有限数、重复JSON key、深度/编码、非法单位/注册/插值均覆盖 |
| 旧路径 | 默认latest/M2/M3/M4独立进程不导入M5、pyproj/osgeo或torch；M5选型仍拒绝；纯输入检查前后占据快照/revision完全一致 |
| 全仓轻量回归 | 670/670通过（21.834s），新增21项；[日志](../.runtime/m5-sw01-lightweight-20261028.log) |

runner明确`terrain_layer_executed=false`、`occupancy_updated=false`、`ros_master_started=false`、
`real_dem_loaded=false`，不将保存的状态/高程预期写成候选验证成功。
有界检查只保护本次JSON文件/结构输入，不声称已经验证未来候选峰值、版本去重或64事件缓存。

首次19项定向检查中有一条测试误将“x平移置0、y/z仍非零”当作单位阵并要求拒绝；
该输入符合非零平移合同。已将测试修正为三轴平移全部置0，另外保留旋转/方向反例，
没有为通过测试放宽输入规则。首次通过20项后增加目标垂直基准和占据无修改检查，最终21项/全仓通过。
初次冻结会话[182852](../.runtime/runs/m5-fixture-20261028T182852246375/report.json)保留，
最终新增明确目标高程基准后使用182933会话，不覆盖先前产物。

复现：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m5_fixture_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p test_m5_fixture_contract.py -v
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

文档链接/代码引用、Git差异空白检查通过。因新模块未接任何运行装配，本轮未重启旧ROS/Gazebo；
既有实际ROS证据保持原记录，不写成本轮新验收。

## 能力与下一交付

已有：M1—M4合成地图、公开查询/回放、既有ROS/应用与Gazebo/RViz可视化。
本轮实现：私有地形输入合同、JSON加载/静态校验、独立冻结预期及复现runner。
本轮验证：45组输入/5个请求语法、独立算例、21项新增和670项全仓轻量回归。
未验证：独立地形候选、安装/采样/质量传播/去重/到期/事务、真实DEM、真实基准/标定、公共地形ROS或融合质量/性能。

下一项M5-SW-02（计划）：实现显式独立纯Python地形候选和私有回放，对本轮保存预期核对；
保留公共接口/默认地图不变，不接ROS或占据融合。之后SW-03覆盖时序/资源/失败恢复组合。
正式M1—M5、完整Phase 4、研究质量及PERF-01继续按原门槛，未自动关闭。
