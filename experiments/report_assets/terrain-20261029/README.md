# 地形公共接口软件演示素材（2026-10-29）

来源：[EXP-20261029-001](../../2026-10-29-m5-terrain-delivery.md)，
最终实际ROS/RViz run：`.runtime/runs/terrain-delivery-20261029T095312938935/`。
图片为本次自有RViz/Ogre渲染目标读回，非浏览器或示意绘图。

| 图片 | 可用中文图注 |
| --- | --- |
| [01-current.png](01-current.png) | 合成DTM地形公共查询显示：绿色为当前且高度质量可用的中心样本，蓝色为高度存在但完整质量缺失；no-data不生成零高程表面。 |
| [02-stale.png](02-stale.png) | 运行授权到期后保留原高程但显示为过期橙色；不刷新安装/采集时间，不将地形转为占据或自由空间。 |
| [03-unavailable.png](03-unavailable.png) | clock断流导致地形不可用，显示器清除全部当前地形样本；背景网格不是地形数据。 |
| [04-recorded.png](04-recorded.png) | 公共记录严格执行回放后在独立历史命名空间显示，明确标记recorded；不发送到live服务或话题。 |

本素材只展示独立地形公共接口软件能力。图中不是实际DEM、真实标定/模型预测、占据融合、
Gazebo/PX4同场景地理注册或机载性能验收；原场景/Radar/IR素材仍见此前sensor-scene目录。
原始图、像素结果和录制/回放收据保留于上述run，文件未自动发布到外部。
