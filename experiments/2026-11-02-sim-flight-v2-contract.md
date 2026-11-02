# 公共 flight v2 离线合同验证

编号：EXP-20261102-001；日期：2026-11-02；任务：SIM-FLIGHT-SW-03A。
主责任：integration_engineer；状态：已完成（离线合同/严格codec/实际ROS线格式范围）。
交付：[合同、22文件清单及SW-03B交接](../docs/SIM_FLIGHT_SW03A_CONTRACT_20261102.md)。

## 1. 范围与先行预期

按用户本轮完整授权，重新读取根/涉及目录规范、状态/架构、接口/坐标、指定方案与实际v1生产消费链。
未发现上轮遗留测试/构建进程；分支feature/engineering-initialization，原HEAD=d96d443。
保留全部既有改动和未跟踪文件；查明根build/仅148KiB构建产物后增加忽略规则，不删除。
606文件既有基线已提交e51c752，.runtime/.codex/build均排除，不包含研究仓或外部备份。
Git暂存/提交因沙箱.git只读通过提权工具执行，用户已明确授权，无自动审查拒绝。

先写固定profile、独立字面量/采样表和测试专用struct编码器，再执行freeze；
[freeze.json](../.runtime/runs/flight-sw03a-oracle-20261102/freeze.json)保存时生产包不存在。
包含245组v2独立线格式字节、20组旧v1真实字节、59份旧文件原文（其中25份消息定义），
以及独立时间/坐标/身份/枚举/类型/额外监督字段拒绝预期；无新Hash或历史产物覆盖。
旧v1无applied_frame失败响应不带版本的缺口按合同第2节处理并记ADR-044：v2拒绝此响应，
未来应用前失败用服务错误，不能编造applied_frame。未放宽旧合同或改变消息布局。

## 2. 实际执行

全部Python经统一环境，sys.executable核对为/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -c 'import sys; print(sys.executable)'
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_flight_v2_offline_check.py freeze .runtime/runs/flight-sw03a-oracle-20261102
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py'
bash ros_ws/sim01_env.sh cmake -S ros_ws/src -B .runtime/ros/build -DPYTHON_EXECUTABLE=/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -DCATKIN_DEVEL_PREFIX=/home/zxj/catkin_ws/src/UAV-FusionMap/.runtime/ros/devel
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_sim_flight_v2_*.py' -v
bash ros_ws/sim01_env.sh cmake --build .runtime/ros/build --target uav_fusionmap_sim_scene_msgs_generate_messages -- -j2
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/sim_flight_v2_offline_check.py verify .runtime/runs/flight-sw03a-oracle-20261102
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B -m unittest discover -s tests -p 'test_*.py'
```

日志位于同一独占新目录：baseline-lightweight.log、configure.log、targeted.log、message-build.log、final-lightweight.log。
后续重复核验只允许verify，freeze强制生产包不存在且目录exclusive-create；同一保存目录不能重冻或覆盖。
构建只使用.runtime/ros，没有构建外层catkin_ws、安装新依赖或修改Conda/ROS选择。

## 3. 实际结果与限制

| 验证 | 实际结果 |
| --- | --- |
| 本轮旧基线 | 1090/1090，91.574秒，重新执行，不引用上轮结果冒充 |
| 新定向 | 28/28，0.318秒；覆盖100点表、步号/原时间、坐标边界、全部嵌套监督隔离、身份/枚举/非有限/超限、presence槽、绑定与两版本拒绝 |
| 实际生成消息 | SceneFrame/SceneStepRequest/SceneStepResponse/SceneCaptureAck真实genpy，245组独立字节逐值一致/序列化往返；包含全部100采样步双传感器ACK，不是mock或JSON替代 |
| 旧字节/保护 | 20组旧字节保持且双向交叉拒绝；59文件逐文本保持，其中25消息定义；旧v1合法无帧失败响应仍可用，只在v2拒绝 |
| 隔离构建 | CMake配置与实际消息生成目标成功，Python/输出目录符合规定；没有新类型或运行端点 |
| 最终全仓 | 1118/1118，92.222秒，全部通过；相较本轮基线新增28项，无失败/跳过 |
| 文档与清单 | 新增/改动链接23处全部存在，git diff --check通过；功能交付共22文件（13新增、9修改），不含先行基线提交 |

[实际字节验证报告](../.runtime/runs/flight-sw03a-oracle-20261102/verification-20261102T103722983660.json)
passed=true，binding_status=unverified/control_gate_accepted=false。
所有新增测试首轮通过，无实现错误后修改阈值/预期或运行失败后覆盖证据。
Matplotlib在全仓既有测试中提示用户配置目录不可写并使用/tmp缓存，不影响结果；未修改环境。

本轮没有ROS master/节点、插件/端点、30/40秒FDM或采样运行、heartbeat/模式/arming/manual/参数写；
没有训练、完整模型推理、研究仓修改、DEM融合或正式PERF。
已有10秒准备结果、私有diagnostic v2、1秒运动链分别保留原验收范围；不以它们替代本公共v2长窗运行。

## 4. 交接

本轮仅关闭SW-03A。SW-03B具体条件见交付第7节：原生两侧同合同、应用前错误/后段失败、
整数源时间/10000步独立适配、长窗准备与armed=false/零输出、固定100点真实屏障、
同tick地图/回放、唯一时钟状态与TF、预算/故障/新run/迟到/History/原生窗口及旧入口兼容。
严格周期绑定、非零因果、模式/arming与真实离地仍另验，不自动进入SW-04。
风险是生成类型本身不阻止错版本连接，运行消费者必须显式调用对应codec和绑定校验；本轮没有运行消费者。
恢复可继续旧v1入口；research保持fail-closed，真实设备/模型、真实地形公共服务/注册/融合和完整阶段门槛仍待验。
