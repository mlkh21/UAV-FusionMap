# EXP-20261028-010：M5离线时序、资源与失败恢复

日期：2026-10-28；主责任：mapping_engineer；状态：已完成（私有离线合成软件范围）。
对应任务：M5-SW-03；[详细说明](../docs/M5_SW03_TIME_RESOURCES_20261028.md)。

## 目的与前置条件

在已完成SW-01合同/独立预期及SW-02独立候选基础上，核对多版替换、到期、reset、
失败重试、身份容量及运行中临时副本，保持占据层隔离；不开展研究模型质量或真实DEM。
Git位于feature/engineering-initialization，有大量既有未提交/未跟踪文件；全数保留，未提交/推送。
根/模块规范、状态、架构、M5设计/输入/候选及真实调用链已核对；.runtime忽略规则保持。

## 输入与执行

解释器实际为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`（Python 3.8），
全部通过`bash ros_ws/sim01_env.sh ...`运行。没有启动ROS master、Gazebo、研究模型、GPU或GIS。

输入先保存到新目录inputs.json：4组显式时序及其独立期望、4×4压力tile。
期望构建器不导入候选；执行阶段重读保存的输入，不重建预期。
压力tile每个规范身份载荷16,000字节，64身份全部保留，不计算Hash。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m5_time_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m5_time_run.py --input .runtime/runs/m5-time-20261028T191532492862
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_m5*.py' -v
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

## 实际结果

| 检查 | 结果 |
| --- | --- |
| 独立时序 | 64/11/5/4事件，合计84；44条查询覆盖valid/unknown/stale/unavailable，19次明确拒绝，逐项保存预期一致 |
| 重放 | 每组重复一致；--input独立新run与首次保存输入/完整results.json解析后逐值一致 |
| 满容量及重试 | 64次成功安装；第64版五处故障保留63身份/旧状态，随后同身份成功；满容量重复幂等 |
| 满容量拒绝 | 第65版、同身份异内容、ASCII/Unicode编码超限及退役版本均明确失败，不消耗/淘汰旧身份 |
| 末样本失败 | 第16样本数值溢出导致整版回滚；修正后同版本重试成功，未混用旧样本 |
| 到期/reset/disable | 不延寿、不复活；注册结束及终止门控无高程；未来/历史查询不改变观察时钟 |
| 占据隔离 | 所有序列/压力前后既有非空占据快照逐值相同，未产生占据/自由或训练监督输入 |
| 稳定载荷 | 活动转换样本16、活动spec 16格、模板16格；64身份JSON载荷1,024,000字节 |
| 临时对象采样 | 87,796个行/返回采样；2状态、64 grid槽、32样本/查询记录、127身份目录引用；完整JSON 1,040,000字节、编码片段16,000、当前片段196,610，均在结构界限内 |
| 定向 | 新增10项；M5共55/55通过（33.146s） |
| 最终全仓轻量 | 704/704通过（54.561s），见[日志](../.runtime/m5-sw03-lightweight-final-20261028.log) |

早期9项/全仓703项也通过，随后资源审查发现直接对象超长文本在JSON编码后才拒绝。
因此在私有`m5_contract._text`增加编码前字符数门控，并补充Unicode转义峰值及第10项回归，
重新执行55项、最终704项、完整runner和保存输入重放；早期产物/日志全部保留。
没有业务输出失败被改成成功，也没有放宽断言或覆盖历史预期。

## 产物

- [最终首次运行](../.runtime/runs/m5-time-20261028T191532492862/report.json)：inputs.json、results.json、report.json。
- [保存输入重放](../.runtime/runs/m5-time-20261028T191616320309/report.json)：输入与结果逐值一致。
- [最终全仓日志](../.runtime/m5-sw03-lightweight-final-20261028.log)；先前703项日志与19:08/19:11等中间run保留。
- 既有SW-01/02运行目录只读，未重建或覆盖。

## 变更、限制与恢复

已有能力是独立TerrainFixture及有界私有回放；本轮新增组合验收工具与一处私有文本提前拒绝。
源码：mapping/ufm_mapping/m5_contract.py；新增测试文件：tests/m5_time_scenarios.py、
tests/m5_time_validation.py、tests/m5_resource_audit.py、tests/m5_time_run.py、tests/test_m5_time_resources.py。
配套更新PROJECT_STATUS、设计/计划/架构进展、决策/实验索引及本说明；公共数据字段没有变化。

资源结果是逻辑保留项及候选Python行/返回可达载荷采样，不是完整分配器峰值/RSS。
JSON/deepcopy内部瞬时对象、测试仪器缓存、调用者额外保存的输入/历史输出和回放收据未计入；
本次传入spec的可达载荷已纳入对象采样，但任意直接对象的既有分配不能靠校验消除。
没有正式机载内存、时延、功耗或PERF-01结论。
本轮没有运行实际ROS图；旧入口的软件回归随全仓通过，不复述为新ROS运行证据。
真实DEM/地理转换、实际标定/控制点/高度质量、公共地形ROS/应用、占据辅助融合均未验证。

只关闭M5私有离线合成软件范围，正式M1—M5及完整Phase 4保持未关闭。
恢复为停止离线工具、新建实例/run重放保存输入，不清理版本身份、不回写原产物。
下一项M5-IFACE-DESIGN-01仅设计独立地形公共合同、生产消费、兼容与恢复；实际扩展另确认。
