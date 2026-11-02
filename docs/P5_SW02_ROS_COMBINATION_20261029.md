# P5-SW-02：实际ROS组合与公开收据回放

日期：2026-10-29；主责任：integration_engineer；版本：v1。
状态：已完成（A/B合成软件ROS组合范围）；S09/C仍属SW-03。
后续SW-03已完成[S09/C与软件全矩阵交接](P5_SW03_NATIVE_DELIVERY_20261029.md)；
本文保留SW-02当轮范围，四个C子例不是本轮A/B运行的一部分。
依据：[组合设计](PHASE5_SOFTWARE_COMBINATION_DESIGN_20261029.md)、
[SW-01冻结输入/预期](P5_SW01_INPUT_CONTRACT_20261029.md)、ADR-041。
实际运行与失败历史见[EXP-20261029-004](../experiments/2026-10-29-phase5-ros-combination.md)。

## 1. 已有代码与本轮新增

沿用现有状态适配/StateClockGate、Radar/IR构造及Bundle配对、PerceptionEngine与可选CPU worker、
M1/M4工厂和地图ROS节点、TerrainNode/Provider、两种应用查询客户端、占据/地形执行回放。
本轮不改这些业务实现或公共字段，不改默认launch；所有装配只由显式新测试入口创建。

| 新文件 | 作用 |
| --- | --- |
| [p5_combination_run.py](../ros_ws/p5_combination_run.py) | 每子例新Master/进程、新run与输出目录，监督期限、实际进程解释器和退出审计；缺省运行33个A/B子例 |
| [p5_ros_case.py](../tests/p5_ros_case.py) | 测试控制台：只按inputs调度源状态/clock/显式逆观测/故障，观察公开消息/服务与具名测试诊断，不读expected决定动作 |
| [p5_ros_nodes.py](../tests/p5_ros_nodes.py) | tests专用sensors、perception、terrain、阻塞服务proxy及错误clock来源适配器；各角色在独立进程调用所属层入口 |
| [p5_test_engine.py](../tests/p5_test_engine.py) | 可被真实spawn worker承载的CPU后端故障替身，仅placeholder分支，不注册research |
| [p5_checkpoints.py](../tests/p5_checkpoints.py) | 执行后才读取的独立检查点比较器、实例符号绑定和TCPROS连接屏障 |
| [p5_map_call.py](../tests/p5_map_call.py) | 真实同步MapQueryClient的独立进程；外部期限到达后由测试监督器终止，不冒充客户端自行取消 |
| [p5_public_replay.py](../tests/p5_public_replay.py) | 在独立离线进程真正执行现有占据/地形回放，比对完整公开收据；不读取场景expected |
| [test_p5_checkpoints.py](../tests/test_p5_checkpoints.py) | 8项比较器/身份/上界/连接反例测试 |

## 2. 实际链与边界

A：测试Simulation源通过ROS发布原始world_ned/body_frd AircraftState和clock；
tests sensors薄包装复用既有SensorFixture的状态适配/门控，按本次观测生成Radar/IR、真实调用build_sensor_bundle，
通过ROS给生产感知包装；感知真实执行placeholder/输出校验/worker，再通过ROS进入生产M1节点。
没有直接发布SW-01保存的Bundle来代替该链。运动点/位姿年龄/缺IR等来自显式测试输入，
不是Gazebo/PX4飞行动力学或真实传感器物理模型。

B：具名测试逆观测生产者通过ROS送生产M4节点，完整保留非零map←odom注册、区间/缺失及原证据时间。
不经过Radar/IR，也不把placeholder域改名成逆观测域。A和B各自独立Master/run，互不继承地图。

TerrainProvider并行只接基础设施clock；测试TerrainNode子类在每个接收clock后调用原有tick并发测试ACK，
维持原有0.5s墙钟心跳、1s接收超时、授权/注册/实例门控。ACK用于离散调度确认，不更改公共协议或期限。
状态、中心查询、pin与整组结果由公开TerrainClient/Transport消费；application不读地形私有配置或缓存。
测试控制台可观察多层话题用于验收，不作为可部署application节点。

各组启动前检查实际ROS图：唯一clock发布者，map只消费占据，terrain只消费clock，perception只消费Bundle，
sensor只消费源状态/clock，在线无LiDAR/target/observed_mask旁路。不生成定位/TF新权威，不增加占据融合或地理注册。

## 3. 调度屏障、故障与观测

节点ready参数之后仍须检查getBusInfo中真实已连接的出站TCPROS：Bundle到感知和观察器、
占据到地图和观察器都要求两个连接，快照/诊断/clock ACK也须连通。仅Master注册或“有一个连接”
不能证明业务下游已接通，禁止首帧丢失后补发或忽略缺失收据。

事件保留SW-01整数业务时间和wall_ns。wall_ns定义相邻调度点的最早间隔；依赖ACK未完成时等其完成，
不强行追赶已过的墙钟计划。实际dispatch/completion单调时间另存，不能拿声明墙钟冒充实测时间/延迟。
所有1ns边界靠消息的整数时间实现，不靠sleep精度；45s子例期限独立于这些功能事件。

