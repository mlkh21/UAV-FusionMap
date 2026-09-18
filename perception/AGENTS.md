# perception 模块规范

基线：v0.1；日期：2026-09-16；责任角色：perception_engineer。
先读[根规范](../AGENTS.md)、[项目状态](../PROJECT_STATUS.md)和[系统架构](../docs/SYSTEM_ARCHITECTURE.md)。

## 1. 模块职责

提供统一感知入口，完成Radar/IR处理、融合、Occupancy输出与研究后端适配。
支持disabled、placeholder、research三种运行模式。
设备无关清洗由sensors完成；模型特定voxel、归一化、裁剪、张量布局和IR特征适配
保留在本层，避免传感器接口绑定单一checkpoint协议。

## 2. 输入输出定义

输入：SensorBundle，包含Radar、IR、参考时刻、标定和状态上下文。
输出：OccupancyObservation，包含占据概率、观测掩码、confidence、uncertainty及
地图转换上下文。各模式使用相同公共接口，并明确输出来源和有效性。
训练数据生成另可读取独立监督记录构造target/observed mask，但该监督不是运行时
SensorBundle字段，也不是research forward输入。

## 3. 允许修改范围

经确认修改本目录预处理、后端接口、占位实现、适配器和模块测试。
研究模型张量布局及归一化在适配边界转换，保持公共接口与具体模型独立。

## 4. 禁止修改范围

不得直接修改同级研究仓库，不得写入地图、读取地图内部状态或调用控制器。
不得把预测第3通道当作不确定性；不得将缺失模型、空输入或超时转换为全自由空间。
不得让disabled或placeholder模式依赖GPU、权重或研究仓库安装。
不得订阅在线LiDAR或把训练监督点云、target、observed mask派生特征送入Radar+IR模型
forward；训练标签路径与推理输入路径必须可审计地分离。

## 5. 与其他模块接口关系

消费sensors公开契约，向mapping发送占据观测及同一时刻的变换元数据。
模型生成与离线真值评价分离；外部研究组件来源见algorithms/README。
ROS包装不复制预处理和推理逻辑。

## 6. 测试要求

验证三种模式的契约一致性、无模型启动、已知体素布局、时空元数据保留、未知掩码、
超时及不支持输入的明确状态。真实模型另验权重加载、单帧输出、质量、耗时与资源。
占位通过不替代真实感知质量验收。

## 7. 文档要求

记录输入/输出映射、模型版本、预处理、坐标、标定、阈值及不确定性来源。
明确代码存在、运行通过和质量达标的不同状态；输出示例标注真实或占位。
