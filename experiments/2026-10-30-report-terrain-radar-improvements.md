# 真实高程、Radar参数化与报告更新实验

编号：EXP-20261030-017；日期：2026-10-30；主责任：integration_engineer。
状态：已完成；任务：REPORT-UPDATE-SW-01。

## 1. 目的与授权

用户指出原报告图3仅含离散合成样本、图6缺少RViz观测变化、场景拥挤及飞机过大、Radar回波过密过规则，
并明确授权安装高程工具和实施此前提出的演示与报告改进。任务包括真实高程独立读取/查询/显示、
新显式参数化场景、实际运行截图与Word/PDF更新；主线飞行合同及控制任务继续独立推进。

## 2. 环境与数据

分支`feature/engineering-initialization`，保留全部既有修改与未跟踪文件，未自动提交或推送。
运行前核对固定Python`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，版本3.8.12。
安装Rasterio 1.3.11、pyproj 3.5.0、affine 2.4.0、attrs 24.2.0、cligj 0.7.2、click-plugins 1.1.1至
`.runtime/terrain-tools`；Rasterio自带GDAL为3.9.2。原Conda包不变，无GPU或大型仿真依赖。
[安装收据](../.runtime/terrain-tools-installed-20261030.json)、[固定依赖](../configs/terrain_tools_requirements.txt)。

下载[Copernicus N30/E103原始瓦片](../.runtime/terrain-data/copernicus-N30E103/Copernicus_DSM_COG_10_N30_00_E103_00_DEM.tif)，
42,734,774字节，3600×3600、单波段、EPSG:4326。来源及许可入口保存在
[官方readme](../.runtime/terrain-data/copernicus-N30E103/readme.html)，报告保留产品名称与地理位置。
本次区域中心103.25°E/30.75°N，源窗口[col800,row800,width201,height201]，共40,401个有效高度，
1226.328247～2741.102295米，EGM2008。产品明确为DSM，未转换为DTM或WGS84椭球高。

## 3. 实施与真实链路

| 文件 | 本次作用 |
| --- | --- |
| `mapping/ufm_mapping/elevation_raster.py` | 有界原始高程读取、声明产品/基准、UTM坐标和原像元查询 |
| `application/ufm_application/elevation_visualization.py` | 消费显式静态导出生成三角表面，保留无数据空洞 |
| `ros_ws/terrain_tools_env.sh` | 在统一环境内显式加载项目隔离高程依赖 |
| `ros_ws/real_elevation_prepare.py`、`real_elevation_view.py` | 裁剪、独立查询对照、静态导出、原生ROS/RViz与报告图生成 |
| `configs/terrain_tools_requirements.txt`、`report_sensor_scene.yaml` | 工具版本与显式新场景/测量参数 |
| `sensors/radar_measurement_model.h`、`gazebo_scene_radar.cpp` | 几何可见性之后的检测、漏检、测量噪声、随机预算 |
| `sensors/ufm_sensors/scene_stream.py` | 新测量参数有界验证，原同步与业务合同保持 |
| `simulation/ufm_simulation/sensor_scene.py` | 可选场地、相机、外观尺度及测量参数装配 |
| `ros_ws/sim_motion_gate_run.py`、`sim_motion_delivery.py` | 显式`--report-scene`、新测量检查与原生显示配置 |
| `ros_ws/sim_motion_build.py`、`sensor_scene_run.py` | 可选隔离构建目录与新头文件构建依赖 |
| `tests/report_motion_checks.py`、`report_radar_probe.cpp`、`test_report_improvements.py` | 实际wire独立检查、实际C++模型与高程行为测试 |
| `tests/terrain_rviz_capture.py` | 可选独立显示配置，默认保持 |
| `tests/test_sim_motion_multiscene_engine.py` | 为既有无构造器显示测试补齐实际profile，旧断言不变 |
| `experiments/report_assets/progress-update-20261030/prepare_figures.py` | 保留原生图与原始IR，明确排版对照来源 |
| `experiments/report_assets/progress-20261030/render_report.py` | 支持新输出目录、长对照图和图3b图注 |

图形链仍是JSBSim→原场景推进协议→Gazebo Ray/Camera→原SensorBundle→placeholder→M1→查询/回放；
默认旧profile、公共消息字段、唯一clock/state/TF及训练数据边界不变。新报告场景的构建位于
`.runtime/ros/report-motion-build`和`.runtime/ros/report-native-build`。

地形链是原GeoTIFF→mapping读取/查询与`ufm.elevation.preview.v1`显式静态导出→application表面适配→
独立`/uav/terrain_demo/markers`。该导出不是旧M5合成dataset；没有放宽`m5_fixture_v1`或将DSM冒充DTM。
原始查询保持绝对EGM2008高度；仅显示减去区域最低高度，x/y为声明UTM原点偏移，不发布TF。

## 4. 实际结果

| 检查 | 结果与证据 |
| --- | --- |
| 真实高程 | [最终准备/49查询](../.runtime/runs/real-elevation-20261030T181113915286/query-checks.json)逐值等于原GeoTIFF独立像元读取，越界无高度 |
| 原生地形 | [最终显示](../.runtime/runs/real-elevation-20261030T181113915286/view-manifest.json)通过，20,000显示三角形；[清理](../.runtime/runs/real-elevation-20261030T181113915286/view-cleanup.json)正常退出 |
| 改进场景首次 | [174718运行](../.runtime/runs/sim-motion-report-20261030T174718108466/manifest.json)通过，原生前后图与业务链完整 |
| 隔离构建后的报告运行 | [175334运行](../.runtime/runs/sim-motion-report-20261030T175334777829/manifest.json)、[实际检查](../.runtime/runs/sim-motion-report-20261030T175334777829/validation.json)通过：250步/10对/20 ACK |
| Radar与IR | 每帧161/176/205/210/245/256/256/256/256/256点，总2277点；表面残差99分位0.23785m，Doppler误差标准差0.05125m/s；IR前后变化69,136像素 |
| 地图与应用 | [业务检查](../.runtime/runs/sim-motion-report-20261030T175334777829/delivery-validation.json)：10组Bundle/占据/快照、14查询；公开回放与独立进程重放逐值一致 |
| 原生图 | [图像检查](../.runtime/runs/sim-motion-report-20261030T175334777829/figure-validation.json)通过，真实Gazebo/RViz before/after/history；非浏览器界面 |
| 第二次运行复现 | [180206运行](../.runtime/runs/sim-motion-report-20261030T180206164954/manifest.json)通过；与175334运行的10份Radar和10份IR原始消息逐字节一致 |
| 旧默认兼容 | [175827旧运动入口](../.runtime/runs/sim-motion-sw03-20261030T175827472591/manifest.json)实际通过；13,217点严格Doppler/强度和IR检查、地图查询及独立回放保持 |
| 定向与全仓 | 新增7项、旧运动84项、旧场景11项通过；[最终全仓日志](../.runtime/report-improvements-final-regression-20261030.log)1090项通过 |
| 报告 | 17页、9图，Word/PDF文字与源图核对；原参考14页，前版15页，旧Word/PDF及Markdown保留 |

## 5. 修正记录

初次高程准备以极大越界坐标触发投影非有限结果，已在投影前检查区域范围；no-data与非法输入保持区分。
初次地形显示因新环境入口未保留原ROS Python搜索路径而失败，已保留原统一环境并只增加高程路径。
随后一次截图读取在PNG写完前发生，改为等待捕获完成收据；两个失败显示run保留：
`real-elevation-20261030T174432123905`、`real-elevation-20261030T174924578491`。
最初C++探针对不同种子“输出不同”的数量假设忽略了两侧同时漏检，按独立概率事件修正该测试断言；
生产检测参数、误差幅度和实际运行检查门槛未改变。旧显示测试补齐profile后原84项通过，未删除旧断言。

## 6. 后续与边界

真实高程已完成独立读取、查询和原生显示，真实地形服务profile、Gazebo地理注册及占据融合留后续。
新Radar参数是工程级观测模型，无实物校准、材质RCS、多径或虚警质量结论。
飞机0.35倍为视觉代理调整，未改JSBSim质量、惯量和安装外参；本次运动仍为原1秒无控制窗口。
按用户要求未开展研究质量、训练或完整模型推理，未修改同级研究仓，未执行正式PERF。
飞行主线仍接SW-03A离线公共v2，严格执行器因果与受控飞行另验。

交付：[报告与素材](report_assets/progress-update-20261030/README.md)、[使用说明](../docs/REPORT_IMPROVEMENTS_20261030.md)。
