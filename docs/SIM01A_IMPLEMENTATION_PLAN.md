# SIM-01A：状态与仿真时钟接入实施提案

日期：2026-09-14；主责任角色：simulation_engineer；统筹：Technical Lead。
状态：用户于2026-09-14确认实施，另指定所有Python默认Conda Radar-Diffusion。
公共细化已纳入v0.1接口；实施结果以实验记录和PROJECT_STATUS为准。
依据：[当前状态](../PROJECT_STATUS.md)、[分层架构](SYSTEM_ARCHITECTURE.md)、
[数据契约](DATA_FORMAT.md)、[坐标规范](COORDINATE_SYSTEM.md)。

## 1. 范围与责任

用户要求调用对应子agents推进下一步。本次由system_architect、simulation_engineer、
sensor_engineer并行只读分析，Technical Lead汇总具体方案、接口细化和验收清单。
不新增算法、研究后端、地图或控制能力；SIM-00B原始遥测成功仍不等于系统接口实现。

| 责任 | 本步交付 | 修改所有权 |
| --- | --- | --- |
| system_architect | 四个ROS消息编码与公共契约对应，评审模块边界 | 接口提案；正式契约由Technical Lead汇总修改 |
| simulation_engineer | 源筛选、解码、时钟、预热门控与运行状态 | simulation/ufm_simulation及其测试 |
| sensor_engineer | 源NED/FRD状态到odom/base_link的适配 | sensors/ufm_sensors及其测试 |
| Technical Lead兼integration_engineer | 独立catkin、薄ROS节点、配置、联调、状态台账 | ros_ws、configs、跨模块验收及管理文档 |

实施时每个文件只有一个修改责任方，子agent不得回退其他人的修改；边界调整先汇总。

## 2. 数据通路与ROS编码

```text
/mavlink/from
  → simulation源筛选/时钟与状态门控
      → /clock（仅基础设施）
      → /uav/sim/state（AircraftState；world_ned / body_frd）
          → sensors坐标适配
              → /uav/sensors/state（AircraftState；odom / base_link）
```

新增/uav/sensors/state仅供sensors内部后续同步及记录；perception仍消费SensorBundle，
mapping仍消费OccupancyObservation。两段状态复用同一消息，不新建RawAircraftState。
两个薄节点各自只调用所属业务库；库不依赖rospy或ROS生成类型，以普通数据对象交换。

拟建立uav_fusionmap_msgs包的四个消息：

| 消息 | 字段与编码 |
| --- | --- |
| ObservationHeader | string schema_version/clock_id/run_id/sample_id/frame_id/reason；int64 timestamp；uint8 source_type/status及具名常量 |
| Uncertainty | uint8 status及常量；string kind/unit/source；float64[] value |
| Quality | bool confidence_available；float32 confidence；Uncertainty uncertainty |
| AircraftState | ObservationHeader header；float64[3] position/linear_velocity；float64[4] orientation_xyzw；string body_frame_id/velocity_frame_id；uint8 state_source及常量；Quality quality |

纳秒只做整数us×1000，不经浮点秒转换。枚举拟固定为source_type的simulation=0、
measured=1、fixture=2、model=3、derived=4；status的valid=0、degraded=1、unavailable=2；
state_source的ground_truth=0、estimated=1；uncertainty的unavailable=0、available=1。
未知枚举必须拒绝；ROS默认值不构成有效数据，空run_id/clock_id/sample_id仍须校验。

本步confidence_available=false；uncertainty.status=unavailable、value=[]，保留不可用
原因与源证据。未来available位姿协方差编码为36元素行优先、维序[x,y,z,rx,ry,rz]，
但当前PX4并未完整提供该矩阵，本步不启用available，不将缺失量补成零方差。

