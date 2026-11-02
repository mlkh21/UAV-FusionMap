"""Native RViz report workbench. Launch with report_rviz_run.py for isolated Qt libraries."""
import argparse
import collections
import copy
import ctypes
import datetime
import json
import os
from pathlib import Path
import queue
import signal
import sys
import threading
import time

if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
    raise RuntimeError('Radar-Diffusion Python required')

# RViz was built against the system Qt. Limit this choice to this GUI process.
sys.path.insert(0, '/usr/lib/python3/dist-packages')
from PyQt5 import QtCore, QtGui, QtWidgets
from rviz import bindings as rviz
import sip
sys.path.remove('/usr/lib/python3/dist-packages')

import rospy
from geometry_msgs.msg import Point, PointStamped
from rosgraph_msgs.msg import Clock
from visualization_msgs.msg import Marker, MarkerArray
from uav_fusionmap_msgs.msg import MapSnapshot
from uav_fusionmap_msgs.srv import MapQuery, MapQueryRequest
from ufm_ros_contract.perf01a_codec import from_ros_snapshot
from ufm_ros_contract.query_codec import from_ros_query_result

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'application'))
from ufm_application import MapQueryClient
from ufm_application.visualization import COLORS, STATES, SnapshotView, load_recording


LABELS = dict(occupied='占据', free='自由', unknown='未知', stale='过期', unavailable='不可用')


def marker_array(frame, visible, bounds=True):
    result = MarkerArray()
    for number, state in enumerate(STATES):
        marker = Marker()
        marker.header.frame_id = frame['header']['frame_id']
        marker.ns, marker.id, marker.type, marker.action = 'public-map', number, Marker.CUBE_LIST, Marker.ADD
        marker.pose.orientation.w = 1.
        marker.scale.x, marker.scale.y, marker.scale.z = [v * .92 for v in frame['resolution']]
        marker.color.r, marker.color.g, marker.color.b, marker.color.a = COLORS[state]
        if visible.get(state, True):
            marker.points = [Point(*cell['center']) for cell in frame['cells'] if cell['state'] == state]
        result.markers.append(marker)
    edge = Marker()
    edge.header.frame_id = frame['header']['frame_id']
    edge.ns, edge.id, edge.type, edge.action = 'coverage', 0, Marker.LINE_LIST, Marker.ADD
    edge.pose.orientation.w, edge.scale.x = 1., .035
    edge.color.r, edge.color.g, edge.color.b, edge.color.a = .55, .66, .67, .55
    x0, x1, y0, y1, z0, z1 = frame['coverage']
    corners = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    if bounds:
        for i, first in enumerate(corners):
            for second in corners[i + 1:]:
                if sum(a != b for a, b in zip(first, second)) == 1:
                    edge.points.extend([Point(*first), Point(*second)])
    result.markers.append(edge)
    return result


