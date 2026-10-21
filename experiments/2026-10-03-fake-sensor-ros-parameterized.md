# 参数化 fake Radar/IR ROS 短链路

编号：EXP-20261003-003  
日期：2026-10-03  
责任角色：sensor_engineer / integration_engineer / tester  
状态：已完成短时功能验证；不构成真实性、性能或机载验收。

## 目的

验证启用参数后的fake Radar/IR能沿独立异步发布器、sensors匹配、SensorBundle、
placeholder感知和Local Map完整闭合，同时保持原有5 ms同步门限、严格拒绝理由和unknown语义。

## 配置与命令

场景：`parameterized_sensors`；Radar/IR相位分别为2 ms/4 ms；Radar FOV为120°×30°、
最大量程6 m、强度噪声0.05、扫描时长2 ms；IR背景值0.4、噪声0.01、曝光时长4 ms；
随机种子23。位置噪声在该静态地图严格oracle场景中关闭，单元测试单独覆盖非零位置噪声。

实际入口：

```text
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01a_async_run.py --scenario parameterized_sensors \
  --duration-s 2 --port 12432
```

## 结果

- 首次试运行目录：`.runtime/runs/perf01a-async-20261003T195431579587`，严格校验失败，
  原始错误为`map: occupied/unknown semantics changed`；保留该失败证据。
- 根因不是传感器链路或地图更新错误，而是位置噪声0.01 m使静态回波跨越0.5 m地图格，
  与固定静态oracle冲突。未放宽校验，改为在本场景关闭位置噪声。
- 修正运行目录：`.runtime/runs/perf01a-async-20261003T195734311200`，`passed=true`，
  20个有效Bundle/Occupancy/Map样本闭合，Radar/IR实际采样时间保持，2 ms/4 ms时间窗
  参数生效，进程和资源清理通过。
- 没有启动大图性能测试，没有产生20 ms性能结论；真实设备采样时钟、物理真实性、资源
  和研究模型质量仍未验收。

## 结论

参数化fake Radar/IR已完成一次真实ROS短链路验证。位置噪声会改变离散地图占据格，后续若
启用它，必须预登记动态地图oracle或连续空间误差门槛，不能复用固定静态格点校验。
