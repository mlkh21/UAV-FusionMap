# 坐标系统与变换规范

版本：v0.1；更新日期：2026-10-14；责任角色：system_architect / sensor_engineer。
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
| terrain_utm_local | 真实高程独立预览；x/y为UTM东距/北距减声明原点，z保留源高程基准 | 2026-10-30四川样例为EPSG:32648、EGM2008高度；不是odom或严格ENU，不发布TF |
| terrain_display_local | 独立静态地表显示；x/y同上述UTM偏移，z=源高程−显式display_height_origin_m | 仅RViz预览坐标，不用于定位或占据；原始高程查询仍返回EGM2008高度 |
| imu | IMU数据坐标，系统约定前左上 | 比力/加速度语义与安装外参单独声明 |
| model_lidar | 保留已有模型训练时LiDAR参考系的逻辑名称 | 仅研究适配使用；不意味着无人机新增LiDAR硬件 |
| training_lidar | fake/离线LiDAR监督扫描坐标 | 仅训练数据生成；不得成为在线TF、定位、SensorBundle或地图输入 |

可选仿真IMU的`sim_pilot_virtual_flu_v1`只将已声明为虚拟pilot点
`body_frd`的比力和角速率矢量分别乘`diag(1,-1,-1)`，输出`imu`的前左上
分量；保留采样时刻，未声明`base_link`/真实IMU安装原点相等，不发布
`base_link -> imu`静态TF或安装平移。源坐标或比力语义与此配置不符时拒绝
发布，真实外参`T_body_imu`仍待标定，不能复用此虚拟适配。

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
  SENS-TRAIN-01 schema `0.2`对非零扫描先将每条射线按采集时刻转换到odom，再用
  `T_odom_training_lidar(t_scan_mid)`逆变换到扫描中点的`training_lidar`坐标；记录同时
  保留原始点、逐点时间和插值状态sample_id。该补偿仅属于训练fixture；2026-10-13
  已接入训练ROS JSON记录路径，非在线TF或实机标定，见
  [验证记录](../experiments/2026-10-13-sens-train-motion-ros.md)。
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

T-14当前由同一个`state_adapter_node`按开关可选发布`nav_msgs/Odometry`兼容镜像和
动态`odom -> base_link` TF。两者直接使用同一条AircraftState的采样时间、位置和姿态，
不新增定位来源；默认配置关闭，mapping仍不得以Odometry替代AircraftState或观测时刻
SpatialContext。该软件fixture验证不等于实机外参或定位质量验收。

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
2026-10-14可选基础实现按观测`SpatialContext.T_mapping_body`在odom中的位置
和初始锚点整格平移，体素轴始终与odom对齐；观测网格原点必须落在同一整格
格点，其index通过观测原点对应的物理坐标换算到当前窗口。偏航只影响上游
Radar点的观测时刻坐标投影，不让地图随航向旋转。失效变换或断流不移动窗口；
odom若发生定位跳变/重置必须终止当前run并用新实例和run_id重建，不能将
不同连续性域的原点当成同一个地图。实现及边界见
[EXP-20261014-011](../experiments/2026-10-14-local-map-rolling.md)。
Scene Map使用map时，定位跳变要触发明确的重新注册、子地图切换或重建策略，不能
继续把新旧姿态当成同一连续参考系。具体策略在对应阶段验收。

2026-10-27的[M4具体方案](M4_SOFTWARE_TRIAL_PLAN_20261027.md)仅提出固定合成注册子集：
显式T_map_odom将odom局部网格转为map中的固定Scene格点，不直接改frame_id；
变换绑定run/clock、来源和有效时段，非零平移算例已核对，旋转/非整格或动态修正拒绝。
DESIGN-01时这尚未成为运行能力。现有SpatialContext没有独立reset/epoch或map←odom关系字段，
首版计划沿用显式new run重建、禁止跨run子地图继承；同run未声明跳变不能可靠识别，
真实定位连续性、动态注册/重注册及位姿误差传播仍须另验，不能从软件fixture推导。

