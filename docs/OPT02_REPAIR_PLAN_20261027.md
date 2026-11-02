# OPT-02 第二轮审查修改计划

日期：2026-10-27；主责任：integration_engineer；状态：已完成（软件与fixture ROS范围）。
依据：OPT-01实施后的第二轮只读审查；完成状态以新增实验记录为准。

## 1. 目标与边界

关闭已复现的5项遗漏：Bundle组合一致性、反射矩阵、必需业务连接握手、XML-RPC
配置快照和质量字段校验。保留OPT-01已完成的子范围与历史证据，新增问题单独跟踪。

本次沿用现有0.1消息及字段、Radar参考时刻、5ms同步和10ms历史位姿年龄边界；
启动图显式覆盖参数时由同一装配值传给生产侧与消费侧，不能在消费端另写冲突默认值。
40ms默认等待、20ms性能目标、训练监督隔离、PERF-01/ENV-03和阶段退出门槛保持原约定。
不引入新的定位层、研究forward、传感器输入或概率地图算法；不修改研究仓库、环境或旧run。
2026-10-27收到“按照计划执行，不要过度防御”，开始按下列范围实施及验证。

## 2. 工作包与执行顺序

| 批次/编号 | 优先级 | 唯一主责任角色 | 工作 | 输入依赖与交付 |
| --- | --- | --- | --- | --- |
| A / OPT-02A | P1 | perception_engineer | SensorBundle消费入口一致性 | 现有DATA_FORMAT/SENSOR_INTERFACE；单一入口校验及反例测试 |
| A / OPT-02B | P1 | perception_engineer | 合法旋转校验 | A的可信上下文分类；源/机体变换反射拒绝，固定/滚动行为一致 |
| A / OPT-02C | P2 | mapping_engineer | Quality结构与数值校验 | 既有Quality及查询合同；编码、解码、纯业务地图入口与查询保真测试 |
| B / OPT-02D | P2 | integration_engineer | 必需业务连接与可选观察分离 | A/B/C通过定向测试；确定性延迟连接测试及源开始发布门禁 |
| B / OPT-02E | P2 | integration_engineer | 有效配置与参数快照序列化 | 现有纳秒字符串约定；3秒以上整数往返、同配置及启动测试 |
| C / OPT-02V | 验收 | tester | 组合回归与软件子范围验收 | A—E全部完成；全仓回归、独立ROS证据、清理及文档交付 |

批次按表顺序推进；角色表示责任，不默认已安排多人或并行agent。
目标顺序为A→B→C，具体执行日期以实施开始登记为准；不据此修改原阶段日期。

## 3. OPT-02A：Bundle消费入口

真实链路：sensors构造SensorBundle → ROS编解码 → perception入口 → 选定模式 →
OccupancyObservation → mapping。字段可解码不代表整个组合满足契约。

在perception内建立一个可独立测试的消费入口校验，ROS节点只调用它；保持codec
处理线格式，不把同步匹配算法搬进ROS包，也不让perception导入sensors私有实现。
候选改动为`perception/ufm_perception/input_contract.py`、现有`modes.py`及感知节点。
源端`build_sensor_bundle()`继续负责生产与匹配，消费端验证已经声明的关系，不重新配对。

- 内外Header的run/clock必须一致，frame与对象语义一致；Radar参考时刻必须等于Bundle时刻。
- 重算`abs(IR.timestamp - Radar.timestamp)`及`Radar.timestamp - State.timestamp`，
  同时检查门限、非负历史年龄和与声明delta/age一致；不能只相信消息中的年龄字段。
- 校验Bundle、IR与SpatialContext的标定引用一致，以及上下文参考时间、clock与源/目标frame。
  这只证明引用一致，不代表真实标定已经通过；不能假设Radar与Body重合。
- paired launch将已有max_delta/max_pose_age参数同时注入sensors/perception；异步runner
  从同一个已解析profile装配两侧门限。滚动fixture使用具名配置，不读sensors私有ROS参数。

错误出口必须区分：外层身份或上下文不可信时只诊断拒绝，不伪造坐标/时刻；
外层身份与上下文可信、内部组合不成立时可输出该外层身份下的空unavailable；
后端异常沿用明确unavailable。三种情况都不能新增地图证据或刷新旧单元时间。

验收包括：跨run、跨clock、错frame、Radar参考时刻不一致、IR超时、未来/过旧位姿、
伪造delta/age、标定引用不一致；另覆盖5ms/10ms边界及合法配置覆盖，防止误拒绝。

## 4. OPT-02B：旋转与上下文

对声明available的变换检查有限4×4、齐次末行、正交性和`det(R)≈+1`；
`diag(-1,1,1)`反射、缩放、剪切和退化矩阵必须拒绝。保持已有容差，除非RED证明
其与当前数值精度不兼容；不使用单位矩阵修复坏输入，不无条件重新正交化。

修改范围：`placeholder.py`的Radar→odom变换校验、A的上下文校验，以及
`mapping/local_map.py`中固定/滚动模式所消费body变换的相同合法性规则。
合法旋转和平移仍按原观测时刻使用，不新增TF查询或姿态插值。

验收：反射输入不生成valid占据、不进入地图；合法90°旋转、平移和边界容差不回归。
对已有地图注入错误上下文时，origin、cells、revision和观测时间均不得部分改变。

