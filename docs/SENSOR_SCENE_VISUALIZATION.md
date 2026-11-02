# 场景与Radar/IR仿真可视化

日期：2026-10-28；主责任：sensor_engineer；范围：SENS-VIS-01独立功能级场景。

这是本轮按用户澄清交付的入口：一个Gazebo三维场景窗口，加一个标准RViz传感器窗口。
此前[地图工作台](ROS_VISUALIZATION.md)仍可使用，但仅地图工作台不满足本任务。

10-29旧场景/Radar/IR/占据/RViz完整兼容回归通过，见
[EXP-20261029-001](../experiments/2026-10-29-m5-terrain-delivery.md)。
新增[可选地形显示](M5_IFACE_SW03_DELIVERY_20261029.md)是独立合成接口演示，未与本场景做地理注册或占据融合；本入口保持。
10-29后续[P5-SW-03](P5_SW03_NATIVE_DELIVERY_20261029.md)再次实际核对原生窗口/图/清理，
[本轮八张报告图与中文图注](../experiments/report_assets/p5-delivery-20261029/README.md)包括场景、Radar/IR/地图及独立地形四状态。
统一[软件交付清单](SOFTWARE_DELIVERY_20261029.md)与[八图报告正文](REPORT_20261029.md)已整理。
后续[SW-03运动交接](SIM_MOTION_SW03_DELIVERY_20261029.md)已完成单profile有界运动入口，
真实同FDM→Radar/IR→placeholder地图/公开查询与回放通过，并有[新运动图片](../experiments/report_assets/sim-motion-20261029/README.md)。
下列旧入口继续为固定飞机场景；运动验收命令单独使用sim_motion_delivery_run.py，完成会自动关闭本次窗口。
后续[SW-04C](SIM_MOTION_SW04C_DELIVERY_20261029.md)已完成同源码9核心/3兼容，
[多场景26张原生图/中文图注](../experiments/report_assets/sim-motion-multiscene-20261029/README.md)
包含S05遮挡和S07 before/empty/after/history。显式多场景入口示例：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_motion_multiscene_ros_run.py --case S07 --native
```

仍是最长1秒、无控制的自由动力学实采；完成自动清理。新视图IR显示范围用1帧，
避免连续空背景影响首次返回图像；默认旧静态视图配置不变，均不代表受控飞行或真实融合效果。

## 启动与截图

从仓库根目录执行：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sensor_scene_run.py
```

首次用本机已有g++/Gazebo11/ROS Noetic/Qt/Ogre开发库构建小型插件，不安装依赖。
缺依赖、模型网格、端口或显示权限时明确退出，不替换为旧fake图像或固定点云。
默认本机`:0`显示器、用户GDM Xauthority；其他会话用`--display`和`--xauthority`指定。
默认独占ROS 11711、Gazebo 11712，冲突时用`--port`和`--gazebo-port`另选端口，不终止既有会话。

- Gazebo：查看飞机、热箱、冷柱、暖柱、墙体和地面；原生相机支持旋转、缩放和选择。
  左上角`Save scene PNG`保存当前三维场景。
- RViz：`Radar point cloud`为同一场景碰撞采样生成的点云；右侧`IR intensity (fixture)`是
  同场景相机投影；`Placeholder map (Radar-only)`为点云驱动的占位地图，可分别开关。
  `File → Save sensor view PNG`保存包含IR面板的窗口；RViz原有`Save Image`可保存三维视图。
- 图片保存在本次打印的`.runtime/runs/sensor-scene-时间/figures/`，启动约15秒也会自动留图。
  每次会话复制自己的RViz配置，界面保存配置不会改仓库默认文件。
- 关闭任一窗口或终端Ctrl-C停止本会话；新启动创建新run，不混用旧地图。

RViz使用内置PointCloud2、Image、TF、MarkerArray显示器，配置是标准
[sensor_scene.rviz](../configs/sensor_scene.rviz)。辅助C++入口仅装载标准VisualizationFrame、
安排面板和读回自己的渲染目标，不要求自定义RViz显示插件，也不抓取其他桌面窗口。

## 话题与时空语义

| 显示/边界 | 话题或来源 | 语义 |
| --- | --- | --- |
| 三维场景 | [sensor_scene.yaml](../configs/sensor_scene.yaml)生成Gazebo world | 可见几何和碰撞几何同源，物体各有独立可见颜色与热强度材质 |
| Radar | `/uav/sensors/radar/raw`，PointCloud2 | radar系，m、m/s，Doppler正向away；power为arbitrary/uncalibrated_intensity |
| IR | `/uav/sensors/infrared/raw`，Image | thermal_optical系，320×240，32FC1、fixture_intensity；相机内参另见camera_info |
| 状态 | Gazebo Odometry → `/uav/sim/state` →既有state_adapter→ `/uav/sensors/state` | state_source保持ground_truth；不是PX4 estimated |
| 在线输入 | `/uav/sensors/bundle` | 只含Radar、IR、AircraftState及既有上下文，不含训练监督 |
| 占位地图 | `/uav/map/snapshot` → `/uav/visual/map` | 既有placeholder→latest Local Map；没有IR模型融合或自由空间射线填充 |

具名注册`gazebo_scene_world_enu_identity_v1`仅适用于本场景：scene_world和odom显式同原点ENU。
body为FLU，Radar安装平移`[0.8,0,0]m`；热相机同位置，optical到body四元数
`[-0.5,0.5,-0.5,0.5]`。当前body位于`[0,0,2]m`，所以Radar到odom平移为`[0.8,0,2]m`。
这是合成安装配置，不是真实标定。动态odom→base_link仍由既有state_adapter唯一发布；
新模式显式选择`scene_ground_truth`，旧模式默认`px4_estimated`。

Gazebo采用lockstep，采集时间来自同一仿真时钟；Radar/IR配对偏差上限5ms，pose年龄上限10ms，
待配对Radar超40ms拒绝，队列有界。时钟回退锁定本run，不能自动恢复混用；过期、无回波和
算法不可用不解释为free。暂停可查看历史画面，不代表证据仍然新鲜。

## 能力范围

Radar是静态目标的首表面几何/FOV/量程近似：96×24采样、约80°×40°视场、0.5–30m；配置请求10Hz。
本机lockstep短窗实际Radar约5Hz、IR约10Hz，不代表已达请求频率或实时性能门槛。
无电磁传播、真实RCS、多径、虚警或目标速度模型。内部使用Gazebo通用碰撞射线，不发布、
订阅或生成LiDAR监督。静态目标Doppler仅考虑传感器自运动，不代表动态目标速度仿真。

IR是Ogre独立`FusionThermal`材质通道的场景投影与遮挡；冷/暖/热合成强度约0.15/0.60/0.90。
它不是普通RGB改名，不是Kelvin温度、辐射测量、传热或真实相机噪声模拟。
placeholder目前只将Radar回波映射为占据0.9；IR可显示、配对和传输，但没有真实Radar–IR融合。

当前飞机固定悬置于场景中；本入口不启动PX4/JSBSim飞行动力学，不提供解锁、航线或自主控制。
已有PX4/JSBSim入口保持独立，尚未把它与此Gazebo传感器场景联动。真实设备、研究模型质量、
动态目标Doppler、真实标定及正式PERF-01均未验证。

运行验收加`--check`：检查几何表面、冷暖像素、安装坐标、公开Bundle/地图、无训练ROS图、
原生渲染像素与进程清理；仅该检查会临时移动热箱1.5m验证两个传感器都随场景变化，随后恢复。
报告素材与实际证据见[实验记录](../experiments/2026-10-28-sensor-scene-visualization.md)。
