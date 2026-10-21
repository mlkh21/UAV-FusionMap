# EXP-20260920-004：线格式成本、旁路订阅与整链资源对照

日期：2026-09-20；主责任：Technical Lead。
状态：成本归因、三拓扑对照、基础资源采样和单候选复测已完成；候选未达采纳条件，
20ms目标未达到，PERF-01保持进行中。

## 授权与边界

依据用户“按你说的做”，本轮落实真实ROS序列化/反序列化测量、不订阅大图的观察器
对照、整链基础资源采样，以及一个有证据的优化候选。仍使用静止paired 20Hz、
640×512×32FC1、单Radar点和占位感知；20ms目标、原业务时间和未知质量语义保持。
不启动40分钟SIM-01D、35/50/70m/s场景、训练或外部归档。

分支`feature/engineering-initialization`，在原未提交代码上增量实施，未自动提交。
解释器经正式入口核对为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，
沿用环境已有psutil 7.1.3与NumPy，没有安装依赖或修改系统ROS/Conda文件。

## 实际测量方法

`--wire-profile`启用原20个分段，同时在进程内包装生成消息的实际serialize/deserialize。
探针在真实publish及TCPROS接收调用中触发，记录单调start/end、线程CPU时间、线格式
字节数和身份；不以再次离线序列化的微基准代替真实调用。节点将小型记录存入内存，
正常停止时排他写入sensor-wire.json、perception-wire.json、observer-wire.json。
数据不含图像副本或新哈希，探针不修改生成文件、ROS系统包或业务消息字段。

每个已接受bundle连续分解为：

```text
publish入口 -> serialize开始 -> serialize结束
           -> deserialize开始 -> deserialize结束 -> 感知回调入口
```

中间serialize结束至deserialize开始仍是入队、数据复制、传输与调度的混合项。
deserialize结束至回调包含接收框架工作、对象管理和探针记录，不当作纯网络或纯调度。
逐样本各段求和必须等于原bundle发送至回调时长；独立P99不相加。
线程CPU与墙钟使用各自时钟做区间差，不将两种绝对时间相减；计时调用与记录本身仍有开销。

传输身份、序列、时间、run/clock、图像尺寸/数量、字节数以及分段完整性均须闭合。
消息采集时间和坐标合同保持；ROI、像素压缩、图像尺寸、队列深度和CPU亲和性均未修改。

## 三种观察拓扑

| 模式 | 观察器IR订阅 | 观察器bundle订阅 | 像素遍历 | 业务感知bundle订阅 |
| --- | --- | --- | --- | --- |
| full | 有 | 有 | IR/bundle各一次完整min/max | 有 |
| light | 有 | 有 | 无 | 有 |
| metadata | 无 | 无 | 无 | 有 |

metadata强制要求wire-profile，不能关闭生产/消费身份检查。所有模式都保持低载荷
state/radar/occupancy/map与原有事件订阅，地图revision/observed/丢帧检查保留。
缺失、重复、乱序、错误clock、意外订阅数量及缺失审计文件均令功能验收失败。

当前独立IR话题只有观察器一个订阅者。Noetic的`rospy/topics.py`在无连接时跳过序列化，
因此metadata模式虽然仍调用IR publish，但没有独立IR线格式发送或接收。
该模式仅声明独立IR发布尝试可核查；实际IR载荷随bundle到感知端，由两端记录核对。
full/light要求IR连接1、bundle连接2；metadata要求IR连接0、bundle连接1。
这项试验量化包含额外序列化/传输/反序列化在内的旁路订阅成本，不是只关像素扫描。

## 资源采样的自检与修订

已有采样器仅覆盖observer；新增`--sample-resources`以0.5秒间隔采集本次runner及其
子进程，包含source、sensor、perception、mapping、observer和ROS基础设施的CPU/RSS、
上下文切换，另记录主机负载及可读取的频率。CPU百分比100代表一个逻辑核；RSS最大值
是采样点最大值，不冒充连续高水位。正式汇总限定在首个生成事件至最后地图事件之间，
各业务角色至少两个样本；原始resources.json保留包含启动阶段的记录。

第一版同时遍历整机频率和温度。冒烟发现采样墙钟P50约53ms、P99约70ms；独立只读
探针分解一次调用为全CPU频率20.17ms、温度30.25ms，单CPU频率0.119ms。
已保留第一版完整九run探索矩阵：
[manifest](../.runtime/runs/perf01a-compare-20260920T154730546757/manifest.json)、
[结果](../.runtime/runs/perf01a-compare-20260920T154730546757/comparison.json)。
它们功能通过，但不混入修订后的正式统计，也不据此选择优化。

