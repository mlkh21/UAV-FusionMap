# EXP-20260911-002：现有环境只读核查

日期：2026-09-11；类型：环境/文件/源码检查；主责任角色：simulation_engineer。
关联任务：ENV-01；状态：已完成核查，存在依赖缺项和GPU查询失败；运行链路未验收。

## 1. 目的与范围

在初始化文档完成后，根据用户“继续”的指示核查本机已有资产，为ENV-02提供实际依据。
用户进一步说明交互终端每次选择`Foxy(1)`或`Noetic(2)`；该信息已与shell文件核对。
交付为[环境清单](../configs/ENVIRONMENT_INVENTORY.md)及同步后的计划、状态、决策依据。

未安装软件、升级系统、修改shell、构建工作区、启动ROS/PX4/JSBSim、加载模型或训练。
未移动或修改外部研究仓库、PX4仓库、数据、权重及已有运行产物。

## 2. 版本、输入和输出

- 工程仓库：/home/zxj/catkin_ws/src/UAV-FusionMap。
- 工程分支：feature/engineering-initialization；尚无首次提交，文件未跟踪。
- PX4：v1.13.3，提交1c8ab2a0d7db2d14a6f320ebd8766b5ffaea28fa，干净的detached HEAD。
- 桥接：Tools/jsbsim_bridge子模块，提交68de2cc63ded9a0d6641d45e9eb3ed2b43454cba。
- 输入：已安装包元数据、环境变量、标准路径、Git状态、CMake缓存及桥接源码。
- 数据集、模型、随机种子、飞行参数：不适用，本次没有算法或仿真运行。
- 持久交付：本记录、configs/ENVIRONMENT_INVENTORY.md和下列五份已有文档的更新。
- 修改前五份文档的临时副本：/tmp/uav-env01-_b2vdgg_；仅用于本次恢复，非长期备份。

## 3. 实际检查过程

| 检查 | 方法 | 实际结果 |
| --- | --- | --- |
| 系统和工具 | /etc/os-release、uname、dpkg-query、命令路径与Python元数据 | Ubuntu 20.04.6、系统Python 3.8.10、当前Conda base Python 3.13.5；完整版本见清单 |
| ROS安装 | /opt/ros、dpkg、组件package.xml | Noetic与Foxy都存在 |
| ROS会话 | 各自独立的bash --noprofile --norc子进程，移除继承的ROS/Conda/Python路径，source一个setup文件 | 两个子进程退出0；发行版变量、命令及模块路径发现通过；没有节点通信测试 |
| 终端启动选择 | 只读/home/zxj/.bashrc的非交互保护、switch_ros和启动菜单段 | 菜单1=Foxy、2=Noetic；旧switch_ros函数不能作为已验证切换入口 |
| 既有catkin配置 | src/CMakeLists.txt链接、build/CMakeCache.txt、devel登记 | 与Noetic及系统Python关联；未重建 |
| Conda研究环境 | .conda/environments.txt、conda-meta、site-packages元数据 | Radar-Diffusion/sam2/wifi等存在；未导入torch或修改环境 |
| PX4与桥接 | Git状态/提交/子模块、file、CMake缓存及源代码 | v1.13.3、px4二进制和桥接源码存在；桥接构建目录为空 |
| JSBSim与MAVROS | 包清单、标准头文件/库路径、ldconfig、所查ROS包目录 | 检查范围内未找到所需开发安装和MAVROS |
| 状态输出入口 | jsbsim_bridge_ros.cpp、package.xml、launch及CMakeLists | ROS节点包装存在，statusloopCallback仍TODO；状态源需设计 |
| CPU/内存/磁盘 | lscpu、free -h、df -h | 获得开发机资源快照；未进行性能基准 |
| GPU | /proc/driver/nvidia、dpkg及nvidia-smi；沙箱外复核 | NVML驱动/库不一致，查询失败；CUDA计算未验证 |
| CUDA工具 | 版本文件、目录链接及显式nvcc --version | 多个Toolkit目录，默认链接12.1，nvcc 12.1.105可执行 |

实际执行的代表性命令包括：

```bash
git status --short --branch
uname -srmo
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
/usr/local/cuda/bin/nvcc --version
```

