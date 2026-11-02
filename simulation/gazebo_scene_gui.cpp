// Native Gazebo scene screenshot control; captures only the active scene camera.
#include <gazebo/gui/GuiPlugin.hh>
#include <gazebo/gui/GuiIface.hh>
#include <gazebo/rendering/UserCamera.hh>
#include <QHBoxLayout>
#include <QPushButton>
#include <QTimer>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <cstdlib>

namespace gazebo {
class FusionSceneGui : public GUIPlugin {
 public:
  FusionSceneGui() {
    auto* layout = new QHBoxLayout(this);
    auto* save = new QPushButton("Save scene PNG", this);
    layout->addWidget(save);
    connect(save, &QPushButton::clicked, this, [this]() { Save(); });
    setStyleSheet("QPushButton {padding: 7px; color: #202a30; background: white;}");
    move(10, 10); resize(170, 48);
    auto* timer = new QTimer(this);
    connect(timer, &QTimer::timeout, this, [this]() {
      if (!gui::get_active_camera()) return;
      gui::get_active_camera()->SetCaptureData(true);
      const char* request=std::getenv("UFM_SCENE_CAPTURE_REQUEST");
      if (!request) { if (++ticks_ == 8) Save(); return; }
      Receipt("gazebo-ready.json",QJsonObject{{"ready",true}});
      QFile file(QString::fromLocal8Bit(request));
      if (file.open(QIODevice::ReadOnly)) {
        const auto stage=QString::fromUtf8(file.read(32)).trimmed();
        if ((stage=="before" || stage=="empty" || stage=="after" || stage=="history") && stage!=last_request_) {
          last_request_=stage; Save(stage);
        }
      }
    });
    timer->start(std::getenv("UFM_SCENE_CAPTURE_REQUEST") ? 100 : 1000);
  }
 private:
  void Receipt(const QString& name, const QJsonObject& value) {
    const char* directory=std::getenv("UFM_SCENE_FIGURES");
    if (!directory) return;
    QFile file(QDir(directory).filePath(name));
    if (file.open(QIODevice::WriteOnly | QIODevice::NewOnly)) file.write(QJsonDocument(value).toJson());
  }
  void Save(QString stage=QString()) {
    auto camera = gui::get_active_camera();
    const char* directory = std::getenv("UFM_SCENE_FIGURES");
    if (!camera || !directory) return;
    const QString filename = QDir(directory).filePath((stage.isEmpty() ? "gazebo-scene-" : "gazebo-motion-"+stage+"-") +
        QDateTime::currentDateTime().toString("yyyyMMddThhmmsszzz") + ".png");
    camera->SetCaptureData(true);
    camera->SaveFrame(filename.toStdString());
    if (!stage.isEmpty()) Receipt("gazebo-"+stage+".json",QJsonObject{{"file",filename}});
  }
  int ticks_ = 0;
  QString last_request_;
};
GZ_REGISTER_GUI_PLUGIN(FusionSceneGui)
}
