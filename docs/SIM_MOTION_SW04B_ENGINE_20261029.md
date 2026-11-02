# 多场景运动装配与真实机制门

日期：2026-10-29；版本：v0.1；任务：SIM-MOTION-SW-04B；主责任：simulation_engineer。
状态：已完成（显式装配/真实空域、切换、故障定向机制范围）。
依据：[多场景设计及修订](SIM_MOTION_SW04_MULTISCENE_DESIGN_20261029.md)、
[SW-04A冻结合同](SIM_MOTION_SW04A_CONTRACT_20261029.md)、ADR-043。
完整9核心/3兼容、S05/S07原生窗口及正式阶段验收尚未完成。

## 1. 已有代码与本轮文件

复用同一FGFDMExec宿主、SceneRegistration/SceneTransactions、受控Ray/Camera与真实ACK，
以及SceneStream→placeholder→M1、公开查询/独立占据回放。研究后端、公共消息字段、
旧固定profile/地图算法/静态world生成器及原默认启动语义保持。

| 本轮文件 | 改动与消费者 |
| --- | --- |
| [multiscene_world.py](../simulation/ufm_simulation/multiscene_world.py) | 显式IC/场景装配；只对新case去默认ground，保留旧generator行为 |
| [gazebo_scene_step.cpp](../simulation/gazebo_scene_step.cpp) | 新增默认不启用的S07几何epoch端点，与SceneStep共用事务锁 |
| [sim_motion_gate_run.py](../ros_ws/sim_motion_gate_run.py) | 仅显式suite_mode选择清单/IC/地图/故障，冻结输入/源码，观察产物预算；旧CLI不接case |
| [新ROS入口](../ros_ws/sim_motion_multiscene_ros_run.py) | 独立命名，避免遮蔽SW-04A离线入口；默认无原生窗口 |
| [MultisceneDelivery](../ros_ws/sim_motion_multiscene_delivery.py) | 场景化空图/旧证据/TTL查询、几何RPC读回与公开执行回放，不实现地图算法 |
| [check_sim_motion_live.py](../tests/check_sim_motion_live.py) | 新显式空点/均匀IR判据；默认仍要求旧场景有回波、IR变化 |
| [sim_motion_multiscene_live.py](../tests/sim_motion_multiscene_live.py) | 独立原始FDM转换、IC/安装/SDF、逐射线最近面/点序、Camera切换核验 |
| [严格几何预期](../tests/fixtures/sim_motion_strict_geometry_expectations.json) | 新run采样前冻结的固定零豁免规则，物理容差保持 |
| [新增测试](../tests/test_sim_motion_multiscene_engine.py) | 11项装配/IC保真、独立射线/坏输出/旋转/CLI测试 |

另新增本说明和中文实验记录，更新状态、架构、接口、计划及实验/决策索引。
生产模块不导入测试oracle；simulation不消费点云/图像生成地图，mapping不读取仿真或raw。

## 2. 显式运行与兼容

