# 公共flight v2长窗观察链验证

编号：EXP-20261102-002；日期：2026-11-02；任务：SIM-FLIGHT-SW-03B。
主责任：integration_engineer；状态：已完成（40秒无控制观察及采样/地图/原生/故障兼容软件范围）。
交付：[运行链、门槛与预算](../docs/SIM_FLIGHT_SW03B_DELIVERY_20261102.md)。

## 1. 授权与先行证据

用户在SW-03A完成后明确“继续下一步”，按已交第7节实施SW-03B；未进入SW-04。
分支feature/engineering-initialization、起点5b04270、起始工作区干净；保留所有旧运行与既有提交。
读取根/模块规范、当前状态/架构、原飞行和初始化方案及真实源/消费链。
固定Python通过sim01_env使用，构建在.runtime/ros，未修改Conda或终端ROS选择。
先保存独立输入/采样/准备检查点与故障预期，再实现生产目录；
[先行freeze](../.runtime/runs/flight-sw03b-oracle-20261102/freeze.json)含485份源文本，production_exists=false。

## 2. 初次检查与失败

独立宿主和v2原生插件build-only：
[141648308411](../.runtime/runs/flight-scene-normal-20261102T141648308411/manifest.json)，构建/五类控制拒绝自检通过。
新10项定向初次通过；初次socket预检因沙箱Operation not permitted未启动场景，随后经提权工具获得本机执行许可。
无自动审批拒绝或系统网络修改，未向硬件/QGC/远程发送控制。

| 尝试 | 实际结果与处置 |
| --- | --- |
| [141910450969](../.runtime/runs/flight-scene-normal-20261102T141910450969/manifest.json) | 125 Run/.5秒、首SYS_AUTOSTART原文已保存；新记录器重复argv构造异常。修正为显式原字段投影并补回归；清理通过 |
| [142042465762](../.runtime/runs/flight-scene-normal-20261102T142042465762/manifest.json) | 541步时读取到写入中的半行，记录最大3335字节未超16KiB；原始完整文件/终态保留。修正累计读至换行且保持同字节界/期限；清理通过 |
| [142221273828](../.runtime/runs/flight-scene-normal-20261102T142221273828/manifest.json) | 7000步/28秒、112合法查询后期限停止。第112条正文耗时8.94954ms，监督器递归盘点数万份收据干扰其后期限检查；将wire收据放独立目录并按实际写入字节计数，仍每0.5秒盘点外部日志且保留200/400ms期限；原失败不回填 |
| [143110573154](../.runtime/runs/flight-scene-normal-20261102T143110573154/manifest.json) | 原生版完成10000 Run和100采样，但RViz的IR显示关闭，图中No Image，原生验收明确失败；修正仅新flight窗口显式启用IR并记录真实接收数/原戳，保留失败六图和收据 |
| 首次轻量回归 | 1128项中1项错误，旧测试用__new__构造收据对象而未有新参数；为工具保留类级原默认值，原11项引擎测试通过。失败日志lightweight-first.log保留 |

修复后新增12项定向通过，包括原文argv、分段写入和超限回归；测试不以改答案/删用例/放宽限制解决失败。
实际故障/原生/兼容结果分别记录如下，不将工程失败改成已通过。

首个完整正常：[142707281102](../.runtime/runs/flight-scene-normal-20261102T142707281102/manifest.json)，
[validation](../.runtime/runs/flight-scene-normal-20261102T142707281102/validation.json)、
[同tick地图](../.runtime/runs/flight-scene-normal-20261102T142707281102/delivery-validation.json)及
[独立审计报告](../.runtime/runs/flight-scene-audit-20261102T143055607849/report.json)均通过。
10000 Run/40秒、150合法查询/三末准备点true、100组raw/Bundle/占据/快照/200 ACK、107公开查询/回放。
真实wire独立重读10000 HIL_SENSOR/39 HIL_GPS/9572零执行器、10039源收据，控制发送为false；
181000 Radar点、唯一TF/Context与独立进程公共回放通过。采样期IR零像素变化为静止观察实测，不称作运动/飞行。
墙钟129.10012035秒，检查时产物180500790字节；最终字节与完整套件总预算另核，不作为RSS/PERF。

