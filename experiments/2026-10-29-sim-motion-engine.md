# EXP-20261029-008：同FDM真值与受控采样真实闸门

日期：2026-10-29；主责任：simulation_engineer；状态：已完成（SIM-MOTION-SW-02软件范围）。
方案与文件清单：[交接说明](../docs/SIM_MOTION_SW02_ENGINE_20261029.md)；依据ADR-042。
保留分支feature/engineering-initialization、HEAD d96d4439da1007489c80e7f21b132abff16505bf及全部dirty/untracked。
仅改本仓；没有改研究仓库、第三方原源码/旧PX4与bridge二进制、Conda、终端ROS选择或历史产物。
无提交/推送、新Hash、训练、模型forward、真实DEM、占据融合或飞行控制指令。

## 1. 目的与预期

按SW-01保存的独立预期，真正读取同一JSBSimBridge持有的FDM，并验证Gazebo暂停步进、
真实Ray/Camera采样、同帧运动元数据、唯一公共clock/state/TF及terminal失效。
新的运行目录先保存literal坐标/时间、profile和gate预期，再构建/运行。
固定4ms/1ms步进、每25步采样、1ns源时间容差、首3s/后1s ACK墙钟门槛均不放宽。
软件采样总窗250步/1s，显式IC速度5m/s和高度8m；不要求或声称稳定受控飞行。

## 2. 过程、失败与修补

1. sys.executable核对为/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python。
   独立编译现有11个桥接源和本仓宿主，另编译共享元数据、step、Ray/IR插件。
   仅使用.runtime/sim-motion-build，无外层catkin构建或依赖安装。
2. 首次真实[152427207003](../.runtime/runs/sim-motion-sw02-20261029T152427207003/manifest.json)：
   首100ms双ACK成功，第200ms只有IR，Radar异步更新竞争，外层RPC超时，run失败并完整清理。
   保留50条成功事务及原raw/ACK/终止，不把缺首帧之后的窗口当通过。
   改为暂停world步进后显式强制真实Ray采样，原LastMeasurementTime仍精确200ms；
   IR内部准备子步缓冲，公开输出仍10Hz。未替换轨迹、点云或图像，未改戳。
3. [152633552937](../.runtime/runs/sim-motion-sw02-20261029T152633552937/validation.json)：
   首次250步/10对/20 ACK通过。后续增加实际二进制逐点Doppler、IR像素和TF几何核验，
   不把这一轮早期检查说成已经覆盖新增核验。
4. 两次首100ms ACK丢失注入[152729221250](../.runtime/runs/sim-motion-sw02-20261029T152729221250/manifest.json)、
   [152939260259](../.runtime/runs/sim-motion-sw02-20261029T152939260259/manifest.json)：
   时钟停在96ms、terminal和锁定技术检查通过，但PX4启动尚未完成，停止时启动脚本返回2、进程255；
   两轮完整用例均保留失败，第二轮先停PX4仍复现，因此不能只归因为先关闭bridge。
   后续将运行期故障明确放在第250步，且要求PX4启动脚本成功，不改变正常首帧/窗口或ACK门槛。
5. 初次全仓[153127899943](../.runtime/runs/sim-motion-sw01-20261029T153127899943/report.json)：
   855项中1项ImportError，新ROS运行器与旧tests/sim_motion_run.py同名被全仓sys.path解析覆盖。
   新运行器改名sim_motion_gate_run.py，旧测试入口保持，定向36/全仓855复验通过。
6. 运行期故障[153342575240](../.runtime/runs/sim-motion-sw02-20261029T153342575240/validation.json)通过：
   第250步仅控制端忽略IR ACK，raw与两条真实ACK仍在观察收据中；提交止于249/996ms，
   terminal与旧run锁定通过，真实PX4已启动且清理全部正常。
7. 增加八类真实服务拒绝后的正常[153425923646](../.runtime/runs/sim-motion-sw02-20261029T153425923646/manifest.json)
   保留失败：terminal抢在最后clock跨话题到达前清除适配层pending，缺最后有效state/TF。
   正常结束前增加有界last-state/TF排空，不重发或修改任何测量/clock，不改变状态适配门槛。
   [修补后153602032941](../.runtime/runs/sim-motion-sw02-20261029T153602032941/validation.json)全部通过。
   最后以同一源码复验[运行期故障154332927492](../.runtime/runs/sim-motion-sw02-20261029T154332927492/validation.json)，
   249步/996ms停止、真实原始载荷、terminal/锁定及清理全部通过；最终正常/故障源快照一致。
