# 有界多场景运动回归具体设计

日期：2026-10-29；版本：v0.1；任务：SIM-MOTION-SW-04-DESIGN。
主责任：simulation_engineer；状态：已完成（具体设计）；新增多场景尚未实施或运行。
依据：[SW-03交接](SIM_MOTION_SW03_DELIVERY_20261029.md)、[原运动设计](SIM_SCENE_MOTION_DESIGN_20261029.md)、
ADR-042/043；实际核验：[EXP-20261029-010](../experiments/2026-10-29-sim-motion-multiscene-design.md)。

## 1. 问题与边界

SW-03只验证固定初始姿态/场景下的1秒运动。点从Radar投影到地图正确，尚不能证明
不同朝向的场景回波正确、遮挡取最近表面，或真实空回波能贯通到公开查询。
本批保持同一JSBSim FDM、4ms步长、250步、初速5m/s、ENU锚点[0,0,8]m，
Gazebo四个1ms子步、每25步真实Ray/Camera采样，以及单clock/state/TF和同tick Context。
不新增控制/解锁/航点、第二轨迹源或训练监督，不延长自由动力学窗口。

新增范围为测试场景清单、独立预期、显式装配和核验器；公共消息/服务字段保持。
现有motion profile v1严格固定，不能静默放宽；旧入口及默认静态地面保留。
真实设备、研究质量、DEM/占据融合、机载资源/正式PERF-01和完整阶段退出独立跟踪。

## 2. 真实链审计

| 源码/符号 | 当前事实 | 实施要求 |
| --- | --- | --- |
| [profile.py](../ros_ws/src/uav_fusionmap_sim_scene_msgs/src/ufm_scene_contract/profile.py) `validate_profile` | v1逐字段/类型精确匹配，改初速即拒绝 | 新增独立测试清单，不放宽旧校验 |
| [sim_motion_gate_run.py](../ros_ws/sim_motion_gate_run.py) `main` | LSZH IC固定8m/5m/s/psi=90；CLI只暴露IR ACK故障25/250步 | 新装配只选有限IC/几何/故障；默认保持 |
| [scene_motion.py](../simulation/ufm_simulation/scene_motion.py) `SceneRegistration` | 初始ENU/质心FLU注册，消费真实FDM输入 | 独立核对新IC旋转及原始输入转换 |
| [sensor_scene.py](../simulation/ufm_simulation/sensor_scene.py) `create_world` | 自动前置ground，障碍collision/visual共几何；飞机仅visual | 清空objects仍有地面；空碰撞域必须显式去地面 |
| [scene_motion_world.py](../simulation/ufm_simulation/scene_motion_world.py) `create_motion_world` | 复用旧生成器，替换pose插件并设置受控传感器 | 新几何只作用于显式新测试 |
| [gazebo_scene_radar.cpp](../sensors/gazebo_scene_radar.cpp) `Update` | 96×24端点均含，非有限/≤0.5m/≥30m被过滤；零点也发布/ACK | 空回波来自真实Ray，不丢点模拟 |
| 同上 | v外层/h内层，Doppler含角速度×0.8m杆臂 | 独立最近相交、点序、速度/功率核验 |
| [gazebo_scene_step.cpp](../simulation/gazebo_scene_step.cpp) `AckReceived`/`StepReceived` | 可丢kind1/2回执，失败锁定且不提交clock | 新增第125步Radar故障装配，无需改公共协议 |
| [scene_stream.py](../sensors/ufm_sensors/scene_stream.py) `SceneStream` | 精确pose为显式开关；terminal锁定；空点可配对 | 新场景继续精确pose，空回波不等于不可用 |
| [local_map.py](../mapping/ufm_mapping/local_map.py) `update`/`query` | 有效空帧推进revision/header，保留旧cell时间 | 区分初始unavailable、有效空图unknown和旧证据TTL |
| [sim_motion_delivery.py](../ros_ws/sim_motion_delivery.py) `after_step`/`finish` | 强制每帧非空且有当帧cell | 按场景核验，不吞异常或伪造占据 |
| [motion_delivery_checks.py](../tests/motion_delivery_checks.py) `verify_chain` | 由实测SceneFrame重算Context/投影/voxel | 补独立原始FDM转换与最近相交，不止下游自洽 |