不新增角速度、reset_counter、source_sample_id等必需业务字段；HIGHRES_IMU先作时钟
和原始证据，独立ImuSample及其物理加速度语义留待后续明确。reset_counter属于入口
内部状态并写入原始记录/诊断。输出sample_id使用自身生产者前缀并可确定性关联源ID，
重复输入维持同一身份；映射规则和输入来源写入manifest，不以MAVLink八位seq单独标识。
候选身份规则为sim.odometry:<sysid>:<compid>:<source_us>，适配输出为
sensors.state:<输入sample_id>；唯一性范围由run_id限定。同一身份内容冲突不得作为
新的观测发布，应拒绝并报告；不会因重传生成新身份。

## 3. 源状态与质量

只接受指定sysid=1/compid=1、正确framing及可独立解码的目标消息。
ODOMETRY必须确认LOCAL_NED/BODY_FRD、AUTOPILOT估计来源，保留采样time_usec，
四元数从[w,x,y,z]显式重排为[x,y,z,w]。非有限位姿/速度、无效四元数、错误坐标或
估计类型拒绝并诊断，不让“字段存在”替代有效性检查。

源头姿态旋转定义由PX4 vehicle_odometry.msg声明为body FRD到参考系；源发布者
ODOMETRY.hpp将世界线速度转到body，但速度协方差仍有未完成的旋转TODO。
EKF2.cpp的完整pose covariance初始化为零而仅填写位置对角，姿态传播仍TODO，
因此完整位姿及速度协方差都保持不可用。现代Python解码器读到默认quality=0不能
视为已校准置信度。本步状态可以在几何/时间有效时供适配使用，质量不可用独立保留。

## 4. 坐标与原点提案

候选配置明确：本run的odom沿用源估计局部原点、轴向为ENU；base_link定义为源body
同原点的虚拟FLU框架。这是仿真入口约定，不证明它等于JSBSim世界原点、物理IMU
安装原点或实机重心。缺少这一配置时适配不可用；不伪造map→odom或硬件标定。

采用列向量，C=C_enu_ned，D=C_flu_frd：

```text
C = [0 1 0; 1 0 0; 0 0 -1]
D = [1 0 0; 0 -1 0; 0 0 -1]
p_odom = C p_ned
R_odom_base = C R_ned_frd D^T
v_base = D v_frd
```

输出velocity_frame_id=base_link；不能直接把body速度乘C。时间、run_id和state_source
保持；转换后source_type=derived。角速度不进入本步AircraftState公共接口。
旋转顺序、归一化和q/-q等价需测试；不把错误四元数默认为单位姿态。

## 5. 时钟、等待和重置策略

/clock仅由有效HIGHRES_IMU.time_usec生成，是源采样时钟的离散代理，不能由墙上时间
或SYSTEM_TIME Unix时间推进；没有新有效采样时保持不动。超时检查使用本地单调时钟。
MAVROS保持PASSTHROUGH、publish_sim_time=false，系统/同步时间发送率0。

已有短测出现启动阶段reset_counter变化，且状态可能比最近HIGHRES_IMU先到，不能
立即发布所有ODOMETRY。拟采用PREPARING、ACTIVE、FAULT三个入口状态：

- PREPARING：尚未对外发布任何valid状态；观察时钟与状态，重置时清除候选缓存并
  重新开始稳定性观察，此处仅允许估计器reset计数变化。只报告等待诊断，不宣称
  已经建立连续odom；进入ACTIVE时丢弃预热历史缓存，不补发准备期旧状态。
- ACTIVE：预热条件满足后，按源时刻释放状态；只有state.timestamp≤最近有效/clock
  才能发布。领先状态进入有长度和墙上等待上限的队列，按源时间排序，超时丢弃并报告。
- FAULT：ACTIVE后reset_counter变化，或任何阶段IMU源时间回退/生产者重启，停止有效状态输出，
  清空缓存，停止本次联调；完整重启并使用新run_id后重新进入PREPARING。

