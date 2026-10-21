# 参数化 fake Radar 位置噪声与动态地图 oracle

编号：EXP-20261003-004  
日期：2026-10-03  
责任角色：sensor_engineer / mapping_engineer / tester  
状态：已完成短时功能验证；不构成性能、真实性或机载验收。

## 目的

解决位置噪声使 Radar 点跨越0.5 m地图栅格后，固定静态 oracle 无法继续适用的问题。
新增独立`map_oracle: radar_points`路径：从已接收 Bundle 中的Radar点和
`T_mapping_source`计算连续坐标及体素索引，再核对地图累计cell集合、概率、observed和
最后观测时间。该 oracle 不读取地图实现内部状态，也不从地图结果反推期望。

## 配置与验证

- 场景：`parameterized_position_noise`。
- Radar：FOV 120°×30°、最大量程6 m、位置噪声标准差0.01 m、强度噪声0.05、扫描时长2 ms。
- IR：背景值0.4、噪声标准差0.01、曝光时长4 ms；随机种子23。
- 实际运行：

```text
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python \
  ros_ws/perf01a_async_run.py --scenario parameterized_position_noise \
  --duration-s 2 --port 12433
```

- 运行目录：`.runtime/runs/perf01a-async-20261003T233932170227`。
- 结果：`passed=true`；全链路严格功能、时间字段、传输身份、20个有效样本、地图累计
  cell核对和进程清理通过。
- 相关纯测试和完整PERF-01A回归在本次变更后另行执行；不启动大图性能测量。

## 边界

该结果证明位置噪声下的功能级点到栅格核对路径可运行，不证明噪声分布等同真实Radar，
也不证明地图精度、感知质量或20 ms实时目标。无回波仍不生成自由空间证据；5 ms同步门限、
严格拒绝理由和LiDAR在线隔离不变。