第二版只周期读取亲和性允许范围内四个代表CPU的频率，温度只在启动业务前采集一次。
不修改频率/温控/亲和性。频率仅是主机诊断，不能绑定为每个节点执行时的真实频率，
没有完整温度趋势、GPU/NPU利用率或功耗验收。所有正式组使用同一第二版采样器。

第二版正式run的采样循环墙钟P99仍在12.120—62.326ms之间，不能称为零干扰。
收尾增加线程CPU计时（版本2.1，仅增加计时字段），再独立做两个5秒自检：
[full](../.runtime/runs/perf01a-20260920T160048459491/perf-report.json)、
[metadata](../.runtime/runs/perf01a-20260920T160056346478/perf-report.json)。
各10个活动窗口采样点，采样墙钟P50/P99为7.067/20.079ms、9.738/12.399ms；
线程CPU P50/P99为7.061/16.330ms、8.997/11.703ms。采样存在实际CPU成本及等待，
不将墙钟耗时全归因于线程抢占，也不倒填到旧run。两run仅作采样自检，不并入正式对照。

## 正式拓扑对照

每run10秒任务、200样本；顺序full/light/metadata、light/metadata/full、
metadata/full/light。无预热排除或离群样本剔除，分位数采用nearest-rank。
预登记[manifest](../.runtime/runs/perf01a-compare-20260920T155046395207/manifest.json)、
[结果](../.runtime/runs/perf01a-compare-20260920T155046395207/comparison.json)。

| 重复 | full P99 ms | light P99 ms | metadata P99 ms |
| --- | ---: | ---: | ---: |
| 1 | 33.257 | 30.953 | 26.225 |
| 2 | 33.571 | 30.779 | 26.874 |
| 3 | 32.850 | 33.582 | 27.746 |

九run均200/200、5000个PerfEvent闭合且资源角色覆盖完整，进程/端口清理通过。
三组metadata均低于相邻full/light，但仍超过20ms，且已改变旁路订阅拓扑，不能宣称
保持完整观察负载后已完成业务优化。差值包括取消独立IR序列化及额外bundle接收等成本。

各模式600样本汇总：

| 模式 | 感知P50/P95/P99 ms | 地图P50/P95/P99 ms |
| --- | --- | --- |
| full | 22.038 / 28.591 / 33.257 | 23.445 / 30.194 / 34.997 |
| light | 22.692 / 29.403 / 31.377 | 24.076 / 31.183 / 33.276 |
| metadata | 20.330 / 25.203 / 27.546 | 21.837 / 26.736 / 29.491 |

实际bundle线格式分解，单位ms，每格为P50/P95/P99，各600样本：

| 连续区间 | full | light | metadata |
| --- | --- | --- | --- |
| publish至serialize | 0.008 / 0.012 / 0.014 | 0.009 / 0.012 / 0.015 | 0.014 / 0.019 / 0.025 |
| serialize | 4.603 / 6.775 / 7.655 | 4.757 / 6.863 / 7.674 | 6.761 / 7.618 / 8.108 |
| serialize后至deserialize前 | 2.111 / 3.549 / 4.475 | 2.077 / 3.412 / 4.329 | 2.637 / 3.536 / 3.929 |
| deserialize | 2.981 / 5.134 / 6.920 | 3.021 / 5.186 / 6.831 | 4.438 / 6.926 / 7.969 |
| deserialize后至回调 | 1.547 / 2.324 / 2.628 | 1.520 / 2.408 / 2.660 | 1.909 / 2.645 / 2.826 |

full独立IR serialize墙钟P50/P95/P99=6.627/8.075/8.860ms，线程CPU为
6.487/7.897/8.697ms；bundle serialize线程CPU=4.452/6.552/7.366ms，
感知deserialize线程CPU=2.983/5.136/6.924ms。可确认编解码包含明显的实际CPU计算成本，
不能把原19ms混合区间整体叫网络瓶颈。线程CPU区间含计时调用边界开销，可能略大于墙钟区间。

metadata的部分编解码分位数反而更高，故不能把组间端到端差值精确拆成每项旁路成本。
主机四个代表CPU频率范围约799.5—5609.8MHz，load1约0.68—1.43；未固定CPU频率，
也未将节点绑定到所采样CPU。不能由这些诊断直接认定节点变慢是降频造成。