此预热规则是对原“reset变化即停止”的已确认细化：仅在没有发布valid状态的准备期
允许建立新候选基准，不能在ACTIVE中自动重置odom或继续沿用旧地图。
重复采样按身份去重，不刷新时钟；不能使用容许若干毫秒倒退的规则吞掉真实reset。

现存SIM-00B完整原始记录（IMU跨度121秒，区别于120.056秒验收窗口）的2407条
ODOMETRY全部为源1/1、AUTOPILOT=8及帧1/12，reset计数为
{3:8,4:95,5:2304}；在1.256秒和6.007999秒发生两次变化。2130条状态到达时超前最近
IMU时钟，最大20000us；按下一覆盖IMU释放的离线队列最大1条，最长接收单调等待
约47.990ms，文件结束无剩余。这些是历史静止样本，不能替代ROS队列和异常测试。

首轮可审查配置如下，均为冒烟参数提案，非PERF-01高速预算：

| 参数 | 提案值 | 依据与使用 |
| --- | --- | --- |
| warmup_stable_sim_ns | 10000000000（10秒） | 首个有效源状态后按源时间观察；每次准备期reset重启窗口，需持续有新有效状态/时钟；稳定不代表定位准确 |
| startup_timeout_wall_s | 60 | 延续初次等待上限；超时停止联调，不无限预热 |
| pending_limit | 100条 | 有界缓存；离线记录最大1条只是参考，不推断极端流量上限 |
| pending_timeout_wall_s | 0.5 | 高于静止记录最大约0.048秒；超时丢弃并诊断，不调时间戳 |
| source_timeout_wall_s | 2 | 独立单调看门狗；无新有效源样本时停止有效输出，时钟不外推 |
| quaternion_norm_tolerance | 0.001 | 仅容忍微小模长误差后归一化；不是姿态精度，超过该值或零模长拒绝 |

IMU与ODOMETRY分别维护最后有效接收单调时间并检测断流，不能以IMU持续掩盖状态
断流。预热窗口按有效ODOMETRY采样时间且已有时钟覆盖推进；首次尚未收到对应流时
使用启动等待，不让未初始化的最后接收时间产生假超时。

IMU同源回退按fail-stop处理，理由注明“源序列回退或乱序”，不凭单包断言发生真实
重启；ODOMETRY中完全相同样本去重，已过处理水位的旧状态丢弃，reset变化不能被
去重过滤而忽略。不同消息流时间落后彼此是正常现象，不触发源重启判断。

跨ROS话题无到达顺序保证。simulation先发clock事件再释放状态；sensors薄包装
仍以本地已接收/clock做有界接收检查，业务库不创建第二个时钟。这两处分别处理源
消息先到和传输后重新排序，不能以发布顺序代替接收证据。门控队列参数统一配置。
致命故障除诊断外，在同一源状态话题发布status=unavailable的终止状态，保留run域
和最后已知采样时间、明确reason；消费者清除待发布状态并锁定该run，不能将状态槽
中的占位数值当观测。恢复必须完整新run，超时与终止原因须有固定测试用例。

终止事件使用独立sample_id=sim.terminal:<首个故障码>:<最后源采样us>；尚无样本时
timestamp取0并说明无有效样本，重复终止维持同一身份，不复用最后valid状态ID。
reason采用terminal:<故障码>，与普通暂时不可用原因区分。sensors校验来源、run、
枚举及终止原因后优先处理该事件，绕过普通采样水位、时钟覆盖和几何校验，清缓存并
锁run；随后在自身状态话题发布独立身份的unavailable终止状态，通知后续内部消费者。

本步先发布状态消息，不新增TF广播；后续若广播odom→base_link，须单一权威来源并
沿用同一采样时间，不能引入另一套时间/参考系定义。

## 6. 文件与实施顺序

拟新增的最小功能文件组（不是本轮已创建代码）：

