# SIM-FLIGHT-SW-01私有飞行合同与离线验证

编号：EXP-20261030-001；日期：2026-10-30；主责任：simulation_engineer。
状态：已完成（私有离线合同/有界校验/旧协议兼容子范围）。
依据：[设计](../docs/SIM_FLIGHT_DESIGN_20261029.md)、ADR-044；
交付及修改文件清单见[合同说明](../docs/SIM_FLIGHT_SW01_CONTRACT_20261030.md)。

## 1. 问题、范围与环境

真实桥接已有PX4执行器写同一FDM，但没有当前周期绑定、超时拒绝与FDM结果的完整证据。
本轮先定义可审计的私有数据，不以旧1秒自由动力学或离线codec通过宣称受控飞行。
用户连续“继续”授权当前SW-01范围；分支feature/engineering-initialization，
HEAD=d96d4439da1007489c80e7f21b132abff16505bf。大量既有dirty/未跟踪文件全部保留。
Git及忽略边界、现有生产消费链按设计复核；不改旧消息、默认入口、第三方源或同级研究仓库。

实际解释器核对为/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python，全部Python经sim01_env入口。
没有启动FDM/PX4/ROS/Gazebo、新控制客户端或长任务，没有安装依赖、计算Hash、提交或推送。
新配置/模块/测试共六份；文档更新状态、接口及ADR索引。需要撤回时只停用新增离线入口，
旧运行链不依赖这些文件；历史产物不覆盖或删除。

## 2. 独立预期与实现

先保存[独立预期](../.runtime/runs/sim-flight-sw01-20261030T000905024587/independent-expectations.json)，
再实现标准库flight_contract；最终逐字节复核该预期未改，不从被测映射反向生成oracle。
预期包含ground IC、2/5/7/4×−1/−1/−1/+1、三组float32探针、100个未来采样点边界及合成流统计。
manual x=−178对应约8.01度仅为设计算例，不发送命令。

实现固定observation_only/commands_enabled=false的具名profile、严格JSON/JSONL编解码与有界流校验。
缺失执行器为null，区别于disarmed全零；原始uint64时间、float32值、peer/接收序号、
属性before/requested/after、FDM ran/result/前后时间及整数墙钟分开保存。
拒绝未知/训练监督字段、坏版本/身份/枚举、非有限/重复键/非法编码及超深/超长/超容量。
逐流校验连续步/属性/独立时间顺序、bootstrap500步/5s墙钟、失败terminal及后续拒绝；
输入/上一条状态独立复制，实际文件字节预算包括空白，超长整数在转换前拒绝。

binding_status固定unverified；合成包故意不假定发送/回包时间相等，控制门始终false。
结构合法的armed单条探针在observe流中拒绝。合法短前缀不是完整40s日志或控制许可。
100个采样时刻只为离线表，ground .5m未安装到FDM或旧Gazebo v1。

## 3. 实际执行与结果

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_flight_run.py --full
```

最终目录[sim-flight-sw01-20261030T002214270144](../.runtime/runs/sim-flight-sw01-20261030T002214270144/report.json)，
其引用的[旧协议/回归目录](../.runtime/runs/sim-motion-sw04a-20261030T002214316781/report.json)为实际生成目录。
先冻结完整当前源码文本和输入，再验证，最后复核429份源码未变；没有用mock替代旧ROS线格式。

| 验证 | 实际结果 | 能力边界 |
| --- | --- | --- |
| 新定向 | 25/25通过 | 包含float32负零、整数时间、坏字段/预算、bootstrap边界、FDM网格/步长及导入隔离 |
| 私有JSON | 8组真实字节往返通过 | profile/IC/header及五类合成record，不是MAVLink实际wire |
| 独立预期 | 3映射探针、100时刻、两条JSONL一致 | 两条只有1次合成执行器观测，不是运行收据 |
| 旧场景协议 | 77组真实genpy字节、36公共往返/18合成源转换通过 | 不重跑旧ROS或实际运动矩阵 |
| 旧运动定向 | 84/84通过 | 受影响合同回归 |
| 全仓轻量回归 | 928/928通过，64.221s | 不含训练/完整模型/正式PERF或新飞行运行 |
| 交接隔离 | 旧423份源码、25份消息/服务定义、7入口及19项设计源事实不变 | [文本核对报告](../.runtime/runs/sim-flight-sw01-20261030T002214270144/handoff-audit.json)，不以Hash替代内容 |

新模块独立导入不拉入rospy/pymavlink/torch或ROS业务合同；生产目录无新模块/profile消费者。
各预算测试使用小限额注入，正式profile的64MiB/12288等边界保持，不做大型内存或机载性能实验。

## 4. 保留的失败与修正

初次23项中1项预算测试失败：[原始日志](../.runtime/runs/sim-flight-sw01-20261030T000905024587/initial-targeted.log)。
原因是测试缩小内部限额，却未同步其输入头部固定profile，先触发profile一致性拒绝。
仅修测试注入，使其命中目标资源边界；未放宽正式限额。
后续补bootstrap/源时间相等与越界、大整数字面量、自包含源码冻结以及生成器修改旧对象的反例。
终审进一步要求成功Run的单步增量本身满足4ms±1ns，不能只检查前后各自距网格≤1ns；
加入前−.9ns/后+.9ns反例，最终代码重新完成25/84/928全部验证。
中间成功运行也保留，最终结论只引用上述最终目录。

## 5. 未验证能力与下一项

未验证真实HIL包因果关系、实际属性/FDM读回、peer认证、就绪/armed/离地或稳定飞行；
没有v2公共codec/端点、新ground/40s装配、命令或RViz飞行显示。
没有RSS/机载资源/正式PERF、真实Radar-IR模型质量、DEM/占据融合；research继续fail-closed。

下一项SIM-FLIGHT-SW-02：本仓适配隔离构建到.runtime/ros，最多250步/1秒采集实际
HIL原值/接收序号、属性与同FDM返回；不发heartbeat/arm/manual/参数写，不启v2或长准备。
ground .5m只接私有诊断宿主，不能接旧Gazebo v1的z>.5端点。
bootstrap未就绪、缺包或失败必须明确留证，禁止填零、静默沿用或将unverified当匹配。
SW-03/04继续按设计依赖推进，不反复回到真实数据缺失/暂缓研究质量任务。
