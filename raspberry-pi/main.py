#!/usr/bin/env python3
"""
FaceLogX Raspberry Pi - Main Orchestrator
Runs face recognition on 3 cameras with LCD displays.
Sends attendance data to the FaceLogX web server.

Usage:
    python3 main.py                # Normal operation
    python3 main.py --test-lcd     # Test LCD displays
    python3 main.py --test-cameras # Test camera feeds
    python3 main.py --debug        # Verbose logging
"""

import sys
import os
import time
import signal
import logging
import threading
import argparse

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CAMERAS, FACE_RECOGNITION, LCD, SYSTEM, SERVER_URL, API_KEY
from camera_manager import CameraManager
from lcd_controller import LCDManager
from face_processor import FaceProcessor
from api_client import FaceLogXAPI


# ============================================
# LOGGING SETUP
# ============================================
def setup_logging(level="INFO"):
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("facelogx.log", mode="a"),
        ],
    )


logger = logging.getLogger("FaceLogX")


# ============================================
# MAIN APPLICATION
# ============================================
class FaceLogXSystem:
    """Main system that orchestrates cameras, face recognition, LCDs, and server communication"""

    def __init__(self):
        self.running = False
        self.api = FaceLogXAPI(SERVER_URL, API_KEY)
        self.camera_manager = CameraManager(CAMERAS)
        self.lcd_manager = LCDManager(CAMERAS, LCD)
        self.face_processors = {}
        self.active_sessions = {"morning": False, "afternoon": False}
        self._encoding_data = []

        # Create face processor for each camera
        for cam_config in CAMERAS:
            cam_id = cam_config["id"]
            lcd = self.lcd_manager.get_display(cam_id)
            processor = FaceProcessor(
                camera_id=cam_id,
                config=FACE_RECOGNITION,
                api_client=self.api,
                lcd_display=lcd,
            )
            self.face_processors[cam_id] = processor

    def start(self):
        """Start the entire system"""
        logger.info("=" * 50)
        logger.info("FaceLogX Face Recognition System Starting")
        logger.info("=" * 50)

        # Show startup message on LCDs
        self.lcd_manager.show_startup()

        # Validate API key
        if not API_KEY:
            logger.error("No API key configured! Run: python3 register_pi.py")
            self.lcd_manager.clear_all()
            for lcd in self.lcd_manager.displays.values():
                lcd.write("No API Key!", "Run register_pi")
            return False

        # Test server connection
        logger.info(f"Connecting to server: {SERVER_URL}")
        if not self.api.test_connection():
            logger.error("Cannot connect to FaceLogX server!")
            for lcd in self.lcd_manager.displays.values():
                lcd.show_error("Server Offline")
            return False

        logger.info("Server connection OK")

        # Start cameras
        logger.info("Starting cameras...")
        results = self.camera_manager.start_all()
        for cam_id, success in results.items():
            if not success:
                logger.warning(f"Camera {cam_id} failed to start")
                lcd = self.lcd_manager.get_display(cam_id)
                if lcd:
                    lcd.show_error("Cam Offline")

        connected = self.camera_manager.get_connected_cameras()
        if not connected:
            logger.error("No cameras connected!")
            return False

        logger.info(f"{len(connected)} cameras online: {connected}")

        # Load known face encodings from server
        self._refresh_encodings()

        # Set running
        self.running = True

        # Start background threads
        self._start_heartbeat_thread()
        self._start_encoding_refresh_thread()

        # Start face recognition loop for each camera
        self._start_recognition_threads()

        logger.info("System started successfully!")
        self.lcd_manager.show_all_scanning()

        return True

    def stop(self):
        """Stop the system gracefully"""
        logger.info("Shutting down FaceLogX system...")
        self.running = False

        self.lcd_manager.show_shutdown()
        self.camera_manager.stop_all()

        # Print stats
        for cam_id, proc in self.face_processors.items():
            stats = proc.get_stats()
            logger.info(
                f"Camera {cam_id} stats: "
                f"{stats['total_scans']} scans, "
                f"{stats['total_recognized']} recognized, "
                f"{stats['total_unknown']} unknown"
            )

        logger.info("System stopped.")

    # ============================================
    # FACE RECOGNITION LOOP
    # ============================================

    def _recognition_loop(self, camera_id):
        """Main recognition loop for a single camera (runs in thread)"""
        processor = self.face_processors[camera_id]
        lcd = self.lcd_manager.get_display(camera_id)
        cam = self.camera_manager.get_camera(camera_id)

        logger.info(f"[Camera {camera_id}] Recognition loop started")

        idle_counter = 0

        while self.running:
            try:
                # Check if camera is still connected
                if not cam.connected:
                    lcd.show_error("Cam Offline")
                    time.sleep(5)
                    continue

                # Check if any session is active
                if not any(self.active_sessions.values()):
                    if idle_counter % 30 == 0:  # Update LCD every 30 iterations
                        lcd.show_no_session()
                    idle_counter += 1
                    time.sleep(1)
                    continue

                idle_counter = 0

                # Get latest frame
                frame = self.camera_manager.get_frame(camera_id)
                if frame is None:
                    time.sleep(0.1)
                    continue

                # Process frame for face recognition
                results = processor.process_frame(frame, self.active_sessions)

                # If no faces detected for a while, show scanning message
                if not results:
                    lcd.show_scanning()

                # Small delay to control processing rate
                time.sleep(0.2)  # ~5 FPS processing

            except Exception as e:
                logger.error(f"[Camera {camera_id}] Recognition error: {e}")
                time.sleep(1)

        logger.info(f"[Camera {camera_id}] Recognition loop stopped")

    def _start_recognition_threads(self):
        """Start recognition thread for each connected camera"""
        for cam_id in self.camera_manager.get_connected_cameras():
            thread = threading.Thread(
                target=self._recognition_loop,
                args=(cam_id,),
                daemon=True,
                name=f"Recognition-Cam{cam_id}",
            )
            thread.start()
            logger.info(f"Started recognition thread for Camera {cam_id}")

    # ============================================
    # BACKGROUND TASKS
    # ============================================

    def _refresh_encodings(self):
        """Download latest face encodings from server"""
        logger.info("Refreshing known face encodings from server...")
        data = self.api.get_known_encodings()
        self._encoding_data = data

        # Distribute to all face processors
        for processor in self.face_processors.values():
            processor.load_known_faces(data)

        logger.info(f"Loaded {len(data)} known faces")

    def _heartbeat_loop(self):
        """Periodically send heartbeat and get session status"""
        while self.running:
            try:
                # Send camera statuses
                statuses = self.camera_manager.get_all_statuses()
                response = self.api.send_heartbeat(statuses)

                if response and "active_sessions" in response:
                    old_sessions = self.active_sessions.copy()
                    self.active_sessions = {
                        "morning": response["active_sessions"].get("morning", False),
                        "afternoon": response["active_sessions"].get("afternoon", False),
                    }

                    # Log session changes
                    for stype in ["morning", "afternoon"]:
                        if self.active_sessions[stype] != old_sessions.get(stype):
                            status = "STARTED" if self.active_sessions[stype] else "STOPPED"
                            logger.info(f"{stype.capitalize()} session {status}")

            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

            time.sleep(SYSTEM["heartbeat_interval"])

    def _encoding_refresh_loop(self):
        """Periodically refresh face encodings from server"""
        while self.running:
            time.sleep(SYSTEM["encoding_refresh_interval"])
            try:
                self._refresh_encodings()
            except Exception as e:
                logger.error(f"Encoding refresh error: {e}")

    def _start_heartbeat_thread(self):
        """Start heartbeat background thread"""
        thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="Heartbeat",
        )
        thread.start()

    def _start_encoding_refresh_thread(self):
        """Start encoding refresh background thread"""
        thread = threading.Thread(
            target=self._encoding_refresh_loop,
            daemon=True,
            name="EncodingRefresh",
        )
        thread.start()