本轮13项只读探针证实固定profile拒绝、自动ground、空图/TTL语义和初始解析算例；不是新引擎运行。

## 3. 独立测试清单

SW-04A拟新增 `configs/sim_motion_multiscene_fixture.json`，schema为
`sim_motion_multiscene_fixture.v1`，只供测试装配，不进入在线业务合同。
根字段固定 `schema_version / suite_id / base_motion_profile / cases / resource_limits`；
base引用现有v1文件，冻结保存完整副本并逐值比较，不新增Hash。
case固定字段 `case_id / ic_degrees / geometry_id / epochs / fault / expected_id / native`；
IC为[phi,theta,psi]度，只允许下节枚举，只改生成IC的三个角，其他IC字段保真。
不允许任意CLI浮点覆盖、duration/速度/锚点覆盖、随机场景、路径跳转或未知字段。

清单≤256KiB、深度≤8、节点≤8192、UTF-8字符串≤128字节；恰好9个唯一case。
最多7个具名几何模板、每模板≤8个轴对齐box、每case≤2次切换；尺寸有限且为正，
step/时间必须整数、对象名唯一、材质已登记。重复键、bool冒充整数、非有限值、
非法枚举/版本/身份/路径、LiDAR/target/observed_mask监督字段拒绝。
几何物体使用obstacle身份，几何评测信息不发布到在线业务图。

继承原scene传感器/标定/注册参数，不编辑原scene配置。S01保留原地图；S02—09用
显式稀疏测试地图：origin[-40,-40,-8]m、resolution[0.5,0.5,0.5]m、shape[160,160,64]、
max_active_cells=20000、TTL=500000000ns。更大逻辑覆盖不分配稠密数组，不代表RSS达标。
每case独立map_id/run/clock、Master/rootfs/收据；S09只把S08身份用于拒绝探针。

## 4. 九个核心用例

角度为JSBSim NED/FRD初始欧拉角；ψ=0/90/180对应ENU yaw=90/0/-90度。
正常case均250步/1s、10对raw/20 ACK/10 Bundle/占据/快照，pose_age/IR差均0。
S01为必要兼容回归；新case不复用它的实测点数/末帧位姿作预期。

| 用例 | IC [phi,theta,psi]度 | 几何/注入 | 独立通过条件 |
| --- | --- | --- | --- |
| S01 旧基线 | [0,0,90] | legacy/原地图 | 原SW-03线格式/逐层查询/回放保持，不要求原精确点数 |
| S02 向北 | [0,0,0] | north_wall | 初始yaw=90及杆臂旋转正确，真实box回波与解析相交一致 |
| S03 向南 | [0,0,180] | south_wall | yaw=-90轴向/符号正确，同tick投影与公开查询一致 |
| S04 倾斜 | [10,5,90] | east_wall | 初始ENU R=Rz(0)Ry(-5)Rx(10)，动态旋转/杆臂/Doppler正确 |
| S05 遮挡 | [0,0,90] | occlusion_boxes；原生显示 | 首采样冻结选定射线穿过近/远box，回波取近表面；后续逐帧解析核验 |
| S06 空碰撞域 | [0,0,90] | empty，无ground/障碍/飞机collision | 10份真实零点raw与正常IR/ACK、valid空占据/快照；revision10/unknown，绝不free |
| S07 有回波→空→返回 | [0,0,90] | moving_box；原生显示 | 100—400ms有回波，500—900ms空，1000ms返回；旧cell证据时间/TTL保持 |
| S08 中途Radar ACK故障 | [0,0,90] | east_wall，第125步丢Radar ACK | clock止于124步/496ms；4组下游/最后400ms；500ms raw不提交；terminal锁定/清理 |
| S09 新身份恢复 | [0,0,90] | east_wall，S08清理后新run | 首帧前revision0/unavailable；正常10组；旧run/clock查询拒绝，不导入旧cell/raw |