活动窗口资源，CPU百分比为每run各采样区间P50的范围，RSS为三run中最大采样值：

| 角色 | full CPU% / RSS MiB | light CPU% / RSS MiB | metadata CPU% / RSS MiB |
| --- | --- | --- | --- |
| observer（含采样器） | 47.03—47.50 / 113.50 | 31.30—32.11 / 112.97 | 5.91—7.79 / 58.07 |
| source | 1.98—3.83 / 45.11 | 3.89—3.91 / 45.24 | 3.90—3.91 / 45.29 |
| sensor | 35.35—36.73 / 89.24 | 35.21—37.29 / 91.41 | 25.53—27.35 / 80.07 |
| perception | 15.44—15.64 / 76.14 | 13.82—15.74 / 76.79 | 19.52—19.59 / 77.21 |
| mapping | 1.93—1.96 / 45.03 | 1.95—1.96 / 45.22 | 1.95—1.96 / 44.98 |

记录包括本次master/roslaunch/rosout等子进程，表仅列五个核心角色。资源不是目标Jetson
平台测量。三run不能当作600次独立试验，不声称统计显著；关闭额外订阅后的改善有重复
证据，但尚未排除原事件、轻量审计、资源采样和主机调度的剩余影响。

## 单个优化候选

线格式探针证实bundle编解码有数毫秒实际线程CPU开销。在最大消息承载区间中，仅试调
感知接收端的解码：调用现有生成代码deserialize_numpy，再将数组恢复成既有Python
list/float容器后进入业务层。发送端、观察器、ROS线格式和消息合同保持。
候选通过`--receive-backend numpy`显式选择，标准方式为`standard`。
NumPy生成代码的此候选只验证小端主机；非小端显式拒绝，不假定字节序相同。

前置验证包括非恒定像素、完整640×512图、空质量数组的线格式逐字节往返及业务字典
一致性；2秒full观察实际ROS候选冒烟40/40通过，
[结果](../.runtime/runs/perf01a-20260920T155451084820/perf-report.json)。

正式比较保持full完整观察和第二版资源采样，standard/numpy、numpy/standard、
standard/numpy各10秒。测试前登记采纳条件：全部功能检查通过，至少三对重复，
每对端到端P99均下降且下降比例中位数至少10%。这是本次工程筛选规则，不是统计显著性
声明；20ms目标另外保留，失败结果不剔除。

正式候选预登记[manifest](../.runtime/runs/perf01a-compare-20260920T155536256988/manifest.json)、
[结果](../.runtime/runs/perf01a-compare-20260920T155536256988/comparison.json)：

| 重复 | standard感知P99 ms | numpy感知P99 ms | 降幅 |
| --- | ---: | ---: | ---: |
| 1 | 31.007 | 30.988 | 0.061% |
| 2 | 32.081 | 29.483 | 8.096% |
| 3 | 32.091 | 31.786 | 0.950% |

六run均200/200、5000事件、完整像素与两端审计通过，资源覆盖及清理通过。
端到端降幅中位数0.950%，低于预登记10%，`candidate_decision.accepted=false`。
每种方式600样本汇总感知P99=32.063/31.131ms；实际deserialize P50/P95/P99为
standard 2.951/5.211/6.893ms、numpy 2.588/5.001/6.626ms。转换回原Python容器后，
局部收益有限，不能依据只测NumPy frombuffer的速度宣称整链改善。
决定保留standard默认，numpy仅保留为可复现候选。六run全部20ms诊断失败。

## 验证与复现

```bash
bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_*.py' -q
bash ros_ws/sim01_env.sh python ros_ws/perf01a_compare.py --duration-s 10 --pairs 3 --modes full light metadata --wire-profile --sample-resources --port 11630 --label wire-topology
bash ros_ws/sim01_env.sh python ros_ws/perf01a_compare.py --duration-s 10 --pairs 3 --modes full --receive-backends standard numpy --wire-profile --sample-resources --port 11660 --label receive-numpy-candidate
```

当前代码采样器为2.1，较正式记录版本2仅多采样线程CPU字段；上述复现会新建目录并
在报告标注实际采样版本，不能把新run写成旧版本的精确重放。端口须空闲，矩阵串行执行。
manifest保存顺序、实际命令、平台、解释器与候选门槛；run保存预算/场景、events、
receipts、三份wire审计、resources、perf-report和节点日志。可用wire.samples逐样本
重算连续线格式分解，代码检查器`perf01a_wire_report.py`只读取输入，不写旧产物。

