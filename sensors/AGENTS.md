# sensors 模块规范

基线：v0.1；日期：2026-09-16；责任角色：sensor_engineer。
先读[根规范](../AGENTS.md)、[项目状态](../PROJECT_STATUS.md)和[系统架构](../docs/SYSTEM_ARCHITECTURE.md)。

## 1. 模块职责

管理Radar、IR、IMU的功能级模拟或设备接入、标定、同步，以及飞行状态到系统标准
状态的适配。维护当前定位权威职责和观测时刻状态缓存；按功能级、参数化、高真实性
的顺序发展。训练数据生成模式另负责fake LiDAR监督，运行时不把LiDAR作为系统传感器。

## 2. 输入输出定义

输入：仿真场景和状态或真实设备数据、标定参数；驱动可提供PointCloud2/Image等载荷。
输出：RadarFrame、InfraredFrame、ImuSample、AircraftState、SensorBundle及其时空上下文；
训练配置可旁路输出LiDAR监督点云、occupancy target和observed mask。
每个原始观测保留采集时间和坐标；无标定质量估计时明确标为不可用。

## 3. 允许修改范围

经确认修改传感器模拟、驱动适配、数据转换、同步和标定处理及相应测试。
频率、FOV、量程、噪声通过有单位的configs参数提供。
驱动载荷到业务契约的适配负责字段类型/单位、Doppler方向、强度含义和时间语义；
模型特定voxel、归一化、张量布局及IR特征提取不属于本层。

## 4. 禁止修改范围

不得实现占据网络、概率地图或控制器；不得将仿真真值伪装成测量数据。
不得把无回波解释为全空间自由，也不得把任意强度值直接宣称为物理功率。
不得默认Radar、Camera、Body坐标相同或以接收时间替代采集时间。
不得把PointCloud2字段名当作完整物理合同；不得把训练监督LiDAR加入在线SensorBundle、
定位或地图输入，也不得让其派生数据进入Radar+IR模型forward输入。

## 5. 与其他模块接口关系

只向perception提供约定的SensorBundle；时间、标定和状态上下文一并传递。
同步及异常行为以SENSOR_INTERFACE为准；消息包装归ros_ws。
`nav_msgs/Odometry`若后续提供，仅为ROS兼容镜像；AircraftState继续保留run/clock、来源、
状态与失效原因。mapping不得直接订阅最新Odometry，位姿仍随OccupancyObservation传递。

## 6. 测试要求

验证字段单位、轴方向、Doppler正负方向、图像编码、同步残差、丢帧/乱序、扫描时间
跨度、已知场景与外参转换。观测超时不得无限等待，降级行为必须可观测。
训练数据测试还须证明Radar/IR输入与LiDAR监督同步、LiDAR未进入SensorBundle/forward、
未覆盖区域保持unknown，并分别验证training与inference启动图。

## 7. 文档要求

记录参数来源、标定方向/版本/适用范围、时钟来源、模拟等级及已验证的接口。
修改同步或字段语义时更新公共文档和DECISION_LOG，实验记录配置和结果。
