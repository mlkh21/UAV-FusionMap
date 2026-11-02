# 原生RViz地图工作台

日期：2026-10-28；主责任：integration_engineer；任务：APP-VIS-01。
状态：报告软件版本已完成；目标交付日期2026-10-30前，实际于10-28验证。

10-29追加独立[地形公共接口/RViz说明](M5_IFACE_SW03_DELIVERY_20261029.md)与
[地形报告截图图注](../experiments/report_assets/terrain-20261029/README.md)。
地形live/recorded Marker是可选新入口，原占据工作台与场景/Radar/IR入口保持；不表示DEM占据融合。
10-29后续[P5-SW-03分窗验收与软件矩阵交接](P5_SW03_NATIVE_DELIVERY_20261029.md)已完成，
[新报告图片](../experiments/report_assets/p5-delivery-20261029/README.md)保留场景与地形各自基准，不作未注册叠图。
统一[交付清单](SOFTWARE_DELIVERY_20261029.md)和[含图报告正文](REPORT_20261029.md)提供复现与阶段边界总览。

## 启动

在仓库根目录执行，窗口关闭后监督器清理本次创建的进程：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/report_rviz_run.py
```

默认demo启动独立11701端口master、既有M4 mapping节点、明确标识的合成占据生产者及
原生RViz窗口。示例障碍物通过OccupancyObservation进入M4，不是直接往界面画一张假地图。
示例不运行Radar–IR研究模型、训练、LiDAR或DEM。它是地图/界面报告场景，不能称为
真实传感器或PX4实飞数据；旧Radar/IR placeholder链另有live接入运行证据。
默认display=:0；不同桌面可显式传`--display`与`--xauthority`。
端口占用时指定其他`--port`，不会停止已有master。需要定时退出可传`--duration-s 30`。

依赖使用本机已有Noetic RViz/Ogre/Qt、编译器及标准ROS消息；不安装大型依赖。
所有Python进程仍使用指定Conda解释器。RViz由系统Qt 5.12构建，而Conda Qt/TIFF不同，
启动器仅对GUI子进程选择系统PyQt/TIFF，GUI配置/缓存/HOME隔离到新run的gui-home。
小型C++读回库每run编译到运行目录，编译命令/日志记录在manifest和capture-build.log；
该库只调用RViz公开渲染接口，不修改ROS、系统库或原Conda环境。
此环境适配只验证本机组合，换机须先检查对应RViz/Qt ABI。
报告入口默认`--render-backend software`，仅在GUI子进程显式设置Mesa/llvmpipe软件渲染
（2个渲染线程），实际OpenGL日志已核对，不自动fallback。它仍是原生RViz/Ogre渲染。
`--render-backend system`保留系统显卡路径；该路径曾出现一次初始化SIGSEGV，根因未定位，
不作为推荐报告入口或稳定性已验收结论。默认软件渲染的demo/独立回放/live均已通过。

## 界面功能

- 原生RViz鼠标旋转/缩放、三维与XY俯视、复位视角；标准工具条可选Publish Point。
- 五类单元图层、覆盖边界及完整计数；灰色网格和未列出区域均不是自由证据。
- 地图map_id、frame、revision、分辨率与纳秒时间。完整run/clock可悬停查看，导出保留原值。
- XYZ地图坐标单点查询；Publish Point点击只在frame匹配时调用同一公开MapQuery。
- 暂停显示、滑块定位、上一/下一帧；live恢复直接回到最新已接收快照，不阻塞地图更新。
- PNG截图、单独viewport PNG、JSON来源记录及公开快照导出。输出在新run的figures中，
  不覆盖旧图片。截图直接读回本窗口与Ogre目标，避免桌面遮挡内容混入。

实时接收使用最新值队列，历史最多120个已采样快照，每个最多20000个cell；这是界面边界，
不是无损rosbag或地图资源预算。历史回放按快照自身的证据时刻显示，不重建私有目录或
Scene结构时间，也不向当前MapQuery服务发送历史请求。公开质量原样保留在导出收据中。

显示TTL与阈值必须显式匹配地图配置；它们只决定视图颜色，查询以地图服务为准。
未配置阈值的保留单元显示unknown，未知/失效/无观测不变成free。恰TTL仍新鲜、超TTL为stale，
保留原概率/质量/证据时间；时钟缺失/倒退/错域或3s墙钟断流时只保留灰色历史，当前视图不可用。
墙钟3s仅为界面连接状态，不替换设备同步、模型deadline或PERF-01预算。
查询最多一个后台请求；2s界面等待超时后拒绝迟到响应，不声称取消了底层调用。
单点结果对应请求中的query_timestamp，完整响应及来源随截图保留，不能当作持续有效的规划结论。

## 只读接入已有ROS图

已有地图服务、公开快照与同域/具名clock时，可显式连接：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/report_rviz_run.py --mode live --master-uri http://127.0.0.1:11311 --clock-id sim:YOUR_RUN --ttl-ns 100000000
```

