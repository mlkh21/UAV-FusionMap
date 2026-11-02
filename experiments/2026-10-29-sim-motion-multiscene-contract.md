# EXP-20261029-011 多场景运动输入与独立预期离线验证

日期：2026-10-29；任务：SIM-MOTION-SW-04A；主责任：simulation_engineer。
状态：已完成（离线清单/有界校验/独立预期/真实消息线格式范围）。
依据：[具体设计](../docs/SIM_MOTION_SW04_MULTISCENE_DESIGN_20261029.md)、ADR-043；
交付/文件列表：[合同说明](../docs/SIM_MOTION_SW04A_CONTRACT_20261029.md)。

## 1. 环境与保护

分支feature/engineering-initialization，HEAD=d96d4439da1007489c80e7f21b132abff16505bf。
开始检查Git、忽略规则和真实IC→FDM/场景→raw→Bundle/placeholder→M1/query消费者；
既有大量修改和未跟踪文件全部保留，未提交或推送，没有修改研究仓库。
Python实际sys.executable逐字为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，
所有调用经`bash ros_ws/sim01_env.sh ...`。没有环境/依赖安装，没有运行构建或外层catkin。

## 2. 修改与预期保存顺序

新增8个代码/输入文件：独立configs清单、simulation逻辑校验模块、tests独立字面量/fixture/
oracle/checks/入口/23项测试；新增本记录和合同说明，同步状态与必要索引。
生产模块不导入测试oracle；旧公共字段、旧profile、默认启动及算法/地图实现没有修改。

先在[175017286505](../.runtime/runs/sim-motion-sw04a-20261029T175017286505/independent-expectations.json)
保存独立字面量/77组struct预期，随后补完整合成源输入并在
[175152509142](../.runtime/runs/sim-motion-sw04a-20261029T175152509142/source-inputs.json)另目录冻结。
实现前后均未用生产模块生成预期。
复核发现TTL reference若按S07从100ms开始完整九帧，应为revision9；原先孤立400ms开始示例
的revision6不适合完整序列。此处在实际语义校验前更正，
[175530090613](../.runtime/runs/sim-motion-sw04a-20261029T175530090613/independent-expectations.json)
另目录保存，旧两份保留，未依据实测输出调整状态/TTL/容差。

首轮77协议/36公共往返、18合成转换、65项定向及884项全仓通过，见
[首轮报告](../.runtime/runs/sim-motion-sw04a-20261029T175530090613/report.json)。
收尾审查补充冻结输入缺项/重排拒绝及测试，防止整组样例被漏验；另加恰好256KiB合法输入、
几何监督字段拒绝，并记录实际生成类来源，随后新目录复验。没有删除失败或放宽预期；本轮无测试失败。

## 3. 最终实际验证

主证据：[180043096394](../.runtime/runs/sim-motion-sw04a-20261029T180043096394/report.json)。
实际命令（内部仍先freeze，再导入生产校验/codec进行verify）：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_motion_multiscene_run.py --full
```

| 检查 | 实际结果 | 证据 |
| --- | --- | --- |
| 新增/运动定向 | 新增23项，66/66通过 | [targeted.log](../.runtime/runs/sim-motion-sw04a-20261029T180043096394/targeted.log) |
| 全仓轻量 | 885/885通过，59.416s | [full.log](../.runtime/runs/sim-motion-sw04a-20261029T180043096394/full.log) |
| 实际场景消息 | 77组/19,751字节，独立struct字节及真实genpy反序列化逐值一致 | [冻结输入](../.runtime/runs/sim-motion-sw04a-20261029T180043096394/wire-inputs.json)、同目录expected/actual二进制及report.generated_types |
| 旧公共空观测消息 | 36组/11,191字节，10空帧与六查询往返、缺失flags/规范质量槽保持 | [public-empty-validation.json](../.runtime/runs/sim-motion-sw04a-20261029T180043096394/public-empty-validation.json)、同目录public-empty二进制 |
| 合成源转换 | 18次通过，初始方向/非零ECEF差、feet→m、FRD→FLU、原整数时间匹配 | [source-validation.json](../.runtime/runs/sim-motion-sw04a-20261029T180043096394/source-validation.json) |
| 拒绝/边界 | 坏版本/身份/路径、IC/几何绑定、bool/浮点step、坏epoch/fault、重复键/非有限/超长/超深/超量、监督字段、部分证据/输入缺项重排拒绝 | 23项新增测试，定向日志 |
| 兼容 | 25份既有定义、7份旧配置/入口逐值不变 | old-definitions.json、old-entrypoints.json与report计数 |
| 文档/静态检查 | 10份文档762处相对链接、6份Python AST、状态/结果计数和git diff --check通过 | [最终检查](../.runtime/runs/sim-motion-sw04a-20261029T180043096394/document-final-checks.json)，不替代运行验证 |

空观测输入是纯软件fixture：10帧valid空占据推进到revision10/unknown，未产生free。
历史序列在900ms的header/revision9保持400ms cell；900ms query occupied、+1ns stale；
899999999ns因早于最新地图而unavailable，新身份不读取旧证据。
MapQueryResult旧codec将缺失uncertainty规范化为unavailable结构，概率保留原float32精度，
状态/缺失flags和原证据整数时间精确核对。

## 4. 未验证能力、风险与恢复

没有启动ROS Master/Gazebo/PX4/JSBSim、新Camera/Ray或原生窗口；没有实际新轨迹/遮挡/空回波/几何切换。
18次转换使用合成原始字段，77组消息中的姿态是协议算例，不是假装飞行实测记录。
新模板当前仅具名逻辑数据；旧world生成器仍自动加ground，后续必须显式实现真正空碰撞域。
新IC自由动力学、切换屏障/Camera缓冲、解析边界分类/实测误差、完整公共回放/兼容入口及9场景预算
适用性仍未验证；本轮不重复旧窗口/旧运行短测充作新进展。
真实设备/研究质量/DEM与占据融合/机载RSS/正式PERF-01/完整阶段退出保持未关闭，research继续fail-closed。

每次保存新目录，不覆盖旧预期/actual/日志；部分证据拒绝复用，只另建run。
没有运行服务需要停止或回滚。下一项SW-04B显式装配/几何切换/场景化核验，SW-04C再完成最终矩阵和原生交接。
