# 同FDM真值与受控场景采样交接

日期：2026-10-29；任务：SIM-MOTION-SW-02；主责任：simulation_engineer。
状态：已完成（有界真实动力学/采样软件闸门）；不代表受控飞行、SW-03或正式阶段验收。
依据：[具体设计](SIM_SCENE_MOTION_DESIGN_20261029.md)、[冻结合同](SIM_MOTION_SW01_CONTRACT_20261029.md)、
ADR-042；实测与失败：[EXP-20261029-008](../experiments/2026-10-29-sim-motion-engine.md)。

## 1. 已有代码与本轮实现

复用已有PX4 SITL、JSBSim 1.1.13、JSBSimBridge、Gazebo11真实Ray/Camera和SW-01生成消息。
本轮没有改第三方源码、旧PX4/bridge二进制、公共消息字段或默认launch。独立构建产物位于
`.runtime/sim-motion-build`，C++桥接重新编译到该目录，原动态模型与既有补丁来源保持。
不是手写飞行动力学，也没有发送解锁、起飞、航点、offboard或控制命令。

| 文件 | 新增或修改职责 |
| --- | --- |
| [jsbsim_scene_host.cpp](../simulation/jsbsim_scene_host.cpp) | 持有传入原JSBSimBridge的同一FGFDMExec；每次Run完成后读ECEF feet、Tb2ec、UVW、PQR、原始double时间和整数index，命令FIFO只接受next/quit |
| [scene_motion.py](../simulation/ufm_simulation/scene_motion.py) | 初始大地纬度/经度固定ENU注册；feet→m、FRD→FLU、SciPy旋转；单pending/最后完成事务、重复/冲突/失败锁定及terminal |
| [gazebo_scene_step.cpp](../simulation/gazebo_scene_step.cpp) | 暂停world的SceneStep服务、4个1ms子步、代理pose实际回读、同run连续step与有界缓存、真实ACK来源/身份/时间门控 |
| [scene_motion_context.h](../simulation/scene_motion_context.h)、[实现](../simulation/scene_motion_context.cpp) | 同一Gazebo进程内的公开SceneFrame基础设施邮箱和传感器就绪/受控采样钩子；不交换点云、图像或地图结果 |
| [scene_motion_capture.h](../sensors/scene_motion_capture.h) | 原始测量时间匹配、每传感器每采样step一次ACK；只有实际publish后才published=true |
| [Radar](../sensors/gazebo_scene_radar.cpp)、[IR](../sensors/gazebo_scene_ir.cpp) | 显式controlled_motion分支；真实Ray采样、FLU线速度/角速度杆臂Doppler、真实相机渲染；旧默认分支保持 |
| [scene_motion_world.py](../simulation/ufm_simulation/scene_motion_world.py) | 从旧场景显式生成新受控world，去掉旧scene_pose状态权威，保留真实障碍物与热材料 |
| [state_adapter.py](../sensors/ufm_sensors/state_adapter.py)、[scene_stream.py](../sensors/ufm_sensors/scene_stream.py) | 声明注册/真值身份检查后传播非几何terminal；流清空旧pending并锁定，旧消息不能恢复 |
| [构建](../ros_ws/sim_motion_build.py)、[运行器](../ros_ws/sim_motion_gate_run.py) | 环境/进程/端口监督、FDM与SceneStep薄装配；独立编译、先保存预期、单clock/状态来源审计 |
| [实测收据检查](../tests/check_sim_motion_live.py)、[11项新增测试](../tests/test_sim_motion_engine.py) | 有界真实ROS二进制收据、解析坐标oracle、坏事务/终止、新run隔离、逐点Doppler/IR/TF核验；坏收据create-only并停止后续接收，保留首份失败证据 |

## 2. 真实推进与采样细节

初始IC仅在本次目录生成：沿原LSZH经纬度/地面定义，初始高度8m、前向速度5m/s、航向90°。
不是飞控保持指令；1s内飞机受真实动力学自由演化、下降和俯仰，不能叫作稳定巡航。
原始初始ECEF、GetGeodLatitudeRad、GetLongitude、固定Q与锚点均存盘，不向首个到达消息重对齐。
每个raw double时刻经SW-01网格检查后才生成index×4000000整数时间，容差仍为1ns。

每次事务设置静态代理准确pose，同步安装该SceneFrame到进程内基础设施邮箱，并发布
`/uav/scene/frame_applied`同内容镜像。传感器读公开类型的同帧元数据，不依赖ROS回调先后次序；
simulation不读取raw点云/图像或传感器私有业务对象。ACK仍经真实ROS回路进入SceneStep，
校验callerid=/gazebo以及run/clock/step/kind/原始测量时间，单个待执行事务，无无限去重表。

