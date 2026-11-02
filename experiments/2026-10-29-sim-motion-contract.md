# EXP-20261029-007：运动输入与场景推进公共合同

日期：2026-10-29；主责任：simulation_engineer；状态：已完成（SIM-MOTION-SW-01离线软件范围）。
依据：[运动设计](../docs/SIM_SCENE_MOTION_DESIGN_20261029.md)、ADR-042；
字段与复现：[SW-01合同](../docs/SIM_MOTION_SW01_CONTRACT_20261029.md)。

## 1. 目的与范围

按已交付设计先冻结profile、原始FDM输入边界、独立坐标/时间/杆臂预期和场景推进线格式，
为后续同FDM/Gazebo逐帧握手提供明确合同。新包生成2.msg/1.srv，复用旧AircraftState，
新逻辑校验与codec不导入仿真/模型执行器，不改变旧字段、launch、codec或在线消费链。

开发前核对根及涉及目录规则、dirty/untracked状态、忽略规则和真实生产消费链。
HEAD仍为d96d4439da1007489c80e7f21b132abff16505bf，分支feature/engineering-initialization；
全部既有修改保留。未改同级研究仓库、第三方源、Conda环境或终端ROS选择。
新包只依赖原公共消息，新旧业务节点没有反向依赖新包。

## 2. 执行顺序与产物

核对sys.executable为/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python。
独立预期是手工JSON/struct布局，生成expected时不导入生成消息或生产codec。
初次[135240241313](../.runtime/runs/sim-motion-sw01-20261029T135240241313/independent-expectations.json)
先保存profile、输入、六组坐标/六时间点预期、20份expected二进制与旧17份定义副本，
然后才进行catkin生成及真实消息执行。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_motion_run.py --freeze-only
bash ros_ws/sim01_env.sh cmake -S ros_ws/src -B .runtime/ros/build -DCATKIN_DEVEL_PREFIX=/home/zxj/catkin_ws/src/UAV-FusionMap/.runtime/ros/devel -DPYTHON_EXECUTABLE=/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python
bash ros_ws/sim01_env.sh cmake --build .runtime/ros/build --target uav_fusionmap_sim_scene_msgs_generate_messages -j2
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_motion_run.py --verify .runtime/runs/sim-motion-sw01-20261029T135240241313 --full
```

初次20组字节、25项定向/844项全仓均通过。随后源码复核发现验证运行器可能在二次验证时
先覆盖actual二进制再因日志已存在退出；尚未发生该覆盖。改为执行前拒绝任何既有实际证据，
二进制create-only，新增一项部分证据保留反例，并移除未使用的内部辅助函数。
因工具行为和测试新增，另建[最终140032058561](../.runtime/runs/sim-motion-sw01-20261029T140032058561/report.json)：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_motion_run.py --full
```

没有覆盖前次成功/失败产物或更改冻结预期来取得通过；两份独立预期/字节另做一致性核对。
本轮没有启动ROS Master、GUI、PX4、JSBSim、forward/训练，也没有构建外层catkin_ws或新增依赖。

## 3. 实际验证与边界

| 检查 | 结果 |
| --- | --- |
| 实际生成类型 | SceneFrame、SceneCaptureAck与SceneStep请求/响应，C++/Python等生成目标通过；Python为指定Conda |
| 保存预期对账 | 20组真实genpy serialize/deserialize对独立struct字节一致，另按生成类直接deserialize后经新codec复核 |
| 样例 | 0/负局部z、初始/非采样/采样tick、整数时间>2^53、Radar/IR ACK、未应用/部分失败及availability区分 |
| 坏输入 | 枚举/版本/身份/训练字段、非有限、错长度、bool伪整数、字节/结构限额、非规范缺失槽位及恶意长度/截断/尾随拒绝 |
| 嵌套旧合同 | 四个旧类型实际字段布局与独立布局一致，17份旧.msg/.srv源码未改；新包严格检查旧codec会忽略的缺失confidence槽，不修改旧行为 |
| 相关及全仓 | 最终新增26项、定向26/26（0.119s）、全仓845/845（58.151s）通过；第一次25/844仅作为修补防覆盖前的运行记录保留 |

可选绑定检查实际响应身份、step、注册与应用几何；采样时间/计数精确整数比较。
原始FDM源输入仅检查时间网格、有限值及正交右手矩阵；六组坐标/杆臂oracle为独立解析算例，
没有运行新FDM坐标转换器或动力学，不把消息承载当M01—M12已验收。
profile是固定测试参数，不是目标机实时预算；JSON/消息限额不等于RSS。
最终delivery-audit.json核对13页/802条本地链接有效、16份新增源码/配置/测试快照，
两轮20份独立expected字节一致；初次expected文件早于生成的SceneFrame Python文件，
实际消息文件位于隔离.runtime/ros，CMakeCache指定解释器正确，HEAD未变化。git diff --check通过。

## 4. 修改清单

- 新增configs/sim_scene_motion_fixture.json与tests/fixtures/sim_motion_expectations.json。
- 新增ros_ws/src/uav_fusionmap_sim_scene_msgs包（2.msg/1.srv、CMake/package/setup、逻辑合同/profile/codec）。
- 新增tests/sim_motion_fixture.py、sim_motion_run.py、test_sim_motion_contract.py、test_sim_motion_codec.py。
- 新增本记录与SW-01说明；同步公共数据/传感器/坐标说明、状态、设计/计划、ADR和实验/交付索引。

源码、定义、快照与核验报告保存在本次新run，不计算无消费者Hash。
旧主链、消息字段和默认入口保持；没有生成新运行服务或偷偷接入默认launch。

## 5. 下一项与未验证能力

下一项SIM-MOTION-SW-02：同一FDM真值读取/坐标转换、真实推进状态机、暂停Gazebo受控step、
传感器运动元数据与采样ACK、唯一clock及真值terminal传播；实际相机线程握手是硬闸门，失败不能改戳绕过。
SW-03再验证端到端感知地图、原生窗口及正常/故障清理与旧入口实际兼容。
本轮没有联动运行，飞机仍固定；真实模型质量、设备、DEM融合、机载资源和正式阶段门槛保持未完成。
无自动提交、推送或外部归档，旧原始数据/实验/环境原位保留。
