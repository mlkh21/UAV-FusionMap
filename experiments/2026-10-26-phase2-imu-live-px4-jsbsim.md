# EXP-20261026-004：PX4/JSBSim 在线 IMU 虚拟源链短测

- 日期：2026-10-26；主责任角色：sensor_engineer；ROS监督器由integration_engineer协作。
- 目标：补齐EXP-20261026-003仅使用MAVLink fixture的缺口，以**本次启动的**
  PX4 v1.13.3、JSBSim bridge及MAVROS的原始 HIGHRES_IMU 核对源/适配IMU的值、
  身份、时间、坐标轴、失效质量。不进行真实设备校准、训练、正式PERF-01或飞行试验。
- Python：`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`；所有ROS命令经
  `bash ros_ws/sim01_env.sh`；新run独立目录，监督器只停止自己的进程组。

## 源链与实现

桥接`Tools/jsbsim_bridge/src/sensor_imu_plugin.cpp:getData`读取模拟pilot点加速度
和机体角速率并加噪；`mavlink_interface.cpp`构造HIL_SENSOR。PX4
`src/modules/mavlink/streams/HIGHRES_IMU.hpp:send`用选中的`vehicle_imu`
delta-velocity/delta-angle除以各自采样周期、减估计偏置，以`timestamp_sample`
发六轴值。源代码语义不能单独证明实物传感器安装、噪声、偏置或重力约定。

新增`sim01_smoke.py --imu-live`；旧命令默认不开启，fixture与该选项互斥。
运行器显式把`publish_imu:=true`、`imu_calibration_id:=sim_pilot_virtual_flu_v1`
传给旧launch。观察器独立从`/mavlink/from`逐帧解码CRC有效的HIGHRES_IMU，
并从`/uav/sim/imu`、`/uav/sensors/imu`接收ROS对象；按sample_id比较原始六轴、
采样ns、同域clock覆盖、FRD→FLU三个轴各自的符号、比力标志及unknown协方差；
不足300个三链完整匹配样本即失败。保留逐条原始`mavlink.jsonl`、`imu.jsonl`、
`clock.jsonl`、`states.jsonl`及manifest/清理收据。不使用ROS IMU值自身充当原始
数值oracle；不对零速场景强制指定加速度的正负号或宣称量测误差上界。

复现（从项目根执行，保证专用端口未占用，且无其他PX4 run）：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  -m unittest discover -s tests -p 'test*.py' -q
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  ros_ws/sim01_smoke.py --imu-live
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  ros_ws/sim01_smoke.py --fixture
```

## 实际结果

首次沙箱内尝试在socket探测时收到`PermissionError: Operation not permitted`，
未启动PX4/ROS。该失败预检目录保留为
`.runtime/runs/sim01a-live-20261026T202721866429/`（监督器的finally同样受沙箱
socket限制，未生成manifest；只留下配置副本与空目录）。经权限审批后独立在线
run `.runtime/runs/sim01a-live-20261026T202741741905/`通过，
`result.json`、`manifest.json`及`cleanup-audit.json`均已归档：有效状态跨度
30.204秒，源/适配状态各605条，clock2302条；原始HIGHRES_IMU、源和适配
有效IMU各2302条，原始→源及源→适配匹配各2302条，无对账错误。
最终版重新独立运行于`.runtime/runs/sim01a-live-20261026T203023619306/`：
`result.json`报告30.196秒有效状态窗口、状态各605条，2300条raw/source/adapted
IMU按身份、时间和六轴全部匹配，`errors=[]`；`manifest.json`和
`cleanup-audit.json`均报告成功。原始加速度各轴均值约为
`[1.225, -0.186, -9.731] m/s²`，角速率各轴均值约
`[0.000052, -0.000147, -0.000485] rad/s`；数值仅用于虚拟源短测观测，
不证明静止重力处理、pilot点到实物IMU的安装外参或偏置精度。

旧入口fixture run `.runtime/runs/sim01a-fixture-20261026T202946481103/`
`passed=true`且清理通过。新增5项纯门禁覆盖完整匹配、原始缺帧、符号/值错误、
NaN/零协方差伪装及run/clock冲突；全仓轻量399/399通过。

## 限制与恢复

真实PX4/JSBSim进程和真实ROS传输已核对；这是**仿真虚拟pilot点**采样，
不是Radar/IR/实物IMU驱动。没有与JSBSim内部独立物理真值逐帧比对；PX4
`HIGHRES_IMU`不是未经处理的桥接HIL_SENSOR原值。未测动态转动、实机温度/
噪声/偏置/安装标定、跨设备采样时钟或完整Phase 2。关闭`publish_imu`
或不带`--imu-live`即恢复默认旧入口，不回填任意缺失IMU观测。
实验目录按现有规则忽略；不自动提交或更改忽略规则。
