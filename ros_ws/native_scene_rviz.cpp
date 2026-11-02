// Standard RViz VisualizationFrame, with owned render-target captures for acceptance.
#include <rviz/visualization_frame.h>
#include <rviz/visualization_manager.h>
#include <rviz/display_group.h>
#include <rviz/ogre_helpers/render_widget.h>
#include <OGRE/OgreRenderWindow.h>
#include <QApplication>
#include <QDateTime>
#include <QDir>
#include <QDockWidget>
#include <QPainter>
#include <QMenuBar>
#include <QMenu>
#include <QAction>
#include <QStyle>
#include <QTimer>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QStatusBar>
#include <QLabel>
#include <ros/ros.h>
#include <rosgraph_msgs/Clock.h>
#include <sensor_msgs/Image.h>
#include <csignal>
#include <cstdlib>

static volatile std::sig_atomic_t closing = 0;
static void stop(int) { closing = 1; }

int main(int argc, char** argv) {
  ros::init(argc, argv, "sensor_scene_rviz", ros::init_options::NoSigintHandler);
  QApplication application(argc, argv);
  if (argc < 2) return 2;
  rviz::VisualizationFrame frame;
  frame.setSplashPath("");
  frame.initialize(argv[1]);
  frame.setWindowTitle("RViz - Radar / IR / placeholder map (functional scene)[*]");
  frame.resize(1500, 950);
  frame.show();
  for (auto* dock : frame.findChildren<QDockWidget*>()) {
    if (dock->windowTitle().contains("IR intensity")) {
      frame.addDockWidget(Qt::RightDockWidgetArea, dock);
      dock->setMinimumWidth(340);
    }
  }
  QTimer::singleShot(1000, [&]() {
    auto* displays = frame.getManager()->getRootDisplayGroup();
    for (int i = 0; i < displays->numDisplays(); ++i)
      if (displays->getDisplayAt(i)->getName().contains("IR intensity"))
        displays->getDisplayAt(i)->setEnabled(true);
  });
  const char* directory = std::getenv("UFM_SCENE_FIGURES");
  const char* request_file = std::getenv("UFM_SCENE_CAPTURE_REQUEST");
  const bool guard = std::getenv("UFM_SCENE_CLOCK_GUARD") != nullptr;
  const bool flight_view = std::getenv("UFM_FLIGHT_SCENE_VIEW") != nullptr;
  QLabel* source_status = guard ? new QLabel("Waiting for source clock",&frame) : nullptr;
  if (source_status) frame.statusBar()->addPermanentWidget(source_status);
  bool has_clock = false, history = false;
  ros::WallTime last_clock;
  uint64_t stamp_ns = 0;
  uint64_t infrared_messages = 0, infrared_stamp_ns = 0;
  ros::NodeHandle node;
  ros::Subscriber infrared_sub;
  if (flight_view) infrared_sub = node.subscribe<sensor_msgs::Image>("/uav/sensors/infrared/raw", 2,
      [&](const sensor_msgs::Image::ConstPtr& msg) {++infrared_messages;infrared_stamp_ns=msg->header.stamp.toNSec();});
  auto clock_sub = node.subscribe<rosgraph_msgs::Clock>("/clock", 2,
      [&](const rosgraph_msgs::Clock::ConstPtr& msg) {
        has_clock = true; last_clock = ros::WallTime::now(); stamp_ns = msg->clock.toNSec();
      });
  auto receipt = [&](const QString& name, const QJsonObject& value) {
    if (!directory) return;
    QFile file(QDir(directory).filePath(name));
    if (file.open(QIODevice::WriteOnly | QIODevice::NewOnly)) file.write(QJsonDocument(value).toJson());
  };
  QTimer capture;
  bool captured = false;
  auto capture_view = [&](QString stage=QString()) {
    if (!directory) return;
    const auto base = QDir(directory).filePath((stage.isEmpty() ? "rviz-sensors-" : "rviz-motion-"+stage+"-") + QDateTime::currentDateTime().toString("yyyyMMddThhmmsszzz"));
    QPixmap image = frame.grab();
    QPainter painter(&image);
    int number = 0;
    QJsonArray targets;
    for (auto* widget : frame.findChildren<QWidget*>()) {
      auto* render = dynamic_cast<rviz::RenderWidget*>(widget);
      if (!render || !render->isVisible() || !render->getRenderWindow()) continue;
      const auto name = base + "-viewport-" + QString::number(number++) + ".png";
      render->getRenderWindow()->writeContentsToFile(name.toStdString());
      bool infrared = false;
      for (auto* parent=render->parentWidget(); parent; parent=parent->parentWidget()) {
        auto* dock=qobject_cast<QDockWidget*>(parent);
        if (dock && dock->windowTitle().contains("IR intensity")) infrared=true;
      }
      targets.append(QJsonObject{{"file",name},{"role",infrared ? "infrared" : "scene"}});
      const auto offset = render->mapTo(&frame, QPoint(0,0));
      painter.drawPixmap(offset.x(), offset.y(), render->width(), render->height(), QPixmap(name));
    }
    painter.end();
    image.save(base + ".png");
    bool radar_enabled=false, infrared_enabled=false;
    auto* displays=frame.getManager()->getRootDisplayGroup();
    for (int i=0;i<displays->numDisplays();++i) {
      auto* display=displays->getDisplayAt(i);
      if (display->getName().contains("Radar point cloud")) radar_enabled=display->isEnabled();
      if (display->getName().contains("IR intensity")) infrared_enabled=display->isEnabled();
    }
    if (!stage.isEmpty()) receipt("rviz-"+stage+".json",QJsonObject{
        {"file",base+".png"},{"history",history},{"clock_ns",QString::number(stamp_ns)},
        {"raw_displays_enabled",radar_enabled && infrared_enabled},
        {"radar_enabled",radar_enabled},{"infrared_enabled",infrared_enabled},
        {"infrared_messages",QString::number(infrared_messages)},{"infrared_stamp_ns",QString::number(infrared_stamp_ns)},
        {"render_targets",targets},
        {"source_status",source_status ? source_status->text() : QString()}});
  };
  auto* save = frame.menuBar()->actions().first()->menu()->addAction(
      frame.style()->standardIcon(QStyle::SP_DialogSaveButton), "Save sensor view PNG");
  QObject::connect(save, &QAction::triggered, [&](){ capture_view(); });
  QObject::connect(&capture, &QTimer::timeout, [&]() {
    if (!guard && !captured) { captured = true; capture_view(); }
  });
  capture.start(15000);
  QTimer stop_timer;
  QString last_request;
  QObject::connect(&stop_timer, &QTimer::timeout, [&]() {
    ros::spinOnce();
    if (closing) frame.close();
    if (!guard) return;
    const bool stale = has_clock && (ros::WallTime::now()-last_clock).toSec() >= 3.;
    source_status->setText(stale ? "History: source clock stopped" : has_clock ?
        "JSBSim truth | t="+QString::number(stamp_ns/1.e9,'f',3)+" s | functional scene" : "Waiting for source clock");
    if (stale != history) {
      history=stale;
      auto* displays=frame.getManager()->getRootDisplayGroup();
      for (int i=0;i<displays->numDisplays();++i) {
        auto* display=displays->getDisplayAt(i);
        if (display->getName().contains("Radar point cloud") || display->getName().contains("IR intensity")) {
          display->reset(); display->setEnabled(!history);
        }
      }
      frame.setWindowTitle(history ? "RViz - History: source clock stopped" : "RViz - JSBSim truth / Radar / IR / placeholder map");
      if (history) receipt("rviz-history-ready.json",QJsonObject{{"history",true},{"raw_displays_enabled",false}});
    }
    if (flight_view && has_clock && !history) {
      auto* displays=frame.getManager()->getRootDisplayGroup();
      for (int i=0;i<displays->numDisplays();++i) {
        auto* display=displays->getDisplayAt(i);
        if (display->getName().contains("IR intensity") && !display->isEnabled()) display->setEnabled(true);
      }
    }
    receipt("rviz-ready.json",QJsonObject{{"ready",true}});
    if (request_file) {
      QFile file(QString::fromLocal8Bit(request_file));
      if (file.open(QIODevice::ReadOnly)) {
        const QString stage=QString::fromUtf8(file.read(32)).trimmed();
        if ((stage=="before" || stage=="empty" || stage=="after" || stage=="history") && stage!=last_request) {
          last_request=stage; capture_view(stage);
        }
      }
    }
  });
  stop_timer.start(100);
  if (const char* seconds = std::getenv("UFM_RVIZ_CLOSE_AFTER_S"))
    QTimer::singleShot(int(std::atof(seconds) * 1000), &frame, &QWidget::close);
  std::signal(SIGINT, stop);
  std::signal(SIGTERM, stop);
  return application.exec();
}
