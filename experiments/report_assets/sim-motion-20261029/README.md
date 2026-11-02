# 运动场景报告素材

日期：2026-10-29；来源run：sim-motion-sw03-20261029T161731864328。
任务：SIM-MOTION-SW-03；[完整记录](../../2026-10-29-sim-motion-delivery.md)。
这里是新的运动素材，旧sensor-scene/rviz/p5-delivery目录和历史图保持。
所有图片直接复制自同次原生Gazebo/RViz渲染目标，无拼接、重绘或生成替代；来源见sources.json。

| 文件 | 建议图注 |
| --- | --- |
| scene-before.png | JSBSim同FDM真值驱动的Gazebo代理，源时间0.1s；真实动力学初始速度5m/s、高度8m，未解锁/控制 |
| scene-after.png | 同一1s短窗终点，位置约[5.4363,-0.0025,4.6266]m；代理跟随真实动力学，下降并俯仰，不能称为稳定巡航 |
| rviz-before.png | t=0.1s的真实Radar回波、IR功能热强度及placeholder占据地图，观测时刻Context与该tick位姿一致 |
| rviz-after.png | t=1.0s，同次运动后的Radar/IR及M1 latest；10个Bundle/占据/快照，缺失质量保持不可用，未观测区域unknown |
| rviz-history.png | 源clock停止3s后的历史视图；Radar/IR显示已关闭、地图为历史不可用，底栏明确History，不把冻结画面当实时观测 |

实际运动位移6.397858m，原始IR前后67,933像素变化；原生Gazebo前后133,109像素、
RViz前后174,999像素有显著变化。原始wire和逐帧对账保存在原run，图片不能替代数值验收。
实际13,217回波Doppler/杆臂核验、14条公开查询和独立进程地图回放通过。
这是地面开发机上的功能级传感器、仿真真值和placeholder软件闭环，不是研究网络质量、
实机标定、DEM融合、受控固定翼飞行、高速实时或正式阶段验收。

原生有界复现：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_motion_delivery_run.py
```

在仓根运行，完成后自动清理本次进程；候选端口11801/11802及PX4固定端口需空闲。
公共clock/状态始终由新运动源唯一发布，旧默认静态入口不改变。
