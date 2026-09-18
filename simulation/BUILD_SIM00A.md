# SIM-00A：依赖准备与隔离构建

日期：2026-09-12；主责任角色：simulation_engineer。
状态：本机依赖解析与构建已通过；仿真启动、遥测和ROS数据闭环尚未验证。
关联：[验证方案](../docs/SIMULATION_VALIDATION_PLAN.md)、
[实验记录](../experiments/2026-09-12-sim00a-build.md)。

## 1. 已建立的构建基础

本任务将依赖解包到本仓库`.runtime/`，复制固定提交的PX4及其已初始化子模块，
在独立目录构建。没有使用sudo、apt安装、pip安装或修改系统/研究环境。
MAVROS使用取得的官方二进制包；PX4和独立JSBSim桥接程序由源码构建。

| 项目 | 本次实际值 |
| --- | --- |
| 系统基础 | Ubuntu 20.04.6，现有/opt/ros/noetic |
| 编译工具 | /usr/bin/gcc与g++ 9.4.0，CMake/Ninja；系统Python 3.8.10 |
| PX4 | v1.13.3，1c8ab2a0d7db2d14a6f320ebd8766b5ffaea28fa |
| JSBSim桥接 | 68de2cc63ded9a0d6641d45e9eb3ed2b43454cba |
| JSBSim | 开发包1.1.13，发布资产构建号986，amd64/focal；链接libJSBSim.a |
| MAVROS | 1.20.1-1focal.20250520.005419 |
| MAVLink头文件包 | 2025.5.5-1focal.20250505.181801；桥接显式使用include/mavlink/v2.0 |
| GeographicLib / geoid | 1.50.1-1build1 / EGM96-5 |

隔离的是新增依赖、源码、构建输出和命令环境。现有系统库、Noetic和系统Python用户
目录仍被读取，这不是完整容器镜像或异机恢复验收。Python依赖包括empy 3.3.2、
kconfiglib 14.1.0、jinja2 3.1.6、jsonschema 4.23.0、numpy 1.24.4、PyYAML 5.3.1、
packaging 20.3、toml 0.10.0、genmsg 0.6.1及pymavlink 2.4.49。

## 2. 资产位置与来源

下列路径均相对UAV-FusionMap根目录；`.runtime/CATKIN_IGNORE`阻止外层catkin扫描。

| 位置 | 内容 |
| --- | --- |
| .runtime/downloads/debs/ | 8个原始deb：JSBSim开发包及7个APT依赖 |
| .runtime/downloads/metadata/ | APT下载URL/大小/SHA256、包控制信息、JSBSim发布元数据 |
| .runtime/downloads/egm96-5.tar.bz2 | 原始geoid压缩包，10,225,152字节 |
| .runtime/deps/jsbsim-1.1.13/ | JSBSim开发包解包前缀 |
| .runtime/deps/ros-noetic/ | 7个APT包共同解包前缀；其中opt/ros/noetic为ROS前缀 |
| .runtime/deps/geographiclib/share/GeographicLib/geoids/ | egm96-5.pgm及随包说明 |
| .runtime/src/px4-v1.13.3/ | 固定提交的独立源码，含递归子模块，共33个仓库 |
| .runtime/build/px4-v1.13.3/、.runtime/build/jsbsim-bridge/ | 本项目构建输出 |
| .runtime/logs/sim00a/ | 命令、构建日志、检查结果与源码清单 |
| .runtime/ros/home/、.runtime/ros/logs/ | ROS缓存与后续日志位置 |

