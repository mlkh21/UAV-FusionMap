# EXP-20261005-002：PERF-01预算正式测量门禁预检

- 日期：2026-10-05；任务：PERF-01；主责任角色：Technical Lead。
- 类型：配置审计、只读门禁和纯Python契约测试；未启动ROS、长时间仿真、训练或研究模型。
- 代码基线：`feature/engineering-initialization`；Python使用
  `/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。

## 目的

现有PERF-01-A能够给出开发机 Radar ROS 回调到占据就绪的诊断，但目标机载平台、设备
采样时钟、跨时钟映射和正式20 ms起止点仍未确认。若继续重复开发机大图短测，只会增加
诊断样本，不能解除正式验收阻塞。因此本项把配置从“工程估计”到“正式可测量”的转换
条件固化为只读门禁。

## 修改范围

1. 在[`configs/perf01_budget.yaml`](../configs/perf01_budget.yaml)增加
   `formal_measurement`字段组，初始值保持`pending_confirmation`和空值；不填造平台、
   端点或时钟来源。
2. 新增[`ros_ws/perf01_budget_gate.py`](../ros_ws/perf01_budget_gate.py)，只读取YAML并
   输出`reference_only`/`formal_ready`、阻塞项和配置错误；默认不执行ROS。
3. 新增[`tests/test_perf01_budget_gate.py`](../tests/test_perf01_budget_gate.py)，覆盖当前
   配置保持阻塞、5/20 ms阈值漂移失败，以及填入完整正式输入后才能ready。

## 实际命令与结果

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01_budget_gate.py configs/perf01_budget.yaml

bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  -m unittest discover -s tests -p 'test_perf01_budget_gate.py' -v

bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  -m unittest discover -s tests -p 'test_*.py' -q
```

门禁输出：`mode=reference_only`、`ready=false`、`errors=[]`，阻塞项共10项：目标平台
未确认；正式测量状态、平台身份、起止端点、采样时钟源、跨时钟映射和持续时长缺失；
Radar频率/时间误差未绑定选定配置；IR传感器与时间配置未确认。3项门禁单测通过。

## 结论

PERF-01仍为全项目第一优先级，当前处于“可执行正式验收前的输入阻塞”，不是性能通过或
性能失败。预检锁定5 ms同步门限和20 ms P99目标；不改变matcher、SensorBundle、
开发机计时起点或现有短测结果。下一步需要确认正式平台、IR/Radar配置和端点/时钟方案，
之后才能预登记目标平台测量矩阵。SIM-01D至少40分钟持续性仍独立处理；SENS-TRAIN-01
不因本项预检提前启动。
