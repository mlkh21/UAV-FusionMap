# EXP-20261023-001：ALG-01 / T-13B 研究后端前置审计与感知模式 fail-closed

## 1. 基本信息

- 日期：2026-10-23
- 责任角色：perception_engineer / Technical Lead
- 关联任务：ALG-01、T-13B、REQ-01、REQ-05、REQ-13
- 工作区：UAV-FusionMap `feature/engineering-initialization`
- 研究仓库：`/home/zxj/catkin_ws/src/4D-Radar-Diffusion`，只读；未修改
- Python：`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`

## 2. 审计结论

### 已有代码

- `perception/ufm_perception/placeholder.py` 是当前唯一实际感知业务实现，按 Radar 点
  生成 fixture 占据，不生成 free 证据。
- `ros_ws/src/uav_fusionmap_perception/scripts/perf01a_placeholder_node.py` 原先直接导入
  placeholder；旧 launch 入口未有研究模型调用。
- 研究仓库正式 LDM/CD launch 使用 `scripts/diagnose_checkpoint_chain.py`，当前文件缺失；
  `scripts/inference.py`、融合网络、预测通道协议和检查点加载逻辑仍存在。
- 研究模型 forward 的源码参数包含 Radar、IR、标定矩阵、时步和状态质量，不包含
  LiDAR target 或 observed mask；研究输出协议仍使用 `model_lidar` 逻辑网格参考系。

### 仅文档或源码声明

- 研究 launcher 的注释声明只读取 sensor-aware Radar+IR，但不等于已完成 UAV-FusionMap
  SensorBundle 适配、标定绑定或 ROS 在线调用。
- 研究源码存在 checkpoint、归一化、LiDAR 参考系和 calibration 检查逻辑，但当前没有
  可运行的主仓研究适配器，也没有加载权重或执行模型 forward。

### 当前阻塞

本轮 preflight 的真实报告为 `BLOCKED`，明确列出：缺失
`diagnose_checkpoint_chain.py`、VAE/LDM checkpoint、occupancy threshold artifact、
Radar normalization 绑定、`model_lidar` 到 Radar/Body 的已验证坐标契约和 UAV-FusionMap
研究后端适配器。研究后端不满足前置条件时不产生模型占据，也不回退到 placeholder。

## 3. 本轮实现

- 新增 `perception/ufm_perception/research_preflight.py`：只检查路径、CLI、权重、阈值、
  归一化 JSON、标定目录、坐标矩阵、输入契约、Conda 依赖和适配器存在性；不导入研究
  模型、不加载 checkpoint、不访问 GPU、不执行生成。
- 新增 `configs/research_backend_input_contract.json`：明确 SensorBundle 必需字段，禁止
  LiDAR、target、observed_mask 及训练监督派生字段进入 forward。
- 新增 `unavailable.py` 与 `modes.py`：disabled 输出 unavailable 空观测；research 前置
  阻塞或适配器未实现时输出 model/unavailable 空观测；两者均不产生 free 证据。
- 旧 placeholder ROS 节点增加私有 `~mode` 参数，默认仍为 `placeholder`。research 只在
  分支内加载 preflight checker，失败原因通过 PerfEvent 和 unavailable 观测保留；没有
  placeholder fallback。
- 未新增公共 ROS 消息，未改变 SensorBundle、OccupancyObservation、定位或 mapping 字段。

## 4. 验证

定向测试：

```text
/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python tests/test_research_preflight.py
7/7 通过
```

覆盖 disabled/placeholder 无研究导入、缺 CLI、缺 checkpoint、真实归一化/threshold/标定
结构检查、LiDAR/target/mask 拒绝、research 失败不回退和旧 placeholder launch 默认值。

全仓轻量回归：

```text
bash ros_ws/sim01_env.sh python -B -m unittest discover -s tests -p 'test_*.py' -q
Ran 386 tests ... OK
```

旧 placeholder ROS 入口：

```text
bash ros_ws/sim01_env.sh python -B ros_ws/perf01a_async_run.py \
  --duration-s 2 --port 11583 --audit-online-graph
```

结果：`passed=true`，在线图和占位链路通过，未启动研究模型；该运行在沙箱外执行以取得
ROS 临时端口权限，进程/端口清理正常。