验证结果：全仓141/141单元/契约通过；收尾增加采样CPU字段后7/7定向测试通过。
覆盖线格式逐字节一致、Python类型保持、缺失/重复/错clock/字节数/订阅拓扑拒绝、
采样CPU口径、候选收益门槛及既有同步/地图契约。

实际ROS回归：

- [metadata + sync_timeout](../.runtime/runs/perf01a-20260920T155856786762/perf-report.json)：40源、30地图、10拒绝、850事件。
- [metadata + ir_missing](../.runtime/runs/perf01a-20260920T155901680247/perf-report.json)：40源、30地图、10拒绝、820事件。
- [metadata + pose_stale](../.runtime/runs/perf01a-20260920T155906629571/perf-report.json)：40源、30地图、10拒绝、850事件。
- [full + numpy + 5ms边界](../.runtime/runs/perf01a-20260920T155911572447/perf-report.json)：40/40地图、1000事件，原IR时间偏移保留。
- [默认small入口](../.runtime/runs/perf01a-20260920T155916456750/perf-report.json)：40/40、原五事件共200条，默认full/standard且不开新探针。

三故障的drop_rate仍0.25，unexpected_missing_maps=0，精确拒绝后恢复；metadata观察器
IR/bundle接收数为0是预登记拓扑，实际bundle交付从sensor/perception文件核对，不能用
删除两路检查掩盖丢帧。所有本次run均无强杀、无本次进程组残留且master端口关闭。

本轮总计33个ROS run：九个第一版采样探索、九个正式拓扑对照、六个正式候选对照、
两个2秒冒烟（首个见[metadata冒烟](../.runtime/runs/perf01a-20260920T154625895300/perf-report.json)）、
五个回归、两个5秒采样自检。首次沙箱命令因socket权限失败、尚未创建run；随后所有ROS
命令通过沙箱外执行许可运行。15个正式run均未达20ms，未剔除任何失败诊断。
收尾只读重读33个run的报告与原始记录，重新执行线格式身份/数量核查及逐样本区间
求和，全部通过；7份涉及文档的145处本地链接和`git diff --check`通过。
宿主机按本轮采样记录中的234组PID/创建时间核对，存活匹配数为0；未发送额外信号。

## 修改清单与后续

- `ros_ws/src/uav_fusionmap_msgs/src/ufm_ros_contract/perf01a_wire.py`：进程内实际编解码探针和两端记录。
- `ros_ws/src/uav_fusionmap_msgs/src/ufm_ros_contract/perf01a_numpy_receive.py`：可选接收端候选，恢复原Python容器。
- `ros_ws/src/uav_fusionmap_sensors/scripts/perf01a_sensor_node.py`：生产审计和按拓扑等待连接就绪。
- `ros_ws/src/uav_fusionmap_perception/scripts/perf01a_placeholder_node.py`：接收审计、回调身份及可选解码。
- `ros_ws/perf01a_wire_report.py`：独立核查发布/消费数量和身份，逐样本线格式分解。
- `ros_ws/perf01a_resources.py`：本次进程树及主机诊断，活动窗口汇总与采样自检。
- `ros_ws/perf01a_run.py`：新模式/开关、收尾核查、失败路径保留原始记录。
- `ros_ws/perf01a_compare.py`：多拓扑轮换与单候选AB/BA，测试前登记并执行筛选条件。
- `tests/test_perf01a_wire.py`：7项新增定向测试。
- `docs/DATA_FORMAT.md`、`docs/SENSOR_INTERFACE.md`、`docs/DECISION_LOG.md`、`docs/PERF01_BUDGET.md`、`docs/EXPERIMENT_LOG.md`、`PROJECT_STATUS.md`与本文：契约边界、证据和状态。

默认full/standard、64KiB读块且不开wire-profile/sample-resources，保留原入口行为。
所有新增探针与候选可由CLI关闭，无需修改系统包或删除结果来恢复默认路径。
本轮交付测量与候选处置，不把短时fixture通过写成机载实时通过。后续可推进独立
Radar/IR时序与有界匹配缓存，沿用本轮审计及基础资源采样；真实时间误差、GPU/NPU/功耗
与机载平台仍待验证。20ms失败继续保留，SIM-01D的40分钟验收和外部归档边界不变。
