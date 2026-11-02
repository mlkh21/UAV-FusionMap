# EXP-20261029-014：受控短窗与同FDM具体设计审查

日期：2026-10-29；主责任：simulation_engineer；状态：已完成（设计与只读核验）。
任务：SIM-FLIGHT-DESIGN-01；依据：SW-04C交付、用户“继续”及PROJECT_STATUS下一任务。
类型：源码链审计、纯解析/算例、既有离线合同/真实消息往返；不是新飞行或控制运行。

## 1. 环境与保护边界

分支feature/engineering-initialization，HEAD d96d4439da1007489c80e7f21b132abff16505bf。
大量既有修改/未跟踪文件保留；本轮只新增/更新中文设计、实验及索引文档。
核对Python为/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python，命令统一sim01_env.sh。
未改研究仓库、.runtime/src第三方树、Conda、旧profile、消息、宿主或运行节点。
未启动FDM/PX4/ROS/Gazebo，未发heartbeat、arm、manual、起飞、参数写或其他控制命令。
没有安装依赖、生成额外Hash、删除历史、提交或推送。

## 2. 已完成的审查与结论

[具体方案](../docs/SIM_FLIGHT_DESIGN_20261029.md)登记19项源码事实并沿真实链核对：
PX4模拟器输出→HIL_ACTUATOR_CONTROLS→bridge poll/接收→index/scale→JSBSim属性→同FDM Run，
另追踪MANUAL_CONTROL→输入选择→PX4已有STABILIZED控制→静态mixer。

主要差距是执行器回包未绑定源时间/身份/新鲜度，poll超时可能使用旧值继续推进；
FDM Run结果也未由现有void Run导出。当前“有执行器连接”不能当严格闭环控制验收。
Rascal使用2/5/7/4四路而非通用0/1/2/3，scale分别−1/−1/−1/+1。
JSBSim v1 altitude是AGL；初始elevation419.2m与8m运动锚点必须分别说明，不是8m MSL。
参考[对应JSBSim源码](https://raw.githubusercontent.com/JSBSim-Team/jsbsim/v1.1.13/src/initialization/FGInitialCondition.cpp)。
旧Python/C++/宿主多处固定250步/8m锚点，不能只放大时长或把地面0.5m塞入旧门禁。

交付选择为：先离线私有合同，再1秒只读HIL诊断；其后另做v2/新ground profile的无命令准备，
最后才准入冻结STABILIZED脚本。新profile拟40s，前30s源记录全保留，
公共raw固定30.1—40s最多100组；没有隐藏预热/改戳或把准备期无raw解释为valid空观测。
新v2复用生成类型但严格分codec/端点，旧v1不放宽；本轮均未实现。
正常arm/模式确认、实际输入/执行器/离地、停止与disarm事实分开判定，不能只看ACK。

## 3. 实际验证

实际命令：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -c 'import sys; print(sys.executable)'
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_motion_multiscene_run.py
```

[本轮离线报告](../.runtime/runs/sim-motion-sw04a-20261029T233639643686/report.json)：
84/84既有运动定向（1.192s）、77组实际genpy字节、36组旧公共消息往返、18个合成源转换通过；
25份旧定义与7个旧配置/入口相对本轮开始快照逐值不变。无新测试或运行算法，本轮未重跑全仓。
903/903全仓仍引用SW-04C上一轮事实，不冒充本轮结果。

[15项独立核验](../.runtime/runs/flight-design-20261029T233844868507/report.json)先保存独立字面量，
再解析实际IC/通道/mixer与源码、调用旧严格校验器：

| 核验 | 实际结果 |
| --- | --- |
| 原IC AGL/elevation | .5m、419.2m及M单位一致 |
| 4路index/scale/property | 与独立2/5/7/4表一致 |
| 非对称16路算例 | rudder+.25、aileron−.3、elevator+.2、throttle.6，非控制发送 |
| mixer槽位 | 两个空槽、后续7个混控槽，非通用通道假设 |
| 旧profile | 250步/锚点8m保留，10000步改写被拒绝 |
| 旧源/native边界 | step251拒绝；原生250步/z>.5静态断言保持 |
| poll→施加→Run顺序及void接口 | 源码检查一致，不作为实际执行器时间绑定证明 |
| manual pitch量纲 | x=−178与45°上限算例为+8.01° |
| 拟议采样表算例 | 7525—10000步每25步，首30.1s/末40s/100组；未执行新profile |
| 旧协议/生产源码 | 25份定义、423份SW-04C冻结源码逐值保持 |

19份源码全文快照及独立预期保存在同核验目录；新设计运行阈值只是提案，不回写历史预期。
按本机真实路径修正了最初搜索使用的新版PX4文件名，没有修改或替换版本。
另有[文档终审](../.runtime/runs/flight-design-20261029T233844868507/document-final-checks.json)：
11份文档、848个本地链接与19个源码行号锚点通过；423份生产源码、19份只读证据源及25份旧定义保持。

## 4. 未验证与下一任务

未验证：实际HIL回包与当前周期对应关系、长预热就绪、控制指令/实际arm与模式、
地面响应、离地、姿态稳定/持续飞行、新v2采样、资源和新故障矩阵。
本轮不以旧原生图或源码推断这些能力；research继续fail-closed，真实质量、DEM与PERF未关闭。

直接下一项SIM-FLIGHT-SW-01，仅离线IC/执行器收据合同、冻结fixture/独立oracle/限额测试及旧线格式兼容。
没有FDM/ROS/控制客户端或公共消息变更；SW-02/03/04按具体方案依赖依次推进，不跨步发控制。