研究 preflight 实际输出：`ready=false`。输入契约和 Conda `numpy/torch/yaml` 依赖检查
通过；研究 CLI、权重、阈值、归一化绑定、坐标契约和适配器仍阻塞。没有训练、完整模型
推理、PERF-01或科研对照试验。

## 5. ALG-01-R 研究仓库入口与资产恢复审计

本轮只读核对同级研究仓库当前真实文件，不修改该仓库、不加载 checkpoint、不执行
模型 forward：

- launcher：`launch/inference_ldm.sh`、`inference_cd.sh`、`inference_uniified.sh` 和
  `scripts/inference.py` 均存在；三个 launcher 都调用缺失的
  `scripts/diagnose_checkpoint_chain.py`，因此正式入口当前不可执行。
- 已发现候选资产：`formal_v2_1_80m_86p8_db_snr_v1` 和
  `formal_v2_1_80m_86p8_db_snr_smoke_v3` 具备 VAE/LDM/CD 及对应 threshold；另有
  `formal_v2_1_80m_86p8_db_snr_v1_three_state_full20_20261014_tmux` 和
  `formal_v2_1_80m_86p8_db_snr_v1_three_state_smoke_20261020_parent` 仅具备 VAE/LDM
  及 threshold。它们不是 launcher 默认的 `formal_v2_80m_86p8_v1`，不能自动绑定。
- 归一化候选存在于研究仓库 `config/`，其真实协议为
  `radar_normalization_v1/v2`，包含 `target_size=[32,128,128]`、80 m 网格和
  intensity/doppler/variance 四通道物理语义；本仓 preflight 已修正为检查该真实结构。
- `Data/config` 中存在 Radar/Livox/thermal 外参及 thermal 内参文件，但文件存在不等于
  已验证适用于 UAV-FusionMap；`model_lidar` 到 Radar/Body 的坐标契约仍未绑定。
- `occupancy_threshold.json` 具备 `formal_chain_v2`、stage、选定阈值和 checkpoint 绑定
  字段；本仓 preflight 只做结构检查，不计算或重写文件哈希。

### 恢复性结论

- `diagnose_checkpoint_chain.py` 曾在研究仓库提交 `02c4fd3` 新增、在 `7b22149` 修改，
  并在 `fe24c00`（2026-09-04“文件整理”）被删除；当前 `HEAD`、`main`、
  `uav_system_dev`、`origin/main` 和 `origin/withir` 均不再包含该路径。
- `test/diagnostics/occupancy/diagnose_checkpoint_chain.py` 与 `7b22149` 中的正式脚本
  内容一致；当前工作区还残留 `.pyc`，但二进制缓存不是可审计的源码入口。
- 历史脚本在当前 Conda 环境执行 `--help` 成功；它调用的
  `validate_formal_checkpoint_chain`、`checkpoint_state_dict`、`safe_torch_load` 及
  `target_stage/allow_legacy_protocol` 参数仍与当前 `checkpoint_chain.py` 兼容。
- 因此该文件可以从 `7b22149` 精确恢复，或从测试副本核对恢复；本轮没有执行恢复，
  因为恢复会修改同级研究仓库，需作为独立授权任务处理。

### 临时恢复验证（用户授权）

用户授权后，临时从 `7b22149` 恢复到研究仓库正式 launcher 路径：
`diffusion_consistency_radar/scripts/diagnose_checkpoint_chain.py`。使用当前 Conda
环境执行：

- `--help`：通过，正式 CLI 可导入。
- `validate --target_stage ldm`：真实
  `formal_v2_1_80m_86p8_db_snr_v1/vae/vae_best.pt` 与 `ldm/ldm_best.pt` 通过，报告
  `protocol=formal_chain_v2, stages=vae,ldm`。
- `validate --target_stage cd`：同一 VAE/LDM 加 `cd/cd_best.pt` 通过，报告
  `protocol=formal_chain_v2, stages=vae,ldm,cd`。

本次只读取并校验 checkpoint 协议，不执行 `--construct`、模型 forward、完整推理或报告
写入。验证完成后已删除临时恢复文件；研究仓库恢复为操作前状态，既有未提交改动均保留。
因此当前正式 launcher 路径仍然缺失该文件，UAV-FusionMap preflight 继续 fail-closed。

