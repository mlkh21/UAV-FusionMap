# EXP-20261029-013：多场景最终矩阵与原生交接

日期：2026-10-29；主责任：tester；状态：已完成（SIM-MOTION-SW-04C软件范围）。
类型：实际PX4/JSBSim/Gazebo/ROS、原生渲染、公开回放、单元/合同与轻量全仓。
依据：[具体设计及修订](../docs/SIM_MOTION_SW04_MULTISCENE_DESIGN_20261029.md)、ADR-043。
实现文件清单、逐例证据及限制见[交付说明](../docs/SIM_MOTION_SW04C_DELIVERY_20261029.md)。

## 1. 目的、环境与独立预期

在同一最终源码上完成9核心/3兼容，补足B未覆盖的航向、实际倾斜、遮挡、显式恢复与原生阶段图。
分支feature/engineering-initialization，HEAD d96d4439da1007489c80e7f21b132abff16505bf；
大量既有修改/未跟踪文件原位保留，无提交/推送。开始与最终源码清单见矩阵git-state/final-source.json。
Python固定/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python，运行前核对sys.executable；
全部命令由sim01_env.sh装配。本机已有Noetic/Gazebo11/Qt/Ogre/Mesa，源JSBSim为1.1.13。
构建仅本仓.runtime/sim-motion-build、sensor-scene-build及既有.runtime/ros生成类型。

在实采前保存独立清单、几何/IC/查询/预算与严格零豁免预期，保存423份实现/配置/测试全文；
每例前后及其源码副本逐值比较。固定每case≤250步/1秒、原启动/采样/事务期限。
S01是旧cylinder/地面兼容，不列为box解析案例；S02—S09独立最近相交逐射线核验。

## 2. 实际命令与结果

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_motion_matrix_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_motion_multiscene_run.py --full
```

最终[矩阵231006722634](../.runtime/runs/sim-motion-sw04c-20261029T231006722634/manifest.json)：
9核心/3兼容全部通过，非B部分结果拼接。9核心实际2,134个原始FDM样本、84组业务输出、
121条公开查询及独立占据回放一致。S02—S09的75帧/103,420点严格解析，距离最大误差约5.33e-7m，豁免0。

S04原始初始姿态满足[10,5,90]度；S05首帧真实遮挡、末帧视场离开后0点/均匀IR合法且不刷新旧cell。
S06从revision0/unavailable到10帧valid空图、unknown/no_observation；未制造free。
S07两次暂停切换读回一致且不推进时间，500—900ms五空帧保留400ms证据，
900ms等TTL仍occupied、+1ns stale，末帧1,233点返回；共16查询及before/empty/after/history八图。
S08失败tick125不提交，业务时间最后496ms/4组；S09全新身份拒绝实际S08的旧run/clock，从空地图恢复10组。
三兼容例均实际执行：estimated/T-14 fixture、旧静态原生、旧IR首采样故障。
最后一例clock96ms/0组，PX4 shutdown客户端255与daemon0/正常关机标记分别保存，未混淆退出码。

原生图为S05六张、S07八张；另12个scene/IR viewport，
[26张素材与中文图注](report_assets/sim-motion-multiscene-20261029/README.md)逐字节对原run。
像素、实际clock/开关及History地图失效通过，并人工查看原生图；没有桌面其他窗口截图或历史图拼接。

最终[软件报告231404082927](../.runtime/runs/sim-motion-sw04a-20261029T231404082927/report.json)：
新增7项，运动84/84，全仓903/903（60.291s），77个Scene真实生成消息字节、
36组旧公共消息往返和18个合成源转换通过。25份旧定义保持；两个旧运行文件显式增量，默认入口有实际兼容证据。

## 3. 原失败、修正与恢复

完整尝试依次在S02、S04、S05、S07失败停止，见[全部尝试终审](../.runtime/runs/sim-motion-sw04c-20261029T231006722634/handoff-audit.json)。
具体失败目录/依据/文件改动列于交付说明，原失败没有改判、覆盖或删除。
S02修测试侧旋转估计，1e-9输入与1e-12比较界保持；S04只省略生成IC的冲突gamma项，不改第三方IC或冻结角度。
S05失败断言与独立10帧解析相矛盾，改为合法空观测保留旧证据；实采不改。
S07实际IR已返回，但RViz默认5帧中值范围留下黑图，像素验收正确拒绝；新视图Median window=1后新矩阵通过。
后两项不改公共raw时间/32FC1或地图语义。每次修正后从S01新身份重跑。
原生工具另补empty阶段、owned target角色收据和History地图检查；矩阵预算包含独立回放目录。

新增单测曾因选择的矩阵不足以区分两种旋转估计而失败，后更换为合法可区分算例；
一次诊断未加tests导入路径失败，补路径后只读执行。最终端口审计第一次被默认沙箱禁止socket，
后在已授权本机权限下重做通过；未发生自动审批拒绝，未因权限绕过或改写验收结果。

## 4. 预算、清理与限制

最终源时间8.496s；核心线格式72,617,940B/≤144MiB，核心会话106.539s/≤1080s，
整套198.310s/≤1800s，结束时产物405,119,985B/≤3GiB（含构建及独立回放），每例/流均有界。
全部五轮30次case观察产物约1.060GB，另有后续审计/文档/素材；不把观察值当硬磁盘或RSS上限。
跨全部尝试364个自有PID无残留，11个端口探针均空闲；仅停止本轮自有进程。

不新增飞行控制、真实DEM、占据融合、研究推理、训练或正式PERF。
当前最长1秒自由动力学不证明受控/持续/高速飞行；状态为ground_truth，感知为placeholder。
完整阶段退出及真实输入/机载资源仍未关闭，研究质量继续暂缓且research fail-closed。
下一项仅做受控飞行联动的具体设计审查，不自动启动解锁/起飞或扩展运行窗口。
