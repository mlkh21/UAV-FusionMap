# EXP-20261027-012：M3-SW-01显式合同、合成输入与独立oracle

日期：2026-10-27；主责任：mapping_engineer；状态：已完成（输入/预期软件范围）。
依据：[M3具体方案](../docs/M3_SOFTWARE_TRIAL_PLAN_20261027.md)交付后用户“继续”。
分支`feature/engineering-initialization`，先读取规则、接口及真实M2合同/fixture/编码链，
检查Git状态和忽略规则，保留全部既有未提交改动；未提交/推送。

## 实现与边界

新增[显式配置](../configs/m3_fixture.yaml)，schema为m3_fixture.v1，
fixture_only=true、enabled_by_default=false。包含完整M2算术子配置、独立map_id
m3-fixture、输入示例区间与精确profile；不借其他模块私有数据或设备配置补默认值。

新增[纯合同检查](../mapping/ufm_mapping/m3_contract.py)，复用同模块M2输入的
来源、odom坐标、观测时刻变换、网格、质量基础检查，再对M3显式输入约束：

- available kind仅occupancy_probability_interval、unit仅dimensionless、恰为两个
  有限非bool且有序的概率端点，严格包含本voxel均值；输入/累计source分别为
  m3_fixture_bounded_inverse_v1及m3_fixture_bounded_accumulator_v1，禁止反向混用。
- unavailable必须value=None，与可用零宽区间不同；[0,0]或空数组不代替不可用。
  p=0.5的中性输入只允许可用[0.5,0.5]或不可用质量，不产生新累计证据。
- 首版pose_uncertainty仍为unavailable；不把位姿误差、方差、熵、模型分数或confidence
  伪装成概率范围。顶层训练字段、voxel附加训练字段、错误源/domain/frame均拒绝。
- 均值先确定float32承载值再构造区间；输入不采用输出舍入容差，不改写端点。
  配置中occupied/free均值也须已为float32还原值，防止oracle与实际输入取不同均值；
  内部clip界保留双精度，但不能量化到排除的0/1端点。
- internal输出检查严格包含；wire输出使用`round32(lower)≤wire_mean≤round32(upper)`，
  即端点的nearest-even映像，不采用任意epsilon。覆盖0.5边界两侧不同float32间距、
  中点ties、clip界和零宽区间；不改变公共载荷中的数值来修补误差。

此模块没有累计器、ROS或研究导入；不加入默认包入口，也没有修改M1/M2、
ROS节点/launch、现有codec或应用客户端。全局通用kind范围保持。
目前map_backend=m3_fixture仍未实现，输入检查不代表地图后端已接通。

## Fixture、oracle与冻结产物

[m3_fixture.py](../tests/m3_fixture.py)复用测试专用M2公开占据构造，显式生成M3
sample_id及质量，输入仍为fixture OccupancyObservation，不读SensorBundle、Radar/IR、
LiDAR、target或训练observed_mask。默认10组具名场景、43条观测：
正负累计/截断/反证、float32零宽、缺失锁存、缺失后TTL重启、无证据保持、
无历史无证据、中性零宽、TTL恰边界与超界。
这些是保存预期的输入场景，不是本轮执行了真实地图的时序/TTL验收。

[m3_oracle.py](../tests/m3_oracle.py)仅依赖Fraction，独立于业务合同、fixture转换、
log-odds和地图更新器。按显式有理数recipe逐帧相乘odds、逐帧clip，分别给出名义值
和上下界；事件时间必须严格递增，不排序或补旧消息。缺失贡献后锁存质量不可用，
TTL之后新贡献从先验重启。预期另含observed、最后贡献时间、revision及五类状态，
只属于测试产物，不是新增公共ROS字段。

手算三步分别固定为3/4及[7/10,4/5]、9/10及[49/58,9/10]、
3/4及[49/85,27/34]。0.7零宽场景显式使用11744051/16777216的float32均值；
输入区间随同一个还原值构造，没有在接收端偷偷扩大0.7区间。
有理数recipe表示声明的算术预期，实际float64端点的数值承载须在后续累计对账中
按约定容差另验，不能仅凭分数oracle声明浮点累计器已正确。

