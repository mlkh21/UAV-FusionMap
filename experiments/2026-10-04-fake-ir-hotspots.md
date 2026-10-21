# fake IR空间热点功能级验证

编号：EXP-20261004-001  
日期：2026-10-04  
责任角色：sensor_engineer / tester  
状态：已完成；真实热成像物理、温度标定和模型质量未验收。

## 目的

在保持默认全背景图兼容的前提下，为fake IR增加可重复的二维空间结构，验证热点像素能够
经过ROS序列化、SensorBundle同步和placeholder→Local Map链路，而不改变Radar时间配对或
地图占据语义。

## 实现

`hotspots`为列表，每项字段为`x_px`、`y_px`、`radius_px`和`value`。坐标以图像左上角为
原点，按行优先写入`width * height`数组；热点覆盖圆内像素，重叠热点的`value`增量相加，
随后再叠加可选fixture噪声。所有值仍是`fixture_intensity`，不解释为温度、开尔文或辐射功率。
默认`hotspots: []`时既有背景图输出不变。

## 验证

- 新增7项fake传感器测试通过，覆盖行优先布局、圆形覆盖、热点叠加、可重复性和非法参数。
- 旧场景6项、wire 7项、ROS wrapper 10项测试通过。
- 实际命令：

```text
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01a_async_run.py --scenario parameterized_sensors \
  --duration-s 2 --port 12434
```

- 运行目录：`.runtime/runs/perf01a-async-20261004T152242994066`。
- 结果：`passed=true`；参数化发布、实际ROS传输、匹配、Bundle、占位感知、地图和清理闭合。

## 边界

本次不验证热辐射、温度转换、镜头内参、遮挡、多径、传感器坏点或真实设备时钟；不启动大图
性能测量，不改变5 ms同步门限、严格拒绝理由、20 ms目标或LiDAR在线隔离。
