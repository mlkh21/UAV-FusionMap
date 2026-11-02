# EXP-20261029-006：软件交付整理与运动联动设计审查

日期：2026-10-29；主责任：Technical Lead；状态：已完成（文档交付与设计核验）。
任务：DELIVERY-SW-01、SIM-MOTION-DESIGN-01；决策：ADR-042。
用户确认：先完成交付包/报告整理，再形成PX4/JSBSim与Gazebo传感器场景运动联动具体设计。

## 1. 修改目的与范围

P3、M1—M5公共合成软件和P5冻结软件矩阵已有交接，当前缺少统一的可读报告及启动/配置/
查询/回放/证据和未关闭门槛入口；下一功能缺口是固定飞机场景尚未与已有动力学链联动。
本轮新增[软件交付清单](../docs/SOFTWARE_DELIVERY_20261029.md)、
[含八图的报告正文](../docs/REPORT_20261029.md)与
[联动具体设计](../docs/SIM_SCENE_MOTION_DESIGN_20261029.md)。
同步PROJECT_STATUS、README、开发/推进计划、系统架构、ADR与实验及显示/素材索引。
未修改业务代码、消息、launch、配置、训练或研究仓库；未新增联动宿主/插件或运行器。

初始HEAD为d96d4439da1007489c80e7f21b132abff16505bf，分支feature/engineering-initialization；
dirty/untracked清单保存在本次核验目录，全部保留，没有自动提交/推送/打tag或外部归档。
交付是本机文档与证据索引，不把当前提交单独视为完整release，不把本机目录视为ENV-03备份。

## 2. 核验方式

先读取根规范/状态/架构、涉及模块AGENTS与数据/坐标/传感器接口，再沿真实入口追踪：
PX4原始MAVLink→SourceTimeline→state_adapter；Gazebo模型/时钟→Ray/相机→SceneStream；
既有JSBSimBridge::Run及本机FDM/Gazebo头文件能力。16项事实定位在设计第2节。
不从“目录/接口名称存在”推断已经具有真值源、运动联动或相机同步。

运行前核对指定解释器，核验脚本只读历史产物，所有新日志输出到
[software-delivery-20261029T131105259841](../.runtime/runs/software-delivery-20261029T131105259841/report.json)：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B .runtime/runs/software-delivery-20261029T131105259841/audit.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/terrain_recording_replay.py --input .runtime/runs/terrain-delivery-20261029T123853103628/recording --output .runtime/runs/software-delivery-20261029T131105259841/terrain-replay-review.json
```

核验脚本及回放输出create-only；后续复查应新建输出目录，不能覆盖本次结果。
既有像素检查器会写原目录，本轮没有调用它覆盖历史pixel-validation；只读其结果并检查PNG来源/可读性。

## 3. 实际结果

| 范围 | 本轮实测 |
| --- | --- |
| [综合核验](../.runtime/runs/software-delivery-20261029T131105259841/report.json) | 57项检查通过；包括源码/证据、16项源码事实、九个入口CLI帮助及四组相关既有定向结果 |
| 原P5矩阵 | 再比冻结37例/253事件/95检查点/228项收据，核对A/B和C装配源码快照与当前内容一致；未重跑ROS |
| 八图 | sources.json内八张PNG与原图逐字节一致、可读，共727587字节；未新抓图或修改原图 |
| 相关既有定向 | test_sensor_scene 11、test_sim01_source 25、test_sim01_clock_gate 14、test_sim01_frames 14，共64/64通过 |
| 严格地形执行回放 | 原公开记录22事件、8结果重新执行并匹配，生成新playback_session_id；mode=recorded，原实例不改，原记录不写 |
| 既有全仓结果 | 核对上一轮819项/P5 45项日志与退出码，未把它们记成本轮重跑 |

九个CLI帮助仅验证参数入口，不表示本轮在线服务或窗口运行。64项为已有实现回归，
不是新设计M01—M12验收；本轮没有启动ROS/Gazebo/PX4/JSBSim、完整模型或正式PERF-01。
文档/链接和修改边界检查另保存delivery-review.json；不因纯文档改动重跑819项全仓。
最终文档检查14页、765条本地相对链接及报告八张图片引用通过，git diff --check通过；
新回放除playback_session_id外与原回放逐值相同，HEAD未变化。

## 4. 设计结论与下一项

旧PX4状态源固定estimated，现有场景流只接受ground_truth且另有Gazebo时钟，直接拼接会
造成身份/时钟/坐标混用。选定新显式真值功能模式：同一个JSBSim FDM产生运动与时间，
Gazebo受控采样，逐步/逐采样ACK完成后才提交公共clock/状态；默认估计链与旧静态场景保持。
动力学用已有桥接类和JSBSim引擎，本仓薄宿主持有FDM读取句柄，不复制引擎或修改第三方原仓。
姿态/位置使用ECEF到固定初始ENU的具名注册，严格区分大地/地心纬度、质心/pilot点及角速度杆臂。

拟新增独立场景推进2.msg/1.srv、同帧ACK和有界状态机，当前仅为设计，没有生成新类型。
受控Gazebo Step与Ray/IR异步渲染握手仍待实测，失败须修订设计，不能以改戳或双自由时钟替代。
首版只做有界动力学初值运动，不解锁/起飞/发控制任务，不宣称受控飞行或真实定位质量。

直接下一项：SIM-MOTION-SW-01（主责任simulation_engineer），冻结profile、输入/独立预期、
场景推进合同与严格codec，使用真实生成消息验证线格式；随后SW-02动力学/Gazebo握手，
SW-03感知地图/原生显示交接。现有64项通过不能提前关闭新用例。

## 5. 未验证能力与恢复

真实设备/标定/研究模型质量、真实DEM/占据融合、目标机资源/功耗/20ms、完整阶段退出及
ENV-03独立恢复保持未完成；按用户要求不返回缺真实数据的暂缓任务。
新设计不是已运行的联动能力，当前报告仍使用固定飞机场景。
本轮仅新增文档和新核验输出，旧入口、图片和全部历史失败产物原位保留，无需迁移环境或恢复数据。