新模板均无地面且collision/visual相同。east_wall中心[12,0,8]、尺寸[1,12,12]m；
north_wall中心[0,12,8]、尺寸[12,1,12]m；south_wall中心[0,-12,8]、尺寸[12,1,12]m。
moving_box近态同east_wall，远态中心[100,0,8]m；occlusion_boxes近box中心[8.5,0,8]、
尺寸[1,6,6]m，远box中心[12.5,0,8]、尺寸[1,2,2]m；empty无box，legacy只引用旧场景。

初始轴向射线近/远面距离7.2/11.2m，但偶数网格没有正中射线。
h48/v12角为0.007368421052631469/0.015217391304347794rad，初始距离约
7.201029212956173/11.201600997931823m。首采样是100ms，必须用真实原始FDM独立转换
的pose重新求交，不能把初始算例套到所有帧。S05要求首采样选定射线有遮挡；
后续允许姿态/高度改变露出远表面，但仍须逐帧符合oracle。
S04的1秒新姿态尚未实测；若触发既有z>0.5m/锚点距离≤200m门禁，保留失败，
不裁剪轨迹、自动换角度或放宽门槛。

## 5. 独立预期与核验顺序

1. 先保存IC/几何字面量、step/epoch/故障表、解析旋转/射线算例、查询顺序/状态和预算，
   再构造IC/SDF、执行实际生成消息序列化。沿用genpy真实字节对账和旧定义比较；
   不用mock或新生成器输出反写expected。
2. 保存真实IC、ECEF英尺/姿态矩阵/uvw/pqr/浮点时间和整数step。独立测试侧按冻结单位、
   NED/FRD→ENU/FLU矩阵及初始大地注册重算逐步SceneFrame，不调用生产SceneRegistration算预期。
   不冻结跨IC末帧轨迹；原时间/四元数/身份门禁保持。
3. 从独立box清单做slab最近正相交，使用96×24角网格、原始pose和0.8m杆臂，
   不用raw range或生产world生成结果当预期。另读回SDF与Gazebo物体pose，核对实际安装几何。
   S01旧cylinder沿原链核验，不声称已覆盖box解析oracle。
4. 恢复每点唯一v/h索引、点序，角误差≤5e-6rad；非边界射线命中/无命中一致。
   距离容差0.011m（声明0.01m分辨率加0.001m数值裕量）；距box边缘≤0.02m或量程端点
   ≤0.011m的射线由解析oracle先标记边界，最多48条/帧，只允许解析相邻面/端点所列结果。
   遮挡选定射线必须非边界；超额或没有合格射线直接失败，不能看实测差异再调容差。
   Doppler、float32有限值/范围及功率继续独立核对。
5. 真实反序列化Bundle，以独立旋转/平移/voxel oracle对占据逐值核验：probability=.9、
   缺失质量、observed来源不变。公开snapshot/query与独立进程公共占据回放逐值比较。
   在线感知/地图不得读取几何oracle或原始FDM来生成占据，mapping不得订阅raw/仿真。

容差/预算是待实施约束；本轮初始解析探针不代表实际引擎精度或误差分布已通过。

## 6. 空观测、切换与故障

S06首次观测前query为unavailable/revision0；首次valid空帧后snapshot为valid/revision1，
覆盖内未观测cell为unknown/no_observation、无概率/证据时间。到1s revision10、cells为空。
IR允许均匀背景，核对Camera真实时间、尺寸、32FC1、有限载荷和ACK；
不套用旧“IR必须变化/地图必须occupied”判据，不把均匀背景当相机故障。

S07在400ms采样/下游排空且world暂停、无pending SceneStep时，把唯一obstacle移远；
900ms排空及TTL检查后移回。显式测试监督仅设置/读回两个冻结位置，
下一步FDM前确认collision/visual一致并保存world time未推进收据，不改飞机/FDM状态。
若现有Gazebo接口不能在此边界提供一致几何，则在本仓自有薄插件补具名设置/读回屏障，
先验证屏障再组合；不得静默降为丢点模拟或偷偷多走world步刷新渲染。
下一采样必须来自切换后真实几何，Camera过渡缓冲不通过即保留失败。

