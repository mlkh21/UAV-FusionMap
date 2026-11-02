# 研究组件来源与接入登记

版本：v0.1；核查日期：2026-10-23；责任角色：perception_engineer / mapping_engineer。
状态：源码路径和关键调用链已静态核查；运行、预测质量与实时性能未验收。

## 1. 仓库位置和版本快照

- 本机绝对路径：`/home/zxj/catkin_ws/src/4D-Radar-Diffusion/`。
- 相对UAV-FusionMap根目录：`../4D-Radar-Diffusion/`。
- 相对本README所在algorithms目录：`../../4D-Radar-Diffusion/`。
- 本次核查分支：`uav_system_dev`；HEAD短提交号：`6dd61e2`。
- 工作区存在原有未提交修改和删除记录；该提交号不能完整描述工作区状态。
- 两仓分别有自己的.git。此次初始化未修改研究仓库、环境、数据、权重或产物。

上述为本机当日快照；接入或复现前重新核对路径、完整提交、工作区状态与实际配置。
其他机器可以配置不同源码位置，系统公共数据契约不依赖该绝对路径。

## 2. 已有实现和真实入口

下列链接按同级仓库布局解析。行号是本次核查位置，后续修改可能变化，应同时搜索符号。

| 组件 | 源码/符号 | 本次可证实内容 | 系统责任 |
| --- | --- | --- | --- |
| 预处理 | [preprocess-v3.sh](../../4D-Radar-Diffusion/NTU4DRadLM_pre_processing/preprocess-v3.sh)，行67—99 | 时间索引、标定、align_to lidar、velocity_mode none等配置存在 | sensors/perception边界评估输入适配 |
| 数据与元数据 | [NTU4DRadLM_VoxelDataset](../../4D-Radar-Diffusion/diffusion_consistency_radar/cm/dataset_loader.py)，行1234起 | IR、r_mat/t_vec/k_mat、观测掩码及预处理/标定信息 | perception |
| 融合网络 | [CompleteDualModalityPerceptionNet.forward](../../4D-Radar-Diffusion/diffusion_consistency_radar/cm/multimodal_fusion.py)，行309起 | IR特征、几何投影、Radar编码、门控融合与三维网络调用 | perception研究后端 |
| 推理 | [RadarGenerator.generate](../../4D-Radar-Diffusion/diffusion_consistency_radar/scripts/inference.py)，行1187起 | 采样、VAE解码，主循环加载Radar及多模态元数据 | perception研究后端 |
| 预测协议 | [PREDICTION_CHANNEL_SCHEMA](../../4D-Radar-Diffusion/diffusion_consistency_radar/prediction_artifact_protocol.py)，行14起 | 占据与辅助重建通道分开，正式地图仅消费占据通道 | perception输出适配 |
| 概率地图 | [SlidingProbabilisticGridMap.update_from_voxel](../../4D-Radar-Diffusion/diffusion_consistency_radar/cm/probabilistic_mapping.py)，行942起 | 时间、掩码、位姿及生成占据语义检查与地图更新路径 | mapping独立评估 |
| 地图回放 | [streaming_map_update.main](../../4D-Radar-Diffusion/diffusion_consistency_radar/scripts/streaming_map_update.py)，行1231起循环 | 逐文件读取观测与位姿后更新地图 | 离线验证参考，未证明ROS在线闭环 |

这份清单记录关键入口与边界，不是全仓缺陷审计或完整算法质量评价。

## 3. 感知适配边界

```text
系统SensorBundle
→ 对应模型的体素化/归一化/IR及标定处理
→ 研究生成器
→ 预测占据、独立不确定性、观测域与时空上下文
→ 系统OccupancyObservation
```

模型生成调用不把LiDAR目标点云作为forward输入，但现有流程保留LiDAR体素参考系
和相关标定依赖。不能据此声称已消除全部LiDAR参考依赖，也不能推断无人机必须增加LiDAR。
系统决定把LiDAR严格限制为离线/仿真训练监督：fake或记录LiDAR与Radar/IR同步生成
occupancy target和observed mask，但不进入SensorBundle、模型forward、定位或mapping。
在线保留的`model_lidar`名称只是历史模型逻辑参考系，必须由Body/Radar变换支持。

原始Radar列为[x,y,z,intensity,doppler]，字段与物理量另由
[radar_field_schema](../../4D-Radar-Diffusion/diffusion_consistency_radar/radar_field_schema.py)验证。
系统power字段必须注明是功率、SNR还是未标定强度；confidence需单独处理。
当前preprocess-v3声明velocity_mode none，不能将其写成已完成自运动Doppler补偿。

预测通道0为occupancy_probability；通道1/2/3分别为辅助LiDAR强度、Radar Doppler、
Doppler有效性重建，不消费为系统confidence或uncertainty。不确定性在推理中独立保存，
其类型、布局、分辨率和校准状态需验证后映射。系统转换规则见[DATA_FORMAT](../docs/DATA_FORMAT.md)。

