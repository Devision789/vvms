from PyQt5.QtCore import QSettings, QObject, pyqtSignal
import json
import os
import logging
from typing import Dict, Any

class Settings(QObject):
    settings_changed = pyqtSignal(str, object)  # Signal khi settings thay đổi (key, value)
    settings_loaded = pyqtSignal()  # Signal khi load settings
    settings_saved = pyqtSignal()  # Signal khi save settings

    def __init__(self, organization="MyOrg", application="SecuritySystem"):
        super().__init__()
        self.settings = QSettings(organization, application)
        self.default_settings = {
            # Camera settings
            "cameras": {},
            "default_resolution": (1920, 1080),
            "default_fps": 30,
            "default_codec": "H264",
            
            # Recording settings
            "recording": {
                "segment_duration": 300,  # 5 minutes
                "max_storage_days": 30,
                "min_free_space": 10,  # GB
                "storage_path": "recordings",
                "backup_path": "backups"
            },
            
            # Motion Detection settings
            "motion_detection": {
                "enabled": True,
                "sensitivity": 20,
                "min_area": 500,
                "blur_size": 21,
                "threshold": 25
            },
            
            # Alert settings
            "alerts": {
                "email": {
                    "enabled": False,
                    "smtp_server": "",
                    "smtp_port": 587,
                    "username": "",
                    "password": "",
                    "recipients": []
                },
                "telegram": {
                    "enabled": False,
                    "bot_token": "",
                    "chat_ids": []
                },
                "push_notifications": {
                    "enabled": False,
                    "service": "firebase"
                }
            },
            
            # UI settings
            "ui": {
                "theme": "dark",
                "language": "en",
                "grid_layout": "2x2",
                "show_timestamps": True,
                "show_camera_names": True
            },
            
            # System settings
            "system": {
                "auto_start": False,
                "log_level": "INFO",
                "log_retention_days": 7,
                "enable_hardware_acceleration": True,
                "port": 8000
            }
        }
        
        # Initialize logging
        self.setup_logging()
        
        # Load settings
        self.load_settings()

    def setup_logging(self):
        """Thiết lập logging"""
        log_level = self.get_value("system/log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename='security_system.log'
        )
        self.logger = logging.getLogger(__name__)

    def load_settings(self):
        """Load settings từ file hoặc tạo mới với default values"""
        try:
            # Load từng group settings
            for group, values in self.default_settings.items():
                if isinstance(values, dict):
                    self.settings.beginGroup(group)
                    for key, default_value in values.items():
                        if not self.settings.contains(key):
                            self.settings.setValue(key, default_value)
                    self.settings.endGroup()
                else:
                    if not self.settings.contains(group):
                        self.settings.setValue(group, values)
            
            self.settings_loaded.emit()
            self.logger.info("Settings loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Error loading settings: {str(e)}")
            # Sử dụng default settings nếu load thất bại
            self.reset_to_defaults()

    def save_settings(self):
        """Lưu settings hiện tại"""
        try:
            self.settings.sync()
            self.settings_saved.emit()
            self.logger.info("Settings saved successfully")
            
        except Exception as e:
            self.logger.error(f"Error saving settings: {str(e)}")

    def get_value(self, key: str, default=None) -> Any:
        """Lấy giá trị setting theo key"""
        try:
            value = self.settings.value(key, default)
            return value if value is not None else default
        
        except Exception as e:
            self.logger.error(f"Error getting setting {key}: {str(e)}")
            return default

    def set_value(self, key: str, value: Any):
        """Set giá trị cho setting"""
        try:
            self.settings.setValue(key, value)
            self.settings_changed.emit(key, value)
            self.logger.debug(f"Setting updated - {key}: {value}")
            
        except Exception as e:
            self.logger.error(f"Error setting {key}: {str(e)}")

    def reset_to_defaults(self):
        """Reset về default settings"""
        try:
            self.settings.clear()
            
            # Reset từng group
            for group, values in self.default_settings.items():
                if isinstance(values, dict):
                    self.settings.beginGroup(group)
                    for key, default_value in values.items():
                        self.settings.setValue(key, default_value)
                    self.settings.endGroup()
                else:
                    self.settings.setValue(group, values)
                    
            self.settings_loaded.emit()
            self.logger.info("Settings reset to defaults")
            
        except Exception as e:
            self.logger.error(f"Error resetting settings: {str(e)}")

    def export_settings(self, filepath: str):
        """Export settings ra file JSON"""
        try:
            settings_dict = {}
            
            # Export từng group
            for group in self.default_settings.keys():
                if isinstance(self.default_settings[group], dict):
                    settings_dict[group] = {}
                    self.settings.beginGroup(group)
                    for key in self.default_settings[group].keys():
                        settings_dict[group][key] = self.settings.value(
                            key, 
                            self.default_settings[group][key]
                        )
                    self.settings.endGroup()
                else:
                    settings_dict[group] = self.settings.value(
                        group,
                        self.default_settings[group]
                    )
                    
            with open(filepath, 'w') as f:
                json.dump(settings_dict, f, indent=4)
                
            self.logger.info(f"Settings exported to {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error exporting settings: {str(e)}")

    def import_settings(self, filepath: str):
        """Import settings từ file JSON"""
        try:
            with open(filepath, 'r') as f:
                settings_dict = json.load(f)
                
            # Clear current settings
            self.settings.clear()
            
            # Import từng group
            for group, values in settings_dict.items():
                if isinstance(values, dict):
                    self.settings.beginGroup(group)
                    for key, value in values.items():
                        self.settings.setValue(key, value)
                    self.settings.endGroup()
                else:
                    self.settings.setValue(group, values)
                    
            self.settings_loaded.emit()
            self.logger.info(f"Settings imported from {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error importing settings: {str(e)}")
            # Rollback to defaults if import fails
            self.reset_to_defaults()

    def get_camera_settings(self, camera_id: str) -> Dict:
        """Lấy settings cho một camera cụ thể"""
        try:
            self.settings.beginGroup("cameras")
            camera_settings = self.settings.value(camera_id, {})
            self.settings.endGroup()
            
            # Merge với default settings
            default_camera = {
                "name": f"Camera {camera_id}",
                "url": "",
                "enabled": True,
                "resolution": self.get_value("default_resolution"),
                "fps": self.get_value("default_fps"),
                "codec": self.get_value("default_codec"),
                "motion_detection": True,
                "recording": True
            }
            
            if isinstance(camera_settings, dict):
                default_camera.update(camera_settings)
                
            return default_camera
        
        except Exception as e:
            self.logger.error(f"Error getting camera settings: {str(e)}")
            return {}

    def set_camera_settings(self, camera_id: str, settings: Dict):
        """Set settings cho một camera"""
        try:
            self.settings.beginGroup("cameras")
            self.settings.setValue(camera_id, settings)
            self.settings.endGroup()
            
            self.settings_changed.emit(f"cameras/{camera_id}", settings)
            self.logger.debug(f"Camera settings updated - {camera_id}")
            
        except Exception as e:
            self.logger.error(f"Error setting camera settings: {str(e)}")

    def remove_camera_settings(self, camera_id: str):
        """Xóa settings của một camera"""
        try:
            self.settings.beginGroup("cameras")
            self.settings.remove(camera_id)
            self.settings.endGroup()
            
            self.settings_changed.emit(f"cameras/{camera_id}", None)
            self.logger.debug(f"Camera settings removed - {camera_id}")
            
        except Exception as e:
            self.logger.error(f"Error removing camera settings: {str(e)}")

    def get_all_cameras(self) -> Dict:
        """Lấy settings của tất cả cameras"""
        try:
            self.settings.beginGroup("cameras")
            cameras = {
                key: self.get_camera_settings(key) 
                for key in self.settings.childKeys()
            }
            self.settings.endGroup()
            return cameras
        
        except Exception as e:
            self.logger.error(f"Error getting all cameras: {str(e)}")
            return {}