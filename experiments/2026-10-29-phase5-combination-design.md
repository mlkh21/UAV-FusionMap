# EXP-20261029-002：Phase 5软件组合场景设计审查

日期：2026-10-29；任务：P5-DESIGN-01；主责任：integration_engineer。
类型：真实入口/消费链审计、既有定向单元/契约回归与文档检查。
状态：已完成（设计交付），新组合场景运行未执行。

## 1. 目的与基线

用户继续授权按总体计划推进，不回到真实输入/研究质量阻塞任务。M5-IFACE-SW-01—03
已完成公共合成软件范围，PROJECT_STATUS下一项为Phase 5组合场景/需求矩阵设计。
本轮保留feature/engineering-initialization分支全部既有修改及未跟踪文件，不提交或推送。
读取根/文档/实验/测试规范、阶段安排、公共字段/时间/坐标及M5交付；沿实际生产消费链审计，
没有修改同级研究仓库、公共字段或运行入口。

交付：[具体设计](../docs/PHASE5_SOFTWARE_COMBINATION_DESIGN_20261029.md)。
其中15项事实、三种显式配置、九组场景、REQ-01—14矩阵与SW-01—03工作包均区分当前与计划。

## 2. 关键审计结论

1. placeholder只提供Radar点占据域，M2/M3/M4要求显式逆观测fixture域；两条配置必须分开。
2. paired缺IR没有Bundle，不等价于可信后端失败产生unavailable；组合账本须分别检查。
3. M1查询按请求时间/max_age老化，无TerrainProvider同等墙钟存活/reset门控；旧同步地图客户端无调用deadline。
4. 地形与Gazebo/Scene没有共同地理注册；相同map名称、run/clock不能作为空间叠加依据。
5. 地形录制每个clock计事件，总64事件；设计单列短窗口，并保留v1不可表达故障的incomplete边界。
6. 35/50/70m/s仅功能级坐标/年龄预算；新设计不改20ms、正式机载或完整阶段门槛。

证据入口及符号见设计F01—F15。设计新增时序控制/测试后端/调用隔离均为待实施测试设施，
没有通过文档声明其已存在。

## 3. 环境与实际验证

入口固定`bash ros_ws/sim01_env.sh ...`，实际核对sys.executable为
`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。
工作区`.runtime`由现有忽略规则隔离；不在外层catkin_ws构建，不改环境，不安装依赖。

实际命令核心为在上述入口下，`sys.path`添加仓库tests目录后执行：

```python
names = [
    "test_perf01a_motion", "test_perception_node", "test_local_map_query",
    "test_application_query_client", "test_m4_scene_map", "test_sim01_clock_gate",
    "test_terrain_client", "test_terrain_recording",
]
suite = unittest.defaultTestLoader.loadTestsFromNames(names)
unittest.TextTestRunner(verbosity=2).run(suite)
```

预期：既有运动变换、失败保留、查询年龄/身份、Scene域、时钟锁、地形客户端/录制边界仍成立。
实际：76/76通过，耗时2.037s；部分节点包装单元测试使用mock，此处不算实际ROS/线格式新验收。
独立日志：`.runtime/runs/phase5-design-20261029T101139313647/targeted-tests.log`。
本轮仅文档变更，未重跑全仓774项；774是上轮已记录的历史结果，不能写成当前新运行。

文档检查覆盖新增/修改页面本地链接、15个源码入口、九个场景与14项需求、状态/索引一致性，
以及`git diff --check`：8个页面共613个本地链接零缺失，15项事实/9场景/14需求表项齐全，
差异空白检查通过。本轮未新增业务测试或生成新协议类型。

## 4. 结果、风险与下一步

已有代码：P3工程入口、M1—M4合成地图/应用、M5公共软件、原生Gazebo/RViz等沿用已有记录。
本轮实现：只交付具体设计、实验记录、ADR-041及必要状态/索引。
实际验证：既有76项定向通过；文档静态核对，不含新组合运行。
未验证：S01—S09、完整系统长时稳定性、真实设备/模型/DEM、占据融合、机载资源及正式Phase 4/5。

下一项P5-SW-01先保存小型输入与独立预期/限额，再做实际生成消息往返；
运行器与实际ROS属于SW-02，原生图/失败清理交接属于SW-03。
旧MapQuery墙钟缺口按实际记录，实施不得未经具体评审扩成生产接口重构。
本轮恢复只需撤销本轮文档增量，不涉及运行进程、消息、数据、历史产物或研究仓库。

本轮修改文件清单（均为文档）：

- 新增`docs/PHASE5_SOFTWARE_COMBINATION_DESIGN_20261029.md`：具体设计与独立预期种子。
- 新增`experiments/2026-10-29-phase5-combination-design.md`：本审查和实际验证记录。
- 更新`PROJECT_STATUS.md`：设计完成范围及下一项P5-SW-01。
- 更新`docs/STAGE_ADVANCE_PLAN_20261027.md`：跨阶段排程与实现/设计分界。
- 更新`docs/DEVELOPMENT_PLAN.md`：设计索引与后续实施顺序。
- 更新`docs/SYSTEM_ARCHITECTURE.md`：组合测试边界索引，不改架构。
- 更新`docs/DECISION_LOG.md`：ADR-041。
- 更新`docs/EXPERIMENT_LOG.md`：本轮实验索引。