8. 最终收据审查发现未触发的证据风险：raw已写入但业务解码失败后，计数不增加，后续同类消息可能复用路径。
   改为create-only，首次记录错误后停止继续接收，新增一项实际生成坏载荷的二进制保全反例。
   [最终正常154737606036](../.runtime/runs/sim-motion-sw02-20261029T154737606036/validation.json)和
   [最终故障154851651514](../.runtime/runs/sim-motion-sw02-20261029T154851651514/validation.json)均通过；
   [最终离线154728742795](../.runtime/runs/sim-motion-sw01-20261029T154728742795/report.json)37项/856项通过。

以上修补没有覆盖任一既有run，失败manifest仍为false。运动场景端到端感知/地图和新窗口另属SW-03。

## 3. 最终实测与回归

| 检查 | 结果及证据 |
| --- | --- |
| 同FDM真实运动 | 最终250步/1s，初始[0,0,8]m、终点[5.4362694069936195,-0.0024849018548632144,4.626639929639477]m；位移6.397858m，显示代理回读匹配 |
| 时间与单权威 | 251条公共clock/有效source/适配state/动态TF，10组实际采样时间100—1000ms，20 ACK；Gazebo clock进诊断，未启动旧state_clock/scene_state_source/scene_pose |
| 真实载荷 | 13,217回波，逐点功能Doppler/杆臂/强度核验；最大Doppler误差5.22062510555088e-7m/s；IR 320×240 32FC1前后67,933像素变化；TF几何等于应用帧 |
| 事务 | step24暂停100ms不推进或重复raw；step25幂等；八类实际坏请求在world=0原子拒绝；不存在无限去重或消费raw来伪造状态 |
| 故障范围 | 第250步控制端丢ACK后公共时钟止于996ms、terminal非几何传播、旧run拒绝；仅证明发布/推进门，未证明Bundle消费 |
| 严格合同 | [154728742795](../.runtime/runs/sim-motion-sw01-20261029T154728742795/report.json)：20组实际genpy与保存字节一致、旧17份定义保持，37项定向0.167s、856项全仓59.594s通过；先前855项成功记录保留 |
| 旧estimated链 | [T-14 fixture](../.runtime/runs/sim01a-fixture-20261029T153435611895/manifest.json)：实际ROS旧状态、Odometry/唯一TF及异常检查通过，清理通过 |
| 旧静态原生入口 | [153629640467](../.runtime/runs/sensor-scene-20261029T153629640467/manifest.json)：Gazebo/标准RViz、原始Radar/IR/地图、图与像素/清理检查通过；这些图片仍是旧固定场景 |

新增11项测试覆盖实际转换器对冻结解析值、地心/大地纬度区别、旋转/单位/杆臂、源时间/距离/
地面拒绝、单pending、重复/冲突/身份、新run空事务、失败/晚响应、坏回读、terminal流锁定与首份坏收据保全。
本轮不是机载RSS或正式性能测试；每流512/总16MiB只约束逻辑/线格式收据。
实际二进制、源FDM、注册、事务、图、参数、预期与各run源快照均保留，无无用途Hash。

## 4. 执行命令与修改范围

从仓根以bash ros_ws/sim01_env.sh启动指定解释器，使用新名字sim_motion_gate_run.py：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_motion_gate_run.py --build-only
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_motion_gate_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_motion_gate_run.py --fault missing-ir-ack
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_motion_run.py --full
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim01_smoke.py --fixture --t14-compat
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sensor_scene_run.py --check
```

新增/修改源码、测试与角色边界见[交接文件表](../docs/SIM_MOTION_SW02_ENGINE_20261029.md#1-已有代码与本轮实现)。
同步PROJECT_STATUS、README、架构/数据/传感器/坐标规范、具体设计、开发计划、ADR/实验索引、交付/报告增量。
恢复使用新隔离run，只停止本轮进程组；端口占用或既有PX4直接拒绝，默认旧入口保留。

## 5. 未验证与下一项

下一项SW-03，接通明确真值模式的SceneStream/placeholder/M1 latest和公开查询/执行回放，
验证观测时刻Context、无回波/失效不free、失联历史与新run恢复，并交付新的原生运动窗口素材。
本轮新模式没有装配该端到端链路，也没有为运动场景截图；旧报告八图不替换为新运动结论。
首个采样立即失败时的PX4启动中断仍保留两次失败记录，未宣称该完整清理用例已通过。
真实感知/设备/DEM/占据融合、机载资源、高速控制与正式阶段退出保持未验收，research保持fail-closed。
