# EXP-20261028-009：M5独立地形候选与私有回放

日期：2026-10-28；任务：M5-SW-02；主责任：mapping_engineer。
状态：已完成（离线合成候选子范围）。用户在SW-01完成后“继续”授权本工作包。
具体行为：[候选说明](../docs/M5_SW02_TERRAIN_CANDIDATE_20261028.md)。

## 范围与真实链路

先读根规范、当前状态、架构、mapping/tests/docs/experiments规则与已冻结M5输入/预期，
核对真实工厂和公共地图/消息/回放链。分支feature/engineering-initialization保留全部既有未提交修改。
指定Conda Python 3.8.12，经sim01_env.sh执行；没有GIS/模型加载、ROS/Gazebo进程或环境安装。
不改研究仓库、传感器/占据消息、地图工厂/既有占据回放、应用/可视化，不提交或推送。

| 文件 | 改动及原因 |
| --- | --- |
| mapping/ufm_mapping/terrain_fixture.py | 显式独立地形候选，固定fixture注册/中心采样、高程界/缺失、原子整版替换、重复/冲突身份、时钟/reset/disabled和私有查询 |
| mapping/ufm_mapping/terrain_replay.py | ≤64条私有事件、新实例回放、拒绝收据及安装失败状态核对；不读取测试期望 |
| mapping/ufm_mapping/m5_contract.py | 提取请求语法检查供候选区分非法请求与合法错域unavailable，保留原SW-01严格入口 |
| tests/test_m5_terrain_fixture.py | 新增24项行为/原子性/限额/隔离测试 |
| tests/m5_candidate_run.py | 只读取既有SW-01保存产物执行候选验收，每次输出独立run |
| docs/M5_SW02_TERRAIN_CANDIDATE_20261028.md、本记录 | 当前API、时间/质量/数值精度、资源及已验证范围 |

同步更新PROJECT_STATUS、DEVELOPMENT_PLAN、STAGE_ADVANCE_PLAN、SYSTEM_ARCHITECTURE、DATA_FORMAT、
COORDINATE_SYSTEM、RUNTIME_CONFIGURATION、M5设计/SW-01后续状态和决策/实验索引。
未修改上轮配置、fixtures/m5_expectations.json、预期构建器或历史run。

候选只接受私有fixture spec及明确同域时钟/请求。没有向mapping主链投递障碍结果；
高度界是m制绝对高程区间，注册tz界独立，不将它们当作概率或真实方差/质量。
版本提交失败保持原活动spec/样本/revision/版本目录，运行时钟独立记录，不回滚已观察时间。

## 已执行验收

原始输入/预期：[SW-01会话](../.runtime/runs/m5-fixture-20261028T182933778256/report.json)。
最终候选：[report.json](../.runtime/runs/m5-candidate-20261028T184851953489/report.json)、
[完整结果](../.runtime/runs/m5-candidate-20261028T184851953489/candidate-results.json)。
先前首次通过会话[184754](../.runtime/runs/m5-candidate-20261028T184754946307/report.json)亦保留。

| 验证 | 实际结果 |
| --- | --- |
| 4个保存样本 | 源中心/行方向与map点一致；height10→13、height11→14、-2→1；no-data保持null/unknown |
| 质量 | 合成首点区间约[12.65,13.35]m；float64端点向外舍入，独立Fraction核对没有缩窄；缺少样本或注册质量时保持unavailable，不补0 |
| 5个保存边界 | 99/100/199/200/300ns分别unavailable/valid/valid/stale/unavailable，原采集/授权/安装时间保留 |
| 7条保存事件 | 首装/相同/冲突/坏v2/到期/注册到期/reset结果依次installed/idempotent/rejected/rejected/stale/unavailable/unavailable；revision保持1，reset锁定，重复回放逐值一致 |
| 45组保存输入 | 4接收/41拒绝，与SW-01声明一致；候选拒绝后仍未安装；缺失质量可显示未校准高度 |
| 运行验收合计 | 135项检查通过，预期仅来自原SW-01保存文件，未重建或由候选反算 |
| 版本/故障定向 | 成功整版v2替换推进revision，旧版不复活；样本准备与最终状态构造故障不污染版本身份，同身份重试成功；no-data和缺失质量不借旧版 |
| 时钟/隔离/限额 | 明确观察回退终止本实例，历史query不造成reset；错误域无高程载荷；disable无历史输出；64身份与输入字节上限不淘汰旧身份；浮点溢出拒绝；调用者不能修改返回值污染状态 |
| 现有占据隔离 | 安装、重复、冲突、查询、到期、reset和disable前后的既有MapSnapshot逐值不变；默认M1—M4不导入地形/GIS的SW-01测试保持通过 |
| 定向 | M5共45/45通过（0.591s），新增24项，见[日志](../.runtime/m5-sw02-targeted-final-20261028.log) |
| 全仓轻量 | 694/694通过（23.217s），见[日志](../.runtime/m5-sw02-lightweight-20261028.log) |

没有失败运行或测试；额外核查发现Python3.8无math.nextafter，采用受测float64位操作进行必要的区间端点向外舍入。
此数值检查只是合成区间算术，不是模型质量或实际高程误差校准。
保存产物runner明确terrain_layer_executed=true、occupancy_updated=false、ros_master_started=false、real_dem_loaded=false。

## 复现与限制

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m5_candidate_run.py --fixture-run .runtime/runs/m5-fixture-20261028T182933778256
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_m5*.py' -v
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

文档相对链接/源码引用、git diff --check通过，运行产物仍命中.runtime忽略规则。
此次候选未接任何ROS装配，因此没有重启旧ROS/Gazebo；既有运行证据保留原时间/范围。
完整多版本时序、资源临时副本与故障组合尚待SW-03；64×16KiB身份载荷另计活动/候选/返回副本，
不能以16样本上限推断总内存或正式RSS/机载性能。候选单线程，未验证并发服务或长期稳定性。

已有能力：SW-01私有合同与独立预期、M1—M4合成地图/公开应用及既有Gazebo/RViz。
本轮实现：独立地形候选/高程与质量查询、整版安装/去重/冲突及私有回放。
本轮验证：135项保存预期核对、24项新增/M5共45项与694项全仓轻量回归。
未验证：完整SW-03组合、真实DEM/地理注册、真实高程质量、公共地形ROS/应用协议、占据融合或正式PERF-01。

下一项M5-SW-03（计划）：按已实现行为形成更长多版本/时效/故障/资源组合，明确稳定状态与临时峰值，
仍保持离线合成、占据隔离和公共协议关闭；不恢复暂缓的研究质量任务或自动关闭正式阶段门槛。
