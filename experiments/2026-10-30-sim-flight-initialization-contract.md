# 初始化准备私有离线合同验证

编号：EXP-20261030-010；日期：2026-10-30；任务：SIM-FLIGHT-INIT-SW-01。
主责任：simulation_engineer；状态：已完成（离线软件与合成验证）。
交付：[合同、文件清单与未验证能力](../docs/SIM_FLIGHT_INIT_SW01_CONTRACT_20261030.md)。

## 1. 范围与环境

用户继续授权已交INIT-DESIGN-01的直接下一项；本轮只实现独立fixture/私有合同/测试和中文交接。
已读根规则/状态/架构、相关目录AGENTS及接口/设计，核对Git dirty/忽略规则和真实生产消费链。
分支feature/engineering-initialization，HEAD=d96d4439da1007489c80e7f21b132abff16505bf。
Python实际核对/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python，全程sim01_env；没有构建或启动新运行。
既有build/等未跟踪内容保留，不碰外层catkin、研究仓、第三方原源或系统依赖。

## 2. 先行预期和步骤

先手工保存独立检查点/时间/查询/单位/缺失/四门预期及N01—24组，再机械提取9份原生msg与已审计源片段。
[oracle目录](../.runtime/runs/flight-init-sw01-oracle-20261030T110243259023/sim_flight_initialization_cases.json)
在生产实现前冻结三输入文件；实现后字节保持，没有Hash或由被测parser生成oracle。
tests只依据这些字面量/原生布局展开合成物理和原文，不把旧status或合成轨迹接在线输入。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -c 'import sys; print(sys.executable)'
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_sim_flight_initialization.py' -v
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_flight_initialization_run.py --full
```

首条定向31项通过；补充文件/纯预算guard后首次完整stage33项新增、飞行125/运动84/全仓1028通过。
随后复核补未来/倒退原生时间拒绝与“未Run不计成功输出”两项边界，以新run完整重跑。
首轮没有失败或扩大阈值，所有旧产物/历史失败保留。

## 3. 最终结果

最终[阶段目录](../.runtime/runs/flight-init-sw01-20261030T111445613013/report.json)与
[旧消息实际genpy兼容](../.runtime/runs/sim-motion-sw04a-20261030T111502953376/report.json)：

| 内容 | 实际结果 | 边界 |
| --- | --- | --- |
| 独立合同/私有字节 | 24预期组、88次JSON实际往返，header/step/query/84事件；terminal另有往返/坏字段测试 | 私有JSON，不冒充新ROS线格式或实际PX4运行 |
| 合成ready | 2500步/84查询，最后500步合成零执行器；四门true、整体通过、控制门false | 只证明checker对冻结输入的行为 |
| 合成missing | 2500步/84查询；采集/物理静稳完整，初始化/输出false、整体失败 | 按预期拒绝运行就绪，不填缺失或回退 |
| 定向/全仓 | 新35项，飞行127/127、运动84/84、全仓1030/1030通过 | 无新准备期或正式性能/飞行结论 |
| 旧公共兼容 | 77场景字节、36公共往返、18合成源转换，25定义/7入口不变 | 用实际生成消息序列化，非mock |
| 保护 | 总466份源码冻结，原458份源码/配置逐文本保持；仅新增8文件与配套文档 | 旧v1/quality-v2、宿主/runner/研究仓不改 |

初次完整stage为[111133676074](../.runtime/runs/flight-init-sw01-20261030T111133676074/report.json)，
仅作中间结果保留。最终结果对应新源码快照及未来/倒退时间、失败Run输出边界。
没有实际daemon查询、FDM/PX4/ROS/Gazebo/RViz、模式/arm/manual/参数写，也没有新受管仿真进程需清理。

## 4. 交接与恢复

完整字段/嵌套/单位/缺失和limits在交付合同及固定fixture中可核对；
源前后、原始HIL与打印原文分别保留，typed参数、同块隔离和四门不能互相替代。
下一项INIT-SW-02才实现独立私有宿主/适配与有界准备，最长10s到界未就绪即失败，不改IC/阈值或无限扩窗。
本轮未验证实际收敛、selected姿态、零执行器链或严格周期绑定，公共v2/长窗/控制仍后续分步。
真实设备、研究质量、DEM/融合与正式PERF继续暂缓；历史/既有dirty保留，不提交/推送。
后续失败以新run恢复，不覆盖旧证据，不把退出当disarmed或着陆。
