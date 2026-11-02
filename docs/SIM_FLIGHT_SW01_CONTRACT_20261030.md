# 飞行IC与执行器收据离线合同

日期：2026-10-30；版本：v0.1；任务：SIM-FLIGHT-SW-01；主责任：simulation_engineer。
状态：已完成（私有离线合同/有界校验及旧协议兼容范围）。
依据：[具体方案](SIM_FLIGHT_DESIGN_20261029.md)、ADR-044。
本轮没有FDM/ROS/宿主/控制客户端、新公共类型或飞行运行；40s与采样表仅为静态合同数据。

## 1. 已有代码与本轮文件

已有SW-04C同FDM/真实采样及公开地图链保留；新模块没有运行入口或业务消费者。
只复用既有离线测试基础设施验证旧线格式，不修改旧运动profile、消息或默认运行语义。

| 文件 | 本轮用途 |
| --- | --- |
| [固定profile](../configs/sim_flight_fixture.json) | 具名ground/observe合同、AGL/基准/姿态、2/5/7/4通道、时间/预算；命令固定关闭 |
| [flight_contract](../simulation/ufm_simulation/flight_contract.py) | 标准库纯逻辑：profile/IC/record/header校验、JSON编解码、流式JSONL读取；不调用仿真或ROS |
| [独立预期](../tests/fixtures/sim_flight_expectations.json) | 在实现前保存IC、非对称float32探针、100个未来采样时刻边界及两记录统计 |
| [测试fixture](../tests/sim_flight_fixture.py) | tests专用合成bootstrap/disarmed/armed探针/失败/未执行记录，不是动力学轨迹或在线输入 |
| [25项测试](../tests/test_sim_flight_contract.py) | 缺失/位宽/float32/属性读回/时序/终止/容量/导入隔离与输入快照检查 |
| [离线入口](../tests/sim_flight_run.py) | 先冻结独立预期与输入/源码，再编解码与JSONL重读、旧genpy线格式和回归；不依赖某个历史run路径 |

另更新本说明、中文实验、状态/计划/架构及接口索引。没有新增Hash、依赖或第三方源适配。
代码检索确认ros_ws/sensors/perception/mapping/application尚不消费新flight_contract或profile。

## 2. 固定profile与IC

sim_flight_fixture.v1是具名离线数据，不是旧sim_scene_motion_fixture.v1的可调扩展。
profile_id=sim-flight-ground-observe-v1，fixture_only/simulation_only=true，
commands_enabled=false、observation_only=true，command_policy.allowed为空且force_arming_allowed=false。
修改这些值、未知字段或任意模型/路径/命令都拒绝，不能在该版本启用控制。

IC固定LSZH经纬度、altitude_reference=AGL、altitude_m=.5、terrain_elevation_m=419.2、
true_airspeed_mps=0、phi/theta/psi=[0,0,90]度，gamma=null表示未来生成时省略冲突项。
实际AGL/ASL或姿态还未读取；此合同没有进行地理转换、创建IC XML或安装FDM。
ground锚点[0,0,.5]、注册jsbsim_cg_to_flight_enu_v1也只作私有元数据，旧8m注册不变。

max_step=10000、prepare_steps=7500、4ms步、step>7500且每25步采样，
首7525/30.1s、末10000/40s、共100组。capture_step只计算这张离线表，不推进时钟或开启传感器。
后续SW-02仍须独立硬限制≤250步/1s，只消费ground IC/私有诊断，不把.5m真值送进旧z>.5的Gazebo v1端点。
40s及v2的实际装配仍属SW-03；不能凭本profile绕过旧250步/8m限制。

## 3. 私有记录与缺失语义

sim_flight_actuator_record.v1精确字段如下，嵌套对象也拒绝额外键：

| 字段 | 规则与含义 |
| --- | --- |
| schema_version/run_id/clock_id | 版本固定，身份≤128 UTF-8字节、clock必须sim:+run；不允许控制字符 |
| step_index/source_step | int且非bool，1..10000，source_step=n−1 |
| hil_sensor_time_us | 实际发送的原始uint64微秒；不以n×4000替换 |
| has_actuator/actuator | bool必须显式；false时actuator=null，不能用零包冒充观测 |
| binding_status/reason | binding_status仅unverified；缺失reason=actuator_not_received，有观测reason为空 |
| actuator.receive_sequence/peer/time_usec | 递增uint64接收序号、loopback TCP peer及sysid/compid=1/1、原始uint64回包时间；端口记录实际值 |
| actuator.flags/mode/armed/controls | flags只0/1，当前PX4模式只1/129，armed必须与128位一致；16路实际float32值，未armed时全部为0 |
| properties | before/requested/after按rudder/aileron/elevator/throttle四槽；requested严格等于2/5/7/4×−1/−1/−1/+1，after读回误差≤1e−6 |
| fdm | ran/result区分未调用(null结果)、调用失败(false)、成功(true)；原始前/后时间和4ms±1ns界分别核对 |
| wall | hil_sent_ns/actuator_received_ns/properties_applied_ns/fdm_finished_ns为有序非负int64；缺失时中间两项null，不能替换源时间 |

