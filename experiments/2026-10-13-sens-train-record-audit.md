# EXP-20261013-002：非零扫描训练记录合同与验证器审计

日期：2026-10-13；责任角色：sensor_engineer；类型：纯函数/记录合同回归。
状态：功能级记录合同子范围通过；SENS-TRAIN-01、IFACE-01整体仍进行中。

## 目的与边界

本次继续在正式平台、物理传感器时钟和功耗输入缺失的条件下推进，不启动PERF-01、
真实设备接入、长训练或对照试验。目标是确保非零扫描记录可以独立追踪每条射线的
采集时间：无回波射线也必须保留时间槽，不能因没有点记录而丢失时序语义。

## 修改内容

`build_training_sample`现在在v0.1和v0.2记录中显式保存
`lidar.ray_time_offsets_ns`。该列表覆盖配置中的全部射线；v0.2要求从0覆盖到扫描
总时长并有序，v0.1零时长使用全零偏移。有效回波通过唯一`ray_index`引用对应槽，
无回波射线只保留时间槽，不生成free或occupied标签。

`validate_training_sample`新增以下拒绝条件：

- 记录缺少逐射线时间槽，或偏移与配置、扫描时长不一致；
- 同一`ray_index`出现多个回波点；
- 点记录不是字典，或点时间、偏移、状态sample_id、原始/补偿坐标缺失或非有限；
- 记录顶层、传感器分区、header或监督分区缺失时统一返回合同错误，而不是依赖字段访问异常；
- 仍保持已有的run/clock、scene、calibration、扫描区间和target/observed_mask校验。

历史零时长v0.1记录缺少该字段时按兼容规则解释为全零；新写入记录始终显式保存字段。
没有新增公共ROS消息，现有`sens_train_01.launch`仍是零时长v0.1图。

## 执行与结果

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  tests/test_sens_train_01.py -q
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  -m unittest discover -s tests -p 'test_*.py' -q
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  tests/test_sens_train_01_ros.py -q
```

定向测试 `18/18`、现有ROS编解码测试 `2/2` 通过。覆盖全射线时间槽、混合命中/无回波、
整帧无回波槽保持、
缺字段、重复回波、畸形点、顶层/分区缺失的fail-closed行为、零时长v0.1兼容，以及前一轮
运动补偿、遮挡、量程、FOV和场景矩阵。全仓轻量回归随后通过 `276/276`，Python编译与
`git diff --check`通过。

## 结论与限制

本次只证明离线fixture记录的时间可追溯和验证器拒绝边界，不证明真实设备能提供可靠的
逐点时间、ROS v0.2记录路径、时钟映射、真实标定、实时性能或研究模型质量。下一步仍是
取得真实驱动字段/逐点时钟方案，再单独设计ROS记录器升级和图审计；对照试验继续放在
工程输入和可复现数据门禁之后。
