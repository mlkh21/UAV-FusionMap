# 有界uORB查询实施与空实例拒绝

编号：EXP-20261030-004；日期：2026-10-30；任务：SIM-FLIGHT-SW-02B。
主责任：simulation_engineer；状态：进行中（软件已交付，实际21次查询验收未通过）。
详细[合同、文件清单、失败、源码证据及下一项](../docs/SIM_FLIGHT_SW02B_PROBE_20261030.md)。

## 1. 目的、范围与环境

按用户继续授权实施已交付的九类topic/三个参数、21次只读补证方案。
根规范/状态/架构、接口与目录规范、dirty/忽略规则及真实生产消费链先核对。
feature/engineering-initialization；HEAD=d96d4439da1007489c80e7f21b132abff16505bf。
全部既有修改保留，不修改同级研究仓、旧公共字段/profile/C++桥接或第三方原源。
Python实际核对/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python，统一经sim01_env入口。
仅隔离.runtime/ros构建，≤250步/1秒，不发控制/参数写，不启ROS/Gazebo/模型或训练。

## 2. 独立预期与实际步骤

1. [字面量独立预期](../.runtime/runs/sim-flight-sw02b-oracle-20261030T013515386163/independent-expectations.json)先保存，包含固定argv/计划/缺失及原生文本预期。
2. 实现私有合同、完整msg布局解析、身份核对及有界真实子进程，初批47项飞行测试通过。
3. 首次实际probe在设备注释处失败；核对Device.hpp，接受其精确嵌套括号语法并新增回归，48项通过。
4. 第二次实际probe在第二条estimator_status空实例处停止；保留标准，新增该实际形状拒绝测试，共49项。
5. 不重复失败probe；独立运行旧stage的normal/disconnect、真实genpy兼容和全仓轻量检查。
6. 离线严格读取唯一有效快照、对照宿主时间/步号、确认空输出及部分流被拒绝，审计源码/进程/端口。

实际命令：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -c 'import sys; print(sys.executable)'
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_sim_flight*.py'
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/sim_flight_diagnostic_run.py --uorb-probe
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_flight_stage_run.py --full
```

新增tests/sim_flight_probe_run.py尚未整体执行；其未来运行会实际重开probe，本轮不为覆盖装配器重复相同失败。

## 3. 实际结果

| 范围 | 预期 | 实际 |
| --- | --- | --- |
| 首次probe | 严格完整文本才生成快照 | [014231618309](../.runtime/runs/sim-flight-sw02b-probe-20261030T014231618309/manifest.json)：1查询，probe_native_annotation；原文保留、停止清理 |
| 第二次probe | 21查询，未知不当作0，坏输出停next | [014636029383](../.runtime/runs/sim-flight-sw02b-probe-20261030T014636029383/manifest.json)：2查询/1有效快照，step125/约.5s停止；probe_native_incomplete，整体未通过 |
| 有效IMU | 原始整数时间与实例分别保留 | 3实例，timestamp/sample=492000us、积分dt均4000us；宿主lastHIL=496000us |
| EKF状态 | 不能由标题/exit0推断字段值 | 六实例只有标题，未取得状态/标志；唯一根因未确认，后续topic/参数未读 |
| 旧normal/disconnect | 旧入口/限额/缺包语义保持 | [最终stage](../.runtime/runs/sim-flight-sw02-stage-20261030T014816354843/report.json)：250次Run/1s与125次Run/停.5s通过，实际执行器均0包 |
| 轻量与线格式 | 合同拒绝/旧实际消息兼容 | 飞行49、运动84、全仓952项通过；77场景字节/36公共往返/18合成源转换通过 |
| 源码/清理 | 不动旧公共/原源或残留会话 | [独立审计](../.runtime/runs/sim-flight-sw02-stage-20261030T014816354843/probe-audit.json)：445源码冻结；原439仅改授权runner、新增6文件，25定义/7入口保持；11自有PID退出/端口free，无实际强制清理 |

两次probe原文/文件均保留，资源23539/27816字节是查询产物大小，不是RSS、时延统计或正式性能结果。
部分流严格重读仍报probe_stream_incomplete，不填补缺失19次、参数值或EKF状态。
源码解释：orb_exists依据advertised，listener现值分支不传播copy失败，EKF状态发布受update成功分支限制。
这只是可核对的失败路径，不证明本次所有内部状态；六份源文本另行冻结，没有新Hash。

## 4. 未验证、风险与下一项

SW-02B的21次实际查询、最终参数核对、EKF/选择器/模式/混控/发送链尚未验收。
打印浮点不是float32原始位模式，逐次查询不构成原子同tick；绑定仍unverified、控制门仍false。
未安装ULog依赖、扩窗、启v2/长准备或发解锁/控制，不涉及真实设备/DEM/占据融合/正式PERF。
研究质量继续暂缓，research fail-closed，训练监督不进入在线链。
下一项DIAG-DESIGN-03仅针对空实例提出三态/独立诊断事件的具体补证方案，不改本轮失败结论。
所有本次进程已停止；恢复用新run，默认旧入口保持，不删除或覆盖历史产物，不自动提交/推送。
