# EXP-20261028-013：独立地形Provider/ROS及拒绝恢复

日期：2026-10-28；主责任：mapping_engineer；任务：M5-IFACE-SW-02。
状态：已完成（合成Provider/独立ROS软件范围）。依据：用户“继续”、ADR-040及
[已交付具体方案](../docs/M5_IFACE_DESIGN_20261028.md)。
实现与接口说明：[SW-02说明](../docs/M5_IFACE_SW02_PROVIDER_20261028.md)。

## 当前问题与实施边界

SW-01已具备公共类型/严格codec，但没有公共运行层。私有TerrainFixture.query不推进时钟，
允许离线未来边界检查，不能直接等同live服务。旧占据ROS与应用继续独立。
本轮新增mapping串行Provider与只订阅clock的独立薄节点，执行实际evaluation、来源/时效、
实例/revision/pin、单次启动安装、状态心跳和拒绝恢复；不接真实DEM或占据融合。
客户端、公共录制/执行回放及RViz地形未实施，仍属于SW-03。

已核对根AGENTS/状态/架构、数据/传感器/坐标合同、M5接口设计/合同及各涉及目录AGENTS。
沿真实链读取TerrainFixture.install/query、dataset_context、公共codec、旧map节点与ROS进程/图审计工具。
分支feature/engineering-initialization，大量既有修改/未跟踪文件全部保留；新源码不被忽略，.runtime被忽略。
没有修改同级研究仓库、原Conda环境、旧消息/入口、历史实验或checkpoint；未提交/推送。

## 具体实现

先保存[独立运行预期](../tests/fixtures/m5_provider_expectations.json)，随后实现：

| 文件/范围 | 修改原因与行为 |
| --- | --- |
| mapping/ufm_mapping/terrain_provider.py | 公共运行门控与原私有采样分离；一把RLock保护clock/安装/查询/状态，完整版本投影先准备后提交；UUID区分进程实例 |
| ros_ws/terrain_ros.py | 公开codec薄包装、clock唯一发布者/连接callerid审计、单服务槽和墙钟心跳，不复制地形算法 |
| ros_ws/src/uav_fusionmap_terrain/ | 新CMakeLists/package.xml/scripts/terrain_node.py；仅rospy/rosgraph_msgs/新消息包依赖，固定指定Python |
| ros_ws/launch/terrain_fixture.launch | 独立入口默认enabled=false；显式启用才装配dataset/run/clock/指定clock发布者 |
| tests/test_m5_provider.py、test_terrain_node.py | 15项Provider与5项包装/默认关闭测试；真实消息codec沿用SW-01 |
| ros_ws/m5_provider_run.py | 独立master/新run、公共dataset保存、旧占据兼容、重启协调与进程/端口清理监督 |
| tests/check_m5_provider_ros.py、m5_clock_peer.py | 真实服务/clock观察者与测试专用异常clock发布者；不属于产品客户端 |

新增中文说明/本记录；更新PROJECT_STATUS、SYSTEM_ARCHITECTURE、DATA_FORMAT、SENSOR_INTERFACE、
M5接口设计、SW-01后续指向、DECISION_LOG、DEVELOPMENT_PLAN、STAGE_ADVANCE_PLAN、EXPERIMENT_LOG。
旧私有TerrainFixture、公共类型/字段、工厂、旧节点/launch与可视化源码均未修改。

## 实际命令与环境

运行前核对sys.executable为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。
Noetic/catkin沿既有环境，隔离构建仅.runtime/ros，无外层catkin_ws构建、依赖安装或模型/GPU调用。
实际执行：

```bash
bash ros_ws/sim01_env.sh cmake -S ros_ws/src -B .runtime/ros/build -DCATKIN_DEVEL_PREFIX=/home/zxj/catkin_ws/src/UAV-FusionMap/.runtime/ros/devel -DPYTHON_EXECUTABLE=/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python
bash ros_ws/sim01_env.sh cmake --build .runtime/ros/build --target uav_fusionmap_terrain_msgs_generate_messages -j2
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/m5_provider_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
```

定向104项由unittest按模块加载test_m5_fixture_contract/test_m5_terrain_fixture/test_m5_time_resources/
test_m5_iface_codec/test_m5_iface_recording/test_m5_provider/test_terrain_node，全部经同一sim01_env与固定Python。
定向/全仓在受控子进程保存完整日志；没有启动真实服务以外的长作业。

## 实际验证

