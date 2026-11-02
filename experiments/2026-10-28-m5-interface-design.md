# EXP-20261028-011：地形公共接口前置审计与具体设计

日期：2026-10-28；主责任：mapping_engineer；状态：已完成（设计交付与既有边界核对）。
任务：M5-IFACE-DESIGN-01；交付：[具体方案](../docs/M5_IFACE_DESIGN_20261028.md)。

## 目的与范围

按用户“继续”推进上一任务列出的下一项：在M5私有离线软件关闭后，提出独立地形查询、
状态、记录回放的公共合同，列出生产消费、完整字段、时间/坐标/高度质量、默认关闭、兼容与恢复。
本轮仅修改中文文档，不新增.msg/.srv、节点、codec、客户端、ROS启动或业务实现。

当前Git为feature/engineering-initialization，已有大量修改/未跟踪文件；未覆盖或清理，未提交/推送。
已读根AGENTS/状态/架构及mapping/application/ros_ws/tests/docs/experiments规则、
数据/传感器/坐标合同、SW-01/02/03真实入口与相关消息/客户端/回放/显示消费者。
.runtime仍被忽略；本轮审计输出/轻量日志保存在其中，历史产物不覆盖。

## 代码事实与设计结果

14项源码证据及行号列于方案§1。实际调用链：

```text
已有私有：m5_contract → TerrainFixture.install/query → terrain_replay
已有占据：perf01a_map_node → MapQuery/query_codec → MapQueryClient → 原占据RViz
拟议地形：TerrainProvider → 独立TerrainQuery/TerrainStatus → 独立客户端/显示
```

主要事实：旧MapQueryResult无高度/地形身份，客户端只接受占据五状态；
私有snapshot不是公共接口；私有query不推进时钟且允许未来/历史边界检查；
旧ROS客户端只限制等待服务时长，实际调用直接阻塞；现有回放不提供公共地形事件合同。
新地形消息包经实时环境查询仍不存在，不能声称接口已接通。

具体提案为独立包4.msg/1.srv与结构化公共记录：
TerrainHeightQuality、TerrainContext、TerrainQueryResult、TerrainStatus、TerrainQuery；
字段/枚举/空值flags、实例+revision绑定、source/运行时钟分离及三种高度质量角色已逐项列出。
拟议live门控明确区别于已有私有候选：拒绝未来请求、当前注册失效不返回历史高度、按实际evaluation追加到期。
状态心跳/clock接收超时与数据时效分开；安装失败与仍有效旧版分开表达；调用期限不冒充阻塞调用已取消。
初版只启动装载一版，不开远程安装端点；多版在离线Provider/公共回放核对。
记录有明确总量/单条/事件上限，缺输入或截断严格incomplete；旧占据接口、训练边界和TF权威保持。

## 实际检查

全部Python使用`bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ...`，
运行时sys.executable核对一致。没有启动ROS master/Gazebo/模型/GPU/GIS或联网下载。

| 检查 | 实际结果 |
| --- | --- |
| 已有候选5组查询 | [111,179]@100为valid/height=13，完整界向外包含[12.65,13.35]；no-data与覆盖外为unknown/null；@200为stale/原高度，@300为unavailable/null |
| 查询与版本/时钟 | 未来查询不改观察时钟；同版异内容明确拒绝且状态逐值不变；clock回退明确锁定，无高程 |
| 监督隔离 | grid加入lidar/target/observed_mask三种输入均拒绝；实际生成SensorBundle字段只有Radar/IR/state/context等既有字段 |
| 旧客户端 | 用地形valid状态作旧MapQuery回应时返回unavailable，无概率，不解释成free |
| 公共类型事实 | 实际MapQueryResult字段无地形高度；新uav_fusionmap_terrain_msgs未安装/不存在 |
| 相关既有定向 | 74/74通过（0.664s）：21项M5输入、24项候选、6项应用客户端、12项节点包装、7项旧服务codec/图规则、4项占据回放 |
| 文档检查 | 11份文档的首轮661个本地链接及源码行号引用无缺失/越界，见[静态检查报告](../.runtime/m5-iface-design-doc-check-20261028.json)；16组未来验收与三步工作包齐全，Git空白检查通过 |

定向复现命令：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -c 'import sys,unittest; sys.path.insert(0,"tests"); names=["test_m5_fixture_contract","test_m5_terrain_fixture","test_application_query_client","test_map_query_node","test_map_query_ros","test_local_map_replay"]; r=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromNames(names)); sys.exit(not r.wasSuccessful())'
```

产物：[实际边界审计JSON](../.runtime/m5-iface-design-audit-20261028.json)、
[74项定向日志](../.runtime/m5-iface-design-baseline-20261028.log)。
上一任务704项全仓结果保留为既有基线；本轮只改文档，未重跑全仓，不把旧结果计成本轮新验收。

## 变更清单与恢复

新增本记录与docs/M5_IFACE_DESIGN_20261028.md；更新PROJECT_STATUS、DEVELOPMENT_PLAN、
STAGE_ADVANCE_PLAN、SYSTEM_ARCHITECTURE、DATA_FORMAT、SENSOR_INTERFACE、M5总体设计、
DECISION_LOG、EXPERIMENT_LOG中的提案索引和任务状态。只追加设计指向，不冻结现有公共运行字段。
恢复为停止按此提案实施，原代码/启动/消息继续使用；保留本次审计与历史记录，不操作数据/checkpoint。

## 已有、已交付与尚未验证

已有：私有地形候选/回放、旧占据查询与显示。已交付：公共地形具体提案及14项源码审计。
已验证：上述既有边界与74项定向测试、文档静态核对。
未验证：提案消息生成/序列化、新Provider/ROS服务/状态、公共记录回放、调用超时/RViz地形显示、
真实DEM/高程质量/标定、正式RSS/时延/功耗。16组I01—I16全部是未来协议验收，不是本轮通过项。

下一项M5-IFACE-SW-01拟先做4.msg/1.srv、公开逻辑对象/codec与记录schema的离线验证；
新公共类型属于实施闸门，按根AGENTS §11.3/§11.4确认具体方案后执行；不在设计任务中自动生成。
完整M5/Phase 4、真实设备/研究质量/正式PERF门槛保持。
