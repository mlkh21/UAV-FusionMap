# EXP-20261014-010：Local Map ROS单点查询服务

- 日期：2026-10-14
- 主责任角色：mapping_engineer；Technical Lead集成，tester验证
- 状态：已完成固定网格单点查询软件子范围；完整地图能力仍未完成
- 前置：EXP-20261014-009纯业务查询及326项轻量复核
- 范围：新增MapQuery服务和结果消息、既有地图节点可选包装、编解码与ROS短测

## 预登记

服务默认关闭。启用后与OccupancyObservation更新使用同一地图实例和锁，响应
保留五类状态、概率/索引/时间/质量可用性；不改变已有MapSnapshot消息。
fixture在独立Master运行，不连接PX4或硬件；明确的占位自由观测不来自Radar无点。
测试0.3/0.7阈值只供fixture；max_age为同域纳秒，不用墙钟或重发更新时间。

预期：消息/服务序列化往返保留int64时间；空地图、五类状态、未配置阈值、年龄
边界、断流/恢复、去重、错误身份/坐标、非法请求、清理和图隔离均成立。
实现与旧PERF-01-A回归分别检查。

## 实际结果

### RED/GREEN

1. 消息/服务编解码定向测试初始因缺少`query_codec`导入而RED；加入编解码后6项GREEN。
2. 节点单元测试初始允许外部run在空地图上种入首个观测而RED；加入节点`run_id`门控后4项GREEN。
3. 查询边界新增极大但有限的越界点测试，初始索引计算抛出`OverflowError`而RED；将覆盖
   判断前置后7项纯查询测试GREEN，避免合法越界请求异常退出。
4. 首次实际ROS启用模式功能检查的25项业务检查通过，但连接图断言错误地排除了ROS
   `use_sim_time`自动订阅的公共`/clock`，该失败目录保留；图规则修正为允许公共clock、
   仍拒绝所有传感器/状态/Odometry/Radar/训练LiDAR订阅后复测通过。

### 通过命令与证据

统一使用`bash ros_ws/sim01_env.sh`，Python为
`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`：

```bash
bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_*.py'
bash ros_ws/sim01_env.sh catkin_make -C .runtime/ros --source ros_ws/src --build .runtime/ros/build --force-cmake
bash ros_ws/sim01_env.sh python ros_ws/local_map_query_run.py --mode enabled --port 11451
bash ros_ws/sim01_env.sh python ros_ws/local_map_query_run.py --mode disabled --port 11452
bash ros_ws/sim01_env.sh python ros_ws/local_map_query_run.py --mode unclassified --port 11453
bash ros_ws/sim01_env.sh python ros_ws/perf01a_run.py --duration-s 2 --scenario small --port 11454
```

最新启用模式证据为`../.runtime/runs/local-map-query-enabled-20261014T155350319397/`：
30次有效查询、5条观测发布、2次快照、并发读一致、极大有限越界点、Python审计、端口
释放均通过。关闭模式为`../.runtime/runs/local-map-query-disabled-20261014T155426133491/`，
未配置阈值模式为`../.runtime/runs/local-map-query-unclassified-20261014T154647647489/`；
该首次通过目录保留；文档定稿后使用当前代码再次复核的目录为
`../.runtime/runs/local-map-query-unclassified-20261014T161853179161/`，通过且清理成功。
以上关闭与未配置阈值run均通过。旧PERF-01-A回归为
`../.runtime/runs/perf01a-20261014T154739607691/`，40/40样本闭合并通过清理；它仍是
fixture占位链路，不是正式平台性能结论。

### 范围结论

已完成：新增ROS类型与可选服务、共享地图实例/锁、五类状态和显式可用性、请求错误
边界、默认关闭兼容性、三种ROS fixture和图隔离。

未完成：滚动局部地图、概率累计、不确定性融合、区域/多点查询、自动TF转换、真实
Radar/IR输入、正式平台/设备时钟/功耗、研究模型质量、飞行和对照试验。对照试验继续
放在最后。

未执行：真实设备、物理时钟、功耗、研究模型、飞行、滚动窗口和对照试验。
