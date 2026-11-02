# UAV-FusionMap 软件交付清单

日期：2026-10-29；版本：v1；任务：DELIVERY-SW-01；主责任：Technical Lead。
状态：已完成（仓内交付整理）；不是安装发行包、独立备份或正式阶段验收。
报告正文：[工程进展报告](REPORT_20261029.md)；过程与核验：[EXP-20261029-006](../experiments/2026-10-29-software-delivery-motion-design.md)。
后续增量：[SIM-MOTION-SW-01场景推进合同](SIM_MOTION_SW01_CONTRACT_20261029.md)已生成独立类型并通过离线验证；
随后[SW-02同FDM/受控采样门](SIM_MOTION_SW02_ENGINE_20261029.md)新增显式sim_motion_gate_run入口，
250步/10对实采和运行期故障通过；后续[SW-03交接](SIM_MOTION_SW03_DELIVERY_20261029.md)已完成
10组/14查询/独立回放与[新原生运动素材](../experiments/report_assets/sim-motion-20261029/README.md)。
本文保留原交付时819项/八图历史证据，845/856/862项分别见后续记录，旧图片不作运动证明。
后续[SW-04C同源码多场景交接](SIM_MOTION_SW04C_DELIVERY_20261029.md)完成9核心/3兼容、
84组业务/121查询、独立回放与[26张原生图/图注](../experiments/report_assets/sim-motion-multiscene-20261029/README.md)，
运动84项/全仓903项通过。旧默认入口保留，新运行仍最长1秒/无控制，不构成受控飞行或正式阶段验收。

## 1. 版本、环境与资产

核对时分支`feature/engineering-initialization`，HEAD为`d96d4439da1007489c80e7f21b132abff16505bf`。
实际交付还包含大量已修改/未跟踪文件，不能仅凭此提交重建全部当前内容。
本轮没有提交、打tag、推送、复制外部归档或生成源码压缩包；完整dirty清单保存在
[核验目录](../.runtime/runs/software-delivery-20261029T131105259841/initial-git-state.json)。
这是本机工作区交付索引，不是已经冻结的可移植release。历史run、失败记录、原始数据与环境原位保留。

所有新增Python命令使用`bash ros_ws/sim01_env.sh ...`，解释器固定：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -c 'import sys; print(sys.executable); assert sys.executable == "/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python"'
```

本机已有Noetic、Gazebo11、RViz、Qt/Ogre及Conda环境；JSBSim头文件前缀为
`.runtime/deps/jsbsim-1.1.13`，PX4源码位于`.runtime/src/px4-v1.13.3`。
依赖来源、构建和历史版本见[SIM-00A](../simulation/BUILD_SIM00A.md)，
环境隔离以[sim01_env.sh](../ros_ws/sim01_env.sh)及[配置](../configs/sim01_environment.bash)为准。
已有生成消息使用`.runtime/ros`，不构建外层catkin_ws；本轮未安装依赖或重新构建。

## 2. 能力与配置索引

| 范围 | 已有实现及可用入口 | 配置/接口 | 验证边界 |
| --- | --- | --- | --- |
| PX4/JSBSim状态与clock | [SIM-01B记录回放](../simulation/RUN_SIM01B.md)、SIM-01C/D历史入口 | sim01_state.yaml；AircraftState、独立可选ImuSample | 静止/时钟/故障/持续性子范围，不是当前场景飞行联动 |
| 无模型闭环 | local_map_query_run.py --mode inference | local_map_fixture.yaml；Radar/IR→Bundle→OccupancyObservation | paired fixture，默认M1 latest；research不可用且不fallback |
| M2/M3/M4 | 显式m2_stage_run.py / m3_stage_run.py / m4_stage_run.py；公开占据回放 | m2/m3/m4_fixture.yaml；原MapSnapshot/MapQuery字段 | 合成逆观测域与区间，M4固定合成注册；不能直接累计placeholder后验 |
| 独立地形 | terrain_fixture.launch、terrain_delivery_run.py、terrain_recording_replay.py | 独立terrain msgs；公开dataset及三文件recording v1 | 中心高程/no-data/实例/时间/pin；未接真实DEM或融合占据 |
| 场景/Radar/IR | sensor_scene_run.py；标准RViz PointCloud2/Image/TF/MarkerArray | sensor_scene.yaml、sensor_scene.rviz | 飞机固定，Radar几何代理、IR热强度代理，非真实模型 |
| 运动场景/Radar/IR/地图 | sim_motion_delivery_run.py；受控Gazebo+标准RViz及独立公开回放 | sim_scene_motion_fixture.json、同场景具名安装参数 | 真实同FDM短窗、精确tick Context、placeholder M1；无自动解锁/控制，完成自动清理 |
| 地图工作台 | report_rviz_run.py的demo/live/replay | report_rviz.rviz；只读快照/查询及clock | 查询与历史查看；不是传感器场景的替代入口 |
| 组合验收 | p5_combination_run.py（A/B）、p5_delivery_run.py（C） | tests/fixtures/p5_combination_*.json | 冻结软件37例，不关闭正式Phase 5 |

配置加载优先级、显式后端选择及错误处理见[运行配置](RUNTIME_CONFIGURATION.md)。
字段：[DATA_FORMAT](DATA_FORMAT.md)；坐标：[COORDINATE_SYSTEM](COORDINATE_SYSTEM.md)；
生产消费：[SENSOR_INTERFACE](SENSOR_INTERFACE.md)。这些是唯一语义依据，本文不另定义协议。

## 3. 常用启动与停止

从仓库根运行。以下均为已有入口，本轮核对CLI参数，不重新启动ROS或窗口；
历史实际运行证据在第5节，重跑会创建新run并使用本机GUI/socket。

场景、Radar点云、IR与地图交互查看：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sensor_scene_run.py
```