在900ms快照排空后、物体移回之前，选400ms实际观测且此后未再命中的cell：
query_timestamp=900000000时occupied、900000001时stale，证据始终400000000。
query只是显式请求时间，不推进clock；必须在1000ms快照前执行，否则旧时刻请求会
query_before_latest_map_time/unavailable，不能误当TTL通过。
S07另在900ms暂停期间保存empty阶段的Gazebo/RViz渲染目标，证明真实移远/零点显示，
IR允许均匀背景，地图允许保留旧cell；拍摄后再移回物体，不把空阶段截图当free证据。
1000ms只要求真实重新命中的cell获得新证据；未再命中的旧cell仍保留旧时间。

S08只忽略实际发布的kind1回执，不改raw/IR/measurement_timestamp。
具体timeout/terminal原因、496ms clock、4组下游、无失败tick提交和清理必须同时满足，
不能只凭非零退出码判成功。原身份继续请求必须scene_run_locked，不推进失败clock。
S09确认自有进程/端口清理后新建身份，不自动杀用户进程、不沿用失败地图或补发旧证据。

## 7. 上界、兼容与原生交付

| 项目 | 冻结约束 |
| --- | --- |
| 核心 | 9 case串行、各一次正式判定；失败保留并停止，修复后新目录/身份复验 |
| 每case | ≤250步、每流≤512条、线格式总收据≤16MiB；原启动60s/首采样3s/事务1s/会话120s保持 |
| 核心累计 | 9×16MiB=144MiB线格式收据；8正常+1故障合计成功提交源时间8.496s，非墙钟速度指标 |
| 几何/地图 | ≤8 box/模板、≤2切换/case、≤20000稀疏cell，无新稠密体素或无限缓冲 |
| 产物/墙钟 | 每case产物≤256MiB；全套含构建/兼容≤3GiB、≤1800s，核心会话合计≤1080s |
| 超限 | 自有writer写前检查；外部PX4/Gazebo日志按墙钟监测并停止，可能间隔超写，须记录而非声称硬磁盘/RSS上限 |
| 原生 | 仅S05/S07启Gazebo及标准RViz，各存before/after/history两种渲染目标和IR viewport，S07另存900ms empty两图；其他case仍运行真实Camera |
| 兼容 | 旧profile/17份旧定义、精确/历史pose单元；装配后实际旧estimated、旧静态原生、旧IR首采样故障各一例，共3例计入预算 |
| 清理 | PX4串行，检查固定端口/外部进程，新Master/rootfs；daemon/shutdown客户端退出码分开保存，不强改失败为成功 |

预算/日志监测/像素不证明RSS、机载吞吐、20ms、持续飞行或正式性能。
旧13,217点/10,125,044字节只属于SW-03，不证明新场景预算已通过。
原生核对S05/S07阶段几何/显示、History raw关闭/地图历史失效；不要求S06有纹理截图。

## 8. 分步任务、文件范围与恢复

| 任务 | 主责任 | 修改/交付 | 完成条件 |
| --- | --- | --- | --- |
| SIM-MOTION-SW-04A | simulation_engineer | 新清单/有界校验、独立IC/box/空图/TTL/故障预期、fixture/真实genpy对账及中文记录 | 预期先保存，9 case结构/拒绝边界通过，旧profile/定义保持；不启新多场景引擎 |
| SIM-MOTION-SW-04B | simulation_engineer | 显式装配、IC/SDF、几何切换屏障、场景化query/checker；必要时仅改本仓薄插件 | 同FDM/原始时间/唯一权威，定向真实空域/切换/中途故障及受影响旧默认通过 |
| SIM-MOTION-SW-04C | tester | 冻结矩阵、回放/原生/恢复/清理/兼容、轻量全仓及交接 | 最终实现上9核心+3兼容完整收据、独立几何/查询、预算及实际清理；仅关闭本软件包 |

