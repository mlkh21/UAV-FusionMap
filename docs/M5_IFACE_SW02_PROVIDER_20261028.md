# M5-IFACE-SW-02：独立地形Provider与ROS服务

日期：2026-10-28；主责任：mapping_engineer；状态：已完成（合成软件/独立ROS范围）。
依据：[具体方案](M5_IFACE_DESIGN_20261028.md)、[SW-01公共合同](M5_IFACE_SW01_CONTRACT_20261028.md)。
实际记录：[EXP-20261028-013](../experiments/2026-10-28-m5-provider-ros.md)。

## 1. 实际生产消费链

```text
显式公共dataset JSON -> mapping.TerrainProvider -> 私有TerrainFixture
受认可的唯一/clock -> ROS薄包装 -> Provider.observe_clock
TerrainProvider.query/status -> SW-01严格codec -> TerrainQuery / TerrainStatus
```

[TerrainProvider](../mapping/ufm_mapping/terrain_provider.py)只在显式构造时启用，默认enabled=False。
公开消息字段保持SW-01冻结值；不将地形加入旧地图工厂、MapQuery或任何占据更新。
新增包[uav_fusionmap_terrain](../ros_ws/src/uav_fusionmap_terrain/package.xml)依赖rospy、rosgraph_msgs与独立地形消息包。
[terrain_node.py](../ros_ws/src/uav_fusionmap_terrain/scripts/terrain_node.py)调用
[terrain_ros.py](../ros_ws/terrain_ros.py)，后者只包装mapping公开入口与基础设施审计。
不导入application、GIS、研究模型，不订阅Radar/IR/state/Odometry/TF/训练监督，不发布TF或控制。

| Provider入口 | 已实现行为 |
| --- | --- |
| 构造(dataset,run_id,clock_id,enabled=False) | 有界验证公共输入、绑定具名注册/域，生成新UUID实例；尚未安装 |
| set_clock_source(available,reason) | 设置装配/来源核对结果；来源失效清除接收存活，恢复须再收到合法clock |
| observe_clock(timestamp,received_ns) | 整数运行时间和独立单调接收时间；回退永久锁定，不允许请求推进时钟 |
| startup_install() | 授权前等待；仅一个启动候选/首次尝试，不反复重载/重绑时间 |
| install(dataset) | 仅离线多版本入口；预备公共Context/版本集合后调用原候选原子安装，失败单独保留尝试结果 |
| query(request) | 捕获同一临界区的evaluation/版本，执行live门控，返回独立公开逻辑对象 |
| status() | 状态序号递增；保持采集/安装时间和地形revision；显示最后安装尝试及失败 |
| disable() | 终止本实例地形使用，后续不给旧Context/高度 |

时钟、安装、查询、状态共用一把RLock；同一查询的Context/质量/高度来自同一已提交版本。
状态/结果返回拷贝，消费者修改不影响已安装地形。
Provider遇到锁竞争可返回busy；ROS服务另有非阻塞单请求槽，覆盖解码后审计、业务和编码整个处理段。
busy响应只用不可变实例/请求信息，revision=0、evaluation不可用且无载荷，不无锁读取当前版本。

## 2. 运行门控与失败恢复

沿方案顺序：语法非法→服务invalid_request；外域→request_domain_mismatch；
disabled/reset/clock不可用/断流→明确unavailable；当前注册失效→registration_unavailable；
未来请求→query_ahead_of_clock；pin实例/revision不符→明确拒绝；
未安装/激活前→unavailable；合法中心才调用私有查询；非中心服务错误。
当前evaluation或请求时间到eligibility结束则stale，注册结束始终不给历史高程。
no-data/覆盖外保留各自缺失形态，过期不补零，不向占据或free转换。

原私有query允许离线未来边界检查的行为不变，live限制只在Provider新增。
本轮实际验证0/负高度、缺失贡献、旧采集时间/安装时间保留、版本冲突/退役拒绝和坏新版保持旧版。
安装尝试计数独立，失败时旧版仍有效可CURRENT，同时last_install_outcome=REJECTED；到期后仍EXPIRED。
公开原因只用稳定代码candidate_rejected等，不复制异常或输入全文。
注册/几何/身份改变或第65个新身份会锁定，要求新实例；未知安装内部异常也锁定并抛错，不输出可能不一致的旧版。
reset后同实例不能解锁，实际ROS恢复用新run/新UUID；同revision=1不能延续旧pin。

## 3. ROS装配与clock来源