class ReportWindow(QtWidgets.QMainWindow):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.setWindowTitle('UAV-FusionMap | ROS / RViz 地图工作台')
        self.resize(1560, 980)
        self.setMinimumSize(1060, 740)
        self.policy = SnapshotView(args.ttl_ns, args.free_threshold, args.occupied_threshold)
        self.history = collections.deque(maxlen=120)
        self.pending = queue.Queue(maxsize=1)
        self.results = queue.Queue(maxsize=1)
        self.clock_ns, self.clock_receipt = None, 0.
        self.snapshot = self.frame = self.last_query = None
        self.paused, self.replay_playing, self.query_busy = bool(args.receipt), False, False
        self.selected = 0
        self.error = ''
        self.clock_reset = False
        self.last_identity = None
        self.publisher = rospy.Publisher('/uav/report/markers', MarkerArray, queue_size=1, latch=True)
        self.subscribers = [rospy.Subscriber('/clock', Clock, self.receive_clock, queue_size=1),
            rospy.Subscriber('/uav/report/clicked_point', PointStamped, self.clicked_point, queue_size=1)]
        if args.receipt:
            self.history.extend(load_recording(json.loads(args.receipt.read_text())))
            self.snapshot = self.history[0]
        else:
            self.subscribers.append(rospy.Subscriber('/uav/map/snapshot', MapSnapshot,
                                                     self.receive_snapshot, queue_size=1))
        self.build_ui()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(200)
        self.play_timer = QtCore.QTimer(self)
        self.play_timer.timeout.connect(self.next_frame)
        self.play_timer.start(700)
        rospy.set_param('/uav/report_ui/ready', True)
        if args.exercise:
            self.exercise_step = 0
            self.exercise_queries = []
            self.exercise_captures = []
            self.exercise_timer = QtCore.QTimer(self)
            self.exercise_timer.timeout.connect(self.exercise_replay if args.receipt else self.exercise)
            self.exercise_timer.start(600)

    def build_ui(self):
        self.setStyleSheet('''QMainWindow,QWidget {background:#f4f6f7;color:#202b30;font-size:14px;}
            QLabel#title {font-size:24px;font-weight:600;} QLabel#section {font-size:15px;font-weight:600;}
            QLabel#source {background:#fff0cd;color:#684c06;padding:7px 12px;}
            QPushButton,QToolButton {background:white;border:1px solid #ccd5d7;padding:7px 12px;}
            QPushButton:hover,QToolButton:hover {background:#e7eeef;}
            QPushButton:checked {background:#d1ede6;border-color:#17876f;}
            QPushButton:disabled {color:#8b9599;} QDoubleSpinBox {background:white;padding:5px;}
            QSlider::groove:horizontal {height:5px;background:#cbd5d8;}
            QSlider::handle:horizontal {width:13px;margin:-5px 0;background:#17876f;}
            QPlainTextEdit {background:#fff;border:1px solid #d6dfe1;font-family:monospace;font-size:12px;}
            QCheckBox {padding:3px 0;} QStatusBar {background:#e8eeef;}''')
        center = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(center)
        layout.setContentsMargins(22, 16, 22, 12)
        layout.setSpacing(12)
        top = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel('UAV-FusionMap  /  地图工作台')
        title.setObjectName('title')
        top.addWidget(title)
        top.addStretch()
        self.source = QtWidgets.QLabel('等待公开地图 · 来源未确认')
        self.source.setObjectName('source')
        top.addWidget(self.source)
        layout.addLayout(top)
        toolbar = QtWidgets.QHBoxLayout()
        self.connection = QtWidgets.QLabel('ROS / 等待地图')
        toolbar.addWidget(self.connection)
        toolbar.addStretch()
        for text, callback in [('三维', lambda:self.camera('3d')), ('俯视 XY', lambda:self.camera('xy')),
                               ('复位视角', lambda:self.camera('3d')), ('截图 PNG', self.save_capture),
                               ('导出公开收据', self.export_recording)]:
            button = QtWidgets.QPushButton(text)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        layout.addLayout(toolbar)
        body = QtWidgets.QHBoxLayout()
        self.rviz = rviz.VisualizationFrame()
        self.rviz.setSplashPath('')
        self.rviz.initialize()
        self.rviz.setMenuBar(None)
        self.rviz.setStatusBar(None)
        self.rviz.setHideButtonVisibility(False)
        reader, config = rviz.YamlConfigReader(), rviz.Config()
        reader.readFile(config, str(ROOT / 'configs/report_rviz.rviz'))
        self.rviz.load(config)
        self.rviz.setStyleSheet('QToolButton {font-size:12px;padding:3px 5px;}')
        for dock in self.rviz.findChildren(QtWidgets.QDockWidget):
            dock.hide()
        self.manager = self.rviz.getManager()
        body.addWidget(self.rviz, 1)
        side = QtWidgets.QWidget()
        side.setFixedWidth(304)
        column = QtWidgets.QVBoxLayout(side)
        column.setContentsMargins(8, 0, 0, 0)
        column.setSpacing(5)
        self.heading(column, '地图与时间')
        self.metadata = QtWidgets.QLabel('尚无 MapSnapshot')
        self.metadata.setWordWrap(True)
        self.metadata.setMinimumHeight(128)
        self.metadata.setStyleSheet('font-size:13px;')
        self.metadata.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        column.addWidget(self.metadata)
        self.heading(column, '图层 / 单元状态')
        self.layers, self.counts = {}, {}
        for state in STATES:
            line = QtWidgets.QHBoxLayout()
            checkbox = QtWidgets.QCheckBox(LABELS[state])
            checkbox.setStyleSheet('padding:0;')
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self.render)
            color = QtWidgets.QLabel('■')
            color.setStyleSheet('color:rgb(%d,%d,%d);font-size:18px' % tuple(int(v * 255) for v in COLORS[state][:3]))
            count = QtWidgets.QLabel('0')
            line.addWidget(color)
            line.addWidget(checkbox)
            line.addStretch()
            line.addWidget(count)
            column.addLayout(line)
            self.layers[state], self.counts[state] = checkbox, count
        self.bounds = QtWidgets.QCheckBox('覆盖边界')
        self.bounds.setChecked(True)
        self.bounds.stateChanged.connect(self.render)
        column.addWidget(self.bounds)
        note = QtWidgets.QLabel('未列出区域：未知\n显示分类使用显式阈值；查询以地图服务为准。')
        note.setWordWrap(True)
        note.setStyleSheet('color:#687579;font-size:12px')
        column.addWidget(note)
        self.heading(column, '单点查询 / 地图坐标 · m')
        xyz = QtWidgets.QHBoxLayout()
        self.coordinates = []
        for axis, initial in zip('XYZ', (40.25, .25, .25)):
            item = QtWidgets.QDoubleSpinBox()
            item.setRange(-1e6, 1e6)
            item.setDecimals(2)
            item.setSingleStep(.5)
            item.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
            item.setPrefix(axis + ' ')
            item.setValue(initial)
            item.setFixedWidth(90)
            xyz.addWidget(item)
            self.coordinates.append(item)
        column.addLayout(xyz)
        self.query_button = QtWidgets.QPushButton('查询 MapQuery')
        self.query_button.clicked.connect(self.start_query)
        column.addWidget(self.query_button)
        self.query_status = QtWidgets.QLabel('尚未查询')
        self.query_status.setStyleSheet('font-size:18px;font-weight:600;padding:5px 0;')
        column.addWidget(self.query_status)
        self.query_details = QtWidgets.QPlainTextEdit()
        self.query_details.setReadOnly(True)
        self.query_details.setMinimumHeight(105)
        self.query_details.setMaximumHeight(120)
        column.addWidget(self.query_details)
        column.addStretch()
        footer = QtWidgets.QLabel('ROS1 Noetic · 原生 RViz\n工程功能演示 / 非飞行或模型质量验收')
        footer.setStyleSheet('font-size:12px;color:#687579')
        footer.setWordWrap(True)
        column.addWidget(footer)
        scroll = QtWidgets.QScrollArea()
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setFixedWidth(324)
        column.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)
        scroll.setWidget(side)
        body.addWidget(scroll)
        layout.addLayout(body, 1)
        playback = QtWidgets.QHBoxLayout()
        self.pause = QtWidgets.QPushButton('暂停显示')
        self.pause.setCheckable(True)
        self.pause.setChecked(self.paused)
        if self.args.receipt:self.pause.setText('继续回放')
        self.pause.clicked.connect(self.toggle_pause)
        playback.addWidget(self.pause)
        previous = QtWidgets.QPushButton('上一帧')
        previous.clicked.connect(lambda:self.step_frame(-1))
        playback.addWidget(previous)
        following = QtWidgets.QPushButton('下一帧')
        following.clicked.connect(lambda:self.step_frame(1))
        playback.addWidget(following)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, max(0, len(self.history) - 1))
        self.slider.sliderMoved.connect(self.seek)
        playback.addWidget(self.slider, 1)
        self.frame_label = QtWidgets.QLabel('公开快照 0 / 0')
        playback.addWidget(self.frame_label)
        layout.addLayout(playback)
        self.setCentralWidget(center)
        self.statusBar().showMessage('等待公开地图与同域时钟；模型后端未参与该界面验收。')
        self.camera('3d', initial=True)

    @staticmethod
    def heading(column, text):
        label = QtWidgets.QLabel(text)
        label.setObjectName('section')
        label.setContentsMargins(0, 8, 0, 3)
        column.addWidget(label)

    def receive_clock(self, msg):
        stamp = msg.clock.to_nsec()
        if self.clock_ns is not None and stamp < self.clock_ns:
            self.clock_reset = True
        self.clock_ns, self.clock_receipt = stamp, time.monotonic()

    def receive_snapshot(self, msg):
        try:
            snapshot = from_ros_snapshot(msg)
            try:
                self.pending.put_nowait(snapshot)
            except queue.Full:
                try:self.pending.get_nowait()
                except queue.Empty:pass
                self.pending.put_nowait(snapshot)
        except (ValueError, KeyError, TypeError) as exc:
            self.error = '无效快照: ' + str(exc)

    def clicked_point(self, msg):
        # ROS callbacks hand requests to the Qt thread, which owns all widgets.
        self.clicked = (msg.header.frame_id, [msg.point.x, msg.point.y, msg.point.z])

    def tick(self):
        if rospy.is_shutdown():
            self.close()
            return
        try:
            snapshot = self.pending.get_nowait()
            self.policy.frame(snapshot, snapshot['header']['timestamp'], snapshot['header']['clock_id'])
            identity = tuple(snapshot['header'][k] for k in ('run_id', 'clock_id', 'frame_id')) + (snapshot['map_id'],)
            if self.last_identity is not None and identity != self.last_identity:
                self.history.clear()
                self.last_query = None
                self.clock_reset = False
            self.last_identity = identity
            if not self.history or snapshot['revision'] > self.history[-1]['revision']:
                self.history.append(snapshot)
            if not self.paused:
                self.selected = len(self.history) - 1
                self.snapshot = snapshot
            self.error = ''
        except queue.Empty:
            pass
        except (ValueError, KeyError, TypeError) as exc:
            self.error = '无效快照: ' + str(exc)
        if hasattr(self, 'clicked'):
            frame_id, point = self.clicked
            del self.clicked
            if self.snapshot and frame_id == self.snapshot['header']['frame_id']:
                for widget, value in zip(self.coordinates, point):widget.setValue(value)
                self.start_query()
            else:
                self.last_query = None
                self.query_status.setText('不可用 / 坐标系不匹配')
                self.query_details.clear()
        try:
            result, identity = self.results.get_nowait()
            self.query_busy = False
            current = tuple(self.snapshot['header'][k] for k in ('run_id', 'clock_id', 'frame_id')) + (
                self.snapshot['map_id'],) if self.snapshot else None
            if current == identity and not self.paused and not self.args.receipt and not self.query_timed_out:
                self.last_query = result
                self.show_query(result)
        except queue.Empty:
            pass
        if self.query_busy and time.monotonic() - self.query_started > 2. and not self.query_timed_out:
            self.query_timed_out = True
            self.last_query = None
            self.query_status.setText('不可用 / 查询超时')
            self.query_details.setPlainText('单个查询仍在等待，迟到响应将丢弃。')
        self.slider.setMaximum(max(0, len(self.history) - 1))
        self.slider.setValue(self.selected)
        self.frame_label.setText('公开快照 %d / %d' % (self.selected + 1 if self.history else 0, len(self.history)))
        self.query_button.setEnabled(bool(self.snapshot) and not self.query_busy and not self.paused and not self.args.receipt)
        self.render()

    def render(self, *unused):
        if not self.snapshot:return
        historical = self.paused or self.args.receipt
        header = self.snapshot['header']
        stamp = header['timestamp'] if historical else self.clock_ns
        connected = historical or (time.monotonic() - self.clock_receipt < 3. and not self.clock_reset)
        try:
            self.frame = self.policy.frame(self.snapshot, stamp,
                header['clock_id'] if historical else self.args.clock_id, connected and not self.error)
        except (ValueError, KeyError, TypeError) as exc:
            self.connection.setText('不可用 / ' + str(exc))
            return
        self.manager.setFixedFrame(header['frame_id'])
        self.publisher.publish(marker_array(self.frame,
            {state:widget.isChecked() for state, widget in self.layers.items()}, self.bounds.isChecked()))
        source = ' + '.join(self.frame['sources'])
        self.source.setText(('公开收据回放' if historical else '实时 ROS') + '  /  ' +
                            ('合成 FIXTURE' if self.frame['sources'] == ['fixture'] else source.upper()))
        self.connection.setText('ROS / ' + ('历史帧' if historical else
            '已连接' if self.frame['available'] else '不可用 · 时钟/地图状态'))
        counts = self.frame['counts']
        for state, label in self.counts.items():label.setText(str(counts[state]))
        self.metadata.setText('地图  %s\n坐标  %s  ·  revision %d\n分辨率  %s m\n证据时刻  %s ns\n显示时刻  %s ns' % (
            self.frame['map_id'], header['frame_id'], self.frame['revision'],
            ' / '.join('%g' % v for v in self.frame['resolution']), header['timestamp'],
            stamp if stamp is not None else '不可用'))
        self.metadata.setToolTip('run: %s\nclock: %s\nsource: %s' % (header['run_id'], header['clock_id'], source))
        self.statusBar().showMessage(self.error or ('未列出区域保持未知  |  TTL %d ms  |  显示阈值 %s / %s  |  %s' % (
            self.args.ttl_ns // 1_000_000, self.args.free_threshold, self.args.occupied_threshold,
            '历史帧：不向当前服务发查询' if historical else '查询结果来自公开 MapQuery 服务')))

    def camera(self, mode, initial=False):
        view = self.manager.getViewManager().getCurrent()
        for name, value in [('Distance', 26.), ('Yaw', .85), ('Pitch', 1.56 if mode == 'xy' else .68)]:
            view.subProp(name).setValue(value)
        target = [45., 0., .5]
        if self.frame and self.frame['cells'] and not initial:
            target = [(min(c['center'][a] for c in self.frame['cells']) +
                       max(c['center'][a] for c in self.frame['cells'])) / 2 for a in range(3)]
            target[2] = .5
        focal = view.subProp('Focal Point')
        for name, value in zip(('X', 'Y', 'Z'), target):focal.subProp(name).setValue(value)

    def toggle_pause(self, checked):
        self.paused = checked
        self.replay_playing = bool(self.args.receipt) and not checked
        self.pause.setText('继续回放' if checked and self.args.receipt else '恢复实时' if checked else '暂停显示')
        self.last_query = None
        self.query_status.setText('历史帧 / 查询关闭' if checked or self.args.receipt else '尚未查询')
        self.query_details.clear()
        if not checked and self.history and not self.args.receipt:
            self.selected = len(self.history) - 1
            self.snapshot = self.history[-1]

    def seek(self, index):
        if not self.history:return
        self.paused = True
        self.pause.setChecked(True)
        self.toggle_pause(True)
        self.selected = max(0, min(index, len(self.history) - 1))
        self.snapshot = self.history[self.selected]

    def step_frame(self, delta):
        self.seek(self.selected + delta)

    def next_frame(self):
        if self.args.receipt and self.replay_playing and self.history:
            self.selected = (self.selected + 1) % len(self.history)
            self.snapshot = self.history[self.selected]

    def start_query(self):
        if self.query_busy or not self.snapshot or self.paused or self.args.receipt:return
        header = self.snapshot['header']
        if (self.args.clock_id != header['clock_id'] or self.clock_ns is None or self.clock_reset or
                time.monotonic() - self.clock_receipt >= 3.):
            self.query_status.setText('不可用 / 时钟断流或重置')
            self.query_details.clear()
            return
        request = dict(map_id=self.snapshot['map_id'], frame_id=header['frame_id'],
            run_id=header['run_id'], clock_id=header['clock_id'], query_timestamp=self.clock_ns,
            max_age_ns=self.args.ttl_ns, point=[widget.value() for widget in self.coordinates])
        self.query_busy = True
        self.query_started, self.query_timed_out = time.monotonic(), False
        self.query_status.setText('查询中…')

        def worker():
            def transport(fields):
                try:
                    rospy.wait_for_service('/uav/map/query', timeout=.8)
                    service = rospy.ServiceProxy('/uav/map/query', MapQuery)
                    return from_ros_query_result(service(MapQueryRequest(**fields)).result)
                except (rospy.ROSException, rospy.ServiceException) as exc:
                    raise OSError(str(exc))
            result = MapQueryClient(transport).query(**request)
            self.results.put((result, tuple(request[k] for k in ('run_id', 'clock_id', 'frame_id', 'map_id'))))
        threading.Thread(target=worker, daemon=True).start()

    def show_query(self, result):
        self.query_status.setText(LABELS[result['status']] + ' / ' + result['status'])
        color = COLORS[result['status']]
        self.query_status.setStyleSheet('font-size:18px;font-weight:600;color:rgb(%d,%d,%d)' %
                                       tuple(int(v * 255) for v in color[:3]))
        quality = result['uncertainty'] or {}
        self.query_details.setPlainText('p = %s  |  rev %s\nindex = %s\n证据 = %s ns\n区间/质量 = %s\n%s' % (
            '未提供' if result['probability'] is None else '%.4f' % result['probability'],
            result['revision'], result['index'], result['last_observed_timestamp'],
            quality.get('value') if quality.get('status') == 'available' else '未提供',
            result['reason'] or quality.get('source', '')))
        self.query_details.setToolTip(json.dumps(result, ensure_ascii=False, indent=2))

    def artifact_path(self, suffix):
        self.args.output.mkdir(parents=True, exist_ok=True)
        return self.args.output / ('report-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f') + suffix)

    def save_capture(self, *unused):
        path = self.artifact_path('.png')
        viewport_path = path.with_name(path.stem + '-viewport.png')
        panel = self.rviz.centralWidget()
        library = ctypes.CDLL(str(self.args.capture_library))
        capture = library.ufm_capture_rviz
        capture.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        capture.restype = ctypes.c_char_p
        error = capture(sip.unwrapinstance(self.rviz), os.fsencode(viewport_path))
        if error:raise OSError(error.decode())
        pixmap = self.grab()
        painter = QtGui.QPainter(pixmap)
        offset = panel.mapTo(self, QtCore.QPoint(0, 0))
        painter.drawPixmap(offset.x(), offset.y(), panel.width(), panel.height(), QtGui.QPixmap(str(viewport_path)))
        painter.end()
        if not pixmap.save(str(path)):
            raise OSError('screenshot save failed')
        metadata = dict(kind='own Qt widgets plus actual RViz Ogre render readback', frame=self.frame, query=self.last_query,
            viewport=str(viewport_path), viewport_rect=[offset.x(), offset.y(), panel.width(), panel.height()],
            mode='recorded snapshot' if self.paused or self.args.receipt else 'live ROS',
            scope='engineering fixture; not model quality, flight or PERF-01 acceptance')
        path.with_suffix('.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
        self.statusBar().showMessage('截图及来源记录：' + str(path))
        return path

    def export_recording(self, *unused):
        if not self.history:return
        path = self.artifact_path('-snapshots.json')
        path.write_text(json.dumps(dict(snapshots=list(self.history),
            scope='sampled public MapSnapshot history; no private map state',
            display_policy=self.frame['display_policy'] if self.frame else None), indent=2))
        self.statusBar().showMessage('已导出公开收据：' + str(path))
        return path

    def exercise(self):
        """Optional native Qt acceptance, using the actual rendered RViz window."""
        if (not self.frame or len(self.history) < 5 or
                not rospy.get_param('/uav/report_fixture/complete', False)):return
        try:
            if self.exercise_step == 0:
                self.camera('3d')
                self.start_query()
            elif self.exercise_step == 1:
                if self.query_busy:return
                if not self.last_query or self.last_query['status'] != 'occupied':
                    raise AssertionError('actual service query must be occupied')
                self.exercise_queries.append(copy.deepcopy(self.last_query))
                self.exercise_captures.append(str(self.save_capture()))
                for widget, value in zip(self.coordinates, (35.25, -6.75, .25)):widget.setValue(value)
                self.start_query()
            elif self.exercise_step == 2:
                if self.query_busy:return
                if self.last_query['status'] != 'free':raise AssertionError('actual free query failed')
                self.exercise_queries.append(copy.deepcopy(self.last_query))
                for widget, value in zip(self.coordinates, (51.25, .25, .25)):widget.setValue(value)
                self.start_query()
            elif self.exercise_step == 3:
                if self.query_busy:return
                if self.last_query['status'] != 'unknown':raise AssertionError('actual unknown query failed')
                self.exercise_queries.append(copy.deepcopy(self.last_query))
                self.layers['free'].setChecked(False)
                self.camera('xy')
            elif self.exercise_step == 4:
                self.exercise_captures.append(str(self.save_capture()))
                self.layers['free'].setChecked(True)
                self.seek(0)
            elif self.exercise_step == 5:
                if self.query_button.isEnabled():raise AssertionError('historical service query enabled')
                self.step_frame(1)
                self.export_path = str(self.export_recording())
                self.resize(1100, 780)
                self.camera('3d')
            elif self.exercise_step == 6:
                self.exercise_captures.append(str(self.save_capture()))
                self.pause.setChecked(False)
                self.toggle_pause(False)
                self.selected = len(self.history) - 1
                self.snapshot = self.history[-1]
                self.resize(1560, 980)
                for widget, value in zip(self.coordinates, (40.25, .25, .25)):widget.setValue(value)
                rospy.set_param('/uav/report_fixture/expire', True)
            elif self.exercise_step == 7:
                if self.clock_ns <= 150_000_000:return
                if self.frame['counts']['stale'] != 1352:return
                self.start_query()
            elif self.exercise_step == 8:
                if self.query_busy:return
                if self.last_query['status'] != 'stale':raise AssertionError('actual stale query failed')
                self.exercise_queries.append(copy.deepcopy(self.last_query))
                self.exercise_captures.append(str(self.save_capture()))
                rospy.set_param('/uav/report_fixture/stop_mapping', True)
                self.loss_started = time.monotonic()
            elif self.exercise_step == 9:
                if time.monotonic() - self.loss_started < 2.:return
                self.start_query()
            elif self.exercise_step == 10:
                if self.query_busy:return
                if self.last_query['status'] != 'unavailable':raise AssertionError('service loss must be unavailable')
                self.exercise_queries.append(copy.deepcopy(self.last_query))
                rospy.set_param('/uav/report_fixture/stop_clock', True)
            elif self.exercise_step == 11:
                if self.frame['available']:return
                if self.frame['counts']['free'] != 0 or self.frame['counts']['unavailable'] != 1352:
                    raise AssertionError('clock loss displayed as valid/free')
                self.exercise_captures.append(str(self.save_capture()))
                report = dict(passed=True, captures=self.exercise_captures,
                    public_recording=self.export_path, queries=self.exercise_queries, frames=len(self.history),
                    rviz_library=rviz.__name__, python=sys.executable, qt=QtCore.QT_VERSION_STR,
                    checks=['all five public query states', '3D and XY', 'layer toggle', 'seek and step',
                            'historical query disabled', 'public export', 'desktop resize',
                            'actual service loss unavailable', 'actual clock loss no free', 'stale history preserved'])
                (self.args.output / 'ui-validation.json').write_text(json.dumps(report, indent=2))
                self.close()
                return
            self.exercise_step += 1
        except Exception as exc:
            self.args.output.mkdir(parents=True, exist_ok=True)
            (self.args.output / 'ui-validation.json').write_text(json.dumps(dict(passed=False, error=str(exc))))
            self.close()

    def exercise_replay(self):
        if not self.frame:return
        try:
            if self.query_button.isEnabled():raise AssertionError('replay called current map service')
            if self.exercise_step == 0:
                self.pause.setChecked(False)
                self.toggle_pause(False)
                self.replay_start = self.selected
            elif self.exercise_step == 1:
                if self.selected == self.replay_start:return
                self.seek(len(self.history) - 1)
                self.camera('3d')
            elif self.exercise_step == 2:
                capture = self.save_capture()
                exported = self.export_recording()
                report = dict(passed=True, mode='public snapshot replay', captures=[str(capture)],
                    public_recording=str(exported), frames=len(self.history), python=sys.executable,
                    checks=['actual RViz replay render', 'play and seek', 'current service query disabled',
                            'public recording re-export'])
                (self.args.output / 'ui-validation.json').write_text(json.dumps(report, indent=2))
                self.close()
                return
            self.exercise_step += 1
        except Exception as exc:
            (self.args.output / 'ui-validation.json').write_text(json.dumps(dict(passed=False, error=str(exc))))
            self.close()

    def closeEvent(self, event):
        self.timer.stop()
        self.play_timer.stop()
        if hasattr(self, 'exercise_timer'):self.exercise_timer.stop()
        (self.args.output / 'ui-session.json').write_text(json.dumps(dict(
            sampled_frames=len(self.history), frame=self.frame, query=self.last_query,
            replay=bool(self.args.receipt), paused=self.paused, error=self.error,
            python=sys.executable, qt=QtCore.QT_VERSION_STR), ensure_ascii=False, indent=2))
        for subscriber in self.subscribers:subscriber.unregister()
        rospy.signal_shutdown('report window closed')
        event.accept()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ttl-ns', type=int, required=True)
    parser.add_argument('--clock-id', required=True)
    parser.add_argument('--capture-library', type=Path, required=True)
    parser.add_argument('--free-threshold', type=float)
    parser.add_argument('--occupied-threshold', type=float)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--exercise', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rospy.init_node('ufm_report_ui', disable_signals=True)
    app = QtWidgets.QApplication(['UAV-FusionMap RViz'])
    app.setFont(QtGui.QFont('Noto Sans CJK SC', 10))
    window = ReportWindow(args)
    signal.signal(signal.SIGINT, lambda *_:window.close())
    window.show()
    return app.exec_()


if __name__ == '__main__':
    sys.exit(main())
