# 空实例三态诊断的只读审计与具体设计

编号：EXP-20261030-005；日期：2026-10-30；任务：SIM-FLIGHT-DIAG-DESIGN-03。
主责任：simulation_engineer；状态：已完成（设计/既有证据核对，不含新模式实施）。
交付：[三态诊断与有界补证方案](../docs/SIM_FLIGHT_DIAG_DESIGN03_20261030.md)。

## 1. 范围与环境

用户“继续”确认上一轮明确的空实例补证设计，当前问题为已存estimator_status六实例无字段。
按根规范读取状态/架构、目录规则与数据/接口/坐标合同，检查dirty、忽略规则和真实调用链。
分支feature/engineering-initialization，HEAD=d96d4439da1007489c80e7f21b132abff16505bf。
保留全部既有修改和未跟踪文件，不自动提交/推送，不安装依赖/Hash或修改同级研究仓库。
Python实际核对/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python，所有检查经sim01_env入口。

## 2. 输入、检查与实际结果

产物目录：[flight-diag-design03-20261030T012035582753125Z](../.runtime/runs/flight-diag-design03-20261030T012035582753125Z/report.json)。
旧输入为SW-02B第二次probe及最终445份源码冻结，不启动新仿真或重复失败probe。

| 检查 | 实际结果 | 边界 |
| --- | --- | --- |
| 源码事实 | 九份源文本、16项指定语句/行号核对通过 | 未从源码猜测当前内部errno或tilt_align |
| 旧raw原文 | exit0/stderr空、estimator_status六空实例，原文逐字相同 | 无载荷不改判为有效或字段0 |
| 旧严格校验 | 原parse_output仍probe_native_incomplete，部分流仍probe_stream_incomplete | 未放宽SW-02B验收或回写旧产物 |
| 唯一有效快照 | 严格JSON重新读取，三实例0/1/2均492000us、lastHIL496000us | 旧数据重读，不是新采集或EKF姿态证明 |
| 相关回归 | [既有49/49飞行测试](../.runtime/runs/flight-diag-design03-20261030T012035582753125Z/flight-targeted.log)通过 | 包含原17项probe/有界子进程检查；本轮未新增测试或三态实现 |
| 内容保护 | 445份源码/配置与上一轮一致，8原生msg/30原桥接源逐文本保持 | 不使用Hash，不重跑原952项全仓或ROS矩阵 |

临时只读审计器冻结源文本/旧输出检查和结果到新目录，不加入生产代码，也不实现新分类器。
复核与测试使用的入口形状：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_sim_flight*.py' -v
```

上述测试由只读审计器以同解释器实际调用，完整输出保存在本轮日志。

## 3. 设计结论

保留旧strict与失败，引入拟议独立sim_flight_uorb_diagnostic.v1和--uorb-diagnostics显式模式。
三态为payload、not_published、payload_unavailable；混合完整/空实例逐块保存，全局不可用，
部分字段/混乱数量/错topic/非有限/异常行仍停止，armed=true不能被空块掩盖。
空字段用null，不输出有效旧快照；单实例无显式编号用null，不据advertise计数推断primary。
输出形状只表明本次无有效载荷，不断言“从未初始化”或copy错误的唯一原因。

仍使用125/250检查点九topic加三个param的21次固定只读计划，原命令白名单、1s/250步、
5s bootstrap/30s session及200ms客户端/400ms组/32KiB原文/8MiB总文件预算均保持。
期限覆盖身份核对/解析/持久化；新模式可继续诊断，不代表状态/控制可用。
分别报告采集完整性、载荷完整性与控制门；旧SW-02B实际未通过不改。
详细字段、精确语法、18组独立先行验收预期、失败/恢复及影响文件清单见设计。

## 4. 未执行与下一项

本轮只改设计和中文记录/索引，没有新合同实现/分类器/fixture、SITL查询、ROS/Gazebo或ULog解码。
全仓952/运动84是上一轮结果，不作为本轮再次验证；新三态合同/21次新采集仍未验证。
下一项SIM-FLIGHT-SW-02C按具体方案先冻结独立原文预期，再实现隔离事件/显式模式和实际有界补证。
不自动扩大准备/活动窗口、启v2、发解锁或控制，不进入真实设备/研究质量/DEM/占据融合/正式PERF。
所有产物新目录保存，恢复维持旧入口即可；旧失败不删除，不把诊断采集完整写成受控飞行准入。
