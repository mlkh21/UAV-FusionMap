# EXP-20261008-003：零噪声IR生成候选与三航速复测

- 日期：2026-10-08；主责任：sensor_engineer；状态：候选功能闭合通过，20ms开发机诊断失败。
- 关联失败基线：[EXP-20261008-002](2026-10-08-perf01a-three-speed-fixture.md)；
  三档640×512 IR在1倍仿真时钟下40 Radar全部严格拒绝，不得替换其产物或结论。

## 假设与变更边界

基线35m/s的IR首帧在Radar首帧被拒之后才publish；同刻IR到匹配器时/clock
为86ms，超出40ms等待窗口。当前`make_fake_infrared`即使`noise_std=0.0`，
仍对640×512每个像素执行一次`rng.gauss(0.0, 0.0)`；同一Conda环境三次单帧
计时约104.137/105.293/103.332ms。这是**本机fixture生成**的诊断，
不是物理IR采集成本，也不是端到端P99。

候选仅在已校验`noise_std == 0.0`时跳过没有数值作用的逐像素随机采样；
非零噪声、热点、随机种子、header、曝光中点、image全像素、ROS消息及
Radar/IR频率、1ms clock、5ms同步、40ms匹配截止、10ms pose、0.5s墙钟
上限和20ms诊断目标均保持原值。不引入替代模型、硬件主张或训练监督LiDAR。
先用随机采样调用计数RED/GREEN、无噪声热点像素与有噪声重复性单测确认语义，
再运行全仓轻量回归；发现像素/身份变化则不做ROS短测。

## 实际ROS预登记

沿用`normal --full-ir --duration-s 2 --pairing-policy exact --endpoint-probe`，
各航速单独端口，按35、50、70m/s顺序串行；35失败仍执行50/70以登记结果。
仅添加业务内部的零噪声优化，不更改runner/profile/oracle/launch或观察订阅数。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01a_async_run.py --scenario normal --full-ir --duration-s 2 \
  --speed-mps 35 --pairing-policy exact --endpoint-probe --port 12148
# 50m/s使用端口12149；70m/s使用端口12150，其余参数相同。
```

预期每档Radar计划40、IR计划100，实际传输完整、20采用及20按原理由拒绝，
Bundle/占据/地图20对严格身份闭合，clock/state排空、资源角色/清理通过。
分别记录每条run的`passed/errors`、收据、拒绝理由、IR生成到publish的
墙钟分位数、IR接收clock、相同Radar回调到占据P99；P99若>20ms仍如实标
为开发机诊断不达标，空P99即无可验收的延迟样本。不能合并不同run的分位数，
更不能用fixture改善推断机载PERF-01已通过。未取得平台/设备采样时钟/外部功耗，
正式预算门禁继续`reference_only`。

## 实际结果

执行前实际检查12148—12150无监听；独立授权后在沙箱外运行，每个run均为
Conda `Radar-Diffusion`解释器。新增的零噪声随机采样断言先RED（仍调用
`_sample_rng`）、后GREEN；现有非零噪声重复性及全仓245项轻量测试通过。
同机单帧生成3次约0.564/0.598/0.596ms；该微测与前文的约103—105ms
仅供同机fixture瓶颈定位，不是正式时延基准。

| 航速、端口与run目录（`.runtime/runs/`下） | 实际闭合/拒绝、收据/清理 | IR生成→publish P99 | Radar回调→占据P99 |
| --- | --- | --- | --- |
| 35m/s,12148,`perf01a-async-20261008T152707296388` | `passed=true`；40 Radar/100 IR实际收据，20 Bundle/占据/地图；20采用、20 `radar_ir_timeout`，严格oracle通过；资源角色完整、无采样错误、0意外传输丢失、端口与进程组清理通过 | 1.294100 ms（100帧，最近秩） | 49.703038 ms，20ms诊断失败 |
| 50m/s,12149,`perf01a-async-20261008T152739486564` | 同上，20采用/20严格拒绝；清理通过 | 1.114595 ms | 49.834441 ms，20ms诊断失败 |
| 70m/s,12150,`perf01a-async-20261008T152805518052` | 同上，20采用/20严格拒绝；清理通过 | 1.992740 ms | 60.719994 ms，20ms诊断失败 |

各run的`scenario.json`、`infrared-audit.json`、`matcher-audit.json`、
`perf-report.json`、`resources.json`均留在表中对应原始目录；每条时钟
收据为2201个，0—2.2秒覆盖，完整状态/时钟排空与地图oracle由run报告核账。
35m/s首个IR在匹配器收到时`/clock=6ms`，旧失败目录中同刻IR为86ms；
此对照只说明0噪声fixture生成开销的影响，不能将不同run的分位数合并、
推断IR物理驱动性能，或抹掉旧失败结果。所有run的设备采样时钟仍标记
`capture_clock_status=unavailable`；没有真实Radar/IR、机载平台、跨时钟映射
或外部功耗。功能级闭合不是PERF-01通过，严格拒绝理由、5ms同步和20ms目标
均未放宽，正式预算门禁仍`reference_only`。

逐帧只读检查：35m/s最慢Radar序号34的49.703038ms由同帧
`pairing_wait_and_build=37.332904ms`及`bundle_send_to_callback=10.877919ms`
等组成；50m/s最慢序号20的49.834441ms中配对等待36.776859ms、
发送到回调11.519048ms。70m/s最慢序号34的60.719994ms中，
配对等待16.452449ms、`ready_to_encode=29.963558ms`、发送到回调
12.942690ms；编码本身仅0.546255ms。`ready_to_encode`是两个时间
事件之间的墙钟间隔，不能单独称为CPU或网络耗时。下个候选需对同帧
匹配输入、worker调度和ROS发送/回调分别取证，不以不同样本阶段P99
相加归因，也不未经实验改变40ms匹配截止或严格拒绝理由。
