# EXP-20261027-005：P3软件交接、M1占据回放与应用查询客户端

日期：2026-10-27；状态：已完成（所列软件/fixture子范围）。
主责任：integration_engineer；P3由perception_engineer、回放由mapping_engineer负责。
依据：[跨阶段计划](../docs/STAGE_ADVANCE_PLAN_20261027.md)及用户“允许进行，继续”。
分支`feature/engineering-initialization`，保留全部既有改动，不提交/推送或修改研究仓库。

## 1. P3-SW-01/02/03交接

用户授权后独立ROS短测可实际执行；前轮权限超时事实继续保留在
[EXP-20261027-004](2026-10-27-p3-perception-engine-worker.md)。

| 运行 | 结果及证据 |
| --- | --- |
| 旧placeholder入口，2秒small | 40组Bundle/占据/地图闭合；[报告](../.runtime/runs/perf01a-20261027T133450620737/perf-report.json) |
| P3 CPU测试后端组合图 | 8次Bundle发布、7个占据结果、4次有效地图快照；坏frame输出拒绝、busy新帧拒绝、旧慢任务结果丢弃、独立timeout及恢复均通过；[验收](../.runtime/runs/p3-software-20261027T133511656868/validation.json)、[原始收据](../.runtime/runs/p3-software-20261027T133511656868/receipts.json)、[清理](../.runtime/runs/p3-software-20261027T133511656868/cleanup-audit.json) |
| disabled新入口兼容 | 20个有效Bundle、20个不可用占据与拒绝事件，无新地图证据；[验收](../.runtime/runs/perception-mode-disabled-20261027T134246784964/validation.json) |
| research前置阻塞兼容 | 同样20组不可用链路；保持model来源与明确阻塞原因，不执行forward；[验收](../.runtime/runs/perception-mode-research-20261027T134242402698/validation.json) |

组合图查询验证旧地图时间不刷新且返回stale，合法新观测恢复occupied；运行时图无训练/LiDAR，
感知只订阅Bundle及公共clock，地图只订阅占据及公共clock。上述运行均清理本次进程和端口。
P3三项只关闭软件执行/错误边界交接，不关闭真实融合质量或完整Phase 3。

## 2. M1-SW-02：复用公开占据收据回放

新增`mapping/ufm_mapping/replay.py`，只调用`SparseLocalMap.update/snapshot/query`。
每次回放创建新地图，绑定显式run_id；按记录接收顺序处理，不排序、改写观测或自动跨run继承。
保留每条fused/not_fused/rejected结果；拒绝输入必须不改变公开快照。

装配工具`ros_ws/local_map_replay.py`只读既有`receipts.json`，复用observations/
occupancies/published、snapshots和queries；新报告写入独立`.runtime/runs/local-map-replay-*`。
不定义新的公共ROS字段或记录协议，不读取Radar、IR、LiDAR、模型张量或地图私有缓存。
快照/查询逐字段比对，整数身份/时间精确；float32量采用1e-6绝对容差。

查询按记录的result.revision选择已复现的地图版本，再使用原request重算全部响应字段。
该revision是回放查询的调度输入，不是输出通过的oracle；概率、索引、时间、状态和质量
仍与原始响应独立对账。这能复现记录版本的查询，**不证明原ROS线程/墙钟交错**。

| 来源及场景 | 对账结果 | 回放证据 |
| --- | --- | --- |
| 新滚动ROS图，平移/偏航、空回波、unavailable、旧帧拒绝、大位移淘汰与恢复 | 7占据、5快照、20查询一致，1条迟到拒绝；[源验收](../.runtime/runs/local-map-query-rolling-20261027T133659504776/validation.json) | [回放报告](../.runtime/runs/local-map-replay-20261027T133933528952/report.json) |
| P3故障图，同run失败→老化→恢复 | 7占据、4快照、5查询一致 | [回放报告](../.runtime/runs/local-map-replay-20261027T133933527845/report.json) |
| 最终应用查询ROS图，显式occupied/free、unknown、stale、空地图/错域/错run及质量 | 5发布占据、2快照、30查询一致，1条foreign run拒绝 | [回放报告](../.runtime/runs/local-map-replay-20261027T134500208550/report.json) |