## 4. 已知接入阻断和限制

| 项目 | 当前事实 | 接入前要求 |
| --- | --- | --- |
| 正式推理CLI | 三个 launcher 均调用缺失的`scripts/diagnose_checkpoint_chain.py`；该文件可从研究提交`7b22149`精确恢复，测试目录有一致副本；用户授权的临时恢复验证已通过真实LDM/CD链 | 正式文件当前已删除，需在研究仓库正式变更中恢复后才可启用；不在UAV-FusionMap伪造入口，不借测试脚本冒充生产入口 |
| 模型运行 | 本仓未加载权重、未执行生成；研究仓库已有离线结果显示当前候选质量不足 | 先替换或修复研究候选并完成独立质量门；未通过前不得接入 |
| 时间/坐标 | 研究网格为model_lidar逻辑参考系，文件身份需关联真实时间 | 明确model_lidar到Body/Radar关系及观测时刻变换；不要求在线LiDAR |
| 训练监督 | LiDAR只生成target/observed mask，不能进入forward | 独立记录training_lidar时间/外参/覆盖并做输入标签防泄漏检查 |
| 严格地图模式 | 要求观测掩码、位姿和推理记录 | 不省略合同；地图只消费模型OccupancyObservation，不消费LiDAR监督 |
| 高级地图输入 | 严格模式拒绝未绑定记录的uncertainty、动态证据和未注册DEM | 独立定义来源、坐标、时间和质量契约后验收 |
| 在线系统 | 现有主入口使用文件循环，所查主业务目录未发现ROS发布订阅实现 | ROS节点、状态同步、性能和异常行为另行实现及验证 |

CLI证据：[inference_ldm.sh](../../4D-Radar-Diffusion/diffusion_consistency_radar/launch/inference_ldm.sh)，行12和39；
[inference_cd.sh](../../4D-Radar-Diffusion/diffusion_consistency_radar/launch/inference_cd.sh)，行12和40；
[inference_uniified.sh](../../4D-Radar-Diffusion/diffusion_consistency_radar/launch/inference_uniified.sh)，行11和53。
严格地图限制见streaming_map_update.py的validate_runtime_args（行846—882）。

## 5. 复用顺序与验收

1. 固定要评估的源码状态、环境与输入输出协议，不移动原仓库。
2. 先通过系统占位接口验证时间、坐标、未知和地图消费。
3. 先对候选checkpoint执行独立质量审计；当前16帧Radar+IR LDM结果已被否决，不能把
   LiDAR目标自编码上界或4帧CD smoke当作部署质量证据。
4. 仅在候选通过质量门、checkpoint加载和坐标契约后，验证研究后端小样本加载和生成，
   记录质量、耗时及内存。
5. 再接入perception适配器，验证三种模式使用同一系统契约；研究失败不得fallback。
6. mapping对研究地图原型独立评估；高级功能仍按Local Map开始逐项验收。

运行方式是后续决策，未默认安装研究依赖或选择进程内/独立进程接入。
研究算法不可用时不阻塞系统基础模块和占位链路。

## 6. 2026-10-23前置审计补充

UAV-FusionMap新增只读 `perception/ufm_perception/research_preflight.py`，检查研究
launcher、`inference.py`、checkpoint-chain CLI、VAE/LDM权重、threshold artifact、
Radar normalization、标定目录、`model_lidar`坐标契约、Conda依赖和研究适配器存在性。
当前真实结果为 `ready=false`：三个正式 launcher 均引用缺失的 checkpoint-chain CLI；
研究仓库存在多组候选 VAE/LDM/CD 和 threshold，但默认 `formal_v2_80m_86p8_v1` 资产
目录不存在，不能自动选择旧协议或 smoke 资产。checker 能识别真实
`radar_normalization_v1/v2` 结构和标定文件存在性，但已验证坐标契约和主仓适配器仍阻塞。
该 checker 不加载研究模块、不访问GPU、不执行模型生成，也不修改同级研究仓库。

旧 placeholder ROS 入口增加私有 `~mode` 参数，默认仍为 `placeholder`；disabled 和
research 失败均发布明确 `unavailable` 空观测，禁止静默 fallback。输入契约拒绝 LiDAR、
target 和 observed_mask 及其训练监督派生字段；这只证明前置和边界检查，不证明模型质量、
模型forward、真实标定、实时性能或部署能力。

同日只读核对研究仓库已有质量产物：16帧Radar+IR LDM保存评估的occupied 3D IoU为
`0.573125`，ground false-positive rate为`0.733570`，threshold safety recall为
`not_qualified`；4帧CD A/B CPU smoke保存评估均为occupied IoU `0.566494`、free
recall `0`、ground false-positive rate `1`，两组指标完全相同。该证据足以将当前候选
标记为`rejected_for_integration`，但不宣称完成完整模型质量验收或已定位根因。研究
适配器、forward、真实标定和正式性能仍保持阻塞。
