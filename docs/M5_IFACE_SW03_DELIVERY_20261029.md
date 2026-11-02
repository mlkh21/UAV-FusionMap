# M5-IFACE-SW-03：客户端、公共回放与RViz地形交付

日期：2026-10-29；主责任：integration_engineer。
依据：[具体方案](M5_IFACE_DESIGN_20261028.md)、[SW-01合同](M5_IFACE_SW01_CONTRACT_20261028.md)、
[SW-02运行层](M5_IFACE_SW02_PROVIDER_20261028.md)。
状态：已完成（合成公共接口软件范围）；实际结果见
[EXP-20261029-001](../experiments/2026-10-29-m5-terrain-delivery.md)。

## 1. 新增生产消费链

| 入口 | 责任与输入输出 |
| --- | --- |
| [TerrainClient](../application/ufm_application/terrain_client.py) | 仅消费公开status/result；绑定terrain/run/clock、维护状态存活，按公开Context枚举≤16中心并逐点固定实例/revision |
| [TerrainQueryTransport](../ros_ws/terrain_query_transport.py) | ROS服务发现≤2s、调用≤1s墙钟；全程只保留一个未结束worker，超时与迟到结果分开处理 |
| [terrain_visualization](../application/ufm_application/terrain_visualization.py) | 只将通过校验的公开组结果转换为样本标记，历史模式只读公开回放输出 |
| [TerrainRecorder/RecordedTerrainProvider](../mapping/ufm_mapping/terrain_recording.py) | mapping层串行录制公共输入/操作/收据，写schema v1三文件；失败不改变已提交地形 |
| [replay_recording](../mapping/ufm_mapping/terrain_recording.py) | 有界读取公开记录，按顺序真正执行新Provider并比较，原输入/操作决定结果，不用expected驱动安装 |
| [terrain_rviz_node](../ros_ws/terrain_rviz_node.py) | 标准MarkerArray薄转换，live仅订阅公开地形status并查询公开服务；墙钟显示清理 |
| [terrain_recorded_view](../ros_ws/terrain_recorded_view.py) | 仅发布独立/uav/terrain/recorded/markers，标注recorded；不向live话题/服务发送历史数据 |

没有修改任何旧消息字段、地图工厂、研究后端、旧占据/场景/传感器显示入口或TF权威。
新增包只增加标准visualization_msgs运行依赖，未安装GIS或大型依赖；未执行模型或训练。
application不读公共dataset、私有DEM/spec/snapshot；dataset仍只由mapping读取。

## 2. 客户端的存活、pin与期限

客户端构造时声明terrain_id/run_id/clock_id，frame_id固定map；不自动猜测map=odom或重绑run。
单次latched status只作为候选状态：必须看到同实例status_sequence增长，或实际主动查询成功，才证明本实例响应。
状态1.5s未刷新、序号回退/重复、实例切换、revision回退或坏字段均清除当前显示组。
新实例可从revision=1开始；与旧实例同号不能混用。组内用同一个实例/revision/Context，
若中途版本、实例、状态或Context切换，整组丢弃；到期跨界不能拼成current/stale混合组。
最多16个结果，缺失高度仍保留no-data等语义，但不作为可画高度；失败不补0、不转free。

本地失败返回独立unavailable封套：provider_instance_id为空、revision=0、evaluation/context/高度均不可用。
该本地封套不经ROS发布，不冒充满足服务端实例非空合同的实际响应，也不把expected ID填成已收到ID。
有效响应继续经过SW-01严格codec和实例/回显/pin校验；没有字段/枚举修正或placeholder fallback。

传输只创建一个daemon worker：发现服务有2s期限，发现后调用再给1s墙钟期限；
忙碌时立即拒绝，不排队、不随重试新增线程。超时丢弃本次代次，迟到响应只结束原worker，不写回当前组。
底层rospy阻塞调用没有被取消；若始终不返回，保持busy/unavailable，须重启客户端恢复。
`close()`使后续结果失效，不宣称能强制终止底层线程；这不是网络连接/RSS或正式PERF-01保证。

## 3. 公共录制与执行回放

ROS Provider新增默认空的recording_directory参数；空值保持未录制路径。
非空时由mapping创建全新目录，不允许复用/覆盖既有目录；不采用source_ref作为输出位置。
正式格式仍为SW-01的manifest.json/datasets.json/events.jsonl，字段未扩展、版本仍v1。
manifest初始recording_complete=false，内容先写入同目录临时文件并替换，成功关闭才标true。
这是本机写入完整性机制，不宣称断电持久化或外部独立真实性；没有计算Hash。

