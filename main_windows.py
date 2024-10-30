import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import cv2
import datetime
from camera_view import CameraView
import resources_rc # File chứa icons

class CameraViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Camera System")
        self.setGeometry(100, 100, 1400, 900)
        
        # Set style theme
        self.current_theme = "dark"
        self.apply_theme()

        # Main widget và layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left panel với width cố định ban đầu
        left_panel = QWidget()
        left_panel.setMinimumWidth(300)
        left_layout = QVBoxLayout(left_panel)
        
        # Camera tree với icons
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Cameras")
        self.tree.setIconSize(QSize(24, 24))
        camera_item = QTreeWidgetItem(["Camera Group"])
        camera_item.setIcon(0, QIcon(":/icons/camera-group.png"))
        
        # Add camera items với status indicators
        self.add_camera_item(camera_item, "Camera 1", True)
        self.add_camera_item(camera_item, "Camera 2", False)
        self.tree.addTopLevelItem(camera_item)
        camera_item.setExpanded(True)
        left_layout.addWidget(self.tree)

        # Enhanced Camera controls
        controls = QGroupBox("Camera Controls")
        controls_layout = QVBoxLayout(controls)
        
        # Add camera control widgets
        self.create_camera_controls(controls_layout)
        left_layout.addWidget(controls)

        splitter.addWidget(left_panel)

        # Right panel (camera views)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Grid container for camera views
        grid_widget = QWidget()
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setSpacing(10)
        
        # Camera views (2x3 grid)
        self.camera_views = []
        self.create_camera_grid()
        
        right_layout.addWidget(grid_widget)
        splitter.addWidget(right_panel)

        # Set stretch factor
        splitter.setStretchFactor(0, 1)  # Left panel
        splitter.setStretchFactor(1, 4)  # Right panel

        # Enhanced Toolbar
        self.create_toolbar()

        # Status bar with system info
        self.create_status_bar()

        # Add enhanced tabbed interface
        self.create_tab_interface()

        # Initialize camera system
        self.init_camera_system()

    def create_toolbar(self):
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(32, 32))
        self.addToolBar(toolbar)

        # Camera control group
        toolbar.addAction(QIcon(":/icons/connect.png"), "Connect Camera", self.connect_camera)
        toolbar.addAction(QIcon(":/icons/disconnect.png"), "Disconnect Camera", self.disconnect_camera)
        toolbar.addSeparator()

        # View control group
        self.view_actions = []
        for i in range(6):
            action = QAction(QIcon(f":/icons/layout-{i+1}.png"), f"{i+1} Cameras", self)
            self.view_actions.append(action)
            toolbar.addAction(action)
        toolbar.addSeparator()

        # Recording group
        self.record_action = QAction(QIcon(":/icons/record.png"), "Record", self)
        self.record_action.setCheckable(True)
        toolbar.addAction(self.record_action)
        toolbar.addAction(QIcon(":/icons/snapshot.png"), "Take Snapshot", self.take_snapshot)
        toolbar.addSeparator()

        # Settings group
        toolbar.addAction(QIcon(":/icons/settings.png"), "Settings", self.show_settings)
        theme_action = QAction(QIcon(":/icons/theme.png"), "Toggle Theme", self)
        theme_action.triggered.connect(self.toggle_theme)
        toolbar.addAction(theme_action)
        
        # Help
        toolbar.addAction(QIcon(":/icons/help.png"), "Help", self.show_help)

    def create_camera_controls(self, layout):
        # Camera selection
        camera_combo = QComboBox()
        camera_combo.addItems(["Camera 1", "Camera 2", "Camera 3"])
        layout.addWidget(QLabel("Select Camera:"))
        layout.addWidget(camera_combo)

        # Camera parameters
        for param in ["Brightness", "Contrast", "Saturation"]:
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(50)
            layout.addWidget(QLabel(param))
            layout.addWidget(slider)

        # PTZ Controls
        ptz_group = QGroupBox("PTZ Controls")
        ptz_layout = QGridLayout()
        
        # PTZ buttons
        ptz_buttons = {
            "⭯": (0,0), "↑": (0,1), "⭮": (0,2),
            "←": (1,0), "●": (1,1), "→": (1,2),
            "⟲": (2,0), "↓": (2,1), "⟳": (2,2)
        }
        
        for label, pos in ptz_buttons.items():
            btn = QPushButton(label)
            btn.setFixedSize(40, 40)
            ptz_layout.addWidget(btn, pos[0], pos[1])
            
        ptz_group.setLayout(ptz_layout)
        layout.addWidget(ptz_group)

        # Zoom controls
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QPushButton("Zoom -"))
        zoom_slider = QSlider(Qt.Horizontal)
        zoom_slider.setRange(1, 10)
        zoom_layout.addWidget(zoom_slider)
        zoom_layout.addWidget(QPushButton("Zoom +"))
        layout.addLayout(zoom_layout)

    def create_camera_grid(self):
        for i in range(6):
            view = CameraView()
            row, col = i // 3, i % 3
            self.grid_layout.addWidget(view, row, col)
            self.camera_views.append(view)

    def add_camera_item(self, parent, name, connected):
        item = QTreeWidgetItem(parent, [name])
        item.setIcon(0, QIcon(":/icons/camera.png"))
        status_icon = ":/icons/connected.png" if connected else ":/icons/disconnected.png"
        item.setIcon(1, QIcon(status_icon))
        return item

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CameraViewer()
    window.show()
    sys.exit(app.exec_())