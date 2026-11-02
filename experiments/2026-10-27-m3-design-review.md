# EXP-20261027-011：M3-DESIGN-01真实链审计与合成区间方案

日期：2026-10-27；主责任：mapping_engineer；状态：已完成（方案交付）。
依据：M2软件交接完成后，用户“继续”执行下一项M3-DESIGN-01。
分支`feature/engineering-initialization`，先核对Git状态、忽略规则与模块规则，
保留既有未提交改动；本轮无业务/测试源码修改，无提交/推送。

## 目的与审计证据

沿真实链核对，而非将Uncertainty字段存在当作M3能力：

1. `PerceptionEngine.process → _infer`调用后端并经`validate_output`校验；placeholder固定0.9并
   输出confidence=None、uncertainty unavailable（placeholder.py:74）。
2. `output_contract._quality`、`local_map._validate_quality`及
   `codec._uncertainty_fields`均检查available元数据/有限值，已知occupancy_variance为
   单个非负值，但没有完整kind对应单位、形状或校准登记。
3. `SparseLocalMap.update`在local_map.py:197复制最后有效输入quality，
   `query`:305返回该质量，超龄标stale但不改质量/证据时间；不是多帧质量融合。
4. `FixedProbabilityMap.update`:81累计后显式清除confidence和uncertainty，
   `test_m2_fixed_map.py:206`已有反例防止把输入质量当融合质量。
5. `perf01a_codec`在occupancy/snapshot往返调用通用quality检查，
   `query_codec`保持可用性；`MapQueryClient.query`:36核对身份/时间/概率后保真返回，
   自定义字典transport绕过codec时尚不独立核对坏quality。

逐项链接、现状/提案/正式门槛分离见
[M3方案](../docs/M3_SOFTWARE_TRIAL_PLAN_20261027.md)。本轮不读取或修改研究仓库，
不加载checkpoint、模型、GPU或真实设备；未运行新ROS图。

## 只读探针与数值检查

通过指定Conda解释器及sim01_env.sh执行内存探针，保存独立
[report.json](../.runtime/runs/m3-design-20261027T161433188266/report.json)。
9项事实与源码相符：placeholder不可用质量；已知方差保真；stale保留历史质量；
已知零方差可用；当前通用链接受variance带m2单位；通用链接受未限定维数的
position_covariance；自定义应用transport的负confidence和非有限uncertainty仍被返回；
M2不会将输入available质量冒充累计质量。

这份报告的passed表示“审计得到预期的当前行为”，包括明确记录上述缺口；
不表示这些错误/未定义载荷已通过M3语义验收。真实ROS路径仍有codec基础检查，
不能把自定义字典transport的缺口表述为已在ROS运行中观察到坏数值穿透。
通用kind未声明的单位/维度门禁属于本次设计输入，不在文档任务中偷偷收紧旧接口。

另用独立Fraction odds算术核对三组提案预期，逐帧clip至[0.1,0.9]：

| 输入序列 | 累计p | 累计区间 |
| --- | --- | --- |
| 0.75，[0.7,0.8] | 3/4 | [7/10,4/5] |
| 再0.75，[0.7,0.8] | 9/10 | [49/58,9/10] |
| 再0.25，[0.2,0.3] | 3/4 | [49/85,27/34] |

只验证拟用算术的预期与包含关系，没有M3累计器运行，也不是统计覆盖率验证。
拟用kind为occupancy_probability_interval，输入和累计source分开；
任何贡献缺少范围则累计质量unavailable，直到TTL重启或淘汰重建。
neutral规则、混合缺失、区间错形状/单位/source、原子拒绝与恢复均在方案验收表列明。

## 既有定向回归

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_map_query_ros.py' -q
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_application_query_client.py' -q
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_perf01a_ros_codec.py' -q
```

结果分别7/7、4/4、6/6，共17/17项通过，包含已知质量、历史时间与消息往返。
另只读复核M2最终manifest/validation/cleanup及回放报告4份均passed，路径登记于审查产物。
全仓515/515是上一轮SW-04记录，本轮无代码改动未重跑全仓或重复已关闭的ROS场景。
文档相对链接与`git diff --check`通过。

## 交付、文件与下一步

新增docs/M3_SOFTWARE_TRIAL_PLAN_20261027.md及本记录，更新PROJECT_STATUS.md、
docs/DEVELOPMENT_PLAN.md、docs/STAGE_ADVANCE_PLAN_20261027.md、docs/DATA_FORMAT.md、
docs/DECISION_LOG.md及docs/EXPERIMENT_LOG.md。未修改公共消息、默认入口或地图算法。

已有能力仍为M1质量保真和M2质量不可用；本轮新增的是M3具体方案、审计事实和独立算例。
尚未实现M3候选、类型profile、区间传播、应用质量修复或M3 ROS/回放，
不得将本轮17项既有测试记成M3实现通过。

下一项M3-SW-01：显式合成profile/config、fixture与独立oracle；后续固定累计→TTL/滚动→
ROS/应用按方案工作包推进，具体试制实施范围待确认。真实质量/标定、
位姿误差传播、资源/功耗与正式M1/M2/M3验收仍分别跟踪；研究模型质量继续暂缓。
恢复只需暂停尚未开始的软件工作包，既有M1/M2入口与历史资产保持原状。
