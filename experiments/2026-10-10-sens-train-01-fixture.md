# EXP-20261010-001：SENS-TRAIN-01同场景训练监督小图

日期：2026-10-10；责任角色：sensor_engineer；类型：纯函数/ROS消息契约、独立真实ROS功能级短测；
状态：最小fixture场景通过，不是机载传感器、研究模型质量或PERF-01验收。

## 目的、输入与边界

按[训练监督方案](../docs/SENS_TRAIN_01_IMPLEMENTATION_PLAN.md)验证同一静态odom障碍物，
具名仿真安装外参、Radar/IR采集输入和仅训练LiDAR首回波监督。
配置快照为[最终run配置](../.runtime/runs/sens-train-01-20261010T153539744378/sens_train_01_fixture.yaml)：
单个0.5 m立方障碍中心odom `[0,4,0.2]` m，Radar/IR/LiDAR外参互不默认相同；
LiDAR单条前向射线、零扫描时长、量程6 m、栅格0.5 m、14×8×8；
IR 5×3、投影校验热点 `(2,1)`，背景0.4/热点0.9为无单位fixture强度。
飞机运动0.1 m/s、10 Hz、20帧；参考时刻100 ms到2000 ms，
均为仿真时钟，不代表高速或真实标定。输入为Radar/IR；LiDAR标签只在训练记录器侧路。

## 预期和执行

- 同run/clock/scene/calibration记录、三个模态各20条；Radar/IR消息值往返一致。
- 射线到首命中前free且observed、命中occupied且observed、命中后/无返回/未覆盖unknown。
- 非单位安装外参及运动时首命中落同一odom面；校准、采集偏移、姿态年龄或身份失配拒绝。
- 在线推理launch无训练节点；ROS实际LiDAR发布节点仅有训练fixture，订阅仅训练记录器和监督器；
  无标签进入SensorBundle/forward/定位/mapping。退出后master端口释放。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  -m unittest discover -s tests -p 'test_*.py' -q
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  ros_ws/sens_train_01_run.py --port 11447
```

## 实际结果与保留失败

首轮[失败记录](../.runtime/runs/sens-train-01-20261010T152940163083/validation.json)
因fake-LiDAR节点在首次`/clock`发布前调用`rospy.sleep`（仿真时间等待），
形成启动握手互等；20帧超时，源节点未就绪。保留原始日志，不重写结果；
将就绪等待改为有界墙钟等待，端口收尾考虑TIME_WAIT。

修复握手后[第二轮通过记录](../.runtime/runs/sens-train-01-20261010T153100092279/validation.json)
已达到20/20/20；进一步把功能级假传感器消息`source_type`从`simulation`
改为更准确的`fixture`，原目录保留。
最终[通过记录](../.runtime/runs/sens-train-01-20261010T153539744378/validation.json)
`passed=true`、`errors=[]`、20/20 Radar、20/20 IR、20/20监督消息、20条
[独立JSONL标签记录](../.runtime/runs/sens-train-01-20261010T153539744378/training-records.jsonl)，
逐条验证身份/时间与ROS Radar/IR消息sample_id对账；LiDAR topic发布者1个训练节点，
订阅者只有训练记录器和短测监督器；两个子进程正常退出、11447端口释放。
定向6项（包括真实ROS消息编解码及静态推理图隔离）通过，全仓256项轻量测试通过。
未修改在线launch、SensorBundle消息定义、模型输入、研究仓库、历史实验或checkpoint。

## 限制与后续

ROS标签使用`std_msgs/String`包裹独立JSON记录，不是公开LiDAR消息合同；
尚无真实设备驱动、校准误差、非零扫描去畸变、完整3D射线、多场景标签质量和
大规模训练数据校验。场景真值仅用于构建明确标注的功能级监督，不能进入在线推理。
IFACE-01剩余的PointCloud2驱动适配、状态插值、可选Odometry镜像与TF唯一责任
未完成；PERF-01正式资源/设备时钟输入仍阻塞。故SENS-TRAIN-01整体保持进行中。
