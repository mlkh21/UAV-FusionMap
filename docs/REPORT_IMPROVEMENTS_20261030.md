# 真实高程、参数化Radar与报告更新交付

日期：2026-10-30；版本：v1；状态：已完成；主责任：integration_engineer。
任务：REPORT-UPDATE-SW-01；依据：用户确认安装高程工具，并按报告问题方案实施。

## 1. 已交付内容

- Rasterio 1.3.11与pyproj 3.5.0及必要Python依赖安装在`.runtime/terrain-tools`，固定Python仍为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，原Conda环境包保持。
- 下载Copernicus GLO-30 Public的四川N30/E103瓦片；独立读取、局部UTM坐标查询及原生RViz连续地表显示完成。
- 新显式演示场景为180×140米地面、30个分散几何代理，飞机外观缩放为原网格的0.35倍。它只改变显示几何，不改变JSBSim动力学模型及传感器外参。
- Radar增加可配置的距离相关检测概率、漏检、距离/角度/Doppler误差及点数预算；默认旧场景不启用。
- 补齐同一JSBSim运行的Gazebo、RViz和原始IR前后对照，更新17页Word/PDF，保留先前版本。

报告与素材入口：[最新报告](../experiments/report_assets/progress-update-20261030/README.md)。
实际记录：[EXP-20261030-017](../experiments/2026-10-30-report-terrain-radar-improvements.md)。

## 2. 工具安装与真实高程

安装清单：[terrain_tools_requirements.txt](../configs/terrain_tools_requirements.txt)。
用户授权后执行的安装方式如下，不写系统Python或原Conda环境：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -m pip install --target .runtime/terrain-tools --only-binary=:all: --no-deps -r configs/terrain_tools_requirements.txt
```

运行入口[terrain_tools_env.sh](../ros_ws/terrain_tools_env.sh)先使用统一sim01环境，再将项目内高程工具加入本次子进程搜索路径。现有certifi、click、NumPy等包继续来自原环境。

数据来源：[Copernicus公开数据说明](https://copernicus-dem-30m.s3.amazonaws.com/readme.html)、
[许可入口](https://spacedata.copernicus.eu/en/web/guest/collections/copernicus-digital-elevation-model/#Licencing)。
实际瓦片：[原始GeoTIFF](../.runtime/terrain-data/copernicus-N30E103/Copernicus_DSM_COG_10_N30_00_E103_00_DEM.tif)，
文件42,734,774字节。产品为DSM，保留植被/建筑等表面信息；源高程为EGM2008，未转换为椭球高。

以103.25°E、30.75°N为中心，裁剪201×201像元，坐标由EPSG:4326转换至EPSG:32648。
局部x/y是UTM东距/北距减去声明原点，不能直接当作Gazebo的odom或严格ENU。
查询采用原像元高度，no-data不补零；显示高度减去1226.328247米，三维x/y/z保持相同米制尺度。
原始导出坐标为`terrain_utm_local`，减去显示高度原点后的RViz坐标单独命名`terrain_display_local`。

```bash
bash ros_ws/terrain_tools_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python ros_ws/real_elevation_prepare.py --source .runtime/terrain-data/copernicus-N30E103/Copernicus_DSM_COG_10_N30_00_E103_00_DEM.tif
```

命令打印新运行目录后，将其传给显示入口；每次重新prepare，避免覆盖已有显示证据：

```bash
bash ros_ws/terrain_tools_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/real_elevation_view.py --input <新运行目录>
```

本轮真实高程不使用`m5_fixture_v1`。mapping的ElevationRaster公开导出`ufm.elevation.preview.v1`元数据及`terrain.npz`，后者只包含east/north/height/valid数组；application只读这些显式静态导出生成显示三角网格，ros_ws发布`/uav/terrain_demo/markers`。不发TF，不连接占据更新或旧地形服务。

## 3. Radar与场景参数

显式入口：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_motion_delivery_run.py --report-scene
```

[report_sensor_scene.yaml](../configs/report_sensor_scene.yaml)由真实场景生成器、Radar插件和原有传感器适配消费。
沿原1秒/250步、10次成对采样的JSBSim→Gazebo→Radar/IR→SensorBundle→placeholder→M1→查询/回放链路运行。

| 参数 | 本次值及语义 |
| --- | --- |
| 检测概率 | `0.24 / (1 + (range / 45m)^2)`，在几何遮挡判定之后独立漏检 |
| 测量误差 | 距离σ=0.08m，方位/俯仰各σ=0.003rad，Doppler σ=0.05m/s |
| 点数预算 | 每帧最多256点；超过预算后随机无放回保留 |
| 随机种子 | 20261030与原采样时间共同初始化，保持帧间变化和同运行轨迹复现 |
| 原始强度 | 继续使用`1/(1+range²)`任意强度，不声明为物理RCS/功率 |
| RViz | 原始点云与地图图层分开查看，IR固定0～1灰度范围 |

这些是显式工程参数，不是实物设备标定值。该模式未引入RadaRays、GPU依赖或新的飞行控制命令。
旧入口继续读取原`sensor_scene.yaml`，未启用测量模型时仍输出原几何回波。
新演示构建位于`.runtime/ros/report-motion-build`与`.runtime/ros/report-native-build`。

## 4. 验证与后续

真实高程40,401有效样本、49个原文件独立查询对照；零/负高、no-data、坐标、窗口上界和异常输入有定向测试。
实际改进场景完成10组Bundle/占据/地图快照及14查询，公开记录回放一致，原生图像与清理通过。
两次实际改进运行的10份Radar和10份IR原始消息字节一致；旧默认运动入口实际通过严格几何Doppler/IR与地图查询回放。
新增7项及全仓1090项轻量回归通过，结果见实际记录。

真实地形接入的下一步是独立真实数据profile、服务接口及地形与场景的空间注册；占据融合随后另行验证。
原飞行主线下一项仍按SW-03A公共v2离线合同推进，再做长窗采样与执行器因果验证；本轮不扩展飞行控制范围。

恢复方式：直接使用旧运行命令，不加`--report-scene`；高程工具仅由新环境入口加载，旧业务节点不依赖它们。