默认ROS 11711、Gazebo 11712，`:0`与用户GDM Xauthority；支持`--port`、`--gazebo-port`、
`--display`、`--xauthority`。关闭任一原生窗口或Ctrl-C结束自有会话。
保存当前视角、自动截图与话题说明见[场景使用说明](SENSOR_SCENE_VISUALIZATION.md)。

地图工作台与无模型短测分别运行，不与场景共享同一个Master：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/report_rviz_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/local_map_query_run.py --mode inference
```

工作台默认ROS 11701；短测默认11451并自动退出。地图工作台live接入已有图时须显式指定
`--master-uri`、`--clock-id`与`--ttl-ns`，回放用`--mode replay --receipt`；
完整示例见[RViz使用说明](ROS_VISUALIZATION.md)，不缺参fallback到demo。

独立地形四状态与真实录制/执行回放短测：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/terrain_delivery_run.py --with-rviz
```

默认ROS 11691，完成current/stale/unavailable/recorded截图后退出。
地形与场景没有共同注册，须独立查看；不得把两个Master的画面称为同空间融合图。

上述是交互/短测入口；A/B及C矩阵是显式验收工具，命令与期限分别见
[SW-02](P5_SW02_ROS_COMBINATION_20261029.md)、[SW-03](P5_SW03_NATIVE_DELIVERY_20261029.md)。
端口占用时选择其他端口，不停止既有进程、不执行pkill或清理历史目录。

## 4. 查询与离线复现

地图查询为`/uav/map/query`，CLI需提供map_id、frame、run/clock、整数请求时间与max_age。
场景map_id为`sensor-scene-local`、frame为`odom`；M4为`m4-scene-fixture`、frame为`map`。
请求时间从当前公开消息读取，不能填写墙钟或把旧run身份发给新实例。
下列是参数模板，变量须由当前会话提供，本轮只核对CLI没有执行在线请求：

```bash
bash ros_ws/sim01_env.sh env ROS_MASTER_URI=http://127.0.0.1:11711 /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/map_query_client.py --map-id sensor-scene-local --frame-id odom --run-id "$UFM_RUN_ID" --clock-id "sim:$UFM_RUN_ID" --timestamp-ns "$UFM_SAMPLE_NS" --max-age-ns 500000000 --point 8.25 0.25 0.25
```

sim01_env会清除调用终端的ROS变量，已有Master必须如上显式通过env传入。
返回保留occupied/free/unknown/stale/unavailable、概率/质量缺失及原观测时刻。
旧MapQueryClient没有主动服务调用期限；P5阻塞测试的外部子进程终止不属于客户端功能。