controls要求保持实际float32可精确表达的值，例如实际0.6f在JSON中是0.6000000238418579；
不能先舍入成0.6再冒充原始值。负零允许并保留。油门范围[0,1]、其余通道[−1,1]；非有限/坏类型拒绝。
缺失时requested=null、after=before；这不表示已测到disarmed或零控制。
独立非对称探针映射为[+.25,−.30000001192092896,+.20000000298023224,.6000000238418579]。

有观测且mode=129的单条诊断在结构上可校验，但绑定observation_only头部后明确拒绝，
不能把结构合法提升为运行许可。未收到/错时间/坏包的实际原始wire须由后续宿主另外保存，
不能为符合本schema重写原值；本轮合成数据没有MAVLink原始包来源证明。

重要分界：本轮不验证HIL回包是否真正对应当前周期。
unverified记录允许发送/回包时间不同，保留uint64原值；逐流仍拒绝回退/重复时间与序号。
不存在matched/成功控制门出口，统计control_gate_accepted始终false；SW-02实测关系后再明确扩展。

## 4. 记录头、流式边界与原子性

sim_flight_recording.v1头部精确包含schema_version、run/clock、完整固定profile、
peer、initial_properties与initial_wall_ns。初始属性固定零，peer地址127.0.0.1、端口1024..65535，
sysid/compid=1/1；这些字段是待核对声明，本轮不进行socket认证或连接。

JSONL首行为头部，其后逐条record。每条校验run/clock/peer、连续step、递增接收序号、
独立发送/回包时间顺序、属性与FDM时间连续、非交叠墙钟；不能把迟到/重复记录当新步。
首次执行器前最多500步/2s源时间且5s墙钟；收到首包后再缺包，不允许继续FDM Run或沿用旧输出。
缺包但未运行FDM可作为terminal；FDM失败也terminal，之后有记录即拒绝。
本函数是无状态离线审计，不创建或恢复运行实例；合法短前缀不等于完整40s验收。

头部/profile≤256KiB，单记录≤16KiB，深度≤8、节点≤8192、单列表≤512，
日志≤64MiB、条数≤12288（连续执行器step另受10000界）。
读取按界+1、逐行、累计实际文件字节，不用文件stat或紧凑重编码长度冒充原文件大小。
JSON拒绝重复键、NaN/Inf、非法UTF-8、孤立代理项、控制字符和超长文本，
大整数字面量转换前先限制长度。树检查在编解码/schema前执行，未知训练监督字段拒绝。
输入不被修改，上一条属性状态与头部独立复制，生成器事后修改旧对象不能绕过连续性。
库只有读文件/编解码；测试入口用独占创建模式写本次验证产物，不能覆盖历史run。

## 5. 实际验证与复现

在仓根使用固定Conda环境，本轮实际执行：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_flight_run.py --full
```

实现前[独立预期冻结](../.runtime/runs/sim-flight-sw01-20261030T000905024587/independent-expectations.json)保持未改。
最终[报告002214270144](../.runtime/runs/sim-flight-sw01-20261030T002214270144/report.json)：
25/25新增定向、8组私有JSON字节往返、3组独立通道探针、100个采样时刻及两条JSONL重读一致。
这是私有JSON合同，不是实际HIL包序列化或FDM执行回放。

[既有协议/全仓报告](../.runtime/runs/sim-motion-sw04a-20261030T002214316781/report.json)；
84/84旧运动定向、77组Scene真实genpy字节、36组旧公共往返、18个合成源转换及928/928全仓通过。
旧25份定义/7配置入口保持，既有423份生产/测试源码未改；新模块不导入rospy/pymavlink/torch或ROS合同。

初次预算测试通过缩小内部限额触发边界，却被固定profile的同值检查提前拒绝，
原[23项/1失败日志](../.runtime/runs/sim-flight-sw01-20261030T000905024587/initial-targeted.log)保留；
只修测试注入时的头部限额一致性，不改变实际64MiB/12288等合同。
随后补bootstrap/源时间与单步增量边界、大整数字面量及当前源码自冻结，最终25项与全仓通过。

## 6. 未验证与下一步

没有新宿主/桥接patch、IC安装、真实socket/HIL记录、v2 codec/服务、命令发送或新窗口运行。
不证明实际armed、控制时序、ready、离地、稳定飞行、RSS/功耗或正式PERF。
真实模型质量、DEM/占据融合仍未验收，research继续fail-closed。

直接下一项SIM-FLIGHT-SW-02：隔离构建只读诊断宿主，实际≤1s/250步采集同FDM的HIL/属性/结果，
不发送heartbeat/arm/manual/参数写，不启v2/长窗。未就绪须明确报告，不能把缺包填零或把离线统计当控制门通过。

后续状态：SW-02已完成[实际有界诊断/断连接交接](SIM_FLIGHT_SW02_DIAGNOSTICS_20261030.md)。
正常1s内执行器0包，保持bootstrap_not_ready/unverified；本合同仍不能作为控制许可。
