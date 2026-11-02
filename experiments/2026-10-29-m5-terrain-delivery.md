# EXP-20261029-001：地形客户端、公共执行回放与RViz交付

日期：2026-10-29；主责任：integration_engineer；任务：M5-IFACE-SW-03。
状态：已完成（独立公共地形合成软件范围）。依据：用户“继续”、ADR-040及
[已交付方案](../docs/M5_IFACE_DESIGN_20261028.md)。
实际入口、命名空间、录制边界及使用方式见
[交付说明](../docs/M5_IFACE_SW03_DELIVERY_20261029.md)。

## 目的与实施前核对

SW-02已有默认关闭Provider与实际服务，尚缺独立应用客户端、公共执行回放及地形显示。
本轮在五层边界内补齐上述链路，验证存活/期限/迟到/重启/整组pin和记录完整性，
不扩展旧公共类型或恢复真实数据/研究模型质量任务。

已读根AGENTS/PROJECT_STATUS/SYSTEM_ARCHITECTURE、M5公共方案、SW-01/02合同与运行层、
数据/传感器/坐标约定，以及application/mapping/ros_ws/tests/configs/docs/experiments局部规则。
沿真实Provider、recording校验、codec、旧应用查询、原RViz渲染和场景runner追踪生产消费。
分支feature/engineering-initialization，全部既有修改/未跟踪文件保留；新源码未被忽略，.runtime被忽略。
无提交/推送，无同级研究仓库改动、依赖安装、模型/训练或正式PERF-01运行。

## 修改清单与原因

| 范围 | 文件与原因 |
| --- | --- |
| 应用层 | 新增application/ufm_application/terrain_client.py、terrain_visualization.py：只消费公开状态/结果，维护存活/实例/整组版本；输出live或recorded独立样本标记 |
| mapping | 新增mapping/ufm_mapping/terrain_recording.py：create-only三文件录制、真实Provider事件重放与结果比对；失败incomplete，不影响已提交地形 |
| 传输/显示 | 新增ros_ws/terrain_query_transport.py、terrain_recording_replay.py、terrain_rviz_node.py、terrain_recorded_view.py；单worker期限、严格离线输出、公开MarkerArray和独立历史namespace |
| 装配/配置 | 新增ros_ws/launch/terrain_rviz_fixture.launch与configs/terrain.rviz，默认关闭；地形包CMakeLists增加显示脚本、package.xml声明visualization_msgs；terrain_fixture.launch/terrain_ros.py仅增加默认关闭录制参数/包装与结束完整性检查 |
| 验收 | 新增ros_ws/terrain_delivery_run.py、tests/check_terrain_delivery_ros.py、terrain_rviz_capture.py、test_terrain_client.py、test_terrain_recording.py；21项新增及真实ROS/自有窗口像素验收 |
| 旧包装测试 | tests/test_terrain_node.py对两个已明确新增的地形launch分别验证默认关闭，其余原launch仍禁止导入地形 |
| 中文交付 | 新增本记录、docs/M5_IFACE_SW03_DELIVERY_20261029.md、独立报告截图/图注；更新状态/架构/数据/传感器/设计/阶段/决策/实验及可视化索引，历史时点结论保留 |

旧消息/服务字段、私有TerrainFixture、旧工厂、旧占据节点与Gazebo/Radar/IR/RViz入口均未修改。
新增显示只查询公共服务/状态，不读dataset/spec/snapshot、不订阅定位/训练，不发布TF或控制。
公共记录schema仍v1，不在reason/source塞隐藏JSON，不新增Hash。

## 实际环境、命令与预期

Python启动核对为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，全部Python通过sim01_env；
ROS/Qt沿原Noetic环境，RViz进程单独选择系统Qt库与Mesa软件渲染，不改原Conda/终端ROS。
隔离catkin重新配置只使用.runtime/ros；没有构建外层catkin_ws。

```bash
bash ros_ws/sim01_env.sh cmake -S ros_ws/src -B .runtime/ros/build -DCATKIN_DEVEL_PREFIX=/home/zxj/catkin_ws/src/UAV-FusionMap/.runtime/ros/devel -DPYTHON_EXECUTABLE=/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/terrain_delivery_run.py --with-rviz
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sensor_scene_run.py --check --port 11721 --gazebo-port 11722
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
```

定向70项：test_terrain_client、test_terrain_recording、test_terrain_node、test_m5_provider、
test_m5_iface_codec、test_m5_iface_recording，以unittest模块加载运行并保存完整日志。
新增测试继续只读SW-01/02保存的独立输入/Context/高程/区间预期，不用被测输出更新oracle。
实际ROS fixture先保存本次公共dataset/配置，录制原操作，再严格执行回放；预期只用于结果比对，不驱动安装。
RViz截图只读自建窗口的Ogre渲染目标；没有抓取其他桌面窗口。

## 实际结果

