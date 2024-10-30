from PyQt5.QtCore import QObject, QThread, pyqtSignal, QMutex, QDateTime
import cv2
import numpy as np
import os
import json
from datetime import datetime, timedelta
import sqlite3
import queue
import time

class RecordingManager(QObject):
    recording_started = pyqtSignal(str)  # Signal khi bắt đầu recording (camera_id)
    recording_stopped = pyqtSignal(str)  # Signal khi dừng recording (camera_id)
    recording_error = pyqtSignal(str, str)  # Signal khi có lỗi (camera_id, error_message)
    storage_warning = pyqtSignal(float)  # Signal cảnh báo dung lượng lưu trữ (percentage_left)

    def __init__(self, base_path="recordings"):
        super().__init__()
        self.base_path = base_path
        self.recorders = {}  # Dictionary lưu các recording threads
        self.db_path = os.path.join(base_path, "recordings.db")
        self.mutex = QMutex()
        self.init_storage()
        self.init_database()

    def init_storage(self):
        """Khởi tạo thư mục lưu trữ"""
        try:
            if not os.path.exists(self.base_path):
                os.makedirs(self.base_path)
                
            # Tạo cấu trúc thư mục
            self.create_directory_structure()
            
            # Kiểm tra dung lượng
            self.check_storage_space()
            
        except Exception as e:
            print(f"Storage initialization error: {str(e)}")

    def init_database(self):
        """Khởi tạo database để lưu metadata"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Tạo bảng recordings
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS recordings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    camera_id TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    duration INTEGER,
                    has_motion BOOLEAN DEFAULT FALSE,
                    metadata TEXT
                )
            ''')
            
            # Tạo bảng events
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recording_id INTEGER,
                    event_type TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    description TEXT,
                    FOREIGN KEY (recording_id) REFERENCES recordings (id)
                )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Database initialization error: {str(e)}")

    def start_recording(self, camera_id, config=None):
        """Bắt đầu recording cho một camera"""
        try:
            self.mutex.lock()
            
            if camera_id in self.recorders:
                self.stop_recording(camera_id)
                
            recorder = RecorderThread(camera_id, self.base_path, config)
            recorder.recording_error.connect(
                lambda err: self.recording_error.emit(camera_id, err))
            
            # Kết nối các signals
            recorder.finished.connect(
                lambda: self.handle_recording_finished(camera_id))
            
            self.recorders[camera_id] = recorder
            recorder.start()
            
            self.recording_started.emit(camera_id)
            self.log_event(camera_id, "recording_start", "Recording started")
            
        except Exception as e:
            self.recording_error.emit(camera_id, str(e))
        finally:
            self.mutex.unlock()

    def stop_recording(self, camera_id):
        """Dừng recording cho một camera"""
        try:
            self.mutex.lock()
            
            if camera_id in self.recorders:
                self.recorders[camera_id].stop()
                self.recorders[camera_id].wait()
                del self.recorders[camera_id]
                
                self.recording_stopped.emit(camera_id)
                self.log_event(camera_id, "recording_stop", "Recording stopped")
                
        except Exception as e:
            self.recording_error.emit(camera_id, str(e))
        finally:
            self.mutex.unlock()

    def handle_recording_finished(self, camera_id):
        """Xử lý khi recording kết thúc"""
        try:
            if camera_id in self.recorders:
                recorder = self.recorders[camera_id]
                
                # Cập nhật database
                self.update_recording_metadata(
                    camera_id,
                    recorder.start_time,
                    recorder.end_time,
                    recorder.file_path,
                    recorder.file_size,
                    recorder.duration
                )
                
                # Cleanup
                del self.recorders[camera_id]
                
        except Exception as e:
            self.recording_error.emit(camera_id, str(e))

    def create_directory_structure(self):
        """Tạo cấu trúc thư mục theo ngày"""
        today = datetime.now()
        month_path = os.path.join(self.base_path, today.strftime("%Y-%m"))
        day_path = os.path.join(month_path, today.strftime("%d"))
        
        os.makedirs(month_path, exist_ok=True)
        os.makedirs(day_path, exist_ok=True)
        
        return day_path

    def check_storage_space(self):
        """Kiểm tra và quản lý dung lượng lưu trữ"""
        try:
            # Lấy thông tin dung lượng
            total, used, free = self.get_storage_info()
            
            # Tính phần trăm còn trống
            free_percent = (free / total) * 100
            
            # Gửi cảnh báo nếu dung lượng thấp
            if free_percent < 10:
                self.storage_warning.emit(free_percent)
                
            # Tự động dọn dẹp nếu cần
            if free_percent < 5:
                self.cleanup_old_recordings()
                
        except Exception as e:
            print(f"Storage check error: {str(e)}")

    def get_storage_info(self):
        """Lấy thông tin về dung lượng lưu trữ"""
        import shutil
        
        total, used, free = shutil.disk_usage(self.base_path)
        return total, used, free

    def cleanup_old_recordings(self):
        """Dọn dẹp các recording cũ"""
        try:
            # Lấy danh sách recording cũ hơn 30 ngày
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            thirty_days_ago = datetime.now() - timedelta(days=30)
            
            cursor.execute('''
                SELECT file_path FROM recordings 
                WHERE start_time < ? 
                ORDER BY start_time ASC
            ''', (thirty_days_ago,))
            
            old_recordings = cursor.fetchall()
            
            # Xóa các file
            for (file_path,) in old_recordings:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
                    # Xóa record trong database
                    cursor.execute('''
                        DELETE FROM recordings WHERE file_path = ?
                    ''', (file_path,))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Cleanup error: {str(e)}")

    def update_recording_metadata(self, camera_id, start_time, end_time, 
                                file_path, file_size, duration):
        """Cập nhật metadata cho recording"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE recordings 
                SET end_time = ?,
                    file_size = ?,
                    duration = ?
                WHERE camera_id = ? AND file_path = ? AND start_time = ?
            ''', (end_time, file_size, duration, camera_id, file_path, start_time))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Metadata update error: {str(e)}")

    def log_event(self, camera_id, event_type, description):
        """Ghi log event"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Lấy recording_id hiện tại
            cursor.execute('''
                SELECT id FROM recordings 
                WHERE camera_id = ? 
                ORDER BY start_time DESC LIMIT 1
            ''', (camera_id,))
            
            result = cursor.fetchone()
            if result:
                recording_id = result[0]
                
                # Thêm event
                cursor.execute('''
                    INSERT INTO events (recording_id, event_type, timestamp, description)
                    VALUES (?, ?, ?, ?)
                ''', (recording_id, event_type, datetime.now(), description))
                
                conn.commit()
                
            conn.close()
            
        except Exception as e:
            print(f"Event logging error: {str(e)}")

class RecorderThread(QThread):
    recording_error = pyqtSignal(str)  # Signal báo lỗi

    def __init__(self, camera_id, base_path, config=None):
        super().__init__()
        self.camera_id = camera_id
        self.base_path = base_path
        self.config = config or {}
        
        # Recording status
        self.is_recording = False
        self.frame_buffer = queue.Queue(maxsize=300)  # Buffer 10 seconds at 30fps
        
        # Recording info
        self.start_time = None
        self.end_time = None
        self.file_path = None
        self.file_size = 0
        self.duration = 0
        
        # Video writer
        self.writer = None
        
        # Initialize settings
        self.init_settings()

    def init_settings(self):
        """Khởi tạo các thiết lập recording"""
        self.fps = self.config.get('fps', 30)
        self.resolution = self.config.get('resolution', (1920, 1080))
        self.codec = self.config.get('codec', 'H264')
        self.segment_duration = self.config.get('segment_duration', 300)  # 5 minutes
        
        # Codec settings
        if self.codec == 'H264':
            self.fourcc = cv2.VideoWriter_fourcc(*'X264')
        elif self.codec == 'MJPG':
            self.fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        else:
            self.fourcc = cv2.VideoWriter_fourcc(*'XVID')

    def run(self):
        """Main recording loop"""
        try:
            self.is_recording = True
            self.start_time = datetime.now()
            
            # Tạo file path
            self.file_path = self.create_file_path()
            
            # Khởi tạo video writer
            self.writer = cv2.VideoWriter(
                self.file_path, 
                self.fourcc, 
                self.fps, 
                self.resolution
            )
            
            segment_start_time = time.time()
            frames_written = 0
            
            while self.is_recording:
                if not self.frame_buffer.empty():
                    frame = self.frame_buffer.get()
                    
                    if frame is not None:
                        self.writer.write(frame)
                        frames_written += 1
                        
                        # Check if need to start new segment
                        if time.time() - segment_start_time >= self.segment_duration:
                            self.start_new_segment()
                            segment_start_time = time.time()
                            
                else:
                    # Avoid busy waiting
                    time.sleep(0.001)
                    
            # Cleanup
            self.end_recording(frames_written)
            
        except Exception as e:
            self.recording_error.emit(str(e))
            self.cleanup()

    def create_file_path(self):
        """Tạo đường dẫn file recording"""
        now = datetime.now()
        filename = f"{self.camera_id}_{now.strftime('%Y%m%d_%H%M%S')}.mp4"
        return os.path.join(self.base_path, filename)

    def start_new_segment(self):
        """Bắt đầu segment recording mới"""
        # Close current writer
        if self.writer:
            self.writer.release()
            
        # Update file size
        self.update_file_size()
            
        # Create new file path
        self.file_path = self.create_file_path()
        
        # Create new writer
        self.writer = cv2.VideoWriter(
            self.file_path, 
            self.fourcc, 
            self.fps, 
            self.resolution
        )

    def add_frame(self, frame):
        """Thêm frame vào buffer"""
        if not self.frame_buffer.full():
            self.frame_buffer.put(frame)

    def stop(self):
        """Dừng recording"""
        self.is_recording = False

    def end_recording(self, frames_written):
        """Kết thúc recording và cập nhật thông tin"""
        self.end_time = datetime.now()
        self.duration = (self.end_time - self.start_time).total_seconds()
        self.update_file_size()
        self.cleanup()

    def update_file_size(self):
        """Cập nhật kích thước file"""
        if self.file_path and os.path.exists(self.file_path):
            self.file_size = os.path.getsize(self.file_path)

    def cleanup(self):
        """Dọn dẹp resources"""
        if self.writer:
            self.writer.release()
            self.writer = None