| 位置 | 文件/职责 |
| --- | --- |
| ros_ws/src/uav_fusionmap_msgs/ | package.xml、CMakeLists.txt及msg下四个消息 |
| ros_ws/src/uav_fusionmap_simulation/ | package.xml、CMakeLists.txt、scripts/state_clock_node.py |
| ros_ws/src/uav_fusionmap_sensors/ | package.xml、CMakeLists.txt、scripts/state_adapter_node.py |
| ros_ws/src/CMakeLists.txt | 本项目catkin入口，仅构建此src |
| simulation/ufm_simulation/ | __init__.py、mavlink_source.py、source_timeline.py：源契约解码与可独立测试的时钟/流状态机 |
| sensors/ufm_sensors/ | __init__.py、state_adapter.py：几何适配与质量保留 |
| configs/ | sim01_environment.bash、sim01_state.yaml：独立环境、帧/来源和首轮门槛 |
| ros_ws/ | sim01_env.sh、launch/sim01_state.launch：环境入口和两个薄节点装配 |
| tests/ | test_sim01_source.py、test_sim01_frames.py、test_sim01_ros_contract.py：行为及消息往返 |
| simulation/ | SIM-01A实际运行/验证说明，完成后填写命令和证据 |

纯Python业务包通过本阶段独立环境的显式PYTHONPATH加载simulation和sensors目录；
节点不散布sys.path.insert、不导入研究代码或加载模型。这是仓库源码运行方式，不宣称安装空间
脱离仓库也可运行。SIM-00A/B已验收入口保留，SIM-01使用自己的环境与配置。

实施顺序：先确认本提案及契约细化 → 建立消息与纯函数/状态机回归 → 两层实现 →
独立catkin与消息序列化 → 薄节点和有界轻量联调 → 实验记录/状态更新。
Python工具、消息生成、ROS节点和观察器统一使用Conda Radar-Diffusion解释器；
Noetic作为ROS库来源，现有pymavlink在项目目录复制使用，不修改Conda或系统安装。
catkin只以本仓库ros_ws/src为source，build/devel/install指向.runtime/ros；不构建
外层catkin_ws，不更新系统ROS或第三方桥接。新增参数不作为高速性能验收阈值。

## 7. 验收与停止边界

至少覆盖：

1. ROS消息往返保持纳秒、身份、帧、枚举和质量不可用；无效字段被拒绝。
2. 源类型/坐标/CRC筛选，时钟只随有效采样前进，断流不伪造进展。
3. 状态先到时等待正确时钟覆盖；缓存超限/超时、重复、回退、预热与ACTIVE重置行为。
4. NED/FRD已知向量、非平凡旋转姿态、q/-q、逆变换和错误原点配置。
5. 两个ROS节点只订阅约定上游，源/适配状态同一采样时间且来源可追踪。
6. 全新项目输出目录构建/包发现通过，Python显式使用Radar-Diffusion，
   Foxy/外层工作区及其他Conda环境不被混入或覆盖。

坐标确定性样例：NED[1,2,3]→ENU[2,1,-3]；FRD[1,2,3]→FLU[1,-2,-3]。
源单位姿态得到xyzw=[0,0,√½,√½]；源NED yaw=+90°得到单位姿态；源NED
roll=+90°、yaw=0得到[0.5,0.5,0.5,0.5]，允许整体符号相反。组合旋转/逆变换
往返误差≤1e−6；零四元数/非有限值拒绝，归一化仅接受可解释的微小数值误差。
已有记录四元数模长范围约0.9999999338—1.0000001304，实施前在配置中明确接受
上表阈值并测试边界，不无条件归一化任意错误输入。

SIM-01A先以现有原始记录作离线输入和确定性异常fixture验证；回放测试不冒充实时
节点或ROS bag回放已验收。后续轻量节点联调沿用600秒源时间/900秒墙上上限；
300秒记录回放属于SIM-01B，暂停/倍速/断流属于SIM-01C，40分钟属于R-10修复后的D。

用户已确认ROS编码、新内部状态话题、虚拟原点约定和预热门控；本步范围据此执行。
