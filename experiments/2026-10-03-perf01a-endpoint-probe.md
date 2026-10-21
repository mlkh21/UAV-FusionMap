# EXP-20261003-001：PERF-01端点与时钟桥接探针实测

日期：2026-10-03；主责任：integration_engineer；状态：诊断完成，性能验收未通过，未登记A/B。
预登记：[端点与时钟桥接探针预登记](2026-10-03-perf01a-endpoint-probe-prereg.md)。

## 1. 实际执行

在预登记的独立目录、同一Conda解释器和同一负载下串行执行三条2秒短测：

```text
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01a_async_run.py --scenario normal --speed-mps 70 \
  --pairing-policy exact --full-ir --wire-profile --match-trace \
  --endpoint-probe --duration-s 2 --port 12065
```

后两条仅将端口顺序改为12066、12067；每条独立新run，不覆盖历史产物。
第一次在受限沙箱内的端口探测被系统拒绝，未进入运行逻辑；按环境权限重新执行后
三条均完成。运行前端口/进程检查通过，结束后无残留PERF-01-A进程。

产物目录：

- `.runtime/runs/perf01a-async-20261003T144232132400/`
- `.runtime/runs/perf01a-async-20261003T144532639898/`
- `.runtime/runs/perf01a-async-20261003T144823326052/`

## 2. 门禁结果

| run尾号 | 严格功能 | 采用/拒绝 | wire/状态-clock/地图 | 资源/清理 | Radar回调到占据P99 |
| --- | --- | ---: | --- | --- | ---: |
| 144232 | 通过 | 20/20 | 通过 | 通过 | 58.745 ms |
| 144532 | 通过 | 20/20 | 通过 | 通过 | 78.635 ms |
| 144823 | 通过 | 20/20 | 通过 | 通过 | 53.507 ms |

三条报告均为`passed=true`、`errors=[]`、端点探针开启；20ms诊断三次均失败。
严格拒绝理由、5ms同步、40ms决定截止、身份和排空门禁均未改变。

## 3. 同一样本端点结果

下表为同一Radar根身份的独立分位数；不将不同端点或不同run的P99相加。

| run尾号 | 占据就绪P99 | occupancy publish调用P99 | occupancy回调入口P99 | map update结束P99 | MapSnapshot事件P99 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 144232 | 58.745 ms | 58.975 ms | 59.176 ms | 59.315 ms | 59.450 ms |
| 144532 | 78.635 ms | 78.724 ms | 79.664 ms | 79.794 ms | 80.008 ms |
| 144823 | 53.507 ms | 53.642 ms | 55.110 ms | 55.269 ms | 55.510 ms |

从占据就绪到下游端点的增量P99分别为：

- run 144232：publish调用0.245 ms、occupancy回调1.769 ms、地图更新1.927 ms、快照2.085 ms；
- run 144532：publish调用3.215 ms、occupancy回调3.125 ms、地图更新3.216 ms、快照3.314 ms；
- run 144823：publish调用0.346 ms、occupancy回调1.874 ms、地图更新1.959 ms、快照2.049 ms。

因此，将感知端点从`occupancy_ready`延伸到下游消费或地图事件，不能解释当前
约53.5--78.6ms的主长尾；地图端点也不能替代感知20ms目标。

## 4. 输入时钟和长尾归因

三条run的Radar和IR生产审计中，所有已发布样本均为
`capture_clock_status=unavailable`、`capture_monotonic_ns=null`、
`capture_timestamp_ns=null`。当前fixture没有设备曝光/采样时钟，故本轮没有生成
物理设备采样到回调的数据年龄，不把fixture业务timestamp或生成时刻冒充采样点。

最慢三个同根样本的互斥段显示来源不一致：

| run/样本 | 主要区间 | 证据含义 |
| --- | --- | --- |
| 144232/30 | 配对到Bundle约39.758ms；Bundle发送到感知回调约16.473ms | 决定前混合等待和下游线/队列区间同时偏大 |
| 144532/32 | 配对到Bundle约55.589ms；Bundle发送到感知回调约19.916ms | 以决定前混合等待为主 |
| 144532/20 | Bundle发送到感知回调约39.534ms | 与同run样本32的原因不同 |
| 144823/4 | Bundle发送到感知回调约33.405ms | 下游混合区间长尾 |
| 144823/38 | 配对到Bundle约35.303ms | 决定前混合等待长尾 |
| 144823/22 | 配对到Bundle约15.518ms，ready到编码约18.118ms | 存在未被单一stage覆盖的决定后间隔 |

`decision.emit`在三条run均有局部较长样本，但没有在三条run各自最慢三个样本中
都达到预登记的`>=10ms`墙钟且`>=10ms`线程CPU条件；`bundle.publish`也不满足。
`pairing_wait_and_build`虽在多条run出现，但它是由多个输入回调、状态/clock、锁和
调度组成的互斥混合区间，不是单一可逆优化点。因此本轮不登记单点A/B。

## 5. 判定和后续

1. 新端点探针有效：能够在同根样本上区分占据就绪、occupancy消费和地图事件；
   下游端点不是当前主长尾来源。
2. 时钟桥接仍缺失：开发fixture不能回答机载物理数据年龄；Technical Lead仍需
   确认真实设备采样点、跨设备时钟映射和20ms正式验收起止点。
3. 长尾仍由不同样本中的决定前混合等待、Bundle线/队列混合区间和未覆盖间隔组成；
   没有重复且可控的单一stage，暂不改matcher、不做A/B。

严格拒绝理由、5ms同步门限、20ms目标、SIM-01D 40分钟持续性、目标机资源/功耗和
研究模型质量均保持原验收边界，分别处理。

验证：108项PERF-01-A轻量回归通过；新增端点统计回归通过；三条实测run严格门禁
通过但20ms诊断失败；三份原始报告、审计和wire产物保留。未执行真实设备时钟标定、
机载资源测量或性能A/B。
