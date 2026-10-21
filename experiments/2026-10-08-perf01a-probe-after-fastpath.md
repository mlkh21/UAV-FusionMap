# EXP-20261008-005：大图闭合后的同帧等待/线格式探针

- 日期：2026-10-08；主责任：integration_engineer；状态：探针run与只读同帧联接通过，20ms诊断失败。
- 基线：[EXP-20261008-003](2026-10-08-perf01a-zero-noise-candidate.md)中
  70m/s无额外探针的20个闭合样本，回调到占据P99为60.719994ms；
  最慢序号34的`ready_to_encode=29.963558ms`尚无CPU/调度归因。

沿用零噪声fast path和`normal`场景、640×512 IR、2秒、70m/s、`exact`，
只增加现有可选的matcher阶段/锁探针与ROS线格式探针，保留端点探针。
不修改消息、时钟、采样频率、5ms同步、40ms匹配、10ms姿态年龄、
观察订阅数、20ms目标和预登记oracle。探针可能改变调度与耗时，不能把
本run分位数同无探针run当作同口径A/B；若严格oracle因探针成本失败，
完整保留失败产物，离线分段分析只在通过身份/线格式前置时执行。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01a_async_run.py --scenario normal --full-ir --duration-s 2 \
  --speed-mps 70 --pairing-policy exact --endpoint-probe \
  --match-trace --wire-profile --port 12151
# 仅当报告严格通过时，对此run只读执行：
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01a_critical_path.py --match-trace --top 3 <本次run绝对路径>
```

预期仍是40 Radar/100 IR实际收据、20采用/20严格拒绝、地图/身份/
clock排空与清理通过。记录run目录、实际返回码、匹配/传输错误及探针
给出的同帧等待归因；不把探针运行、fake数据或合成指标作为正式PERF-01
性能/设备采样时钟证据，原配置仍`reference_only`。

## 实际结果

预检端口12151未被监听；独立授权后执行上述实际ROS命令，run目录：
`.runtime/runs/perf01a-async-20261008T153825310225/`。返回码0，
`perf-report.json`的`passed=true/errors=[]`；40 Radar/100 IR实际收据，
20采用/20 `radar_ir_timeout`，20个Bundle/占据/地图完成身份与oracle核账。
资源角色齐全、无采样错误、`wire.errors=[]`，唯一时钟覆盖0—2.2s；
进程组/端口清理通过。设备采样时钟依旧`unavailable`。

随后运行预登记的只读`perf01a_critical_path.py --match-trace --top 3`
成功；同一次插桩run中Radar回调→占据P99为44.871696ms（20个有效样本），
仍超20ms。最慢Radar序号36同帧：IR回调比Radar回调晚17.593624ms；
IR自身序列化6.184084ms、序列化结束→反序列化开始的队列/传输/调度
混合区间11.617851ms、IR反序列化6.830434ms；Radar到配对决定
27.446786ms，最后必需输入到位→worker锁约1.189355ms；Bundle序列化
5.416900ms、反序列化5.915234ms。各区间可能嵌套，不可直接求和或从
不同帧P99拼接总延迟。最慢序号36在本run的`ready_to_encode=0.073273ms`，
因此无探针run序号34所见约29.96ms长尾**未在该次探针run重现**，
不能以本run确定其CPU/调度根因。下一步优先以同帧身份测量真实IR接收
时序、Bundle线格式和调度长尾，再预登记单一候选，不放宽同步/拒绝理由。

探针影响负载，44.871696ms和无探针60.719994ms不是受控A/B；
通过只代表本机fixture功能与这组自洽计时，缺目标机/设备时间/外部功率证据，
正式PERF-01仍阻塞。失败和成功run均只追加新目录，旧目录未修改。
