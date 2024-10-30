from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import cv2

class CameraView(QWidget):
    clicked = pyqtSignal()
    double_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.is_recording = False
        self.motion_detected = False
        self.camera_connected = False
        self.zoom_level = 1.0
        self.pan_position = QPoint(0, 0)
        self.last_mouse_pos = None

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Header với thông tin camera
        self.header = QWidget()
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(5, 5, 5, 5)

        self.camera_name = QLabel("Camera Name")
        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(12, 12)
        self.recording_indicator = QLabel()
        self.recording_indicator.setFixedSize(12, 12)
        
        header_layout.addWidget(self.status_indicator)
        header_layout.addWidget(self.camera_name)
        header_layout.addWidget(self.recording_indicator)
        header_layout.addStretch()

        # Container cho video feed
        self.video_container = QLabel()
        self.video_container.setAlignment(Qt.AlignCenter)
        self.video_container.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                border: 1px solid #333;
                border-radius: 4px;
            }
        """)

        # Overlay controls
        self.overlay = QWidget(self.video_container)
        self.overlay.hide()
        overlay_layout = QHBoxLayout(self.overlay)

        # Control buttons
        self.create_overlay_controls(overlay_layout)

        # Information overlay
        self.info_overlay = QLabel(self.video_container)
        self.info_overlay.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                padding: 5px;
                border-radius: 3px;
            }
        """)
        self.info_overlay.hide()

        # Motion detection indicator
        self.motion_indicator = QLabel(self.video_container)
        self.motion_indicator.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 0, 0, 0.7);
                color: white;
                padding: 5px;
                border-radius: 3px;
            }
        """)
        self.motion_indicator.setText("Motion Detected")
        self.motion_indicator.hide()

        self.layout.addWidget(self.header)
        self.layout.addWidget(self.video_container)

        # Timer để ẩn overlay controls
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_overlay)

    def create_overlay_controls(self, layout):
        # Snapshot button
        snap_btn = QPushButton(QIcon(":/icons/snapshot.png"), "")
        snap_btn.clicked.connect(self.take_snapshot)
        
        # Record button
        self.record_btn = QPushButton(QIcon(":/icons/record.png"), "")
        self.record_btn.setCheckable(True)
        self.record_btn.clicked.connect(self.toggle_recording)
        
        # Fullscreen button
        full_btn = QPushButton(QIcon(":/icons/fullscreen.png"), "")
        full_btn.clicked.connect(self.toggle_fullscreen)
        
        # Settings button
        settings_btn = QPushButton(QIcon(":/icons/settings.png"), "")
        settings_btn.clicked.connect(self.show_settings)

        for btn in [snap_btn, self.record_btn, full_btn, settings_btn]:
            btn.setFixedSize(32, 32)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 0, 0, 0.7);
                    border: none;
                    border-radius: 16px;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: rgba(0, 0, 0, 0.8);
                }
            """)
            layout.addWidget(btn)

    def update_frame(self, frame):
        if frame is None:
            return
            
        # Xử lý zoom và pan
        if self.zoom_level != 1.0:
            height, width = frame.shape[:2]
            center_x = width / 2 + self.pan_position.x()
            center_y = height / 2 + self.pan_position.y()
            
            M = cv2.getRotationMatrix2D((center_x, center_y), 0, self.zoom_level)
            frame = cv2.warpAffine(frame, M, (width, height))

        # Chuyển đổi frame sang QImage
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        
        # Scale image to fit container
        pixmap = QPixmap.fromImage(q_img)
        scaled_pixmap = pixmap.scaled(self.video_container.size(), 
                                    Qt.KeepAspectRatio, 
                                    Qt.SmoothTransformation)
        
        self.video_container.setPixmap(scaled_pixmap)
        
        # Update FPS và thông tin khác
        self.update_info_overlay()

    def update_info_overlay(self):
        info_text = f"""
            Resolution: {self.video_container.pixmap().width()}x{self.video_container.pixmap().height()}
            FPS: {self.current_fps:.1f}
            Zoom: {self.zoom_level:.1f}x
        """
        self.info_overlay.setText(info_text)

    def enterEvent(self, event):
        self.overlay.show()
        self.hide_timer.start(3000)  # Ẩn sau 3 giây

    def leaveEvent(self, event):
        self.hide_timer.start(800)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_mouse_pos = event.pos()
            if event.type() == QEvent.MouseButtonDblClick:
                self.double_clicked.emit()
            else:
                self.clicked.emit()

    def mouseMoveEvent(self, event):
        if self.last_mouse_pos is not None:
            delta = event.pos() - self.last_mouse_pos
            self.pan_position += delta
            self.last_mouse_pos = event.pos()

    def mouseReleaseEvent(self, event):
        self.last_mouse_pos = None

    def wheelEvent(self, event):
        # Zoom with mouse wheel
        zoom_factor = 1.1
        if event.angleDelta().y() > 0:
            self.zoom_level *= zoom_factor
        else:
            self.zoom_level /= zoom_factor
        self.zoom_level = max(1.0, min(5.0, self.zoom_level))

    def set_camera_status(self, connected):
        self.camera_connected = connected
        color = "#00ff00" if connected else "#ff0000"
        self.status_indicator.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border-radius: 6px;
            }}
        """)

    def toggle_recording(self, recording):
        self.is_recording = recording
        self.recording_indicator.setStyleSheet("""
            QLabel {
                background-color: #ff0000;
                border-radius: 6px;
            }
        """) if recording else self.recording_indicator.clear()

    def set_motion_detected(self, detected):
        self.motion_detected = detected
        self.motion_indicator.setVisible(detected)

    def take_snapshot(self):
        # Implement snapshot functionality
        pass

    def toggle_fullscreen(self):
        # Implement fullscreen functionality
        pass

    def show_settings(self):
        # Implement settings dialog
        pass

    def hide_overlay(self):
        self.overlay.hide()