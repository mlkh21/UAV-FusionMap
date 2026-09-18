# SIM-01A 状态/时钟接入运行说明

日期：2026-09-14；责任：Technical Lead / integration_engineer。
状态：本机独立构建、44项单元/契约、11项ROS fixture及轻量静止联调通过。
证据：[EXP-20260914-002](../experiments/2026-09-14-sim01a-implementation.md)。

## 1. 环境与数据通路

所有新Python执行使用Conda Radar-Diffusion 3.8.12；Noetic提供ROS库。
`sim01_env.sh`在独立子进程激活环境，不改终端Foxy(1)/Noetic(2)选择。
Conda用户site禁用，pymavlink 2.4.49和netifaces 0.10.4由现有安装复制到项目
`.runtime/deps/python-radar`，两个source.json登记来源；没有安装到Conda或系统。
netifaces是CPython3.8 amd64扩展，换解释器/机器需重新验证ABI和依赖。

```text
PX4/JSBSim → MAVROS /mavlink/from
  → simulation 源解码、预热、时钟覆盖
      → /clock + /uav/sim/state（world_ned/body_frd）
          → sensors 坐标适配、接收时钟覆盖
              → /uav/sensors/state（odom/base_link）
```

状态是PX4估计，不是真值；位姿/速度协方差和confidence保持不可用。
虚拟原点、坐标及时间语义以[接口](../docs/DATA_FORMAT.md)和
[坐标规范](../docs/COORDINATE_SYSTEM.md)为准。本步不广播TF。
业务库从simulation/sensors源码目录加载；未验收脱离仓库的独立安装空间。

## 2. 复现命令

以下命令从UAV-FusionMap根目录执行，已有SIM-00A/B项目资产是前置条件。
Python入口没有回退到系统Python；rosmaster shell入口同样显式调用Conda。

```bash
cd /home/zxj/catkin_ws/src/UAV-FusionMap
bash ros_ws/sim01_env.sh python -c 'import sys; print(sys.executable)'
bash ros_ws/sim01_env.sh python -m unittest discover -s tests -p 'test_sim01*.py' -v
```

构建只处理本仓库ros_ws/src，生成输出都放.runtime/ros：

```bash
cd /home/zxj/catkin_ws/src/UAV-FusionMap/ros_ws
bash sim01_env.sh python /opt/ros/noetic/bin/catkin_make \
  --source /home/zxj/catkin_ws/src/UAV-FusionMap/ros_ws/src \
  --build /home/zxj/catkin_ws/src/UAV-FusionMap/.runtime/ros/build \
  -DCATKIN_DEVEL_PREFIX=/home/zxj/catkin_ws/src/UAV-FusionMap/.runtime/ros/devel \
  -DCMAKE_INSTALL_PREFIX=/home/zxj/catkin_ws/src/UAV-FusionMap/.runtime/ros/install \
  -DPYTHON_EXECUTABLE=/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -j4
cd /home/zxj/catkin_ws/src/UAV-FusionMap
```

重建固定历史记录的完整离线接口链（输出路径必须尚不存在）：

```bash
bash ros_ws/sim01_env.sh python tests/check_sim01_history.py \
  .runtime/runs/sim00b-20260912T123817/mavlink.jsonl \
  .runtime/runs/history-sim01a-new.json
```

实际ROS fixture和静止联调：

```bash
bash ros_ws/sim01_env.sh python ros_ws/sim01_smoke.py --fixture
bash ros_ws/sim01_env.sh python ros_ws/sim01_smoke.py
```

每次创建独立run_id和新产物目录，Master使用11331。端口占用/既有PX4时停止本次任务，
不停止已有进程。只有同一时刻一个本项目冒烟运行；不要并发运行这两个命令。
常规联调不发送解锁、起飞或自主控制命令，目标是至少30秒valid状态跨度和500对状态。
初次等待和断流使用单调墙钟；轻量监督器最多180墙秒，源时钟上限600秒。
桥接TCP4560绑定INADDR_ANY，不能将本入口描述为所有端口只绑定回环。

## 3. 配置与停止

共享配置：[sim01_state.yaml](../configs/sim01_state.yaml)。稳定窗口10秒源时间，
启动等待60墙秒、源双流看门狗各2秒、等待队列100条/0.5墙秒，quat容差0.001。
ROS1参数服务器32位整数限制使warmup_stable_sim_ns使用十进制字符串，节点读入后
转Python int；消息timestamp仍为int64整数纳秒，不改变业务采样时间。
这些参数是首次接口冒烟值，PERF-01另定高速预算。

simulation：PREPARING允许未输出valid前的估计器reset并重新观察；ACTIVE后reset、
任意阶段IMU回退或有效源断流进入FAULT，不再输出valid，发布终止和ERROR诊断。
sensors：终止优先清缓存锁run，或接收clock回退锁run并持续ERROR。
实际联调观察器收到终止/致命诊断返回失败，监督器结束本次进程组并写清理记录。
节点留活以发送终止；手工启动时操作者必须处理ERROR和重启新run，不能只看进程存在。

## 4. 本轮结果与限制

固定历史：6051 clock、2407 accepted odometry、准备期2次reset，2103源/适配状态；
首valid为16.051999秒，不补发预热历史。本机轻量实测：605对状态、2302 clock，
valid跨度30.196秒；采样时间、帧、坐标轴、未知质量和身份关联检查通过。
所有被记录的8个Python进程及本次后代实际可执行文件均属于Radar-Diffusion。
11项ROS fixture覆盖状态先到、时钟不足/覆盖、重复、等待超时、终止优先和run锁定。
当前所有本次进程退出、已知端口释放；失败运行完整保留。

尚未执行300秒bag记录回放、暂停/倍速/断流下的整run停止、40分钟或高速飞行。
终止传播已测，致命事件到监督停止的实现已审查；异常整run停止另在SIM-01C实测。
R-10的32位微秒边界和节奏疑点未修改；身份账本保留有限run记录，长期常驻内存另验。
GPU与研究模型未加载，不能据本轮结果声明模型质量或机载实时能力。
