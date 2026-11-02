# EXP-20261029-004：P5实际ROS组合与独立回放

日期：2026-10-29；任务：P5-SW-02；主责任：integration_engineer。
类型：真实ROS功能级组合、故障/恢复、公开执行回放、旧入口与轻量回归。
状态：已完成（A/B软件范围），S09/C原生交接未执行。
依据：[设计](../docs/PHASE5_SOFTWARE_COMBINATION_DESIGN_20261029.md)、
[SW-01](../docs/P5_SW01_INPUT_CONTRACT_20261029.md)、ADR-041。
实现/命令/新文件清单见[SW-02交付](../docs/P5_SW02_ROS_COMBINATION_20261029.md)。

## 1. 目的、基线与保护

用户继续后，按SW-02执行已冻结A/B子例；原37子例中的4个S09/C留给SW-03，不静默算通过。
读取根/相关目录规范、状态/架构及字段/传感器/坐标、设计/输入合同，沿真实源状态、
传感器配对、感知信任校验/worker、地图节点/查询、TerrainNode/应用期限/公共回放追踪。
feature/engineering-initialization全部既有修改/未跟踪文件保留，不提交、不推送、不改研究仓库。
只有8个新测试/监督源码及配套文档；旧公共消息、业务实现、launch默认值均未改变。

## 2. 环境与实际命令

