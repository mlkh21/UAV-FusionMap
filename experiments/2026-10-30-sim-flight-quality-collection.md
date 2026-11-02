# 条件质量隔离与21次实际采集

编号：EXP-20261030-008；日期：2026-10-30；任务：SIM-FLIGHT-SW-02D。
主责任：simulation_engineer；状态：已完成（私有隔离/有界采集及回归子范围）。
交付：[合同、文件清单、实际证据与边界](../docs/SIM_FLIGHT_SW02D_QUALITY_20261030.md)。

## 1. 目的与环境

用户继续授权DIAG-DESIGN-04的具体实施：独立私有v2/显式模式，严格两字段条件隔离，不改旧两个合同或失败。
先读根规范/项目状态/架构、目录规则/接口，核对dirty、忽略规则与真实生产消费链。
分支feature/engineering-initialization，HEAD=d96d4439da1007489c80e7f21b132abff16505bf。
Python实际核对/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python，全程sim01_env入口，构建仅.runtime/ros隔离目录。
原21次白名单/1s/250步与墙钟界保持，不发控制/参数写，不安装依赖/Hash或修改研究仓，保留全部既有改动。

## 2. 先行预期及实际运行

先保存20组独立预期、16组合与手工字段投影，并机械提取已审计旧原文/关键源片段/消息布局到
[oracle](../.runtime/runs/sim-flight-sw02d-oracle-20261030T100529339136/sim_flight_quality_cases.json)，再实现v2/记录器/测试。
关键源与布局在构建前核对，源码变化拒绝假定旧条件仍有效；未引入Hash，旧原文不作在线状态输入。
92项定向先通过，再运行一次完整stage；本轮没有失败后改阈值或扩大两字段白名单。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_sim_flight*.py' -v
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_flight_quality_stage.py --full
```

第二条实际调用显式--uorb-quality-diagnostics、独立重读和旧stage两用例及真实消息/轻量回归。

## 3. 实际结果

| 范围 | 实际结果 | 限制 |
| --- | --- | --- |
| [新采集](../.runtime/runs/sim-flight-sw02d-quality-20261030T101131381746/manifest.json) | 原计划21查询/21合法事件，三个参数1033/0/0、250 Run/1s，完整采集通过 | body_complete=false、payload_complete=false，控制门false |
| 条件隔离 | 250步六status实例各两nan，12条明确原因/原token/null；四源位条件及二进制标注核对通过 | 不把NaN当合法数值、整条有效状态或空正文；旧两个codec仍拒绝旧原文 |
| 原生链路 | IMU可读；六flags样本tilt/yaw=False、baro=True、gps=False；selected姿态无载荷，wire执行器0包 | 样本时间不同，不能据此判唯一根因、推断更长窗必定恢复或开放控制 |
| [独立重读](../.runtime/runs/sim-flight-sw02d-stage-20261030T101130232351/acquisition-result.json) | 21 JSONL/原文argv/输出/返回码、宿主HIL/FDM/检查点、三组期限/summary逐项一致 | 只验证本run采集，不回填旧SW-02B/C验收 |
| [回归](../.runtime/runs/sim-flight-sw02d-stage-20261030T101130232351/report.json) | 新23项+旧69项飞行共92、运动84、全仓995项通过，旧normal/disconnect/实际genpy兼容通过 | 不代表正式性能/真实模型/飞行验收 |
| [保护/关闭](../.runtime/runs/sim-flight-sw02d-stage-20261030T101130232351/closeout-audit.json) | 458份冻结源码，原451仅改诊断runner、新增7文件；旧25定义/7入口、8msg/4语义源/30桥接源保持；27自有PID退出/端口free，无强制清理 | 不删除历史、不清理其他会话，未提交/推送 |

三组墙钟37416114/45050790/13511114ns，末组结束距initial约2.720s；原文/布局/源基线/报告等共446431字节，
JSONL79062字节。这些是单次限额核对，不是RSS、时延分布、实时倍率或正式PERF。
Query状态8 payload/2 not_published/10无载荷/1质量不可用；实例14完整/30无载荷/6质量不可用。
旧消息检查仍为77场景字节/36公共往返/18合成源转换，不用mock替代实际线格式。
测试transport替身仅用于期限/停止验证，真实21次daemon调用另有原文/进程身份证据。

## 4. 交接与未验证

新模式采集已完成；旧B/C失败保留，载荷完整/姿态与执行器就绪未通过，控制门继续关闭。
没有启公共Scene v2、长准备/新IC/命令或新ROS/Gazebo图，没有真实DEM/占据融合、训练/完整模型/正式PERF。
本次直接flags样本与PublishAttitude/attitude_valid源码共同将缺口收敛到初始化/姿态准入段，
仍未取得低通/方差收敛过程与有效primary关联，不能按静态依赖图确定唯一原因。
下一项SIM-FLIGHT-INIT-DESIGN-01先审查同FDM/IMU/地面IC与无控制准备条件，
交具体窗口/停止/证据及SW-03衔接方案，不重复已完成采集或自动扩窗/控制。
全部原文和既有dirty保留；后续新run恢复，清理不作为着陆/disarmed证据。
