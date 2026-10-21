# EXP-20260923-002：运动格网边界与异步大图承载复核

日期：2026-09-23；主责任：integration_engineer；分支：`feature/engineering-initialization`
（有未提交改动）。本记录绑定本工作区当前源码与各run独立`scenario.json`，并非冻结提交。

## 范围和预期

仍用35/50/70m/s直线功能级fixture、5ms同步上限、10ms历史位姿年龄、40ms采样
截止、500ms墙钟缓存；地图分辨率0.5m。明确格网合同：从收到的`SensorBundle`
中的Radar点及其观测时刻携带的`T_mapping_source`算出连续odom坐标，按
`floor((x-origin)/resolution)`的半开格网索引核对占据与地图。独立核对固定障碍物
世界真值和速度乘位姿年龄的连续误差预算；靠近边界的体素可变，不能把真值点取整
后要求相同格子。不加容差去改写格子，不实施位姿插值。

可选`--wire-profile`在独立IR发布进程、matcher、感知进程的真实ROS消息方法上
审计IR/Bundle的serialize、deserialize及回调入口，以sample_id和字节数联接。
`serialized_to_deserialize`含队列、复制、传输、调度，不等同纯网络延迟；
`deserialize_to_callback`含框架及对象管理。探针有成本，本轮不与无探针历史P99
做稳定收益比较。20ms端到端诊断及严格预登记oracle不变。

## 执行和结果

Python均为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，运行使用
`bash ros_ws/sim01_env.sh <解释器> ros_ws/perf01a_async_run.py`加下表参数；
2秒窗口、seed=17、独立master/端口和全新`.runtime/runs/perf01a-async-<后缀>`目录。
小图2×2，大图640×512。每run原始schedule、expected、producer/matcher审计、
IR/sensor/perception线格式、收据/地图老化、资源及perf-report均原样保留。

| 后缀 / 端口 | 附加参数 | 严格功能 | 占据P99 / 20ms |
| --- | --- | --- | --- |
| `20260923T161428893347` / 12011 | `--scenario normal --speed-mps 50 --pairing-policy exact --wire-profile` | 通过，20采用/20拒绝 | 7.155ms / 通过 |
| `20260923T161508915494` / 12012 | `--scenario normal --speed-mps 70 --pairing-policy exact --full-ir --wire-profile` | 通过，20/20 | 44.181ms / 失败 |
| `20260923T161556561493` / 12013 | `--scenario recovery --speed-mps 70 --pairing-policy exact --full-ir --wire-profile` | **失败保留**，12/28 | 64.368ms / 失败 |
| `20260923T161738871044` / 12014 | `--scenario normal --speed-mps 70 --pairing-policy deadline --full-ir --wire-profile` | 通过，20/20 | 79.776ms / 失败 |
| `20260923T161935756275` / 12015 | `--scenario pose_offset --speed-mps 50 --pairing-policy exact --boundary-obstacles --wire-profile` | 通过，20/20；40个点处于边界敏感带 | 44.487ms / 失败 |
| `20260923T162409704949` / 12016 | `--scenario normal --speed-mps 70 --pairing-policy exact --full-ir --wire-profile` | 通过，20/20 | 47.756ms / 失败 |
| `20260923T162449387313` / 12017 | `--scenario normal --speed-mps 70 --pairing-policy deadline --full-ir --wire-profile` | **失败保留**；末尾状态未排空，Radar/IR各40/100完整接收 | 111.516ms / 失败 |
| `20260923T162751472697` / 12018 | `--scenario recovery --speed-mps 70 --pairing-policy exact --full-ir --wire-profile` | **失败保留**，Radar19拒绝理由不符 | 46.540ms / 失败 |

最后一run显式恢复旧4.25/6.25m世界点，不修改默认4.32/6.32m fixture。
5ms历史位姿造成最大0.250000m连续世界误差，地图索引按实际传递的变换计算。
此前`20260923T153108464398`的失败报告未覆盖，原oracle把理想连续坐标取整当作
地图真值，此处修正判定合同；不宣称边界邻格与理想真值体素相同。

大图normal `exact` 的IR serialize/混合排队/deserialize/回调后P99分别为
5.862/22.910/8.385/1.830ms；Bundle对应5.995/2.760/8.696/2.557ms。
`deadline` IR分别6.674/37.951/10.415/1.928ms，Bundle分别
8.005/4.309/7.041/3.309ms。IR取锁/业务decode/缓存发布的`exact` P99分别
3.361/1.375/3.304ms；这些是不同样本集/独立分位数，不可相加或归因为单一瓶颈。
本轮可确认大图实际ROS反序列化和混合排队有可测成本；40ms等待、匹配/发布
路径也需逐样本定位。短run波动较大，不支持宣称`exact`稳定优于`deadline`。

两次大图recovery仅Radar19（950ms）预期`infrared_unavailable`，实际
`radar_ir_timeout`，双方均拒绝。IR24（480ms）收到时clock=521ms，最终以
`wall_timeout`退出；Radar19决策clock=990ms、墙钟等待约36.68ms。
说明理想1x oracle的旧IR候选存在性与实际墙钟缓存不同；仍保持**整run失败**。
该run地图故障期stale和恢复期fresh单项审计通过，不抵消匹配理由失败。

第二次大图`deadline`的state gate记录221条已接收、219条已发布；末尾
2190/2200ms状态在独立ROS话题的clock覆盖与runner要求finish之间未完成排空。
仅Radar/IR的交付账完整，不能把这次run当成完整功能通过；需在finish前明确
状态/clock排空门禁并证明不越权合成时钟，不覆盖本次失败。

本轮全仓`test_*.py` 196项通过，包含占据索引单独被改坏的RED/GREEN测试与
线格式身份/区间负例。所有八个run本次进程正常清理、端口关闭；无强制终止。
沙箱无法创建回环socket，实际ROS短测按权限审批在沙箱外执行；未进行长时间
性能重复、机载资源实测、PX4高速输入、SIM-01D长测或研究模型质量验收。

下一步先对大图恢复候选过期/理想oracle假设提出可验证的双时钟验收规则，
保留原门禁；再按同一探针在重复大图run中逐样本对齐IR和Bundle尾延迟并评估
提前配对的适用范围；还需对跨话题状态排空增加验收门禁。不能通过放宽5ms或20ms
指标达标。