| 检查 | 结果与限制 |
| --- | --- |
| 新增应用/传输/显示 | 11/11通过：latched单次不作存活，心跳/主动查询证明实例，1.5s状态超时、回退/重启清组，坏响应/质量拒绝、整组版本/到期切换弃用、0/负高/no-data和历史命名空间 |
| 新增录制/执行回放 | 10/10通过：create-only/incomplete、逐值执行、幂等/拒绝/新版、单调时间重建断流/到期/reset、篡改合法形状expected仍失败、64事件/16中心和写盘失败保护 |
| 最终定向 | 70/70通过，1.892s |
| 最终全仓轻量 | 774/774通过，57.241s（753既有+21新增） |
| 实际公共录制/回放 | 最终ROS录制23事件、8查询收据、3次记录状态，严格重放逐值一致；原实例身份保留、另有playback_session_id，文件仍schema v1 |
| 实际客户端/故障服务 | 12项检查通过，18条status收据/132条MarkerArray；4中心整组pin、重启换实例、过期/断流清理、真实阻塞服务1s调用期限、单未完成调用、迟到不回写、服务消失本地空实例封套 |
| 实际RViz | current/质量缺失、stale、unavailable清空、recorded四图通过；每图682×654，current与recorded绿色434/蓝色577像素，stale橙色781像素，unavailable三色均0 |
| 图边界 | 显示只消费地形公开status/服务（允许rospy内部clock），recorded另发历史namespace；无LiDAR/target/observed_mask、定位/TF旁路 |
| 地形清理 | 所有监督进程退出0，无强制信号/残留审计PID；11691端口释放，固定Python进程审计通过 |
| 旧场景/Radar/IR/占据/RViz | 原入口完整通过：11 Radar/20 IR/10 Bundle/10地图收据，1790回波/594占据cell；冷/暖/热投影、热箱移动14779 IR像素/408雷达点联动后恢复、无训练图；5图像素检查通过 |
| 旧场景清理 | 无强制终止或残留审计PID，11721/11722端口释放；原唯一状态/TF职责保持 |
| 文档/旧协议核对 | 15份文档724个本地链接无缺失、Git空白检查通过；19份既有.msg/.srv和旧包定义与冻结副本一致，无Hash计算；静态报告在最终回归目录doc-check.json |

地形与旧场景是两组独立隔离run，不是同run地理注册或DEM融合证据；原飞机仍固定，传感器仍功能级代理。
线程故障测试和实际阻塞服务证明期限/单worker行为，不代表底层调用取消、真实模型可中断、
网络连接/RSS/机载资源或正式PERF-01达标。15/20ms等正式性能门槛未在本轮重定义。

## 失败记录与合同边界

轻量初查中，手工探针曾覆盖sim01_env提供的PYTHONPATH，导致辅助模块导入失败；
修正探针路径后最小真实Provider录制/回放成功，没有修改环境配置或生产搜索路径。
旧launch测试最初把新增terrain_rviz_fixture.launch也当旧入口，因此失败；
改为对这两个显式新增入口分别验证默认关闭，剩余旧入口约束保持，随后全部通过。

初次实际验收在沙箱socket探针被PermissionError拒绝，尚未创建ROS子进程，清理探针同样受限；
失败目录[保留](../.runtime/runs/terrain-delivery-20261029T094657238872/)。
随后经工具权限审核允许沙箱外本地ROS/GUI短测，完整通过并清理，无未解决权限阻塞。

旧场景首次使用15s人工上限，ROS检查已过但尚未完成窗口截图，runner如实passed=false；
该次正常清理，未将其计成完整验收，目录[保留](../.runtime/runs/sensor-scene-20261029T095037220454/)。
随后不设额外短期限，使用原入口自带90s安全上限，完整场景/像素/清理通过。
前次地形成功run和770项回归也保留为过程证据，最终结论只引用最后代码的774项结果。

recording v1的clock_transport仅含online布尔值，无法重现运行后的clock_source_mismatch等细分来源错误；
此类错误、无返回的非法query和并发busy明确标录制incomplete，严格回放拒绝；不默默丢事件后宣称完整。
这是记录覆盖边界，Provider继续fail-closed；本轮未扩展公共schema来隐藏解决该问题。
省略心跳的单次状态序号差额>4096也明确拒绝，避免重放执行无界循环。

## 最终产物与恢复

- [地形最终ROS/RViz目录](../.runtime/runs/terrain-delivery-20261029T095312938935/)：
  validation.json、client-receipts.json、recording三文件、replay.json、pixel-validation.json、
  figures/01-current.png—04-recorded.png、manifest.json、cleanup-audit.json及各进程日志。
- [最终轻量回归](../.runtime/runs/terrain-sw03-regression-20261029T095302325564/)：targeted.log、full.log、report.json。
- [旧场景完整兼容run](../.runtime/runs/sensor-scene-20261029T095123223417/)：scene-validation.json、
  figures、figure-check.log、sensor-audit.json、manifest/cleanup与各节点日志。
- [独立报告素材及图注](report_assets/terrain-20261029/README.md)：复制本轮四张地形图，不覆盖旧地图/场景报告素材。

恢复只需停止新terrain_rviz_fixture/recorded_view及录制选项，继续旧入口；保留所有新源码和产物。
本轮没有自动提交/推送，没有删除历史实验或原数据/checkpoint。
已有：SW-01/02类型、私有候选和Provider。新增：客户端、录制/执行回放、live/recorded Marker显示。
实际验证：上述轻量/真实ROS/RViz/旧场景检查。未验证：真实DEM/基准/质量、占据融合、机载RSS/功耗/时延、
PX4联动飞行或完整M5/Phase 4。下一项按总体计划进入Phase 5软件组合场景与需求矩阵具体设计。