## 5. OPT-02C：质量字段

修改范围：`ufm_ros_contract/codec.py`及`perf01a_codec.py`/`query_codec.py`的共用质量
转换路径；`mapping/local_map.py`保留纯业务输入防线，不反向导入ROS包。

confidence只能为None或有限[0,1]数值，拒绝bool、NaN、Inf及越界值；0不是缺失。
unavailable保持逻辑None与ROS空数组语义；available必须有kind、unit、source及
有限非空数值。occupancy_variance按既有标量非负语义检查；其他种类只执行已有
明确合同，不发明统一维度、单位或阈值。不为代码复用开放尚未验收的State/IMU协方差。

验收：非法质量不能以available状态进入地图/查询；地图更新拒绝必须具有原子性。
已有confidence=0/0.25、occupancy_variance=[0.125]和None均往返保真，unknown不变free。
不裁剪非法confidence，也不静默丢弃错误数值并补写成可信质量。

## 6. OPT-02D：启动握手

缺陷是关闭观察器等待后连必需业务输出连接也跳过，而源只检查ready与state/clock连接。
应分别定义“节点已初始化”“必需业务连接就绪”“可选观察器就绪”，不增加公共消息。

- sensors在所需状态/clock与Bundle→perception连接成立后允许源采样。
- perception在Occupancy→mapping业务连接成立后报告业务ready。
- mapping不要求快照观察器或查询客户端存在；诊断关闭时不要求PerfEvent订阅者。
- source只在同run的必需业务ready均成立后发布首帧；等待采用有界单调墙钟，不能等仿真clock启动。

修改范围：源/paired sensor/perception节点、`inference_fixture.launch`及现有相关launch；
仅在其他入口存在同一缺陷时联动，不把全部历史runner重写为新框架。
验收先用可控连接计数：地图晚连接时源发布数必须为0；连接后从原首个sample开始。
再用独立ROS延迟启动场景验证原20帧全部闭合；必需消费者始终缺失则明确超时，
不能宣称ready。旧观察器开启、关闭诊断和无快照客户端三种组合均覆盖。

## 7. OPT-02E：配置快照

修改范围：`ros_ws/runtime_config.py`、感知/地图的`~resolved_map_config`发布，以及
消费该快照的`local_map_query_run.py`检查。业务计算使用原整数纳秒，写参数服务器时
按现有约定把纳秒字段编码为十进制字符串；读取/比较时统一解析，不转浮点、不截断。
配置文件原schema与字段不变，已有小整数快照可由读取端兼容。

验收：100ms、3s、32位边界与int64边界精确保真；至少一个3秒TTL的真实ROS启动
通过。无效/越界/非整数时间应在启动源前明确拒绝；记录错误不能掩盖配置错误。
感知与地图快照归一化后仍一致，现有独立入口验收不因字符串/整数承载差异误失败。

## 8. 测试、产物与关闭条件

1. 在正确Conda解释器下把5项已复现遗漏固化为RED测试，再逐工作包GREEN；
   修改既有将0个必需业务连接视作ready的测试预期，保留不需要观察订阅者的要求。
   旧测试若手工构造了身份/时间自相矛盾的Bundle，应修正其fixture生产数据并记录依据，
   不为维持原绿灯放宽校验，也不把这些旧测试输入视为新的合法契约。
2. 以最近423项轻量测试为基线运行完整回归，新增组合测试覆盖“坏帧→合法恢复”、
   “已有地图→错误输入→查询时间不刷新”、同run计时端点和未知区域；不以测试数量代替覆盖。
3. 用独立Master/端口、新run目录完成：延迟业务连接、3秒TTL、旧paired、异步、
   disabled/research拒绝、滚动查询、可选IMU和独立训练yaw。按实际影响合并场景，
   不重复相同短测当新交付；ROS本地socket若受沙箱限制，按工具权限机制执行。
4. 每个ROS run保留实际命令、有效配置、输入/输出身份与计数、错误原因、查询结果、
   Python路径及进程/端口清理收据；P99只作对应run诊断，不宣布正式性能通过。
5. 追加独立中文实验记录并更新EXPERIMENT_LOG、PROJECT_STATUS、适用契约说明及
   DECISION_LOG；旧OPT-01记录保留，可追加勘误链接，不覆盖其历史结果。

关闭OPT-02必须同时满足：5项遗漏均有反例修复证据；合法边界与旧入口兼容；
错误输入无新增地图证据；必需业务未连接不发首帧；配置纳秒精确；全部本次进程/端口
清理通过。未执行或失败项单独保留，不以最近全仓测试通过替代新的ROS验收。

## 9. 风险与恢复

最主要风险是严校验误拒绝合法退化消息、节点互等和把承载类型改动误当成业务值变化。
实施时逐批保存差异与结果；失败只修正本批补丁，保护已有未提交工作和全部历史产物。
不以关闭校验、放宽门限或删失败记录作为恢复方式；不自动提交/推送。

现有schema字段和层间数据流预计无需改变。如发现必须新增消息字段、跨层共享包、
新标定/时钟假设或改变同步政策，先更新具体方案再确认，不能夹带进本次修复。
本计划不关闭真实设备/研究模型质量、PERF-01、ENV-03或完整阶段验收。
