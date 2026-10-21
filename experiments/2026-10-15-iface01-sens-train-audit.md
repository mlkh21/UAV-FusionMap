# EXP-20261015-001：IFACE-01记录合同与SENS-TRAIN-01标签审计

- 日期：2026-10-15；主责任角色：sensor_engineer，IFACE-01合同由system_architect复核。
- 类型：纯函数契约测试、离线已知场景矩阵；任务：IFACE-01、SENS-TRAIN-01。
- 环境：`bash ros_ws/sim01_env.sh python -B`，检查`sys.executable`为
  `/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`；分支
  `feature/engineering-initialization`，保留已有未提交改动。
- 无目标机硬件、设备实测时钟或外部功耗记录；未运行研究模型/ROS新图，
  未改公共ROS消息、在线SensorBundle、mapping或正式PERF-01门槛。

## 问题、方案与RED

真实调用链的离线审计：`device_time_adapter` → `device_time_record` →
`validate_device_time_record/stream`。原验证可接受被篡改为PTP的
ARS548/Mid-360 `payload.time_source`或逐点时间语义、同步来源标志，
并允许同一run/设备流混用不同`frame_id`。增加记录/流篡改负例，
首次定向设备测试14项有5个失败子例；后补frame测试15项再失败1例。
只校验原适配器已有的列表/逐点时间语义、同步来源枚举和流frame稳定性，
不新增时钟估计或新业务字段；合法记录、收件顺序可乱的同frame流仍通过。

训练链为仿真状态 → sensors状态适配 → `TrainingScanBuffer` →
`build_training_sample` → 私有训练JSONL → 独立`audit_case`。原独立
场景审计只比对occupied端点/全无回波/遮挡，未独立约束命中前已扫过的free：
将有效free改为unknown+mask=false仍被接受，新增场景测试首次9项失败1例。
有其他射线回波时，将远离全部射线路径的unknown改成free+mask=true
同样曾被接受，新增场景测试首次10项失败1例。
从已知障碍几何的面交点及观测时刻位姿独立采样命中前射线；只检查远离
移动格界的保守可证free子集；同时拒绝落在所有回波线段保守包围盒之外的free，
已有occupied优先，固定格界采用上侧单元。包围盒内部但未在射线上的
假free仍可能漏检，**这不是全体素逐单元质量证明**。
原标签验证亦把整数`1`当作布尔mask接受；
新增严格布尔负例后首次20项失败1例，修复只收`bool`，不更改生成的标签值。

## GREEN与产物

```bash
bash ros_ws/sim01_env.sh python -B -m unittest discover -s tests -p 'test_device_time_adapter.py' -q
bash ros_ws/sim01_env.sh python -B -m unittest discover -s tests -p 'test_sens_train_01*.py' -q
bash ros_ws/sim01_env.sh python -B -m unittest discover -s tests -p 'test_*.py' -q
bash ros_ws/sim01_env.sh python -B tests/sens_train_01_scene_suite.py
```

结果：设备记录15/15、训练定向49/49、全仓353/353通过；新输出目录
[矩阵报告](../.runtime/runs/sens-train-scenes-20261015T094041549226/report.json)
`passed=true`、12场景/36记录/102回波（30插值）/78无回波槽、
free=442、occupied=62、unknown=45576，observed=1.09375%，
最大补偿数值残差`3.084608628661778e-07 m`。报告自称
`hardware_validated=false`、`model_quality_validated=false`、
`formal_perf_validated=false`；全仓测试不是实际ROS图/硬件验收。
中间两次复核通过矩阵分别保存在独立
[`093603`](../.runtime/runs/sens-train-scenes-20261015T093603498046/report.json)和
[`093753`](../.runtime/runs/sens-train-scenes-20261015T093753741259/report.json)，
均未重写历史产物；最终报告是加入越界free负例之后的新目录。

修改文件：`sensors/ufm_sensors/device_time_record.py`、
`sensors/ufm_sensors/training_supervision.py`、
`tests/sens_train_01_scene_suite.py`、`tests/test_device_time_adapter.py`、
`tests/test_sens_train_01.py`、`tests/test_sens_train_01_scene_suite.py`及
项目状态、契约和本实验索引。无需回滚接口：若新增审核需修正，只调整
相应验证器并保留RED与新输出目录，不重写原实验。

## 风险与待验

严格校验曾可被接受的坏记录会被拒绝；旧合规样本已通过回归，真实设备
记录尚未取得。独立free子集与保守包围盒不能证明全部格点标签正确；真实回波/标定、
模型训练标签充分性、ROS驱动与机载功耗均未验收。训练LiDAR只属监督，
无回波/未知/过期不标free。`experiments/`和`tests/`当前被工作区
`.gitignore`忽略，本机新记录/测试虽存在却不会自动进入普通`git status`；
尚未取得改变忽略规则或归档的授权，不自动暂存或提交。
