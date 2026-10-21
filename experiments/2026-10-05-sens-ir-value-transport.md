# EXP-20261005-001：同帧 IR 热点/背景数值守恒真实 ROS 短测

- 日期：2026-10-05；任务：SENS-IR-01；主责任角色：sensor_engineer。
- 类型：纯 Python 负例契约测试 + 实际 ROS 功能级短测，不是实机 IR、热物理或机载性能验收。
- 代码基线：`feature/engineering-initialization`，HEAD `4bd0c33`；工作区已有大量未提交文件，
  本项修改在同一工作区上增量进行，未覆盖已有结果/配置。Python 和 ROS 节点均使用
  `/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，Noetic 由 `sim01_env.sh` 隔离加载。

## 问题与预期

10-04 的 [热点短测](2026-10-04-fake-ir-hotspots.md)只证明传感器→Bundle→占位感知→地图
链路闭合：观察器验证 IR 采样时间、尺寸和像素数量，却不采集发布图像，也不比较 Bundle 内
同帧像素。预期从 `/uav/sensors/infrared` 独立订阅原始消息，按 `sample_id` 对齐
`/uav/sensors/bundle` 内每次采用的 IR；核对 run/clock/frame 身份、采样/曝光时间、
编码/单位、**所有**像素的传输一致性及行优先热点/背景 oracle。未匹配帧不得被伪装为
已采用帧；匹配拒绝理由、5 ms 门限、排空及清理仍使用原有严格检查。

本项仅在 `--verify-ir-values` 且专用 `ir_value_transport` 小图场景开启额外订阅和图像记录，
不修改生产消息、业务同步算法、默认性能路径或在线 Bundle 字段。配置在
[`configs/perf01a_async.yaml`](../configs/perf01a_async.yaml)：4×3、`32FC1`、
`fixture_intensity`，背景 0.4；(1,1) 半径 0 像素热点增量 0.5，故中心行优先索引 5
预期 0.9；(0,0) 索引 0 预期 0.4；IR 噪声 0，曝光 4 ms、采样时间为曝光中点；
Radar/IR 相位 2/4 ms，频率 20/50 Hz，传感器噪声 seed 23。`float32[]` 对十进制参数
比较采用绝对容差 `1e-6`；发布帧与 Bundle 同帧图像逐像素核对亦采用该容差。

## 执行与产物

```bash
# 10-04场景基线：退出0并非像素验收通过。
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01a_async_run.py --scenario parameterized_sensors --duration-s 2 --port 12445

# 专用无噪声场景：首次失败目录不覆盖，修正配置后换端口重跑。
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01a_async_run.py --scenario ir_value_transport --duration-s 2 \
  --port 12447 --verify-ir-values

bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  -m unittest discover -s tests -p 'test_*.py' -q
```

| 阶段 | 独立目录/证据 | 实际结果 |
| --- | --- | --- |
| 旧检查基线 | [旧场景本次报告](../.runtime/runs/perf01a-async-20261005T151542885742/perf-report.json)、[收据](../.runtime/runs/perf01a-async-20261005T151542885742/receipts.json) | `passed=true`、100 帧 IR 发布/接收、20 Bundle；收据只含 IR ID/时间/尺寸/像素数，没有原始发布像素；**不能**用该结果验收数值守恒 |
| 新场景首次运行（保留失败） | [失败报告](../.runtime/runs/perf01a-async-20261005T152841990757/perf-report.json)、[配置快照](../.runtime/runs/perf01a-async-20261005T152841990757/scenario.json) | `passed=false`；新场景继承了 Radar 的 `null` FOV/量程，ROS 参数 XML-RPC 拒绝序列化，节点尚未启动；后续仅补场景内有效 Radar 参数，未更改门限或历史目录 |
| 修正后真实 ROS 2 秒 | [通过报告](../.runtime/runs/perf01a-async-20261005T153338134262/perf-report.json)、[原始及 Bundle 收据](../.runtime/runs/perf01a-async-20261005T153338134262/receipts.json)、[场景快照](../.runtime/runs/perf01a-async-20261005T153338134262/scenario.json) | `passed=true`，值校验 `errors=[]`；100/100 IR 接收、20/20 Bundle 同帧比较通过、20/20 地图更新，预期拒绝 20/20、意外丢帧 0；唯一 `/clock`，清理未强杀且 master 端口关闭 |
| 负例/回归 | [`test_perf01a_ir_values.py`](../tests/test_perf01a_ir_values.py) | 6 项值级契约通过（像素、背景、身份/时间、复用和缺帧反例）；全仓 226 项轻量 Python 测试通过 |

通过 run 的首个采用帧 `fixture.infrared:perf01a-async-20261005T153338134262:0`：
IR `timestamp=4000000 ns`，曝光 `[2000000,6000000] ns`，frame=`thermal_optical`。
中心索引 5 的原始/Bundle 值均为 `0.8999999761581421`（oracle 0.9）；背景索引 0
两端均为 `0.4000000059604645`（oracle 0.4）。报告逐个记录其余 19 个采用帧的
ID、时间和两个像素；本次代码还核对所有 100 帧原始消息的尺寸、编码、曝光中点及
oracle，并在每个采用帧上核对全部 12 个像素（不是仅比较两个代表像素）。

## 结论与边界

SENS-IR-01 的独立小图功能级数值守恒门禁通过；原来的 `passed=true` 不能倒推像素验收。
本次 `sensor_to_occupancy_ns` P99 为 45.144325 ms，20 ms **诊断不通过**；额外
订阅开启时不能将该短测用于性能 A/B。PERF-01 正式计时端点/跨时钟/目标平台仍待定，
SIM-01D 的至少 40 分钟持续性完全未由本实验覆盖。fake IR 仍是
`fixture_intensity`，不代表温度、辐射或模型质量；此实验没有创建训练 LiDAR，
SENS-TRAIN-01 的独立 `target`/`observed_mask`、unknown 与在线隔离仍需另行设计验收。
