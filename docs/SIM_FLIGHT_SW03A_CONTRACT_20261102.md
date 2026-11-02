# 公共 flight v2 离线合同与严格 codec

日期：2026-11-02；版本：v0.1；任务：SIM-FLIGHT-SW-03A；主责任：integration_engineer。
状态：已完成（离线软件范围）；实验：[EXP-20261102-001](../experiments/2026-11-02-sim-flight-v2-contract.md)。
依据：[原方案第5/7/8节](SIM_FLIGHT_DESIGN_20261029.md)、
[初始化分工](SIM_FLIGHT_INIT_DESIGN_20261030.md#8-实施分工与独立预期)、
[INIT-TIME交接](SIM_FLIGHT_INIT_TIME_SW01_DELIVERY_20261030.md#6-下一任务与未验证能力)、ADR-044。

## 1. 交付与分界

新增公开 `ufm_flight_contract`，位于已有 `uav_fusionmap_sim_scene_msgs` 包内。
逻辑校验、固定profile和端点声明不导入ROS；codec只在显式转换/序列化时加载真实生成类型。
没有插件、ROS节点、命令客户端或新运行装配；本轮没有推进FDM、启动30/40秒准备或采样。
旧25份 `.msg/.srv` 定义、v1合同、旧profile、默认入口和既有运行产物保持。
`SceneFrame.PROTOCOL_V1`等生成常量仍为1；新codec显式写入 `protocol_version=2`，不修改旧常量。
私有 `diagnostic.v2` 与本公共v2无替代关系；公共AircraftState仍沿既有0.1字段语义。

问题是旧运动profile固定250步/1秒、8m锚点，无法表达已设计的地面准备和延迟采样。
实施范围限于ROS层独立公共合同、配置、离线测试及中文文档，复用旧纯字段校验和公开state转换；
没有更改simulation/sensors/perception/mapping业务实现。默认关闭由“无运行消费者/无默认装配”实现。
恢复时显式使用旧v1入口；本轮新包不被旧codec或默认launch导入，历史字节无需迁移。

## 2. 逻辑合同

公开函数为 `validate_frame`、`validate_request`、`validate_ack`、`validate_response`、
`capture_step`；支持四种codec名称 `SceneFrame`、`SceneStepRequest`、`SceneStepResponse`、`SceneCaptureAck`。
所有嵌套对象要求精确键集；拒绝LiDAR、target、observed_mask等额外字段，含嵌套隐藏形式。
整数拒绝bool/float，文本检查UTF-8字节/空白身份/NUL，向量要求有限数与固定形状。

| 对象 | 字段与约束 |
| --- | --- |
| SceneFrame | protocol_version=2、state、step_index、registration_id、angular_velocity_flu；步号0..10000 |
| state/header | 原AircraftState逻辑字段；run非空、clock=`sim:<run>`、schema=0.1、timestamp=step_index×4000000ns、sample_id=`scene.frame:<run>:<step>`、scene_world/simulation/valid/空reason |
| state几何 | position为scene_world ENU米；orientation_xyzw为base_link FLU到scene_world，范数误差≤.001；linear_velocity与angular_velocity_flu为base_link FLU，单位m/s和rad/s；state_source=ground_truth |
| state质量 | confidence=None；uncertainty精确为unavailable、空kind/unit、value=None、source=jsbsim_scene_truth_no_covariance_v1；不能补造质量 |
| SceneStepRequest | 仅frame；执行请求与帧使用同一严格合同 |
| SceneCaptureAck | protocol_version/run_id/clock_id/step_index/measurement_timestamp/sensor_kind/published/reason；kind严格1或2，published严格bool；成功空reason，失败具名小写reason；成功和失败均只允许采样步且时间等于本步原时刻 |
| SceneStepResponse | accepted/reason/applied_frame/radar_timestamp/infrared_timestamp；必须有真实已应用的v2帧；时间可为None，存在时须属于本采样步；成功采样须两时间齐全，准备步须两者None；失败可保留本步已实际采集的一侧时间 |

ACK可显式绑定frame；response可显式绑定request，核对run/clock/step/header/注册及实际读回几何。
应用位置/速度/角速度容差1e-9，姿态按q与-q等价比较、分量容差1e-12；这不是状态机或采样屏障。
codec无请求时只检消息自身；运行端必须在SW-03B逐次传入绑定并核验发布者、连续性和迟到收据。

### 无版本失败响应的处理

现有 `SceneStepResponse` 外层没有protocol_version，原v1允许 `applied_frame=None` 的失败响应。
这种字节没有v2身份，无法在保留消息布局且不修改v1的条件下实现双向版本区分。
因此v2严格拒绝无applied_frame响应，即使给出request绑定也拒绝；不能为携带版本伪造“已应用”。
SW-03B必须把应用前校验失败作为ROS服务错误/事务失败结束；只有实际已应用v2帧的后段失败
才能返回accepted=false并保存真实applied_frame/部分采样收据。源监督器停止，不提交失败tick公共clock/state。
本轮只冻结该合同，未实现服务错误分支。所有合法v2响应因此有嵌套版本2，旧v1 codec将拒绝。

## 3. 坐标、时间与固定profile

`configs/sim_flight_scene_fixture.json` 的schema为 `sim_flight_scene_fixture.v2`，
profile_id为 `sim-flight-scene-observe-v2`，fixture_only/simulation_only/observation_only=true、
commands_enabled=false。它是SW-03B的有界元数据，不是运行入口或可调飞行配置器。
`load_profile`限256KiB输入、深度8、8192节点，并拒绝重复键、坏UTF-8、非有限和未知字段；
`validate_profile`逐字段逐类型匹配固定值，旧v1 profile与新profile双向拒绝。

冻结注册 `jsbsim_cg_to_flight_enu_v1`：以初始化ECEF位置、大地纬度和经度固定ENU基，
JSBSim虚拟CG FLU原点的scene锚点为 `[0,0,0.5]m`，step0必须恰为该锚点。
后续位置要求z>.2m、距锚点三维距离≤250m；这是场景几何界，不能代替源CG AGL或飞行安全包线。
LSZH地面基准419.2m/初始AGL .5m来自原已批准IC；本轮不实现ECEF转换、不读取DEM或安装TF。
scene_world到odom仍需显式注册，唯一动态TF继续由原state_adapter拥有，不能把两坐标系默认等同。

4ms一步，最多10000步/40秒；不重置、不裁剪源时间，不隐藏前30秒。
仅 `step>7500 && step%25==0` 允许采样，固定7525..10000共100点，即30.1..40秒。
准备期每个SceneFrame保留原时间；无Radar/IR/ACK/Bundle表示尚未采样，不能写成valid空帧、free或可用地图。
未来运行从0起保存原FDM/SceneFrame/clock/state，并经成功事务后提交；本轮表格不是实际运行证据。

profile同时冻结Gazebo 1ms步、Radar安装[.8,0,0]、热光学四元数[-.5,.5,-.5,.5]、
每流12288收据、控制/阶段4096事件、单记录16KiB、控制日志64MiB、全订阅wire128MiB、
全产物512MiB/case；启动60秒、首采样3秒、事务1秒、case240秒墙钟。
SensorBundle配对仍为Radar/IR≤5ms、同tick pose_age=0、等待≤40ms。
预算只是声明和输入校验，尚无长窗运行资源证据；SW-03B须补总预算监控与套件范围，不能据此宣称PERF。

## 4. 独立端点合同

`endpoints.ENDPOINTS`为只读名称/类型表，`validate_endpoints`只接受精确清单。
服务和话题均未注册；生成类型相同意味着ROS布局相同，不代表v1/v2语义可混用。

| 用途 | 冻结端点 | 实际生成类型 |
| --- | --- | --- |
| 逐步请求/响应 | /uav/flight/scene/step | uav_fusionmap_sim_scene_msgs/SceneStep |
| 应用帧镜像 | /uav/flight/scene/frame_applied | uav_fusionmap_sim_scene_msgs/SceneFrame |
| 采样回执 | /uav/flight/scene/capture_ack | uav_fusionmap_sim_scene_msgs/SceneCaptureAck |

旧 `/uav/scene/*` 继续v1。SW-03B需独立插件编译/显式选择、共同事务锁与同步帧安装，
保留单发布者身份核验、真实ROS ACK、成功后唯一clock/state提交和state_adapter唯一TF。
ACK仅承载身份、时间、发布完成状态，不承载原始点云、IR、训练标签或地图业务。

## 5. 严格codec与实际验证

`to_ros/from_ros/serialize/deserialize`使用原实际生成类，要求精确消息类型、字段类型/数组形状。
先做4096字节总界及线格式扫描，再调用genpy解码；字符串128字节、reason256字节、
未知/非零uncertainty变长数组、非规范bool字节、非有限、负时间、截断/尾随字节均拒绝。
缺失confidence的数值槽必须为+0，未采集timestamp槽必须为0，presence标志必须是真bool；
解码后复验逻辑合同和重序列化字节一致性，没有JSON/mock替代ROS验证或版本fallback。

先行[freeze.json](../.runtime/runs/flight-sw03a-oracle-20261102/freeze.json)保存独立输入/采样边界/拒绝预期、
245组独立struct编码的v2字节及20组旧v1真实字节；production_package_exists=false。
随后28项新测试通过；真实生成消息序列化/反序列化与双向拒绝、59文件逐文本保护检查通过，见
[验证报告](../.runtime/runs/flight-sw03a-oracle-20261102/verification-20261102T103722983660.json)。
构建仅在.runtime/ros，固定Python；本轮基线1090项、最终全仓1118项均重跑通过，日志见实验记录。
未启动ROS master/节点或插件，不把离线消息往返写成实际ROS运行图验收。

## 6. 修改文件

| 文件 | 作用 |
| --- | --- |
| ros_ws/src/uav_fusionmap_sim_scene_msgs/src/ufm_flight_contract/{__init__,contract,codec,profile,endpoints}.py | 独立逻辑、实际类型codec、固定profile与名称/类型合同，共5文件 |
| ros_ws/src/uav_fusionmap_sim_scene_msgs/setup.py | 同包安装新公开逻辑包；旧生成类型不变 |
| configs/sim_flight_scene_fixture.json | 固定观察profile元数据 |
| tests/fixtures/sim_flight_v2_expectations.json | 独立字面量输入、采样表、边界与拒绝预期 |
| tests/sim_flight_v2_fixture.py、tests/sim_flight_v2_offline_check.py | 测试专用独立struct字节、先行保存及真实genpy/旧源码复核 |
| tests/test_sim_flight_v2_contract.py、tests/test_sim_flight_v2_codec.py | 28项语义/字节定向测试 |
| 本文、experiments/2026-11-02-sim-flight-v2-contract.md | 中文交付与实验记录 |
| PROJECT_STATUS.md、docs/{DATA_FORMAT,SENSOR_INTERFACE,COORDINATE_SYSTEM,SYSTEM_ARCHITECTURE,DECISION_LOG,DEVELOPMENT_PLAN,EXPERIMENT_LOG}.md | 状态、公共规范与必要索引，共8文件 |

实施前按用户授权提交既有606文件基线e51c752；只补根.gitignore的/build/忽略规则，保留本机构建目录。
本轮功能交付独立提交，未推送；不把Git提交当外部备份/ENV-03验收。

## 7. SW-03B交接条件与未验证能力

下一项为SW-03B，需在其明确范围内完成下列工作：

1. 采用本v2生成类型/codec/profile与三个独立端点，原生插件两侧实施相同边界；
   测应用前服务错误、应用后部分失败与v1误接拒绝，不能复用旧插件后宣称v2。
2. 将原整数时间生产修复显式适配到最多10000步，重新核源码范围/预算和原1ns网格，
   不直接扩大旧2500步函数/宿主；同FDM、原始时间从0连续保存，不能隐藏准备或修戳。
3. 重新核长窗无控制准备/两个末检查点及实际armed=false/零执行器，冻结30秒时限；
   未就绪即停，不顺延30.1秒首采样，binding仍unverified、control_gate_accepted仍false。
4. 实施准备期禁采样、100点真实Radar/IR/ACK屏障和完整预算监控，缺ACK/超时失败不提交业务tick；
   验同tick SensorBundle/占据/地图查询、公开回放，准备期地图为unavailable，合法空帧不能变free。
5. 同源SceneFrame显式scene_world→odom注册与state_adapter唯一TF，禁止第二时钟/状态权威；
   测新run空地图、迟到ACK拒绝、停止History、故障/清理及旧默认入口兼容和原生窗口。

以上是交接要求，本轮未实现或执行。严格当前执行器周期绑定、非零控制因果、模式切换、arming、
真实离地/受控飞行仍属SW-04独立门槛，不能由本合同或旧10秒准备结果推出。
research继续fail-closed；真实模型/设备质量、DEM公共服务/地理注册/占据融合、正式PERF仍分别待验。
