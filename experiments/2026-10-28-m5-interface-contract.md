# EXP-20261028-012：公共地形消息/codec/记录合同离线验证

日期：2026-10-28；主责任：integration_engineer；任务：M5-IFACE-SW-01。
状态：已完成（新增类型与离线合同范围）；实施依据：用户本轮明确授权、ADR-040及
[具体方案](../docs/M5_IFACE_DESIGN_20261028.md)。
字段与实际入口：[实施合同](../docs/M5_IFACE_SW01_CONTRACT_20261028.md)。

## 目的与前置核对

此前只有独立私有TerrainFixture及占据ROS/应用链，新地形公共类型不存在。
本轮建立独立4.msg/1.srv、公开逻辑/codec/dataset/recording校验，先用独立预期验证真实生成线格式，
保留旧公共字段与运行装配。没有恢复暂缓的真实数据或研究质量任务。

已读根AGENTS/PROJECT_STATUS/SYSTEM_ARCHITECTURE、数据/传感器/坐标合同、
M5接口设计与SW-01/02/03说明、ADR-040、上轮实验及mapping/ros_ws/tests/docs/experiments规则。
分支为feature/engineering-initialization，大量既有修改和未跟踪文件保留，未提交/推送。
核对忽略规则：.runtime被忽略，新源码/预期不被忽略。中断后检查未发现遗留构建/测试任务。
Python核对为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`（3.8.12），所有命令经sim01_env。

实际调用链：旧factory→M1/M2/M3/M4与旧MapQuery/query_codec/客户端保持；
私有m5_contract→TerrainFixture/terrain_replay保持；
新增显式链仅为公开dataset→严格检查→私有包装适配、公开逻辑对象↔新genpy类型、三文件记录→结构校验。
没有新在线生产者/消费者、Provider或运行节点。公开共享合同放在新包内，避免未来消费者导入mapping实现。

## 实施与独立预期

先保存[独立预期JSON](../tests/fixtures/m5_iface_expectations.json)，包括完整Context、4个样本、
各枚举、>2^53整数与float64界、旧字段布局；随后才创建实现/生成新消息。
[测试布局与struct编码](../tests/m5_iface_fixture.py)明确列出线格式顺序/类型，不读取生成类或生产codec反算预期。
界端点用独立Fraction算例核对：例如0.65的最近二进制float64略偏大，下界保存为0.6499999999999999；
不以被测地形候选输出确定期望。运行前另保存全部旧.msg/.srv、CMakeLists和package.xml副本，未计算Hash。

实现包含严格字段、bool/int/float64/枚举、规范缺失槽、源/注册/结果质量角色及贡献、
实例/revision/回显/pin、Context时间/坐标一致性和独立JSON/ROS字节预算。
dataset包装只替换schema/profile并构造旧私有固定标志，不丢额外字段接受坏输入。
recording校验包含引用、安装尝试/提交revision、序号/单调记录时间、版本Context、incomplete及目录限额。
它只验证记录声称的结构，不执行安装或逐事件回放；不会读取source_ref所引用文件。

## 构建与复现

Noetic/catkin 0.8.12，沿现有隔离.runtime/ros构建，没有构建外层catkin_ws、安装依赖或修改Conda环境。
实际执行：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -c 'import sys; print(sys.executable)'
bash ros_ws/sim01_env.sh cmake -S ros_ws/src -B .runtime/ros/build -DCATKIN_DEVEL_PREFIX=/home/zxj/catkin_ws/src/UAV-FusionMap/.runtime/ros/devel -DPYTHON_EXECUTABLE=/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python
bash ros_ws/sim01_env.sh cmake --build .runtime/ros/build --target uav_fusionmap_terrain_msgs_generate_messages -j2
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/m5_iface_run.py --full
```

生成器实际输出4消息/1服务的Python/C++/NodeJS/Lisp/EusLisp代码；本轮线格式验证使用真实genpy类型。
服务请求与响应封套实际serialize/deserialize，不使用mock替代线格式，也未注册或调用真实ROS服务。
runner先在新目录保存独立输入/期望字节，再产生实际字节与日志；同一目录不覆盖既有产物。

## 实际结果与失败记录

