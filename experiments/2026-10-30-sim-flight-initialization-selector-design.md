# 初始化selector有效槽位与迁移设计审查

编号：EXP-20261030-012；日期：2026-10-30；任务：SIM-FLIGHT-INIT-SELECTOR-DESIGN-01。
主责任：simulation_engineer；状态：已完成（具体设计/只读证据核查）。
交付：[字段/索引、来源、关联、schema、98查询、预算和S01—24预期](../docs/SIM_FLIGHT_INIT_SELECTOR_DESIGN_20261030.md)。

## 1. 范围与环境

按用户“继续”推进已登记的下一设计项，未回到真实数据/研究质量等暂缓任务。
已读取根规范/状态/架构、涉及目录规则、接口/坐标、原准备设计/合同/实际失败及ADR-044。
核对Git/忽略和真实生产消费链，分支feature/engineering-initialization，
HEAD=d96d4439da1007489c80e7f21b132abff16505bf；大量既有dirty/未跟踪build等全部保留。
Python经bash ros_ws/sim01_env.sh核对为/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python。
本轮仅写设计/实验与必要索引，未修改源码/配置/fixture，未构建或启动FDM/PX4/ROS/daemon查询。

## 2. 方法与命令

沿vehicle_imu → VotedSensorsUpdate::sensorsPoll → sensors_status_imu →
EKF2Selector::UpdateErrorScores/PublishEstimatorSelectorStatus追踪，再核原准备query/parser/evaluator与tests消费。
保存6份原生源全文/24项路径行号字面量，重读历史正常run，不重新运行原失败场景。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -c 'import sys; print(sys.executable)'
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B /tmp/ufm_selector_design_audit.py
```

临时审计脚本调用既有source_snapshot、实际wire审计与原parse_native，并执行：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_sim_flight*.py' -v
```

该测试由审计子进程实际运行、输出保存flight-targeted.log；没有把阶段runtime runner作为轻量测试启动。
初次临时审计把fixture外封套与raw直接比较而断言失败；读取其raw字段后新目录审计通过。
[初次目录](../.runtime/runs/flight-init-selector-design01-20261030T121639575115/source-facts.json)保留；
这是审计脚本读取错误，不是生产缺陷或新仿真失败，仓库fixture/原raw未改。

## 3. 实际结果与具体设计

[本轮报告](../.runtime/runs/flight-init-selector-design01-20261030T121653053407/report.json)、
[历史证据重读](../.runtime/runs/flight-init-selector-design01-20261030T121653053407/retained-evidence-audit.json)、
[24项源事实](../.runtime/runs/flight-init-selector-design01-20261030T121653053407/source-facts.json)。

| 对象 | 实际结果/含义 |
| --- | --- |
| 两种槽位 | estimator数组9，available是已见索引高水位，范围内可能历史空洞；IMU数组4，按vehicle_imu槽分别记录gyro/accel设备，不等同primary实例号 |
| 源分支与身份缺口 | IMU设备ID=0分支写nan；selector不发布完整设备表或所消费IMU时间，额外表观测不能证明同一消息/原子快照 |
| 原第30条 | combined/relative各6—8，gyro/accel各3，共8处准确nan；fixture.raw与历史原文件逐值相同，原codec仍probe_native_float |
| 历史实际流 | 500 HIL_SENSOR/1 GPS、500 Run/2s、78真实全零执行器、30 raw/29合法事件独立重读通过；完整准备失败不变 |
| 既有测试与保护 | 飞行134/134通过；476份源码/配置与前轮快照逐文本相同，没有新codec或配置实现 |

设计拟新增独立selector fixture/recording/query/observation v1；原物理header/step/terminal按原合同作为具名同run文件组合，
不改C++宿主、原84封套/默认入口或公共协议。增加每组前后两次sensors_status_imu，固定7+7×13=98；
query_records硬上界128及400ms组期限、10s/2500步与所有原文件/墙钟界保持，不因增加查询自动放宽。
缺失按field/index/token/reason一一对应；9槽范围外准确nan与healthy=false精确配对，范围内nan仍拒绝；
四槽误差准确nan仅显式不可用，主设备关联/有限误差仍须满足，非主设备缺失不会被当作整机健康证明。
前后独立表关联结果始终exact_source_message_verified=false、消费时间null；选中槽不明/不健康/缺失或关联不一致不就绪。
交付S01—24独立预期分组和先离线再实际两个工作包；本轮没有执行这些新规则或新增24项生产测试。

## 4. 修改、风险与交接

新增设计说明和本实验；同步PROJECT_STATUS、README、架构/数据/传感器/坐标、开发计划/ADR/实验索引，
并在原准备交付末尾追加后续链接。最终逐文件/源不变/本地链接检查见
[final-audit.json](../.runtime/runs/flight-init-selector-design01-20261030T121653053407/final-audit.json)。
审计脚本位于/tmp，源/结果快照仅写被忽略.runtime，不改历史产物。

下一项INIT-SELECTOR-SW-01只做独立私有离线合同/先行预期/纯判定与兼容测试；
再INIT-SELECTOR-SW-02单独装配98项并验证一次新规则准备，当前尚未实施或验收。
新增14次查询能否在400ms内完成、两个末检查点实际姿态/设备/输出就绪均未验证；到界不就绪如实失败。
本轮未重跑全仓，1037/1037属于前轮；未新验消息线格式、真实设备、模型质量、RSS或正式PERF。
严格周期绑定/非零属性因果、公共v2/长采样、命令/离地/飞行仍未通过；控制false/绑定unverified。
无依赖安装、Hash、研究仓修改、历史删除、自动提交或推送，全部既有改动保留。
