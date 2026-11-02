# SENS-VIS-01：场景、Radar点云与IR可视化

日期：2026-10-28；主责任：sensor_engineer；状态：已完成（独立功能级场景范围）。
交付：[使用说明](SENSOR_SCENE_VISUALIZATION.md)、[实验记录](../experiments/2026-10-28-sensor-scene-visualization.md)。
依据：用户纠正APP-VIS-01范围，要求三维场景窗口、Radar点云、IR等传感器模拟及地图查看/截图。

现状：原fake Radar为固定点/点表，IR为二维背景和热点，不能称为三维场景传感器。
上一版仅覆盖公开地图工作台，不能作为本任务完成证据。现有PX4/JSBSim为无画面运行，
本机已有Gazebo11/RViz/开发库，没有已接入的场景传感器GUI。

本轮增加独立Gazebo传感器场景模式，不替换PX4/JSBSim，不新增飞控或自主控制：

1. 同一具名场景配置定义几何、材质/合成热强度、传感器位姿、FOV/量程/频率。
2. Gazebo原生窗口显示实际场景；几何碰撞采样生成Radar PointCloud2，保留Doppler方向及任意强度语义。
   这是静态目标、首表面几何近似，无电磁传播/多径/虚警质量声明，不发布或消费LiDAR监督。
3. IR相机通过同一场景的Ogre热强度材质通道渲染，保留投影和遮挡；数值为fixture_intensity，
   不是K、辐射测温或真实热传导。普通场景颜色和IR热强度分别指定，不用背景热点冒充相机。
4. 既有state_adapter显式scene_ground_truth分支保留唯一动态TF职责，sensors场景配对器消费
   其公开AircraftState；使用Gazebo ground_truth姿态、具名world→odom注册、
   Radar/IR安装外参和同一clock生成现有RadarFrame/InfraredFrame/SensorBundle。
   不改现有PX4定位权威或旧入口，不把训练监督字段加入在线数据。
5. 既有placeholder→Local Map消费上述真实场景模拟输出，明确为占位地图，不宣称IR融合或研究模型结果。
6. 标准RViz直接显示PointCloud2、Image、地图Marker和TF；独立传感器诊断不经过application越层读取。
   保留APP-VIS-01工作台，不再以它代替场景与传感器可视化。

公共业务消息字段不变；新增显示/采集使用ROS标准消息。关闭仅停止本次会话，新run重建；
缺依赖/场景/传感器数据时明确失败，不以旧fixture填充。禁止运行同级研究仓库、训练或正式性能。
验证需实际Gazebo+RViz图像/点云、同场景坐标/投影、坏/过期数据拒绝、无LiDAR图、旧入口及轻量回归。
