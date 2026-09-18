# EXP-20260911-003：仿真候选方案与依赖解析核查

日期：2026-09-11；类型：静态源码/依赖模拟/工程文档检查；主责任角色：system_architect。
任务：ENV-02；状态：方案与只读核查已完成，未安装、构建或运行仿真。

## 1. 目的、输入和授权范围

用户在ENV-01交付后要求“下一步”，本轮按预告推进ENV-02候选版本和最小验证方案。
输入为根/模块AGENTS、PROJECT_STATUS、架构/数据/时空契约、ENV-01清单、本机固定
PX4与桥接源码、APT缓存和官方源码/版本说明。输出见
[SIMULATION_VALIDATION_PLAN](../docs/SIMULATION_VALIDATION_PLAN.md)与ADR-006。

本轮只新增/更新工程文档并进行只读查询，不改变公共数据字段或分层，不编写算法、
运行节点或启动脚本，不安装软件、修改外部源码或终端、修复驱动、训练或运行仿真。

## 2. 版本与过程记录

- UAV-FusionMap：feature/engineering-initialization，尚无首次提交，保留未跟踪文件。
- PX4：1c8ab2a0d7db2d14a6f320ebd8766b5ffaea28fa，对应本机v1.13.3。
- 桥接：68de2cc63ded9a0d6641d45e9eb3ed2b43454cba。
- 在线检查：MAVROS 1.20.1固定tag的传输/时钟/位置源码及安装说明；JSBSim v1.1.13
  官方发布页；ROS REP-2000。源码存在不表示已安装或运行，具体链接见方案。
- 预编辑副本与原始状态记录：/tmp/uav-env02-c4id_5g9；仅本轮临时恢复用途。
- 数据集、模型、随机种子、实际飞行配置：不适用，未执行算法或飞行。

| 检查 | 实际方法 | 结果及边界 |
| --- | --- | --- |
| 规则/契约 | 读取根和涉及目录AGENTS及DATA_FORMAT/SENSOR_INTERFACE/COORDINATE_SYSTEM | 方案使用既有五层契约，源状态保留NED/FRD后交sensors适配 |
| 版本路线 | 现场PX4/桥接、历史CI配置、ROS官方支持期 | Noetic为优先验证候选；未证明实际兼容，Humble/Jazzy为替代路线 |
| 状态流 | rg定位并按行阅读ODOMETRY.hpp、HIGHRES_IMU.hpp与simulator_mavlink.cpp | 找到估计状态、采样时间、坐标与时钟传递证据；速度协方差仍有TODO |
| 时钟与ROS传输 | 读取MAVROS固定tag的sys_time.cpp、uas_timesync.cpp、mavros.cpp | 内置/clock使用Unix时间；原始消息可承载源payload，外层header是接收时刻 |
| 位置同步 | 读取MAVROS local_position.cpp的真实处理函数 | local_position/odom读取缓存姿态，不能证明各字段同采样时刻 |
| 启动行为 | 检查sitl_run.sh、setup_jsbsim.bash、rascal.xml、px4-rc.mavlink | 原脚本含同名进程终止及隐藏stderr；instance 0遥测端口为14580→14540 |
| 时间范围 | 检查SendSensorMessages(int)并查询本机ctypes.c_int大小 | 4字节；32位微秒边界为2147.483647秒；静态风险，未运行触发 |
| 运行节奏 | 阅读JSBSimBridge::Run | elapsed_time使用开始减结束，实际倍速需测；未作性能结论 |
| 依赖 | apt-cache policy及apt-get --simulate | 核心MAVROS方案新增7包、升级0、移除0；未下载或安装 |
| geoid | 查询/usr/share及/usr/local/share的GeographicLib/geoids/egm96-5.pgm | 两个标准路径均未发现；不排除自定义路径，节点加载待验证 |

实际执行的依赖模拟命令：

```bash
apt-get --simulate --no-install-recommends install ros-noetic-mavros=1.20.1-1focal.20250520.005419
```

