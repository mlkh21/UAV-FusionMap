# 初始化selector私有离线合同交付

日期：2026-10-30；版本：v0.1；任务：SIM-FLIGHT-INIT-SELECTOR-SW-01。
主责任：simulation_engineer；状态：已完成（独立私有离线软件/合成验证范围）。
依据：[具体设计](SIM_FLIGHT_INIT_SELECTOR_DESIGN_20261030.md)、ADR-044；
实验：[EXP-20261030-013](../experiments/2026-10-30-sim-flight-initialization-selector-contract.md)。

## 1. 交付与边界

新增独立selector fixture、recording/query/observation严格JSON合同、98项固定计划、
逐数组槽位不可用表示、前后设备表关联及原四门的离线组合评价。
先保存独立预期/原生基线，再实施；原476份源码/配置、84项合同/默认入口/宿主与公共消息保持。
新数据仅由tests合成生产、simulation私有纯函数校验、tests离线消费，不接在线状态/定位/地图或forward。
本轮没有新增daemon客户端/运行装配，没有启动FDM/PX4/ROS/Gazebo、准备期或控制发送。

[阶段报告](../.runtime/runs/flight-init-selector-sw01-20261030T125535247310/report.json)：
新增28项、飞行162/162、运动84/84、全仓1065/1065通过；
两组合成2500步/98事件实际文件重读、101次新私有JSON往返和旧真实genpy兼容通过。
阶段passed=true仅代表本离线软件通过；runtime_accepted=false，原实际准备失败不回填。

## 2. 新增文件与原因

| 文件 | 用途与生产/消费边界 |
| --- | --- |
| [selector fixture](../configs/sim_flight_initialization_selector_fixture.json) | 新显式观测profile、原完整物理profile、七检查点/13topic/七参数、原全部预算；不加载到旧宿主冒充新运行 |
| [flight_initialization_selector.py](../simulation/ufm_simulation/flight_initialization_selector.py) | 新严格封套/codec、原文逐槽投影、有界流/同run固定文件重读、设备关联和四门纯评价；无进程/ROS/命令IO |
| [独立字面量](../tests/fixtures/sim_flight_initialization_selector_cases.json) | S01—24分组、98计划/组编号、历史8处缺失、主实例1/gyro槽2/accel槽0及两类结果预期，先于实现保存 |
| [原生基线](../tests/fixtures/sim_flight_initialization_selector_native.json) | 10份msg、6份selector/传感器生产源全文及原质量语义片段；具名布局/分支预检消费者，不新增Hash |
| [合成输入工厂](../tests/sim_flight_initialization_selector_fixture.py) | 不导入被测parser/plan，沿独立字面量生成原文/预期；复用原tests物理输入和其他topic合成器，不改旧测试 |
| [新增测试](../tests/test_sim_flight_initialization_selector.py) | 28项，覆盖设计S01—24及物理终态/路径/畸形/故障状态分界 |
| [离线阶段工具](../tests/sim_flight_initialization_selector_run.py) | 核先行oracle、冻结合成输入后验证实际字节/文件、旧严格拒绝、既有真实genpy和轻量回归；不启动仿真 |

共7份新增源码/配置/fixture；当前快照483份，原476份逐文本相同。
配套新增本说明/实验，并更新状态、README、架构/接口/坐标、开发计划/ADR/实验索引及设计后续链接。
旧C++宿主、84查询包装/runner、9份原msg及其他公共协议/入口不改，恢复可显式选择旧入口，但同样nan仍会拒绝。

## 3. 精确合同与源检查

