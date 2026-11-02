# EXP-20261029-009：运动感知地图与原生窗口交接

日期：2026-10-29；主责任：tester；状态：已完成（SIM-MOTION-SW-03单profile软件范围）。
依据ADR-042、[具体设计](../docs/SIM_SCENE_MOTION_DESIGN_20261029.md)与
[交接及复现](../docs/SIM_MOTION_SW03_DELIVERY_20261029.md)。
分支feature/engineering-initialization、HEAD d96d4439da1007489c80e7f21b132abff16505bf；
全部既有dirty/untracked保留，无提交/推送，不改同级研究仓库/第三方源码/原Conda或终端ROS。
无训练/模型forward、真实DEM/占据融合、控制指令、大型依赖安装或无用途Hash。

## 1. 已有实现与本轮修改

已有SW-02同FDM/坐标/受控Ray/Camera/ACK；既有SensorBundle/placeholder/M1 latest及公开query/replay。
本轮新增ros_ws/sim_motion_delivery_run.py、sim_motion_delivery.py显式装配和验收监督，
扩展sim_motion_gate_run.py可选handoff、故障step25/250、第二clock图负例及首采样shutdown。
旧SW-02默认不装配下游/窗口，公共消息及旧launch不改。

涉及文件：

- sensors/ufm_sensors/scene_stream.py新增默认关闭的require_exact_pose；scene_sensor_node.py显式flag/ready/锁定诊断。
- tests/check_sim_motion_live.py复用有界线格式记录器、可选下游streams与独立decoder；原默认记录流保持。
- tests/motion_delivery_checks.py独立几何/栅格、来源/图及公开回放对账；check_motion_delivery_figures.py验证真实原生渲染目标。
- tests/motion_graph_conflict.py仅广告第二clock、不发布假时间；test_sim_motion_delivery.py新增6项配对/无回波边界。
- ros_ws/local_map_replay.py新增可选--map-config，默认配置保持；支持本次具名场景几何的独立回放进程。
- ros_ws/native_scene_rviz.cpp、simulation/gazebo_scene_gui.cpp新增仅显式环境开启的分阶段截图；运动RViz停钟清空raw并标History。
- 新增五图/来源/图注、新交接与本记录，同步全局状态、接口/架构/坐标说明、计划、ADR和报告/素材索引。

## 2. 独立预期与实际执行

核对Python为/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python，统一bash ros_ws/sim01_env.sh入口。
每次新目录先复制冻结profile/坐标时间oracle，保存交接预期、源快照后再执行引擎。
真实链每采样tick等待对应公开快照；非采样step仍真实4ms FDM/4×1ms Gazebo。
Camera/Ray原始测量时间、IR≤5ms、pose≤10ms、等待≤40ms、源1ns网格及事务预算均不放宽。

| 运行 | 结果与限制 |
| --- | --- |
| [160638299468](../.runtime/runs/sim-motion-sw03-20261029T160638299468/manifest.json) | 首次实际10 Bundle/占据/快照，但5帧pose_age=4ms，未过独立同tickoracle；保存failed，不将旧10ms合法配对冒充同帧 |
| [160830417494](../.runtime/runs/sim-motion-sw03-20261029T160830417494/delivery-validation.json) | 新运动模式精确pose等待后10组/14查询与独立回放通过，原生前后/历史六图通过；之后补足实际显示开关/底栏和图拒绝核验 |
| [161109867941](../.runtime/runs/sim-motion-sw03-20261029T161109867941/manifest.json) | 首采样故障0组/空地图/锁定通过；shutdown客户端255、daemon实际0，但初次检查把两者混为失败，run保留false；daemon POSIX关机源码system_exit(0)与原始日志均核对 |
| [161302697539](../.runtime/runs/sim-motion-sw03-20261029T161302697539/manifest.json) | 严格区分客户端/daemon后首采样故障及清理通过；不是将旧daemon255放宽为成功 |
| [161450959654](../.runtime/runs/sim-motion-sw03-20261029T161450959654/delivery-validation.json) | 运行期第250步控制端丢IR ACK：9 Bundle/占据/快照、13查询、clock996ms，实际raw1000ms不提交；回放/清理通过 |
| [161615581161](../.runtime/runs/sim-motion-sw03-20261029T161615581161/manifest.json) | 第二clock广告，按motion_graph_authority:/clock预期拒绝，尚未创建FDM/PX4；manifest保持false，10个自有子进程退出0、端口释放 |
| [最终正常/恢复161731864328](../.runtime/runs/sim-motion-sw03-20261029T161731864328/delivery-validation.json) | 上一故障run之后，从新身份/0时刻/空地图开始；10组/14查询、逐帧Context及独立CLI/回放通过，真实原生六图/历史开关/像素通过 |
| [最终首采样故障161927705875](../.runtime/runs/sim-motion-sw03-20261029T161927705875/delivery-validation.json) | 24成功step、clock96ms、0组/空地图，terminal锁定，PX4 daemon=0、IPC客户端255分别留证，全部清理正常 |

故障注入是控制端忽略IR ACK，原始IR和ACK仍真实发布；不伪称真实相机损坏或跳过首个采样。
没有在失败run推进新clock补齐PX4启动，没有重写raw时间或换轨迹/旧图片取得通过。

## 3. 最终结果与证据类型