2026-10-28 SW-01已实现上述注册与输入checker：严格声明同轴同分辨率、非零整格平移、
绑定run/clock及有效时段；完整活动窗口不得超出固定Scene envelope，不按点中心重采样。
非valid输入不读取不可用body占位变换。半格窗口边界及相邻float64、注册左闭右开边界
已定向检查，独立算例仍为odom点[8.25,0.25,0.25]→map点[40.25,0.25,0.25]→[80,32,8]。
这是合同/输入预期证据，未运行Scene Map或动态坐标注册，见
[EXP-20261028-001](../experiments/2026-10-28-m4-fixture-contract.md)。

SW-02显式Scene候选已在固定合成注册下执行格点重索引：先从局部origin与T_map_odom
平移计算整格offset，再将每个局部index转换为Scene index，不旋转地图轴或重采样概率。
查询只接受frame_id=map，不能把odom点直接传给Scene服务；来源/域/有效期错配无cell载荷。
固定注册、历史封存与返回算例对保存预期通过，见
[EXP-20261028-002](../experiments/2026-10-28-m4-scene-candidate.md)。该轮尚无M4 ROS证据。
SW-04随后在实际ROS中核对同一非零注册：map点[40.25,0.25,0.25]查询index=[80,32,8]，
odom同数值未被隐式转换，错frame请求unavailable；封存/返回/淘汰和公开回放一致，见
[EXP-20261028-004](../experiments/2026-10-28-m4-ros-handoff.md)。真实注册/定位跳变仍未验收。

## 7. 时间和不确定性

变换使用观测参考时刻，扫描点可带相对偏移。必须记录插值、外推与补偿状态。
禁止用处理结束时的最新位姿变换过去采集的点。

位姿协方差按[x,y,z,rx,ry,rz]排列，位置m、角度rad，各元素单位由两个维度的单位
相乘确定。改变参考系时按相应Jacobian转换；无协方差标不可用，不能默认为零。
标定误差、状态误差和模型不确定性分别登记，不能混为单个没有单位的精度声明。

DEM必须同时说明水平参考系和垂直高程基准。椭球高、海拔和局部高度不能直接混用；
TerrainPrior注册在Phase 4的DEM任务中单独验证。

2026-10-28[M5设计](M5_TERRAIN_PRIOR_DESIGN_20261028.md)进一步区分源像素中心/角点、
CRS轴序/单位、垂直模型、地理锚点→局部ENU→map完整注册与M4的fixture平移。
缺少基准/必须网格或注册到期时地形不可用，不以零校正或单位阵替代；
当前仅核对合成同轴算例，不实现真实重投影或以h-h0近似代替大范围ENU转换。

后续M5-SW-01私有输入校验要求源fixture:terrain_xy_v1/terrain_height_zero_v1与目标
fixture:map_xy_v1/map_height_zero_v1分别声明，T_map_terrain只允许具名非零平移；
源/目标同分辨率整格对齐，请求只能使用目标map样本中心，不能自动插值或把odom点改名map。
独立样例[101,199,height=10]经平移[10,-20,3]的目标预期为[111,179,height=13]，
本轮只校验输入/独立算例，尚未执行地形候选转换，见[合同](M5_SW01_CONTRACT_20261028.md)。

SW-02随后已在独立地形候选执行上述固定fixture中心/平移与高程界转换，4个保存样本一致，
不放宽同轴同格距/整格注册/直接中心采样。区间按源绝对高程界加注册tz界，输出float64时
必要向外舍入以保留包含关系；缺失质量保持unavailable，不推导真实误差或概率质量。
证据见[SW-02记录](../experiments/2026-10-28-m5-terrain-candidate.md)，真实地理转换仍未实施。

## 8. 必要验证样例

- 单位变换：只在明确声明同一参考系的fixture中，点位置保持不变。
- 方向样例：源原点经T_target_source得到目标中的平移，逆变换恢复原点。
- 90度绕z旋转：验证x正向映射到y正向，检查四元数顺序。
- NED样例：[1,2,3]映射为ENU[2,1,-3]；FRD[1,2,3]映射为FLU[1,-2,-3]。
- 网格样例：origin为零、旋转为单位、resolution=[1,1,1]时，索引[0,0,0]中心为[0.5,0.5,0.5]。
- 时间样例：运动状态下两次采集同一静态障碍，经各自观测时刻变换后应重合到允许误差内。

上述为后续测试要求，不表示已经完成实际传感器标定或动态变换验证。

