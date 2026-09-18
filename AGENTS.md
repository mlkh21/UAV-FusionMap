# 高速固定翼无人机多传感器感知与地图构建工程项目规范

工程初始化基线：v0.1；更新日期：2026-09-16。

Python默认环境：用户于2026-09-14指定Conda `Radar-Diffusion`，解释器默认
`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。新增Python工具、测试、catkin
消息生成及ROS Python进程均使用该环境；运行前核对`sys.executable`。不要因ROS脚本
的系统shebang静默换回系统Python，不修改原Conda环境或终端双ROS选择。SIM-01入口为
`bash ros_ws/sim01_env.sh ...`；已归档的SIM-00A/B历史命令保留其原验证环境。

每次开发先读取本文件、[PROJECT_STATUS.md](PROJECT_STATUS.md)、
[系统架构](docs/SYSTEM_ARCHITECTURE.md)，再读取涉及目录的 AGENTS.md 和接口文档。
Phase 0工程初始化任务的授权范围为工程管理文档和目录占位；后续算法代码与运行功能
按当前PROJECT_STATUS、阶段计划和已确认的具体任务推进。

## 1. 项目目标

本项目目标不是单独完成某个算法，而是构建完整的无人机感知工程闭环：

无人机仿真平台
↓
机载状态与传感器数据
↓
4D毫米波雷达-热红外融合感知
↓
三维障碍物表达
↓
概率障碍物地图
↓
局部场景地图更新
↓
规划接口

最终面向高速固定翼无人机复杂环境自主飞行需求。

---

## 当前算法基础状态


本项目已有4D-Radar-Diffusion研究代码，独立维护于
`/home/zxj/catkin_ws/src/4D-Radar-Diffusion/`，与UAV-FusionMap为同级独立仓库。
相对UAV-FusionMap根目录的路径为`../4D-Radar-Diffusion/`。
本仓库通过工程接口评估和接入研究组件；来源与代码证据见
[algorithms/README.md](algorithms/README.md)。

该部分目前处于算法研发和调试阶段。


已有：

- 数据预处理和标定处理代码；
- 雷达-红外特征融合网络；
- 生成式三维占据预测代码；
- 离线概率地图与查询原型。

上述描述表示实现存在，不表示运行稳定性、预测质量或机载实时能力已通过验收。


当前存在：

- 数据预处理链尚未完全适配新版数据；
- 模型训练/推理流程尚未完全确认；
- 当前版本无法保证稳定生成有效预测结果；
- 可运行的工程接口尚未形成。


因此：

4D-Radar-Diffusion当前作为算法探索模块，
不作为系统其他模块的必要前置条件。


系统开发必须支持：

1. 无感知算法情况下运行；
2. 使用简单占位感知输出测试；
3. 后续替换为4D-Radar-Diffusion。
---

## 3. 系统总体架构

### 3.1 仿真平台层

负责：

- PX4
- JSBSim
- ROS通信
- 飞行状态输出

输出：

- position
- velocity
- attitude
- IMU
- timestamp

---

### 3.2 传感器层

包括：

4D毫米波雷达：

输出：

- x
- y
- z
- doppler
- power
- timestamp

热红外：

输出：

- thermal image
- timestamp

所有传感器必须包含时间信息。

驱动层可以使用`sensor_msgs/PointCloud2`、`sensor_msgs/Image`等ROS标准载荷，但
设备无关业务接口仍须保留Radar的Doppler方向、强度物理量、逐点/扫描时间、有效性和
质量语义。传感器通用化不等于只统一消息类型。

LiDAR不属于在线感知、定位或地图输入。仿真训练数据生成模式可以启动
`fake_lidar_node`，与fake Radar/IR同步产生训练监督点云、occupancy target和
observed mask；在线推理、地图联调和部署模式不得把LiDAR加入SensorBundle。

---

### 3.3 感知层

已有4D-Radar-Diffusion作为研究基础。

目标：

逐步形成工程化感知模块。

输入：

Radar + IR

输出：

- occupancy
- confidence
- uncertainty

---

### 3.4 地图层

负责：

- 局部障碍物地图；
- 多帧融合；
- 概率更新；
- 子地图管理；
- DEM融合。

开发顺序：

local map

↓

probability map

↓

uncertainty

↓

DEM fusion

禁止跳过基础地图直接开发高级方法。

---

# 4. 开发原则

## 4.1 工程优先

任何功能必须满足：

1. 可以运行；
2. 可以测试；
3. 可以复现；
4. 有记录（中文）。

论文公式不能替代工程实现。

---

## 4.2 不进行无依据重构

修改前必须说明：

- 当前问题；
- 影响范围；
- 修改方案；
- 验证方式。

禁止：

- 删除已有实验；
- 删除checkpoint；
- 大规模重写核心代码；
- 无理由的代码重构；
- 无意义的 Hashing;
- 不要过度防御。

---

# 5. 坐标系统规范

所有空间转换必须明确：

- 源坐标系；
- 目标坐标系；
- 外参方向；
- 时间戳。

主要坐标：

Radar frame

Camera frame

Body frame

World frame

Map frame

禁止默认：

Radar = Camera = Body = World

---

# 6. 时间同步规范

高速飞行条件下：

时间误差会导致空间误差。

所有：

- Radar
- Camera
- IMU
- Odometry
- 训练监督LiDAR（仅训练数据生成模式）

必须记录timestamp。

---

# 7. 虚拟传感器开发原则

第一阶段：

功能级模拟。

目标：

数据格式正确，接口可用。

第二阶段：

参数化模拟。

加入：

- FOV
- range
- frequency
- noise

第三阶段：

高真实性模拟。

加入：

- 多径
- 虚警
- 环境影响

禁止一开始追求完整物理雷达仿真。

虚拟传感器必须区分`training_data_generation`与`inference`运行配置。训练配置可同时
生成fake Radar、fake IR和训练监督LiDAR；模型输入仍只含Radar+IR，LiDAR及其派生标签
不得进入在线SensorBundle或模型forward输入。推理配置不得启动或依赖训练监督LiDAR。

---

# 8. Git规范

开发必须使用分支。

稳定：

main

开发：

develop

功能：

feature/\*

提交信息：

feat:
fix:
refactor:
test:

---

# 9. Agent职责

project_manager：

控制项目阶段。

system_architect：

设计系统结构。

simulation_engineer：

负责无人机仿真。

sensor_engineer：

负责虚拟传感器。

perception_engineer：

负责感知模块工程化。

mapping_engineer：

负责地图。

integration_engineer：

负责系统联调。

experiment_manager：

负责实验记录。

reviewer：

负责发现风险。

tester：

负责验证。

---

# 10. 当前优先目标

第一阶段目标：

完成：

已有4D-Radar-Diffusion分析

↓

工程接口设计

↓

ROS数据闭环设计

不要优先开发：

- DEM融合；
- 完整NanoMap；
- 自主控制。

---

# 11. 工程管理约束

## 11.1 模块职责

根目录负责系统范围、模块边界、阶段验收和变更管理。子目录 AGENTS 补充本模块
约束，不能放宽本文件的保护要求。存在冲突时先说明冲突并修订设计，不能自行绕过。
角色名称表示责任分工；未指定实际人员时由 Technical Lead 暂代管理责任，不代表
相应模块已有实现或已安排独立执行者。

## 11.2 输入输出定义

- 输入：用户需求、当前代码、配置、运行证据、问题和变更请求。
- 输出：模块边界、接口约定、开发任务、决策、实验记录和交付状态。
- 业务层间只交换公开数据契约；字段语义以 [DATA_FORMAT.md](docs/DATA_FORMAT.md)
  为准，坐标语义以 [COORDINATE_SYSTEM.md](docs/COORDINATE_SYSTEM.md) 为准。
- 主链为 Simulation → Sensors → Perception → Mapping → Application Interface。
  ROS 工作区只做消息、节点包装与启动装配，不成为跨层调用的通道。
- 当前不新增独立localization目录。PX4估计状态的筛选、坐标适配、连续odom语义及未来
  定位源选择属于明确的“定位权威职责”，现阶段仍由simulation/sensors现有边界承载。
  `nav_msgs/Odometry`可作为ROS兼容镜像，不能单独替代包含run/clock/source/status的
  AircraftState；mapping仍只消费OccupancyObservation携带的观测时刻SpatialContext。

## 11.3 允许修改范围

在已确认的任务范围内，可修改所属模块的实现、配置、测试和配套文档。
根目录维护全局规范、README 和 PROJECT_STATUS；模块规则见各目录 AGENTS。

修改前必须：

1. 读取本文件、PROJECT_STATUS、SYSTEM_ARCHITECTURE 和涉及目录的 AGENTS。
2. 检查 Git 状态、真实入口及相关生产者和消费者，保留已有未提交改动。
3. 说明当前问题、修改方案、影响模块、验证方法和必要的恢复方法。
4. 等待用户确认后执行；用户已确认的同一范围连续完成，不反复请求相同确认。
5. 扩大范围、改变公共接口或架构时，先补充具体方案再确认。

开发使用功能分支。稳定基线使用 main，集成使用 develop，任务使用 feature/*。
已有代码、数据、checkpoint、日志、结果和会话配置均不得作为初始化附带修改。
提交前核对文件清单；不使用 `git add .` 混入无关文件，不自动提交或推送。

## 11.4 禁止修改范围

- Phase 0仅建立管理文件和目录边界，不编写算法或运行节点，不安装大型依赖，
  不迁移、删除或重构核心目录；后续阶段按已确认任务实施。
- 不直接修改、搬入或清理同级4D-Radar-Diffusion研究仓库。
- disabled/placeholder模式启动不得依赖研究模型、GPU、checkpoint或研究数据目录；
  research后端仅在其已验证的前置条件满足时启用。
- 不跨层导入业务实现、读取其他模块私有文件或直接订阅越层业务话题。
- 不把未知、超时或算法不可用解释为空闲空间；不默认坐标系相同。
- 不将占位结果、离线回放、接口存在或语法检查写成真实感知、实时部署或飞行验收。
- 不让训练监督LiDAR进入在线SensorBundle、定位、mapping或研究模型forward输入；
  不把仿真LiDAR“无点”直接标为自由空间，监督必须保留observed mask。
- 不删除或覆盖历史实验，不做无意义的哈希、不必要重构和过度防御。

## 11.5 与其他模块接口关系

| 目录 | 责任角色 | 主要职责 |
| --- | --- | --- |
| simulation | simulation_engineer | 飞行仿真、场景、时间和状态输出 |
| sensors | sensor_engineer | 传感器、标定、同步、状态/定位权威适配及训练监督生成 |
| perception | perception_engineer | 工程感知入口、占位输出、研究后端适配 |
| mapping | mapping_engineer | 局部地图、概率更新、场景地图、后期DEM |
| application | integration_engineer | 地图查询、规划数据接口、可视化适配 |
| ros_ws | integration_engineer | 消息、节点包装、启动及回放连接 |
| algorithms | perception_engineer / mapping_engineer | 按组件登记研究来源与复用条件 |
| configs | system_architect及配置所属模块 | 参数、标定引用、版本组合 |
| tests | tester / reviewer | 跨模块契约、集成和系统验收 |
| experiments | experiment_manager | 实验复现、结果和产物索引 |
| docs | system_architect / project_manager | 设计依据、计划和决策 |

每项任务只指定一名主责任角色。Technical Lead负责协调，reviewer检查风险，tester
提供验证证据；具体人员与任务状态在PROJECT_STATUS或DEVELOPMENT_PLAN登记。

## 11.6 测试要求

- 文档初始化检查必需文件、七项模块规则、链接、字段、坐标和状态一致性。
- 后续代码修改运行与影响相匹配的单元、契约或集成检查；不要仅测试实现细节。
- 修复明确错误时，先复现问题，再验证修复结果；记录未执行的检查及原因。
- 占位链路和研究模型质量分别验收；时间、坐标、未知区域和过期数据必须覆盖。
- 长训练、全量预处理和会覆盖产物的运行不属于默认轻量验证范围。

## 11.7 文档要求

开发和实验记录使用中文，保留必要的代码符号。每次修改完成后报告：
修改文件列表、修改原因、测试方式、测试结果、潜在风险。
同步更新PROJECT_STATUS；接口或架构变化记录DECISION_LOG，实验记录EXPERIMENT_LOG。

状态使用“计划 / 进行中 / 阻塞 / 已完成”，完成必须链接可核对的交付物或验证记录。
明确区分“已定义接口”“已有代码”“已验证运行”“已通过场景验收”。
计划日期属于管理基线，变更时记录原因，不通过省略测试将任务标为完成。
