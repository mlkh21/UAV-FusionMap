# 同FDM有界执行器诊断交付

日期：2026-10-30；版本：v0.1；任务：SIM-FLIGHT-SW-02；主责任：simulation_engineer。
状态：已完成（隔离诊断软件、实际短窗/断连接及兼容子范围）；实际执行器正向收据未就绪。
依据：[具体设计](SIM_FLIGHT_DESIGN_20261029.md)、[私有合同](SIM_FLIGHT_SW01_CONTRACT_20261030.md)、ADR-044。

## 1. 结果与边界

本轮已在新隔离构建中采集真实HIL原始字节、发送时间、初始属性、同一FDM的Run返回及前后时间。
正常250步/1s、断连接125步后停止均通过独立MAVLink解码/合同核对；未创建ROS/Gazebo图或新v2端点。
两组都没有HIL_ACTUATOR_CONTROLS回包，因此has_actuator=false、requested=null，不能写成观测到disarmed零包。
readiness=bootstrap_not_ready，binding_status=unverified，control_gate_accepted=false。
本轮未实际验证执行器→属性施加或当前周期时间匹配，不关闭严格控制准入或飞行验收。

## 2. 文件清单与隔离

| 新文件 | 用途 |
| --- | --- |
| [adapt.py](../simulation/flight_bridge/adapt.py) | 对三份源副本作唯一上下文适配；上下文不符或重复适配拒绝 |
| [diagnostics.h](../simulation/flight_bridge/diagnostics.h) | 本仓私有观察hook声明，不成为公共消息/服务 |
| [diagnostics.cpp](../simulation/flight_bridge/diagnostics.cpp) | 实际wire、接收身份/值、属性写入/读回、Run结果及停止收据 |
| [host.cpp](../simulation/flight_bridge/host.cpp) | 唯一FGFDMExec、私有FIFO next/quit、硬上限250步与terminal |
| [sim_flight_build.py](../ros_ws/sim_flight_build.py) | 独立复制桥接src/include，编译到.runtime/ros/sim-flight-build/<run> |
| [sim_flight_diagnostic_run.py](../ros_ws/sim_flight_diagnostic_run.py) | 显式正常/断连接装配、私有ground IC、监督期限及自有进程清理 |
| [独立预期](../tests/fixtures/sim_flight_diagnostic_expectations.json) | 250步/1s、IC、允许发送ID、终止及控制门关闭要求；先于运行保存 |
| [独立字节检查](../tests/sim_flight_diagnostic_checks.py) | pymavlink逐字节CRC/字段与收据核对、径向高度算例、JSONL重新读取 |
| [7项新增测试](../tests/test_sim_flight_diagnostics.py) | 真实源上下文/重复拒绝、IC保护/坏输入、独立字节及篡改反例 |
| [整组验证入口](../tests/sim_flight_stage_run.py) | 先冻结源码/预期，再两实际用例、旧真实线格式与可选全仓回归 |

另更新中文实验、PROJECT_STATUS、README、架构/接口/坐标/计划与ADR/实验索引。
既有429份源码/配置保持，旧25份定义/7入口不改；第三方原源只读，不用private/public宏或修改PX4核心。
构建保留第三方版权头和原始上下文，适配只落在本次新副本；不缓存回退到旧宿主冒充新机制。
若停止使用新入口，旧sim-motion-build、默认launch、地图和研究后端不受依赖影响；不删除历史产物。

## 3. 实际调用链及停止行为

监督器生成新的私有IC XML：AGL=.5m、地面419.2m、vt=0、Euler=[0,0,90]度并省略gamma。
本仓宿主创建一个FGFDMExec，隔离桥接持有其指针；HIL传感器和FDM推进仍使用既有插件/实际Run。
新路径只监听127.0.0.1:4560，连接后以getpeername读取实际peer端口；sysid/compid仍须由实际包验证。
宿主发送路径只准HIL_SENSOR(107)/HIL_GPS(113)，未主动发送heartbeat、arm、manual、模式或参数写。
PX4既有启动流程自己发来的HEARTBEAT/COMMAND_LONG是RX诊断，不是本仓向飞控发送的控制命令。

每个next先读取步前属性/源时间；真实发送后记录原始uint64微秒和单调墙钟，保存TCP发送/接收块原始hex。
只有本步确实收到合法执行器才调用既有SetActuatorCommands，并从实际SetCommandToProperty保存requested，
读回四属性后才Run。未armed要求16路零；坏身份/模式/flags/值拒绝，不把数据静默清零。
首次执行器前只在声明的零初始属性下bootstrap，500源步/5s墙钟界继续生效；本宿主额外限制250步。
首次执行器后缺包、连接关闭或poll墙钟超限均终止，禁止沿用旧值；SIGPIPE转为可记录的发送失败。
Run返回false或4ms±1ns/源网格检查失败同样停止，实际发生的数据保留，不回滚或改戳。
异常收据若无法符合严格schema，保留wire/原始文件与失败manifest，不改写成合法记录。

