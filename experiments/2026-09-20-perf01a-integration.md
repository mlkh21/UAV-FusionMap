# EXP-20260920-001：PERF-01-A占位闭环与SIM-01D前置复核

日期：2026-09-20；主责任：Technical Lead；状态：短时占位链路技术验证已完成，PERF-01进行中。

## 范围与版本

用户授权先提交Git，再继续除归档外的工作。基线为功能分支
`feature/engineering-initialization`的`4bd0c33 feat: establish engineering baseline`。
本记录对应该基线之后的工作区实现；未额外提交或推送。ENV-03不执行归档。
system/simulation/sensors/perception/mapping的业务边界和训练专用LiDAR隔离保持。
本次使用simulation的静止状态fixture，没有启动PX4/JSBSim或研究模型。

## 修改与原因

- `simulation/ufm_simulation/perf01a_fixture.py`、source薄节点：状态生成归simulation；
  等待下游就绪，按配置发布固定样本数，发布完后等待运行器排空并停止。
- `sensors/ufm_sensors/perf01a_fixture.py`、sensor薄节点：功能级Radar/IR及同步，
  用已适配odom/base_link状态构造参考时刻变换；state/clock回调共同门控同一采样，去重旧状态。
- `perception/ufm_perception/placeholder.py`：修复Radar字典索引错误；使用实际姿态/平移
  生成odom占据，输出context与网格参考系一致，不产生free证据。
- `mapping/ufm_mapping/local_map.py`：几何/时间/context先校验再原子更新；不可用首次输入
  不使地图变valid；严格时间递增、最近样本去重和稀疏cell上限；保留last_observed_timestamp。
- ROS新增10条消息，总计14条；新增perception/mapping包，总计5包。codec保留采样纳秒、
  质量不可用语义、pose/voxel/cell uncertainty；既有AircraftState消息未改变。
- `ros_ws/perf01a_run.py`：统一启动、先订阅后发源、逐话题计数/身份/时间校验、地图排空、
  独立端口和进程清理。每次run目录唯一，结果用`open('x')`防覆盖。
- `ros_ws/perf01a_metrics.py`：nearest-rank百分位、拒绝负阶段时延和重复事件，
  丢帧按未闭合Radar根样本计数，不能用同一样本多次拒绝抵消其他样本丢失。
- `configs/perf01_budget.yaml`保留ARS548未知硬件频率，另标20Hz fixture频率；
  runner读取预算、向launch传参并在新run保存配置。Conda/Noetic环境增加业务包路径。
- SIM-01D运行器只接受项目独立候选；checker默认stdout只读，显式`--output`拒绝覆盖。

## 运行与结果

复现入口（项目根目录，均使用Radar-Diffusion Python）：

```bash
bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_*.py' -q
bash ros_ws/sim01_env.sh python ros_ws/perf01a_run.py --duration-s 8
```

无需分开启动observer/roscore或手工选择终端菜单；runner自动选择独立11421端口，
端口被占用时拒绝启动。交互终端Foxy(1)/Noetic(2)菜单不改变项目入口的Noetic/Conda选择。

- 122/122全仓契约测试通过（PERF核心14、metrics2、ROS codec3、SIM-01D6及原有97）。
- 独立catkin构建已于09-18通过：5包/14消息，Python为指定Conda解释器。
- SIM-01D现有C++边界程序复跑PASS，6/6前置契约回归通过，候选ldd预检通过。
- 09-20两次统一短run通过：`perf01a-20260920T103113500289`、
  `perf01a-20260920T103413332214`。后者含最终配置绑定及端口关闭校验。

最终run：
[报告](../.runtime/runs/perf01a-20260920T103413332214/perf-report.json)、
[原始事件](../.runtime/runs/perf01a-20260920T103413332214/events.json)、
[接收记录](../.runtime/runs/perf01a-20260920T103413332214/receipts.json)、
[预算配置](../.runtime/runs/perf01a-20260920T103413332214/budget.json)。

| 检查 | 实际结果 |
| --- | --- |
| 采样任务 | 20Hz × 8秒，共160样本；业务timestamp跨度7.95秒 |
| state/Radar/IR/bundle/occupancy/map接收 | 各160条，身份与参考时间一致 |
| PerfEvent | 800条valid，160根样本全部闭合 |
| 缺失/显式拒绝 | 0/0 |
| 实际地图 | 每次1个observed cell，revision为1至160 |
| sensor→occupancy P50/P95/P99 | 1.479 / 2.166 / 2.565 ms |
| sensor→map P50/P95/P99 | 2.464 / 3.368 / 3.561 ms |
| 排空和清理 | 节点组与master退出0，无强杀/进程组残留，11421端口关闭 |

计时起点是fixture生成路径中的Radar事件，终点是地图发布调用后的事件。
这是同机monotonic时钟的功能链路时延；不含设备曝光、真实驱动接收或跨机时钟误差。
sensor_bundle_ready/occupancy_ready事件在业务发布之前发出，确保跨节点计时因果顺序。
接收记录另证地图实际送达，报告的发布时延不等同于应用接收时延。

## 失败、纠正与证据偏差

1. 09-18两次零事件的直接证据是观察窗口未重叠：observer日志中第一次
   16:12:04.506结束，而节点16:12:25才初始化；第二次observer16:26:07.133结束，
   节点16:26:24才初始化。此前将零事件归因于rospy.Timer/首批状态丢失的说法无证据支持，撤回。
   已去除无依据墙钟重复采样，改为状态与clock驱动；统一入口消除分步审批/启动延迟。
2. 09-18重复使用`.runtime/runs/perf01a-short-20260918/perf-report.json`，工具命令曾
   `rm -f`旧报告后重建，早期零事件报告原文件/mtime未完整保留。该操作违反历史产物保护要求；
   旧`ros-logs`和会话中的0事件输出仍可核对，但不能声明旧报告字节/mtime保持不变。
   不重造历史文件，不伪造时间；本次新run的技术结论不代表用户已接受此证据偏差。
3. 09-20第一次统一run `perf01a-20260920T102926076186`恰遇并行修改中间态，
   map模块语法错误导致启动失败。该run日志/失败报告保留；待几何单测完成后重跑通过。
4. 纯测试还先复现了字典索引、坐标遗漏、unavailable变valid、无效体素部分写入等问题；
   修复后按同一契约回归，没有通过放宽预算阈值让运行通过。

## 限制与下一步

实测负载为静止状态、单Radar点、2×2红外fixture、0.5m分辨率、64×32×16小网格
（覆盖32×16×8m），不是640×512热图或300×120×60m预算覆盖。
IR参与配对，但占位算法只把Radar点转成占据，不是已实现Radar—IR融合网络。
时间差/pose_age在此fixture中均为0；一般接口仍无姿态插值和扫描运动补偿。
内存/CPU统计仅为observer自身，未测目标Jetson、GPU/NPU、整链功耗。
地图目前是固定odom格网和稀疏cell保留上限，未实现随飞机平移的滚动窗口、ROS查询或高级概率融合。
老化查询函数可检测过期cell，但尚无独立应用查询服务。disabled/research完整运行模式仍待接入。

PERF-01继续推进独立Radar/IR时序与丢帧/超时场景、完整图像负载、阶段计时细化和资源采样，
再进入35/50/70m/s场景。SIM-01D完成前置修补，40分钟连续跨边界试验仍未执行。
ENV-03按用户指示不归档；无模型质量、机载实时、HIL或实飞验收结论。