新schema为sim_flight_initialization_selector_fixture.v1、recording.v1、query.v1、observation.v1，
均使用同一sim_flight_initialization_selector_前缀；精确键集见[设计表](SIM_FLIGHT_INIT_SELECTOR_DESIGN_20261030.md#4-拟议独立schema文件与迁移)。
profile_id固定sim-flight-initialization-selector-observe-v1；simulation/fixture/observation_only=true，
commands_enabled/capture_active=false；run_id/clock_id、owner/argv、单位/时间和控制门按原严格语义。
原物理v1与新封套显式组合，禁止新旧query/observation/profile/header交叉接受或自动fallback。

selector 9槽数组按实例高水位A判断，A须1..9、primary须0..A-1；
combined/relative在范围内必须有限（combined>0），范围外必须准确nan且healthy=false。
healthy=false不能豁免范围内nan；relative可负/零，IMU误差有限值须≥0，零/负零不视为缺失。
四槽gyro/accel误差准确nan仅显式不可用，不借实例号、A或另一类设备表证明本类身份。
每处缺失保留固定长度数组中的null和有序field/index/native_token/reason四键说明，
原token只能nan，两个原因仅native_estimator_slot_not_seen/native_imu_slot_unavailable。
原文/投影逐值逐类型一致，null/说明一一对应；删除、重复、重排、错索引/原因或数值类型替换均拒绝。
其余字段非有限、NaN/inf/伪token、部分/重复字段和畸形文本仍拒绝；未发布、无载荷和质量不可用分开。
原estimator_status的vel/pos两标量仍只按原同块mask和三键缺失说明校验，未扩大该白名单。

sensors_status_imu完整11字段按原生uint64/uint32/uint8/bool和两组四槽float32解析，
两inconsistency全有限且非负；零ID槽必须inconsistency/priority=0、healthy=false，非零ID不得同类重复。
gyro和accel分别按其主ID在各自四槽中唯一匹配；同块零槽只说明该输出槽不可用，不声称物理硬件不存在。
verify_sources消费冻结10消息/6完整源及原4段质量语义，漂移即拒绝；仅验证源码/布局前提，不能证明任意二进制兼容。
后续实际装配仍须核对当前非受限SITL构建和宿主适配身份，本合同不静默支持受限max=2构建。

## 4. 查询、时序、关联与四门

98计划为125步先原七参数，再七检查点各13项，首尾sensors_status_imu夹住原11项。
组范围固定8—20/21—33/34—46/47—59/60—72/73—85/86—98；
逻辑before/after不改变原生topic名称；参数/token期望与原合同一致。
argv只固定listener --instance 0 <白名单topic> -n 1或七项param show。
owner前后/跨流保持，计数/顺序/无重试、原生整数/未来/倒退时间和Run后/下一HIL前落盘界严格校验。

checkpoint_ready先复用原纯判定函数（只读取事件字段，不伪造旧query或修改原全局），
再加前后A不变、故障标志均false和独立设备关联门。
两IMU表须完整/年龄≤200ms，前后设备ID向量和primary相同且匹配selector主ID；
主槽前后healthy=true、priority>0；两selector各相应误差须有限，其他槽与所观测ID可用性也须一致。
未发布/过期/设备变更/身份缺失或槽位矛盾可以保存结构合法的观察，但检查点不就绪。
association输出observed_stable_ids/unavailable/inconsistent及具名原因/原时间/两类槽，
selector_consumed_imu_timestamp_us始终null、exact_source_message_verified始终false。
前后观测一致不证明selector实际消费同一消息、没有中间变更或原子同tick。

原四门仍分collection_complete/input_settled/initialization_ready/output_chain_observed；
两个末检查点2000/2500、原连续250步静稳、姿态/样本增长/land/mode/选中健康/设备门保持。
另报selector_payload_complete，有数组缺失或selector正文不可用即false；非选中合法缺失不被填成健康数值。
合成就绪也始终binding_status=unverified、control_gate_accepted=false，不开放后续控制或飞行准入。

## 5. 文件、有界与停止

新selector-header.json固定引用同run的header.json、diagnostics/steps.jsonl、terminal.json和wire.jsonl，
原物理header/step/terminal仍用原codec。两header/terminal的run/clock、末step、原物理时间和查询边界关联校验。
新观测只在selector-queries/observations.jsonl；同目录存在旧queries即拒绝混合。
只接受固定相对文件位置；根/祖先或内部符号链接拒绝，不读任意路径或同级仓库。
load_recording统计全部产物及selector-queries含metadata的总量后按原界读取，
step≤16KiB/2500条/64MiB、event≤256KiB/98条、query含metadata≤16MiB，wire≤8192事件/16MiB原载荷、case≤256MiB。
wire这里只校验封套/十六进制和逻辑载荷界，MAVLink语义/真实包/物理逐值还需SW-02独立原始wire审计。
两组合成wire文件为空，没有伪造真实PX4包或将空文件当wire验收。

编码前检查文本、深度8/节点8192/list512，严格JSON重复键/非有限/坏UTF-8/过长整数及未知监督字段拒绝。
query_records硬上界仍128，精确合法条数98；新增14次不提高client200ms/group400ms或原全部预算。
墙钟build180s/startup60s/prepare60s/session120s/transaction1s，source10s/2500步及原1ns物理容差保持。
原check_budget纯guard可供下一运行包装在spawn前/保存后/next前调用；本轮只验证离线边界，不证明实际调度达标。
坏结构/身份/armed/非零/时间倒退或未来/超界仍停止，不把非法原文写正常事件；只读关联失败只否决就绪。
实际Run前停止/清理与13项400ms可完成性仍属下一任务，不能用离线codec通过替代。

## 6. 验证证据与交接

[先行oracle](../.runtime/runs/flight-init-selector-sw01-oracle-20261030T124951555793/report.json)在生产模块存在前保存24组独立预期、
fixture和原生基线；阶段工具逐字节核对，不用被测parser/plan产生预期。
原历史第30条仅作离线投影：新规则精确8个null/说明，旧codec仍probe_native_float；
[离线结果](../.runtime/runs/flight-init-selector-sw01-20261030T125535247310/historical-offline-projection.json)
明确historical_event_accepted=false，不改历史raw、合法事件数或manifest。

[ready](../.runtime/runs/flight-init-selector-sw01-20261030T125535247310/ready-result.json)与
[missing](../.runtime/runs/flight-init-selector-sw01-20261030T125535247310/missing-result.json)各2500条物理step/98事件实际文件重读。
ready例主实例1/gyro槽2/accel槽0，500个合成零执行器、四门全true、selector_payload_complete=false；
missing例物理输入静稳/采集完整但初始化和输出门false，整体false；两者消费消息验证false且控制false。
101次新JSON往返=profile/header/query各1+98个事件；这不是新ROS序列化或真实PX4准备运行。

28新增/飞行162、运动84、全仓1065通过；
[旧兼容报告](../.runtime/runs/sim-motion-sw04a-20261030T125603368174/report.json)含77组场景字节、36组旧公共往返、18合成源探针，
使用实际生成genpy，25份旧定义/7入口保持。没有重跑未改的旧实际PX4/ROS/Gazebo场景。
最终核对见[final-audit.json](../.runtime/runs/flight-init-selector-sw01-20261030T125535247310/final-audit.json)。

下一项SIM-FLIGHT-INIT-SELECTOR-SW-02（计划；主责任simulation_engineer）：新增独立显式98查询/runner，
复用原同FDM/IC物理宿主/硬门；先坏原文/期限/保存失败等离线停止，再一次新规则正常准备及断连接/期限故障。
须保存原文、原始MAVLink/逐步源物理与七检查点关联，独立审计、原入口兼容及自有进程/端口清理。
组超时或10s未就绪明确失败，不改IC/模型/噪声/阈值、扩窗、补采旧run或重复相同失败。
本轮未实现该装配/实际98采集、完整准备/姿态就绪、严格周期绑定/非零属性因果；
公共Scene v2/长采样、模式/arming/manual/离地及飞行仍留后续SW-03/04。
研究质量/真实输入/DEM/占据融合/机载资源继续独立暂缓，未安装依赖/Hash/改研究仓或提交/推送。

2026-10-30后续：[selector SW-02](SIM_FLIGHT_INIT_SELECTOR_SW02_PREPARATION_20261030.md)已新增独立实际装配，
59合法查询/1007 Run/582零包后1008条因原桥接微秒截断少1us而Run前停止，完整准备未通过且未重跑。
本私有合同的末组/固定资源链接组合边界先复现再修正，槽位条件/schema/预算不变；
新11/飞行173/运动84/全仓1076及故障兼容通过，下一项仅隔离发送端整数时间修复。
