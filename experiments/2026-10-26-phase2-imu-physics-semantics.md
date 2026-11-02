# EXP-20261026-005：JSBSim pilot 点 IMU 比力语义独立对照

- 日期：2026-10-26；主责任角色：sensor_engineer。
- 范围：接[EXP-20261026-004](2026-10-26-phase2-imu-live-px4-jsbsim.md)的
  PX4/ROS在线六轴值对账，核对当前 Rascal/LSZH 的 pilot 点物理取值、重力/
  比力区别和安装位置来源。不改变公共消息、仿真桥接副本、ROS生产链或同级研究仓库。
- 判定：`passed`仅表示独立 JSBSim 场景对照通过，不表示同 run 逐帧真值、偏置
  精度、实机标定或完整 Phase 2 退出。

## 源码/配置证据

- 当前 bridge `configs/rascal.xml` 的 `<imu>` 无自定义属性；
  `include/sensor_imu_plugin.h` 默认从
  `accelerations/a-pilot-{x,y,z}-ft_sec2`与`velocities/{p,q,r}-rad_sec`取值，
  `sensor_imu_plugin.cpp:getAccelFromJSBSim`把 ft/s² 乘0.3048成 m/s²，
  `addNoise`再叠加仿真噪声及偏置；`mavlink_interface.cpp:SendSensorMessages`
  写入 HIL_SENSOR。`models/Rascal/Rascal110-JSBSim.xml`的`EYEPOINT`为
  `[20,0,5] in`（模型结构坐标）；未启用`systems/px4_default_imu_sensor.xml`
  里另一个位置，二者不能混称。
- 本机安装 JSBSim 1.1.13 的`models/FGAuxiliary.h`将 pilot 感受的加速度
  与 CG→EYEPOINT 的旋转臂相关；`models/FGAccelerations.h:GetBodyAccel`
  明确受力加速度不含重力。对应版本 JSBSim 的 `FGAuxiliary.cpp`以
  `GetBodyAccel`加角加速度/角速度作用于 CG→EYEPOINT 的臂，形成
  `vPilotAccel`并绑定上述`a-pilot`属性。这是模型源码定义，不是实机
  外参或默认重力方向的经验猜测。
- 本机 PX4 v1.13.3 的`simulator_mavlink.cpp:update_sensors`把 HIL_SENSOR
  加速度送到模拟加速度计（含一个FIFO量化支路）；`VehicleIMU.cpp`
  积分采样；`streams/HIGHRES_IMU.hpp:send`从选定`vehicle_imu`的增量/
  采样周期减估计偏置后发布。因此不能认为在线 HIGHRES_IMU 与 JSBSim
  内部属性在数值和采样时间上可直接逐条相等。

## 复现与结果

独立工具`simulation/imu_physics_probe.cpp`只链接项目已有的
`.runtime/deps/jsbsim-1.1.13/usr/lib/libJSBSim.a`。运行器使用上述机型/
LSZH初始条件、4ms步长、750步；仅改本次FDM对象的初始滚转/高度，不写
模型文件，也不启动PX4、ROS、网络或研究后端。输入的历史在线收据只用来
列出异run数值差，不参与通过判定。根目录复现命令：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  simulation/imu_physics_validation.py \
  --live-result .runtime/runs/sim01a-live-20261026T203023619306/result.json
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B \
  -m unittest discover -s tests -p 'test*.py' -q
```

本次初步产物`.runtime/runs/imu-physics-20261026T221120532775/`
保留。增加缺实际姿态收据的fail-closed单测后重新独立运行，最终产物
[validation.json](../.runtime/runs/imu-physics-20261026T221506521348/validation.json)
为`passed=true, errors=[]`。逐场景记录和编译日志保存在该目录；启动日志
标明JSBSim 1.1.13，编译器只输出新目录中的探针，不覆盖现有运行器/模型。

| 独立JSBSim场景 | pilot代表值 (m/s²) | 观察限制 |
| --- | --- | --- |
| 地面初始0° | 末样本 `[1.423, ~0, -9.705]`；本run 3秒均值 `[1.308, ~0, -9.686]` | 接地后稳定；0.2秒 z=-13.990 是起落架接地瞬态，不当作静止标定 |
| 离地1000ft AGL、初始0° | 0.2秒 `[0.222, ~0, -0.367]`；同期重力模约9.822 | 近似自由落体初段比力接近零；3秒后受空气力影响，末样本 z=-3.788，不把全程均值当自由落体 |
| 地面初始+20° | 0.2秒实际滚转+18.943°，pilot y=-3.934 | 随后姿态受接地反力回落，不是固定姿态标定 |
| 地面初始-20° | 0.2秒实际滚转-18.943°，pilot y=+4.861 | y符号反向；接触力使幅值不对称 |

四场景均从 JSBSim property 与 `FGAuxiliary::GetPilotAccel`两个取值入口逐轴
核对同一FDM对象（不是两个独立物理真值）；`EYEPOINT=[20,0,5] in`被
实际加载，CG随燃料/质量变化，约`[36.396,0,3.390] in`。
对比[前一次真实PX4/JSBSim在线run](../.runtime/runs/sim01a-live-20261026T203023619306/result.json)
原始HIGHRES_IMU均值`[1.225,-0.186,-9.731] m/s²`：与地面探针
末样本同量级、z符号一致。两个run的控制、噪声、机体状态、时刻和PX4偏置
均不相同；**没有**按样本配对或计量误差结论。定向缺场景、错误自由落体/
滚转、错误EYEPOINT和缺实际姿态收据均按预期失败；全仓轻量回归
404/404通过，`git diff --check`通过。没有启动ROS、PX4或长时推理；
原始在线run仅只读作为异run参考。

## 明确保留

静态源码+另一条JSBSim进程支持将本配置 `a-pilot`解释为**含重力反力效应
但不直接加重力向量**的pilot点比力读数；ROS `acceleration_type=specific_force`
在此虚拟配置下有支撑。没有同run的桥接内FDM属性/HIL_SENSOR/vehicle_imu
同步收据，不能证明全链物理逐值误差或动态安装杆臂补偿；当前虚拟适配
没有真实IMU安装外参、偏置/协方差质量、设备同步或雷达红外物理标定。
继续保持默认关闭的可选IMU和既有未知质量语义；不把本子范围写成正式
PERF-01、完整 Phase 2 或实机验收。
