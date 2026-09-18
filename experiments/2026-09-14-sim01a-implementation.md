# EXP-20260914-002：SIM-01A实现与Conda验证

日期：2026-09-14；状态：已完成；主责任角色：simulation_engineer。
Technical Lead负责集成、实验和台账，system_architect审查，sensor_engineer负责坐标与门控。
用户确认依据：“确认，默认所有python环境使用conda环境 Radar-Diffusion”。
方案：[SIM01A_IMPLEMENTATION_PLAN](../docs/SIM01A_IMPLEMENTATION_PLAN.md)；决定：ADR-009。

## 1. 问题、范围与实现

SIM-00B只证明原始遥测可运行，尚无系统采样时钟/状态契约；源是NED/FRD估计状态，
启动reset和状态先于时钟到达需显式处理。当前质量不能解释为完整协方差或置信度。
本轮实现四ROS消息、simulation源筛选/时钟状态机、sensors坐标/接收门控、两层薄节点、
独立catkin和有界轻量监督器。未修改研究算法、第三方桥接、地图或控制实现。

simulation只读取公开MAVLink入口，输出world_ned/body_frd AircraftState与唯一/clock；
sensors只消费源状态及基础设施clock，输出odom/base_link内部状态。采样纳秒不重写，
质量None/不可用元数据保留。准备期稳定观察，ACTIVE后致命故障停止valid并传播终止。
接收端排序等待、过期丢弃、终止清队列锁run；节点不发布TF、不绕过感知直连地图。

## 2. 环境与产物

- 分支：feature/engineering-initialization，仓库尚无首次提交，全部工程文件未提交。
- Python：Conda Radar-Diffusion，3.8.12，实际可执行文件python3.8。
- Noetic ROS库和既有项目MAVROS前缀，PX4 v1.13.3及SIM00B-INIT-01桥接副本。
- JSBSim 1.1.13，Rascal/LSZH，HEADLESS，速度因子1，未发送解锁/起飞命令。
- Conda模块：empy 3.3.4、catkin_pkg 1.1.0、rospkg 1.6.0、PyYAML 6.0.2、numpy 1.24.4。
- Conda激活禁用用户site；从既有安装复制pymavlink 2.4.49和CPython3.8 netifaces 0.10.4
  到.runtime/deps/python-radar，source.json登记来源，没有安装到Conda或系统。
- `.runtime/ros/{build,devel,install}`为本轮输出前缀；已验证build/devel，未验收独立install部署。
- 管理快照/日志：`.runtime/logs/sim01a-implementation-20260914/`；快照在部分消息文件已
  创建后建立，不能代替首次Git提交，也不是整个任务开始前的完整回滚基线。

## 3. 测试方式与实际结果

命令详见[RUN_SIM01A](../simulation/RUN_SIM01A.md)，均通过`sim01_env.sh`使用Conda。

| 验证 | 实际结果 | 证据 |
| --- | --- | --- |
| 独立catkin | 四消息生成及三个包构建通过；生成Python节点shebang为Radar-Diffusion | catkin-build-fixed.log、catkin-build-final.log |
| 源筛选与状态机 | 11项行为测试通过；包含CRC、源/帧、时钟、预热、重复、缓存、断流、reset及终止ID | all-unit-tests-final.log |
| 坐标与质量 | 14项通过；向量、非平凡姿态、q/-q、逆变换、原点、非法几何和来源保留 | sensors-checks.json |
| 接收时钟门控 | 12项通过；状态早到、排序、过期/超限、身份冲突、终止优先、跨run及回退锁定 | all-unit-tests-final.log |
| ROS消息往返 | 6项通过，真实serialize/deserialize；int64边界及None/空数组语义 | ros-contract-tests.log |
| 参数服务器 | 1项通过；配置可XML-RPC往返并保留10秒纳秒阈值 | all-unit-tests-final.log |
| 固定历史整链 | 45660行输入，6051 clock、2407 accepted odometry、2 preparing reset、2103对valid状态 | history-chain.json |
| 实际ROS fixture | 11检查通过：等待/覆盖、轴变换、重复、过期、终止绕过水位、清队列锁run | fixture run result.json |
| 本机静止联调 | 605源+605适配，2302 clock，valid跨度30.196秒，无致命错误、未解锁 | live run result.json |
| Python进程 | 抽查监督器及本次后代共8个Python进程全部为Conda实际可执行文件 | live manifest.json python_process_audit |
| 正常结束清理 | 本次直接子进程退出，已知端口全部释放；记录的Python后代PID后检无残留 | cleanup-audit.json、preservation-audit.json |
| 文档/语法 | 37份Markdown、217处本地链接、12份AGENTS七项、20个Python文件AST通过 | document-validation.json |
| 架构收尾 | AR-01至004代码问题已收尾；停止链、依赖、持续ERROR、质量来源复核通过 | architecture-review-final.json |

单元/契约总计44项。历史首valid=16.051999秒、末=121.152秒、无FAULT、门控无剩余。
实测首valid=16.059999秒、末clock=46.287999秒，状态时间、身份关联、坐标轴、单位
四元数与未知质量均检查通过。原始记录包含其他MAVLink ID，保留原始报文，不将所有
未知ID宣称为已语义验收。接收者的日志跨话题顺序不能替代门控决策，ROS fixture另验。

实际产物目录：

```text
.runtime/runs/sim01a-fixture-20260914T140538817010/
  result.json / fixture-states.jsonl / manifest.json / cleanup-audit.json
.runtime/runs/sim01a-live-20260914T140614282706/
  result.json / mavlink.jsonl / states.jsonl / clock.jsonl / diagnostics.jsonl
  manifest.json / cleanup-audit.json / sim01_state.yaml / 各子进程日志
.runtime/logs/sim01a-implementation-20260914/
  all-unit-tests-final.log / catkin-build-final.log / environment.json
  history-chain.json / architecture-review-final.json / preservation-audit.json
```