退出码0。完整本轮输出保存在/tmp/uav-env02-c4id_5g9/apt-mavros-simulation.txt，
7个新增候选及版本完整抄录在方案第3节，作为持久记录。包含mavros-extras的早期比较
模拟也退出0，预计新增8包；最终最小路线暂不包含该可选包。
APT未刷新缓存，模拟成功只证明当前缓存下的依赖解析，不证明下载仍可用或节点可启动。

JSBSim v1.1.13发布页可读取，列出Focal amd64资产支持；部分资产列表/源码页面获取
未成功，因此未填造完整开发包文件名或声称已经取得包。SIM-00A把资产内容与来源
复核列为安装前置，不提供未经核实的下载/安装一键命令。

## 3. 本轮交付与结果

| 交付目标 | 实际结果 |
| --- | --- |
| 候选组合和比较 | 选定Noetic/PX4 v1.13.3/JSBSim 1.1.13/MAVROS 1.20.1为优先验证组合；正式运行基线待测 |
| 状态/时间/坐标方案 | 源ODOMETRY解码、HIGHRES_IMU采样时钟、sensors转换、质量不可用、重置与回放约束已定义 |
| 执行范围 | 明确独立源码/构建/运行位置、7包依赖及JSBSim/geoid资产、进程与日志责任 |
| 可测量步骤 | SIM-00A/B、SIM-01A—D有输入、输出和短测/持续性门槛；性能预算仍由PERF-01确定 |
| 维护和恢复 | 增加归档/恢复检查、2026-10-15与2027-01-15复审节点，保留独立ROS 2替代路线 |
| 实际运行 | 未执行；不能由本轮文档审查关闭Phase 1、GPU、真实感知或高速飞行验收 |

## 4. 文件修改清单

| 文件 | 原因 |
| --- | --- |
| docs/SIMULATION_VALIDATION_PLAN.md | 新增版本候选、接入设计、最小验证与维护方案 |
| experiments/2026-09-11-simulation-plan-review.md | 新增真实静态/模拟检查和结果边界 |
| PROJECT_STATUS.md | 登记ENV-02设计完成、新风险和SIM-00A准备任务 |
| docs/DEVELOPMENT_PLAN.md | 明确ENV-02结果、SIM-00/SIM-01子任务与前置条件 |
| docs/DECISION_LOG.md | 登记ADR-006验证候选决定，正式运行组合继续待验 |
| docs/EXPERIMENT_LOG.md | 添加本记录索引，保留历史记录 |
| docs/SYSTEM_ARCHITECTURE.md | 增加Phase 1具体方案入口，保持层级/公共字段不变 |
| README.md | 更新当前交付与下一步入口 |

文档验证通过：相对预编辑副本仅上述6份已有文档改变、2份文档新增，没有文档删除；
全仓27份Markdown的格式、代码围栏、冲突标记及131处本地链接检查通过，12份AGENTS
仍包含七项规则。任务/实验链接、候选版本、时钟/重置、维护日期和短测边界覆盖通过。
PX4、其桥接子模块和研究仓库的Git状态与本轮开始时一致。临时机器检查报告为
/tmp/uav-env02-c4id_5g9/documentation-check.json；本记录构成持久结果摘要。
本轮未新增业务测试，未执行节点、仿真、训练、GPU复测或Git提交。
恢复时比较临时副本，仅处理本轮对应文件；不通过git reset/clean处理尚未提交的仓库，
也不覆盖既有会话或外部研究数据。

## 5. 下一步与开放风险

下一项SIM-00A先完成依赖准备与隔离构建，ENV-03的精确忽略/产物保存规则必须在填充
运行目录前落地。具体安装事务与输出位置已经列入方案，实际变更仍按根AGENTS的
确认范围实施。R-01/R-08等运行风险保持开放；新增桥接时间范围风险在持续性验收前
必须处理，短测上限不等于修复。GPU查询结果沿用ENV-01当日证据，本轮未重复查询。
