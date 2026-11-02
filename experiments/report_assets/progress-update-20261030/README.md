# 真实高程与场景改进后的报告

日期：2026-10-30；版本：v3；状态：已完成；主责任：integration_engineer。

- [Word报告](贴地飞行第二部分进度汇报2026-10-30.docx)
- [PDF报告](贴地飞行第二部分进度汇报2026-10-30.pdf)
- [本版正文快照](../../../docs/REPORT_20261030_v3.md)
- [后续四方向整编版](../progress-integrated-20261030/README.md)
- [工具、入口和验证说明](../../../docs/REPORT_IMPROVEMENTS_20261030.md)
- [此前15页版本](../progress-20261030/README.md)

新版17页、9幅图。延续“完成工作与后续安排”的表达方式，不展开源码修改和排错过程。
图3改为四川山地区域的真实Copernicus GLO-30高程，增加同数据的RViz连续地表；
图6补齐0.1秒和1.0秒的同次RViz点云/IR对照；场景扩大为180×140米、30个分散障碍物，
Radar在实际输出中加入稀疏与测量误差，本次每帧161～256点。

## 图片来源

[sources.json](sources.json)记录每幅图的源文件与处理方式。
Gazebo/RViz截图直接复制原生渲染目标；`motion-observations.png`由两幅完整RViz截图排版，外加时间标识。
`infrared-comparison.png`来自原始IR消息，以同一0～1强度范围转换灰度，并列呈现两个时刻。
真实高程平面色彩图与三维曲面均使用同一201×201像元裁剪。

| 图 | 来源 |
| --- | --- |
| 图1、图5a/5b | 本次改进场景的实际Gazebo渲染 |
| 图2、图4、图6 | 同一JSBSim运行的原生RViz窗口，两个时刻分别为0.1秒、1秒 |
| 图3、图3b | Copernicus GLO-30 Public四川N30/E103真实DSM，EGM2008高程 |
| 图7 | 同次运行的原始320×240 IR消息，固定灰度范围 |

地形来源：[公开数据说明](https://copernicus-dem-30m.s3.amazonaws.com/readme.html)及其
[许可入口](https://spacedata.copernicus.eu/en/web/guest/collections/copernicus-digital-elevation-model/#Licencing)。
本区域中心为103.25°E、30.75°N，高程约1226～2741米；不是旧2×2合成样例，也未和Gazebo障碍物做地理融合。

## 核对与保留

同一LibreOffice环境下，9月18日原报告14页、此前修订版15页、本版17页。
已核对正文、嵌入图片及全部PDF文字，浏览各页并放大检查真实地形与运动观测页。
此前Word/PDF和Markdown留存不覆盖。
[最终交付核对](validation.json)包含页数、195块文字、9幅嵌入图、39个本地引用及实际运行/回归结果。

导出：

```bash
bash ros_ws/sim01_env.sh /home/zxj/anaconda3/envs/Radar-Diffusion/bin/python experiments/report_assets/progress-20261030/render_report.py --output-dir experiments/report_assets/progress-update-20261030
```

详细运行与故障修正记录见[EXP-20261030-017](../../2026-10-30-report-terrain-radar-improvements.md)。
