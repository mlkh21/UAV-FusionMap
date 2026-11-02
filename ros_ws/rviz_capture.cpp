// Read only RViz's own render target; never capture unrelated desktop windows.
#include <rviz/render_panel.h>
#include <rviz/visualization_frame.h>
#include <rviz/visualization_manager.h>
#include <OGRE/OgreRenderWindow.h>
#include <exception>
#include <string>

extern "C" const char* ufm_capture_rviz(void* frame, const char* path)
{
  static thread_local std::string error;
  try {
    auto* render_panel = static_cast<rviz::VisualizationFrame*>(frame)->getManager()->getRenderPanel();
    render_panel->getRenderWindow()->writeContentsToFile(path);
    return nullptr;
  } catch (const std::exception& exception) {
    error = exception.what();
    return error.c_str();
  }
}