原生正常：[143554316028](../.runtime/runs/flight-scene-normal-20261102T143554316028/manifest.json)，
[六图/渲染目标验收](../.runtime/runs/flight-scene-normal-20261102T143554316028/figure-validation.json)、
[独立wire/原文/公开回放审计](../.runtime/runs/flight-scene-audit-20261102T144418265689/report.json)通过。
仍为10000 Run/40秒、150合法查询、100采样；9574个真实全零执行器，准备/同tick地图/清理通过。
实际人工读取RViz截图确认Radar点、占位网格和IR几何热强度，IR首图enabled=true/messages=1/stamp=30100000000，
末图/History及两原生viewport均检查，未用桌面截图或空“No Image”当通过。
原生前后飞机静止，Gazebo像素不变是地面观察结果；不套用旧运动验收的位移像素阈值或宣称受控飞行。

## 3. 冻结故障结果

| 用例 | 实际结果与独立证据 |
| --- | --- |
| 中途缺IR回执 | [144416957631](../.runtime/runs/flight-scene-missing-ir-ack-20261102T144416957631/manifest.json)：7550物理Run/两组raw，公共停7549步，仅1 Bundle/占据/快照，8公开查询/回放，迟到请求服务错误；[审计](../.runtime/runs/flight-scene-audit-20261102T144636550066/report.json)通过 |
| 首采样缺IR回执 | [144635173445](../.runtime/runs/flight-scene-first-missing-ir-ack-20261102T144635173445/manifest.json)：7525物理Run/一组raw，公共停7524步，0 Bundle/占据/快照，4查询均不可用，迟到请求拒绝；[审计](../.runtime/runs/flight-scene-audit-20261102T144917072086/report.json)通过 |
| 30秒禁止采样 | [144915727879](../.runtime/runs/flight-scene-not-ready-20261102T144915727879/manifest.json)：实际准备原文仍ready=true，独立注入injected_not_ready禁止采样，7500 Run/公共7500步停止，0 raw/ACK/Bundle/占据/快照；不声称真实PX4未就绪，[审计](../.runtime/runs/flight-scene-audit-20261102T145121086129/report.json)通过 |
| 125步后断连 | [145119708230](../.runtime/runs/flight-scene-disconnect-20261102T145119708230/manifest.json)：126物理记录/125成功Run，第126条未Run/peer_closed，公共125步，20合法查询，0采样；[审计](../.runtime/runs/flight-scene-audit-20261102T145235447626/report.json)通过 |

缺IR回执注入发生在闸门接收侧：真实Camera仍发布raw/ACK，闸门不计对应ACK，故真实raw/ACK保存且失败tick不提交公共成功状态。
四例均停止next，晚请求不能复活失败实例；后续新run重新初始化/空地图，独立来源身份/老run查询拒绝。
所有例均无强制进程终止、子PID残留或占用端口，cleanup/ports通过；没有发送飞行控制。

## 4. 兼容、回归与偏差披露

最终轻量回归[final-lightweight.log](../.runtime/runs/flight-sw03b-oracle-20261102/final-lightweight.log)：
1130/1130通过，94.361秒；新12项与旧11项引擎定向通过。初次1128项/1错误原日志保留，不覆盖。
最后两项源码仅为tests兼容包装/收尾审计，在核心实际运行之后新增；核心已记录的源码逐文本保持，后续工具不改变业务实现。

| 兼容用例 | 结果与范围 |
| --- | --- |
| 旧v1运动 | [145449337113](../.runtime/runs/sim-motion-sw03-20261102T145449337113/manifest.json)：250步/1秒、10组真实采样/20 ACK、旧地图/回放通过，构建输出.runtime/ros/flight-compat-v1-build |
| 旧静态原生 | [145640431839](../.runtime/runs/sensor-scene-20261102T145640431839/manifest.json)：旧静态Gazebo/RViz/真实Radar/IR/地图与清理通过，构建输出.runtime/ros/flight-compat-static-build |
| 旧PX4估计默认入口 | [145849520109](../.runtime/runs/sim01a-live-20261102T145849520109/manifest.json)：实际原估计状态链exit=0/errors=[]，cleanup/ports通过；无新构建 |

