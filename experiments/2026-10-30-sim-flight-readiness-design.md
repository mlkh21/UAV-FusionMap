# 执行器未就绪只读归因与补证设计

编号：EXP-20261030-003；日期：2026-10-30；任务：SIM-FLIGHT-DIAG-DESIGN-02。
主责任：simulation_engineer；状态：已完成（只读审计与具体方案）。
交付：[最小补证方案](../docs/SIM_FLIGHT_DIAG_DESIGN_20261030.md)。

## 1. 范围与环境

用户继续授权上一轮明确的只读归因/补证设计；不重复相同SITL、改变1s/250步或发控制命令。
先读根规范、状态/架构、模块规则及数据/接口/坐标合同，复核dirty、忽略规则及真实入口/消费链。
分支feature/engineering-initialization，HEAD=d96d4439da1007489c80e7f21b132abff16505bf。
所有既有改动/未跟踪文件保留；未提交、推送、安装依赖、Hash或改同级研究仓库。
Python实际核对/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python，离线命令统一经sim01_env。

实际产物目录[flight-diag-design02-20261030T011728825531](../.runtime/runs/flight-diag-design02-20261030T011728825531/wire-audit.json)。
读取SW-02 stage确认passed及439份源文本一致后，保存本轮源/状态，再读取两组原wire/PX4日志。
本轮没有修改运行代码、配置、消息或测试文件；只改方案、实验与管理/接口索引。

## 2. 实际只读检查

| 检查 | 结果 | 边界 |
| --- | --- | --- |
| [源事实](../.runtime/runs/flight-diag-design02-20261030T011728825531/source-checks.json) | 32份冻结源文件、30项指定语句/行号核验通过 | 不以源码条件冒充当前run内部状态 |
| [旧wire重新解码](../.runtime/runs/flight-diag-design02-20261030T011728825531/wire-audit.json) | 376个HIL_SENSOR，0个GPS/执行器，双方RX各2条启动消息，原始时间/CRC可解析 | 没有新SITL或伪HIL注入 |
| 瞬时输入检查 | normal143个/disconnect19个样本落入.8g..1.2g且角速度≤15°/s，首个均为428ms；峰值52.2385m/s²/.893392rad/s | 比较范围取自EKF源码；不是内部积分/低通或tilt_align已通过 |
| ULog可用性 | normal127176字节，disconnect96011字节；pyulog未安装 | 未解码，不由文件存在/大小/缺topic判断“从未发布” |
| 既有客户端 | bin/px4-listener和px4-param符号链接存在；源确认AF_UNIX instance及单次快照分支 | 本轮未执行这些查询，无新客户端代码 |
| 相关定向 | [32/32飞行测试](../.runtime/runs/flight-diag-design02-20261030T011728825531/flight-targeted.log)通过 | 仅既有离线合同/适配/独立字节反例；未重跑全仓935项 |

没有新增测试；当前仓库代码与SW-02验证时一致，不通过重复全仓或旧ROS矩阵增加能力声明。
本轮的所有Python都用固定解释器，实际测试方式：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_sim_flight*.py' -v
```

## 3. 归因结果与具体方案

GPS首次更新需要dt>1s，但EKF初始使用baro，姿态有效主要检查tilt_align和有限四元数；
因此不能把“无首GPS”直接定为执行器未产生的唯一原因。
滤波器还需磁场/气压计数、积分dt和低通倾角初始化，tilt误差方差收敛后才发布有效姿态；
多实例选择器、固定翼模式、PWM更新及发送线程的lockstep等待继续形成依赖链。
当前wire只证明发送输入及未收到回包，尚无PX4内部对应帧证据，唯一根因未确定。

最小新工作包SIM-FLIGHT-SW-02B：保持1s/250步上限和所有停止界，显式probe正常用例，
125/250步各用既有listener读9个白名单topic，最后只show三个参数，共21份只读收据。
不传-i/-r，避免在暂停源时误入等待新消息；never published/无字段/零值、实例、旧时间明确区分。
新私有合同/严格输出校验、有界POSIX调用和独立预期在实际运行前完成；
查询只向本次PID/start_ticks/daemon socket核对的PX4，不允许自由命令或查询其他会话。
单客户端≤200ms、topic组≤400ms、参数组≤400ms、stdout/stderr合计≤32KiB、记录≤256KiB、
事件≤32/查询文件≤8MiB，仍受5s bootstrap墙钟和原session界；超时或身份不符立即停next并清理本次进程。
probe只省略默认监督器额外6ms sleep以留出查询预算，旧normal入口不变，不改FDM节拍或实际源戳。
原始文本保留，打印浮点不能代替wire float32位模式；所有snapshot仍不具原子同tick语义或控制许可。

## 4. 风险、未执行及恢复

新增方案不证明listener实际可查询本run，也不证明任一topic存在/新鲜；这些由SW-02B实际交付。
若端点身份/输出尺寸/返回码/字段格式不能确认，须fail-closed，不把exit0或标题当有效状态。
只读查询也会占墙钟并新增临时订阅，必须留证；如原窗口仍不足，基于实际缺口再交具体方案，不能自动扩窗。
ULog解码可以另行补充，但本包不安装依赖、不手写ULog解析器、不执行会在旧输入旁写文件的官方分析脚本。
本轮没有新FDM/PX4/ROS/Gazebo、公共v2/长窗、命令、训练/完整模型/正式PERF或飞行验收。
旧消息、状态/TF权威、研究fail-closed及训练监督隔离保持；回退只需维持现有入口，不涉及清理历史。
