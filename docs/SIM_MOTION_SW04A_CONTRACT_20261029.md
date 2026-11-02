# 多场景运动清单与独立预期离线交付

日期：2026-10-29；版本：v0.1；任务：SIM-MOTION-SW-04A；主责任：simulation_engineer。
状态：已完成（清单/逻辑校验/独立预期/实际线格式离线范围）。
依据：[多场景设计](SIM_MOTION_SW04_MULTISCENE_DESIGN_20261029.md)、ADR-043；
实际记录：[EXP-20261029-011](../experiments/2026-10-29-sim-motion-multiscene-contract.md)。
新增9场景的真实动力学、几何切换及原生窗口均未运行。

## 1. 已有链与本轮文件

复用SW-01的SceneFrame/SceneCaptureAck/SceneStep与严格codec、SW-02的SceneRegistration，
以及既有SceneStream→placeholder→M1和公共Radar/占据/快照/查询codec。
没有改它们的公共字段、运行入口或旧固定profile。

| 本轮新增文件 | 用途/消费边界 |
| --- | --- |
| [清单](../configs/sim_motion_multiscene_fixture.json) | 固定9例IC/几何/epoch/故障/原生显示选择与预算，当前只由离线工具读取 |
| [motion_suite.py](../simulation/ufm_simulation/motion_suite.py) | 独立有界加载、具名逻辑合同/几何模板、隔离case副本；不启动模拟器或ROS |
| [独立字面量](../tests/fixtures/sim_motion_multiscene_expectations.json) | 9例目标、7模板、姿态/杆臂、射线、6查询及源输入参考；不导入生产模块生成 |
| [fixture](../tests/sim_motion_multiscene_fixture.py) | 77组协议输入/独立struct字节、9组原始源输入；不构造真实轨迹 |
| [oracle](../tests/sim_motion_multiscene_oracle.py) | 独立NED/FRD→ENU/FLU矩阵、ECEF/feet算例、box slab最近相交；不被在线模块导入 |
| [checks](../tests/sim_motion_multiscene_checks.py) | 18次合成源转换、纯软件空观测/历史TTL与36组旧公共消息往返 |
| [离线入口](../tests/sim_motion_multiscene_run.py) | create-only先冻结预期/独立字节，再校验/真实genpy对账/定向或轻量全仓 |
| [测试](../tests/test_sim_motion_multiscene.py) | 23项新增输入/几何/语义/真实线格式/证据完整性测试 |

另新增本说明与中文实验记录，更新状态/决策/架构/计划/入口及实验索引。
没有新节点、launch、服务、客户端、世界生成/切换实现；现有运行链未引用新oracle或清单。

## 2. 清单与几何合同

schema为`sim_motion_multiscene_fixture.v1`，suite_id为`sim-motion-multiscene-v1`。
根字段仅`schema_version / suite_id / base_motion_profile / cases / resource_limits`。
base路径必须逐字为`configs/sim_scene_motion_fixture.json`，且加载后继续经旧固定v1校验。
不接受绝对路径、`..`等价路径、未知版本/身份，也不通过替代profile绕过250步/5m/s等界。

case仅`case_id / ic_degrees / geometry_id / epochs / fault / expected_id / native`：
S01—09顺序固定，IC/几何/expected_id逐例绑定；ψ=0/90/180与倾斜[10,5,90]只允许设计枚举。
S07的两次epoch固定在排空后step100/225，唯一obstacle_wall移到[100,0,8]/[12,0,8]m。
S08仅kind1/step125忽略真实ACK；其他case fault必须None，不把传感器故障变为正常空点。
只有S05/S07可native，且必须严格bool；step/预算整数不接受float或bool。

加载最多读取256KiB+1字节，超限先拒绝；允许恰好256KiB的合法空白填充JSON。
拒绝重复键、坏UTF-8、非有限、深度>8、节点>8192、对象>64字段、列表>512、
字符串>128 UTF-8字节；文本先检查字符数再编码。实际合同进一步限制9例、2 epoch和8 box。
所有声明层未知字段拒绝，包括LiDAR/target/observed_mask或控制/时长覆盖。

7个具名模板在独立逻辑模块中定义并与测试侧字面量逐值比较，不能任意修改尺寸/位置/材质。
legacy明确inherit_legacy/include_ground=true；empty明确两者false且objects为空。
继承旧场景与空碰撞域是不同命令，不依赖objects空列表猜测，当前尚未生成新SDF。
`validate_geometry`拒绝非正尺寸、非有限、未知字段、超量对象及与具名模板不符的几何。
每次`geometry_template`/`case_spec`返回独立对象；S01显式继承旧地图，S02—09给出设计中的
[-40,-40,-8]m/0.5m/[160,160,64]/20000 cell/500ms TTL参数，不修改旧配置。

