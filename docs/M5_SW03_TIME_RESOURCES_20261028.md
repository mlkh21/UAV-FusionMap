# M5-SW-03：时序、失败恢复与逻辑资源组合

日期：2026-10-28；主责任：mapping_engineer；状态：已完成（私有离线合成软件范围）。
依据：[M5设计](M5_TERRAIN_PRIOR_DESIGN_20261028.md)、[候选说明](M5_SW02_TERRAIN_CANDIDATE_20261028.md)。
证据：[EXP-20261028-010](../experiments/2026-10-28-m5-time-resources.md)。

## 1. 实际审计与修改范围

沿真实调用链确认：`TerrainFixture.install`先完成校验/规范编码、样本准备与身份目录，
最后一次替换`self._state`；`query`不推进观察时钟；reset/disable为终止门控。
`terrain_replay.replay_terrain`独立新建实例，每批最多64事件，不消费expected决定结果。
工厂/ROS/应用仍没有地形选型、订阅或公开地形服务。

本轮业务代码仅在[m5_contract._text](../mapping/ufm_mapping/m5_contract.py)增加字符数提前拒绝：
字符串字符数大于16,384时，其JSON编码必然超过16KiB，须在strip/编码前失败。
字符数不是字节数；其余输入仍由原规范JSON总字节限额决定是否接收。
这是对既有必拒绝输入的提前失败，没有扩大私有合同或公共字段。

此前直接对象路径允许超长文字先进入JSONEncoder，再按编码片段大小拒绝，
不能据此声称当前编码片段有固定上界。修补后所有可变文本先经过上述长度门控，
默认ASCII JSON最坏每Unicode字符产生12个转义字节（代理对），另有引号2字节。
测试通过拦截JSONEncoder确认超长身份/来源文本在编码前拒绝，旧状态保持；
长度恰为16,384的非BMP字符串则实际触发196,610字节片段，整体拒绝且不提交。
调用者已分配的任意大输入、JSON库内部对象及进程内存不属于这项逻辑保证。

其余新增代码均在tests：

| 文件 | 职责 |
| --- | --- |
| [m5_time_scenarios.py](../tests/m5_time_scenarios.py) | 不导入候选的显式时序预期和16样本/大载荷压力输入 |
| [m5_time_validation.py](../tests/m5_time_validation.py) | 对保存预期重放；五处故障注入及满容量拒绝/恢复组合 |
| [m5_resource_audit.py](../tests/m5_resource_audit.py) | 保留项与运行中唯一对象/身份原载荷、编码片段分开统计 |
| [m5_time_run.py](../tests/m5_time_run.py) | 先保存inputs.json再执行；--input只读已保存输入，独立输出 |
| [test_m5_time_resources.py](../tests/test_m5_time_resources.py) | 10项行为/故障/资源/独立预期及占据隔离回归 |

没有新增节点、消息、GIS依赖或地形→占据规则；没有修改研究仓库。

## 2. 独立时序与联合故障

四组显式预期共84事件，每组在原64事件限制内；每组重复回放逐值一致。
先保存输入与预期，再由候选执行，期望不从候选输出反算；错误预期会使检查失败。

| 序列 | 事件数 | 已验证行为 |
| --- | --- | --- |
| eight_versions_64_events | 64 | 8版整版替换；有效/缺失质量/no-data、原采集时间、安装/授权边界；冲突/退役拒绝；重复不延寿；到期及覆盖外不变free |
| delayed_activation_registration_reset | 11 | 新版授权前安装失败、到时重试；到期stale、注册结束unavailable；时钟回退及后续增长均不恢复 |
| disable_survives_expiry_and_retry | 5 | 停用后即使重复安装或查询历史/过期时刻也无高程输出 |
| independent_new_run_domain | 4 | 独立run从空目录安装；外域请求无载荷，后续本域查询正常 |

容量压力通过直接调用方法执行64次成功安装，不冒充超过64事件限制的私有回放。
第64版提交前依次注入：staged spec已复制、已准备8样本、全部样本完成、身份目录完成、
新状态构建后紧邻提交的五处故障。均保留63个旧身份/旧样本/旧revision，再以同身份成功提交。
单元检查还分别验证各故障后的同身份重试/幂等，以及第16样本数值溢出后的整版回滚/修正重试。

目录满后：活动版重复幂等；第65版、同版内容冲突、超限ASCII/Unicode编码与退役版均明确拒绝，
不得淘汰身份后接受旧版。未来/当前版本安装前的查询不改变时钟；满目录reset/disable仍无高程输出。
贯穿上述序列和压力检查的既有非空占据快照逐值不变。

## 3. 资源口径与实际计数

每版16样本，规范JSON为16,000字节；64身份原载荷合计1,024,000字节。
稳定项分别为模板16格、活动spec 16格、活动转换样本16个、身份64个。
模板/活动输入/转换输出是不同表示，不得将“16个活动样本”描述成总内存。

以下采样仅覆盖terrain_fixture.py的Python行/返回边界，包含方法帧可达输入、已提交/临时状态、
部分样本、snapshot/query返回拷贝；不计调用者保存的历史结果/回放收据、测试仪器字符串缓存，
不覆盖JSON/deepcopy/C运行库的内部瞬时分配，不能作为完整分配器峰值或RSS验收。

| 对象/载荷 | 本次观察最大值 | 保守结构界限 |
| --- | --- | --- |
| 已提交/临时状态 | 2 | 2 |
| grid高度槽（每槽另有mask/质量） | 64 | 5×16=80 |
| 转换样本/查询记录 | 32 | 3×16+1=49 |
| 两状态身份目录引用 | 127 | 2×64=128 |
| 唯一完整规范JSON字节 | 1,040,000 | (64+1)×16,384=1,064,960 |
| 已接收编码片段字节 | 16,000 | 16,384 |
| 编码器当前片段字节 | 196,610 | 12×16,384+2=196,610 |

grid界限预留模板/传入/已提交/临时/返回五份；样本界限预留旧/新/返回及单个查询记录。
旧/新身份目录共享不可变字符串，按对象身份去重计载荷，不能将两目录引用数再乘16KiB当精确占用。
完整JSON和编码片段可能有重叠引用；表格不是可直接相加的精确内存账单。
快照另有最多64项version_ids引用；掩码、质量贡献和固定元数据随上述格槽/样本存在，
没有将这些对象算成“零内存”，也没有宣称表格覆盖全部Python对象或对象头字节。
最多64个事件的回放输入/收据由调用方持有，另于输出报告保存，未纳入候选对象采样预算。

## 4. 复现、恢复与下一步

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m5_time_run.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m5_time_run.py --input .runtime/runs/m5-time-20261028T191532492862
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_m5*.py' -q
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py' -q
```

每次创建新目录，原SW-01/02及本轮中间产物保留；恢复为停止检查并新建私有实例/run，
不清理身份、覆盖旧输入或重写历史结论。`--input`不调用时序预期构建器。

本项关闭私有离线地形软件组合范围；尚不关闭真实DEM、公共地形交接、占据融合或正式M5/Phase 4。
新增10项、M5共55项与最终全仓704项通过；保存输入重放的输入/完整结果逐值一致。
下一项M5-IFACE-DESIGN-01仅交独立地形查询/状态/回放的具体公共合同及生产消费、兼容与恢复方案。
实际新增ROS消息/服务/客户端/显示前另行确认；不恢复暂缓的研究质量任务。