JSBSim来自[官方v1.1.13开发包](https://github.com/JSBSim-Team/jsbsim/releases/download/v1.1.13/JSBSim-devel_1.1.13-986.focal.amd64.deb)，
发布元数据与本地资产大小32,486,574字节一致，包内版本和架构相符。
EGM96来自[GeographicLib发布资产](https://downloads.sourceforge.net/project/geographiclib/geoids-distrib/egm96-5.tar.bz2?use_mirror=autoselect)，
解包后PGM为18,671,448字节，GeoidEval实际读取通过；它不是本项目DEM地图融合实现。

APT精确包版本如下，7个文件均与本机APT索引的SHA256及大小一致：

| 包 | 版本 |
| --- | --- |
| libgeographic19、geographiclib-tools、libgeographic-dev | 1.50.1-1build1 |
| ros-noetic-mavlink | 2025.5.5-1focal.20250505.181801 |
| ros-noetic-libmavconn | 1.20.1-1focal.20250505.183037 |
| ros-noetic-mavros-msgs | 1.20.1-1focal.20250520.005026 |
| ros-noetic-mavros | 1.20.1-1focal.20250520.005419 |

Ubuntu的3个包通过HTTPS取得。ROS源HTTPS出现证书主机名不匹配后，4个ROS包使用
APT索引原有HTTP地址并核对索引SHA256，没有关闭TLS验证。取得这些包不更新系统
dpkg数据库，也不执行包安装脚本；本次验证覆盖所用库和工具，尚未实例化MAVROS插件。

本地源码用`git clone --no-hardlinks --no-checkout`逐仓复制，按清单detach到固定提交，
在新副本初始化子模块登记；原PX4和桥接保持不变。完整33仓路径与提交见
`.runtime/logs/sim00a/source-manifest.json`。恢复时逐项核对清单，不以默认分支最新版
替换缺失资产。保存的deb可用`dpkg-deb --extract <包> <新的前缀>`恢复；geoid仅提取
归档内geoids目录的普通文件。异机备份和完整恢复仍按[保存规则](../docs/VERSION_AND_ARTIFACT_POLICY.md)执行。

## 3. 独立命令环境

[环境入口](sim00a_env.sh)在清空继承环境的Bash子进程中加载
[项目前缀](../configs/sim00a_environment.bash)。调用终端的Foxy(1)/Noetic(2)选择及
Conda保持原样；不要把配置文件直接source进日常终端。

以下命令从本仓库根执行，前提是上述资产已准备。创建缓存目录后包发现无mkdir警告：

```bash
mkdir -p .runtime/ros/home .runtime/ros/logs
bash simulation/sim00a_env.sh rospack find mavros
bash simulation/sim00a_env.sh rospack plugins --attrib=plugin mavros
```

这两项只验证包和插件描述发现，不启动ROS master或节点。入口清除了父环境中的
ROS/Conda/PYTHONPATH；系统Python仍可读取已有`~/.local/lib/python3.8`依赖。

## 4. 构建命令

在本仓库根执行。以下参数对应实际成功构建；首次完整构建使用独立子进程环境，
随后通过本项目环境入口复查增量构建成功。换目录后的全新重建尚待ENV-03恢复检查。

```bash
ufm_build_root="$PWD/.runtime"
bash simulation/sim00a_env.sh /usr/bin/cmake \
  -S "$ufm_build_root/src/px4-v1.13.3" \
  -B "$ufm_build_root/build/px4-v1.13.3" -G Ninja \
  -DCONFIG=px4_sitl_default -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DPYTHON_EXECUTABLE=/usr/bin/python3 \
  -DCMAKE_C_COMPILER=/usr/bin/gcc -DCMAKE_CXX_COMPILER=/usr/bin/g++ \
  -DCCACHE=OFF
bash simulation/sim00a_env.sh /usr/bin/cmake \
  --build "$ufm_build_root/build/px4-v1.13.3" --target px4 --parallel 4

bash simulation/sim00a_env.sh /usr/bin/cmake \
  -S "$ufm_build_root/src/px4-v1.13.3/Tools/jsbsim_bridge" \
  -B "$ufm_build_root/build/jsbsim-bridge" -G Ninja \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_C_COMPILER=/usr/bin/gcc -DCMAKE_CXX_COMPILER=/usr/bin/g++ \
  -DJSBSIM_INCLUDE_DIR="$ufm_build_root/deps/jsbsim-1.1.13/usr/include/JSBSim" \
  -DJSBSIM_LIBRARY="$ufm_build_root/deps/jsbsim-1.1.13/usr/lib/libJSBSim.a" \
  -D_MAVLINK_INCLUDE_DIR="$ufm_build_root/deps/ros-noetic/opt/ros/noetic/include/mavlink/v2.0"
bash simulation/sim00a_env.sh /usr/bin/cmake \
  --build "$ufm_build_root/build/jsbsim-bridge" --target jsbsim_bridge --parallel 4
```

桥接第一次编译曾因include根目录过浅而找不到`common/mavlink.h`；改正CMake参数后
通过，没有修改第三方源码。`v2.0`是头文件布局/协议版本，不是ROS包发布版本号。

## 5. 验证结果与边界

| 检查 | 实际结果 |
| --- | --- |
| PX4配置/完整构建 | 退出码0；855个Ninja步骤，编译日志warning计数0；bin/px4为47,407,424字节 |
| 桥接最终配置/构建 | 退出码0；最终构建13个步骤；jsbsim_bridge为71,058,784字节 |
| 动态依赖 | 两个新二进制及mavros_node、libmavros.so、libmavros_plugins.so的ldd均无not found |
| MAVROS发现 | rospack解析到项目依赖前缀，插件XML可发现 |
| geoid实际读取 | GeoidEval输入0°/0°和47.458159°/8.548004°，分别输出17.1630m、47.2743m |
| 环境隔离 | 父进程为Foxy/模拟Conda污染，子进程为Noetic且不继承污染；带空格参数完整传递 |
| 环境脚本与增量构建 | 两个Bash文件语法通过，两个构建目标通过项目环境入口返回0 |

桥接日志仍有15条HIL_SENSOR/HIL_GPS字段可能未初始化的编译警告。它们需在SIM-00B
前按实际赋值和发送路径审查；编译成功不关闭R-11，也不能证明遥测字段有效。
32位微秒参数约35.8分钟范围及节奏计算风险仍保留，不在本次构建中修复。

下一项SIM-00B先审查警告、独立PID/日志和端口条件，再进行不解锁、不起飞的120秒
静止遥测短测。不要直接执行旧sitl_run.sh。本记录没有已验证的仿真启动命令。
