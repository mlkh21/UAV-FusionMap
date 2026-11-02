# 原生NaN质量语义的只读审计与隔离设计

编号：EXP-20261030-007；日期：2026-10-30；任务：SIM-FLIGHT-DIAG-DESIGN-04。
主责任：simulation_engineer；状态：已完成（设计/只读验证，不含新合同实施）。
交付：[两质量字段隔离补证方案](../docs/SIM_FLIGHT_DIAG_DESIGN04_20261030.md)。

## 1. 目的与环境

用户“继续”确认上一轮明确的原生NaN语义/隔离设计，输入为SW-02C已存第11次原文及源码。
先读根规范、项目状态/架构、目录规则、数据/接口/坐标合同并核对dirty、忽略与真实调用链。
分支feature/engineering-initialization；HEAD=d96d4439da1007489c80e7f21b132abff16505bf。
Python实际核对/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python，统一sim01_env入口。
不重跑相同失败SITL、不装依赖/算Hash、不修改同级研究仓、旧合同/公共字段/默认入口或历史产物。
既有修改和未跟踪文件全部保留，无提交/推送。

## 2. 实际只读验证

产物：[flight-diag-design04-20261030T094904639779](../.runtime/runs/flight-diag-design04-20261030T094904639779/report.json)。

| 检查 | 实际结果 | 限制 |
| --- | --- | --- |
| [源事实](../.runtime/runs/flight-diag-design04-20261030T094904639779/source-checks.json) | 九份冻结文本、20项指定语句/行号核对通过 | 源条件不冒充实际已验收的EKF状态 |
| [旧输出字段核对](../.runtime/runs/flight-diag-design04-20261030T094904639779/archived-status-field-audit.json) | 六实例字段集完整，各两处准确nan，共12处；其余字段可按原规则解析，flags十进制/32位标注一致 | 离线原文投影，不生成新合法事件或改写旧失败 |
| 同载荷源位 | 六组mask均537002496，GPS/光流/EV位置/EV速度四位均0，符合拟议两字段隔离条件 | 不推出无全部水平辅助、数值崩溃或唯一故障原因 |
| [独立算例](../.runtime/runs/flight-diag-design04-20261030T094904639779/independent-mask-examples.json) | 先保存16组四源位组合与独立允许/拒绝预期，掩码算术核对通过 | 不是未来codec测试，也不实施新分类器 |
| 原拒绝保持 | snapshot v1与diagnostic v1对原文均仍报probe_native_float | 不回填旧SW-02B/C验收或替换nan为0 |
| 相关回归 | [既有69/69飞行测试](../.runtime/runs/flight-diag-design04-20261030T094904639779/flight-targeted.log)通过 | 本轮未新增测试/fixture或重跑972项全仓、84项运动/ROS矩阵 |
| 内容保护 | 451份源码/配置与SW-02C最终冻结一致，8原生msg/30桥接原源逐文本保持，旧raw字节未改 | 不依赖Hash，不产生运行能力声明 |

只读审计器保存新目录下的原文副本/源文本/结果；没有在旧run旁新增派生产物或改写其manifest。
审计内部调用既有原生有限解析函数只处理有限字段，nan以原token单列，不调用float('nan')或构造已接受事件。
69项测试由审计器以固定解释器实际调用，入口形状：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_sim_flight*.py' -v
```

## 3. 设计结论

get_innovation_test_status先设vel/pos=NAN，随后按GPS、EV速度/位置及唯一光流等条件更新。
位定义以冻结common.h/estimator_status.msg为准，仅从同一实例完整载荷的control_mode_flags判据读取。
速度隔离要求GPS/EV速度/光流均0（mask=0x0100000c），位置隔离要求GPS/EV位置均0（mask=0x1004）；
不从其他查询的最新flags填补。光流位1时保守拒绝速度nan，不近似复刻飞控的“唯一源”判断。

拟独立sim_flight_uorb_diagnostic.v2及--uorb-quality-diagnostics；两字段仅在准确nan和条件合格时，
以显式隔离描述+fields中对应null保存，原文不丢失，新增payload_quality_unavailable状态。
完整字段/有限数值、空正文、原生未发布及质量不可用分开；其他非有限、部分字段/错条件仍停止。
现有两个v1合同/模式不改，新旧schema双向拒绝，不自动fallback。
采集完整、正文完整、载荷完整和控制门分开，固定21次白名单/1秒/250步及原墙钟/资源界不变。
具体字段、20组未来独立验收、预算/停止恢复与SW-02D改动范围见方案。

## 4. 未执行与下一项

本轮只改文档/索引，没有实现新v2 codec、隔离器、fixture或运行模式，没有新SITL/ROS/Gazebo/ULog。
旧SW-02C仍为11查询/10合法事件、完整采集未通过；原972项全仓与17PID清理是上一轮结果。
下一项SIM-FLIGHT-SW-02D先冻结20组独立原文/投影预期，再实现新隔离合同和显式有界采集，
完成定向/旧入口/实际消息兼容与全仓轻量回归。不能以隔离成功代替正向执行器或受控飞行验收。
不扩窗、发控制、接真实DEM/占据融合或启动研究训练/完整模型/正式PERF；research继续fail-closed。