2026-10-10最小训练fixture已按具名仿真安装参数验证：
`T_odom_training_lidar(t)=T_odom_body(t)*T_body_training_lidar`，
同理组合`T_body_radar`、`T_body_thermal_optical`；参数为子坐标中的齐次列点映到父
坐标、行优先16数、平移单位m。odom采用ENU、body采用FLU、热相机采用optical
轴定义；Radar和training_lidar有不同的具名平移。单障碍两时刻运动投影、
相机像素及LiDAR首命中在odom中对齐的证据见
[EXP-20261010-001](../experiments/2026-10-10-sens-train-01-fixture.md)。
这不提供实机标定或在线training_lidar TF发布权。

2026-10-27 M2-SW-03离线合成滚动候选：占据已显式位于odom，
`T_mapping_source`必须声明单位阵；`T_mapping_body`是同一观测时刻body到odom的
有效刚体变换，用其平移确定窗口中心。body偏航不旋转odom轴向网格。
观测origin须与配置anchor按各轴resolution整格对齐；重叠cell按世界位置迁移，
cell概率、累计值和原证据时间同步保留，移出同步淘汰。不推导Radar/Camera/Body相同。
已验证正负平移、偏航、三轴半格边界及不等距分辨率，证据为
[合成软件记录](../experiments/2026-10-27-m2-rolling-time.md)，不是实物外参或动态传感器标定验收。

M3-SW-03沿用上述观测时刻odom格点滚动规则，显式RollingIntervalProbabilityMap只复用
同模块滚动准备步骤。标量概率区间/缺失状态随cell一起迁移和淘汰，不按空间协方差旋转；
偏航不旋转网格轴，不等距分辨率和多轴半格移动已有离线合成检查。
证据见[EXP-20261027-014](../experiments/2026-10-27-m3-rolling-time.md)，不表示真实标定或位姿误差传播通过。

2026-10-28 SENS-VIS-01独立Gazebo场景显式使用
`gazebo_scene_world_enu_identity_v1`：scene_world→odom为同原点ENU注册，body为FLU。
`gazebo_sensor_scene_mount_v1`定义body←radar平移`[0.8,0,0]m`、单位旋转；
body←thermal_optical为同平移及xyzw四元数`[-0.5,0.5,-0.5,0.5]`。
观测时刻`T_odom_radar=T_odom_body*T_body_radar`；body位于`[0,0,2]m`时Radar原点为`[0.8,0,2]m`。
场景真值保持ground_truth，经既有state_adapter发布唯一动态TF；不注册到PX4场景或充当实机标定。
几何表面与热相机投影验收见[场景记录](../experiments/2026-10-28-sensor-scene-visualization.md)。