clock接收、安装、查询、状态变化和停用按同一串行顺序记录。重复心跳不新增地形事件，
status_sequence可跳跃；回放重建这些省略心跳的序号（单个记录差额上限4096，超限明确失败）。
每个clock包可更新接收时间；回放使用record_elapsed_ns作为模拟单调时钟，重建1s传输失效，不使用当前墙钟猜历史。
源dataset时间、run时间和相对单调记录时间分别保留，不用文件mtime替代。
输入超限/事件满64/数据集满64/单条64KiB/总4MiB或写入失败，录制停止并保持incomplete；
已提交版本继续服务，但该记录不能通过严格回放验收。坏attempt保留有界原对象，不能塞进已接受dataset表。

回放创建独立Provider生命周期与playback_session_id，内部将原实例pin映射到该次回放实例，
对外结果保留原provider_instance_id作记录身份；错误pin不会被修正。
每条安装/查询/状态实际执行并逐值比较，篡改合法外形的expected高度也会失败。
只按公开dataset/记录事件执行，不读取私有候选状态或研究文件；回放不启动ROS服务。
输出显式mode=recorded，不作为live结果流。

v1事件的表达边界须明确：clock_transport只有online布尔值，不能无损表达clock_source_mismatch等细分来源错误；
遇到已经运行后的这类来源失败会标incomplete。无返回结果的非法query及并发busy同样标incomplete，
不伪造result或添加未经评审的隐藏字段。Provider本身仍按SW-02 fail-closed。
正常/候选拒绝、传输超时、到期、reset、停用及坏输入重放均已有离线检查；实际ROS录制覆盖正常短窗口。
因此“公共录制可用”不等于任意ROS错误都能在当前v1完整录制。

## 4. RViz与历史查看

live显示默认关闭，独立入口[terrain_rviz_fixture.launch](../ros_ws/launch/terrain_rviz_fixture.launch)。
它只订阅公开地形status（rospy可能有内部/clock订阅），不读地形输入文件、原始Radar/IR、状态或定位。
画出的每个小方片是独立中心样本，不连接成填洞曲面，不向下生成occupied体素。
绿色表示当前且质量可用，蓝色表示当前高度可用但完整质量缺失，橙色表示过期；no-data/覆盖外不画高度。
不可用、状态超时、reset、实例切换清除整组；每条MarkerArray先DELETEALL，防止少点新组遗留旧点。
墙钟显示循环独立于查询worker，查询阻塞期间仍可清空；无TF/控制发布。
图内标注live或recorded、fixture DTM和revision，不能据此声称真实融合或DEM质量。

可在已有sim01_env运行环境下显式启动：

```bash
bash ros_ws/sim01_env.sh env ROS_MASTER_URI=http://127.0.0.1:11691 /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python /opt/ros/noetic/bin/roslaunch ros_ws/launch/terrain_rviz_fixture.launch enabled:=true run_id:=本次run clock_id:=sim:本次run
```

地址与run须替换为当前Provider的值，sim01_env不继承终端ROS_MASTER_URI，必须显式传入。
不自动启动模型或更改旧场景的master。RViz载入
[configs/terrain.rviz](../configs/terrain.rviz)，Fixed Frame=map；与其他固定帧并用时需要既有坐标权威提供具名变换。

严格离线回放与独立历史显示：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/terrain_recording_replay.py --input 公开记录目录 --output 新replay.json
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/terrain_recorded_view.py --receipt 新replay.json --group 0
```

回放输出用create-only写入，历史显示只读公开replay输出并明确group；RViz将Marker Topic切到
`/uav/terrain/recorded/markers`，不能重映射为live命名空间使用。
历史结果按同版本/请求时刻/evaluation/Context分组，最多16结果；来源不明、跨实例或非recorded输出拒绝。

## 5. 验收入口与限制

已实际验证的短时入口：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/terrain_delivery_run.py --with-rviz
```

默认独立端口11691，创建新master/run和合成dataset、Provider/客户端显示与自有RViz窗口，
实际录制/回放、服务阻塞/消失、重启、过期/断流和四种渲染截图验收后正常清理。
不接真实DEM、训练或机载资源；`--port`可选其他空闲端口，既有会话保留。
功能验证使用真实genpy/服务和RViz渲染目标，故障服务仅为测试专用，不代替研究模型。

旧Gazebo场景/Radar/IR/占据/RViz入口也独立回归；这两种测试不是同run的地形与Gazebo地理注册/融合验收。
M5公共合成接口三步软件范围完成，正式M5/Phase 4、真实基准/DEM/质量、占据融合和机载性能继续未关闭。
按总体计划，下一项进入Phase 5软件组合场景与需求矩阵具体设计，保留上述外部门槛，不反复回到缺真实数据的暂缓任务。