正常1s真实动力学从[0,0,8]到[5.4362694069936195,-0.0024849018548632144,4.626639929639477]m，
位移6.397858m；不是稳定受控飞行。251条公共clock/有效状态/TF、10对raw/20 ACK，
10个Bundle/占据/快照均按同一采样tick。独立SciPy旋转/0.8m杆臂/全部13,217回波投影及栅格对账一致。
M1公开cell数410→1821，只有observed占据、概率float32约0.9、质量unavailable，未观测处unknown。
14条公开query含初始unavailable、逐tick occupied、TTL+1ns stale、未观测unknown和旧run拒绝；
独立application CLI返回occupied、证据时刻1000000000。独立回放进程
[161750730252](../.runtime/runs/local-map-replay-20261029T161750730252/report.json)10快照/14查询逐值一致。

原生Gazebo前后133,109、RViz前后174,999像素显著变化；IR实际前后67,933像素变化。
停钟3s后RViz Radar/IR实际enabled=false，地图Marker仅为历史unavailable、无当前occupied，
底栏History清晰可见；五个原件副本与图注见[素材](report_assets/sim-motion-20261029/README.md)。
新的运动素材没有替换历史固定场景图。

| 设计用例 | 本轮证据类型 |
| --- | --- |
| M01/M02坐标/杆臂 | SW-01解析预期/SW-02实际FDM读取，本轮全部回波Context和栅格独立对账；实际Doppler误差最大5.2206251e-7m/s |
| M03/M04两引擎/小运动 | 真实250步、Gazebo读回、10对Ray/Camera与前后原生像素；没有轨迹替身 |
| M05配对边界 | 新增离线5ms/10ms/40ms及各+1ns测试；真实同tick模式10帧pose_age/IR差均0 |
| M06来源/图 | 实际单clock/state/TF及跨层订阅审计；实际第二clock在FDM/PX4启动前拒绝 |
| M07坏载荷 | 继承SW-01严格codec/旧消息兼容与SW-02八类真实服务拒绝，新入口仍执行八类；不声称每个坏字段都重做物理注入 |
| M08缺失/迟到ACK | 实际首25/运行期250丢回执，业务clock停止、terminal锁定、后续service拒绝；旧ACK跨run严格绑定沿合同测试，未额外物理注入 |
| M09 pause/resume | 新入口沿SW-02实际step24暂停、step25幂等；正常后续从下一步继续，无重复采样 |
| M10 reset/new run | 故障后实际新Master/run/空地图、从0推进、旧run query拒绝；不重置已失败旧身份 |
| M11地图/回放 | 实际10占据/快照/14查询及独立回放；真实失败零/九组，无回波不刷旧时刻有离线测试，本次真实场景并非无回波 |
| M12原生/清理 | 实际原生六图、五图交付、正常/两故障/图拒绝清理；旧估计与静态原生入口实际回归通过 |

正常收据10,125,044字节，低于16MiB/每流512限制；这只是实际线格式计数，不是RSS或正式性能。
SensorStream审计沿用旧clock_reset=failed字段，terminal时为true；实际clock单调，不能据字段名宣称发生回退。

## 4. 回归与未执行检查

- [161616779970](../.runtime/runs/sim-motion-sw01-20261029T161616779970/report.json)：20组真实genpy与独立字节一致，17份旧定义保持；新增6项，运动定向43/43（0.183s）、全仓862/862（61.107s）。
- [旧estimated/T-14](../.runtime/runs/sim01a-fixture-20261029T161937936244/manifest.json)实际ROS状态/镜像/唯一TF及关闭通过。
- [旧静态原生入口](../.runtime/runs/sensor-scene-20261029T161947324857/manifest.json)实际场景/Radar/IR/地图、图与像素及关闭通过，require_exact_pose旧默认false。
- 额外SW-02默认入口单独再跑的前两次启动，自动审批因服务器过载/流连接中断拒绝，命令未执行；未绕过审批。
  随后重试同一命令，[163827460906](../.runtime/runs/sim-motion-sw02-20261029T163827460906/manifest.json)实际通过250步/10对/20 ACK与完整清理；前两次拒绝不当作运行失败或成功。

可复现命令见交接；所有进程用固定解释器或已有原生二进制，日志/源快照/命令、公开收据与图均在新目录。
没有覆盖前次失败或把不同run的计数拼成同一次验收。

最终[证据审计](../.runtime/runs/sim-motion-sw03-audit-20261029T164115720158/audit.json)核对
16份文档/860条本地链接、正常与首故障25份运行源码一致、17份旧定义及五张导出图片原件一致。
随后[宿主清理审计](../.runtime/runs/sim-motion-sw03-audit-20261029T164115720158/host-cleanup-audit.json)
在真实宿主/proc精确核对12个本轮目录、113条自有子进程记录，无残留，所用端口全部释放。
第一次合并宿主审计同样因自动审批服务过载未执行，拆开不依赖宿主的证据核对后，
只读宿主审计通过原审批路径成功执行；未绕过权限，也没有向既有其他进程发信号。

## 5. 限制与下一项

只关闭SW-01—03单profile有界运动的软件工作包，不关闭真实模型/设备、飞控控制、高速实时、
机载资源、DEM/占据融合或正式阶段。MapQuery按显式时间，不新增墙钟liveness；UI历史不等于服务拒绝旧时刻查询。
可继续安排有界多场景运动回归的具体设计，先定义不同姿态/遮挡/无回波及故障恢复输入、独立预期和资源上界；
不自动延长当前自由动力学窗口，不新增控制指令，不回到暂缓的真实数据/模型质量任务。
