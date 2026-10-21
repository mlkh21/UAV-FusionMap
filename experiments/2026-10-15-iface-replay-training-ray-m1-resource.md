# EXP-20261015-002：设备记录回放、训练射线标签与地图资源诊断

- 日期：2026-10-15；主责任角色：sensor_engineer（IFACE-01合同由system_architect审阅）；
  M1准备由mapping_engineer负责，ROS薄封装由integration_engineer维护。
- 范围：仅离线已解码设备JSONL、训练已知场景oracle、默认关闭的Local Map
  软件fixture资源观察；不改变公共ROS接口、地图更新算法、在线输入或正式门槛。
- 环境/版本：`feature/engineering-initialization`已有大量未提交/未跟踪内容；
  `bash ros_ws/sim01_env.sh python -B`，`sys.executable`为
  `/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。使用原
  `configs/sens_train_01_scene_matrix.yaml`、ROS滚动fixture及独立run目录；
  无实物Radar/IR、真实设备时钟/标定或外部功耗输入。

## 问题与RED/GREEN

1. 现有`validate_device_time_stream`只检验内存记录；没有读取落盘JSONL并
   拒绝空行、坏JSON、跨行重复sample或换frame的离线审计入口。新测试首次因
   入口不存在而RED；新增`tests/iface01_device_record_replay.py --input FILE`
   逐行用已有记录验证器校验，不加载ROS、不写输入、不估计设备与接收时钟偏移。
   测试覆盖乱序收件、空/坏/重复/混用、伪造同步映射及CLI输入不变；
   JSON汇总始终标记`time_mapping_status=unmapped`、`hardware_validated=false`。
   真机记录须保留原始驱动载荷与来源，解码记录本身不能证明来源真实性。
2. 原训练审计仅以回波线段的轴对齐包围盒拒绝越界free，盒内离轴体素可能
   漏检。`translation_yaw`中将离轴unknown错误写为free+mask=true时，新增
   定向测试首次RED（未抛异常）。改独立审计为线段对体素的逐轴裁剪，按原
   数值容差保守考虑格面；被扫描的pre-echo free及occupied端点规则不变。
   这加强了已知场景标签质量检查，**不修改监督生成器**，不证明真实数据
   全体素质量或可用于模型训练。
3. 原Local Map短测无进程RSS记录。新增默认关闭的`--sample-resources`，
   仅软件滚动fixture采样同run地图ROS进程的时间戳/RSS/CPU时间，缺两次
   采样、进程重启或采样错误均拒绝；资源汇总显式标记非硬件/非正式性能/
   非功耗。默认模式不生成`resources.json`，没有更改地图订阅或查询服务。

## 实际命令与结果

```bash
bash ros_ws/sim01_env.sh python -B -m unittest discover -s tests -p 'test_*.py' -q
bash ros_ws/sim01_env.sh python -B tests/sens_train_01_scene_suite.py
bash ros_ws/sim01_env.sh python -B ros_ws/local_map_query_run.py --mode rolling --sample-resources --port 11473
bash ros_ws/sim01_env.sh python -B ros_ws/local_map_query_run.py --mode disabled --port 11475
bash ros_ws/sim01_env.sh python -B ros_ws/local_map_query_run.py --mode enabled --port 11476
bash ros_ws/sim01_env.sh python -B ros_ws/local_map_query_run.py --mode unclassified --port 11477
```

- 359/359项全仓轻量单测通过；12场景/36条新离线记录通过，包含102回波、
  78无回波槽，free=442、occupied=62、unknown=45576；监督报告仍为
  `hardware_validated=false`、`model_quality_validated=false`、
  `formal_perf_validated=false`，见[新报告](../.runtime/runs/sens-train-scenes-20261015T102312611647/report.json)。
- 滚动ROS fixture采到地图进程11次RSS，采样峰值45,383,680字节；5快照、
  7条占据、20查询及进程/端口清理通过，见[资源样本](../.runtime/runs/local-map-query-rolling-20261015T102406141231/resources.json)、
  [验证](../.runtime/runs/local-map-query-rolling-20261015T102406141231/validation.json)、
  [清理](../.runtime/runs/local-map-query-rolling-20261015T102406141231/cleanup-audit.json)。
  这是开发机单次、采样间隔0.1s的**采样RSS峰值**，不是持续峰值上界、
  目标机容量或正式资源验收；未测功耗及同一run的完整更新/查询延迟分布。
- 旧关闭查询模式[validation](../.runtime/runs/local-map-query-disabled-20261015T102441370234/validation.json)
  1快照/0查询；旧启用模式[validation](../.runtime/runs/local-map-query-enabled-20261015T102439596764/validation.json)
  2快照/30查询；旧不猜阈值模式[validation](../.runtime/runs/local-map-query-unclassified-20261015T102625847836/validation.json)
  2快照/30查询。三个独立端口与清理均通过，默认未启动资源采样。
- 首次ROS尝试因沙箱禁止创建socket，在进入图验证前以PermissionError退出；
  取得执行许可后用同一独立端口成功重跑。未以首次失败冒充产品缺陷，
  未覆盖或删除历史run；`git diff --check`通过。

## 修改范围、恢复与下一关口

文件：`tests/iface01_device_record_replay.py`、`tests/test_device_time_adapter.py`、
`tests/sens_train_01_scene_suite.py`、`tests/test_sens_train_01_scene_suite.py`、
`ros_ws/m1_resource_observer.py`、`tests/test_m1_resource_observer.py`、
`ros_ws/local_map_query_run.py`及相关数据合同、M1矩阵、计划/状态/实验索引。
如诊断入口需停用，省略`--sample-resources`即可回到旧ROS行为；若需修正
离线oracle/审计，保留本次报告及旧实验，另起RED/GREEN，不回写原始记录。

真实设备原始数据、采样时间与AircraftState时钟误差、可靠标定及质量来源，
目标平台全链RSS/更新和查询延迟分布/功耗与连续场景、独立恢复副本均未具备。
IFACE-01、SENS-TRAIN-01完整验收、M1真实输入/资源门禁、PERF-01正式性能、
ENV-03和完整Phase 1均不因本次fixture通过而关闭；M2概率、DEM、
研究模型接入、自主控制与科研对照不提前开展。训练LiDAR仍只作监督，
未知/超时/无回波仍不可标为free。`tests/`与`experiments/`被当前`.gitignore`
整目录忽略，且项目目录有大量未提交文件；未自动暂存、提交、推送或触碰
同级研究仓库。后续版本收录须单独逐文件审核。
