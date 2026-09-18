# mapping 模块规范

基线：v0.1；日期：2026-09-16；责任角色：mapping_engineer。
先读[根规范](../AGENTS.md)、[项目状态](../PROJECT_STATUS.md)和[系统架构](../docs/SYSTEM_ARCHITECTURE.md)。

## 1. 模块职责

维护局部障碍物地图、多帧概率更新、过期管理、场景地图及后期DEM融合。
顺序为Local Map → probability → uncertainty → Scene Map → DEM。

## 2. 输入输出定义

输入：OccupancyObservation及其时间/变换上下文；后期通过显式TerrainPrior接入DEM。
输出：MapSnapshot和MapQueryResult，包含占据、未知、时间、覆盖范围与质量信息。

## 3. 允许修改范围

经确认修改本目录地图结构、更新、查询、子地图和适配逻辑；独立评估研究地图原型。
算法内部表示可变化，但公共契约和消费者兼容性必须保持或经过版本变更评审。

## 4. 禁止修改范围

不得读取Radar/IR原始数据、直接订阅越层业务话题或调用感知模型内部类。
不得默认位姿为单位矩阵，不得将unknown、模型失效或过期观测当作free。
基础地图未验收前不得优先开发DEM、完整NanoMap或高级融合。
不得把模型方差直接当成单位为m²的地形高度方差。
不得订阅Odometry、AircraftState、训练监督LiDAR或其标签；mapping只使用
OccupancyObservation中绑定到观测参考时刻的SpatialContext。

## 5. 与其他模块接口关系

只消费perception公开输出，向application公开地图快照和查询接口。
位姿、变换和观测标识来自占据消息上下文，不反向访问simulation或sensors。
DEM是本层明确声明的外部先验入口，不借此引入原始传感器旁路。

## 6. 测试要求

验证已知障碍、跨帧位姿变化、重复观测去重、未知域、过期信息、滚动覆盖范围和
内存上限。查询同时覆盖occupied/free/unknown/stale/unavailable；定位跳变需明确处理。

## 7. 文档要求

记录分辨率、原点、坐标系、更新规则、去重/老化策略、有效范围和查询语义。
复用研究实现需记录版本、改动和验证边界；地图与DEM验收分别登记。