ROS子进程检查通过Python subprocess组织：删除继承的ROS_*、CONDA_*、AMENT_*、
COLCON_*、PYTHONPATH、PYTHONHOME、CMAKE_PREFIX_PATH及VIRTUAL_ENV，设置系统PATH和
PYTHONDONTWRITEBYTECODE=1；向`/bin/bash --noprofile --norc -c`分别传入
`/opt/ros/noetic/setup.bash`和`/opt/ros/foxy/setup.bash`，然后使用`/usr/bin/python3 -B`
检查变量、shutil.which和importlib模块发现/包元数据。没有调用roscore或ros2 daemon。

环境缺项搜索有边界：目录名搜索覆盖/home/zxj、/opt、/usr/local/src、/usr/local/lib，
最大深度4，跳过隐藏目录、大型数据/产物和已单独登记的Conda目录，访问446个目录；
另查标准include/lib、ldconfig、APT元数据和两个ROS安装及既有catkin的包清单。
“未发现”不表示穷尽全部磁盘或容器，也不排除尚未登记的自定义安装。

## 4. 预期与实际结果

| 检查目标 | 预期 | 实际 | 判断 |
| --- | --- | --- | --- |
| 形成环境事实清单 | 每项区分存在、版本、已测和未测 | 已登记并链接源码与版本证据 | ENV-01完成条件满足 |
| 双ROS加载检查 | 分别发现正确发行版和入口 | Noetic/Foxy均通过环境发现检查 | 仅环境加载通过 |
| 仿真依赖完整性 | 查明所选候选路径是否有缺项 | JSBSim开发安装、MAVROS未在所查范围找到 | 正式启动前仍有阻断 |
| GPU可查询 | nvidia-smi输出型号/驱动/显存 | 沙箱内退出9；沙箱外退出18，NVML版本不一致 | 查询失败，不声明GPU可用 |
| 系统运行与性能 | 本任务不执行 | ROS通信、仿真、GPU计算和模型均未执行 | 不作验收结论 |

沙箱外只读复核的原始关键错误为：

```text
Failed to initialize NVML: Driver/library version mismatch
NVML library version: 580.178
```

同时读取的内核驱动为580.173.02，已安装驱动包为580.178.04。
这些证据支持版本不一致，尚不足以确定具体修复动作；本次不重启或改装驱动。

## 5. 本次文档修改与验证

| 文件 | 修改原因 |
| --- | --- |
| configs/ENVIRONMENT_INVENTORY.md | 新增可复核的环境/资产与缺项事实，保留双ROS选择说明 |
| experiments/2026-09-11-environment-inventory.md | 新增本次实际检查、失败及验证边界 |
| PROJECT_STATUS.md | 完成ENV-01，登记环境/GPU风险和下一步 |
| docs/DEVELOPMENT_PLAN.md | 更新ENV-01状态及ENV-02前置条件 |
| docs/DECISION_LOG.md | 给ADR-P001补充实测依据，保持选型待决 |
| docs/EXPERIMENT_LOG.md | 增加EXP-20260911-002索引，保留历史记录 |
| README.md | 增加环境清单入口并更新下一步 |

文档检查覆盖上述文件清单、Markdown格式和本地链接、任务状态与证据一致性。
结果：5份已有文档与修改前副本相比均有预期更新，2份新记录存在；全仓25份Markdown
的尾空白、文件结尾、冲突标记和代码围栏检查通过，107处本地链接全部存在；12份
AGENTS仍包含七项模块规则。ENV-01完成、ENV-02下一步、R-07/R-08及实验索引一致。
临时机器检查报告：/tmp/uav-env01-_b2vdgg_/documentation-check.json；检查无错误。
外部PX4及桥接仓库仍干净，研究仓库保留原有未提交状态；没有提交或推送。
上述是文档和文件范围检查，不为纯文档任务添加业务测试，也不代替运行验收。
恢复时仅比较并恢复本任务对应文档，不回退无关文件；两个新增记录可按任务范围处理。

## 6. 风险与下一步

ENV-02继续制定版本候选和最小仿真验证方案。现有Noetic/catkin与ROS 1桥接资产提供
复用候选，但Noetic和Foxy均已结束官方支持；保存环境、依赖补齐与后续维护方式必须
纳入选型。来源及生命周期日期见环境清单，尚未冻结任一版本。

GPU问题另行明确修复范围后处理，不成为CPU上的设计和无模型验证方案的必要前置。
不得将开发机配置当作机载算力，将桥接源文件当作已实现的AircraftState发布接口，
或将ROS加载通过当作PX4—JSBSim—ROS运行闭环通过。
