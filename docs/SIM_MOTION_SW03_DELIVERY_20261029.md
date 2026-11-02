# 运动场景感知地图与原生窗口交接

日期：2026-10-29；任务：SIM-MOTION-SW-03；主责任：tester。
状态：已完成（单一有界运动profile的软件交接）；不代表受控飞行、真实模型质量或正式阶段退出。
依据：[运动设计](SIM_SCENE_MOTION_DESIGN_20261029.md)、[SW-02实采闸门](SIM_MOTION_SW02_ENGINE_20261029.md)、
ADR-042；[实际记录与失败](../experiments/2026-10-29-sim-motion-delivery.md)。
原生新图：[素材与图注](../experiments/report_assets/sim-motion-20261029/README.md)。

## 1. 已有代码与本轮范围

复用SW-02同一FDM/PX4/受控Gazebo实采，以及既有SceneStream、PerceptionEngine placeholder、
M1 latest、公开MapQuery/占据回放、SnapshotView与标准RViz显示器。
只新增显式交接入口和测试监督、修补本次暴露的位姿先后竞争及启动中断关闭；
公共消息字段、旧默认launch、研究后端/模型/DEM/占据融合保持原范围。

链路为同FDM真值/时钟→state_adapter唯一TF→真实Radar/IR→SceneStream→placeholder→M1 latest→
公开query/snapshot。核验器可独立读真值和各层收据，生产mapping仍只读OccupancyObservation。
没有用测试oracle替代真实动力学、Ray或Camera，没有在线LiDAR/target/observed_mask。

## 2. 精确时刻与失效规则

首轮真实链路虽收到10组下游消息，却有5帧选择了早4ms的历史pose。旧策略允许≤10ms，
但这不等于本次同帧几何：Camera/Ray在目标pose采样，历史pose会造成投影错位。
新增默认关闭的SceneStream require_exact_pose，以及scene_sensor_node的--require-exact-pose；
只有新运动入口显式开启，等待同采样时刻state，不把旧pose当fallback。
原IR差≤5ms、历史pose≤10ms、配对等待≤40ms仍保留，新增策略只收紧运动模式。
配对期限内精确pose仍未到即拒绝；不能为取得通过改采样时间、扩大等待或重发旧证据。

每个成功采样tick提交业务clock/state后，测试监督有界等待该时刻下游地图快照，再发下一步FDM命令。
这是功能闭环/可核对交付，不是20ms实时或自由运行吞吐验收。
独立核验用实际SceneFrame四元数和非零0.8m杆臂，重算全部Radar点的odom位置和栅格索引，
对实际Bundle Context及placeholder占据逐值核对；不以最新到达状态覆盖历史观测。

terminal沿既有真值分支非几何传播，SceneStream清空/锁定，未提交tick的未来raw不进入Bundle。
首采样ACK失败时clock止于96ms，raw100ms可已发布，但地图仍revision0、没有占据。
运行期第250步失败时只允许9组/最后900ms地图证据，clock止于996ms，1000ms raw不成为新证据。

首采样失败使PX4仍处于启动脚本中。旧进程组SIGINT会让daemon返回255；本次改为只在该
明确故障分支调用已有px4-shutdown。POSIX shutdown在daemon中system_exit(0)，
可能先关闭IPC使调用客户端返回255。验收严格区分客户端返回值与daemon退出：
保存两者、要求daemon=0及Exiting NOW标志、无强制信号、所有自有进程/端口清理。
未放宽旧daemon退出要求，没有为完成启动继续推进失败run的FDM/clock。

## 3. 原生显示与查询语义

标准RViz显示真实PointCloud2、32FC1 IR及公开地图Marker；同次Gazebo原生窗口显示代理运动。
截图由本窗口/渲染目标读取，通过本run的基础设施请求文件确定before/after/history阶段，
不读取桌面其他窗口、不拼接或重绘。手动截图和旧默认自动截图行为保留。
运动模式clock失联3s后，原生RViz reset并关闭Radar/IR显示，地图沿既有SnapshotView
呈历史unavailable，底栏明确History: source clock stopped。正常采样画面显示源时间和真值来源。

