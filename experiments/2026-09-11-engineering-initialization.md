# EXP-20260911-001 工程初始化验证

日期：2026-09-11；类型：工程文档检查；责任角色：Technical Lead / tester。
关联任务：INIT-01至INIT-05。状态：文档与范围检查通过；运行功能未验证。

## 1. 目的与前置状态

将用户确认的项目分工、接口、开发计划与记录流程落入UAV-FusionMap。
开始时主仓在无首次提交的master，业务目录为空或仅有占位，三份docs仅有标题。
研究仓库位于同级目录，存在原有未提交修改及删除，本次保持不变。

## 2. 工作范围与版本

- 工作分支：feature/engineering-initialization；尚无首次提交。
- 修改范围：工程Markdown及ros_ws/src/.gitkeep；新增application/tests目录边界。
- 原始11个非会话/非Git文件已保存在本机临时目录`/tmp/uav-fusionmap-init-4o09_ptt/`。
  该临时副本仅用于本轮比对，不是长期备份或可移植的交付依赖。
- 未修改算法、运行节点、依赖、研究仓库、会话配置或既有产物。

## 3. 修改文件清单与原因

| 类型 | 文件 | 原因 |
| --- | --- | --- |
| 更新 | AGENTS.md | 保留原有保护规则，明确双仓关系、入口、七项根规则和开发流程 |
| 更新 | README.md | 修正项目名，建立文档入口和目录职责 |
| 更新 | algorithms/README.md | 来源路径基准、关键代码证据、接入限制和复用顺序 |
| 更新 | docs/SYSTEM_ARCHITECTURE.md | 五层架构、模式、时空传递和依赖边界 |
| 更新 | docs/COORDINATE_SYSTEM.md | 坐标、变换、网格原点、责任和验证样例 |
| 更新 | docs/EXPERIMENT_LOG.md | 验证类型、索引、静态检查追溯和实验模板 |
| 新增 | PROJECT_STATUS.md | 已完成、进行中、计划、风险、下一步与证据 |
| 新增 | docs/DATA_FORMAT.md | 数据字段、类型、时间、坐标、未知与质量契约 |
| 新增 | docs/SENSOR_INTERFACE.md | 生产消费、同步、异常、ROS连接候选 |
| 新增 | docs/DEVELOPMENT_PLAN.md | 到2027年3月的阶段、任务、验收与指标预算 |
| 新增 | docs/DECISION_LOG.md | 已采用原则和待决事项 |
| 新增 | simulation/AGENTS.md、sensors/AGENTS.md、perception/AGENTS.md、mapping/AGENTS.md | 业务模块职责与修改边界 |
| 新增 | ros_ws/AGENTS.md、experiments/AGENTS.md、docs/AGENTS.md | 通信、验证记录和设计文档边界 |
| 新增 | algorithms/AGENTS.md、configs/AGENTS.md | 研究来源与配置管理边界 |
| 新增 | application/AGENTS.md、tests/AGENTS.md | 补足应用接口与系统测试边界 |
| 新增 | ros_ws/src/.gitkeep | 保留后续ROS包目录，目前没有包实现 |
| 新增 | experiments/2026-09-11-engineering-initialization.md | 本次文件、检查结果和限制记录 |

## 4. 检查方法与结果

检查采用Python标准库只读遍历/文本核对及Git状态检查，不新增业务测试程序或安装依赖。
结构检查之外人工核对生产消费方向、模式降级、时间/坐标/未知语义、研究适配和阶段门槛。
发现并统一了reason字段名称，并将Phase 0限制明确限定到初始化阶段，避免阻止后续已授权开发。

| 检查 | 预期 | 实际结果 |
| --- | --- | --- |
| 必需文件覆盖 | 根/子目录AGENTS、七份docs、状态及入口完整 | 24个交付文件全部存在；6个原文档更新、18个文件新增 |
| AGENTS七项约束 | 每份包含职责、I/O、允许/禁止、接口、测试和文档 | 12/12通过 |
| 本地Markdown链接 | 本仓及同级研究代码引用存在 | 90处引用路径检查通过；不等于外部代码可运行 |
| Markdown格式 | UTF-8、围栏成对、无行尾空白 | 23份Markdown通过 |
| 数据和架构关键约束 | 必需字段、五层、模式、时空/未知语义及计划一致 | 关键字段/章节文本检查及人工一致性核对通过；未执行接口运行测试 |
| 原文件保护 | 原文件无删除，五个既有.gitkeep不变，修改仅在清单内 | 与临时副本逐文件比对，11个原文件均保留，修改范围符合清单 |
| 研究仓库保护 | 本轮前后Git状态无变化；未运行其代码 | 开始/结束Git状态一致，仍为uav_system_dev / 6dd61e2且保留原有改动 |

Git diff --check无报错，但主仓尚无跟踪文件，该命令不覆盖此次未跟踪文档；以上
文档结果来自实际遍历文件检查和初始副本比对，不能用空Git diff代替验证。

## 5. 限制与风险

本次不能证明仿真、ROS消息、算法质量、地图更新或实时性能已通过。
ROS版本组合、性能预算、研究CLI缺失、Body外参及首次提交基线仍按PROJECT_STATUS跟踪。
未执行训练、推理、仿真、GPU任务、依赖安装、Git提交或推送。