测试后端在真实输入链上注入坏输出、异常、慢任务；不可信子例把实际Bundle的Context clock显式改坏，
生产信任校验拒绝，无占据输出。可信后端错误产生unavailable，地图不提交；没有fallback。
CPU慢任务使用原有1活动/0队列worker，诊断从其active_pid/discarded_results取得；
实际公开占据收据核对较新busy对旧输出的抑制与恢复。

S07地图阻塞由测试服务proxy持有真实调用；隔离的MapQueryClient先在业务clock前预热，
服务端收到实际请求后才开始500ms外部期限。期限后先SIGINT，必要时SIGKILL，仅作用于该新建查询进程组，
wait回收并记录PID/信号/退出码。这是测试隔离处置，不表示旧客户端拥有deadline或底层调用能被取消。
地形仍用原有单未完成调用机制，1s调用超时/迟到结果隔离不变。

比较器消费执行后保存的实际事件收据；身份/时间/revision/flags精确比较，概率按float32映像，
M3分数界按既有数值精度核对，物理高程13与13.0等值且不接受bool。
`recording.event_ceiling=33`是上界断言，实际值来自manifest.event_count，不能把输入预算33回显为实测数。
`declared` owner/封存数量继续仅作独立生命周期说明，不伪造公共字段；通过公开cell与查询检查其可见后果。

## 4. 两种独立执行回放

每例的真实OccupancyObservation、MapSnapshot及成功传输的MapQuery收据单独保存。
执行新地图实例的公开replay_observations，逐字段比较快照/查询、原证据时刻、质量和revision；
传输失败封套不送地图业务回放。公开查询仍由应用客户端校验，不把其本地错误当服务端响应。

S08正常窗口由真实Provider录制三文件，关闭后在另一进程真正执行replay_recording。
超64事件或v1不能表达的来源错误保持incomplete，严格回放在创建Provider前拒绝；
篡改子例复制本次记录到新目录，只修改副本里合法外形的expected高度，执行回放必须发现不一致。
原始记录与全部失败目录保留；没有expected驱动安装、截尾补全或把两种协议拼成一个协议。

## 5. 运行与产物

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -c 'import sys; print(sys.executable); assert sys.executable == "/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python"'
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/p5_combination_run.py
```

默认端口11721，若被占用直接拒绝，使用`--port`选择其他空闲端口；不清理既有进程。
可用`--cases S01.normal S06.arithmetic S08.record`执行具名子集，报告明确full_ab_matrix=false；
S09/C输入在本入口明确拒绝，留给SW-03。

新目录`.runtime/runs/p5-combination-<时间戳>/`包含测试源码副本、每例冻结inputs/independent-expectations、
实际图、逐条公开JSONL、事件收据、完整比较、地图/地形回放、命令/解释器/退出与清理结果。
每话题256条/总16MiB收据超限则失败，不能静默采样；业务与录制各自沿用冻结限额。
仅使用本仓已有`.runtime/ros`生成类型，本轮没有构建外层工作区、安装依赖或计算Hash。

每例单独子进程，外层45s到期先让worker进入finally回收其自有节点，必要的兜底只匹配该会话命令/PID/进程组。
正常业务节点清理与测试故障的隔离查询终止分别记录，不隐去受控SIGKILL。
失败不会重用目录或自动换种子冒充成功；修复后另开验证目录。

## 6. 未验证能力

SW-03的S09原生Gazebo/RViz窗口、图故障与新run交接尚未在本轮执行。
本轮没有使固定飞机联动PX4/JSBSim，没有连接真实设备/DEM或运行研究模型，
没有共同地理注册、占据辅助融合、机载资源/20ms目标或完整Phase 4/5验收结论。
后续按总体计划先完成SW-03，不回到因外部数据缺失而暂缓的研究质量任务。

## 7. 本轮实际结果

最终`.runtime/runs/p5-combination-20261029T120350694666/`的33/33 A/B子例通过：
244执行事件、86检查点、216项冻结预期比较；148条占据、143份快照、14条成功传输地图查询
经33次独立地图执行回放逐值一致。实际地形服务收据26条，33例常规节点清理及解释器审计通过。
S08正常记录20事件逐值执行回放；溢出64事件及来源错误9事件保持incomplete并在执行前拒绝；
篡改副本11事件保持合法schema但执行比较失败。上界33与上述实际20分开报告。

旧默认inference入口实际兼容及清理通过，目录
`.runtime/runs/local-map-query-inference-20261029T121241634503/`。
本轮新增8项比较器/屏障测试；P5定向39项及全仓813项通过，
日志位于`.runtime/runs/p5-sw01-20261029T121200474234/`。
最初的装配失败、外部调用取消和一次自动权限审批超时保留于实验记录；未改冻结预期来消除失败。