## 4. 失败与修复证据

1. 实现前源/坐标测试因库缺失失败，建立实现后GREEN；终止身份与质量来源追加断言
   各先得到失败，再以最小修改恢复通过。agent工具记录与sensors-checks.json可核对最终结果。
2. 首次catkin失败：CATKIN_TOPLEVEL下未设置顶层find标志，catkin_workspace命令未加载。
   补标准顶层查找标志后构建通过；原catkin-build.log保留。
3. 首次ROS fixture因Conda缺netifaces失败：
   `.runtime/runs/sim01a-fixture-20260914T140343369874/`。原包复制到项目后复试。
4. 第二次因ROS1参数服务器无法传10^10 int失败：
   `.runtime/runs/sim01a-fixture-20260914T140436620764/`。阈值改十进制字符串传输，
   节点还原int，语义不变，并加XML-RPC回归。该失败run的被中断observer旧result误报
   passed=true且checks为空，supervisor manifest exit=1仍判整run失败；旧产物保留。
   新脚本明确记录中断并要求完整11检查后才能passed，第三次fixture通过。
5. 只读review发现mavros依赖缺项、锁run周期诊断误报OK、quality来源丢失；分别补依赖、
   持续ERROR/致命诊断停止路径和质量元数据保留，原review及最终review均保留。

## 5. 潜在风险与未执行

本轮验收只到状态/时钟接口；协方差保持unavailable，odom/base_link是明确配置的
局部估计/虚拟轴原点，未证明实机外参或场景全局注册。待发布队列有界；接收身份账本
保存有限run，长期常驻内存需另验。Conda与项目依赖overlay可本机运行，异机恢复未验收。

尚未执行：300秒bag记录回放、暂停/倍速、实际源断流或接收回退导致整run停止、
40分钟持续性、高速飞行、传感器模型、感知推理或地图。终止ROS传播已测，停止链已
代码审查，不能称致命故障整run停止已实测。R-10桥接时间边界和节奏疑点保持开放。
GPU NVML问题、研究推理前置条件、性能预算和第二份资产副本保持原责任/日期。

原PX4及研究仓库Git状态前后相同；没有删除历史产物、修改Conda/系统安装、
修改用户.vscode设置、自动提交或推送。工程恢复仍须ENV-03建立独立保存和版本基线。
下一任务SIM-01B先明确300秒记录/回放方案，再按根AGENTS推进。

## 6. 修改文件列表

以下为本轮交付文件，包含工程实现、测试、规范及配套记录；生成运行产物另见上表。

```text
.gitignore
AGENTS.md
PROJECT_STATUS.md
README.md
configs/AGENTS.md
configs/ENVIRONMENT_INVENTORY.md
configs/sim01_environment.bash
configs/sim01_state.yaml
docs/COORDINATE_SYSTEM.md
docs/DATA_FORMAT.md
docs/DECISION_LOG.md
docs/DEVELOPMENT_PLAN.md
docs/EXPERIMENT_LOG.md
docs/SENSOR_INTERFACE.md
docs/SIM01A_IMPLEMENTATION_PLAN.md
docs/SIMULATION_VALIDATION_PLAN.md
docs/SYSTEM_ARCHITECTURE.md
experiments/2026-09-14-sim01a-implementation.md
ros_ws/AGENTS.md
ros_ws/bin/rosmaster
ros_ws/launch/sim01_sensor_fixture.launch
ros_ws/launch/sim01_state.launch
ros_ws/sim01_env.sh
ros_ws/sim01_smoke.py
ros_ws/src/CMakeLists.txt
ros_ws/src/uav_fusionmap_msgs/CMakeLists.txt
ros_ws/src/uav_fusionmap_msgs/msg/AircraftState.msg
ros_ws/src/uav_fusionmap_msgs/msg/ObservationHeader.msg
ros_ws/src/uav_fusionmap_msgs/msg/Quality.msg
ros_ws/src/uav_fusionmap_msgs/msg/Uncertainty.msg
ros_ws/src/uav_fusionmap_msgs/package.xml
ros_ws/src/uav_fusionmap_msgs/setup.py
ros_ws/src/uav_fusionmap_msgs/src/ufm_ros_contract/__init__.py
ros_ws/src/uav_fusionmap_msgs/src/ufm_ros_contract/codec.py
ros_ws/src/uav_fusionmap_sensors/CMakeLists.txt
ros_ws/src/uav_fusionmap_sensors/package.xml
ros_ws/src/uav_fusionmap_sensors/scripts/state_adapter_node.py
ros_ws/src/uav_fusionmap_simulation/CMakeLists.txt
ros_ws/src/uav_fusionmap_simulation/package.xml
ros_ws/src/uav_fusionmap_simulation/scripts/state_clock_node.py
sensors/ufm_sensors/__init__.py
sensors/ufm_sensors/clock_gate.py
sensors/ufm_sensors/state_adapter.py
simulation/RUN_SIM01A.md
simulation/ufm_simulation/__init__.py
simulation/ufm_simulation/mavlink_source.py
simulation/ufm_simulation/source_timeline.py
tests/check_sim01_history.py
tests/check_sim01_live.py
tests/check_sim01_ros_fixture.py
tests/test_sim01_clock_gate.py
tests/test_sim01_config.py
tests/test_sim01_frames.py
tests/test_sim01_ros_contract.py
tests/test_sim01_source.py
```

共55个工程交付文件；运行产物精确忽略，ros_ws/.catkin_workspace为生成标记已加入忽略。
