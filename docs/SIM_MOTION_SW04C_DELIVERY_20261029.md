# 多场景运动矩阵与原生交付

日期：2026-10-29；版本：v0.1；任务：SIM-MOTION-SW-04C；主责任：tester。
状态：已完成（同源码9核心/3兼容、原生阶段图及软件交接范围）。
依据：[具体设计及实际修订](SIM_MOTION_SW04_MULTISCENE_DESIGN_20261029.md)、ADR-043。

## 1. 已有代码与本轮实现

已有同一FGFDMExec、真实Ray/Camera与ACK、唯一clock/state/TF、显式多场景装配、
暂停几何屏障及SceneStream→placeholder→M1→公开查询/独立回放。本轮不新增地图算法或公共字段。

| 文件 | 本轮改动与用途 |
| --- | --- |
| [matrix_run](../tests/sim_motion_matrix_run.py) | 冻结全源码文本/独立预期；9核心与3兼容串行、失败停止；新身份、回放目录、预算和子进程核验 |
| [矩阵测试](../tests/test_sim_motion_matrix.py) | 拒绝缺例/重排、失败/未清理/混源码、错误提交时间与超限证据 |
| [native_scene_rviz](../ros_ws/native_scene_rviz.cpp)、[Gazebo GUI](../simulation/gazebo_scene_gui.cpp) | 新增empty请求；RViz按真实Widget标识scene/IR渲染目标，保存实际clock/显示开关 |
| [MultisceneDelivery](../ros_ws/sim_motion_multiscene_delivery.py) | S05合法空帧保留旧证据、S07 empty阶段与History地图失效核验；仅新视图Median window=1 |
| [旧Delivery](../ros_ws/sim_motion_delivery.py) | 提取native_config钩子供新视图覆盖；旧默认仍逐字读取同一静态配置 |
| [figure checker](../tests/sim_motion_multiscene_figures.py) | 原生像素/阶段时刻/独立IR viewport及History开关；允许实际Camera均匀背景，不以空图充非空 |
| [multiscene_world](../simulation/ufm_simulation/multiscene_world.py) | 仅生成的非零pitch IC省略会覆盖theta的gamma，第三方IC与零pitch行为保持 |
| [独立oracle](../tests/sim_motion_multiscene_oracle.py)、[live checker](../tests/sim_motion_multiscene_live.py) | 原始矩阵先验不变；独立标量Markley估计与实际四元数矩阵按1e-12比较 |
| [入口](../ros_ws/sim_motion_gate_run.py)、[引擎测试](../tests/test_sim_motion_multiscene_engine.py) | 冻结新核验源码；补姿态估计差异、合法视场离开与新视图配置反例 |

另更新中文实验记录、状态/架构/计划/接口及报告素材索引。没有修改同级研究仓库或安装依赖。

## 2. 复现与冻结

