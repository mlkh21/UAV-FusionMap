# EXP-20261027-007：M2-SW-01合成证据契约、参数与独立数值oracle

日期：2026-10-27；主责任：mapping_engineer；状态：已完成（M2-SW-01软件范围）。
依据：用户在[M2具体方案](../docs/M2_SOFTWARE_TRIAL_PLAN_20261027.md)交付后明确“按你说的做”，
确认合成数据软件试制范围。本轮先完成M2-SW-01，不实现M2累计器或ROS候选模式。
分支`feature/engineering-initialization`，保留既有未提交改动，不提交/推送。

## 实现与文件

| 文件 | 生产者/消费者与作用 |
| --- | --- |
| [m2_fixture.yaml](../configs/m2_fixture.yaml) | 测试fixture/oracle读取，未来M2-SW-02接收显式参数；现有ROS生产入口不读取 |
| [m2_contract.py](../mapping/ufm_mapping/m2_contract.py) | 纯业务配置及合成占据输入契约；不实例化地图或累计概率 |
| [m2_fixture.py](../tests/m2_fixture.py) | 测试专用合成消息生产者；不读取传感器、训练监督或研究模型 |
| [m2_oracle.py](../tests/m2_oracle.py) | 独立精确分数odds乘法与逐步截断，输出后续候选的预期概率/观测时间 |
| [test_m2_fixture_contract.py](../tests/test_m2_fixture_contract.py) | 10项配置、来源/时空、消息往返、坏值、明确free/无证据及手工数值期望测试 |
| [m2_fixture_run.py](../tests/m2_fixture_run.py) | 离线产物运行器，保存实际配置、合成输入和预期值；不启动ROS Master或地图累计器 |

配置明确`fixture_only=true`、`enabled_by_default=false`，域为
`m2_explicit_inverse_fixture_v1`，固定odom网格、合成单位变换标定引用、先验0.5、
occupied/free输入0.75/0.25、概率界限0.1/0.9、分类阈值0.3/0.7、TTL100ms、
采样间隔10ms、身份上限1000、cell上限10000。均为具名软件fixture参数，
不是设备标定、模型校准或机载资源/飞行验收阈值。

合成消息严格沿用现有OccupancyObservation字段，source_type=fixture；
只在明确free场景产生observed=true的0.25体素。unobserved槽位保持0.5且observed=false；
empty/no_return/unavailable/degraded均无体素。该no_return是测试空占据场景，
不模拟或读取实际Radar/LiDAR回波。质量未知保持confidence=None和uncertainty unavailable。

输入校验拒绝非候选domain、model/measured/simulation来源、额外公共合同外字段、
错时空/标定、非法概率0/1/NaN/Inf/bool、重复/越界index与非valid携带体素。
本工作包只允许显式声明的固定单位变换；滚动/任意有效body位姿的扩展留M2-SW-03。
来源标签是测试契约声明，不是原始记录真实性认证。

## 独立oracle与验证结果

oracle只导入标准库`fractions.Fraction`，不导入fixture消息转换器、M1地图或未来M2
累计器；以精确odds乘法实现对照，不使用log/sigmoid路径。手工固定分数序列作为第二层
测试：occupied两次为3/4、9/10；连续三次正证据饱和后一次负证据回到3/4，
而非错误的批量求和后截断结果9/10；正负相抵为1/2且observed=true。

无历史的neutral/unobserved/empty/no_return/unavailable保持probability=None、observed=false、
last_observed_timestamp=None；有历史时这些输入不刷新最后证据时刻。
oracle当前只覆盖A/B/C/D算术与无证据场景，遇到需要TTL重启的新证据时明确拒绝；
不伪造SW-03老化逻辑已经完成的结果，也不执行候选去重/地图查询。

实际命令（指定Conda解释器，经SIM-01环境）：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p test_m2_fixture_contract.py -v
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m2_fixture_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

结果：10/10定向、479/479全仓轻量回归通过；`git diff --check`通过。
运行器交付9场景/31占据消息，全部经现有ROS消息编解码往返保真，
独立[报告](../.runtime/runs/m2-fixture-20261027T144245043459/report.json)、
[配置](../.runtime/runs/m2-fixture-20261027T144245043459/config.json)、
[输入及预期](../.runtime/runs/m2-fixture-20261027T144245043459/fixtures.json)。
报告明确`map_accumulation_executed=false`；没有网络socket或驻留ROS/模型进程需要清理。

## 状态与恢复

M2-SW-01完成，已确认的合成数据软件试制授权登记到状态与决策，不要求后续同范围反复确认。
下一工作包M2-SW-02实现固定网格累计器和公开查询，并消费本轮独立预期验证A—G。
M2-SW-03去重/TTL/滚动、M2-SW-04实际ROS/回放交接仍是后续任务。

当前没有M2累计/查询运行证据，没有新在线ROS图、研究checkpoint/forward、真实设备、
正式M1/M2或PERF-01验收。没有新增公共ROS消息/字段，没有改变M1默认行为或研究仓库。
恢复只需停止使用本轮测试入口；现有运行入口不会读取新配置，历史run保留不动。