纯业务测试另覆盖相同sample重复不累计、先unavailable再迟到记录仍拒绝、不自动改序、
重复回放同结果、跨run输入拒绝与新run新实例。默认map配置来自现有local_map_fixture.yaml；
自定义配置/任意历史运行不是自动兼容范围，记录必须明确提供相应地图构造参数。
当前CLI仅支持本次具名fixture的共享配置、滚动开关及显式分类阈值。

## 3. APP-SW-01：应用公开查询客户端

新增`application/ufm_application/query_client.py:MapQueryClient`，通过注入transport消费
MapQueryResult；不导入mapping或传感器。请求显式含map/frame/run/clock、纳秒时刻、
XYZ米制点及max_age_ns。原样返回五种状态、reason、索引、观测时间、概率及质量，
越界保持unknown/outside_coverage。点查询接口不含完整coverage，不捏造该字段。
传输失联或非法响应生成明确unavailable，概率/观测时间不可用且observed=false，
不做概率重新分类或把stale/unknown解释为free。

新增`ros_ws/map_query_client.py`作为独立ROS包装，默认调用既有`/uav/map/query`；
只增加可选`--service`客户端参数，不新增服务。服务发现墙钟等待2秒，调用异常明确返回；
未承诺对已经连接但不响应的任意ROS服务提供端到端deadline。

在旧query fixture中增加默认关闭的`--application-client`测试选项，复用原地图与公开
服务验证五类响应逐值一致；独立CLI一次返回occupied、另一次访问缺失服务返回unavailable。
不是在业务客户端中引入fixture。最终[ROS验收](../.runtime/runs/local-map-query-enabled-20261027T134419270272/validation.json)
有30条原查询及7条应用响应，[清理](../.runtime/runs/local-map-query-enabled-20261027T134419270272/cleanup-audit.json)
通过。首个通过run`local-map-query-enabled-20261027T134125437302`保留；加强客户端证据时间/
有限概率检查后使用上述新run复测通过。初次应用运行审批返回不完整，命令未执行；核对
隔离范围和语法后重试实际通过，不再构成当前阻塞。

## 4. 复现

统一使用`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，ROS经`bash ros_ws/sim01_env.sh ...`。
本次ROS权限按用户明确授权执行，默认不接研究后端、真实设备、飞控或训练监督。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/perf01a_run.py --duration-s 2 --scenario small --port 11621
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/perception_stage_run.py --port 11623
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/local_map_query_run.py --mode rolling --port 11624
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/local_map_query_run.py --mode enabled --application-client --port 11625
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/perception_mode_run.py --mode disabled --port 11626
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/perception_mode_run.py --mode research --port 11627
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/local_map_replay.py --input .runtime/runs/local-map-query-rolling-20261027T133659504776/receipts.json --run-id local-map-query-rolling-20261027T133659504776 --rolling --free-threshold .3 --occupied-threshold .7
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

新增回放4项、应用4项定向；最终全仓469/469通过，`git diff --check`通过。
全部新ROS run有独立产物和清理收据；离线回放不启动ROS进程、不修改输入。

## 5. 文件与限制

新增业务模块：`mapping/ufm_mapping/replay.py`、`application/ufm_application/__init__.py`、
`application/ufm_application/query_client.py`；新增装配工具`ros_ws/local_map_replay.py`、
`ros_ws/map_query_client.py`及两个定向测试；修改`local_map_query_run.py`和
`check_local_map_query_ros.py`，仅增加可选应用验收。当前研究仓库、模型、消息字段、
地图融合规则和原默认入口未改变。恢复可直接使用不带新选项的旧入口，保留历史产物。

已关闭本批P3-SW-01/02/03、M1-SW-02和APP-SW-01的软件子范围。
尚未验证：研究checkpoint加载/forward/质量、真实标定与设备时钟、机载资源/功耗、
正式PERF-01、完整Phase 2/3或正式M1。GPU取消、概率累计、Scene Map、DEM、
规划算法和飞行不在本次范围。下一软件工作为M2概率更新具体方案及软件试制准入评审；
既有M1→M2实施门禁保持，不直接开发M2算法。
