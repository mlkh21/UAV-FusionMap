# APP-VIS-01：原生RViz报告界面交付

编号：EXP-20261028-005；日期：2026-10-28；主责任：integration_engineer。
状态：已完成（报告软件版本、默认Mesa软件渲染）；期限：2026-10-30周五之前。
用户本轮明确要求用于报告的ROS可视化，并在澄清中指定必须RViz；因此本轮优先交付
该界面，M5-DESIGN-01保留为后续计划，不开展DEM或研究模型质量任务。

## 原有能力与审计

先读取根/涉及目录规则、PROJECT_STATUS、架构、公开地图/查询及坐标约定，检查Git
状态/忽略规则。仍在feature/engineering-initialization，保留全部既有未提交修改，
未提交或推送。代码只在UAV-FusionMap内新增/更新，不改同级研究仓库或原Conda环境。

原来已有M1—M4合成地图与MapSnapshot/MapQuery、application查询客户端和真实ROS交接；
没有可用于报告的RViz布局、交互界面和截图导出。沿真实消费者确认application仅能
消费公开地图/查询，不能为了展示越层读取原始Radar/IR、状态或地图私有目录。
本机已有Noetic RViz/Ogre/Qt及标准visualization_msgs，没有安装大型依赖。

## 本轮实现与文件

| 文件/符号 | 变化及用途 |
| --- | --- |
| [visualization.SnapshotView/load_recording](../application/ufm_application/visualization.py) | 公开快照的几何/数值/域校验、显式TTL/阈值显示、五类单元、有限历史回放；不融合地图 |
| [report_rviz.ReportWindow](../ros_ws/report_rviz.py) | 原生RViz VisualizationFrame和Qt侧栏；订阅公开snapshot/clock、MapQuery与点击交互、图层/视角/回放/导出 |
| [report_rviz_run.main](../ros_ws/report_rviz_run.py) | demo/live/replay显式模式、新run、独立端口/进程、GUI库/配置隔离、解释器/像素与清理审计 |
| [rviz_capture.cpp](../ros_ws/rviz_capture.cpp) | 仅调用RViz/Ogre公开渲染目标写出PNG，避免窗口遮挡混入桌面内容 |
| [report_rviz.rviz](../configs/report_rviz.rviz) | 固定map初始视图、米制网格、标准MarkerArray及Publish Point工具；每帧Fixed Frame取公开地图声明 |
| [report_scene_fixture.py](../tests/report_scene_fixture.py) | 明确合成障碍物/显式自由及冲突输入，经公开OccupancyObservation→既有M4节点→MapSnapshot生成演示，不直接构造界面地图 |
| [check_rviz_figures.py](../tests/check_rviz_figures.py) | 实际Ogre像素、窗口/viewport边界、来源与状态颜色检查 |
| [check_report_live.py](../tests/check_report_live.py) | 原有Radar/IR→placeholder→Local Map链的实际live接入、域/阈值语义及不启动额外业务图检查 |
| [test_snapshot_visualization.py](../tests/test_snapshot_visualization.py) | 7项几何/TTL边界/未知/失效/数值/回放域隔离检查 |
| [test_report_rviz_cli.py](../tests/test_report_rviz_cli.py) | 2项缺live前提、混模式参数拒绝；错误不自动回退demo |

配套更新：README、PROJECT_STATUS、DEVELOPMENT_PLAN、STAGE_ADVANCE_PLAN、
SYSTEM_ARCHITECTURE、SENSOR_INTERFACE、RUNTIME_CONFIGURATION、DECISION_LOG、
EXPERIMENT_LOG、新增[使用说明](../docs/ROS_VISUALIZATION.md)、本记录及
[报告主图/中文图注](report_assets/rviz-20261028/README.md)。
不修改SensorBundle、OccupancyObservation、MapSnapshot或MapQuery字段，不改地图算法。
新增显示通道只用标准MarkerArray/PointStamped，不是新的业务schema或控制指令。