初次自动Ray线程与暂停world竞争，首个100ms成功而200ms缺Radar ACK。修补为受控模式下
Ray关闭自动active，在world四子步完成后显式调用真实RaySensor::Update(true)，插件仍从
LastMeasurementTime发布原始点云。不是重用旧点或修改时间。IR保持真实渲染线程，内部1kHz
准备子步缓冲与热材料；只有正step每25步、实际时间恰好100ms整点才向ROS发布raw/ACK。
公开Radar/IR仍10Hz；内部渲染调度不改变冻结profile的业务频率或任何时间门槛。
step 0不产生观测；首个IR材料选择缓冲不能冒充热图，首个100ms实际热图必须成功。

采样时代理保持该帧pose，直到两路ACK后才能推进下一帧。Gazebo clock只进诊断域；
唯一公共clock与仿真状态来自/sim_motion_host，唯一odom→base_link来自原state_adapter。
成功响应回读物理量绑定沿用位置/速度/角速度1e-9、四元数符号等价1e-12。
运行profile额外拒绝离锚点>200m、z≤0.5m和不能精确应用的非单位四元数，
不更改公共逻辑合同中零/负高度的可表达性。

事务墙钟预算包含world推进及ACK等待：首个采样3s，其余1s；传输监督另留返回失败回执的
小量外壳时间，不接受引擎超预算成功。启动60s、运行会话120s；编译另计。
末帧有效state/TF先有界排空，再发terminal；失败则停止公共clock，terminal不产生新TF。
不存在真实引擎失败后切回fixture、重写采样戳或继续FDM补帧。

## 3. 实际验证

正常：[最终收据](../.runtime/runs/sim-motion-sw02-20261029T154737606036/validation.json)。
故障：[最终运行期丢失IR ACK](../.runtime/runs/sim-motion-sw02-20261029T154851651514/validation.json)。
两者都有完整PX4启动、真实FDM/Camera/Ray与各自清理；全仓结果独立记录，不当作同次运行。

| 项目 | 结果 |
| --- | --- |
| 正常引擎短窗 | 250步、1s源时间，251条公共clock/有效state/动态TF，10对raw和20 ACK；真值terminal正常传递 |
| 实际运动 | [0,0,8]→[5.4362694069936195,-0.0024849018548632144,4.626639929639477]m，位移6.397858m；Gazebo回读与TF匹配 |
| Radar | 13,217回波逐点解析Doppler/杆臂与强度核验，最大Doppler误差5.2206251e-7m/s；624→2304点；无回波不解释为free |
| IR | 实际320×240 32FC1，前后67,933像素变化；功能热强度，不是辐射温度 |
| 事务/暂停 | step24的100ms墙钟暂停不推进world或重复raw；step25重复调用返回原回执，无二次采样 |
| 实际服务拒绝 | 坏版本/身份/非有限/质量/四元数/注册/跳步/超限八类拒绝，world仍0，随后正常连续步进 |
| 运行期故障 | 控制端丢弃第250步IR ACK，raw与ACK本身仍真实发布；只提交至249步/996ms，terminal传播、旧run锁定，未发第251步FDM命令 |
| 离线/线格式 | 11项新增、运动定向37项和全仓856项通过；20组独立字节与真实genpy一致，17份旧定义未变 |
| 旧入口回归 | 旧estimated/T-14 ROS fixture、旧静态Gazebo+标准RViz场景/点云/IR/地图和像素检查均通过 |

同step冲突、坏响应、晚响应不能恢复、新run从空事务开始及terminal几何隔离也有新增测试；
这些离线反例不冒充对应全部故障都已用真实引擎注入。
字节/条数上界为每流512、总16MiB，不表示RSS/正式性能；Doppler误差仅核对功能代理实现。

## 4. 复现与边界

所有命令从仓根使用指定Conda环境；本机已有依赖，不安装或修改环境：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -c 'import sys; print(sys.executable)'
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_motion_gate_run.py --build-only
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_motion_gate_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_motion_gate_run.py --fault missing-ir-ack
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_motion_run.py --full
```

默认ROS/Gazebo端口11801/11802，同时检查PX4固定端口及既有PX4进程，冲突直接拒绝。
运行器完成即清理，不启动新运动Gazebo/RViz窗口；`.runtime/runs/sim-motion-sw02-*`各自保留
预期、输入、源快照、raw FDM、注册、实际原始消息/ACK/状态/TF二进制、事务、图与清理。
恢复须新run；旧静态可视化命令继续保留，不改成默认运动入口。

下一项SIM-MOTION-SW-03：显式接SceneStream→placeholder→M1 latest→公开查询/回放，
以观测时刻Context逐值验证，再交付带来源的新运动Gazebo/RViz图片和失联历史显示。
本轮没有执行该端到端链路或运动窗口验收；旧静态窗口回归不能替代它。
真实设备/模型质量/DEM融合/机载资源、高速控制与正式阶段门槛保持未验收。
