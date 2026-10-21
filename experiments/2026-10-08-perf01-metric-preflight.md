# EXP-20261008-001：PERF-01证据内容数值预检

- 日期：2026-10-08；任务：PERF-01；主责任角色：Technical Lead。
- 类型：纯Python只读预检与合成证据RED/GREEN；无ROS运行、真实设备或长测。
- 目的：防止空文件、`passed=true`或自报达标数值把§6.2的结构预检误导为真实
  性能证据。5ms同步门限、严格拒绝理由及20ms目标均不改变。

## 输入和修改

已读取真实预算消费者`ros_ws/perf01_budget_gate.py`及正式预检
`ros_ws/perf01_formal_preflight.py`、六项必需证据名和PERF-01-A报告聚合入口。
本轮只修改后者、`tests/test_perf01_formal_preflight.py`及关联中文文档；不修改
配置、节点、传感器、地图、研究仓库或已有实验产物。

先在合成正式配置的单run正例中把六类证据写成结构化JSON，并追加空文件、
`{}`、只有`passed=true`、伪造/超标P99、同步与姿态超限、丢帧/超时超限、
过短持续时间、零样本、错run、错航速、功耗超限及错误计数负例。
修改生产预检前，新增反例测试7组失败，其中空文件、仅`passed=true`和虚报P99
均返回`ready=true`，证明原门禁只检查存在性。

随后只读检查六类JSON的同一run/航速/时钟域身份，并用原始逐样本单调时差
按现有`perf01a_metrics.percentile_set`的nearest-rank规则重算P50/P95/P99；
核验逐样本20ms年龄、5ms同步、10ms位姿、计数闭合、丢帧/超时各不超过1%、
确认的Radar频率下的输入数、目标平台已确认的功耗/内存限值及连续时长。
所有样本为测试合成值，不代表真实设备采集。每个manifest只代表一个航速的
单次运行，不代表35/50/70m/s矩阵完成。

## 验证命令和结果

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  -B -m unittest discover -s tests -p 'test_perf01_formal_preflight.py' -q
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  -B -m unittest discover -s tests -p 'test_perf01*.py' -q
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  -B -m unittest discover -s tests -p 'test_*.py' -q
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  -B ros_ws/perf01_budget_gate.py configs/perf01_budget.yaml --require-formal
git diff --check
```

- 测试分别14/14、140/140、243/243通过；Conda解释器为
  `/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，`git diff --check`通过。
- 预算门禁当前仍为`mode=reference_only`、`ready=false`、`errors=[]`、10项
  正式输入阻塞；`--require-formal`以预期的退出码1拒绝正式测量。
- 正例`formal_ready`只在测试生成的合成配置与完整数值数据中出现，绝不
  用作本机或目标平台的真实性能声明。

## 限制与后续

数值预检可识别文件内部不一致、超阈值和资料缺失，不能证明文件由真实设备产生、
设备时钟到单调时钟的offset/drift/误差上界可信，也不能排除低频资源采样漏掉峰值。
目标平台、选定Radar/IR配置、真实时钟标定、连续运行及35/50/70m/s完整矩阵仍需
独立验收。SIM-01D跨边界持续性和现有开发机短测不替代PERF-01。

本轮不启动ROS、不覆盖历史实验；下一项可以在既有fake Radar/IR上做预登记
功能/负载回归，IFACE-01时间/外参定义确认后再做SENS-TRAIN-01训练监督隔离。
