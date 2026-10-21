# EXP-20260923-001：高速运动时空一致性基线

日期：2026-09-23；主责任：integration_engineer；类型：Conda契约回归与短时实际ROS
功能级fixture。分支：`feature/engineering-initialization`，有未提交改动；此记录
绑定本工作区当前源码及各run的排他写入`scenario.json`，不是冻结提交版本。

## 目的、配置与边界

按Radar/IR独立20/50Hz、状态100Hz、clock 1ms，以35/50/70m/s直线速度校验位置、
采样时刻Radar相对观测、历史位姿变换、概率占位格子、拒绝后的老化与恢复。输入为
`configs/perf01a_async.yaml`，seed=17，5ms同步阈值、10ms位姿年龄上限、40ms截止及
500ms墙钟上限保持。`world_ned`北向状态适配到`odom`北向，Radar以fixture单位外参
逆投影两个不随飞机移动的ENU世界点；雷达Doppler无模拟，标记不可用。

每run启动独立Noetic master/source/Radar/IR/matcher/perception/mapping；Python解释器
`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`。所有run均为2秒采样窗口加
200ms排空，端口11981至11991各自独立。实际调用格式：

```text
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01a_async_run.py --scenario normal --speed-mps 35 \
  --pairing-policy exact --duration-s 2 --port 11981
```

其余调用更换`--scenario`、`--speed-mps`、`--pairing-policy`及端口；大图另加
`--full-ir`（640×512），所有完整配置、预登记oracle、原收据、clock、资源、节点
退出及结果保存在下表独立目录。小图为2×2，固定地图分辨率0.5m，地图非移动窗口。
测试是功能级已知真值场景，不是PX4/JSBSim实际高速飞行或研究模型精度验收。

## 实际结果

下表目录均相对`.runtime/runs/`，`功能`是整run严格oracle和地图闭合；20ms列为
Radar实际回调至占据P99，属于独立性能诊断。新run结果不覆盖任何历史结果。

| 目录后缀 | 输入 | 功能 | 有效/拒绝 | 最大连续世界误差 | P99/20ms |
| --- | --- | --- | --- | --- | --- |
| `20260923T152844611000` | 35，normal，小图，exact | 通过 | 20/20 | 约0m | 4.032ms/通过 |
| `20260923T153108464398` | 50，pose_offset，小图，exact | **失败并保留** | 20/20 | 0.250000m | 42.830ms/失败 |
| `20260923T153344591051` | 50，pose_offset，小图，exact | 通过 | 20/20 | 0.250000m | 43.149ms/失败 |
| `20260923T153429476002` | 70，recovery，小图，exact | 通过 | 12/28 | 小于0.000008m | 6.791ms/通过 |
| `20260923T153523035339` | 70，out_of_order，小图，exact | 通过 | 15/25 | 小于0.000008m | 4.881ms/通过 |
| `20260923T153630844015` | 35，normal，小图，deadline | 通过 | 20/20 | 小于0.000001m | 56.853ms/失败 |
| `20260923T153730648574` | 70，normal，大图，exact | 通过 | 20/20 | 小于0.000008m | 69.328ms/失败 |
| `20260923T153845822987` | 70，recovery，大图，exact | **失败并保留** | 12/28 | 小于0.000008m | 39.354ms/失败 |
| `20260923T154305235754` | 70，pose_offset，小图，exact | 通过 | 20/20 | 0.350001m | 43.691ms/失败 |
| `20260923T154346410315` | 70，recovery，小图，exact | 通过 | 12/28 | 小于0.000008m | 10.127ms/通过 |
| `20260923T155338525860` | 35，normal，小图，exact，速度收据回归 | 通过 | 20/20 | 小于0.000001m | 4.323ms/通过 |

上表完整目录前缀为`perf01a-async-`。全部run退出码和`perf-report.json`记录了本次
master/节点正常退出、未强制终止及端口关闭；单次小图或大图成功不构成稳定性矩阵。
最终全仓`test_*.py`契约回归194项通过，包括改写测量点/速度/地图格子时独立oracle失败，
同刻提前匹配、迟到拒绝和10ms位姿门控。35/50/70运动状态的位置随采样时间变化，
每档速度保持对应的恒定非零值；最后一轮ROS收据也核对了`SensorBundle.state.linear_velocity`，位姿变换保留实际
NED/FRD到ENU/FLU旋转，不在测试里覆盖为单位姿态。

首次50m/s pose_offset的世界点恰落在0.5m格网边界：连续坐标误差符合0.25m预算，
但浮点旋转扰动导致某帧地图分入相邻格，严格oracle失败。保留该run；新run将世界点
从4.25/6.25m挪至4.32/6.32m，独立检查同一时间和误差预算，功能通过。这说明在
网格边界附近不能把连续坐标误差达标推断成同一体素，仍需确定性边界归属策略。

70m/s大图recovery的Radar19预期`infrared_unavailable`，实际`radar_ir_timeout`；
有效/拒绝数量相同，但理由与理想1x oracle不符，**整run失败**。未调整5ms门限或
重写报告。该run的实际地图老化审计单独通过，不会抵消配对失败。故障期clock
查询出现stale，恢复期新样本让格子重新新鲜；拒绝输入没有增加map revision或产生
free。老化是节点内`stale_cells`查询审计，不是已实现公开地图查询服务。

## PERF-01等待与承载

`exact`只在同刻IR与同刻状态均被收到时提前决定；50/70m/s的5ms位姿偏差不能
提前，因此仍等40ms。35m/s小图normal同口径单次对照`deadline`/`exact`的
感知P99为56.853/4.032ms；该对照不是多次统计收益证明。即使提前配对，70m/s
大图normal的P99=69.328ms，继续违反20ms目标。

大图normal的逐样本连续分段P99：匹配等待及构建51.322ms，bundle发布起至感知
回调16.464ms（含承载/排队/反序列化，不是纯网络），bundle回调内业务decode
1.270ms。IR接收端回调内decode P99=1.380ms，取锁等待1.900ms，缓存处理/发布
3.004ms；大图recovery对应1.346/2.289/11.433ms。独立分位数不能相加。
ROS进入Python回调前的IR反序列化和队列等待未单独量化，属于后续承载定位工作；
不能据此宣称已经定位到唯一瓶颈或达到机载算力目标。

## 未覆盖与下一步

保持原失败矩阵6/7与10/14结果，详情见[历史补充](2026-09-22-perf01a-async.md)。
当前仍无物理雷达FOV/量程、转弯/扫描去畸变、插值/外推、研究模型质量或PX4高速
状态输入证据；SIM-01D的40分钟持续性、机载GPU/NPU/功耗、公开地图查询和完整
PERF-01高速实时验收均独立进行中。下阶段先针对格网边界制定容差/量化合同，重复
大图配对和分段测量，再评估ROS接收前反序列化/队列与大图内存复制成本。

2026-09-23后续勘误：本段为EXP-20260923-001运行时的下一步；后续
[EXP-20260923-002](2026-09-23-perf01a-boundary-wire.md)明确按实际收到的历史
变换连续坐标量化，并单独检查世界误差。原格网边界失败报告保留，但不能据此
断言当时地图的实际变换坐标索引错误；新的原边界短run功能通过。大图recovery
拒绝理由仍失败，未因此放宽oracle或20ms门槛。