显式使用上述现存 VAE/LDM、threshold、normalization 和 calibration 资产运行 preflight
时，资产项通过，但整体仍为 `BLOCKED`：缺 checkpoint-chain CLI、缺已验证坐标契约和缺
UAV-FusionMap research adapter。该结果说明“资产存在”与“可加载/可运行”已分开。

## 6. 能力边界

- 现有能力：研究源码和静态调用链可审计；placeholder 在线 ROS 链路可运行；训练监督
  LiDAR 与在线 SensorBundle 的字段/图边界已有测试。
- 本轮实现能力：disabled/placeholder/research 三种模式的最小分发；研究前置检查和
  fail-closed unavailable 语义；训练字段输入拒绝。
- 本轮已验证能力：386 项轻量测试通过；旧 placeholder ROS 2 秒在线图审计通过；研究
  preflight 在当前真实目录明确报告阻塞。
- 未验证能力：研究 checkpoint 加载、真实 Radar/IR 预处理、模型 forward、模型质量、
  `model_lidar` 实际标定转换、GPU/资源/时延、真实设备和正式 PERF-01。

## 7. 现有模型质量否决审计（2026-10-23）

本节只读取研究仓库已有保存评估JSON，不启动训练、不加载checkpoint、不执行模型forward，
也不修改同级研究仓库。

### 7.1 可核对证据

- `loop3_three_state_full20_ldm_vs_vae_16f_20261015/evaluation_summary.json`为16帧
  保存预测评估，stage为`offline_evaluation`，阈值来源为validation artifact；Radar+IR
  LDM的occupied 3D IoU为`0.573125`、precision为`0.628417`、recall为`0.867223`、
  free 3D recall为`0.324900`、ground false-positive rate为`0.733570`。
- 同目录报告的微平均还记录known-free false occupancy约`0.675551`，并报告16/16帧
  LDM IoU低于LiDAR目标自编码上界。该上界是目标域确定性重建参照，不是部署质量基线；
  但Radar+IR结果的自由空间误占用已经足以阻止当前候选进入在线地图。
- `cdA_loop3_cpu_smoke_20261023_4f_evaluation`和
  `cdB_loop3_cpu_smoke_20261023_4f_evaluation_retry`均只有4帧，且保存评估数值完全
  相同：occupied IoU `0.566494`、precision `0.566494`、recall `1`、free recall `0`、
  ground false-positive rate `1`、预测/目标点数比`1.765345`；两组threshold safety
  recall均为`not_qualified`。这只能证明保存预测评估链可读，不能证明CD优于LDM或已具备
  在线质量。

### 7.2 决策

当前研究候选标记为`rejected_for_integration`。在研究仓库独立修复或替换候选并形成新的
质量证据前，UAV-FusionMap不新增research adapter、不执行单帧forward、不把占位输出伪装
成研究输出。research模式保持明确`unavailable/error`，不回退placeholder。

这不是“完整模型质量验收已完成”的声明：根因可能涉及阈值、Radar分布、IR投影/标定、
LDM表示或损失，当前证据尚未区分这些原因。它只说明当前候选已有足够的负面质量证据，
不具备工程接入资格。

### 7.3 后续门槛顺序

1. 研究仓库正式恢复checkpoint-chain CLI，并重新绑定候选协议、归一化和权重；不在本仓库伪造入口。
2. 研究仓库独立完成候选替换/修复和质量门，至少覆盖多帧、距离/高度分层、known-free误占用、
   阈值资格及失败样本；未通过前不做UAV适配器。
3. 质量门通过后，才做CPU/map_location只读checkpoint加载冒烟；加载通过后再审查
   `model_lidar`到Radar/Body的真实标定和坐标契约。
4. 坐标、归一化和输入输出协议闭合后，才允许单帧Radar+IR forward；随后独立验证
   输出通道、unknown/free语义和错误不fallback。
5. 最后才进行真实设备、目标平台资源和正式PERF-01；模型质量、真实标定和正式性能
   必须分别验收，不能用占位链路或离线小样本互相替代。
