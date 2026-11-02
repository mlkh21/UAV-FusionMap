# EXP-20261028-006：场景与Radar/IR仿真可视化

日期：2026-10-28；任务：SENS-VIS-01；主责任：sensor_engineer。
类型：真实Gazebo/RViz软件仿真、场景扰动、契约及旧ROS/全仓回归；状态：已完成（所列功能级范围）。
分支：feature/engineering-initialization；开发前Git包含大量既有修改，全部保留；未提交、推送。

## 目的与只读发现

用户明确需要场景、Radar点云和IR等传感器仿真，还要求独立三维场景窗口。
APP-VIS-01地图工作台不覆盖这个目标，旧实现与素材保留，不再以其完成代替本项。

真实调用链核对：`sensors/ufm_sensors/perf01a_fixture.py:make_fake_radar`默认生成固定点，
`make_fake_infrared`为二维背景/热点；它们不是场景相机。现有PX4/JSBSim入口无已接入的
三维传感器GUI，FlightGear未就绪；本机已有Gazebo11.15.1、Noetic RViz及C++开发库。
只读核对Git/忽略规则后，所有新增运行产物写入被忽略的`.runtime`，没有修改同级研究仓库。

## 改动与真实链路

| 文件/交付 | 用途 |
| --- | --- |
| `configs/sensor_scene.yaml`、`simulation/ufm_simulation/sensor_scene.py` | 显式场景/安装/热属性；结构化生成同源visual/collision world；读取既有plane body.dae可视模型 |
| `sensors/gazebo_scene_radar.cpp`、`sensors/gazebo_scene_ir.cpp` | 静态目标几何Radar与独立热强度材质相机；标准PointCloud2/Image/CameraInfo |
| `simulation/sensor_scene_media/materials/scripts/fusion_thermal.material` | 可见颜色与FusionThermal热强度分别指定，不把RGB改名成测温 |
| `simulation/gazebo_scene_pose.cpp`、`ros_ws/scene_state_source.py` | Gazebo ENU/FLU真值→既有AircraftState，保留ground_truth |
| `sensors/ufm_sensors/state_adapter.py`、既有`state_adapter_node.py` | 默认PX4路径不变，显式scene_ground_truth/具名注册；仍由既有节点唯一发布动态TF |
| `sensors/ufm_sensors/scene_stream.py`、`ros_ws/scene_sensor_node.py` | 原始测量语义恢复、有界配对、观测时刻安装变换，输出既有SensorBundle |
| `ros_ws/scene_map_viz.py`、`ros_ws/rviz_map_markers.py` | 仅公开snapshot与clock→标准MarkerArray；空状态组用DELETE，未知/过期不转free |
| `ros_ws/native_scene_rviz.cpp`、`configs/sensor_scene.rviz` | 原生RViz内置显示器、相机交互、包含IR的本窗口截图 |
| `simulation/gazebo_scene_gui.cpp` | 原生Gazebo相机截图按钮与自动留图 |
| `ros_ws/sensor_scene_run.py` | 独占ROS/Gazebo、lockstep、构建/启动/停止、模式专用Mesa与Qt环境；不改原Conda/终端设置 |
| `tests/test_sensor_scene.py`、`tests/check_sensor_scene_ros.py`、`tests/check_sensor_scene_figures.py` | 契约、实际几何/热强度/场景扰动及自身渲染像素验收 |

新入口复用既有placeholder→latest Local Map；地图不能读取场景真值或原始传感器。
RViz自己使用标准显示器查看传感器，application仍只消费公开地图。不新增公共消息/字段。
无LiDAR、target、observed_mask在线输入或训练话题；未运行研究后端、训练或正式PERF-01。

## 命令与通过证据

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sensor_scene_run.py --check
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/local_map_query_run.py --mode inference --port 11715
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

最终场景会话：[manifest](../.runtime/runs/sensor-scene-20261028T164504408022/manifest.json)、
[场景数据验收](../.runtime/runs/sensor-scene-20261028T164504408022/scene-validation.json)、
[传感器配对审计](../.runtime/runs/sensor-scene-20261028T164504408022/sensor-audit.json)、
[像素检查](../.runtime/runs/sensor-scene-20261028T164504408022/figures/pixel-validation.json)、
[清理](../.runtime/runs/sensor-scene-20261028T164504408022/cleanup-audit.json)。