| 检查 | 结果 |
| --- | --- |
| 独立布局/线格式 | 4消息+服务请求/响应字段、枚举、完整Context及预期字节一致；8组保存字节与解码对象逐值一致 |
| 高度/缺失/质量 | 0与负高度、no-data、覆盖外、stale有/无高度、缺失样本或注册质量、不可用空槽通过；两种质量角色独立往返 |
| 类型/绑定/拒绝 | >2^53及int64/uint64边界保真；坏版本/枚举/身份/实例/pin/角色、NaN/Inf、非中心/时间不一致、缺flag/隐藏旧值、截断/尾字节/非规范bool均拒绝 |
| dataset | 45组既有输入的接收/拒绝保持；公开包装双向拷贝保真，Context对独立表一致；各组额外LiDAR/target/observed_mask均拒绝 |
| recording | 三文件保存/读取逐值一致；64dataset/64event边界、缺引用/跳号/旧Context、超限/坏JSON/缺尾行、缺输入标完整/incomplete严格拒绝通过；不是执行回放 |
| 旧接口 | 全部旧.msg/.srv与旧包CMakeLists/package.xml相对实施前副本逐文件一致；旧生成字段布局与旧查询实际字节往返通过；默认工厂不导入地形 |
| 最终新增定向 | 29/29通过，0.546s |
| 最终全仓轻量 | 733/733通过，55.830s；704项既有+29项新增 |
| 文档/工作区 | 11份相关文档667个本地链接无缺失，Git空白检查通过；全部既有改动保留 |
| 资源范围 | 16KiB请求/dataset、64KiB消息/记录、64事件/64dataset及4MiB目录分别检查；非RSS、传输连接资源或PERF-01 |

首轮新增测试16项中两项脚手架断言失败：旧uncertainty逻辑缺失误写为[]，以及误认为生成对象slot不能删除。
修正为旧合同要求的None，删除flag后验证codec明确ValueError拒绝，同时统一缺字段拒绝异常。
没有修改旧codec或放宽旧合同。首轮完整29项/733项已通过；最终又补核对独立质量消息支持注册区间角色，
重新保存独立run并执行上述最终29/733项，通过结果以最终目录为准，旧run保留。

最终产物目录：[m5-iface-sw01-20261028T201233206358](../.runtime/runs/m5-iface-sw01-20261028T201233206358/)。
其中[report.json](../.runtime/runs/m5-iface-sw01-20261028T201233206358/report.json)、
[独立输入/预期](../.runtime/runs/m5-iface-sw01-20261028T201233206358/inputs-and-expectations.json)、
expected/actual-00—07.bin、recording三文件及
[定向日志](../.runtime/runs/m5-iface-sw01-20261028T201233206358/targeted.log)/
[全仓日志](../.runtime/runs/m5-iface-sw01-20261028T201233206358/full.log)保留。
旧定义副本：[baseline](../.runtime/m5-iface-sw01-baseline/)。
前次通过产物仍在`.runtime/runs/m5-iface-sw01-20261028T200843992039/`，未覆盖。

## 修改清单与恢复

- 新增`ros_ws/src/uav_fusionmap_terrain_msgs/`：CMakeLists.txt、package.xml、setup.py，
  4.msg/1.srv及`src/ufm_terrain_contract/{__init__,bounds,contract,codec}.py`。
- 新增`mapping/ufm_mapping/terrain_dataset.py`、`terrain_recording_contract.py`。
- 新增`tests/fixtures/m5_iface_expectations.json`、`tests/m5_iface_fixture.py`、`m5_iface_run.py`、
  `test_m5_iface_codec.py`、`test_m5_iface_recording.py`。
- 新增本记录与`docs/M5_IFACE_SW01_CONTRACT_20261028.md`；更新PROJECT_STATUS及
  DATA_FORMAT、SENSOR_INTERFACE、SYSTEM_ARCHITECTURE、M5_IFACE_DESIGN、DECISION_LOG、
  DEVELOPMENT_PLAN、STAGE_ADVANCE_PLAN、EXPERIMENT_LOG的当前状态/索引，保留历史时点结论。

恢复只需继续使用未改的旧入口，停用新合同的显式调用；不删除生成物、记录、数据或checkpoint，
不重置工作区。新类型仅独立包，未给旧包新增运行依赖；同级研究仓库未修改，无自动提交/推送。

## 已有、实现、验证与未验证

已有代码：私有TerrainFixture/回放、M1—M4占据ROS与旧可视化。
本轮实现：独立公共类型、逻辑/codec/dataset/recording结构校验及离线测试。
实际验证：隔离类型生成、独立字节对真实genpy、29项新增与733项全仓、旧定义兼容。
未验证能力：Provider/可信clock/串行化状态机、真实地形服务/状态流、客户端超时/迟到/重启、
公共录制与执行回放、RViz地形、真实DEM/地理注册/质量、占据融合与机载RSS/时延/功耗。
本轮只完成SW-01；后续SW-02/03按原方案推进，不关闭正式M5/Phase 4。
