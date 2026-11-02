# selector实际准备与原生微秒截断停止

编号：EXP-20261030-014；日期：2026-10-30；任务：SIM-FLIGHT-INIT-SELECTOR-SW-02。
主责任：simulation_engineer；状态：已完成（装配/部分证据/故障兼容软件子范围），完整准备未通过。
交付：[五新增/一修改、结果、时间归因与下一任务](../docs/SIM_FLIGHT_INIT_SELECTOR_SW02_PREPARATION_20261030.md)。

## 1. 环境与实施

用户“继续”确认98项实际装配/一次新规则准备与故障交接；先读根/模块规范、状态/架构/接口/合同与生产消费链。
分支feature/engineering-initialization，HEAD=d96d4439da1007489c80e7f21b132abff16505bf；既有dirty/未跟踪build全部保留。
Python经sim01_env核对/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python，构建仅新.runtime/ros目录。
原同FDM/IC、模型/噪声/阈值、10s/2500步/400ms组界不改；无控制、研究仓读写、训练/推理、DEM或正式PERF。

接线前先复现并修正两处私有离线组合边界：物理terminal先于末组查询、PX4固定rootfs/etc运行资源链接。
前者只允许成功完成2500次物理后最后一组，后者只跳过固定资源目标，原时间/记录链接限制保留。
新增98查询/runner、独立wire/物理/原文审计和阶段工具；原C++宿主/84入口不改。

## 2. 实际命令与权限

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_sim_flight_initialization_selector_runtime.py' -v
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_initialization_selector_run.py --build-only
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_initialization_selector_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_initialization_selector_run.py --case disconnect
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_initialization_selector_run.py --case transaction-timeout
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_flight_initialization_selector_stage.py --normal .runtime/runs/flight-init-selector-sw02-normal-20261030T133458680660 --disconnect .runtime/runs/flight-init-selector-sw02-disconnect-20261030T133633428328 --transaction-timeout .runtime/runs/flight-init-selector-sw02-transaction-timeout-20261030T133730530101
```

build-only位于[133300627800](../.runtime/runs/flight-init-selector-sw02-normal-20261030T133300627800/manifest.json)，无实际场景。
实际前单独本机socket预检在沙箱报Operation not permitted；没有因此启动一个失败正常场景。
本机回环执行许可获准后才执行三例和旧实际兼容；未改系统网络/环境，不是自动审批拒绝。
阶段工具只重读新正常证据，随后旧1s两例及轻量回归，不重跑新正常准备。

## 3. 实际结果

[阶段报告](../.runtime/runs/flight-init-selector-sw02-stage-20261030T133918017071/report.json)
passed=false/runtime_accepted=false，software_regression_and_fault_checks_passed=true。

| 范围 | 结果 |
| --- | --- |
| 新正常 | 1008 HIL_SENSOR/4 HIL_GPS、1007 Run/4.028s、582真实全零执行器及四属性0；59 raw/59合法事件；第1008条错误网格原戳在Run前拒绝 |
| 实际selector交接 | 四组topic/七参数完整；500/1000局部ready=true、primary4/两IMU槽1，32处selector数组缺失显式隔离。未到2000/2500，整体准备仍不通过 |
| 控制/绑定 | 首零包step426，582包actuator-HIL差均−4000us，未证明当前周期或非零因果；消费消息原时间null/验证false，控制false |
| 时间停止原因 | 源double4.028乘1e6=4027999.9999999995，原桥接截断发4027999，网格应4028000；源误差仍在1ns内，raw/原wire均保持，不以放宽接纳 |
| disconnect | 126 raw/125 Run/20合法查询，peer_closed、末条未Run，原约.5s时间保持；独立审计通过 |
| transaction-timeout | 126 raw/125 Run/20合法查询，Run前原1.01s注入触发宿主/监督器，transaction_timeout；末超时raw不作合法step，独立审计通过 |
| 最终回归 | 新11/飞行173/运动84/全仓1076通过；旧实际1s两例、77场景字节/36公共往返/18合成源转换真实genpy兼容、25定义/7入口保持 |

三actual分别见[正常](../.runtime/runs/flight-init-selector-sw02-normal-20261030T133458680660/manifest.json)、
[断连](../.runtime/runs/flight-init-selector-sw02-disconnect-20261030T133633428328/manifest.json)、
[期限](../.runtime/runs/flight-init-selector-sw02-transaction-timeout-20261030T133730530101/manifest.json)；
独立审计在阶段目录各case-audit.json，时间源/数值/原始拒绝副本亦保存于该目录。
最长完整组≈109.3ms、单query≈7.75ms；只描述实际完成部分，非全部10s/98预算或20ms感知/RSS验收。
所有本轮自有进程/端口清理通过、无强制信号，不把退出当已disarmed/着陆。

## 4. 源码与交接

最终新增5文件、只修改已有私有selector合同，488源码；原483中482不变，原物理宿主/合同/第三方与旧入口保持。
三actual使用同一源码快照，实际后仅补tests审计/阶段工具及截断回归；生产者/查询/runner/合同相同，
报告列出later_test_changes，不冒充在最终全部tests源码上实际重跑三例。
[最终审计](../.runtime/runs/flight-init-selector-sw02-stage-20261030T133918017071/final-audit.json)
核源码/独立输入、旧公共定义/入口、历史失败、原源/新raw、Git和PID/文档链接。

下一项INIT-TIME-SW-01按[具体范围](../docs/SIM_FLIGHT_INIT_SELECTOR_SW02_PREPARATION_20261030.md#6-验证源码版本与下一任务)
先冻结独立整数时间预期，再只对新的隔离源副本在发送前按source_step/原1ns界生成整数微秒，
检查HIL_SENSOR与同源GPS时间；不修改接收包/历史原戳或旧默认路径，不以任何fallback/增容差绕过。
本轮未实现该生产者修复，也未重跑相同失败；两末检查点/完整准备、严格绑定/非零因果、公共v2/长窗/命令/飞行未通过。
研究质量、真实数据/DEM/占据融合及正式资源继续独立暂缓；无Hash/依赖安装/历史删除/提交/推送。