[terrain_fixture.launch](../ros_ws/launch/terrain_fixture.launch)默认enabled=false，整个node group不启动。
显式enabled=true时必须同时给出dataset（公共JSON路径）、run_id、clock_id、clock_publisher（绝对节点名）。
路径由mapping按≤16KiB读取，source_ref仅证据标签；不解析私有YAML猜格式，不读取source_ref文件。
launch不包含在任何旧入口中；只有显式启用组设置use_sim_time=true。
坏配置在注册业务服务前失败，没有远程安装端点、动态文件监视或自动fallback。

| 接口/参数 | 实际值 |
| --- | --- |
| 查询服务 | /uav/terrain/v1/query，TerrainQuery |
| 状态 | /uav/terrain/v1/status，TerrainStatus，queue_size=1、latched |
| 唯一订阅 | /clock，Clock，queue_size=1；rospy内部模拟时钟订阅也属于同一基础设施话题 |
| 心跳 | 墙钟循环，目标周期0.5s；不用随模拟时间暂停的rospy.Timer |
| clock接收期限 | 单调时间1s，超时移除当前载荷；重复sim值可维持传输，但不刷新安装或证据 |
| 来源审计 | 每次心跳/服务核对master图只有指定一个clock发布者；回调同时核对连接callerid及≤1s图审计新鲜度 |
| XML-RPC | 使用既有1s超时的rpc_proxy；图查询失败则来源不可用 |
| 服务业务容量 | 1，忙时明确terrain_busy；不代表TCP连接数/ROS接收内存有界 |

Clock没有run/clock标识，域绑定来自显式装配配置；节点核对发布者图与连接来源，不能证明真实设备时钟映射。
这是ROS身份一致性检查，不是恶意节点环境中的认证。异步图变化与回调之间存在观察窗口，
每次服务重新审计；不能声称在任意瞬间可原子观察master和消息到达。
图/连接异常恢复后必须新收到受认可clock；外来较小时间不会触发本实例采用该时间。
真正受认可源的clock回退则保持锁定，后续增长不解除。
节点停止注销本服务/订阅/状态，旧占据服务继续；客户端如何清除旧latched显示仍由SW-03验收。

## 4. 复现与实际证据

构建仅使用隔离.runtime/ros和指定Python，命令见实验记录。
已验证的短时独立ROS验收入口：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/m5_provider_run.py
```

runner在空闲端口11681创建新master、地形node和未修改的旧占据node，测试observer显式作为唯一认可clock源。
生成的公共dataset绑定本次唯一run；输出全在新.runtime/runs/m5-provider-*目录，不覆盖旧目录。
observer控制暂停、异常发布者、到期/reset；监督器负责停止旧地形实例、启动新run和最终清理。
它是验收fixture入口，不是常驻飞行/真实DEM服务，不会启动模型/GPU或训练。
若端口已被使用，明确失败并保留既有进程，可显式传入--port选择其他端口。

实际ROS通过28次查询、15条状态收据、38项检查；旧占据1次快照、revision/概率/时间保持。
地形服务关闭后旧占据继续可查；新run恢复revision=1且实例不同，旧pin及旧域拒绝。
默认关闭launch经实际--nodes检查无地形节点；ROS图只有clock订阅，无监督/定位/TF旁路。
没有强制终止，所有被监督进程退出0、端口释放；详细产物与轻量回归见实验记录。

## 5. 范围与下一步

本轮没有修改旧私有候选、公共字段、旧包依赖或原启动/可视化入口；恢复为停用新launch，保留全部产物。
公共查询的忙碌与并发原子性由离线线程/包装测试验证，实际ROS只验证正常/错误/恢复服务，
没有用真实网络压测证明busy并发连接资源或调用期限。
最多64身份/16样本、输出/副本限额属于软件逻辑预算；未测RSS/机载性能/正式PERF-01。
下一项M5-IFACE-SW-03是独立客户端、公共录制/执行回放和可选RViz地形显示，
含阻塞/断流/迟到/重启/批查询版本组合；真实DEM、占据融合、模型质量和完整M5/Phase 4仍未关闭。

后续10-29 SW-03已完成[独立客户端/公共执行回放/RViz地形](M5_IFACE_SW03_DELIVERY_20261029.md)，
上文尚未实施措辞保留SW-02时点。Provider增加默认空recording_directory的可选串行记录包装，
无录制路径保持原行为，旧消息/默认入口不变；实际记录及v1完整性边界见SW-03说明。