- 单帧1790个有效Radar回波，按安装和body位姿变到odom，距已知几何表面P99为7.63e-7m；
  仅验证理想碰撞采样/坐标，不是物理测距精度。静态Doppler为0。
- IR强度范围0.0784–0.9020；冷柱/暖柱/热箱投影ROI分别约0.149/0.600/0.902，顺序与配置一致。
- 热箱y方向移动1.5m后，14779个IR像素和408个Radar点变化，随后恢复原位；确认两者随同一场景变化。
- Radar→odom平移`[0.8,0,2]m`，非默认各坐标相同。Bundle保留具名calibration与ground_truth。
- 初始地图594个观测cell，全为占位occupied，来源fixture；未生成free。
- 最终短会话收到1350条状态、68帧Radar、134帧IR，发布67个Bundle、1个启动配对超时拒绝，
  无适配异常。配置请求10Hz；lockstep下本机该短窗Radar约5Hz、IR约10Hz，不声明实现10Hz Radar或实时性能达标。
- 实际Gazebo及RViz/IR自身渲染像素检查通过；GUI与所有本会话子进程退出0，无强制清理，端口释放。
- [旧placeholder/inference入口](../.runtime/runs/local-map-query-inference-20261028T164345946938/manifest.json)
  实际ROS、地图查询、无训练监督图与清理通过。
- 新增11项，全仓649/649通过（22.766s），见[轻量回归日志](../.runtime/sensor-scene-lightweight-final-20261028.log)。
  单一动态TF所有者的既有测试保持原样通过。

## 失败保留与修复

1. 前三次构建发现系统Gazebo pkg-config遗漏Ogre Paging/Terrain头路径，以及局部变量与Qt signals宏冲突；
   仅修正本任务构建参数和变量，未安装包。日志保留于`162333`、`162503`、`162530`会话。
2. [162641场景](../.runtime/runs/sensor-scene-20261028T162641512516/scene-validation.json)的IR物体为全白，
   因unlit材质不能得到设定灰度；改用零ambient/diffuse、发射强度材质通道后ROI检查通过。
3. RViz直接quit导致VisualizationFrame析构时隐藏dock，visibility回调访问失效部件；
   [父进程gdb调用栈](../.runtime/runs/sensor-scene-20261028T163245995358/rviz-window.log)定位该退出路径。
   改为事件循环内先关闭frame，配置显式关闭退出保存提示；最终无调试器运行正常退出。
   gdb旧run返回成功只表示调试器退出，不作为GUI正常退出证据；原日志保留。
4. [163912失败场景](../.runtime/runs/sensor-scene-20261028T163912016982/manifest.json)有raw流却无Bundle，
   异步相机与Ray采样相位不稳定；采用Gazebo自身lockstep后不放宽5ms/10ms/40ms契约。
   同时全仓测试发现新节点重复拥有TF职责，保留[首次RED日志](../.runtime/sensor-scene-lightweight-20261028.log)，
   改为复用既有state_adapter，不修改或绕过旧唯一所有者测试。

## 已有、实现、验证及未验证

已有：标准消息/编解码、状态/时钟门控、placeholder、Local Map、公开地图视图和原生RViz。
本轮实现：同源Gazebo场景驱动的Radar/IR、独立truth模式、双窗口查看/截图及自动验收入口。
已验证：固定飞机场景中的测量/安装/热对比、物体位移联动、公开闭环、坏时序拒绝、旧ROS、649项回归与清理。
未验证：PX4/JSBSim与Gazebo联动飞行、动态目标速度/RF、真实测温/标定/设备、研究模型或融合质量、
长时稳定性、机载GPU/功耗和正式PERF-01。研究模式继续不可用；模型质量按用户要求暂不研究。

可提交报告的[图片及中文图注](report_assets/sensor-scene-20261028/README.md)已保存；
[使用说明](../docs/SENSOR_SCENE_VISUALIZATION.md)提供交互入口和恢复方式。
不自动发布报告、提交或推送，不关闭原阶段真实输入/质量/性能门槛。
