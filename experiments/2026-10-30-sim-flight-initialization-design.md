# 无控制初始化准备方案审查

编号：EXP-20261030-009；日期：2026-10-30；任务：SIM-FLIGHT-INIT-DESIGN-01。
主责任：simulation_engineer；状态：已完成（只读审查/具体设计）。
交付：[初始化条件、私有准备合同/预算与SW-03拆分](../docs/SIM_FLIGHT_INIT_DESIGN_20261030.md)。

## 1. 目的与环境

用户继续授权状态中的INIT-DESIGN-01；本轮只制定无控制准备方案，不实施扩窗或新运行。
先读根AGENTS/状态/架构、docs/experiments/simulation/ros_ws/tests/configs规则和相关接口，
核对Git dirty/忽略规则与真实生产链；全部既有修改/未跟踪内容保留。
分支feature/engineering-initialization，HEAD=d96d4439da1007489c80e7f21b132abff16505bf。
通过sim01_env核对Python=/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python；未构建或修改环境。

## 2. 方法与执行

只读追踪地面IC→原桥接pilot IMU→内部积分/缓存→首次初始化→倾角精对齐→磁航向→选中姿态，
同时核对实际缺失和下一步所需观测；源码副本及语句核验有明确设计消费者，没有Hash。
源审计脚本仅在/tmp，输出到新独立[审查目录](../.runtime/runs/flight-init-design01-20261030T103243156519/report.json)，
未新增业务/测试实现；没有运行PX4自带ULog工具或写旧产物。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -c 'import sys; print(sys.executable)'
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B /tmp/ufm_flight_init_design_audit.py
```

第二条只核源码/重读旧字节与既有定向；脚本文本在审查目录随最终审计留存，非项目运行入口。
已有92项定向由脚本实际调用：python -B -m unittest discover -s tests -p 'test_sim_flight*.py' -v。

## 3. 实际结果

| 项目 | 结果 | 边界 |
| --- | --- | --- |
| [24源文本/32项核验](../.runtime/runs/flight-init-design01-20261030T103243156519/source-checks.json) | 全通过；成功update分支才发布完整status，初次初始化与精对齐/姿态发布分开 | 只解释源代码条件，不能算出本run内部低通/方差或唯一根因 |
| [旧21条独立重读](../.runtime/runs/flight-init-design01-20261030T103243156519/sw02d-reload.json) | 采集完整，正文/载荷不完整；六flags样本tilt/yaw=False、selected姿态无载荷 | 非新实际查询，不回填B/C失败或放行控制 |
| [旧wire输入](../.runtime/runs/flight-init-design01-20261030T103243156519/wire-input-audit.json) | 250 HIL_SENSOR，0..996000us/4ms；143原始范围合格样本连续428000..996000us，模长约0..52.238495m/s²/角速度最大.893392rad/s | 两端相距568ms，非EKF低通/方差门；旧记录无逐步AGL/速度/姿态/支柱接触 |
| [方案算术](../.runtime/runs/flight-init-design01-20261030T103243156519/design-numerics.json) | 7检查点/77 topic+7 param=84；2500步/10s；3°平方与默认初始方差分界通过 | 全为拟议值/算术，未执行新准备或证明10s必定收敛 |
| [既有定向](../.runtime/runs/flight-init-design01-20261030T103243156519/flight-targeted.log) | 92/92通过，458源码/配置保持 | 未新增N01—24测试，未重跑全仓；995全仓/84运动仍是上一轮结果 |

新方案先INIT-SW-01离线合同，再INIT-SW-02私有准备，后续SW-03A公共v2离线/SW-03B装配；
不再重复旧21查询作为新任务。准备期保持同IC/同FDM/真实接触和原传感器，不钳制静止或改EKF阈值。
采集、物理静稳、初始化与零执行器输出分别判断；旧1s/500步首包界只属于旧合同，新独立profile须单独验收。

## 4. 文件与保护

新增本实验与具体设计；配套更新PROJECT_STATUS/README、架构/数据/接口/坐标、开发计划、
ADR-044/实验索引及SW-02D后续交接。没有修改业务源码、配置或公共字段，未实现新宿主/codec/节点。
不修改研究仓、第三方/PX4原源，不安装依赖/算Hash，不删除/覆盖历史，不提交/推送。
最终检查本轮文档链接、diff空白、源码及旧工作区保持，结果见同目录final-audit.json。

## 5. 未执行与下一步

初始化准备、两末检查点静稳/有效selected姿态、真实零执行器链均未验证；
公共Scene v2、长准备/采样、严格当前周期绑定、命令/离地及正式飞行验收未执行。
没有新SITL/ROS/Gazebo/RViz/daemon查询、训练/完整模型推理、DEM/占据融合或正式PERF。
直接下一项INIT-SW-01按已交方案先冻结独立字面量/反例再实现私有合同及有界离线验证，
不实施新的实际窗口；研究质量按要求继续暂缓，控制门false、binding=unverified。
