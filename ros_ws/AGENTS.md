# ros_ws 模块规范

基线：v0.1；日期：2026-09-16；责任角色：integration_engineer。
先读[根规范](../AGENTS.md)、[项目状态](../PROJECT_STATUS.md)和[系统架构](../docs/SYSTEM_ARCHITECTURE.md)。

## 1. 模块职责

承载ROS消息定义、节点包装、参数加载、启动装配和记录回放。
SIM-01A使用Noetic，src承载四个状态消息及simulation/sensors薄节点。
Python默认Conda Radar-Diffusion，独立build/devel/install位于.runtime/ros；
不构建外层catkin_ws。正式Phase 1运行冻结仍需记录回放、异常和持续性验收。

## 2. 输入输出定义

输入为各模块公共数据对象和启动配置；输出为保持原语义的ROS消息、服务及运行连接。
话题和服务候选见SENSOR_INTERFACE，不将文档名称冒充已存在的接口。

## 3. 允许修改范围

经确认修改src下消息包、薄节点包装、启动文件和集成测试。
消息转换同时检查生产者和消费者，公共消息变化先更新DATA_FORMAT。
允许在后续已确认任务中用PointCloud2/Image承载驱动原始数据，并为训练监督支路增加
独立namespace/launch；不得用标准载荷类型省略业务字段和质量合同。

## 4. 禁止修改范围

不得在节点包装中复制网络、传感器模型或地图算法；不得通过订阅/文件共享绕过分层。
不得重写采集时间或frame_id掩盖不匹配，不默认同时维护ROS1与ROS2两套实现。
不得把当前目录名解释为已经验证了catkin或某个ROS版本。
不得在inference launch中启动fake LiDAR，不得把训练监督话题remap进SensorBundle。
`nav_msgs/Odometry`兼容输出不得成为第二个冲突的odom→base_link权威来源。

## 5. 与其他模块接口关系

包装节点只调用自己所属业务模块。ROS负责连接，业务数据仍按五层主链流转。
同步/状态适配逻辑归sensors；时钟承载属于基础设施，不携带越层业务数据。

## 6. 测试要求

验证消息往返转换、字段/单位/时间保留、生产者消费者连接、启动停止、超时、回放
及仿真时钟重置。记录所选ROS/PX4/JSBSim/桥接版本及实际命令。

## 7. 文档要求

维护话题/服务清单、消息类型、频率、队列或QoS、启动顺序和复现说明。
只有运行验证后的命令才能标为可用；配置和运行日志进入实验记录。
