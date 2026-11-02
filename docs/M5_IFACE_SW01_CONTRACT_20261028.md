# M5-IFACE-SW-01：公共地形消息与离线合同

日期：2026-10-28；主责任：integration_engineer；状态：已完成（消息/合同离线范围）。
依据：[已确认具体方案](M5_IFACE_DESIGN_20261028.md)、ADR-040。
验证与产物：[EXP-20261028-012](../experiments/2026-10-28-m5-interface-contract.md)。

## 1. 实现与边界

新增独立包[uav_fusionmap_terrain_msgs](../ros_ws/src/uav_fusionmap_terrain_msgs/package.xml)，
仅依赖catkin/message_generation/message_runtime，生成TerrainHeightQuality、TerrainContext、
TerrainQueryResult、TerrainStatus及TerrainQuery。字段、顺序、单位与枚举以.msg/.srv和
[方案§3](M5_IFACE_DESIGN_20261028.md#3-类型与字段提案)为准，protocol_version固定1。
旧消息、服务、包依赖、工厂与启动入口不变；不新增Provider、ROS节点、客户端或显示。

公开逻辑合同放在新包的`ufm_terrain_contract`，而非尚未实现的terrain_provider.py；
可由未来相邻生产者/消费者共同导入，导入不加载rospy、mapping实现、GIS或模型。
mapping内的dataset适配与recording校验仅用于离线结构检查，不执行安装或回放。

| 入口 | 实际职责 |
| --- | --- |
| [contract.py](../ros_ws/src/uav_fusionmap_terrain_msgs/src/ufm_terrain_contract/contract.py) | validate_quality/context/request/result/status；逻辑对象严格字段、字符串枚举与None缺失，不修改输入 |
| [codec.py](../ros_ws/src/uav_fusionmap_terrain_msgs/src/ufm_terrain_contract/codec.py) | to_ros/from_ros(name,value)、serialize/deserialize(name,bytes)；服务封套to_ros_response/from_ros_response |
| [bounds.py](../ros_ws/src/uav_fusionmap_terrain_msgs/src/ufm_terrain_contract/bounds.py) | 有界UTF-8/JSON、重复key/非有限/结构深度拒绝；read_json先限字节后解码 |
| [terrain_dataset.py](../mapping/ufm_mapping/terrain_dataset.py) | validate/load_dataset、公开/私有包装双向拷贝及dataset_context元数据投影 |
| [terrain_recording_contract.py](../mapping/ufm_mapping/terrain_recording_contract.py) | validate/load_recording；三文件结构、引用/序号/提交版本及完整性检查，无录制器或执行回放 |

codec的name为生成类型短名，例如`TerrainQueryRequest`、`TerrainQueryResult`。
from_ros/deserialize结果可传入`request=...`与`provider_instance_id=...`校验回显、pin及已绑定实例；
仅有响应本身无法证明它来自期望提供者，未来客户端必须显式传入绑定。
来自本地传输失败的无实例unavailable封套属于SW-03，不伪造为本轮的真实服务响应。

## 2. 数值、缺失与时间

逻辑evaluation_timestamp/context/height/source_index/source_xy为None时，线格式flag=false，
槽位必须为规范零值；空Context包括所有空字符串、零定长数组、空变长数组和空质量。
质量UNAVAILABLE对应value=None，线上必须[0,0]且kind/unit为空，source可保存缺失标签。
0/负高度可用，源样本、注册tz和map结果区间分别校验，禁止把概率、方差或平移区间冒充点高度界。

VALID要求完整Context、索引/源中心和高度；no-data与覆盖外的缺失形态分别校验。
STALE允许缺失高度；UNAVAILABLE禁止保留缓存Context或高度。
完整质量要求样本与注册两个贡献均可用；任一缺失，结果质量必须缺失。
结果绝对区间必须包含名义高度和两个贡献区间端点的精确十进制和，不允许向内舍入。

int64纳秒不经float转换；uint64实例内revision/状态序号/安装尝试另计。
Context核对源/目标基准、非零固定平移、整格注册、安装/授权区间和源dataset时钟。
已有可用结果校验evaluation、请求时间、注册及授权边界的一致性；这属于静态响应校验，
没有实现实际时钟接收、未来请求门控、reset状态机、串行化安装或原子服务查询。
外域请求可通过语法检查，Provider后续须按设计返回无Context的unavailable，不能在语法层擅自改域。

## 3. 公共dataset

schema_version=`ufm.terrain.dataset.v1`、profile=`m5_fixture_v1`。
其余必需组为identity/source_time/horizontal/vertical/grid/map_grid/registration/eligibility/limits，
各组严格沿用[SW-01完整字段](M5_SW01_CONTRACT_20261028.md#2-冻结编码与单位)。
不含私有fixture_only/enabled_by_default，全部额外字段拒绝；适配只替换包装并构造私有固定标志。
保留数字int/float编码、样本、掩码、质量、来源与时间；不解析source_ref或读取其中引用路径。
dataset_context只投影公开元数据，不返回高度数组、不创建TerrainFixture或安装版本。

单个dataset规范UTF-8 JSON≤16KiB，1tile/每轴≤4/总样本≤16；直接对象同样检查编码大小。
旧私有候选的规范编码/安装限额继续独立执行，不因公开包装通过而豁免后续私有安装检查。
LiDAR/target/observed_mask等额外字段在所有正式输入组均拒绝；拒绝用例的原始attempt只允许保存在未提交记录中。

## 4. recording结构

目录只含manifest.json、datasets.json、events.jsonl；这三个文件是公开离线合同，不能冒充占据回放或私有事件协议。

| 组成 | 严格字段 |
| --- | --- |
| manifest | schema_version=`ufm.terrain.recording.v1`、profile、recording_id、provider_instance_id、run_id、clock_id、mode=`recorded`、event_count、recording_complete、limits |
| limits | max_datasets=64、max_events=64、max_dataset_bytes=16384、max_record_bytes=65536、max_recording_bytes=4194304 |
| datasets数组项 | dataset_ref为唯一uint64、dataset为结构化公开对象；不是嵌入字符串 |
| 所有event | event_sequence从0连续、record_elapsed_ns非递减、operation、run_timestamp_available及run_timestamp（false时0） |
| clock_observed | 无额外字段，运行时间必须可用 |
| clock_transport | online为严格bool；运行时间与相对记录时间分别保留 |
| install | attempt_id、dataset_ref、attempt、input_recorded、input_reason、outcome、reason、revision_before、revision_after |
| query | request、result；结果evaluation与event运行时间一致，回显/pin/实例绑定校验 |
| disable | reason、status；状态必须disabled，原因一致 |
| status_change | status；状态序号可跳跃但递增，与最后安装尝试/提交revision和Context一致 |

install的attempt_id从1连续，outcome为installed/idempotent/rejected。
input_recorded=true时dataset_ref和attempt恰有一项非None；已接受输入必须引用dataset表，
原始attempt仅供rejected事件保留有界坏输入，不加入已提交表。
input_recorded=false时两项均None、input_reason必需，manifest必须incomplete。
严格读取默认拒绝incomplete；require_complete=False仅供检查不完整诊断，不代表可严格重放。
成功提交revision加1，幂等/拒绝保持；查询/状态携带的Context必须对应已记录提交的dataset和安装时间。
这些检查核对记录自身的结构和声称，不重新执行Provider、证明安装结果真实性或替代SW-03逐事件重放。

事件每条≤64KiB（不含JSONL末尾换行），≤64事件/64dataset，总未压缩目录≤4MiB。
读取实际文件大小并限制每次read/readline后再JSON解码；缺文件、额外文件、重复key、缺尾换行、
非有限、缺引用、序号跳跃、未知版本和超限整次拒绝，不截断或反造缺失输入。

## 5. 有界性、验证与恢复

每字符串UTF-8≤16KiB，reason稳定代码≤128字节；规范逻辑请求JSON及ROS请求分别≤16KiB，
逻辑结果/状态JSON及ROS载荷分别≤64KiB。两种编码独立检查，控制字符转义不能绕过JSON预算。
JSON预检查容器/节点/深度（≤16）及文本，再增量编码；ROS对象先检查标量/数组、枚举与缺失槽，再计算字节。
deserialize入口先拒绝过大的原始bytes，真实genpy解码后逐项校验；额外尾字节或非规范bool字节拒绝。
from_ros入口面对的是已反序列化对象，不能撤销ROS接收缓冲或genpy此前分配；本轮不提供网络接收资源保证。
以上是逻辑/编码限额，不是RSS、线程/连接资源或正式PERF-01验收。

独立预期先保存于[JSON](../tests/fixtures/m5_iface_expectations.json)，
[手工线格式布局/struct编码](../tests/m5_iface_fixture.py)不导入生产codec。
随后通过真实生成类型的serialize/deserialize与独立字节逐项比较；没有mock替代消息线格式。
复现构建和完整验证命令见实验记录；runner每次创建独立.runtime/runs/m5-iface-sw01-*目录。

恢复无需撤销旧改动：继续使用旧入口，停止显式导入新合同即可；保留新源码/生成物/验证目录，
不删除历史产物或重置工作区。下一项M5-IFACE-SW-02才实施Provider、独立节点/clock、pin、状态与真实服务验证；
SW-03实施客户端/录制与回放执行/RViz地形显示。真实DEM、占据融合与正式M5/Phase 4继续独立验收。

后续用户“继续”后，SW-02已完成[Provider/独立ROS与拒绝恢复](M5_IFACE_SW02_PROVIDER_20261028.md)，
上文“尚未实现”保留SW-01时点；本轮冻结类型/字段和记录结构保持，客户端与公共执行回放仍待SW-03。