[输入生成器](../tests/m3_fixture_run.py)对每帧先检查，再实际serialize/deserialize
现有ROS OccupancyObservation消息、再次检查并比较完整字典，随后保存独立预期。
它还检查预期输出质量的internal/wire承载可行性，未运行任何地图累计或ROS Master。
每次独立新run，保留旧产物，不使用哈希。

首次通过run `m3-fixture-20261027T163357805832`保留；完善配置精度约束后最终run：

- [report.json](../.runtime/runs/m3-fixture-20261027T163801864738/report.json)：通过，10场景43输入，明确map_accumulation_executed=false及指定解释器。
- [config.json](../.runtime/runs/m3-fixture-20261027T163801864738/config.json)：本次显式完整参数。
- [fixtures.json](../.runtime/runs/m3-fixture-20261027T163801864738/fixtures.json)：逐场景recipe、实际解码输入和分数/浮点预期，供SW-02直接读取核验。
- [定向日志](../.runtime/runs/m3-fixture-20261027T163801864738/ufm-m3-sw01-targeted.log)、[全仓日志](../.runtime/runs/m3-fixture-20261027T163801864738/ufm-m3-sw01-full.log)。

## 验证

新增[test_m3_fixture_contract.py](../tests/test_m3_fixture_contract.py)共19项测试，
覆盖配置默认关闭/错误拒绝、全序列真实消息序列化、错误kind/unit/source/形状/数值、
输入与累计来源隔离、缺失/零宽/中性、来源/训练字段、位姿质量、末尾坏体素不修改输入，
float32均值及零宽反例、nearest-even边界、精确三步预期、逐帧clip反证、缺失锁存/TTL
及无证据时间预期。没有把checker的无副作用测试宣称地图原子提交已验收。

新进程检查默认create_map不导入M3，显式导入合同也不加载torch、numpy或研究模块。
运行器正例保存10场景/43输入；临时错误配置的负例退出1、保存失败报告且不产生fixture，
没有fallback。临时测试输入不覆盖成功run，测试所生成的预期不依赖候选实现。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m3_fixture_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_m3_fixture_contract.py' -v
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

结果：19/19项定向、534/534项全仓轻量回归通过，`git diff --check`与文档链接检查通过。
解释器为/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python，运行器核对sys.executable。
本轮仅新增独立合同/测试输入工具，未修改既有默认运行调用链，因此未重复启动
旧ROS场景；其实际ROS基线证据保留在SW-04交接记录。

## 变更清单与下一步

新增代码/配置6个文件：mapping/ufm_mapping/m3_contract.py、configs/m3_fixture.yaml、
tests/m3_fixture.py、tests/m3_oracle.py、tests/m3_fixture_run.py、tests/test_m3_fixture_contract.py。
同步PROJECT_STATUS.md、M3方案、开发/跨阶段计划、DATA_FORMAT、RUNTIME_CONFIGURATION、
DECISION_LOG与EXPERIMENT_LOG，并新增本记录；既有未提交改动继续保留。

已有能力是M1质量保真、M2累计质量不可用；本轮新增并验证输入profile与独立预期。
M3累计器、缺失锁存/TTL/滚动的实际运行、应用检查接入和M3 ROS均留后续工作包。
未实施真实统计校准、模型质量/forward/checkpoint、位姿误差传播或正式资源/性能验收，
未安装依赖、启GPU/训练或修改同级研究仓库，不关闭正式M1/M2/M3。

下一步M3-SW-02：在提交前构造质量的最小扩展点上实现默认关闭的固定累计候选，
直接读取本次保存的输入/预期，不重算oracle来迁就实现；名义概率对M2、
区间/时间/revision对冻结预期，覆盖缺失锁存、错来源与原子拒绝。
后续同一合成范围按既有授权推进。恢复使用原M1/M2入口，无需迁移公共消息或缓存。
