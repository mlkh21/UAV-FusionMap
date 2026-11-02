# EXP-20261029-005：S09/C原生图、恢复与软件全矩阵交接

日期：2026-10-29；主责任：tester；状态：已完成（冻结合成软件范围）。
设计与入口：[P5-SW-03说明](../docs/P5_SW03_NATIVE_DELIVERY_20261029.md)、ADR-041。

## 目的与前置核对

补齐SW-01已冻结但SW-02明确未执行的四个S09/C子例，交付真实原生窗口与软件矩阵证据。
核对feature/engineering-initialization与大量既有dirty/untracked文件，全部保留；
检查.runtime忽略规则及真实生产消费链，不构建外层catkin、不改公共协议或默认入口。
运行前通过sim01_env.sh确认sys.executable为用户指定Radar-Diffusion解释器。
只使用已有Noetic/Gazebo11/RViz/Qt/Ogre与本仓生成类型，无新依赖、Hash或研究仓库写入。

预期仍来自原tests/fixtures/p5_combination_expectations.json；运行前保存输入与预期副本，
未修改冻结值。实际图/服务/JSONL用于构造收据，执行结束后才与expected比较。
新增文件、四个子例的真实注入、时间与清理语义详见交付说明。

## 实际执行

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -c 'import sys; print(sys.executable)'
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B ros_ws/p5_delivery_run.py --ab-run .runtime/runs/p5-combination-20261029T120350694666 --port 11731
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python -B tests/p5_fixture_run.py --full
```

真实ROS/GUI需要loopback socket与X显示，按已授权任务在宿主权限执行；不更改系统/Conda设置。
原生入口内部指定自己的Master、GUI HOME/缓存及软件渲染环境，不接现有飞行会话。

## 结果与证据

| 运行/范围 | 实测结果 |
| --- | --- |
| [最终S09报告](../.runtime/runs/p5-delivery-20261029T123816555451/report.json) | 4/4，9事件/9检查点/12项比较；三种图错误实际拒绝，失败路径无地图快照；哨兵在每子例清理后仍存活，最后由父监督器正常退出 |
| [新run](../.runtime/runs/p5-delivery-20261029T123816555451/S09.recover_view/new-run.json) | 旧run实际occupied/revision 1及四点组；新run地图revision 0、无概率/观测时间；新地形实例、revision 1；旧pin返回provider_instance_mismatch，旧客户端组清空 |
| [全矩阵](../.runtime/runs/p5-delivery-20261029T123816555451/full-matrix.json) | 37/37、253事件、95检查点、228项独立比较；复核A/B源码/冻结合同与收据，ab_rerun=false；未重跑33个A/B子例，未改其历史产物 |
| [Gazebo/RViz](../.runtime/runs/sensor-scene-20261029T123831232102/manifest.json) | Radar 11、IR 20、Bundle 10、地图9；1790点/594cell，表面距离P99约7.63e-7m；热箱移动1.5m改变14779个IR像素/408个Radar点并恢复；原生窗口/像素/图隔离及清理通过 |
| [独立地形](../.runtime/runs/terrain-delivery-20261029T123853103628/validation.json) | 12项客户端/图/历史显示检查，18状态/128 Marker消息；22事件公共完整记录、8条查询结果真实执行回放；四图像素与清理通过 |
| [回归](../.runtime/runs/p5-sw01-20261029T123830392631/full-result.json) | 新增6项，定向45/45（2.229s），全仓819/819（61.561s）；742次真实genpy序列化回归通过 |
| [宿主清理](../.runtime/runs/p5-delivery-20261029T123816555451/host-cleanup-audit.json) | 宿主/proc核对36个受管命令，remaining_owned与remaining_run_matches均为空；不是仅在沙箱PID命名空间检查 |

恢复子例公开收据实际91445字节、状态90条，均在每话题256条/总16MiB测试限额内。
约48.16s包含旧/新启动、两套原生图形验收与清理，不作为性能数字。
截图已人工查看RViz Radar/IR/占据全窗及独立recorded地形，另有自动像素检查。
[报告素材索引](report_assets/p5-delivery-20261029/README.md)逐图说明来源和边界。
交付文档检查14页、724条本地相对链接均有效，三个新验收源码与实际运行快照逐字节相同；
八张PNG复制后逐字节核对，合计727587字节。git diff --check通过。

## 初次失败与修复

保留以下目录，不自动换种子或覆盖失败结果：

1. [123528533293](../.runtime/runs/p5-delivery-20261029T123528533293/report.json)：首个clock冲突子例及清理通过，父监督器因Python 3.8没有Path.is_relative_to失败。改为relative_to异常检查，不改业务或预期。
2. [123704370958](../.runtime/runs/p5-delivery-20261029T123704370958/report.json)：clock冲突/坏身份通过；缺订阅子例启动等待期间收到关闭而以1退出，未计通过；恢复子例图白名单漏掉rospy自动clock订阅，未进入恢复/原生验证。允许基础设施clock，错误remap支路保持空连接但不发业务消息，使图拒绝与正常清理可独立核对。最终另开目录重跑四例。

前两次失败不追认为全矩阵通过，失败收据和日志继续保留；最终使用修复后的新源码副本。

## 修改清单与限制

新增ros_ws/p5_delivery_run.py、tests/p5_delivery_case.py、p5_delivery_checks.py及test_p5_delivery.py；
新增本记录、交付说明与报告素材目录；同步PROJECT_STATUS、DEVELOPMENT_PLAN、STAGE_ADVANCE_PLAN、
SYSTEM_ARCHITECTURE、ADR-041、EXPERIMENT_LOG、组合设计及既有交付/显示索引。
修改原因是补齐已冻结的C范围，不新增算法、接口、Provider或客户端功能。

完整Phase 4/5、真实设备/标定、模型质量、DEM/占据融合、PX4联动飞行、RSS/功耗/正式PERF-01
仍未验证。六组owner/封存数量仅独立声明，不能从全矩阵228项推断公开生命周期接口存在。
ENV-03外部副本仍阻塞，仓内源码副本及截图不是独立灾备；未复制到外部或自动发布报告。
恢复方式为关闭本轮窗口/监督器，仅回收其自有进程；重新启动产生新run，不混用地图或pin。
