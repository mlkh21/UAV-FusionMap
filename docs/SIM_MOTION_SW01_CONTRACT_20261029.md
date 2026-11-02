# SIM-MOTION-SW-01：运动输入、推进协议与线格式

日期：2026-10-29；版本：v1；主责任：simulation_engineer。
状态：已完成（离线输入/合同与消息软件范围）；不含推进状态机、运行节点或飞行联动。
依据：[联动具体设计](SIM_SCENE_MOTION_DESIGN_20261029.md)、ADR-042；
验证：[EXP-20261029-007](../experiments/2026-10-29-sim-motion-contract.md)。

## 1. 已有代码与本轮新增

复用原AircraftState的字段及实际ROS编码，保持旧消息、codec、包依赖和launch不变。
新增独立[uav_fusionmap_sim_scene_msgs](../ros_ws/src/uav_fusionmap_sim_scene_msgs/package.xml)，
仅新包依赖旧消息包；生成2.msg/1.srv，包内`ufm_scene_contract`提供无ROS副作用的逻辑校验与严格codec。
当前不存在SceneStep服务端、SceneFrame发布者或采样ACK节点。

| 交付 | 用途 |
| --- | --- |
| [固定profile](../configs/sim_scene_motion_fixture.json) | 明确fixture、真值/质心来源、4ms/1ms步长、25步采样、1s短窗、同步及墙钟/收据预算 |
| [独立预期](../tests/fixtures/sim_motion_expectations.json) | 手工字段布局、六组坐标/单位/杆臂算例、六个整数时间点及七种响应状态 |
| [sim_motion_fixture](../tests/sim_motion_fixture.py) | 无ROS导入的测试输入、分数/解析oracle、独立struct字节，不调用生产转换器生成答案 |
| [逻辑合同](../ros_ws/src/uav_fusionmap_sim_scene_msgs/src/ufm_scene_contract/contract.py) | 新帧/ACK/请求/响应及绑定校验，禁止未知字段/训练监督 |
| [profile输入校验](../ros_ws/src/uav_fusionmap_sim_scene_msgs/src/ufm_scene_contract/profile.py) | 有界JSON、固定配置与原始FDM样本时间/旋转校验；不做坐标转换 |
| [严格codec](../ros_ws/src/uav_fusionmap_sim_scene_msgs/src/ufm_scene_contract/codec.py) | 真实生成类型、规范空槽、解码前字节扫描与可选请求/帧绑定 |
| [离线运行器](../tests/sim_motion_run.py) | 先存独立预期/输入/字节，再做生成消息往返、兼容核对和测试；不重复覆盖已有证据 |

## 2. v1逻辑对象与ROS承载

逻辑对象必须字段精确；身份≤128 UTF-8字节，reason≤256字节且为小写机器码。
布尔与整数必须真实类型，拒绝NaN/Inf、未知版本/枚举及所有额外字段。
协议版本为1；内嵌旧AircraftState仍为0.1，两者版本不能相互替换。

| 对象 | 冻结字段与约束 |
| --- | --- |
| SceneFrame | protocol_version、state、step_index、registration_id、angular_velocity_flu。registration固定jsbsim_cg_to_scene_enu_v1；角速度float64[3]、FLU、rad/s |
| 内嵌state | scene_world、simulation、ground_truth、valid；body/velocity均base_link。position/linear_velocity为float64[3]米/米每秒，orientation为xyzw float64[4]；原单位四元数容差0.001、不归一化修补 |
| 内嵌header | run/clock严格sim:run，sample_id=scene.frame:run:step；timestamp=step_index×4000000，非负int64，不经float转换 |
| 内嵌quality | confidence=None；uncertainty固定unavailable、kind/unit空、value=None、source=jsbsim_scene_truth_no_covariance_v1。不虚构协方差或置信分数 |
| SceneCaptureAck | protocol_version、run_id、clock_id、step_index、measurement_timestamp、sensor_kind、published、reason。sensor_kind固定1 Radar/2 IR；step必须>0 |
| SceneStepRequest | 仅frame一个SceneFrame |
| SceneStepResponse逻辑对象 | accepted、reason、applied_frame、radar_timestamp、infrared_timestamp；后三者以None表示缺失，响应外形没有伪造状态或free字段 |

公开协议中step_index虽为uint64，其有效范围还受int64 timestamp约束，最大为
floor((2^63-1)/4000000)；测试profile进一步只允许0—250步原始FDM输入。
0是初始化时刻，不能触发采样；step>0且能被25整除时才是采样tick。
协议允许零/负局部z，不靠正负或数值0推断缺失；实际短窗的地面/覆盖停止闸门留SW-02。

成功ACK必须published=true、reason空、处于采样tick，measurement_timestamp精确等于该tick。
失败ACK的published=false且reason非空，可保留实际错时值，包括0；它不构成推进成功。
绑定frame时run/clock/step必须逐值一致。ACK仅证明发布动作，不证明Bundle、地图或质量已验收。

