# 发送端整数时间与完整无控制准备验证

编号：EXP-20261030-015；日期：2026-10-30；任务：SIM-FLIGHT-INIT-TIME-SW-01。
主责任：simulation_engineer；状态：已完成（隔离时间修复/单profile 10s无控制准备/故障兼容软件范围）。
交付：[十文件清单、时间语义、结果及下一任务](../docs/SIM_FLIGHT_INIT_TIME_SW01_DELIVERY_20261030.md)。

## 1. 范围与环境

用户“继续”确认具体隔离发送端修复，先读根/模块规范、状态/架构、接口/坐标、上轮原始失败与真实调用链。
分支feature/engineering-initialization，HEAD=d96d4439da1007489c80e7f21b132abff16505bf；全部既有dirty/未跟踪文件保留。
Python经sim01_env核对/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python，构建只在.runtime/ros。
先冻结16组独立输入/整数预期、原生产源与原始1008拒绝step，再实现纯C++和精确副本适配。
原488份源码/配置、桥接原树/旧宿主/入口/公共协议不改，IC/模型/噪声/阈值、1ns与所有预算保持。
无控制发送、真实数据/研究仓读写、训练/推理、DEM或正式PERF。

## 2. 执行与先行证据

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -c 'import sys; print(sys.executable)'
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B /tmp/ufm_time_freeze.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_sim_flight_initialization_time.py' -v
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B /tmp/ufm_time_probe_preflight.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_initialization_time_run.py --build-only
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_initialization_time_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_initialization_time_run.py --case disconnect
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_initialization_time_run.py --case transaction-timeout
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_flight_initialization_time_stage.py --normal .runtime/runs/flight-init-time-sw01-normal-20261030T140416952008 --disconnect .runtime/runs/flight-init-time-sw01-disconnect-20261030T140527292790 --transaction-timeout .runtime/runs/flight-init-time-sw01-transaction-timeout-20261030T140631932469
```

[先行oracle](../.runtime/runs/flight-init-time-oracle-20261030T135812795388/report.json)记录production_header_exists=false；
[真实C++/包字节](../.runtime/runs/flight-init-time-probe-20261030T140317997689/report.json)保留16组输出和2501条轨迹输出。
两个/tmp脚本仅保存具名独立预期/实际探针结果，不是运行fallback；已有目标均独占创建，不覆盖历史。
实际前单独socket预检在沙箱报Operation not permitted，没有启动失败正常场景；获本机回环执行许可后才跑实际三例/旧兼容。
未改系统网络/环境，不是自动审批拒绝；本轮没有生产/测试失败后调门槛或重复实际正常场景。

## 3. 实际结果

[阶段报告](../.runtime/runs/flight-init-time-sw01-stage-20261030T140716237059/report.json)
passed/runtime_accepted/software_regression_and_fault_checks_passed均true，范围只为本次单profile 10s无控制准备。

| 检查 | 实际结果及含义 |
| --- | --- |
| C++边界 | 16组，7接受/9拒绝；2501个double累加时刻，5016个真实MAVLink包由独立pymavlink解码通过，非mock或真实PX4运行 |
| 新正常 | 一次2500 Run/10s、2500 HIL_SENSOR/9 GPS、98 raw/98合法事件、2509源时间收据；四门全true，两个末检查点均ready |
| 发送时间来源 | 全HIL/GPS收据等于原物理before源时间/原1ns网格/原始发送wire；最大源误差约.000656812ns，未改接收包/历史原戳 |
| 原失败位置 | 新step1008真正发送4028000us，原源double4.028保留；旧step1008的4027999us/raw/manifest依旧失败，不回填 |
| 姿态/身份 | 末2000/2500主实例5、gyro/accel槽2；姿态sample7992000→9992000us、原land/年龄/健康门通过。初125/250 selector仍缺失，不外推更早就绪 |
| 合法缺失与控制 | selector80处数组null/说明，载荷完整性false；消费消息时间null/验证false、control_gate_accepted=false、绑定unverified |
| 零执行器/物理 | step423—2500共2078个真实全零包，16路/四属性0；末窗口有500包，actuator−HIL仍−4000us。证明规定零输出门，不证明非零因果/严格绑定 |
| 两故障 | 均126 raw/源收据、125 Run/20合法查询，断连peer_closed或1.01s注入transaction_timeout；末条未Run、物理时间保持约.5s，清理通过 |
| 定向/全仓 | 新7/飞行180/运动84/全仓1083通过；旧1s两例及77场景字节/36公共往返/18合成源转换真实genpy兼容、25定义/7入口保持 |

正常/断连/期限的manifest和独立审计链接见交付说明；三actual同最终498源码快照，没有实际后代码漂移或重跑。
物理准备墙钟约30.7621s、最长组131.876ms/单query9.175ms，均在原界；不是实时倍率/感知20ms、RSS或正式PERF验收。
未发heartbeat/模式/arming/manual/参数写；进程退出不代表已完成受控着陆。

## 4. 文件与交接

新增10文件，原488源码/配置保持；新主机只在源副本增加时间调用和有界来源收据，不引入在线业务消费者。
schema/profile/98计划、物理合同/1ns、默认入口及第三方原源保持；本轮只关闭单profile准备软件门。
[最终保护审计](../.runtime/runs/flight-init-time-sw01-stage-20261030T140716237059/final-audit.json)
核498源码/原488、独立预期/原始失败、精确生成源副本、旧定义/入口、全部PID/端口、Git和本地链接。

直接下一项SIM-FLIGHT-SW-03A按原已交方案推进公共v2离线逻辑/codec/独立端点合同，
先冻结预期/100采样时刻，再真实生成消息序列化及旧协议交叉拒绝；仍不启动长窗/节点/命令。
30/40s采样、严格执行器周期绑定/非零因果、模式/arming/离地与飞行、真实设备/研究质量、DEM/占据融合和正式资源仍未验收。
无新依赖/Hash/研究仓修改/历史删除/自动提交或推送。