## 已验证运行

所有Python/ROS命令均通过`bash ros_ws/sim01_env.sh`，解释器为
`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，实际进程审计通过。
Qt绑定选择本机系统5.12.8；GUI专属HOME/缓存/配置在新run，系统Qt/TIFF选择只在GUI进程。
默认render_backend=software，实际日志确认llvmpipe（LLVM 12.0.0）、OpenGL 3.1；
没有研究模型、checkpoint、训练或CUDA推理，图形渲染不作为PERF-01证据。

实际主要命令：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/report_rviz_run.py --exercise --port 11701
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/report_rviz_run.py --mode replay --receipt .runtime/runs/report-rviz-20261028T150952745186/scene-receipts.json --ttl-ns 100000000 --free-threshold 0.3 --occupied-threshold 0.7 --exercise --port 11702
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/check_report_live.py
```

| 运行 | 结果与原始证据 |
| --- | --- |
| 默认software demo | [report-rviz-20261028T150952745186](../.runtime/runs/report-rviz-20261028T150952745186/manifest.json)：5次公开观测/5快照，1352个保留cell；472 occupied/870 free/10 unknown；三维/XY、图层切换、暂停/步进/定位和导出通过 |
| 默认software独立回放 | [report-rviz-20261028T151642059788](../.runtime/runs/report-rviz-20261028T151642059788/manifest.json)：只读保存的5个公开快照，无原mapping/研究进程；播放、定位、截图、重新导出通过，当前服务查询关闭 |
| 默认software live | [report-live-20261028T151727234327](../.runtime/runs/report-live-20261028T151727234327/manifest.json)：原source/sensors/placeholder/map链收到32帧界面采样；保留odom/run/clock，未配置分类阈值保持unknown；[GUI子run](../.runtime/runs/report-rviz-20261028T151727657361/manifest.json)只启动界面，无新master或fixture |

demo的5条观测依次为occupied障碍物、显式free地面、occupied新区域、同区域free冲突、
某历史occupied单元追加missing质量贡献；输入和快照保存于
[scene-receipts.json](../.runtime/runs/report-rviz-20261028T150952745186/scene-receipts.json)。
没有LiDAR、target或observed_mask输入；自由区域来自明确标识的合成逆观测，不是由无点推断。
1352只是本场景单元数，不能当作系统探测范围、地图质量或资源预算。

实际服务验证：

| 请求/故障 | 实际结果 |
| --- | --- |
| map点[40.25,.25,.25] | occupied，p=0.75，index=[80,32,8]，区间[0.7,0.8] |
| map点[35.25,-6.75,.25] | free，p=0.25，有明确观测 |
| map点[51.25,.25,.25] | unknown，p=0.5，reason=between_thresholds，仍为observed |
| 测试时钟推进到200000001ns | 全部1352个历史cell过期，查询stale并保留p=0.75/原时间和质量 |
| 停止本次mapping后查询 | unavailable，reason=map_query_transport_unavailable:OSError，probability=None |
| 再停止本次clock发布 | 3s连接阈值后视图unavailable，保留灰色历史，free计数0；不伪造当前概率 |

完整响应/交互检查见[ui-validation.json](../.runtime/runs/report-rviz-20261028T150952745186/figures/ui-validation.json)。
失败注入只控制本次demo，不对已有live运行执行停节点/停时钟操作。
历史帧关闭当前服务查询；暂停/恢复不回写地图，导出仅为采样公开快照，不是私有状态恢复或无损bag。

## 报告图片与像素核对

主图和俯视图为1560×980，紧凑布局为1100×780，实际检查没有窗口外viewport；
小窗口侧栏可滚动，不将文本强行覆盖视图。原生相机/图层保持可操作。
图像来自本窗口Qt部件及实际Ogre目标读回，没有读取被其他窗口遮挡的桌面内容，
每张图保留独立viewport、当前公开frame、查询、来源/时间JSON。

