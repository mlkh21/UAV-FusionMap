# EXP-20261027-004：Phase 3统一感知入口与有界CPU执行

日期：2026-10-27；主责任：perception_engineer；状态：本记录初次为ROS阻塞，后续已完成软件交接。
关联：[跨阶段计划](../docs/STAGE_ADVANCE_PLAN_20261027.md)。
同日用户再次授权后，旧入口和组合ROS均实际通过；当前结论及M1/应用后续工作见
[EXP-20261027-005](2026-10-27-p3-m1-app-handoff.md)。下文保留初次实现与权限阻塞事实。
分支`feature/engineering-initialization`，保留原有未提交改动，不提交、不推送。

## 当前问题与实现

P3-SW-01将原ROS回调中的输入合同、三模式选择及异常出口收敛到
`perception/ufm_perception/engine.py:PerceptionEngine`。外层身份/上下文不可信抛
`UntrustedInputError`，节点只诊断拒绝；可信上下文下的坏组合或坏后端结果输出
同身份/时刻的空unavailable。原始输入深拷贝后交给后端，避免后端改写身份再导致
失败结果带错时间。disabled/placeholder不导入研究preflight、torch或研究仓库。

`output_contract.py`检查schema、run/clock/sample、Radar参考时刻、source_type、
odom坐标、原观测时刻SpatialContext、配置几何、观测域来源、整数XYZ索引、
重复体素、概率、observed布尔值及质量。错误结果不进入ROS序列化/地图。
正常placeholder函数及其默认输出保留；滚动原点计算提取为本模块公共辅助函数，
生产和输出校验共用同一格点计算，不在ROS包装或mapping重复实现。
训练字段拒绝常量由轻量input_contract维护，research preflight复用同一常量。

P3-SW-02增加`worker.py:BoundedPerceptionWorker`和节点默认关闭的worker开关：
一次最多1个活动子进程，0个等待任务；用spawn隔离CPU任务。
开启必须显式给定`~worker_deadline_s`，单调墙钟deadline从启动任务前开始计算，
包括spawn成本，不替换5ms同步、10ms位姿年龄、40ms匹配等待或20ms正式指标。
忙碌时新输入立即输出`perception_backend_busy`；此后旧任务结果因输出水位而丢弃，
不在新输入失败消息之后发布旧观测。超时输出`perception_backend_timeout`，先
terminate并join，必要时kill并join；崩溃输出`perception_worker_exited`；shutdown
关闭轮询线程与子进程。恢复使用新任务。测试只证明CPU替身，未证明GPU后端可安全中断。

ROS节点主线程/回调与墙钟轮询线程共用锁；不使用受冻结/暂停仿真clock影响的Timer。
默认同步模式继续沿用原计时阶段名；新worker模式的耗时包含调度与子进程启动，不能
套用旧PERF-01-A各同步阶段分布宣称性能收益。

P3-SW-03已准备`ros_ws/perception_stage_run.py`、测试专用后端及独立观察者。
场景预期：正常→错frame输出→恢复→慢任务+忙碌拒绝/旧结果丢弃→恢复→超时→恢复；
逐次核对地图revision、观测时间、stale查询、训练隔离和清理。该场景尚未运行。

## 验证结果

解释器经实际命令确认固定为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。
所有测试通过`bash ros_ws/sim01_env.sh ...`执行。

- 首次新入口测试因`engine.py`尚未实现而RED；实现后GREEN。
- 10项纯业务入口测试：三模式、错身份/时间/frame/网格/观测域、坏体素/质量、
  原子地图拒绝和合法恢复、深拷贝隔离、训练字段拒绝、非默认/滚动几何；新进程中
  实际调用disabled/placeholder并检查无研究preflight/torch导入。
- 5项真实spawn进程测试：正常返回、超时终止且下一帧恢复、零队列忙碌拒绝和
  旧结果丢弃、子进程异常退出、活动任务关闭；未遗留本测试子进程。
- 节点回调测试使用真实ROS消息编解码：默认计时端点、坏输入、后端异常、可选
  worker发布、墙钟deadline和恢复。此处mock rospy传输，不是在线ROS图证据。
- 全仓轻量回归461/461通过；感知相关定向25项通过；新增ROS工具语法检查通过，
  `git diff --check`通过。

测试命令：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

## 未执行的ROS命令与权限阻塞

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/perf01a_run.py --duration-s 2 --scenario small --port 11621
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/perception_stage_run.py --port 11623
```

沙箱内直接socket预检报`PermissionError: [Errno 1] Operation not permitted`。
旧placeholder回归的沙箱外审批首次及允许的一次重试均因自动权限审查未在截止前完成
而被拒绝创建进程；新组合场景的审批也同样超时。上述命令均未启动，未产生本轮ROS
run、P99、连接图或清理证据；这不是测试业务失败，更不能写成通过。

P3-SW-01/02的实现和轻量测试已有，ROS兼容/组合交接仍待执行，工作包暂不标已完成。
M1回放及application客户端按P3-SW-03交接依赖尚未实施。研究checkpoint/forward、
真实设备、模型质量和正式PERF-01均未运行。

## 文件与恢复

新增业务：engine.py、output_contract.py、worker.py；修改轻量input_contract、
研究preflight常量引用、placeholder滚动原点辅助和包导出；修改现有感知ROS节点。
新增engine/worker测试与测试专用ROS后端/观察者、P3运行器；更新原节点测试的后端
patch位置及worker用例。公共消息及层间字段未改变。

worker默认关闭即走同步入口；不把测试后端注册为部署模式或research。
需要恢复旧实现时仅审查本轮文件补丁，不重置已有脏工作区、不动历史run或研究仓库。
潜在风险为严格输出合同误拒绝未声明的后端约定、spawn启动开销与ROS运行兼容；
实际组合ROS验收前不将代码存在等同工程交接完成。