| 检查 | 实际结果 |
| --- | --- |
| Provider新增 | 15/15通过：默认关闭、域绑定、独立边界预期、正/零/负高、no-data/覆盖外、质量、未来/激活前/当前注册门控 |
| 状态/版本/并发 | 旧版保留且安装失败单独可见；幂等不延寿、冲突/退役拒绝；公开元数据/私有准备失败可同身份重试；64身份后锁定；线程证明查询与clock串行、竞争busy无缓存载荷 |
| 包装新增 | 5/5通过：绝对clock身份、多发布者/错误连接header/旧图拒绝、图不可用清载荷、服务busy/invalid_request、旧launch不含地形 |
| 隔离构建 | 新独立节点包被catkin识别，固定Python devel包装生成；新4.msg/1.srv目标构建通过，无旧类型字段改动 |
| 实际ROS主场景 | 28查询、15状态收据、38项检查全部通过；四样本及no-data/覆盖外、语法错、域/实例/revision拒绝、未来请求与历史到期语义通过 |
| clock实际故障 | 认可源暂停→1s接收超时；墙钟心跳继续增长；恢复同sim值不刷新采集/安装时间；新增异常发布者的较小时间拒绝，不采用其时间 |
| reset/实际恢复 | 合法源clock回退后再增长仍锁定；监督器停止旧实例、以新run启动，revision=1但UUID不同；旧pin/旧域明确拒绝 |
| 旧占据兼容 | 同图使用未改旧map节点，1观测/1快照；地形安装前、断流及最终服务关闭后旧查询逐值一致，revision/概率/观测时间不变 |
| 默认关闭/图 | 实际roslaunch --nodes默认无地形节点；地形订阅仅/clock，无LiDAR/训练/定位/TF旁路，无安装服务 |
| 清理/解释器 | 五个监督进程退出0，无强制信号，无残留审计Python PID，11681端口释放；解释器审计通过 |
| 最终定向 | M5/包装相关104/104通过，34.068s |
| 最终全仓轻量 | 753/753通过，55.944s（733既有+20新增） |
| 旧定义核对 | 19份既有消息/服务及旧包CMakeLists/package.xml与上轮冻结副本逐字节一致，未计算Hash |
| 文档/工作区 | 12份相关文档694个本地链接无缺失，Git空白检查通过；检查报告保存于回归目录doc-check.json |

busy/联合原子性是离线线程及包装测试证据，不冒充真实网络并发压测；服务发现/调用客户端期限仍未实现。
源身份核对是显式ROS图/callerid一致性，不是恶意环境认证；图变化存在观察窗口，服务每次重新审计。
本轮只有合成纳秒边界算例，不证明实物设备时间同步、DEM基准精度、真实区间覆盖率或高速机载资源。
状态queue=1、服务业务槽=1与64身份限制不是ROS连接/接收内存、RSS或正式PERF-01结论。

## 失败与修正记录

首轮15项测试有两处脚手架TypeError：辅助函数重复传expected_provider_instance_id关键字，
改为先建请求再update，随后15/15通过；没有改预期或业务阈值。

第一次实际ROS入口在沙箱本地socket探针即报PermissionError，未启动任何子进程；
清理探针同样被权限拒绝，因此cleanup=false，不能将其写成已运行ROS或残留进程故障。
失败目录[保留](../.runtime/runs/m5-provider-20261028T202752637694/)。
随后按工具权限要求申请沙箱外运行并获准，完整实际ROS通过且正常清理，无未解决权限阻塞。

## 产物与恢复

实际ROS目录：[m5-provider-20261028T202824188908](../.runtime/runs/m5-provider-20261028T202824188908/)。
其中[validation.json](../.runtime/runs/m5-provider-20261028T202824188908/validation.json)、
[receipts.json](../.runtime/runs/m5-provider-20261028T202824188908/receipts.json)、
[manifest.json](../.runtime/runs/m5-provider-20261028T202824188908/manifest.json)、
[cleanup-audit.json](../.runtime/runs/m5-provider-20261028T202824188908/cleanup-audit.json)、
两版run配置、独立预期、各进程日志保留，目录不覆盖历史产物。

轻量回归目录：[m5-provider-regression-20261028T202939463974](../.runtime/runs/m5-provider-regression-20261028T202939463974/)，
包含[targeted.log](../.runtime/runs/m5-provider-regression-20261028T202939463974/targeted.log)、
[full.log](../.runtime/runs/m5-provider-regression-20261028T202939463974/full.log)及report.json。

恢复方式：停用新增terrain_fixture.launch/节点，继续原占据/场景入口；保留新增源码/记录/生成物。
不删除数据/checkpoint、不reset工作区、不覆盖历史实验、不自动提交/推送。
下一项M5-IFACE-SW-03；正式M5/Phase 4、真实DEM/占据融合、模型质量与PERF-01仍未关闭。
