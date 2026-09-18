# EXP-20260914-001：SIM-01A多agent设计评审

日期：2026-09-14；主责任角色：simulation_engineer；统筹：Technical Lead。
类型：接口/源码只读分析、历史原始记录审计、设计文档检查。
状态：方案评审已完成，正式消息编码与实现待确认；未开展新的运行验收。

## 1. 授权与实际分工

用户要求“调用对应的子agents进行下一步”。实际调用现有三个子agent，分别独立
分析后复核汇总提案，不把角色清单当成已经完成分工的证据：

| Agent | 实际工作 | 结果 |
| --- | --- | --- |
| /root/system_architect | 公共契约与ROS消息、包布局、来源身份、终止事件 | 共用AircraftState；四个消息；补清终止事件独立身份与sensors优先失效处理 |
| /root/simulation_engineer | PX4源状态/时钟/协方差调用链及现有记录解码 | 确认启动两次reset、状态超前时钟与不完整协方差；提出预热和有界时序策略 |
| /root/sensor_engineer | NED/FRD转换、Body/odom原点及测试向量 | 确认双侧姿态变换和机体系速度；不冒充实际安装标定 |
| /root | 独立构建边界、文件责任、方案收敛、管理台账 | 写入[实施提案](../docs/SIM01A_IMPLEMENTATION_PLAN.md)，保留现行契约等待确认 |

全部子agent只读分析，无文件写入、仿真启动或第三方修改。主agent仅写管理文档，
保留feature/engineering-initialization尚无提交的状态，没有自动提交或推送。

## 2. 新证据

源记录为.runtime/runs/sim00b-20260912T123817/mavlink.jsonl，仍存在；对完整原始记录
解码的结果不应误记为只统计120.056秒验收窗口。主要发现：

- HIGHRES_IMU 6051条，源时间0.2—121.2秒，全部加速度/角速度更新位为63。
- ODOMETRY 2407条，源1/1、AUTOPILOT、LOCAL_NED/BODY_FRD，源时间严格递增。
- reset_counter为{3:8,4:95,5:2304}，1.256秒和6.007999秒发生两次启动阶段变化。
- 2130条状态到达时比最近IMU时钟超前，最大20ms；离线等待覆盖的队列最大1条，
  最大接收单调等待0.047989864秒，文件结束无待处理状态。
- 四元数模长约0.9999999338—1.0000001304；数值有限不等于坐标或质量已经全面验收。

审计方式：通过已有sim00a_env.sh使用系统Python逐行读取JSONL，以线格式筛选
105/331，再调用pymavlink common的decode(bytearray.fromhex(wire_hex))并筛选源1/1。
每条IMU释放采样时间已覆盖的待处理ODOMETRY；等待由receipt_monotonic相减。
这是历史记录分析，没有发布/clock、ROS状态或运行新的仿真。

PX4源证据（均相对.runtime/src/px4-v1.13.3，源提交保持既有基线）：

| 位置 | 事实 |
| --- | --- |
| src/modules/ekf2/EKF2.cpp:1018、1053—1064 | timestamp_sample来自该次输出；完整pose covariance置零后仅填位置对角，姿态传播TODO |
| src/modules/mavlink/streams/ODOMETRY.hpp:91—159 | 原始时间/估计类型/坐标，线速度按本报文姿态转Body，速度协方差旋转TODO |
| msg/vehicle_odometry.msg:34—63 | FRD Body到参考系的姿态方向，协方差排列和角速度参考系 |
| src/modules/mavlink/streams/HIGHRES_IMU.hpp:183 | 时间来自IMU采样；加速度不是未经处理的硬件原始数据 |
| src/modules/mavlink/mavlink/message_definitions/v1.0/common.xml的ODOMETRY定义 | 旧源没有quality字段，现代解码器补零不能成为置信度 |

## 3. 收敛方案与待确认范围

四个消息、两个薄节点，simulation输出源状态/时钟，sensors输出虚拟odom/base_link
状态；不发布TF，不新增角速度或研究算法接口。完整协方差/置信度保持不可用。
坐标公式与三个非平凡姿态样例经sensor agent独立矩阵核算，尚未创建实际单元测试。

10秒稳定源状态预热、100条缓存、0.5秒等待、2秒独立源流断流、60秒启动上限及
0.001四元数模长容差均为首次冒烟参数提案，不作为高速性能预算。
准备期仅允许估计器reset重计窗口；任何阶段源时钟回退均停止，ACTIVE重置终止run。
终止事件独立身份、沿同一状态话题失效传播，以及接收端时钟覆盖检查已纳入二次评审。

需确认的公共细化包括ROS编码、新sensors内部状态话题、虚拟原点约定及预热门控。
正式DATA_FORMAT/SENSOR_INTERFACE/COORDINATE_SYSTEM没有在本轮偷偷替换；确认后
再由各责任agent按文件所有权实施，主agent承担薄包装和集成检查。

## 4. 修改、验证与限制

新增docs/SIM01A_IMPLEMENTATION_PLAN.md和本记录；更新PROJECT_STATUS.md、
docs/DEVELOPMENT_PLAN.md、docs/DECISION_LOG.md及docs/EXPERIMENT_LOG.md。
目的为形成可审查的实现范围、责任和测试依据，未修改业务代码或重新构建。

本轮开始前文件快照与外部Git状态保存在.runtime/logs/sim01a-plan-20260914/；
结束检查验证文档链接/格式和允许修改范围，结果见其中final-check.json。
三个子agent完成二次复核，指出的终止身份、预热缓存及独立断流问题已在提案中修正。
本次没有实际消息包、节点或新运行结果，SIM-01A实现及SIM-01B/C/D仍未验收。