成功响应必须有applied_frame；非采样tick两个时间都为None，采样tick两个时间必须同时精确匹配。
失败响应必须有reason，可保留同请求的部分应用帧/部分采样时间；accepted=false时调用方不得推进。
完全未应用时applied_frame=None，两个采样时间也必须None。
可选request绑定检查帧身份/step/注册/质量精确一致，位置/线速度/角速度绝对误差≤1e-9，
四元数按相同或相反符号绝对误差≤1e-12；容差不用于时间、枚举或计数，也不重写任何结果。

### 缺失标志与规范空槽

ROS响应使用has_applied_frame、radar_captured、infrared_captured三个bool承载逻辑None。
flag=false时数字槽必须0；缺失frame的整个嵌套消息必须为逐字节规范零/空，包括protocol_version=0、
空身份、零数组及空uncertainty数组，不能将其当作有效SceneFrame解码。
失效槽中的非零、负零、残留身份或错误bool类型都拒绝。失败响应中timestamp=0且flag=true表示
“确有该错误采样时刻”，与flag=false不同；成功初始化tick的采样flag必须false。

新codec还检查旧嵌套quality：confidence_available=false时confidence必须规范+0，
unavailable uncertainty的变长value数组必须为空。此严格性只施加在新包入口，不改变旧codec的兼容行为。

## 3. 有界输入、预期与验证方式

单条线格式≤4096字节。decoder在调用genpy前按实际slot类型扫描长度和边界，
拒绝超长string、非空质量变长数组、非0/1布尔字节、非有限浮点、截断和尾随字节。
随后使用真实生成类deserialize并做语义校验/重序列化核对；没有用mock代替线格式。
字符串在UTF-8编码前先按字符长度拒绝超限，拒绝非法Unicode和NUL身份。

JSON文件≤1MiB，深度≤16、总项≤8192、对象≤64字段、列表≤512项；重复键、非有限、超限拒绝。
固定profile只接受登记值及类型，不通过改步长/同步预算或切estimated模式放宽输入。
原始FDM样本精确字段为step_index、sim_time_s、ecef_ft、R_ecef_frd、uvw_ftps、pqr_radps；
以原float的精确分数值核对实际秒与step网格误差≤1ns，拒绝后不四舍五入到成功网格。
矩阵必须有限、正交、右手；这些仅是输入检查，不表明FDM读取或ECEF转换已经实现。

六组独立坐标算例覆盖ECEF非零差的feet→m、NED/FRD、90度姿态/非零安装、
平移Doppler、转动杆臂及大地/地心纬度区别；六个时间点包含0、采样前后及超过2^53的整数纳秒。
本轮检查的是独立reference自洽及消息承载，实际FDM坐标转换器仍属SW-02。

## 4. 复现与实际证据

先确认指定解释器，再冻结，随后隔离构建并验证：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -c 'import sys; print(sys.executable); assert sys.executable == "/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python"'
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_motion_run.py --freeze-only
bash ros_ws/sim01_env.sh cmake -S ros_ws/src -B .runtime/ros/build -DCATKIN_DEVEL_PREFIX=/home/zxj/catkin_ws/src/UAV-FusionMap/.runtime/ros/devel -DPYTHON_EXECUTABLE=/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python
bash ros_ws/sim01_env.sh cmake --build .runtime/ros/build --target uav_fusionmap_sim_scene_msgs_generate_messages -j2
```

以上freeze输出新目录；用`--verify <本次冻结目录> --full`执行一次验证，输出已有时拒绝覆盖。
类型已生成后，`bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_motion_run.py --full`
可每次创建新目录并执行完整离线流程，不需要ROS Master。

首次冻结/构建：[135240241313](../.runtime/runs/sim-motion-sw01-20261029T135240241313/message-build.log)。
最终验证：[140032058561](../.runtime/runs/sim-motion-sw01-20261029T140032058561/report.json)。
20组实际生成消息往返均对保存的独立struct字节逐值一致，17份旧.msg/.srv定义未变。
本轮新增26项定向、最终26/26与全仓845/845通过；只读文档/边界检查见实验记录。

## 5. 未实现能力与下一项

不实现运行中的连续step/重复冲突锁定、ACK等待/取消、pause/resume或回放状态机；
本轮只校验单条合同及可选绑定。没有注册新话题/服务，没有启动FDM、PX4、Gazebo、模型或训练。
raw无run的运行来源绑定、唯一clock/状态/TF、真值terminal传播、实际运动速度/姿态及相机握手
仍需SW-02实测，端到端地图/原生窗口与故障清理归SW-03。旧图仍是固定飞机场景。
research、真实DEM/占据融合、机载性能及正式阶段门槛不变；没有自动提交/推送或外部归档。
