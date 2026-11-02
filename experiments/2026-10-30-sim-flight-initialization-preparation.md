# 私有准备宿主与实际失败/停止记录

编号：EXP-20261030-011；日期：2026-10-30；任务：SIM-FLIGHT-INIT-SW-02。
主责任：simulation_engineer；状态：已完成（软件/部分实际证据/故障兼容子范围）；完整准备未通过。
交付：[十文件清单、预算、结果和下一任务](../docs/SIM_FLIGHT_INIT_SW02_PREPARATION_20261030.md)。

## 1. 范围与环境

用户继续授权SW-02，同IC/单FDM/原传感器、最多10s/2500步私有无控制准备；不改旧入口或PX4核心。
已读根规范/状态/架构、simulation/ros_ws/tests/docs/experiments规则与接口/设计/合同，
核对dirty/忽略规则和真实链，全部既有改动/未跟踪build等保留。
Python核对/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python；入口sim01_env，构建仅新.runtime/ros目录。
分支feature/engineering-initialization，HEAD=d96d4439da1007489c80e7f21b132abff16505bf。
没有新ROS/Gazebo/RViz、模式/arm/manual/参数写、训练/完整模型推理、DEM/占据融合或正式PERF。

## 2. 执行和失败历史

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_initialization_run.py --build-only
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_sim_flight_initialization_runtime.py' -v
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_initialization_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_initialization_run.py --case disconnect
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_initialization_run.py --case transaction-timeout
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_flight_initialization_stage.py
```

先隔离构建/C++离线控制拒绝和5项包装测试通过；初次实际命令在端口核查被沙箱拒绝，无子进程启动。
获本机回环执行许可后，新normal到第500步/2s，第30次selector原文含nan被严格拒绝，停止并保留原文。
未把它改成null/0或截数组继续，也未重跑同一正常场景。
disconnect实际通过；初次timeout实际已在Run前停止，但审计器对.5000000000000003作精确相等误判。
先复现该错误，修正到原1ns界并新增反例，再以新timeout run验证通过；原失败保留。
加入第30条真实原文的严格拒绝回归，最终7项新增，执行独立实际字节/物理审计与旧实际入口/全仓。

## 3. 实际结果

[阶段报告](../.runtime/runs/flight-init-sw02-stage-20261030T120415015778/report.json)passed=false、
runtime_accepted=false；software_regression_and_fault_checks_passed=true，不把“软件检查通过”写成完整准备通过。

| 证据 | 结果 |
| --- | --- |
| [新normal](../.runtime/runs/flight-init-sw02-normal-20261030T115944038112/manifest.json) | 500个HIL_SENSOR/1 GPS、500 Run/2s；78实际全零执行器/四属性请求读回0，首423步，原戳比本步HIL早4000us；30 raw/29合法事件，第30次selector含8个非有限槽位而停止 |
| [物理独立重读](../.runtime/runs/flight-init-sw02-stage-20261030T120415015778/normal-physics-audit.json) | 第33/33/91步三支柱首次WOW；第500步前连续250步满足输入门，末AGL≈.310829m/pitch≈8.422156°。未到两个必需末检查点，整体静稳/初始化/输出门仍未通过 |
| [disconnect](../.runtime/runs/flight-init-sw02-disconnect-20261030T120111523545/manifest.json) | 126原HIL、125 Run、18合法查询；peer_closed，末条未Run/时间保持约.5s，独立审计通过 |
| [timeout最终](../.runtime/runs/flight-init-sw02-transaction-timeout-20261030T120254975810/manifest.json) | 第126步注入1.01s，监督/宿主均停；126 raw/125 Run、transaction_timeout；超时末条只存失败raw，不冒充合法step |
| 回归/兼容 | 新7项、飞行134/运动84/全仓1037项通过；旧实际normal/disconnect通过，77场景字节/36公共往返/18合成源转换用实际genpy，25定义/7入口不变 |

正常第30条selector数组combined/relative索引6—8各nan、gyro/accel error索引3各nan；
primary=1/available=6仅是被拒绝原文，不作有效primary/姿态准入。本轮未到该组flags/姿态查询。
全部零执行器、既有原戳/读回和局部静稳不代表严格周期绑定、完整EKF就绪或受控飞行。

## 4. 文件、保护和交接

新增10个源码/fixture和本实验/交付说明，修改必要管理/架构/接口索引；原466源码、旧宿主/入口和研究仓不改。
新normal与fault分属不同本轮快照，后续变化仅清理统计/timeout审计及tests增强，C++/query/合同/输入保持；
阶段报告列出差异，不冒充同一最终源码完整运行矩阵。最终476源码全仓检查通过后只改文档。
清理只针对本次PID/进程组并核端口，全部失败/原文保留；退出不视为disarmed/着陆。
最终源码/独立输入/公共兼容/本轮所有自有PID与文档链接核对见同阶段目录final-audit.json。

下一项INIT-SELECTOR-DESIGN-01仅审查selector有效槽位/来源/身份、显式不可用与独立反例、查询/schema迁移及预算，
不直接放宽合同或重跑正常准备；尤其不能用estimator实例范围代替IMU设备槽位身份。
完整84采集/10s准备与两个末检查点、严格绑定/非零属性因果、公共v2/长采样和命令/离地仍未通过。
没有安装依赖、计算Hash、改同级研究仓或提交/推送；真实数据/研究质量按要求继续暂缓。
