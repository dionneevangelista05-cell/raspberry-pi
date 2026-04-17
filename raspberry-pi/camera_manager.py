"""
FaceLogX Raspberry Pi - Camera Manager
Manages multiple USB camera streams with threading
"""

import cv2
import threading
import time
import logging

logger = logging.getLogger("FaceLogX.Camera")


class CameraStream:
    """Threaded camera stream for a single USB camera"""

    def __init__(self, camera_config):
        self.camera_id = camera_config["id"]
        self.name = camera_config["name"]
        self.device_index = camera_config["device_index"]
        self.resolution = camera_config["resolution"]
        self.fps = camera_config["fps"]

        self.cap = None
        self.frame = None
        self.lock = threading.Lock()
        self.running = False
        self.connected = False
        self._thread = None

    def start(self):
        """Open camera and start capture thread"""
        try:
            self.cap = cv2.VideoCapture(self.device_index)
            if not self.cap.isOpened():
                logger.error(f"[{self.name}] Failed to open /dev/video{self.device_index}")
                self.connected = False
                return False

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            self.running = True
            self.connected = True
            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()

            logger.info(f"[{self.name}] Started on /dev/video{self.device_index}")
            return True

        except Exception as e:
            logger.error(f"[{self.name}] Start error: {e}")
            self.connected = False
            return False

    def _capture_loop(self):
        """Continuously capture frames"""
        consecutive_failures = 0
        while self.running:
            try:
                ret, frame = self.cap.read()
                if ret:
                    with self.lock:
                        self.frame = frame
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures > 30:
                        logger.warning(f"[{self.name}] Too many capture failures, reconnecting...")
                        self._reconnect()
                        consecutive_failures = 0

                time.sleep(1.0 / self.fps)

            except Exception as e:
                logger.error(f"[{self.name}] Capture error: {e}")
                time.sleep(1.0)

    def _reconnect(self):
        """Attempt to reconnect camera"""
        try:
            if self.cap:
                self.cap.release()
            time.sleep(2)
            self.cap = cv2.VideoCapture(self.device_index)
            if self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                self.connected = True
                logger.info(f"[{self.name}] Reconnected successfully")
            else:
                self.connected = False
                logger.error(f"[{self.name}] Reconnect failed")
        except Exception as e:
            self.connected = False
            logger.error(f"[{self.name}] Reconnect error: {e}")

    def get_frame(self):
        """Get the latest frame (thread-safe)"""
        with self.lock:
            if self.frame is not None:
                return self.frame.copy()
        return None

    def stop(self):
        """Stop camera stream"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=3)
        if self.cap:
            self.cap.release()
        self.connected = False
        logger.info(f"[{self.name}] Stopped")

    def get_status(self):
        """Return camera status string"""
        if not self.connected:
            return "offline"
        if self.frame is None:
            return "error"
        return "online"


class CameraManager:
    """Manages all camera streams"""

    def __init__(self, camera_configs):
        self.cameras = {}
        for config in camera_configs:
            cam = CameraStream(config)
            self.cameras[config["id"]] = cam

    def start_all(self):
        """Start all cameras"""
        results = {}
        for cam_id, cam in self.cameras.items():
            results[cam_id] = cam.start()
        return results

    def stop_all(self):
        """Stop all cameras"""
        for cam in self.cameras.values():
            cam.stop()

    def get_frame(self, camera_id):
        """Get frame from specific camera"""
        cam = self.cameras.get(camera_id)
        if cam:
            return cam.get_frame()
        return None

    def get_camera(self, camera_id):
        """Get camera stream object"""
        return self.cameras.get(camera_id)

    def get_all_statuses(self):
        """Get status of all cameras"""
        return [
            {"camera_id": cam_id, "status": cam.get_status()}
            for cam_id, cam in self.cameras.items()
        ]

    def get_connected_cameras(self):
        """Get list of connected camera IDs"""
        return [
            cam_id for cam_id, cam in self.cameras.items()
            if cam.connected
        ]