peer等待≤60s、单步监督≤2s（poll hook≤1s）、步循环≤30s、构建≤180s；
最多250条收据，原始wire≤128MiB/12288块、单块≤65535字节，监督artifact≤512MiB。
监督器显式每步等待6ms并以10ms轮询读取，记录其墙钟开销；没有隐藏预热、源时间跳变或实时性能结论。
初始元数据不送旧z>.5 Gazebo v1端点，不发布新clock/state/TF或向SensorBundle/地图传递执行器诊断。

## 4. 高度读回的修正

初始实际AGL约.4999999989m、大地高419.7000006361m、JSBSim ASL读回419.7023513543m。
ASL在本版本按地心半径减同射线海平面半径计算，不等于直接将AGL与地面数值相加。
用初始ECEF的(x,y,z)、本模型椭球半轴(a,b)独立核对：

```text
r = sqrt(x*x + y*y + z*z)
r0 = 1 / sqrt(((x*x+y*y)/(a*a) + z*z/(b*b)) / (r*r))
ASL = r - r0
```

椭球轴分别读回约6378137.0000002m、6356752.3141865m，另对WGS84参考半轴核对1mm界。
大地高按IC419.7m核对，AGL/地面与径向ASL分别核对1微米界；没有把原ASL误差容差调大到毫米。
旧8m运动注册不变；上述只是该fixture的局部基准诊断，不是DEM融合或新地理注册验收。

## 5. 最终证据与复现

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_flight_stage_run.py --full
```

最终[同源码整组报告](../.runtime/runs/sim-flight-sw02-stage-20261030T005946343885/report.json)，
[正常实际收据](../.runtime/runs/sim-flight-sw02-normal-20261030T005946760382/verification.json)、
[断连接实际收据](../.runtime/runs/sim-flight-sw02-disconnect-20261030T010008127477/verification.json)，
以及[旧协议/回归报告](../.runtime/runs/sim-motion-sw04a-20261030T010027175743/report.json)。

| 检查 | 最终实际结果 |
| --- | --- |
| 正常短窗 | 250条收据/250次Run成功/源时间1s；250个真实HIL_SENSOR；RX两消息，执行器0包 |
| 断连接 | PX4启动完成后第125步关闭本次PX4；第126条peer_closed，Run未调用；最后源时间.5s |
| 独立核对 | 真实MAVLink CRC/时间与缺失标志、初始高度/姿态及原始JSONL重读一致；两例wire共27950字节 |
| 新增/定向 | 新增7项，飞行32/32（含既有25项）、旧运动84/84通过 |
| 旧线格式 | 77组Scene真实genpy字节、36公共往返及18合成源转换通过 |
| 全仓轻量 | 935/935通过；不是ROS全矩阵重跑或正式PERF |
| 清理/隔离 | 最终四个自有宿主/PX4子进程退出、无强制信号；相关端口探针释放；本仓及第三方源文本不变 |

详细失败、修正和未验收能力见[中文实验](../experiments/2026-10-30-sim-flight-diagnostics.md)。

## 6. 未就绪门槛与下一项

本轮实际16路/armed/flags均缺失，不能声称已验证正向属性施加或时间对应关系。
独立合成MAVLink字节反例只检查审计器，不能替代真实PX4包。
源码显示GPS插件默认1Hz且updated条件为dt>1/update_rate，因此旧1s窗口内没有首GPS；
固定翼控制又依赖新vehicle_attitude及控制模式，PWM输出依赖control更新，发送端依赖输出和lockstep组件。
这些是待定位的依赖事实，尚无当前run内部uORB逐帧收据，不能把“无GPS”直接定为唯一原因。

下一项SIM-FLIGHT-DIAG-DESIGN-02（计划；主责任simulation_engineer）：沿保存wire/PX4日志与
估计/固定翼控制/混控/发送链只读归因，提出有明确输入和停止界的最小补证方案。
不重复相同1s用例充进度、不改PX4核心/参数、发命令或自动扩大窗口。
未得到实际回包与当前周期对应证据前，SW-03长窗运行和SW-04命令准入均保持未开放；
如需调整设计顺序或窗口，先交具体方案，不能凭本轮诊断passed直接启用。
真实研究质量、DEM/占据融合和正式PERF仍按原分界独立登记，research继续fail-closed。

后续DIAG-DESIGN-02已完成[只读归因/最小补证方案](SIM_FLIGHT_DIAG_DESIGN_20261030.md)。
下一项SW-02B只计划在原1s内取本次PX4的有界uORB快照；尚未实现/执行或开放长窗/控制。
