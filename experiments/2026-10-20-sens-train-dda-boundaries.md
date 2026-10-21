# EXP-20261020-002：SENS-TRAIN-COV-02体素边界与有限网格裁剪

- 日期：2026-10-20；主责任角色：sensor_engineer；状态：软件fixture子范围通过。
- 目的：复核训练监督射线遍历仅写入正长度穿越的有限网格体素，缺硬件条件下不
  扩大训练/在线边界或声称传感器实测。
- 输入：当前DDA生成器、独立的逐体素线段/AABB正长度裁剪oracle；固定小网格
  `origin=[0,0,0]`、`resolution=[1,1,1]`、`shape=[4,4,4]`及非等距网格
  `origin=[-1,-2,-3]`、`resolution=[0.5,1,2]`、`shape=[4,3,2]`。

## 方法与RED/GREEN

新增2项定向测试共19个固定线段输入，对DDA体素集合同时核对明确的关键预期集合
和独立逐体素AABB oracle。覆盖轴向正反向、棱/角同时跨界、平行于面/棱、双向网格
裁剪、恰好停在进入/退出边界、角点切触、网格外平行和非等距网格。仅单点接触及
退化线段不应产生free；面对齐沿用`floor`上侧归属，端点occupied仍由既有调用方
另行处理，无回波仍保持unknown。

初次定向执行RED：`zero_length_inside`把`[1.5,1.5,1.5]`到自身的退化线段
错误返回扁平索引21，预期为空；其他固定边界用例通过。只在
`_segment_voxel_indices`入口为起终点相同的线段返回空结果，并在独立oracle中
显式处理同一退化情况；复跑2项定向测试GREEN。`build_training_sample`原有的
退化补偿LiDAR射线拒绝仍保留，本次没有证明实际训练记录曾出现这种错误标签。

## 运行与实际结果

经`bash ros_ws/sim01_env.sh`运行；检查`sys.executable`为
`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`：

```bash
bash ros_ws/sim01_env.sh python -B -m unittest discover -s tests -p 'test_sens_train_01_dda_boundaries.py' -v
bash ros_ws/sim01_env.sh python -B -m unittest discover -s tests -p 'test_sens_train_01*.py' -q
bash ros_ws/sim01_env.sh python -B -m unittest discover -s tests -p 'test_*.py' -q
bash ros_ws/sim01_env.sh python -B tests/sens_train_01_scene_suite.py --matrix configs/sens_train_01_scene_matrix.yaml
bash ros_ws/sim01_env.sh python -B tests/sens_train_01_scene_suite.py --matrix configs/sens_train_01_voxel_coverage_matrix.yaml
bash ros_ws/sim01_env.sh python -B ros_ws/sens_train_01_run.py --fixture motion --port 11471
bash ros_ws/sim01_env.sh python -B ros_ws/sens_train_01_run.py --fixture yaw --port 11472
```

- 2项新增定向、58项SENS-TRAIN相关及374项全仓轻量测试通过。
- [既有12场景](../.runtime/runs/sens-train-scenes-20261020T161515307378/report.json)：
  36条记录；[短弦2场景](../.runtime/runs/sens-train-scenes-20261020T161515340020/report.json)：
  6条记录；均`passed=true`、`errors=[]`、完整正长度oracle通过。
- [motion ROS](../.runtime/runs/sens-train-01-20261020T161555191357/validation.json)
  及[yaw ROS](../.runtime/runs/sens-train-01-20261020T161555224473/validation.json)：
  各20条Radar/IR/训练记录、22条状态/clock；记录与接收载荷和Radar/IR值匹配；
  训练LiDAR监督只被runner/recorder订阅；两个run均`passed=true`、子进程退出0、
  端口释放。沙箱首次尝试因禁止socket未启动，获运行权限后分别在隔离端口通过。

## 边界与恢复

未改公共消息、JSON schema、ROS启动图、感知/地图或训练模型；未执行真实设备、
标定/时钟残差、数据规模与模型质量评价、PERF-01、功耗、概率地图、DEM或科研
对照试验。`hardware_validated/model_quality_validated/formal_perf_validated`仍为false，
Phase 1/2整体和外部输入门槛不因本项关闭。

若后续发现网格边界归属问题，保留测试与原运行目录，单独定位并按确认流程修改
遍历器；不得删除失败证据或通过修改oracle放宽未知区域语义。`tests/`与`experiments/`
仍受现有`.gitignore`规则忽略，本轮不改忽略规则、不暂存、不提交或推送。
