# EXP-20261029-010 有界多场景运动回归设计

日期：2026-10-29；任务：SIM-MOTION-SW-04-DESIGN；主责任：simulation_engineer。
状态：已完成（设计/既有软件定向核验）；新增多场景运行未执行。
交付：[具体设计](../docs/SIM_MOTION_SW04_MULTISCENE_DESIGN_20261029.md)、ADR-043。

## 1. 目的与环境

在SW-03单profile交接之后，明确姿态/遮挡/真实无回波/故障恢复的独立判据与资源上界。
分支feature/engineering-initialization；HEAD=d96d4439da1007489c80e7f21b132abff16505bf。
Git既有大量修改/未跟踪文件全部保留，`.runtime/runs`忽略规则实际生效；未提交或推送。
运行前核对sys.executable为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，
全部Python调用经`bash ros_ws/sim01_env.sh ...`，未改Conda或系统环境。

## 2. 已有代码与本轮改动

已有SW-01固定合同/真实线格式、SW-02同FDM采样闸门、SW-03运动感知地图/公开回放与原生窗口。
沿入口追到IC生成、profile校验、SDF地面/障碍、Ray过滤/零点发布、ACK事务、SceneStream、
placeholder、M1更新/查询和交接核验器，形成12项源码事实表。
本轮仅新增方案/本记录，更新PROJECT_STATUS、README、架构/计划/决策/实验索引及SW-03后续链接。
未新增清单/schema/节点/插件/客户端，未修改业务代码、现有公共定义或运行入口。

方案固定9核心与3个受影响旧入口兼容用例；核心保持250步/1s上限，
先SW-04A独立输入/预期，再B装配/定向机制，最后C完整矩阵/窗口交接。
显式空碰撞域去除默认ground，切换仅在暂停且无pending事务边界；
独立box最近相交补足只验证下游投影自洽的覆盖缺口。

## 3. 实际验证

| 检查 | 实际结果 | 证据 |
| --- | --- | --- |
| Python入口 | 指定Conda解释器逐字一致 | 实际输出sys.executable |
| 既有运动定向/线格式 | 43/43通过，20组真实生成消息字节一致、17份旧定义逐值保持 | [report.json](../.runtime/runs/sim-motion-sw01-20261029T172401537740/report.json)、[targeted.log](../.runtime/runs/sim-motion-sw01-20261029T172401537740/targeted.log) |
| 既有场景单元 | 11/11通过 | 下述实际unittest命令，输出Ran 11 tests / OK；未另存日志 |
| 只读实现/解析探针 | 13/13通过 | [probes.json](../.runtime/runs/sim-motion-sw04-design-20261029T1725/probes.json) |
| 文档相对路径/设计一致性 | 9个改动文档的698处相对链接、9核心/3兼容计数及预算/故障时间关系通过；git diff --check通过 | [最终检查](../.runtime/runs/sim-motion-sw04-design-20261029T1725/document-final-checks.json)，不提高仿真状态 |

实际测试命令：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_motion_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p test_sensor_scene.py -v
```

13探针为：objects为空仍有ground；新图unavailable；10份有效空帧revision10/unknown；
新空帧header=900ms而cell证据400ms；900ms占据与900ms+1ns过期；早于最新图查询拒绝；
改固定v1初速拒绝；三个航向/倾斜旋转；偶数Ray网格无正中射线；近/远box解析相交。
初始h48/v12近/远距离7.201029212956173/11.201600997931823m。
这些使用独立矩阵/解析计算及已有纯软件空点输入，没有运行新FDM轨迹或Gazebo射线，
不计为真实无回波场景验收，也不把实际输出反填计划预期。

## 4. 未验证与风险

未启动ROS/Gazebo/PX4/JSBSim或新窗口，未实施9场景、几何切换屏障或新schema。
未重跑全仓；862/862仅为上一轮SW-03结果，本轮为54项既有定向和13项探针。
新倾斜自由动力学能否跑满1s、引擎与几何oracle的误差/边界比例、切换后的Camera缓冲、
空图公共回放及9场景预算适用性留待后续；本次设计不关闭这些能力。
真实设备/模型质量/DEM融合/机载RSS/正式PERF-01/完整阶段验收保持未关闭，research继续fail-closed。

## 5. 恢复与下一步

本轮无运行服务需要回滚，所有生成证据位于新的被忽略目录，历史实验未覆盖。
文档以新增记录/精确补丁维护，不还原既有脏工作区。
下一项SIM-MOTION-SW-04A：独立测试清单、有界校验、冻结预期和实际消息线格式离线核验，
再推进新引擎装配，不恢复因真实输入缺失而暂缓的研究任务。
