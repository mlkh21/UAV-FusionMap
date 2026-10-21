# EXP-20260923-003：异步状态排空与双时钟拒绝理由诊断

日期：2026-09-23；责任：integration_engineer；分支：`feature/engineering-initialization`
（工作区有未提交改动）。本记录绑定当前源码和独立run的`scenario.json`，不是冻结提交。

## 问题和门禁

EXP-20260923-002的70m/s大图`deadline`中，source发送221条状态、最后真实
`/clock`为2200ms，matcher接收221条状态但clock只覆盖到2180ms，仅发布219条。
runner原先只等Radar/IR收据便下达`finish`。修正后的短run在`finish`前按源审计
等待状态已接收/已发布数量均等于source实际状态数、状态门控pending=0、matcher
最后**真实收到**的clock不早于source最后clock，且run_id一致。超时仍失败，
不伪造clock、不推进仿真时间、不放宽位姿、配对或性能门限。

原预登记oracle基于理想1x仿真时间，IR缓存还受500ms单调墙钟限制。
新增的`oracle_reason_diagnostic`只对收据、真实decision clock和墙钟时刻核算
理由差异：若旧IR在决策时墙钟未过期，但按理想1x时刻本应过期且与Radar采样
相差超过5ms，分类为`wall_clock_carryover`。分类不是验收豁免，
`matching decisions differ from preregistered oracle`仍使整run失败；
状态排空及诊断都不把拒绝改为采用。

## 真实ROS短run

使用`bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
ros_ws/perf01a_async_run.py`加下表参数，全部2秒、seed=17、独立本机端口，
产物位于`.runtime/runs/perf01a-async-<后缀>/`，已有失败run不重写。

| 后缀 / 端口 | 参数 | 结果 |
| --- | --- | --- |
| `20260923T164144847640` / 12021 | `--scenario normal --speed-mps 70 --pairing-policy deadline --full-ir --wire-profile --duration-s 2` | **失败保留**：初次状态参数含`None`，XML-RPC拒绝；节点强制清理已在报告披露 |
| `20260923T164327403366` / 12022 | 同上 | **失败保留**：纳秒整数超XML-RPC 32位界限；状态参数后改为十进制字符串 |
| `20260923T164445527249` / 12023 | 同上 | 功能通过：2200ms真实clock、221接收/221发布、pending=0；感知P99=81.030ms，20ms失败 |
| `20260923T164514378192` / 12024 | `--scenario recovery --speed-mps 70 --pairing-policy exact --full-ir --wire-profile --duration-s 2` | **严格oracle失败保留**：状态排空221/221且clock覆盖2200ms；Radar19预期`infrared_unavailable`，实际`radar_ir_timeout`，诊断为IR24墙钟仍存活；感知P99=32.230ms，20ms失败 |
| `20260923T164704599052` / 12025 | `--scenario normal --speed-mps 35 --pairing-policy exact --duration-s 2` | 小图无wire探针功能通过；不代表大图通过 |

修正后3个run的本次master/节点退出清理和端口关闭检查通过；初次失败run
记录`nodes`被强制终止，第二次失败run虽正常清理仍为失败，均保留。
初次沙箱试跑在创建回环socket时被拒；正式短run经权限审批执行。
`test_*.py`全仓198项通过，含双时钟分类的反例和真实clock覆盖/状态发布
双条件回归。没有执行长时间、机载资源、PX4高速状态或SIM-01D持续性验证。

下一步须确定是否把这种有明确墙钟证据的拒绝理由差异纳入**新的**预登记
双时钟验收规则；未经确认仍保持当前严格失败。需要多轮大图负载重复与
目标平台测量，20ms指标未通过，5ms同步门限未调整。