在仓根运行，Python固定且通过sim01环境入口。完整矩阵命令：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_motion_matrix_run.py
```

每个case新run、Master/rootfs和空地图；S08清理后把其实际run_id作为S09的previous-run-id。
S05/S07使用真实Camera并显式打开Gazebo/RViz窗口；其他核心例仍实采Camera，关闭GUI。
兼容例为旧estimated/T-14 fixture、旧静态原生检查、旧IR首采样ACK故障；不自动解锁或控制飞行。

final-source.json保存配置、实现、类型和测试全文，不生成额外Hash。
每例前后逐值检查同一冻结源码，并核对每个run中的源码副本。
S01旧cylinder/ground沿旧链验收；仅S02—S09计入box解析逐射线统计，固定零豁免/5e-6rad/0.011m。

## 3. 失败与修正

| 尝试 | 原始失败与处置 |
| --- | --- |
| [225511矩阵](../.runtime/runs/sim-motion-sw04c-20261029T225511378153/manifest.json) | S02极分解/Markley估计差约4.2e-11；改独立估计公式，原1e-12比较界保持 |
| [225812矩阵](../.runtime/runs/sim-motion-sw04c-20261029T225812177814/manifest.json) | S04源姿态theta实际0而非5；生成IC省略冲突gamma=0，保留失败，不换设计角度 |
| [230130矩阵](../.runtime/runs/sim-motion-sw04c-20261029T230130725103/manifest.json) | S05末帧合法零回波被过强断言拒绝；只读10帧逐射线完全匹配，修监督断言，不修改实采/几何 |
| [230547矩阵](../.runtime/runs/sim-motion-sw04c-20261029T230547076250/manifest.json) | S07实采IR返回而RViz末图仍黑，像素校验拒绝；只对新视图设1帧显示范围窗口 |

另有新增单测首次使用了不能区分两种旋转估计的合成矩阵，测试自身失败；改为可区分的
合法近正交矩阵后通过，没有改验收界。一次只读诊断因未加tests导入路径退出，补路径后执行。
以上失败均保留，修正后从S01新目录重跑，不把旧部分通过拼为最终矩阵。

SciPy采用Markley估计的依据见[1.10.1文档](https://docs.scipy.org/doc/scipy-1.10.1/reference/generated/scipy.spatial.transform.Rotation.from_matrix.html)；
theta/gamma加载顺序见[JSBSim 1.1.13源码](https://raw.githubusercontent.com/JSBSim-Team/jsbsim/v1.1.13/src/initialization/FGInitialCondition.cpp)；
RViz显示范围默认5帧见[Noetic ImageDisplay源码](https://raw.githubusercontent.com/ros-visualization/rviz/noetic-devel/src/rviz/default_plugin/image_display.cpp)。
显示修复不改变32FC1/raw时间、像素、业务输入或地图查询语义。

## 4. 实际验证

最终矩阵：[231006722634](../.runtime/runs/sim-motion-sw04c-20261029T231006722634/manifest.json)。
其423份源码文本在所有12例前后逐值保持，先前B收据及四次失败尝试未拼入结果。
实际9核心合计2,134个原始FDM样本、84组Bundle/占据/快照、121条公开查询；独立进程回放一致。

| 例 | 本轮最终真实结果 | 证据 |
| --- | --- | --- |
| S01 旧场景 | 1s/10组/14查询，旧地面/cylinder链保持；不宣称box解析覆盖 | [收据](../.runtime/runs/sim-motion-sw04c-20261029T231006722634/S01-receipt.json) |
| S02 北向 | 1s/10组/14查询、10帧逐射线及原始姿态通过 | [收据](../.runtime/runs/sim-motion-sw04c-20261029T231006722634/S02-receipt.json) |
| S03 南向 | 1s/10组/14查询、10帧逐射线及原始姿态通过 | [收据](../.runtime/runs/sim-motion-sw04c-20261029T231006722634/S03-receipt.json) |
| S04 倾斜 | 实际源初始[10,5,90]度；1s/10组/14查询及10帧逐射线通过 | [收据](../.runtime/runs/sim-motion-sw04c-20261029T231006722634/S04-receipt.json) |
| S05 遮挡 | 首采样选定射线先近后远，10帧严格解析；末帧0点/均匀IR合法，旧证据不刷新；六张原生阶段图 | [收据](../.runtime/runs/sim-motion-sw04c-20261029T231006722634/S05-receipt.json) |
| S06 空域 | 10次真实零点、均匀Camera、valid空图、13查询/unknown，无free | [收据](../.runtime/runs/sim-motion-sw04c-20261029T231006722634/S06-receipt.json) |
| S07 切换 | 400/900ms暂停切换；五空帧、旧证据TTL等号/+1ns、末帧1,233点返回、16查询及八张阶段图 | [收据](../.runtime/runs/sim-motion-sw04c-20261029T231006722634/S07-receipt.json) |
| S08 ACK故障 | step125缺Radar ACK；最后提交step124/496ms、4组/8查询；500ms raw存在但不成为Bundle | [收据](../.runtime/runs/sim-motion-sw04c-20261029T231006722634/S08-receipt.json) |
| S09 新身份 | 本轮实际S08 run清理后新run从revision0开始，10组/14查询；旧run/clock明确拒绝 | [收据](../.runtime/runs/sim-motion-sw04c-20261029T231006722634/S09-receipt.json) |
| C01/C02/C03 | 旧estimated/T-14、静态原生、IR首采样故障实际通过；C03业务clock96ms/0组，shutdown客户端255与daemon0分别保留 | [C01](../.runtime/runs/sim-motion-sw04c-20261029T231006722634/C01-estimated-receipt.json)、[C02](../.runtime/runs/sim-motion-sw04c-20261029T231006722634/C02-static-native-receipt.json)、[C03](../.runtime/runs/sim-motion-sw04c-20261029T231006722634/C03-first-ir-fault-receipt.json) |

S02—S09合计75帧/103,420点按独立解析命中集合、点序、角度与最近面核验，豁免0；
最大距离误差5.332124395351912e-7m，小于既有0.011m界。S08包括未提交业务的故障tick原始采样。
S01另按原raw/Doppler/杆臂/占据与查询链核验，不混入上述解析统计。

[原生素材/中文图注](../experiments/report_assets/sim-motion-multiscene-20261029/README.md)含14张阶段总图与
12张独立scene/IR viewport，共26个原生PNG，逐字节等于原run渲染输出，没有裁剪或拼接历史图。
History时Radar/IR真实开关均关闭、IR面板消失，地图变为历史unavailable；这不改变显式时间MapQuery。

预算实测：成功提交源时间8.496s；核心线格式72,617,940字节（≤144MiB）、
核心会话合计106.539s（≤1080s）、整套含启动/清理198.310s（≤1800s）、
产物405,119,985字节（含独立回放与共享构建，≤3GiB）。每例/流均在原界内。
外部日志仅定时观察并停止，不能解释为硬磁盘或RSS上限；终审/文档新增的少量元数据不含在上述冻结结束时数字。
后续[交付终审](../.runtime/runs/sim-motion-sw04c-20261029T231006722634/document-final-checks.json)另计软件检查及素材副本，
观察产物408,966,189字节，仍在3GiB内；16份文档/942个本地链接、10份Python语法及最终源码保持通过。

[最终轻量/协议报告](../.runtime/runs/sim-motion-sw04a-20261029T231404082927/report.json)：
新增7项，运动84/84，全仓903/903（60.291s）；77组真实Scene字节、36组旧公共往返与18个合成源转换通过。
25份旧定义相对B基线逐值不变；gate/Delivery两个旧文件为本轮显式装配/视图钩子改动，
不声称文件字节未变，其默认运行语义由上述实际兼容例验证。

[全部尝试终审](../.runtime/runs/sim-motion-sw04c-20261029T231006722634/handoff-audit.json)：
30次case运行含四次失败，364个自有PID无残留，11个ROS/Gazebo/PX4端口探针均空闲；
失败目录、原始数据及既有工作区修改全部保留。没有提交、推送或删除历史。

## 5. 未验证能力

只交付最长1秒自由动力学软件范围，没有自动解锁、起飞、航点、offboard或规划控制。
唯一状态来源明确为simulation ground_truth；不能作为PX4估计精度或受控飞行证据。
placeholder只把实际Radar命中变成占据，不能证明研究Radar–IR融合质量。
未接真实设备、真实DEM或占据融合；未做机载RSS/功耗/20ms或正式PERF-01。
完整阶段退出、长时间/高速/受控飞行仍独立验收；research继续fail-closed。