## 3. 独立预期与实际字节

冻结输入/预期不导入新生产模块、genpy或动力学转换器。
先保存独立JSON、wire layout、原始合成源输入及struct预期字节，再实际调用已有生成消息。
77组=9例×8组（0/25步Frame、Request、Response及双ACK）+S08五组125步/部分响应。
它们承载初始姿态的协议算例，不是假装100ms或500ms的真实FDM轨迹。
Radar ACK的实际published可为true，同时故障响应radar_timestamp=None：设计是在事务中忽略回执，
不是回执从ROS线格式中消失。整数0、缺失采样时间和部分应用继续由既有flags区分。

独立struct字节与真实genpy逐字节、反序列化/重编码逻辑逐值对账，实际类型来自
`.runtime/ros/devel/lib/python3/dist-packages/uav_fusionmap_sim_scene_msgs`，来源文件记录在report。
未重新生成或修改消息；未用mock代替消息线格式，没有新增Hash。
25份旧消息/服务定义（原17+场景3+地形5）及7份旧配置/入口与冻结副本逐值一致。
验证器也拒绝冻结输入漏项/重排/改值及已有部分actual/日志/报告，防止不完整输入被误算通过。

## 4. 实际结果与证据类型

| 实际验证 | 结果 | 能力边界 |
| --- | --- | --- |
| 23新增/运动定向/全仓 | 23项新增，66/66定向、885/885轻量全仓通过 | 不是9个实际运动场景验收 |
| Scene协议 | 77组、19,751字节与独立struct预期一致 | 真实生成类型，未运行ROS服务 |
| 空观测公共往返 | RadarFrame/OccupancyObservation/MapSnapshot各10份，MapQueryResult六份，共36组/11,191字节 | 使用纯软件输入，不是真实Ray零点/Camera采样 |
| 源转换 | 9例×初始/移动算例共18次，初始姿态、非零ECEF差、单位/轴向均对独立预期 | 实际已有Python转换器，输入为合成源记录，非JSBSim运行 |
| 几何oracle | 初始近/远box、偶数网格h48/v12、平行/后向/内部/量程端点及空/远域2304射线核对 | 未与真实Gazebo距离/碰撞/热像对照；边界分类和实采容差仍待B/C |
| 空图/TTL | 新图unavailable→10空帧revision10/unknown；900ms header保留400ms cell，等TTL occupied/+1ns stale；旧时刻/身份拒绝 | query按显式时间，不新增服务墙钟存活门 |

查询缺失uncertainty经旧codec规范化为unavailable结构，不把None转成可用质量；
旧概率float32只按既有精度比较，缺失标志及原始证据整数时间精确保持。
完整收据和日志见[实验记录](../experiments/2026-10-29-sim-motion-multiscene-contract.md)。

## 5. 运行、恢复与下一步

从仓根执行，入口核对固定Conda解释器；默认仅定向，`--full`加全仓轻量回归：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_motion_multiscene_run.py --full
```

每次创建新目录。`--freeze-only`可先单独保存，后以`--verify`指定该输出目录；
已经实际校验过的目录拒绝复用，不删旧预期/失败/部分结果，另建新run恢复。
本轮不需要构建、Master或窗口，不修改外层catkin、第三方源/二进制、研究仓库或环境。
16MiB收据/512条等预算仅定义与校验，未做实际多场景资源测量或正式性能验收。

直接下一项SIM-MOTION-SW-04B：显式新装配、IC/SDF、暂停几何切换屏障和场景化query/checker，
先核对真实空域/切换/中途故障；SW-04C再执行最终9核心/3兼容及原生交接。
仍保持同FDM/原始时间/唯一权威、1秒上限，无控制或自动解锁；研究质量与真实输入任务继续暂缓。

2026-10-29后续：[SW-04B机制交付](SIM_MOTION_SW04B_ENGINE_20261029.md)已完成实际空域/切换/故障定向。
新严格几何规则/原48假设失败处置见[设计修订](SIM_MOTION_SW04_MULTISCENE_DESIGN_20261029.md)，
不追溯改变本轮离线证据。下一项SW-04C完整最终矩阵与原生交接。
