# EXP-20261013-001：非零扫描边界与场景矩阵审计

日期：2026-10-13；责任角色：sensor_engineer；类型：纯函数/定向回归。
状态：功能级fixture边界子范围通过；SENS-TRAIN-01、IFACE-01整体仍进行中。

## 目的与范围

继续使用无正式平台、无物理传感器时钟、无功耗输入的当前条件。本次不启动PERF-01、
真实设备接入、长训练或对照试验，针对已完成的schema `0.2`运动扫描增加边界审计：
遮挡、量程截断、FOV拒绝，以及单障碍、双障碍、非零扫描三类fixture场景矩阵。

## 执行结果

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  tests/test_sens_train_01.py -q
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  -m unittest discover -s tests -p 'test_*.py' -q
```

定向测试 `16/16` 通过；随后全仓轻量回归 `274/274` 通过。新增检查包括：

- 运动扫描中首回波后方体素保持 `unknown`，不因第二障碍存在而伪造观测；
- 量程缩短到首障碍之前时，不生成点、不标记free，整个监督网格保持unknown；
- 合法但超出声明水平FOV的射线被拒绝；
- 单障碍零时长、双障碍零时长和双障碍非零扫描均通过统一记录校验；
- 原有逐点时间、扫描中点补偿、无回波、擦边、身份和状态历史拒绝测试继续通过。

## 结论与限制

当前纯函数合同已覆盖“可观测首回波前free、首回波occupied、遮挡/量程外/FOV外/无回波
unknown”的基本边界；它只证明给定仿真几何和状态历史下的标签逻辑，不证明真实传感器
回波质量、设备时间误差、标定有效性、ROS v0.2记录路径、实时能力或研究模型质量。

下一步应取得真实驱动字段和逐点时间方案，单独设计ROS记录器升级及图审计；随后再增加
更丰富的运动、遮挡、量程和多场景统计。正式PERF-01及对照试验继续放在工程输入和
可复现数据门禁之后。
