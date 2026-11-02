# EXP-20261029-012 多场景真实引擎装配与定向机制验证

日期：2026-10-29；任务：SIM-MOTION-SW-04B；主责任：simulation_engineer。
状态：已完成（显式装配/真实空域/暂停切换/中途故障软件机制门）。
交付/文件列表：[SW-04B说明](../docs/SIM_MOTION_SW04B_ENGINE_20261029.md)；依据ADR-043与SW-04A。

## 1. 环境与保护

分支feature/engineering-initialization；HEAD=d96d4439da1007489c80e7f21b132abff16505bf。
核对根/目录AGENTS、当前状态、接口、Git脏工作区及忽略规则，全部既有修改和未跟踪文件保留。
Python实际sys.executable为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，
所有Python/ROS进程经`bash ros_ws/sim01_env.sh ...`与既有隔离环境启动；未安装依赖或改研究仓库。
编辑前用[182731104488](../.runtime/runs/sim-motion-sw04a-20261029T182731104488/old-definitions.json)
冻结25份定义和7份旧配置/入口；本轮有意修改其中gate装配入口，另外6份逐值保持。
消息未重新生成，C++只编译本仓自有产物，不改原第三方源/二进制或外层catkin。

## 2. 修改与预期

新入口显式选择冻结case，IC/几何/地图/故障来自具名清单，旧默认入口不接新case。
S06真实无ground/collision；S07仅在step100/225暂停且无pending事务时切换唯一obstacle；
S08在125步忽略实际Radar ACK。原FDM/测量时间、单一clock/state/TF、250步/1s保持。
各次运行在编译/采样前保存输入、独立预期、case-spec和源码，不用实测生成预期轨迹或改raw。
新几何RPC复用标准类型，只载仿真基础设施诊断，不把几何oracle接到在线感知/地图。

## 3. 失败与修正（全部保留）

| 尝试 | 原结果/原因 | 修正与边界 |
| --- | --- | --- |
| 首轮定向 | 75项中两项ImportError；新ROS脚本与旧离线脚本同名，导入了错误模块；终端输出保留于本次工具执行，未单独存日志 | 新入口改为sim_motion_multiscene_ros_run.py；旧离线文件不改 |
| [S06 183746766133](../.runtime/runs/sim-motion-sw04b-S06-20261029T183746766133/manifest.json) | 1s采样/空图回放后，原始矩阵与单位四元数比较失败；最大差8.59e-11 | 原矩阵仍≤1e-9正交界；测试侧独立极分解后严格按1e-12核对，不改原始数据/时间/生产转换 |
| [S07 184114007576](../.runtime/runs/sim-motion-sw04b-S07-20261029T184114007576/manifest.json) | 首次切换scene_geometry_shape_readback，停止；未把部分几何安装算成功 | Link::FillMsg含父link visual与障碍visual，按唯一具名visual读取，尺寸/pose门槛不变 |
| [S07 184406432342](../.runtime/runs/sim-motion-sw04b-S07-20261029T184406432342/manifest.json) | 两次切换完成但末帧63条近边缘射线，旧48条假设失败 | 新run前明确固定零豁免逐射线规则，所有边缘也须通过原命中/顺序/误差界；不提高误差、不删点，原失败不追溯改判 |

