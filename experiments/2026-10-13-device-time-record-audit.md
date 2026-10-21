# EXP-20261013-004：设备时间落盘记录与输入审计

## 1. 基本信息

- 日期：2026-10-13
- 责任角色：system_architect / sensor_engineer
- 关联任务：IFACE-01、SENS-TRAIN-01
- 范围：JSON-ready设备记录封装、字段一致性和单设备流审计
- 前置：EXP-20261013-003型号字段合同

## 2. 目的与边界

把ARS548和Mid-360的型号字段合同固化为可落盘记录，明确分离设备采集时间和主机
接收时间。当前无真实硬件、无原始UDP/以太网记录、无目标平台和功耗输入，因此本次
只做纯函数和固定负例，不启动ROS记录器、设备驱动、PERF-01、长训练或对照试验。

## 3. 记录合同

每条`device_time_record_v1`必须保存：

- `device_timestamp_ns`：设备字段产生的采集时间；
- `receive_timestamp_ns`和`receive_clock_id`：主机接收时间及接收时钟域；
- `run_id`、`clock_id`、`sample_id`、`frame_id`和`device_model`；
- `payload`：`device_time_v1`解码结果；
- `time_mapping_status=unmapped`、空的offset/drift/error和
  `time_sync_verified=false`。

ARS548记录保持列表级时间，检测项逐点时间为空；Mid-360逐点时间必须满足
`point_time_ns=observation_timestamp_ns+offset_time_ns`。Mid-360使用原始包
`time_type`时，记录的`transport`必须声明原始包元数据来源；只使用`CustomMsg`时
同步来源保持未提供。记录流不允许重复`sample_id`或混合设备/时钟身份。

## 4. 实现

新增[`device_time_record.py`](../sensors/ufm_sensors/device_time_record.py)，提供：

- `make_ars548_record`：分离ARS548设备列表时间与主机接收时间；
- `make_mid360_record`：保留Mid-360逐点时间和原始包同步类型来源；
- `validate_device_time_record`：验证单条JSON-ready记录；
- `validate_device_time_stream`：验证单设备流身份和样本唯一性。

该模块不估计设备到主机的时钟偏移，不填充漂移或误差上界，不发布ROS消息；
Mid-360输出仍只属于训练监督分支。

## 5. 验证

命令：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  -B tests/test_device_time_adapter.py -q
```

结果：`Ran 13 tests ... OK`。覆盖：

- 设备时间与接收时间分离及JSON往返；
- 缺失接收时钟、篡改设备时间、虚构映射的拒绝；
- Mid-360原始`time_type`缺失传输来源的拒绝；
- Mid-360 `uint64`设备时间边界的保留；
- ARS548重复样本和混合身份流的拒绝；
- 既有ARS548/Mid-360字段适配和ROS `__slots__`对象支持。

## 6. 未完成与下一步

本次没有证明任何真实设备时钟质量。设备到位后应按以下顺序执行：

1. 记录ARS548 `DetectionList`设备时间、同步状态、原始包/驱动接收时间和丢包信息；
2. 记录Mid-360 `CustomMsg`、原始包`time_type`和设备状态，核对逐点时间回算；
3. 同时记录AircraftState和公共时钟/PPS/PTP/gPTP证据，离线估计偏移、漂移和残差；
4. 通过记录回放和时钟误差门禁后，再设计ROS记录器升级与非零扫描训练路径。

在这些输入到位前，不把`unmapped`改成已映射，不把记录审计写成真实驱动接入，
对照试验继续放在工程数据门禁和接口闭合之后。
