from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition
import cv2
import numpy as np
import time
from datetime import datetime
import queue

class CameraThread(QThread):
    frame_ready = pyqtSignal(np.ndarray, str)  # Signal gửi frame và camera_id
    error_occurred = pyqtSignal(str, str)  # Signal báo lỗi (camera_id, error_message)
    status_changed = pyqtSignal(str, bool)  # Signal báo trạng thái kết nối (camera_id, connected)
    fps_updated = pyqtSignal(str, float)  # Signal cập nhật FPS (camera_id, fps)
    motion_detected = pyqtSignal(str, bool)  # Signal phát hiện chuyển động (camera_id, detected)

    def __init__(self, camera_id, camera_url, config=None):
        super().__init__()
        self.camera_id = camera_id
        self.camera_url = camera_url
        self.config = config or {}
        
        # Thread control
        self.mutex = QMutex()
        self.wait_condition = QWaitCondition()
        self.is_running = False
        self.is_paused = False
        
        # Camera settings
        self.fps_limit = self.config.get('fps_limit', 30)
        self.frame_interval = 1.0 / self.fps_limit
        self.resolution = self.config.get('resolution', (1280, 720))
        
        # Performance monitoring
        self.fps_counter = 0
        self.fps_timer = time.time()
        self.current_fps = 0.0
        
        # Motion detection
        self.motion_detection_enabled = self.config.get('motion_detection', False)
        self.motion_threshold = self.config.get('motion_threshold', 25)
        self.min_motion_area = self.config.get('min_motion_area', 500)
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=16, detectShadows=True)
        
        # Frame buffer
        self.frame_buffer = queue.Queue(maxsize=30)  # Buffer 30 frames
        
        # Error handling
        self.retry_count = 0
        self.max_retries = 3
        self.retry_interval = 5  # seconds

    def run(self):
        self.is_running = True
        while self.is_running:
            if self.is_paused:
                self.wait_condition.wait(self.mutex)
                continue
                
            try:
                cap = cv2.VideoCapture(self.camera_url)
                if not cap.isOpened():
                    raise Exception("Could not open camera connection")
                
                # Configure camera settings
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                
                self.status_changed.emit(self.camera_id, True)
                self.retry_count = 0
                
                last_frame_time = time.time()
                
                while self.is_running and not self.is_paused:
                    # Control frame rate
                    current_time = time.time()
                    if current_time - last_frame_time < self.frame_interval:
                        continue
                        
                    ret, frame = cap.read()
                    if not ret:
                        raise Exception("Failed to grab frame")
                        
                    # Update FPS counter
                    self.update_fps()
                    
                    # Process frame
                    processed_frame = self.process_frame(frame)
                    
                    # Motion detection
                    if self.motion_detection_enabled:
                        motion_detected = self.detect_motion(processed_frame)
                        self.motion_detected.emit(self.camera_id, motion_detected)
                    
                    # Buffer frame
                    if not self.frame_buffer.full():
                        self.frame_buffer.put(processed_frame)
                    
                    # Emit frame
                    self.frame_ready.emit(processed_frame, self.camera_id)
                    
                    last_frame_time = current_time
                    
            except Exception as e:
                self.handle_error(str(e))
                if cap is not None:
                    cap.release()
                    
                if self.retry_count >= self.max_retries:
                    self.error_occurred.emit(self.camera_id, 
                        f"Maximum retry attempts ({self.max_retries}) reached")
                    break
                    
                time.sleep(self.retry_interval)
                self.retry_count += 1
                continue
                
        if cap is not None:
            cap.release()
            
    def process_frame(self, frame):
        """Xử lý frame trước khi gửi đi"""
        try:
            # Resize nếu cần
            if frame.shape[:2] != self.resolution:
                frame = cv2.resize(frame, self.resolution)
            
            # Áp dụng các filter từ config
            if self.config.get('denoise', False):
                frame = cv2.fastNlMeansDenoisingColored(frame)
                
            if self.config.get('sharpen', False):
                kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
                frame = cv2.filter2D(frame, -1, kernel)
                
            if self.config.get('brightness', 0) != 0:
                frame = cv2.convertScaleAbs(frame, 
                    alpha=1, beta=self.config['brightness'])
                
            return frame
            
        except Exception as e:
            self.error_occurred.emit(self.camera_id, f"Frame processing error: {str(e)}")
            return frame

    def detect_motion(self, frame):
        """Phát hiện chuyển động trong frame"""
        try:
            # Apply background subtraction
            fgmask = self.background_subtractor.apply(frame)
            
            # Threshold to binary image
            _, thresh = cv2.threshold(fgmask, self.motion_threshold, 255, cv2.THRESH_BINARY)
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Check for significant motion
            for contour in contours:
                if cv2.contourArea(contour) > self.min_motion_area:
                    return True
                    
            return False
            
        except Exception as e:
            self.error_occurred.emit(self.camera_id, f"Motion detection error: {str(e)}")
            return False

    def update_fps(self):
        """Cập nhật FPS counter"""
        self.fps_counter += 1
        current_time = time.time()
        
        if current_time - self.fps_timer >= 1.0:
            self.current_fps = self.fps_counter / (current_time - self.fps_timer)
            self.fps_updated.emit(self.camera_id, self.current_fps)
            self.fps_counter = 0
            self.fps_timer = current_time

    def handle_error(self, error_message):
        """Xử lý lỗi camera"""
        self.status_changed.emit(self.camera_id, False)
        self.error_occurred.emit(self.camera_id, error_message)

    def pause(self):
        """Tạm dừng camera thread"""
        self.mutex.lock()
        self.is_paused = True
        self.mutex.unlock()

    def resume(self):
        """Tiếp tục camera thread"""
        self.mutex.lock()
        self.is_paused = False
        self.wait_condition.wakeAll()
        self.mutex.unlock()

    def stop(self):
        """Dừng camera thread"""
        self.is_running = False
        self.resume()  # Wake up thread if it's paused
        self.wait()

class CameraManager:
    def __init__(self):
        self.cameras = {}  # Dictionary lưu trữ các camera threads
        self.config = {}   # Cấu hình chung cho cameras
        
    def add_camera(self, camera_id, camera_url, config=None):
        """Thêm camera mới"""
        if camera_id in self.cameras:
            self.remove_camera(camera_id)
            
        camera_config = self.config.copy()
        if config:
            camera_config.update(config)
            
        thread = CameraThread(camera_id, camera_url, camera_config)
        self.cameras[camera_id] = thread
        thread.start()
        
    def remove_camera(self, camera_id):
        """Xóa camera"""
        if camera_id in self.cameras:
            self.cameras[camera_id].stop()
            del self.cameras[camera_id]
            
    def get_camera(self, camera_id):
        """Lấy camera thread theo ID"""
        return self.cameras.get(camera_id)
        
    def update_config(self, config):
        """Cập nhật cấu hình cho tất cả cameras"""
        self.config.update(config)
        for camera in self.cameras.values():
            camera.config.update(config)
            
    def stop_all(self):
        """Dừng tất cả cameras"""
        for camera in self.cameras.values():
            camera.stop()
        self.cameras.clear()