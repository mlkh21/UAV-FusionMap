# selector私有离线合同与独立合成重读

编号：EXP-20261030-013；日期：2026-10-30；任务：SIM-FLIGHT-INIT-SELECTOR-SW-01。
主责任：simulation_engineer；状态：已完成（私有离线软件范围）。
交付：[七文件、精确合同、预算、结果与下一任务](../docs/SIM_FLIGHT_INIT_SELECTOR_SW01_CONTRACT_20261030.md)。

## 1. 范围与保护

用户“继续”确认按selector具体设计推进独立离线合同；未启准备期/daemon查询或扩大公共接口。
读取根规则/状态/架构、simulation/configs/tests/docs/experiments规则、接口/坐标/具体设计和原合同/生产消费链。
核Git/忽略，分支feature/engineering-initialization，HEAD=d96d4439da1007489c80e7f21b132abff16505bf，
既有dirty与未跟踪build等全部保留；原476份源码/配置逐文本不变，无同级研究仓读写。
Python经统一入口核对/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python；无构建/依赖安装/Hash/训练或推理。

## 2. 执行与先行预期

先新增手工S01—24字面量、机械复制原物理profile/10消息/6生产源及质量语义片段，保存独立oracle，
再新增生产模块、独立合成工厂和28项测试。oracle report记录new_production_parser_exists=false，
阶段工具在导入实现前再次冻结独立输入/计划与两组文件，不调用被测parser生成预期。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -c 'import sys; print(sys.executable)'
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B /tmp/ufm_selector_freeze.py
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_sim_flight_initialization_selector.py' -v
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_flight_initialization_selector_run.py --oracle .runtime/runs/flight-init-selector-sw01-oracle-20261030T124951555793 --full
```

freeze脚本仅用于机械保存具名源/独立fixture，不是运行入口；不重复执行覆盖既有目标。
[oracle](../.runtime/runs/flight-init-selector-sw01-oracle-20261030T124951555793/report.json)、
[正式阶段](../.runtime/runs/flight-init-selector-sw01-20261030T125535247310/report.json)、
[旧消息/全仓](../.runtime/runs/sim-motion-sw04a-20261030T125603368174/report.json)均为本轮实际产物。
首次新增28项测试即通过；去除未使用import、加入阶段工具后，以最终483源码运行完整检查，之后只修改文档/审计。
本轮没有新仿真失败/重跑，没有调整旧断连接/准备失败、物理容差、白名单或期望门槛来让测试通过。

## 3. 实际结果

| 检查 | 实际结果与限制 |
| --- | --- |
| 独立输入/源 | 24组预期、10消息/6源/原质量片段消费预检通过；漂移拒绝。不证明实际二进制、非受限构建以外或设备兼容 |
| 历史第30条 | 新解析精确8槽null/说明，旧parse仍probe_native_float；仅离线投影，historical_event_accepted=false，原实际运行仍失败 |
| 新私有字节 | 101次JSON往返（3种封套+98事件）通过；不是新ROS线格式或实际daemon采集 |
| 合成ready文件 | 2500 step/98事件独立生成、落盘重读；主实例1/gyro槽2/accel槽0，500合成零执行器，四门true但selector载荷不完整、控制false/绑定unverified |
| 合成missing文件 | 2500 step/98事件、无执行器/状态不可用；collection_complete/input_settled=true，initialization_ready/output_chain_observed/passed=false，不补零 |
| 来源关联 | 七检查点前后表/selector时间独立保留，消费消息时间null、exact_source_message_verified=false；同表不冒充同消息消费证明 |
| 定向/全仓 | 新增28/28、飞行162/162、运动84/84、全仓1065/1065通过 |
| 旧线格式/入口 | 77场景字节/36公共往返/18合成源转换用真实genpy；25旧定义/7入口不变，旧实际场景未重跑 |

新增严格fixture/recording/query/observation与98计划、设备表校验、精确槽位缺失/原文投影、
有界文件/同run物理组合和原四门扩展；原84合同、宿主、运行包装和默认入口不改。
load_recording消费固定四物理文件/新观测；wire只有封套/载荷限额检查，两个合成wire为空，不伪造实际包。
S01—24及补充测试覆盖坏枚举/数值/数组/身份/缺失说明、两类槽区别、版本/路径/混合记录、
时间/期限/总量、源漂移/监督字段及未就绪否决；异常不静默fallback。

## 4. 文件与交接

新增7份源码/配置/fixture及本说明/实验，必要文档索引同步；
本轮最终[保护/链接审计](../.runtime/runs/flight-init-selector-sw01-20261030T125535247310/final-audit.json)
核483源码不变/原476保持、独立预期原字节、原定义/入口、历史失败及Git分支/HEAD。
新增模块没有在线业务消费者，未增加LiDAR/target/observed_mask输入、定位或TF。

下一项INIT-SELECTOR-SW-02才新增独立98项实际装配，沿原同FDM/IC/10s/2500步及预算，
先离线停止，再一次新规则正常准备和断连接/期限故障、原wire/物理/原文/关联独立对账及清理。
13项400ms组期限、实际设备表/末两检查点姿态/输出就绪仍未验证；到界失败如实保存，不扩窗/补采。
完整准备、同消息消费身份、严格周期绑定/非零属性因果、公共v2/长采样和命令/离地均未新增通过。
研究质量/真实输入/DEM融合/正式资源继续独立暂缓；不自动提交或推送。
