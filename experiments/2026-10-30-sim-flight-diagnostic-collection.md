# 三态uORB诊断实施与NaN拒绝

编号：EXP-20261030-006；日期：2026-10-30；任务：SIM-FLIGHT-SW-02C。
主责任：simulation_engineer；状态：进行中（软件已交付，实际21次采集未通过）。
详细[合同/文件清单/失败证据/下一项](../docs/SIM_FLIGHT_SW02C_DIAGNOSTICS_20261030.md)。

## 1. 目的与环境

用户“继续”授权实施DIAG-DESIGN-03，保留旧strict，显式独立诊断三态，不把空块填0或当有效快照。
先读取根规范/项目状态/架构、目录规则与接口，核对dirty、忽略规则和真实生产消费链。
分支feature/engineering-initialization，HEAD=d96d4439da1007489c80e7f21b132abff16505bf。
Python实际核对/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python，全程sim01_env入口。
构建仅在.runtime/ros隔离目录；原1s/250步、白名单及墙钟/资源界保持，不发任何控制或参数写。
没有安装依赖、计算Hash、改第三方原源/同级研究仓或自动提交/推送；既有dirty与历史产物全部保留。

## 2. 独立预期与步骤

先新增18组字面量预期/六空实例实际原文，冻结[oracle](../.runtime/runs/sim-flight-sw02c-oracle-20261030T093048549326/independent-expectations.json)
与源码/git，再实现独立合同、有界记录器和--uorb-diagnostics分支；审计确认预期未变。
新20项涵盖C01—18、写后期限/预启动期限及CLI互斥，初次69项飞行测试通过。
阶段runner最初与ROS模块同名，旧测试导入被遮蔽；[第一次前检](../.runtime/runs/sim-flight-sw02c-stage-20261030T093502242784/flight-targeted.log)
失败后改新增文件名为sim_flight_diagnostic_stage.py，未启动PX4或改旧测试，日志保留。
随后整套新run运行一次诊断，并完成旧normal/disconnect、真实genpy与全仓轻量回归。

实际入口：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_sim_flight*.py' -v
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_flight_diagnostic_stage.py --full
```

第二条由stage实际调用ros_ws/sim_flight_diagnostic_run.py --uorb-diagnostics和旧stage，不另开重复诊断。

## 3. 实际结果

| 范围 | 预期 | 实际 |
| --- | --- | --- |
| 完整采集 | 21个有序有界事件，三态不提升状态/控制许可 | [实际诊断](../.runtime/runs/sim-flight-sw02c-diagnostics-20261030T093534728429/manifest.json)11次查询/10合法事件，第11次nan严格拒绝，采集未完成 |
| 125检查点 | 完整或明确空块可在新诊断继续，坏输出停 | 九topic均完成：2 payload、6 unavailable、1 not_published，组墙钟39117822ns |
| 250检查点 | 仍保留有限数值拒绝规则 | IMU完整；estimator_status六组vel/pos ratio各nan，12处文本非有限；不编码第11事件、不继续余下10次 |
| 流/原文审计 | 不完整流必须拒绝，不填补事件 | [关闭审计](../.runtime/runs/sim-flight-sw02c-stage-20261030T093533859011/closeout-audit.json)：10条严格重读/原文和宿主时间逐项一致，部分流仍拒绝；原strict仍拒绝旧六空实例 |
| 同FDM/wire | 250步不代表21查询通过 | [副本独立审计](../.runtime/runs/sim-flight-sw02c-stage-20261030T093533859011/independent-host-audit.json)：250 Run/1s、250 HIL_SENSOR、RX2/执行器0包、终止窗口完成 |
| 回归 | 原合同/入口及真实消息保持 | 飞行69/69、运动84/84、全仓972/972、77场景字节/36公共往返/18合成源转换通过；整体阶段报告仍false |
| 保护与清理 | 不改原源/旧协议或残留会话 | 451冻结源码，原445仅改诊断入口、新增6文件；25定义/7入口、8原生msg/30桥接原源保持；17自有PID退出/端口free、无强制清理 |

[阶段报告](../.runtime/runs/sim-flight-sw02c-stage-20261030T093533859011/report.json)明确
diagnostic_collection_complete=false、payload_complete=false、compatibility_passed=true，
旧SW-02B runtime仍未接受，绑定unverified/控制门false。
查询文件60390字节是实际产物大小，组墙钟只有单次记录，非RSS/正式性能。
独立wire检查只在新stage副本写recording.jsonl，失败run的四份原输入未回写或覆盖。

## 4. 新发现、限制与下一步

125步模式原文为timestamp24000us、flag_armed=False、manual=True、rates/attitude=False，
该旧样本不能外推整个运行或控制准入。未取得selected姿态载荷，不能由输入IMU代替EKF对齐。
第11次状态已出现正文，但NaN使整个事件不合法，禁止部分字段入准入、静默归零或作为空块继续。
源码get_innovation_test_status主动先设vel/pos=NAN，再按GPS/EV等辅助源更新；
这说明原生不可用语义有待合同设计，不能仅凭nan声称数值崩溃，也不能据源码猜本run唯一原因。
两份相关原源冻结在本stage，不改飞控或研究代码。

本轮没有为实际nan放宽合同或重复同失败运行；21次完整采集/三参数及后续姿态/输出链仍未验收。
新schema流成功分支的实际完整21事件重读尚未验证，离线完整合成流已验证；二者分别报告。
直接下一项DIAG-DESIGN-04只读核对原生非有限诊断字段语义，提出显式隔离/继续或停止的具体方案，
保留SW-02B/C失败和原预算，不自动进入v2/长窗/命令/训练/完整模型/真实DEM或正式PERF。
所有历史产物保留，恢复采用新run；research及在线训练监督隔离边界保持。
