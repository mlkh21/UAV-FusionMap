# PERF-01-A fake Radar/IR功能级参数化

编号：EXP-20261003-002  
日期：2026-10-03  
责任角色：sensor_engineer / tester  
状态：已完成功能级实现与轻量回归；真实设备接口和质量验收未完成。

## 目的

在不改变现有SensorBundle消息、不引入研究模型或LiDAR的前提下，把fake Radar/IR从固定
占位载荷扩展为可控、可重复的功能级fixture，为后续同步、故障和接口测试提供参数入口。

## 实施范围

- `make_fake_radar`和`make_motion_radar`支持可选FOV门控、最大量程、位置噪声、强度噪声
  和扫描持续时间；运动Radar继续明确`doppler_available=false`。
- `make_fake_infrared`支持背景值、可重复噪声和曝光持续时间；图像单位仍为
  `fixture_intensity`，不解释为辐射测量。
- `configs/perf01a_async.yaml`登记单位、默认值和`sensor_noise_seed`；异步生产器及旧
  场景fixture均消费这些参数。
- 默认FOV/量程为`null`，噪声和扫描/曝光持续时间为0，保持既有点数、像素值和时间边界。
  不新增物理标定或硬件性能声明。

## 验证

使用解释器`/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python`完成：

- fake传感器新增5项测试通过：默认兼容、FOV/量程拒绝、运动Doppler语义、随机种子
  可重复性、非法参数fail-closed。
- motion 7项、contract 14项、scenario 5项、async 34项、ROS wrapper 10项、wire 7项
  均通过；full IR 640x512序列化仍保持327680个0.5像素。
- 未启动新的大图ROS性能短测；本改动不产生PERF-01端到端时延结论。

## 结论与边界

fake Radar/IR现在已有“功能级参数化实现”，但仍不是真实Radar/IR驱动。没有真实设备采样
时钟、辐射/电磁物理、真实丢包链路、机载资源或研究模型质量证据。LiDAR监督边界不变，
不进入在线SensorBundle、感知forward、定位或mapping。5 ms同步门限、严格拒绝理由和20 ms
目标不变。

## 下一步

先在短场景中登记一组明确的FOV/量程/噪声配置并核对点数、时间和未知语义，再决定是否扩展
IR空间热点/温度场或真实设备适配；不把fixture参数直接当作硬件标定值。
