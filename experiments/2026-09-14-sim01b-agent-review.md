# EXP-20260914-003：SIM-01B多agent方案与前置探针

日期：2026-09-14；状态：方案分析已完成，代码实施待确认。
主责任：Technical Lead；system_architect、simulation_engineer、sensor_engineer只读分析。
依据：用户要求“调用对应的子agents进行下一步”，[PROJECT_STATUS](../PROJECT_STATUS.md)
明确下一任务是SIM-01B具体方案。交付：[记录回放方案](../docs/SIM01B_RECORDING_REPLAY_PLAN.md)。

## 1. 分工与真实源码证据

| 责任角色 | 已完成分析 | 证据/结论 |
| --- | --- | --- |
| simulation_engineer | 实際源窗口、监督边界、启动/关闭、安全截止 | sim01_smoke.py:140与check_sim01_live.py:92/99目前只有180/150墙秒及30源秒目标，B需独立入口 |
| sensor_engineer | 首尾及全量逐样本对账、真实旋转/质量、排空 | check_sim01_live.py:109只反查adapted，:124只验姿态模长，:126缺完整quality，:103固定sleep；B补发布台账及完整次数/身份/字段 |
| system_architect | 单bag两种回放、clock权威、原run隔离 | 总方案:198-201已规定唯一clock；B1原样/B2复算分开，B2禁止重播历史适配结果 |
| Technical Lead | Conda bag依赖、字节往返、原生播放器、环境入口 | bag探针通过；普通rosbag play --help因参数进入ROS setup而失败，具体修复待确认 |

读取根规范、状态、架构及相关模块AGENTS，从真实入口和本机官方ROS代码判断。
对应角色通过本线程既有子agent续接任务，没有仅返回调度状态而结束工作。

simulation只读复算A样本：clock49.99337Hz/最大24ms，state20.00265Hz/最大60ms；
clock推进46.019999源秒，用50.704943墙秒，约0.9076倍。据此估算300源秒有效窗口
结束约316源秒、采样推进约348墙秒；该估算用于计划，不当实际B结果。

## 2. 二次评审采用的规则

- LIVE、B1原样回放、B2新sensors复算分为三个独立会话；1倍播放，不添加--clock/loop。
- bag索引是记录器单调经过时间，消息timestamp/Clock内容保持原样，sidecar审计记录序号。
- T0由源发布台账首valid确定，首接收必须对应；T1为首源样本达到300秒跨度，禁止跳过缺首帧。
- publish返回台账证明调用/入队，非网络ACK；台账、接收、bag重读和回放比较集合、次数及话题内顺序。
- 冻结窗口后先停源/封存台账，sensors继续排空，然后停止sensors；记录器最后封存并重读bag。
- 同一串行路径分配记录序号/接收时刻/写入，writer有界；记录或审计错误必须失败。
- 未知quality全部元数据保留；四元数比较实际旋转且允许整体q/-q，不只验模长。
- 600绝对源秒/900墙秒、原源/队列门槛保留；不把B复算称源断流看门狗验收。

源/sensors分别启动的必要性：现有sim01_state.launch把两层都置为required；若同一
roslaunch里正常停止源，可连带结束适配，故B采用两份独立薄launch。

## 3. 已执行轻量探针与失败

Python为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，使用sim01_env.sh。
没有启动ROS Master、300秒仿真、训练或依赖安装。

| 探针 | 实际结果 | 边界 |
| --- | --- | --- |
| 模块导入 | rosbag、rosbag.bag、roslz4、Crypto、Cryptodome、rospy、rospkg通过 | 仅导入，不证明实际回放 |
| 临时bag写读 | 3个实际A的clock/source/adapted消息，显式整数索引、序列化字节往返精确 | /tmp新文件，非现场300秒记录 |
| 原生播放器库 | /opt/ros/noetic/lib/rosbag/play动态库解析无not found | 尚未执行ROS播放 |
| 普通CLI help | `bash ros_ws/sim01_env.sh python /opt/ros/noetic/bin/rosbag play --help` exit127 | 环境入口参数泄漏，尚未修复 |
| 隔离help解析 | 以Python play_cmd传入拼接的help参数，退出0，正常输出帮助 | 只验证解析器/选项，不能当普通入口修复通过 |

根因：ros_ws/sim01_env.sh:13在用户位置参数仍存在时source配置；
configs/sim01_environment.bash:13进一步source Noetic setup，官方setup.sh将未引用
$@传到_setup_util.py。该解析器:254-258识别--help，usage被生成shell脚本随后执行而失败。
且官方_setup_util.py当前shebang为/usr/bin/python3；A曾抽查的8个活跃进程是Conda，
该结果不包含环境加载期间这一短命helper，不能据此声称初始化所有Python都已覆盖。

提案前置将参数数组与环境装配隔离，已有显式搜索路径配合已核对Noetic标准元变量，
替代隐式setup helper，保持工程Python为Conda。system_architect只读核对允许该最小
修复，但须验证参数原样、CLI help、元变量、包发现、既有44项/11 ROS fixture及catkin。
本轮尚未修改任何环境入口代码，不以绕过help故障的探针当修复完成。

## 4. 产物与保护

```text
.runtime/logs/sim01b-plan-20260914/
  bag-probe.json / ros-baseline-vars.json / rosbag-play-help-safe.txt
  source-files-before.txt / before/ / external-before.json
/tmp/ufm-sim01b-bag-probe-6kck5hz0/probe.bag
```

本轮38个实施文件按snapshot逐字节核对一致，外部研究仓库与原PX4仓库Git状态前后相同。
system_architect首次读规则时误重定向到/tmp/sim01b-architecture-rules-read.txt，已报告，
临时文本按指示保留；没有仓库代码/配置修改。没有删除旧运行、研究数据或checkpoint。
当前分支feature/engineering-initialization仍无首次提交，user .vscode保留，未提交/推送。
实际源码及外部仓库保护、文档检查结果写本轮日志；忽略和本地快照不等同独立备份。

## 5. 修改文件、检查与风险

本轮仅工程管理文档：

1. docs/SIM01B_RECORDING_REPLAY_PLAN.md：新增具体范围、数据时间、分工和验收，作为确认依据。
2. 本文件：新增agent结论、真实失败/探针、证据及边界。
3. PROJECT_STATUS.md：登记B方案完成、实施待确认，不将探针写成300秒运行成功。
4. docs/DEVELOPMENT_PLAN.md：连接B方案及保持B/C/D退出门槛。
5. docs/DECISION_LOG.md：ADR-P009记录B提案，未接受实施或冻结Phase 1版本。
6. docs/EXPERIMENT_LOG.md：索引本次方案分析及轻量IO检查。

验证方法：检查本地Markdown链接、12份AGENTS七项、文档状态/阈值一致性；比较本轮
实施源文件snapshot字节及外部Git状态，确认代码未改。实际结果：39份Markdown、233个
本地链接和12份AGENTS七项规则检查通过；38个实施文件逐字节一致，外部仓库状态一致，
错误数为0。结果见本轮document-validation.json。Conda下三类消息的bag字节与时间索引
往返检查通过；标准rosbag CLI help因既有参数泄漏失败，已纳入待确认修复范围。

主要风险是异步尾部缺失、双时钟、过期排队及未解释丢帧；本方案通过分层关闭和多方
对账验收。环境元变量替代可能遗漏hook，须前置核对实际Noetic后通过功能检查。
R-10、ENV-03独立恢复/第二副本、未知协方差、实机原点、PERF-01和GPU保持原责任/日期。
未执行300秒记录、真实回放、异常整run停止或长时/高速飞行，实施确认后分别留新证据。