从仓根使用固定Conda环境。下列三个命令均已实际运行；每次新run、新Master/rootfs及空地图：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_motion_multiscene_ros_run.py --case S06
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_motion_multiscene_ros_run.py --case S07
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_motion_multiscene_ros_run.py --case S08
```

IC只改设计枚举的phi/theta/psi及原有8m/5m/s字段，其他原IC/单位保持。
新CLI不接受fault/fault-step覆盖；S08只能按清单在第125步忽略真实Radar ACK。
仍是4ms原FDM步、Gazebo四个1ms子步、每25步真实双采样，最长250步/1s。
没有解锁、航点、控制指令、第二时钟/轨迹、改戳或真实DEM/训练监督。

默认端口ROS11801/Gazebo11802及PX4固定端口运行前探测，不并行PX4，不杀已有用户进程。
构建只使用本仓`.runtime/sim-motion-build`与已有`.runtime/ros`类型，不改外层catkin或第三方树。
`--native`仅为S05/S07保留显式捕获入口，本轮未执行/验收这些窗口或其像素，不作为交付证据。

## 3. 暂停几何切换屏障

只有S07加载时注册`/uav/scene/geometry_epoch`，复用标准`gazebo_msgs/SetModelState`类型，
不新增公共msg/srv字段。请求只能是world下唯一obstacle_wall、零twist、单位旋转及
冻结的两个位置；与SceneStep共用serial锁，pending/locked/错误step或非法对象请求拒绝。
仅在已完成step100/225、world暂停、时间精确等于400/900ms时安装。

设置后读回实际model/collision pose、collision box及具名visual的相对pose/box尺寸；
world时间前后相同，尺寸为[1,12,12]m。响应status_message只承载
`scene_geometry_epoch.v1`诊断JSON（run、epoch/step、整数world前后时间、位置/尺寸等），
不携带传感器或地图业务。Python监督另以Gazebo标准服务读回位置/时间后才允许下一FDM步。
读回失败锁定并停止，不以丢点、额外world步或原raw重发替代切换。

实际初始边界请求和两次错误对象请求均被拒绝；400ms移远、900ms移回的collision/visual
及标准model API一致。并发pending拒绝有共享锁源码门禁，本轮没有单独进行并发争用压力测试。

## 4. 核验修正与严格规则

第一次S06末尾核验将非完全正交的原始FDM矩阵与单位四元数矩阵直接按1e-12比较，失败保留。
原矩阵正交残差最大1.7188406253865196e-10，在既有1e-9输入界内；独立极分解后与
实际四元数最大差5.671461564271674e-16。因此测试侧先验证原矩阵界，再以独立SVD极分解
比较单位旋转，仍保持1e-12，不改源矩阵、实际四元数、时间或生产转换器。

第一次S07形状读回把Link::FillMsg误当仅返回障碍visual；实际有父link visual及具名visual。
现严格选择唯一`obstacle_wall::body::visual`并保留全部尺寸/pose检查。
这一用法依据[Gazebo gazebo11 Link源码](https://raw.githubusercontent.com/gazebosim/gazebo/gazebo11/gazebo/physics/Link.cc)，
实际切换收据保存visual_records=2和具名visual身份。

随后S07触发原设计“近边缘总射线≤48”假设，末帧为63，该运行继续保留failed。
后续固定采用`strict_all_rays_no_exemptions_v1`，在新run前冻结：
所有射线包括边缘都必须名义命中集合/顺序完全一致，角度≤5e-6rad、距离≤0.011m，
零缺项/新增、零豁免，不允许改用遮挡后的远表面。近边缘数量仅诊断；没有提高物理误差容差，
没有跳过这63条点。旧v1清单的48字段保留兼容，当前不启用任何边界豁免。
这是显式的核验方案修订；原失败没有被追溯改判为通过，不声称旧48条假设已获实测支持。

## 5. 实际结果

| 定向实际运行 | 结果 | 证据 |
| --- | --- | --- |
| S06真实空碰撞域 | 250步/251 clock与TF、10对实采/20 ACK；零Radar点、均匀IR、10 valid空占据/快照、13 query、独立回放一致 | [184000466912](../.runtime/runs/sim-motion-sw04b-S06-20261029T184000466912/delivery-validation.json) |
| S07切换/恢复回波 | 250步/10组/16 query；100—400ms有回波，500—900ms五帧零点，1000ms恢复；两次切换时间不推进；旧400ms cell在900ms等TTL占据、+1ns stale | [185439436758](../.runtime/runs/sim-motion-sw04b-S07-20261029T185439436758/multiscene-validation.json) |
| S08中途Radar ACK故障 | 第125步锁定；clock最后496ms，4组下游/最后400ms；5对raw与10 ACK可存在，但500ms不成为Bundle；失败run继续请求被拒绝 | [184953262719](../.runtime/runs/sim-motion-sw04b-S08-20261029T184953262719/validation.json) |
| 旧默认入口 | 原SW-03无suite模式仍13,217回波、10组/14 query、独立回放/清理通过 | [185131644710](../.runtime/runs/sim-motion-sw03-20261029T185131644710/delivery-validation.json) |
| 软件/协议 | 新增11项、运动77/77、全仓896/896；既有77组Scene字节/36公共消息往返通过，25份定义与6份未改旧配置/入口逐值保持 | [185633547365](../.runtime/runs/sim-motion-sw04a-20261029T185633547365/report.json)、[运行/失败汇总](../.runtime/runs/sim-motion-sw04a-20261029T185633547365/engine-handoff.json) |

S07严格逐射线最大距离误差约5.27e-7m，边缘豁免0。资源证据仅为已记录订阅载荷和产物观察值：
各流≤512、每次线格式收据<16MiB、观察产物<256MiB，非网络总开销、RSS、20ms或正式PERF。
各次运行都有自己的冻结源码；它们不是相同最终源码上的完整9例矩阵。
S06在最终visual选择/严格规则元数据补齐前通过，对其关闭的几何分支及零点集合没有行为变化；
正式最终源码矩阵仍由SW-04C执行。

## 6. 未验证与下一步

S02/S03不同航向、S04倾斜、S05遮挡及S09显式旧身份恢复尚未做新真实组合；
完整9核心/3兼容、原生S05/S07 before/empty/after/history像素与全套预算仍属SW-04C。
旧estimated/静态原生及旧IR首采样故障三兼容例本轮未重跑；旧默认无suite回归另有实测。
真实设备/外参/时钟、研究模型质量、DEM融合、机载资源和正式阶段退出均未关闭，research继续fail-closed。
失败保留目录，另建新run恢复；只清理自有进程，没有删除历史、提交或推送。

2026-10-29 C实施勘误：B中极分解比较只在当时已测航向通过，不是所有IC下与SciPy
Markley估计完全等价的证明；S02实际反例已保留。C改为独立标量Markley估计，仍按1e-12比较。
S04实际还发现旧gamma=0覆盖theta=5，现仅生成的非零pitch IC省略gamma；第三方原文件不变。
两项依据与恢复规则见[设计修订](SIM_MOTION_SW04_MULTISCENE_DESIGN_20261029.md)。
后续[SW-04C完整交接](SIM_MOTION_SW04C_DELIVERY_20261029.md)已完成最终同源码9核心/3兼容，
新增7项、84运动定向/903全仓与原生阶段图通过；此处B历史数字/失败仍保持，不以新结果覆盖原记录。
