# P5-SW-03：原生窗口、图故障与软件全矩阵交接

日期：2026-10-29；主责任：tester；版本：v1。
状态：已完成（冻结合成软件范围）；正式Phase 4/5退出条件保持。
依据：[组合设计](PHASE5_SOFTWARE_COMBINATION_DESIGN_20261029.md)、
[SW-01输入](P5_SW01_INPUT_CONTRACT_20261029.md)、[SW-02实际A/B](P5_SW02_ROS_COMBINATION_20261029.md)、ADR-041。
实际过程与失败见[EXP-20261029-005](../experiments/2026-10-29-phase5-native-delivery.md)。

## 1. 已有代码与本轮范围

复用生产地图节点、TerrainNode/Provider及公开应用客户端，复用SW-02的测试观察器、
clock ACK和实际服务codec；原生显示沿用sensor_scene_run与terrain_delivery_run。
本轮只新增以下显式测试入口与验收代码，公共字段、业务实现、默认launch均未修改。

| 文件 | 本轮职责 |
| --- | --- |
| [p5_delivery_run.py](../ros_ws/p5_delivery_run.py) | 冻结输入/预期，逐例独立Master，管理不属于子例的哨兵；调度独立原生窗口，重新对账A/B与C全部收据 |
| [p5_delivery_case.py](../tests/p5_delivery_case.py) | 实际生产节点装配、图审计素材采集；旧占据/地形pin建立及新run公开查询验证 |
| [p5_delivery_checks.py](../tests/p5_delivery_checks.py) | 图/身份/实际TCPROS连接、旧实例符号绑定、原生窗口与分图检查 |
| [test_p5_delivery.py](../tests/test_p5_delivery.py) | 6项图、实例、检查点和未注册叠图反例测试 |

这是测试控制台，允许观察多层公开话题以核对边界，不作为application部署入口。
application仍只消费公开地图或地形查询/状态，不读取地图或地形私有缓存。

## 2. 四个S09/C子例

| 冻结子例 | 实际动作与判据 |
| --- | --- |
| S09.clock_conflict | 真实创建第二个`/clock`发布者；getSystemState发现来源冲突，拒绝进入业务采集 |
| S09.missing_subscriber | 将真实地图占据订阅显式remap到`/p5/missing/occupancy`，该错误支路只建立空连接、不发消息；原占据链没有地图消费者，图及getBusInfo目的节点检查均拒绝。地图保持可正常退出，不用启动超时冒充图审计 |
| S09.bad_identity | 地图节点实际配置foreign run，ready身份与本例不同；图前检拒绝，未采集地图证据 |
| S09.recover_view | 实际旧run建立occupied/revision 1及四中心pin组；关闭两个业务节点后以新run启动，服务返回空地图revision 0、新地形实例，旧pin被拒绝、旧客户端收到新域状态后整组清空；随后运行原生窗口验收 |

正常地图仅消费占据，允许rospy因use_sim_time自动加入的基础设施`/clock`；
terrain只消费clock，无训练监督或越层业务订阅。前检从实际注册图、ready身份、
已连接TCPROS目的节点和服务存在性取得结果，不读取expected决定是否拒绝。

恢复子例的`$different`先绑定previous-run.json中真实旧组的provider_instance_id，
然后精确要求新实例不同；没有虚构旧ID或忽略实例字段。
旧/新业务节点使用同一隔离Master但不同run与不同业务进程，不继承业务对象。
新地图为空时，旧身份查询同样不可用；这不表示旧M1空地图有额外run绑定能力。

每例finally清理自有节点，核对退出/端口、原哨兵PID及start_ticks仍存活；
父监督器最后才停止自己的哨兵。图故障路径同样需要清理成功才能通过。
该哨兵证明本轮清理保留了具名非子例进程，不据此推断任意宿主故障均可恢复。

## 3. 原生查看与时间预算

实际运行两个既有入口，分别使用独立Master：

- Gazebo场景与标准RViz PointCloud2/Image/MarkerArray/TF；ROS 11733、Gazebo 11734。
- 独立地形RViz；ROS 11735，检查current、stale、unavailable及recorded四张渲染目标。

实际命令、图、配置与各自清理收据均保留。检查场景配置/实际图中无terrain叠层，
地形配置没有Radar/IR图层，两个窗口入口不共享Master。没有建立场景与地形的地理注册。
recorded另用历史话题和标注，不混入当前live数据。截图读取窗口自身渲染目标，未截其他桌面内容。
本轮[八张报告图片与中文图注](../experiments/report_assets/p5-delivery-20261029/README.md)可直接核对。

三个普通负向子例仍用45s监督期限。C恢复/显示聚合子例需要旧/新启动及两套原生入口，
外层明确用260s安全期限；内部场景110s、地形90s包含其既有90s/65s验收与退出预算，
启动就绪仍为15s。原生查看不是3s业务流或性能测试，未放宽A/B的业务期限。
冻结C事件的wall_ns只是逻辑最早调度点，实际完成时间单独记录；本轮恢复/显示/清理约48.16s，
不能把1ms声明解释为图形启动实测时延。每话题256条/合计16MiB的公开收据上限继续检查。

## 4. 运行与交付

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -c 'import sys; print(sys.executable); assert sys.executable == "/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python"'
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/p5_delivery_run.py --ab-run .runtime/runs/p5-combination-20261029T120350694666
```

默认端口11731及其+2/+3/+4；冲突直接退出，不停既有会话。可指定其他`--port`及
`--display`/`--xauthority`。只跑负向子集时用`--cases S09.clock_conflict S09.missing_subscriber S09.bad_identity`，
结果不标全矩阵。完整交付必须显式指定已有完整A/B证据，不暗选最新目录。
交互查看仍使用[场景入口](SENSOR_SCENE_VISUALIZATION.md)与[独立地形入口](M5_IFACE_SW03_DELIVERY_20261029.md)。
验收命令完成后窗口退出；不是启动长期飞行或常驻服务。

最终运行：[p5-delivery-20261029T123816555451](../.runtime/runs/p5-delivery-20261029T123816555451/report.json)。
S09为4/4子例、9事件/9检查点/12项比较。A/B既有33例不重复执行，
先核对其9份装配源码副本与当前源码字节相同，再逐例核对冻结输入/预期、事件顺序、
重新比较全部检查点，并要求原manifest、清理及地图回放通过。
[全矩阵报告](../.runtime/runs/p5-delivery-20261029T123816555451/full-matrix.json)明确ab_rerun=false：
合计37/37子例、253事件、95检查点、228项比较，6组生命周期表仍仅声明，不伪装成公共字段。
这是跨两次有明确来源的软件证据交接，不是37例在同一新会话全部重跑。

新增6项，P5定向45/45及全仓819/819通过；742次实际生成消息序列化回归也通过，
见[回归目录](../.runtime/runs/p5-sw01-20261029T123830392631/full-result.json)。
宿主/proc复查36个受管命令及本轮run标识，无残留；解释器与各自清理通过。

## 5. 未验证能力与后续

仅关闭P5-SW-01—03冻结合成软件工作包。真实Radar/IR质量、真实DEM、动态地理注册、
占据融合、机载资源/功耗/20ms、复杂环境飞行和完整Phase 4/5均未验收。
飞机仍固定，传感器为功能级代理；research保持fail-closed，未加载模型或启动训练。
不以重复fixture制造下一任务；下一批先按总体计划第8节
整理交付清单、可复现入口和未关闭门槛，不返回暂缓的研究质量/缺真实数据任务。
既有未提交改动全部保留，没有修改同级仓库、自动提交或推送。