2026-10-29 SIM-MOTION-SW-01仅冻结[场景运动合同与独立算例](SIM_MOTION_SW01_CONTRACT_20261029.md)。
拟议真值原点为JSBSim质心虚拟FLU（jsbsim_cg_virtual_flu_v1），不等于pilot IMU或真实机体原点；
ECEF feet经初始大地纬度/经度固定ENU注册到scene_world，位置×0.3048，FRD速度/角速度显式转FLU。
注册方向和完整公式以[联动设计第4节](SIM_SCENE_MOTION_DESIGN_20261029.md#4-坐标机体原点与独立预期)为准。
本轮只检查输入矩阵/时间、六组独立reference及消息承载，没有实现或运行FDM坐标转换器，
没有新增TF、定位源或地形/Gazebo地理注册。

后续[SW-02](SIM_MOTION_SW02_ENGINE_20261029.md)已实现并实测上述转换，读取同一FGFDMExec的
GetLocation/Tb2ec/UVW/PQR，初始GetGeodLatitudeRad与经度固定注册，原始double时间单独保留。
scene_world→odom仍为显式同轴同原点真值注册；质心FLU不等于PX4估计原点或pilot IMU。
实际回读/TF和13,217回波Doppler杆臂核验通过；此局部fixture不是地理DEM或实机标定。

后续[SW-03](SIM_MOTION_SW03_DELIVERY_20261029.md)实际核对10帧Bundle的同tick pose/IR，
用实际四元数和0.8m杆臂独立重算13,217回波的odom位置/栅格，匹配占据和公开地图。
新模式等待精确pose，不能用合法但早4ms的旧pose替代已采样的目标几何；旧默认历史pose门槛保持。

后续[SW-04B](SIM_MOTION_SW04B_ENGINE_20261029.md)以真实原始FDM独立重算逐step位置/旋转/单位。
原始矩阵仍按既有1e-9正交/行列式界校验。B使用极分解在已测航向通过，C的S02暴露
极分解与实际SciPy 1.10.1 Markley估计并不完全相同；现由独立标量公式重算后者，
与实际单位四元数矩阵保持1e-12比较，不改写源值或放宽原界，见[具体修订](SIM_MOTION_SW04_MULTISCENE_DESIGN_20261029.md)。
S04生成IC只省略会覆盖theta的gamma=0；实际原始初始姿态必须满足冻结的[10,5,90]度。
切换只改变world/odom同轴注册下具名静态障碍物的world位置；飞机/FDM/地图网格和TF权威不变。

[SIM-FLIGHT设计审查](SIM_FLIGHT_DESIGN_20261029.md)确认JSBSim 1.1.13 v1 IC的altitude为AGL，
elevation另表示地面基准；旧8m运动高度不能叫8m MSL。新ground profile拟AGL=.5m、
独立ENU锚点[0,0,.5]及jsbsim_cg_to_flight_enu_v1，实际AGL/ASL/大地坐标分别读回。
这些新字段/注册尚未实现，旧8m注册和坐标转换保持；固定地面fixture不是DEM地理融合。
2026-10-30 [SW-01](SIM_FLIGHT_SW01_CONTRACT_20261030.md)已将上述AGL=.5m、elevation=419.2m、
Euler=[0,0,90]度、gamma=null和新锚点冻结为私有离线合同；尚未生成/安装IC或发布新注册TF。
2/5/7/4执行器通道及−1/−1/−1/+1符号以独立float32探针核对，不作空间外参或地理高程转换。
后续SW-02的ground真值仅作私有诊断，不能绕过旧v1的z>.5门禁或覆盖旧8m坐标注册。
随后[SW-02](SIM_FLIGHT_SW02_DIAGNOSTICS_20261030.md#4-高度读回的修正)已实际安装私有IC并分别读回AGL/地面/
大地高/ASL/ECEF/椭球轴/姿态。JSBSim径向ASL约419.702351m，大地高约419.700001m，
不强行认为前者等于419.2+.5；以椭球射线半径独立计算核对，原1微米数值界不变。
仍无新TF、公共注册或DEM融合，诊断坐标不能冒充在线定位。
后续[只读补证设计](SIM_FLIGHT_DIAG_DESIGN_20261030.md)区分wire瞬时IMU、PX4积分IMU及EKF低通状态，
三者不能互相替代；本轮只复核保存输入，未由瞬时模长推导tilt_align或实际姿态有效。
拟议快照保留原始微秒/实例与查询墙钟，不改成检查点时间；无新增坐标注册/状态或TF发布者。
随后[SW-02B](SIM_FLIGHT_SW02B_PROBE_20261030.md)已保留实际step125/FDM约.5s、lastHIL496000us，
三组IMU原timestamp/sample492000us与4000us积分周期；不将其对齐改戳为500000us。
打印delta_angle/velocity仅有四位小数，不代表原始float32位模式、EKF低通或姿态有效；
后续空状态输出被拒绝，未生成新的定位/TF/控制数据，仍不具原子同tick或因果绑定。
随后[三态补证设计](SIM_FLIGHT_DIAG_DESIGN03_20261030.md)要求新事件保留每块原生时间，
空块fields=null，不制造时间0或复制其他实例戳；无显式单实例编号不推断primary。
采集完整或载荷完整均不自动给出fresh/当前HIL绑定；本轮只设计，无新状态/TF/坐标注册。
随后[SW-02C实际诊断](SIM_FLIGHT_SW02C_DIAGNOSTICS_20261030.md)已严格保留10条事件的实例/原戳，
125步模式样本timestamp24000us不能改成检查点时间或外推新鲜；单标题编号保持null。
250步第11次原文含nan而未生成合法状态事件；没有新增TF/在线定位或当前周期执行器绑定。
随后[质量隔离设计](SIM_FLIGHT_DIAG_DESIGN04_20261030.md)只拟使用同实例同载荷control_mode_flags核对字段条件，
不借另一次flags查询/历史或其他实例补齐；原时间/编号/文本保留，空正文不产生新时间。
质量字段隔离不证明姿态有效、primary关联或fresh/当前周期绑定；本轮无新定位/TF/坐标注册。
随后[SW-02D实际21查询](SIM_FLIGHT_SW02D_QUALITY_20261030.md#4-实际证据与剩余缺口)保持每块原戳与实例：
250组status的timestamp/sample=988000/908000us；flags实例0/1为964000/884000us，2..5为828000/748000us。
IMU为992000us，模式样本528000us，均未改戳为检查点或宣称原子同tick。
六flags样本tilt/yaw未对齐及selected姿态无载荷是直接观察，不推断primary或唯一初始化根因。
本包无新定位/TF/注册/在线状态，执行器绑定仍unverified；下一设计不由较旧模式样本外推整段disarmed或fresh。
随后[INIT-DESIGN-01](SIM_FLIGHT_INIT_DESIGN_20261030.md#4-拟议准备profile与停止边界)明确GetVel为局部NED ft/s、
GetPQR为body FRD rad/s、Euler为NED/FRD姿态；AGL为CG对地距离，不等于支柱离地。
拟记录源前/后及各自单位/时间，WOW不填成PX4 landed/at_rest；本轮无新坐标注册/TF或定位来源。
随后[INIT-SW-01](SIM_FLIGHT_INIT_SW01_CONTRACT_20261030.md#3-精确合同)已将源前后kinematics/ground、原HIL输入与
NED/FRD/英制单位写入私有离线合同；米制速度/比力及支柱力按固定因子核对，AGL/ASL不混用。
检查点FDM后10s对应last HIL9996000us；原戳不重写，逐实例未来/倒退拒绝、慢快topic年龄分别评价。
这些仅合成字节/连续性证据，实际地面静稳/姿态、地理初值与真实接触仍留下一运行包，不新增定位/TF。
随后[INIT-SW-02](SIM_FLIGHT_INIT_SW02_PREPARATION_20261030.md#4-实际结果与独立证据)实际逐步核对源前后NED/FRD/
英制换算和三支柱接触；500步/2s时CG AGL≈.310829m、pitch≈8.422156°，并非维持初始水平/.5m。
首零包step423的HIL1688000us/actuator1684000us，78包差均−4000us，保持原戳不改为当前周期。
局部静稳和零输出不证明selected姿态或严格因果绑定；无新TF/注册/定位来源，完整准备仍未通过。
随后[selector设计](SIM_FLIGHT_INIT_SELECTOR_DESIGN_20261030.md#5-98项查询与关联就绪判定)区分estimator实例、IMU槽和设备ID，
两类主IMU槽可不同；各topic原uint64时间独立保留，顺序观测不构造原子tick或推算消费时间。
无新坐标/TF/地理注册；本轮仅方案，原−4000us执行器时差与未验证绑定保持。
随后[selector SW-01](SIM_FLIGHT_INIT_SELECTOR_SW01_CONTRACT_20261030.md)已将三种索引和独立topic整数原时间写入私有离线校验，
合成关联保留各自产生时间、消费时间null/同消息验证false；原物理单位/时间/1ns界不改。
无新定位/TF/地理注册或实际运行，既有执行器时间差和完整准备未通过状态保持。
随后[selector SW-02](SIM_FLIGHT_INIT_SELECTOR_SW02_PREPARATION_20261030.md#5-新失败的源码与数值证据)实际主实例4对应gyro/accel槽1，
两类原生时间保留，582执行器差仍−4000us；double4.028s截断发4027999us而网格应4028000，Run前拒绝。
源double仍满足原1ns网格界，不因此接纳错整数戳；无新坐标/TF，完整准备与严格绑定未通过。
随后[INIT-TIME-SW-01](SIM_FLIGHT_INIT_TIME_SW01_DELIVERY_20261030.md)已通过隔离发送前修复完成10s准备，原double源时刻和坐标/单位不改，
发送整数由校验的source_step×4000产生；2509条源收据逐包核对，原失败wire不修正。
末姿态sample7992000→9992000us、主实例5/IMU槽2，执行器仍早4000us，不能由准备通过推严格绑定/新定位或TF注册。
