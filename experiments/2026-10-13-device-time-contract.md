# EXP-20261013-003：ARS548与Mid-360型号特定设备时间字段合同

## 1. 基本信息

- 日期：2026-10-13
- 责任角色：system_architect / sensor_engineer
- 关联任务：IFACE-01、SENS-TRAIN-01
- 分支：`feature/engineering-initialization`
- 范围：公开型号协议/驱动消息核对、离线纯函数适配和回归测试

## 2. 目的与边界

用户已明确项目硬件型号为Continental ARS548毫米波雷达和Livox Mid-360激光雷达。
本实验回答“根据型号能从驱动字段得到哪些时间”，不连接设备、不安装驱动、不启动
PERF-01，不测正式平台、功耗、跨设备时钟误差，也不进行对照试验。Mid-360只作为
训练监督输入，禁止进入在线SensorBundle、perception、定位、mapping和Radar+IR
模型forward。

## 3. 型号字段结论

### 3.1 ARS548

公开`DetectionList`包含：

- `timestamp_seconds`
- `timestamp_nanoseconds`
- `timestamp_syncstatus`
- `list_detections[800]`
- `list_numofdetections`

公开`Detection`包含距离、角度、径向速度、RCS和对象/分类字段，但未提供每个检测
自己的采集时间。因而适配结果只组合
`observation_timestamp_ns = seconds * 1e9 + nanoseconds`，保留同步状态原值，
逐检测`point_time_ns`和`point_time_offset_ns`设为不可用。不能把第三方ROS驱动可能
使用的接收时刻`header.stamp`替换为设备时间。

### 3.2 Livox Mid-360

官方ROS消息提供`CustomMsg.timebase`（首点时间）和每点
`CustomPoint.offset_time`（相对首点的纳秒偏移），因此可计算：

`point_time_ns = timebase + offset_time`

原始UDP包还带`time_type`：0为设备启动时间，1为gPTP/PTP，2为GPS。同步类型不在
`CustomMsg`字段中，所以只有ROS `CustomMsg`时可展开逐点时间，但必须把同步来源标为
未提供；不能从消息到达时间推断PTP/GPS。该字段合同只服务训练监督。

资料：

- [Livox Mid-360协议](https://livox-wiki-en.readthedocs.io/en/latest/tutorials/new_product/mid360/livox_eth_protocol_mid360.html)
- [Livox CustomMsg](https://github.com/Livox-SDK/livox_ros_driver2/blob/master/msg/CustomMsg.msg)
- [Livox CustomPoint](https://github.com/Livox-SDK/livox_ros_driver2/blob/master/msg/CustomPoint.msg)
- [ARS548 DetectionList](https://raw.githubusercontent.com/robotics-upo/ars548_ros/noetic/ars548_messages/msg/DetectionList.msg)
- [ARS548 Detection](https://github.com/robotics-upo/ars548_ros/blob/noetic/ars548_messages/msg/Detection.msg)

## 4. 实现与验证

新增[`sensors/ufm_sensors/device_time_adapter.py`](../sensors/ufm_sensors/device_time_adapter.py)：

- 强制`run_id`、`clock_id`、`sample_id`和`frame_id`身份完整；
- Mid-360校验点数、逐点时间偏移有序、坐标有限、时间不溢出和可选质量字段范围；
- ARS548校验秒/纳秒范围、同步状态、声明数量不超过800；
- 不估计跨设备偏移、不发布ROS消息、不改变在线SensorBundle。

回归命令：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  -B tests/test_device_time_adapter.py -q
```

实际结果：`Ran 8 tests ... OK`。覆盖Mid-360 PTP/gPTP标记、设备启动时间降级、
CustomMsg缺少同步类型、计数/顺序/非法类型、ARS548列表时间组合、固定数组声明数量
和非法输入拒绝；另验证genpy常见的`__slots__`消息对象可直接适配。

## 5. 未完成项与下一步

本实验没有取得真实驱动包、原始UDP/以太网记录、设备状态记录或逐点设备时钟与
AircraftState之间的配对样本，因此以下结论仍未完成：

1. ARS548设备时间与主机/飞控时钟的偏移、漂移和同步状态码映射；
2. Mid-360原始包`time_type`与状态信息的ROS记录路径；
3. 两设备与AircraftState的公共时钟转换及误差上界；
4. 真实外参、非零扫描ROS v0.2记录和大规模训练数据质量。

下一步是基于这份字段合同设计记录器输入审计，收到设备记录后再做离线回放和时钟
残差验证；在此之前不宣称真实驱动接入、机载实时能力或正式性能通过。对照试验继续
放在工程数据门禁和接口闭合之后。