MapQuery服务仍按显式query_timestamp/max_age工作，没有新墙钟liveness门；
即使源已停止，以原1s查询时刻请求仍可能occupied，未来超过TTL的请求才stale，原证据时刻保持。
原生历史显示的3s墙钟条件不冒充地图服务自身已禁止旧时刻查询。
首份sensor-audit的旧clock_reset字段实际取stream.failed，terminal时也为true；
本轮以实际clock收据和terminal计数判定，不把这个旧字段名当真实clock回退证明。

## 4. 实际结果与边界

| 核验 | 结果与证据 |
| --- | --- |
| 正常/新run恢复 | [161731864328](../.runtime/runs/sim-motion-sw03-20261029T161731864328/delivery-validation.json)：250步/1s、251条clock/state/TF、10对raw/20 ACK、10 Bundle/占据/快照，旧run查询拒绝；启动时公开query确认revision0空地图 |
| 观测时刻几何 | 13,217真实回波，10帧IR差与pose_age均0；独立旋转/杆臂/点投影/栅格oracle一致，全部占据质量仍缺失，不产生free |
| 公开应用与回放 | 14条查询，occupied/unknown/stale/unavailable及原证据时间正确；独立应用CLI实际occupied，独立回放进程10快照/14查询逐值一致 |
| 首采样故障 | [161927705875](../.runtime/runs/sim-motion-sw03-20261029T161927705875/delivery-validation.json)：clock96ms、零Bundle/占据/快照、空地图unavailable、terminal锁定，daemon退出0，清理通过 |
| 运行期故障 | [161450959654](../.runtime/runs/sim-motion-sw03-20261029T161450959654/delivery-validation.json)：clock996ms、9 Bundle/占据/快照和13查询，未来raw不提交，公开回放及清理通过 |
| 第二clock拒绝 | [161615581161](../.runtime/runs/sim-motion-sw03-20261029T161615581161/manifest.json)保持failed，原因motion_graph_authority:/clock；这是预期负例，未创建FDM/PX4，全部自有进程退出0 |
| 原生窗口/像素 | 正常同次六个Gazebo/RViz前后/历史渲染目标及IR viewport非空；前后133,109/174,999像素显著变化，历史raw显示实际disabled，地图unavailable；另交付五图原件副本 |
| 软件/旧入口 | 新增6项、运动定向43/43、全仓862/862；20组真实消息字节与17份旧定义保持，旧estimated/T-14、静态Gazebo/RViz及SW-02默认引擎入口实际回归通过 |

正常实际收据共10,125,044线格式字节，仍在16MiB/每流512上限内；不是RSS或正式性能。
无回波不刷新旧证据、IR 5ms/pose 10ms/等待40ms各自+1ns边界、精确pose等待有新增离线测试。
本次真实运动profile每帧都有回波，不能把这些离线反例称为真实无回波场景已执行。
坏版本/枚举/身份/训练字段及同step冲突等沿SW-01/02测试证据；本轮不把全部M01—12反例
统一说成真实引擎注入。详细证据类型映射见实验记录。

## 5. 运行与恢复

从仓根使用固定Conda入口。每次新run、新Master、空地图；失败run不恢复原身份：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_motion_delivery_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_motion_delivery_run.py --no-native --fault missing-ir-ack --fault-step 25
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_motion_delivery_run.py --no-native --fault missing-ir-ack --fault-step 250
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_motion_delivery_run.py --no-native --inject-clock-conflict
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_motion_run.py --full
```

clock-conflict命令预期exit1，需核对具体图拒绝及清理，不把任意错误都算负例通过。
本机默认ROS/Gazebo11801/11802，PX4固定端口及既有PX4也检查；不并行两套PX4。
--previous-run-id可明确提供上一运行身份验证拒绝；新run仍使用新时间/实例，不沿用旧raw。
命令是有界验收入口，完成会关闭自有窗口/进程。旧静态展示入口继续见[SENSOR_SCENE_VISUALIZATION](SENSOR_SCENE_VISUALIZATION.md)。

下一批可先设计有界多场景运动回归（不同初始姿态、遮挡/无回波、故障恢复），
先冻结独立预期与范围，再决定新增profile，不自动扩展飞行时长或控制指令。
真实设备/研究质量/DEM融合/机载资源和正式阶段退出仍按原外部准入跟踪，不重复暂缓任务。

2026-10-29后续：[SW-04多场景具体设计](SIM_MOTION_SW04_MULTISCENE_DESIGN_20261029.md)已完成，
新多场景尚未实施。直接下一项SW-04A独立清单/预期与离线线格式，B/C再分步装配和运行交接。