矩阵诊断实测最大正交残差1.7188406253865196e-10，独立极分解与实际四元数最大差
5.671461564271674e-16。visual选择依据官方[Link源码](https://raw.githubusercontent.com/gazebosim/gazebo/gazebo11/gazebo/physics/Link.cc)，
实测读回visual_records=2、visual_name=obstacle_wall::body::visual。
严格零豁免规则及原48假设处置已补入设计；原v1清单保留兼容，不静默换几何或放宽物理容差。
原始失败数据的只读矩阵复核见[rotation-diagnosis.json](../.runtime/runs/sim-motion-sw04a-20261029T185633547365/rotation-diagnosis.json)，没有回写该失败run。

## 4. 最终实际证据

| 运行 | 通过事实 | 产物 |
| --- | --- | --- |
| S06 184000466912 | 250步/251 clock/TF、10对raw/20 ACK，10组Bundle/空占据/空快照，13 query、unknown/缺失证据与独立回放/清理通过 | [validation](../.runtime/runs/sim-motion-sw04b-S06-20261029T184000466912/validation.json)、[公开录制](../.runtime/runs/sim-motion-sw04b-S06-20261029T184000466912/public-recording.json) |
| S07 185439436758 | 250步/10组/16 query，真实回波→5空帧→返回、两次暂停读回、400ms cell在900ms等TTL/加1ns过期、独立回放/清理通过 | [独立几何核验](../.runtime/runs/sim-motion-sw04b-S07-20261029T185439436758/multiscene-validation.json)、[几何收据](../.runtime/runs/sim-motion-sw04b-S07-20261029T185439436758/geometry-events.json)、[公开录制](../.runtime/runs/sim-motion-sw04b-S07-20261029T185439436758/public-recording.json) |
| S08 184953262719 | 第125步scene_radar_timeout，业务clock496ms，4组下游/最后400ms；5对raw/10个实际ACK，500ms不提交；锁定与清理通过 | [validation](../.runtime/runs/sim-motion-sw04b-S08-20261029T184953262719/validation.json)、[下游核验](../.runtime/runs/sim-motion-sw04b-S08-20261029T184953262719/delivery-validation.json) |
| 旧默认185131644710 | 无suite旧SW-03，13,217回波、10组/14查询、原IR变化/同tick、独立回放与清理通过 | [delivery-validation](../.runtime/runs/sim-motion-sw03-20261029T185131644710/delivery-validation.json) |
| 软件185633547365 | 新增11项、运动77/77、全仓896/896（59.378s），77组Scene独立字节/36公共消息往返通过 | [report](../.runtime/runs/sim-motion-sw04a-20261029T185633547365/report.json)、[targeted.log](../.runtime/runs/sim-motion-sw04a-20261029T185633547365/targeted.log)、[full.log](../.runtime/runs/sim-motion-sw04a-20261029T185633547365/full.log) |

最终S07之前的[184846593173](../.runtime/runs/sim-motion-sw04b-S07-20261029T184846593173/manifest.json)
已在零豁免规则下通过；之后仅补收据逐坐标读取实际model pose和新CLI禁止故障步覆盖，
因此用185439436758在最终插件上重验。S06/旧默认各自冻结源码，不据此宣称完整矩阵同源码验收。

准确复现命令见交付说明；本轮全仓入口仍为：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_motion_multiscene_run.py --full
```

此离线report的new_fdm_trajectory_executed=false只描述该测试入口；上表三个真实机制run单独记录。
实际进程、清理、失败及逐值兼容汇总见[engine-handoff.json](../.runtime/runs/sim-motion-sw04a-20261029T185633547365/engine-handoff.json)。
三例订阅线格式收据分别约6.51/8.34/4.17MB，均<16MiB/每流512；观察产物<256MiB。
这是逻辑载荷和产物监测，未测RSS/网络全部开销、20ms或正式性能。

## 5. 限制与下一步

没有原生新窗口/截图、完整9核心/3兼容、S05实际遮挡或S09显式新run旧身份恢复矩阵，
也没有并发pending几何争用压力测试；不能用源码门禁/已有离线测试替代这些实测。
旧estimated/静态原生/旧IR首采样故障本轮未重跑，留SW-04C；研究质量/真实DEM/占据融合/机载资源/正式阶段仍未关闭。
失败run只清理自有进程、保留全部预期/日志，另建新run；未提交、推送或删除历史。
下一项SW-04C在最终实现上执行9核心/3兼容、S05/S07原生阶段截图、显式恢复及完整证据/预算交接。
收尾已核对13份文档856处相对链接、7份Python AST、25份既有消息定义与结果/状态一致性，
git diff --check通过；所列最终/失败/中间运行共88个已记录子进程PID均无残留，
三个失败runtime manifest保持failed。见[最终检查](../.runtime/runs/sim-motion-sw04a-20261029T185633547365/document-final-checks.json)。
