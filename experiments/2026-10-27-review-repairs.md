# EXP-20261027-002：审查修复与运行配置收敛

日期：2026-10-27；主责任：integration_engineer；状态：已完成（软件修复范围）。
任务：OPT-01；关联REQ-02/03/04/05/07/10/13/14；用户已确认按审查策略修复。

## 目的与范围

修复已复现的数据错误、失效传递和配置不一致，限制身份历史规模，提供独立软件
入口并整理当前状态。分支为feature/engineering-initialization；工作区已有大量
未提交及未跟踪实现，本轮在其上增量修改，未提交或推送。
不修改同级研究仓库、原始数据、checkpoint、原环境及旧run，不计算额外哈希。

## RED与修复

| 问题 | 修复前独立反例 | 修复后行为 |
| --- | --- | --- |
| PointCloud2字段布局 | 合法反向布局应为x=3、doppler=2.5、power=7，实际x=7、doppler=-1、power=3 | 字段名按实际offset排序再与read_points值配对，保留大小端与字段语义检查 |
| 未知枚举/版本 | 变换2/255均被当作available；unsupported schema仍能融合 | 共用Header/枚举校验，未知值拒绝；纯业务地图先验证再修改 |
| 多点同格 | 同一0.5m格内多个点触发duplicate occupancy voxel | 聚合为一个0.9体素，不因点数提高概率 |
| 后端异常 | 模拟ROS回调只有1条诊断、0条占据消息 | 已解码输入输出保留身份/时刻的空unavailable；旧地图revision与观测时间不刷新 |
| 配置覆盖 | 默认噪声0.25局部覆盖range后，runner浅合并得到0.0 | 共用深合并解析器；CLI缺省不覆盖场景，显式0仍覆盖 |
| 身份历史 | pending=0仍持续保存完整输入 | 小容量长序列测试始终有界；过旧重传不能复活，窗口内冲突和终止优先保留 |
| 观察器依赖 | 无event/snapshot订阅者时节点启动超时 | 独立入口关闭诊断与观察器等待；旧实验图保留原就绪规则 |
| 忽略与文档 | 5个原有新增测试/检查及7份小型实验记录被隐藏，状态页727行且含过时下一步 | 恢复Git可见候选；当前页68行，原正文完整保存在历史快照 |

以上RED由定向unittest和上一轮审查中的公开函数/模拟回调复现。后续GREEN新增
非法输入后恢复、非默认网格、计时端点及socket预检失败落盘检查。
最终轻量回归：`423/423`通过（原408项加本轮15项测试方法，包含多组subTest）。

## 实际环境与命令

解释器先核对为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，所有命令均通过
`bash ros_ws/sim01_env.sh ...`；ROS使用独立Master/端口和新run，所有本次进程已清理。
轻量回归：`python -m unittest discover -s tests -p 'test_*.py'`。

| 实际命令（省略统一环境前缀） | 结果 | 新证据目录（.runtime/runs下） |
| --- | --- | --- |
| `python ros_ws/local_map_query_run.py --mode inference --port 11591` | 20源样本、查询revision20、observed=true、概率约0.9；分类阈值未配置故status=unknown；感知/地图最终配置相同，无性能事件/训练/LiDAR话题；清理通过 | `local-map-query-inference-20261027T100143544352` |
| `python ros_ws/perf01a_run.py --duration-s 2 --port 11592` | 旧placeholder入口40组地图闭合，退出0 | `perf01a-20261027T100225614033` |
| `python ros_ws/perf01a_async_run.py --duration-s 2 --scenario parameterized_sensors --verify-radar-values --audit-online-graph --port 11593` | 参数化异步链路、Radar逐点守恒、在线图隔离与清理通过；20次预期严格拒绝；开发机P99=43.920128ms，20ms诊断未通过 | `perf01a-async-20261027T100309482423` |
| `python ros_ws/perception_mode_run.py --mode disabled --port 11594` | 20个Bundle/不可用占据/地图拒绝，0快照，空地图查询与清理通过 | `perception-mode-disabled-20261027T100405814528` |
| `python ros_ws/sim01_imu_run.py --enabled --port 12594` | 源/适配IMU各22条有效及1条终止、clock22/状态13，清理通过 | `sim01-imu-enabled-20261027T100413481542` |
| `python ros_ws/perception_mode_run.py --mode research --port 11595` | research阻塞明确传播20条不可用占据，0地图快照，无forward，清理通过 | `perception-mode-research-20261027T101202451921` |
| `python ros_ws/local_map_query_run.py --mode rolling --port 11596` | 7条占据、5快照、20查询；移动/unknown/老化/隔离及清理通过 | `local-map-query-rolling-20261027T101209076946` |
| `python ros_ws/perf01a_run.py --duration-s 2 --segmented-timing --port 11597` | 最终计时端点修复后40组闭合与分段计时通过；occupancy_ready仍在编码前 | `perf01a-20261027T101719614463` |
| `python ros_ws/sens_train_01_run.py --fixture yaw --port 11598` | Radar/IR/监督各20条、状态/clock各22条，独立训练图与unknown探针通过，端口释放 | `sens-train-01-20261027T101758629835` |

