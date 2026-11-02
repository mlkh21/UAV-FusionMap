# EXP-20261029-003：P5组合输入、独立预期与实际线格式

日期：2026-10-29；任务：P5-SW-01；主责任：tester。
类型：测试合同、反例、实际genpy序列化及全仓轻量回归；状态：已完成（本项软件范围）。
依据：[具体设计](../docs/PHASE5_SOFTWARE_COMBINATION_DESIGN_20261029.md)、ADR-041；
交付与完整运行说明见[输入合同](../docs/P5_SW01_INPUT_CONTRACT_20261029.md)。

## 1. 基线与范围

用户继续后按下一项P5-SW-01实施。读取根/局部规范、状态、系统架构、字段/传感器/坐标合同，
沿实际worker、paired Bundle构造、M4输入与地形公共codec/dataset调用链核对。
分支feature/engineering-initialization，保留大量既有修改及未跟踪文件；未提交、推送或改动同级研究仓库。
现有`.runtime`规则隔离产物，新增tests源码/小JSON没有被忽略；公共消息及旧运行入口均未修改。

已有代码为P3工程感知、M1—M4合成地图、M5公共地形及原生可视化；本轮没有重新实现这些模块。
新增tests私有输入/expected与校验/物化/离线验证工具，未实现组合运行器/ROS节点或模型。

## 2. 先冻结与审查修正

先保存独立expected，再保存输入调度及编写生成/校验。最终九组37子例、253个展开事件、
95检查点/228项预期、6个生命周期声明；物化143组源状态/Radar/IR/Bundle输入与12份逆观测输入。
每次验证先将两份JSON及完整载荷持久化到新目录，再从磁盘读取做codec；没有生成expected的候选运行。

审查修正保留为事实：

- paired超界原因沿源码使用radar_ir_timeout；缺IR保持无Bundle。
- 源码worker对已发较新busy的旧任务超时结果丢弃，分成S03.slow与独立S03.deadline；不改生产worker。
- 新Provider不能假定收到非latched的旧clock，实例重启子例显式补clock并等待安装。
- 子地图owner/封存数量改放declared，不能写成公共接口直接测量值或让application读私有缓存。
- 开发探针发现Python 3.8没有math.nextafter；载荷采用固定float64界，并由Fraction检查外包络，未改环境/安装依赖。
- 理想旋转系数与规范化四元数存在约1e-16浮点差，单独投影容差1e-12；整份实际线格式仍按声明精度比较，整数/高程界不放宽。

S08的33事件是输入预算，超限子例88事件明确预期incomplete；本轮没有实际录制/回放Provider。

## 3. 环境、命令与结果

实际sys.executable为`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`，所有Python命令经
`bash ros_ws/sim01_env.sh ...`。实际旧/新生成消息模块均位于本仓`.runtime/ros/devel/lib/python3/dist-packages/`，
未新增消息或构建、未使用外层catkin_ws；没有ROS Master/服务、GPU、训练或模型推理。

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/p5_fixture_run.py --full
```

最终产物目录：`.runtime/runs/p5-sw01-20261029T112408058122/`。

| 检查 | 实际结果 | 证据 |
| --- | --- | --- |
| 私有输入/预期覆盖与独立算式 | 九组37子例、253事件、95检查点/228项，检查通过 | inputs.json、expectations.json、payloads/ |
| 完整输入/公开样例实际genpy往返 | 143组采样、12逆观测、23样例，共742次通过；独立投影与原字段/质量保真 | report.json、23份bin、37份decoded JSON |
| 新增定向 | 31/31通过，2.012s | targeted.log、targeted-result.json |
| 全仓轻量 | 805/805通过，60.073s | full.log、full-result.json |

反例覆盖重复JSON key、坏编码/非有限/深度/文本/字节超限、float/bool/负/越界时间、
缺失/重复子例和事件、未知字段/操作/版本、墙钟乱序/未声明reset、错配置域、假完整录制、
孤立预期、错误分数区间、训练监督字段、非法公共枚举/身份/flags及合法外形但错误的结果载荷。
实际包覆盖旧SensorBundle/MapQuery/MapQueryResult字段布局、五类地图结果、区间/缺失质量、
地形零/负高/no-data/stale/unavailable、float64界和2^53+1整数时间。没有用mock代替这些线格式检查。

早一轮`.runtime/runs/p5-sw01-20261029T112024335477/`也保留：736次往返、30项定向与804项全仓通过。
之后增加公共状态样例和声明可观测分界反例，故以最终742/31/805为本轮结论，不覆盖旧目录。

## 4. 修改清单与边界

新增8个tests文件的逐项作用见输入合同第1节；另新增本记录与`docs/P5_SW01_INPUT_CONTRACT_20261029.md`。
更新`PROJECT_STATUS.md`、`docs/DEVELOPMENT_PLAN.md`、`docs/STAGE_ADVANCE_PLAN_20261027.md`、
`docs/SYSTEM_ARCHITECTURE.md`、`docs/PHASE5_SOFTWARE_COMBINATION_DESIGN_20261029.md`、
`docs/DECISION_LOG.md`及`docs/EXPERIMENT_LOG.md`，登记本项完成与下一项SW-02。
文档9个相关页面636个本地链接无缺失，任务状态及`git diff --check`通过；
不改任何既有测试的预期或业务源码。

本轮实现：离线输入/预期/schema/序列化及测试完成。
实际验证：上述合同、反例与742次线格式/31项定向/805项轻量回归；全仓中原有mock包装测试不算新ROS运行。
未验证：S01—S09实际组合运行、Provider公共执行回放、新原生图交接/清理、RSS/机载资源、
真实设备/模型质量/DEM、占据融合及完整Phase 4/5。
下一项P5-SW-02实施测试专用装配与公开观察器，再按保存预期执行实际ROS；
外部数据/质量任务保持暂缓，不重跑旧短测冒充新组合能力。