构建目录偏差：首次旧v1兼容[145234093854](../.runtime/runs/sim-motion-sw03-20261102T145234093854/manifest.json)
虽技术passed，但沿用旧函数默认.runtime/sim-motion-build，违反本轮仅.runtime/ros构建约束。
不删除或改写该次记录；新增tests/sim_flight_scene_legacy.py只在测试包装显式传output_directory，
重新执行并以上表隔离构建的兼容结果交付。旧生产默认配置/入口未改，偏差不能被后续通过抹去。
全部新增flight产品与原生工具均在.runtime/ros，没有构建外层catkin_ws、写研究仓或安装大型依赖。

[最终收尾报告](../.runtime/runs/flight-scene-final-20261102T150033101394/report.json)passed=true，
5核心同533份源码快照、3兼容、708自有PID无残留、原25消息定义保持；所有核心原文/字节/回放审计另见前表。
核心合计32701物理记录/32700成功Run、101业务采样/620查询，失败实际物理步与公共提交严格分开。
正常原生case138.493777284秒、397467276最终产物字节、94268817订阅wire字节，均在240秒/512MiB/128MiB界。
五核心墙钟410.575586201秒，登记case/历史尝试/产品总1759078395字节<5GiB；非RSS/正式PERF。
最终核对当前实现仍等于这533份源文本；之后只新增两个tests兼容/收尾工具，接受运行源码未被改写。
原有485份保护源中8份有计划内更改，清单见收尾报告，其他保持；旧25定义/v1合同/默认入口/配置保持。
本次正常9574包actuator−HIL均−4000us，绑定仍未验证；原戳保留，不补正为本step。
交付34文件（18新增/16修改），文件清单在交付第6节；阶段完成后按用户授权独立Git提交，不推送。
新增/修改文档52处本地链接均存在，git diff --check通过；最终核对无PX4/Gazebo/ROS master或本轮窗口进程残留。

## 5. 可复现入口

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_scene_run.py --build-only
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_sim_flight_scene_runtime.py' -v
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_scene_run.py --products .runtime/ros/sim-flight-scene-build/flight-scene-normal-20261102T141648308411 --no-native
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_scene_run.py --products .runtime/ros/sim-flight-scene-build/flight-scene-normal-20261102T141648308411
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_scene_run.py --products .runtime/ros/sim-flight-scene-build/flight-scene-normal-20261102T141648308411 --case missing-ir-ack --no-native
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_scene_run.py --products .runtime/ros/sim-flight-scene-build/flight-scene-normal-20261102T141648308411 --case first-missing-ir-ack --no-native
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_scene_run.py --products .runtime/ros/sim-flight-scene-build/flight-scene-normal-20261102T141648308411 --case not-ready --no-native
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_scene_run.py --products .runtime/ros/sim-flight-scene-build/flight-scene-normal-20261102T141648308411 --case disconnect --no-native
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_flight_scene_legacy.py motion
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_flight_scene_legacy.py static
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim01_smoke.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py'
```

products复用逐文本校验实际构建输入；原隔离源副本/产品保留，原桥接源码不写。
所有新运行独立目录，失败和后续成功分开记录，不覆盖旧manifest/raw或改收据时间。
本机ROS/端口/渲染需要沙箱外执行许可，仅用于用户授权的有界仿真与自有进程清理。

## 6. 风险与交接

仅关闭单profile无控制地面观察的软件范围；实际长窗/100采样/故障/同tick地图和原生交接已按本轮证据通过。
严格周期绑定/非零因果/模式/arming与真实离地不能由本任务推出；控制false、绑定unverified保持。
下一步先做SW-04前置严格绑定/非零因果具体方案与独立预期，不自动启动控制或重复初始化表示修复。
本轮不训练、不完整研究推理、不改同级研究仓、不做DEM融合或正式PERF，不删历史产物、不新增无用途Hash。
