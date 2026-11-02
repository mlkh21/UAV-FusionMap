# P5软件交接报告素材

日期：2026-10-29；主责任：tester；来源：P5-SW-03原生Gazebo/RViz实际验收。
场景：[sensor-scene-20261029T123831232102](../../../.runtime/runs/sensor-scene-20261029T123831232102/manifest.json)；
独立地形：[terrain-delivery-20261029T123853103628](../../../.runtime/runs/terrain-delivery-20261029T123853103628/manifest.json)。
图片复制自本轮窗口自身Qt/Ogre渲染目标，未使用旧图代替新运行。
统一[报告正文](../../../docs/REPORT_20261029.md)已将八图编入工程进展说明；
启动/查询/回放及剩余门槛见[交付清单](../../../docs/SOFTWARE_DELIVERY_20261029.md)。

| 图片 | 中文图注与边界 |
| --- | --- |
| [Gazebo场景](gazebo-scene.png) | 功能级固定翼传感器场景，显示飞机、墙体及冷热物体。飞机固定，未接PX4/JSBSim联动飞行。 |
| [RViz全窗](radar-ir-map.png) | 标准RViz显示Radar点云、IR热强度代理和Radar占位占据；本轮1790回波、594占据cell。不是研究模型预测或真实融合质量结果。 |
| [Radar与地图视口](radar-map-viewport.png) | 高度着色回波与占位体素。未观测空间仍未知，不由无回波推导free；灰色为过期历史。 |
| [IR视口](ir-viewport.png) | 同源场景热强度投影，32FC1 fixture_intensity的灰度显示，不是温度或真实辐射测量。 |
| [独立地形current](terrain-current.png) | 合成DTM中心高程1/13/14m；绿色为已知高度质量，蓝色为缺失质量，no-data不画表面。该fixture未注册到Gazebo场景。 |
| [独立地形stale](terrain-stale.png) | 运行授权到期后橙色历史几何，保留原高程；不视为当前可用或自由空间。 |
| [独立地形unavailable](terrain-unavailable.png) | clock传输失效后清除彩色几何，保留不可用状态，不使用旧高度充当当前结果。 |
| [独立地形recorded](terrain-recorded.png) | 公共三文件记录实际执行回放后显示历史高程，明确recorded及revision；与live分开，不发布到场景坐标系。 |

场景与地形分窗、分Master查看，没有共同地理注册，不可把两组图片拼成同一空间的融合图。
[验收说明](../../../docs/P5_SW03_NATIVE_DELIVERY_20261029.md)、
[实验记录](../../2026-10-29-phase5-native-delivery.md)包含实际图、故障、清理与回归证据。
软件矩阵37例通过不等于完整Phase 5、高速实时、真实DEM、机载资源或飞行验收通过。