首个无观察器入口尝试在沙箱内创建socket被拒，目录
`local-map-query-inference-20261027T100126072308`保留，未启动ROS；原运行器的finally
重复端口探针还使该次无法完成manifest写入。获准沙箱外运行后通过。随后补上finally
探针异常处理，并以不创建socket的单元反例验证：退出1、保留失败manifest和cleanup审计，
不启动进程。未回填首个失败目录或伪造原始日志。

## 本轮修改文件

- 根目录：`.gitignore`、`README.md`、`PROJECT_STATUS.md`。
- configs：`local_map_fixture.yaml`、`sim01_state.yaml`。
- sensors/ufm_sensors：`identity_history.py`、`clock_gate.py`、`imu_adapter.py`、`perf01a_async.py`、`perf01a_fixture.py`。
- perception/ufm_perception：`placeholder.py`、`modes.py`；mapping/ufm_mapping：`local_map.py`。
- ros_ws装配与工具：`runtime_config.py`、`radar_raw_bridge.py`、`perf01a_ros.py`、`perf01a_async_run.py`、`local_map_query_run.py`、`launch/inference_fixture.launch`、`launch/perf01a_placeholder.launch`。
- ROS契约：`src/uav_fusionmap_msgs/src/ufm_ros_contract/{codec,imu_codec,perf01a_codec,perf01a_ros}.py`。
- ROS节点：`src/uav_fusionmap_perception/scripts/perf01a_placeholder_node.py`、`src/uav_fusionmap_mapping/scripts/perf01a_map_node.py`、`src/uav_fusionmap_sensors/scripts/{perf01a_sensor_node,state_adapter_node}.py`。
- tests：`test_iface01_radar_raw.py`、`test_perf01a_contract.py`、`test_perf01a_ros_codec.py`、`test_perception_node.py`、`test_sim01_clock_gate.py`、`test_imu_contract.py`、`test_perf01a_async_profile.py`、`test_map_query_node.py`、`test_perf01a_async.py`、`test_perf01a_async_wrappers.py`、`test_local_map_supervisor.py`。
- docs：`RUNTIME_CONFIGURATION.md`、`PROJECT_HISTORY_20261027.md`、`SYSTEM_ARCHITECTURE.md`、`DEVELOPMENT_PLAN.md`、`DATA_FORMAT.md`、`SENSOR_INTERFACE.md`、`VERSION_AND_ARTIFACT_POLICY.md`、`DECISION_LOG.md`、`EXPERIMENT_LOG.md`；新增本记录。

解除忽略后显现的原有研究preflight、IMU、失效模式测试和实验记录不是本轮新实现；
既有未提交工作保留。原状态正文仅机械调整到docs目录的相对链接，没有删除历史结论。

## 限制、风险与恢复

本轮没有改变消息字段/版本、5ms同步、40ms默认等待、20ms目标、在线LiDAR隔离或阶段
门槛。独立入口仍为paired软件fixture；不宣称实际硬件频率、模型质量或机载性能通过。
结构上限不是RSS验收；有界窗口外不检测被改成未来时间的全部旧身份冲突，生产者
仍须遵守run内sample_id唯一。纯业务API原默认值与旧具名实验oracle保留兼容。
未采纳候选仍默认关闭并保留复现代码/记录，新独立入口不使用它们；没有删除历史工具。

公共消息的版本/未知枚举现在严格拒绝，依赖错误编码的外部调用者需改正输入，不能绕过
校验。需要旧实验就绪/探针口径时使用原runner；代码恢复只针对本轮补丁，保留已有
用户改动和所有产物。正式PERF-01、ENV-03、真实设备、研究质量和M1后续阶段仍开放。