[像素报告](../.runtime/runs/report-rviz-20261028T150952745186/figures/pixel-validation.json)：
主图11127个占据色像素、78957个自由色像素；隐藏free的XY图自由色像素为0；
过期图105201个过期色像素；时钟失效图70224个灰色候选像素且状态计数全部unavailable。
像素检查加人工查看用于确认实际地图非空和图层生效，不是感知精度指标。

两张推荐主图已逐字节复制到[报告素材目录](report_assets/rviz-20261028/README.md)，
含可直接使用的中文图注；`cmp`核对与原图一致，未修改图像标签/地图数据，也未计算哈希。
初版系统渲染图片及原始实验仍保留，推荐报告采用默认software版本。

## 回归、清理与失败修正

新增7项纯视图和2项CLI测试通过。最终全仓命令：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

638/638通过（23.171s），[最终日志](../.runtime/rviz-lightweight-final-20261028.log)。
相对629基线新增9项，没有删除测试或放宽地图质量/时序门槛。
默认software三组ROS/GUI和外层live链均正常退出、无强杀/残留；11701/11702/11703释放，
清理见各run的cleanup-audit.json，已有master/运行未被停止。

以下失败保留，不记为通过：

- [141230初次run](../.runtime/runs/report-rviz-20261028T141230117165/manifest.json)：neutral输入不贡献证据，错误地等待新快照；改为真实occupied/free冲突得到unknown。该次GUI停止曾强制退出，进程已清理。
- [141459](../.runtime/runs/report-rviz-20261028T141459781819/manifest.json)的Qt截图API差异与[141613](../.runtime/runs/report-rviz-20261028T141613531460/manifest.json)成员引用错误已修复，后续正常关闭。
- [141759](../.runtime/runs/report-rviz-20261028T141759034247/manifest.json)交互通过但屏幕抓图可能含遮挡窗口，图像来源判无效，未用于报告；改为Ogre自身读回。首次读回[142102](../.runtime/runs/report-rviz-20261028T142102303526/manifest.json)发现Python绑定未暴露RenderPanel，改用小型C++公共接口桥接并通过像素验证。
- [143258回放](../.runtime/runs/report-rviz-20261028T143258597913/manifest.json)相对文件路径随子进程cwd改变而失效；启动器现在先解析绝对路径，缺文件明确报错，不造fixture替代。
- [144940系统渲染](../.runtime/runs/report-rviz-20261028T144940119344/manifest.json)在RViz初始化前SIGSEGV；随后两次系统回放通过，根因仍未定位，未宣称系统显卡路径稳定。报告入口显式改用现有Mesa软件渲染，demo/回放/live均通过，不自动切换后端。
- [150501软件run](../.runtime/runs/report-rviz-20261028T150501823511/manifest.json)首快照等待超时；补齐快照消费者实际连接握手，后续默认demo通过，5s逐观测等待上限未放宽。

## 未验证能力与恢复

已有地图代码和当前真实GUI运行分别有证据；本轮关闭的是10-30报告用的软件交付，
不是完整Phase 4/5或正式稳定性验收。真实Radar/IR、真实标定/设备时钟、真实map注册、
同run定位跳变识别、研究checkpoint/forward/模型质量、机载资源/功耗和正式PERF-01仍未验证。
系统显卡路径单次初始化崩溃仍为已知未解释风险，不向报告写成已修复或稳定。
报告素材有持续可见的合成fixture来源，不能称为当前4D-Radar-Diffusion的预测效果。

恢复为关闭界面；live不改变现有业务图，demo/replay只清理自己创建的进程/端口。
原Conda环境、旧launch和地图/感知算法保持；不用M4目录、模型或硬件才能打开已有公开收据。
下一步可使用[主图/图注](report_assets/rviz-20261028/README.md)提交本周报告；
没有自动发布或Git提交。之后按整体地图顺序恢复M5-DESIGN-01的具体方案，仍不直接实现DEM。
