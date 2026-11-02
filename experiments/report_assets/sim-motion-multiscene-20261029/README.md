# 多场景原生报告素材

日期：2026-10-29；来源：SIM-MOTION-SW-04C最终同源码矩阵。
[实际记录](../../2026-10-29-sim-motion-multiscene-delivery.md)、
[最终矩阵](../../../.runtime/runs/sim-motion-sw04c-20261029T231006722634/manifest.json)。

26个PNG均直接复制本次原生渲染输出，没有裁剪、着色、叠加或拼接。
[sources.json](sources.json)逐文件记录原run与路径，交接审计逐字节核对，无额外Hash。
文件前缀S05/S07为用例；gazebo为场景渲染，rviz为包含控件/IR的原生窗口，
scene/infrared为该窗口的独立渲染目标。14张阶段总图加12张viewport。

## S05：近远遮挡

| 阶段 | 图 | 中文图注 |
| --- | --- | --- |
| before / 100ms | [Gazebo](S05-gazebo-before.png)、[RViz](S05-rviz-before.png) | 近处红box遮住远处蓝box，选定Ray先命中近表面；点云驱动placeholder占据，IR来自同一Camera |
| after / 1s | [Gazebo](S05-gazebo-after.png)、[RViz](S05-rviz-after.png) | 自由动力学改变视场后末帧0点，IR均匀背景为真实合法测量；旧占据未被新空帧刷新，不解释为free |
| history / 停钟 | [Gazebo](S05-gazebo-history.png)、[RViz](S05-rviz-history.png) | Gazebo停留末姿态；RViz停钟后清空并关闭raw，隐藏IR，地图仅显示历史不可用 |

## S07：移远、返回与历史

| 阶段 | 图 | 中文图注 |
| --- | --- | --- |
| before / 100ms | [Gazebo](S07-gazebo-before.png)、[RViz](S07-rviz-before.png) | 近障碍位于[12,0,8]m，实际Radar命中与Camera投影相符 |
| empty / 900ms | [Gazebo](S07-gazebo-empty.png)、[RViz](S07-rviz-empty.png) | 障碍已移至[100,0,8]m；500—900ms五次零回波和均匀IR，旧cell保留400ms证据，不能当当前新观测 |
| after / 1s | [Gazebo](S07-gazebo-after.png)、[RViz](S07-rviz-after.png) | 暂停边界移回后真实实采恢复1,233点与IR；新视图单帧范围避免旧空背景掩盖返回图像 |
| history / 停钟 | [Gazebo](S07-gazebo-history.png)、[RViz](S07-rviz-history.png) | 实际Radar/IR显示关闭、IR面板消失，地图转为历史unavailable，底栏明确源时钟停止 |

这是功能级传感器、仿真真值、placeholder和M1 latest软件证据。
没有研究Radar–IR网络融合质量、真实DEM/占据融合、PX4估计精度或受控/高速飞行验收。
默认旧静态场景入口仍保留；以下是有界运行，完成后关闭自有窗口/进程：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_motion_multiscene_ros_run.py --case S07 --native
```