实际sys.executable核对为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，所有Python均经
`bash ros_ws/sim01_env.sh ...`。各例的实际Python进程/子进程解释器审计通过。
旧/新ROS类型沿用本仓`.runtime/ros/devel`，未构建外层catkin_ws、未安装依赖或计算Hash。
普通沙箱创建socket被EPERM拒绝后，本机回环ROS测试经自动权限审批执行；不访问外网。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/p5_combination_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/local_map_query_run.py --mode inference --port 11741
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/p5_fixture_run.py --full
```

测试source/observer只由输入调度，事件完成后才由比较器读取独立expected。
每例新Master/run/进程，先等待真实TCPROS业务与观察连接，再按事件推进；未重发丢失帧来补成功。
源状态经ROS到真实传感器构造/配对，感知和mapping仍通过其原公开包装入口处理。
Terrain测试包装每clock调用原有tick及ACK，不改变1s接收超时或公共协议；测试诊断不冒充公共字段。
没有直接发布保存的Bundle替代完整A链，没有把A的Radar点域塞给累计B。

## 3. 预期与最终结果

最终目录：`.runtime/runs/p5-combination-20261029T120350694666/`。

| 对象 | 预期 | 实际 |
| --- | --- | --- |
| 全A/B覆盖 | 33例，S09明确deferred | 33/33，244事件、86检查点、216项独立比较通过 |
| 正常/IR缺失/可信与不可信失败 | 缺IR无Bundle；可信unavailable不提交；不可信无占据；后续恢复 | S01—S03全部通过，原证据时刻/revision保留 |
| 暂停/重复clock/reset/到期 | 业务与墙钟分开，reset锁定；旧M1旧时间查询可仍fresh | S04全部通过，不伪称M1有墙钟存活门控 |
| 35/50/70m/s与5ms/10ms边界 | 携带变换/索引/年龄对独立数值；+1ns拒绝 | S05十个子例通过，非动力学或20ms验收 |
| M4概率/区间/封存/FIFO/缺失/TTL | B独立域、五类查询、旧时间/质量保真 | S06通过，owner/封存数只作声明，不读取私有目录充当应用证据 |
| 应用服务中断/阻塞/迟到/实例pin | 无free fallback；实际外部期限与地形单worker机制分开 | S07通过，旧MapQueryClient仍无主动调用deadline |
| 地图公开回放 | 每例新地图，完整快照/成功传输查询逐字段比较 | 33次执行通过：148占据、143快照、14查询 |
| 地形实际服务收据 | 公开请求/返回可追溯，整组pin与迟到隔离 | 26条服务返回收据，另保留应用本地失败封套 |
| 图、限额、解释器及清理 | 无训练旁路/越层业务订阅；收据不截断；仅清本会话 | 33例审计/常规清理通过，公开JSONL合计2,332,131字节，无限额溢出 |

每例包含inputs/independent-expectations副本、graph.json、public-receipts.jsonl、event-receipts.json、
validation.json、map-observations/snapshots/queries、map-replay.json、进程manifest与cleanup-audit。
总目录sources保留当次测试源码，不以当前Git dirty状态假装存在正式提交版本。

S08的独立地形记录如下；没有将输入预算冒充实际事件数。

| 子例 | 实际记录事件/完整性 | 执行回放结果 |
| --- | --- | --- |
| S08.record | 20，complete；小于冻结上界33 | 执行Provider并逐值一致 |
| S08.overflow | 64，incomplete | terrain_recording_incomplete，执行前拒绝 |
| S08.source_failure | 9，incomplete | v1无法表达来源细错，执行前拒绝 |
| S08.tamper | 原记录11，complete；只篡改新副本expected高度 | 合法schema可读，真实执行报terrain_replay_query_differs |

旧默认入口：`.runtime/runs/local-map-query-inference-20261029T121241634503/`，
实际inference/查询与清理通过。请求首次自动审批未在截止前完成，工具明确允许重试一次，
重试获批且实际通过；不将审批超时解释为动作不安全或技术测试失败。

最终轻量回归：`.runtime/runs/p5-sw01-20261029T121200474234/`，
新增8项比较器/屏障测试，P5定向39/39（2.037s），全仓813/813（60.302s）；
SW-01离线742次消息序列化再次通过，不把它们算作本轮新增ROS运行次数。

## 4. 初次失败、复现与修复

历史目录全部保留，不改冻结预期或覆写结果：

- `p5-combination-20261029T115256917947/`：初始三例2/3。正常链因比较器要求13与13.0的Python类型一致而失败；物理高程改成精确数值等值，bool仍拒绝，并加单元反例。
- `p5-combination-20261029T115448269844/`：首轮全33例29/33。S03.untrusted错误匹配PerfEvent自身sample_id而非parent_sample_id；S03.slow首clock观察连接未就绪；S04.expiry首占据到mapping未连通；S07.map_block子进程SIGINT后仍阻塞而等待超时。原消息已证明相应业务/诊断，修复测试关联/连接/隔离设施。
- `p5-combination-20261029T115929696547/`：前三个复验通过；阻塞调用的启动/关闭耗时超过地形1s接收期限，地形真实unavailable，整例失败，未延长生产超时。
- `p5-combination-20261029T120207265172/`：将独立查询进程在业务clock前预热，服务实际进入后才计外部期限，受控终止该子进程；阻塞隔离和slow两个子例通过。必要的SIGKILL写入/p5/map/cancellation收据，不冒充客户端自行取消或常规优雅退出。
- 最终上述`120350694666`全33例重新执行通过。业务源码/字段/阈值和独立expected保持；测试装配源码按上述问题修复，常规业务节点没有强制退出，隔离查询的故障处置单独登记。

初次外层超时没有在查询自己的finally内完成回收，最终机制在该finally内明确终止/wait。
交付前另在实际ROS所在主机命名空间按本仓P5脚本路径只读检查，当前没有存活的P5运行器/节点/隔离查询进程；
这项当前检查不追写为初次失败时已经通过独立清理验收。
监督器45s上限负责触发worker finally；兜底仅匹配本会话记录的命令/PID/进程组，
不扫描终止其他ROS/PX4/用户进程。未经本轮实际运行的全局故障/原生窗口交接仍留给SW-03。

## 5. 修改清单与下一步

新增8个实现/测试文件的逐项清单见交付文档第1节；另新增
`docs/P5_SW02_ROS_COMBINATION_20261029.md`和本记录。
更新`PROJECT_STATUS.md`、`docs/DEVELOPMENT_PLAN.md`、`docs/STAGE_ADVANCE_PLAN_20261027.md`、
`docs/SYSTEM_ARCHITECTURE.md`、`docs/PHASE5_SOFTWARE_COMBINATION_DESIGN_20261029.md`、
`docs/P5_SW01_INPUT_CONTRACT_20261029.md`、`docs/DECISION_LOG.md`及`docs/EXPERIMENT_LOG.md`，
登记本项完成与SW-03，不覆盖各旧交付时点结论。
交付文档检查：10个相关页面659个本地链接无缺失，`git diff --check`通过。

已有代码：状态/传感器/感知/地图/地形/应用及两种回放沿用现有实现。
本轮实现：显式测试装配、源/故障/公开观察、独立比较与进程监督。
实际验证：33例、216项比较、两类公开执行回放、旧默认入口及813项轻量回归。
未验证：S09/C原生Gazebo/RViz/图故障/新run交接，真实模型/设备/DEM、占据融合、
动态注册、资源/20ms性能及完整Phase 4/5。
下一项P5-SW-03按原计划交接原生窗口与全矩阵；不返回外部数据/研究质量暂缓任务。