把master/clock/TTL替换为该运行的实际值。上面的URI仅为参数示例，不表示本机11311
当前存在可用图；已验证的实际legacy live命令/运行见[实验记录](../experiments/2026-10-28-rviz-report-delivery.md)。
仅当地图确实使用该分类对时才另加`--free-threshold 0.3 --occupied-threshold 0.7`；
不要为让界面“有占据颜色”而替未配置的旧入口补阈值。
live不创建master、fixture、感知或mapping，不改变现有地图参数，关闭只停止本次GUI进程。
缺master/clock/TTL时参数检查失败，不fallback到demo。

| 接口 | 生产者 → 消费者 | 类型/语义 |
| --- | --- | --- |
| /uav/map/snapshot | 既有mapping → 界面适配 | 既有MapSnapshot，完整公开网格/来源/时间 |
| /uav/map/query | 既有mapping服务 → 界面客户端 | 既有MapQuery，地图坐标与run/clock显式 |
| /clock | 当前运行时钟 → 界面/原生RViz | 标准Clock，仅基础设施，不猜设备域 |
| /uav/report/markers | 界面适配 → RViz显示 | 标准MarkerArray，固定状态组每次全量替换，隐藏组发送空点集 |
| /uav/report/clicked_point | RViz工具 → 界面查询输入 | 标准PointStamped，错frame拒绝，无控制命令 |

不新增公共业务消息或修改SensorBundle/OccupancyObservation字段。application不订阅
Radar/IR、AircraftState、LiDAR或模型张量，不读取地图私有目录。RViz内部TF订阅属于
标准渲染基础设施，本版图元和Fixed Frame同源，不利用TF补造map←odom注册。
当前验证支持单个轴对齐公开网格，几何中心严格为origin+(index+0.5)*resolution。
可视间距使用0.92倍分辨率，未改变业务网格。注册与概率累计仍由mapping负责。

## 公开快照回放

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/report_rviz_run.py --mode replay --receipt .runtime/runs/report-rviz-20261028T150952745186/scene-receipts.json --ttl-ns 100000000 --free-threshold 0.3 --occupied-threshold 0.7 --port 11702
```

接受含1—120条公开snapshots的JSON（含界面导出的收据）；不需要研究仓库、checkpoint或
原地图进程。混map/run/clock/frame、非递增revision、倒退证据时间、无效几何/数值或
越限文件拒绝。默认停在第一帧，“继续回放”开始播放；历史服务查询始终关闭。
该命令使用新的独立master，只为RViz承载Marker，不恢复原ROS图或模型。

## 验收与报告素材

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/report_rviz_run.py --exercise --port 11701
```

验收会控制本次fixture时钟、停止本次mapping，验证五类查询、过期与断流；不对已有
live图执行故障注入。额外检查真实Ogre像素、1560×980/1100×780布局、Python与清理。
已通过实际demo、独立回放及旧链live接入，全仓638项通过。
报告主图和中文图注见[素材目录](../experiments/report_assets/rviz-20261028/README.md)，
完整范围、失败修正与原始收据见[EXP-20261028-005](../experiments/2026-10-28-rviz-report-delivery.md)。
