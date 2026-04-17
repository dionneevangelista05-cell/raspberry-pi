"""
FaceLogX Raspberry Pi - API Client
Communicates with the FaceLogX Node.js server
"""

import requests
import logging
import time

logger = logging.getLogger("FaceLogX.API")


class FaceLogXAPI:
    """HTTP client for FaceLogX server API"""

    def __init__(self, server_url, api_key):
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        })
        self.timeout = 10  # seconds
        self._last_error = None

    # ============================================
    # CONNECTION
    # ============================================

    def test_connection(self):
        """Test connection to server"""
        try:
            resp = requests.get(
                f"{self.server_url}/health",
                timeout=self.timeout
            )
            if resp.status_code == 200:
                logger.info("Server connection OK")
                return True
            logger.error(f"Server returned status {resp.status_code}")
            return False
        except requests.ConnectionError:
            logger.error(f"Cannot connect to server at {self.server_url}")
            return False
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    # ============================================
    # FACE ENCODINGS
    # ============================================

    def get_known_encodings(self):
        """Fetch all registered face encodings from server"""
        try:
            resp = self.session.get(
                f"{self.server_url}/face-recognition/encodings",
                timeout=self.timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"Loaded {len(data)} face encodings from server")
                return data
            elif resp.status_code == 403:
                logger.error("Invalid API key. Run register_pi.py first.")
                return []
            else:
                logger.error(f"Get encodings failed: {resp.status_code}")
                return []
        except Exception as e:
            logger.error(f"Get encodings error: {e}")
            self._last_error = str(e)
            return []

    def upload_encoding(self, student_id, encoding):
        """Upload a face encoding for a student"""
        try:
            resp = self.session.post(
                f"{self.server_url}/face-recognition/encode",
                json={"student_id": student_id, "encoding": encoding},
                timeout=self.timeout
            )
            if resp.status_code == 200:
                logger.info(f"Encoding uploaded for student {student_id}")
                return True
            logger.error(f"Upload encoding failed: {resp.status_code} - {resp.text}")
            return False
        except Exception as e:
            logger.error(f"Upload encoding error: {e}")
            return False

    # ============================================
    # FACE RECOGNITION EVENTS
    # ============================================

    def report_recognition(self, student_id, camera_id, confidence):
        """Report a recognized face to server"""
        try:
            resp = self.session.post(
                f"{self.server_url}/face-recognition/recognize",
                json={
                    "student_id": student_id,
                    "camera_id": camera_id,
                    "confidence": float(confidence),
                },
                timeout=self.timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                logger.info(
                    f"Recognition reported: {data.get('student_name', 'Unknown')} "
                    f"(attendance: {data.get('attendance_recorded', False)})"
                )
                return data
            logger.error(f"Report recognition failed: {resp.status_code}")
            return None
        except Exception as e:
            logger.error(f"Report recognition error: {e}")
            return None

    def report_unknown(self, camera_id):
        """Report an unrecognized face"""
        try:
            resp = self.session.post(
                f"{self.server_url}/face-recognition/unknown",
                json={"camera_id": camera_id},
                timeout=self.timeout
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Report unknown error: {e}")
            return False

    # ============================================
    # HEARTBEAT & STATUS
    # ============================================

    def send_heartbeat(self, camera_statuses):
        """Send heartbeat with camera statuses, receive active sessions"""
        try:
            resp = self.session.post(
                f"{self.server_url}/face-recognition/heartbeat",
                json={"cameras": camera_statuses},
                timeout=self.timeout
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
            return None

    def get_session_status(self):
        """Get current attendance session status and settings"""
        try:
            resp = self.session.get(
                f"{self.server_url}/face-recognition/session-status",
                timeout=self.timeout
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.error(f"Session status error: {e}")
            return None

    # ============================================
    # STUDENTS
    # ============================================

    def get_active_students(self):
        """Get list of active students"""
        try:
            resp = requests.get(
                f"{self.server_url}/students",
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            logger.error(f"Get students error: {e}")
            return []
