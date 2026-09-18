# 坐标系统与变换规范

版本：v0.1；更新日期：2026-09-16；责任角色：system_architect / sensor_engineer。
状态：坐标约定已定义；SIM-01A NED/FRD状态适配已实现并有确定性测试，
实际传感器安装外参与场景全局注册仍未验证。

## 1. 基本约定

系统使用右手坐标系、m和rad。姿态统一为归一化四元数[x,y,z,w]；源系统若使用
不同顺序或旋转定义，在接入处显式转换。欧拉角只用于展示或注明顺序的配置。

机体前左上、局部ENU和相机光学轴参考ROS
[REP-103](https://raw.githubusercontent.com/ros-infrastructure/rep/master/rep-0103.rst)，
map/odom的连续性语义参考
[REP-105](https://raw.githubusercontent.com/ros-infrastructure/rep/master/rep-0105.rst)。

## 2. 坐标系登记

| 名称 | 方向与用途 | 责任与限制 |
| --- | --- | --- |
| world | 仿真环境坐标；原点和轴向由实际仿真源声明 | simulation记录，不能默认等于map |
| world_ned | 源系统明确采用NED时的北、东、下坐标 | 只在源适配边界使用 |
| map | 场景地图固定参考系，约定局部ENU和明确原点 | 后期注册/定位来源明确后启用，允许定位修正带来跳变 |
| odom | 连续的局部参考系，初始Local Map使用 | 状态适配维护，可能随时间漂移 |
| base_link | Body坐标，x前、y左、z上；固定安装原点 | 安装原点必须记录，不能默认与飞控IMU原点相同 |
| body_frd | 源系统机体前、右、下坐标 | 显式转换到base_link |
| radar | 系统Radar坐标，x前、y左、z上 | 原生传感器若不同，在sensors适配；外参必须测定/配置 |
| thermal_link | 相机安装坐标，按前左上定义 | 通过标定连接到base_link |
| thermal_optical | 图像光学坐标，x右、y下、z前 | camera_info与图像在此坐标解释 |
| imu | IMU数据坐标，系统约定前左上 | 比力/加速度语义与安装外参单独声明 |
| model_lidar | 保留已有模型训练时LiDAR参考系的逻辑名称 | 仅研究适配使用；不意味着无人机新增LiDAR硬件 |
| training_lidar | fake/离线LiDAR监督扫描坐标 | 仅训练数据生成；不得成为在线TF、定位、SensorBundle或地图输入 |

model_lidar与Body的关系必须由适配设计明确并验证；不能直接套用地面数据集标定作为
无人机安装外参。研究数据中名为lidar的frame只有经显式映射才能对应model_lidar。
training_lidar是监督采集坐标，model_lidar是模型逻辑网格坐标；二者即使初期配置相同
也必须分别登记，不能靠名称或单位变换假定等同。

## 3. 变换方向和组合

使用列向量和齐次变换：`p_target = T_target_source(t) × p_source`。
T的左上3×3为旋转，右上3×1为以m表示的平移，末行为[0,0,0,1]。

- Radar到Body：T_body_radar。
- Body到odom：T_odom_body(t)。
- Radar到odom：T_odom_radar(t) = T_odom_body(t) × T_body_radar。
- 模型体素到odom：T_odom_model(t) = T_odom_body(t) × T_body_model。
- 训练监督LiDAR到Body：T_body_training_lidar；只用于训练样本对齐和标签生成。
- 源外参方向相反时必须求逆，不只取负平移。

静态外参登记calibration_id、source_frame、target_frame、有效期及质量；动态变换
登记实际时间和状态来源。禁止省略方向，禁止将不存在的变换填为单位矩阵。

## 4. 参考变换树与发布责任

```text
map --(已声明的注册/定位关系)--> odom --> base_link
                                            ├── radar
                                            ├── thermal_link --> thermal_optical
                                            ├── imu
                                            └── model_lidar（仅需要时）
```

训练数据生成配置可临时增加`base_link -> training_lidar`监督变换，但它不属于在线部署
TF树。inference配置中不得出现training_lidar生产者或消费者。

箭头表示父子坐标关系，不表示业务层调用。每条边只能有一个权威来源。
Body动态状态和map/odom注册由sensors的状态适配对接已有状态源；安装外参由sensors
标定配置提供；ros_ws只负责将这些定义承载为实际变换消息。

world保持为有明确定义的仿真源。world到odom的关系在运行记录中明确声明；只有已
配置并验证同原点同轴时才能使用单位变换。真值关系与估计关系不能同时争夺同一条边。
没有全局注册时，Local Map保持在odom，不伪造map到odom变换。

## 5. NED/FRD接入转换

对于源数据确实采用NED和FRD的情况：

```text
C_enu_ned = [ 0  1  0 ]       C_flu_frd = [ 1  0  0 ]
            [ 1  0  0 ]                   [ 0 -1  0 ]
            [ 0  0 -1 ]                   [ 0  0 -1 ]
```

`p_enu = C_enu_ned × p_ned`，速度也按其所属坐标转换。
若R_ned_frd表示Body FRD到世界NED的旋转，则
`R_enu_flu = C_enu_ned × R_ned_frd × transpose(C_flu_frd)`。
世界轴变换和机体轴变换都要处理，不能只交换position字段。
该式不是对所有PX4/JSBSim接口的原生定义假设；实际接口必须先核实。

## 6. 网格、原点和地图

SIM-01A用户确认的入口配置为odom_origin_policy=px4_estimator_local_origin与
body_origin_policy=source_body_virtual_flu：odom沿用本run估计器局部原点、轴向ENU，
base_link为源body同原点的虚拟FLU；不声明与物理IMU、实机重心或JSBSim场景原点相同。
缺少明确配置拒绝有效适配。源速度属于body_frd，输出v_base=C_flu_frd v_frd，
velocity_frame_id=base_link；不能将世界轴变换直接用于机体速度。
本步只发状态消息，不广播TF、不伪造map→odom。准备期尚未声明连续odom，
ACTIVE后reset必须终止当前run；下次完整重启采用新run_id。

Occupancy与Map中的origin是网格最小角的位姿。索引为XYZ，体素中心为：

`p_frame = origin.position + R_origin × ((index + 0.5) ⊙ resolution)`。

先由索引获得点在header.frame_id中的位置，再使用同一观测时刻的T_mapping_source
转换到地图；不能把网格索引直接当米制坐标。C,Z,X,Y到XYZ的转置必须明确验证。

滚动Local Map可以改变origin/coverage，但header.frame_id仍为odom，revision需更新。
Scene Map使用map时，定位跳变要触发明确的重新注册、子地图切换或重建策略，不能
继续把新旧姿态当成同一连续参考系。具体策略在对应阶段验收。

## 7. 时间和不确定性

变换使用观测参考时刻，扫描点可带相对偏移。必须记录插值、外推与补偿状态。
禁止用处理结束时的最新位姿变换过去采集的点。

位姿协方差按[x,y,z,rx,ry,rz]排列，位置m、角度rad，各元素单位由两个维度的单位
相乘确定。改变参考系时按相应Jacobian转换；无协方差标不可用，不能默认为零。
标定误差、状态误差和模型不确定性分别登记，不能混为单个没有单位的精度声明。

DEM必须同时说明水平参考系和垂直高程基准。椭球高、海拔和局部高度不能直接混用；
TerrainPrior注册在Phase 4的DEM任务中单独验证。

## 8. 必要验证样例

- 单位变换：只在明确声明同一参考系的fixture中，点位置保持不变。
- 方向样例：源原点经T_target_source得到目标中的平移，逆变换恢复原点。
- 90度绕z旋转：验证x正向映射到y正向，检查四元数顺序。
- NED样例：[1,2,3]映射为ENU[2,1,-3]；FRD[1,2,3]映射为FLU[1,-2,-3]。
- 网格样例：origin为零、旋转为单位、resolution=[1,1,1]时，索引[0,0,0]中心为[0.5,0.5,0.5]。
- 时间样例：运动状态下两次采集同一静态障碍，经各自观测时刻变换后应重合到允许误差内。

上述为后续测试要求，不表示已经完成实际传感器标定或动态变换验证。