B定向验证是新运行机制准入，C执行最终完整矩阵；无新修改/失败不反复重跑既有项。
各步先查Git/忽略规则/真实入口，固定Conda入口、隔离`.runtime/ros`及本仓构建目录，
不构建外层catkin、不改原第三方源/二进制。失败保留预期/产物，停止自有run后另建新run；
不删历史、不自动提交/推送、不用reset/checkout撤回用户修改。
本轮只交付设计及既有软件/只读核验；直接下一项SW-04A，不立即执行9场景或恢复研究质量任务。

2026-10-29后续：[SW-04A离线合同](SIM_MOTION_SW04A_CONTRACT_20261029.md)已完成清单/校验、
独立预期和真实线格式核验，运动66项/全仓885项通过；新增多场景仍未运行。
直接下一项SW-04B，范围/门槛按上表保持，最终9核心/3兼容及原生交接仍属SW-04C。

2026-10-29 SW-04B实测修订：原第5节“近边缘几何射线≤48条”假设在S07末帧出现63条，
该次运行保留失败，不提高48或物理误差容差。后续固定采用
`strict_all_rays_no_exemptions_v1`：所有射线包含边缘都必须逐条满足名义最近相交、
命中集合/顺序精确一致及原5e-6rad/0.011m界，豁免数始终0。
近边缘总数只记录诊断，不按区域宽度跳过数据，也不允许缺失/新增或改用远表面。
因此本规则替代旧的边界候选数量门槛和可选结果分支，验收中的每条物理检查均保留。
旧v1清单的48字段保留兼容，不启用任何边界豁免；独立严格预期在每个新run实采前冻结。

2026-10-29 SW-04C实际核验修订（保持身份、角度/距离及原数值容差）：

- S02实际源矩阵在原1e-9正交界内，但极分解与生产SciPy 1.10.1的Markley矩阵转四元数
  估计相差约4.2e-11；不能把两种估计按1e-12视为同一对象。测试侧独立标量公式重算
  Markley单位旋转，再与实际四元数矩阵按原1e-12比较；不调用生产转换器，也不改源值。
  算法依据见[SciPy对应版本文档](https://docs.scipy.org/doc/scipy-1.10.1/reference/generated/scipy.spatial.transform.Rotation.from_matrix.html)。
- S04生成IC中的theta=5被旧gamma=0覆盖，实际源姿态先验失败；JSBSim v1加载顺序先theta、
  后gamma，见[所用1.1.13源码](https://raw.githubusercontent.com/JSBSim-Team/jsbsim/v1.1.13/src/initialization/FGInitialCondition.cpp)。
  仅非零pitch的生成IC省略冲突gamma项，以phi/theta/psi为显式权威；源IC与零pitch旧行为保持。
  这是“其余IC字段保留”的一个明确例外，不引入控制指令或改写FDM输出。
- S01仍按旧cylinder/地面场景链核验，不计入新增box解析逐射线统计；S02—S09保持严格零豁免。

前两次完整矩阵尝试分别在S02、S04停止，原失败目录保留；修正后必须新身份重跑整套。

后续S05实际末帧姿态/视场离开障碍，合法零点被监督器过强断言拒绝；独立10帧解析全部匹配，
修正为保留旧证据时间，不要求每个合法运动帧有回波。S07实际Camera返回但标准RViz默认
五帧中值显示范围留下黑图，像素校验拒绝；仅新视图设Median window=1，不改raw/业务数据。
对应两次失败同样保留，最终从S01整套重跑。

2026-10-29 [SW-04C最终交付](SIM_MOTION_SW04C_DELIVERY_20261029.md)已完成：
9核心/3兼容、84组业务/121查询、75帧逐射线零豁免、公开回放及14阶段总图/12 viewport通过。
新增7项、运动84项/全仓903项及全部尝试清理通过；仅关闭本多场景软件包，完整阶段门槛不变。
源矩阵仍守原1e-9正交界，独立极分解后与单位四元数旋转保持1e-12比较，原始矩阵/时间不改写。