# ============================================
# TEST FUNCTIONS
# ============================================

def test_lcds():
    """Test all LCD displays"""
    print("Testing LCD displays...")
    lcd_manager = LCDManager(CAMERAS, LCD)

    print("1. Showing startup...")
    lcd_manager.show_startup()
    time.sleep(2)

    print("2. Showing scanning...")
    lcd_manager.show_all_scanning()
    time.sleep(2)

    for cam_id, lcd in lcd_manager.displays.items():
        print(f"3. Camera {cam_id}: Showing recognized...")
        lcd.show_recognized("Juan Dela Cruz", "2024-00001")
        time.sleep(2)

        print(f"4. Camera {cam_id}: Showing attendance marked...")
        lcd.show_attendance_marked("Juan", "morning")
        time.sleep(2)

        print(f"5. Camera {cam_id}: Showing unknown...")
        lcd.show_unknown()
        time.sleep(2)

    print("6. Showing no session...")
    lcd_manager.show_all_no_session()
    time.sleep(2)

    print("7. Clearing all...")
    lcd_manager.clear_all()
    print("LCD test complete!")


def test_cameras():
    """Test all camera feeds"""
    print("Testing cameras...")
    cam_manager = CameraManager(CAMERAS)
    results = cam_manager.start_all()

    for cam_id, success in results.items():
        status = "OK" if success else "FAILED"
        print(f"  Camera {cam_id}: {status}")

    print("\nCapturing test frames...")
    time.sleep(2)

    for cam_id in cam_manager.get_connected_cameras():
        frame = cam_manager.get_frame(cam_id)
        if frame is not None:
            h, w = frame.shape[:2]
            print(f"  Camera {cam_id}: Frame captured ({w}x{h})")
        else:
            print(f"  Camera {cam_id}: No frame")

    cam_manager.stop_all()
    print("Camera test complete!")


# ============================================
# ENTRY POINT
# ============================================

def main():
    parser = argparse.ArgumentParser(description="FaceLogX Face Recognition System")
    parser.add_argument("--test-lcd", action="store_true", help="Test LCD displays")
    parser.add_argument("--test-cameras", action="store_true", help="Test camera feeds")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    log_level = "DEBUG" if args.debug else SYSTEM.get("log_level", "INFO")
    setup_logging(log_level)

    if args.test_lcd:
        test_lcds()
        return

    if args.test_cameras:
        test_cameras()
        return

    # Main system
    system = FaceLogXSystem()

    # Handle graceful shutdown
    def signal_handler(sig, frame):
        print("\nReceived shutdown signal...")
        system.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start system
    if not system.start():
        logger.error("System failed to start. Check logs for details.")
        sys.exit(1)

    # Keep main thread alive
    try:
        while system.running:
            time.sleep(1)
    except KeyboardInterrupt:
        system.stop()


if __name__ == "__main__":
    main()