已有公开地形记录可脱离ROS严格执行回放；以下本轮实际执行，输出为本次新建文件：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/terrain_recording_replay.py --input .runtime/runs/terrain-delivery-20261029T123853103628/recording --output .runtime/runs/software-delivery-20261029T131105259841/terrain-replay-review.json
```

输出create-only，重用同一文件名会拒绝覆盖；后续重跑选新的输出位置。
原记录22事件/8查询。完整记录按事件执行并比对；incomplete记录在执行前拒绝，
篡改不能靠重写预期恢复。占据收据回放的latest/M2/M3/M4命令见[运行配置](RUNTIME_CONFIGURATION.md)。
不把P5测试JSONL直接当成local_map_replay的receipt对象，两种工具各有输入格式。

## 5. 验证证据与报告材料

| 证据 | 实际结果 | 本轮处置 |
| --- | --- | --- |
| [P5全矩阵](../.runtime/runs/p5-delivery-20261029T123816555451/full-matrix.json) | 37例、253事件、95检查点、228项比较 | 重新只读核对源码快照、冻结合同与事件收据；没有新跑37例 |
| [既有回归](../.runtime/runs/p5-sw01-20261029T123830392631/full-result.json) | P5 45项、全仓819项 | 核对日志/退出码；819项为上一轮结果，本轮未重跑全仓 |
| [本轮核验](../.runtime/runs/software-delivery-20261029T131105259841/report.json) | 证据/源码、八图来源、CLI帮助、相关既有定向 | 不生成新模型/ROS运行结论 |
| [八图与图注](../experiments/report_assets/p5-delivery-20261029/README.md) | PNG共727587字节，sources.json登记原图 | 逐字节比对来源并检查PNG可读，不重写原图或原像素结果 |
| [本轮严格回放](../.runtime/runs/software-delivery-20261029T131105259841/terrain-replay-review.json) | 在新输出中实际重建公开地形记录 | 原始recording不改，历史/live分开 |

报告[正文](REPORT_20261029.md)可直接阅读；图注已区分场景、Radar占位地图和独立地形。
不将819个不同层级测试与228项矩阵断言相加作为“总场景数”，不将像素非空说成感知质量达标。
原失败与修复记录沿实验索引保留，本轮未发布报告或改变阶段状态。

## 6. 未关闭门槛与恢复条件

| 门槛 | 状态/责任角色 | 所缺输入或关闭条件 |
| --- | --- | --- |
| 完整Phase 1 | 阻塞；simulation_engineer | 按既有退出复核补齐正式性能与工程保障，不因本次文档整理关闭 |
| IFACE-01 / Phase 2 | 进行中；sensor_engineer | 真实Radar/IR原始记录、单位、外参、设备时钟映射及质量来源；独立回放通过 |
| SENS-TRAIN-01 | 进行中；sensor_engineer | 真实监督标定、规模/标签质量；在线图继续无LiDAR/target/observed_mask |
| ALG-01 / Phase 3 | 按用户要求暂缓；perception_engineer | 恢复研究任务并通过候选质量门后，才审权重/真实forward/适配；不在本仓研究根因 |
| 正式M1—M5 / Phase 4 | 进行中；mapping_engineer | 真实输入/查询时延/内存，质量覆盖率，真实注册/DEM与占据融合；[M1矩阵](M1_INPUT_RESOURCE_GATE_20261015.md)保持 |
| PERF-01 / 正式Phase 5 | 阻塞；integration_engineer | 目标平台、设备配置、20ms起止端点/采样时钟、资源功耗/持续性及复杂场景；保持reference_only |
| ENV-03 | 阻塞；Technical Lead | 独立副本目标、复制与恢复验收；历史明确不归档，本轮不执行外部复制 |
| 运动场景扩展 | 计划；simulation_engineer | [SW-03单profile交接](SIM_MOTION_SW03_DELIVERY_20261029.md)已完成；下一批先设计多场景姿态/遮挡/无回波/恢复，不自动延长自由动力学窗口 |

2026-11-10保留为外部输入风险检查点，不是自动延期或自动通过日期。
新增运动软件按下一设计推进，不反复回到缺真实数据的任务。
任何失败保留新run与收据；恢复旧演示直接使用原入口并建立新run，不迁移旧地图或地形pin。
未提交文件与.runtime不具独立灾备保障，遵循[版本/产物政策](VERSION_AND_ARTIFACT_POLICY.md)。
