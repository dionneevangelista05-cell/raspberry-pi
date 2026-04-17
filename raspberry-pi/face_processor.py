"""
FaceLogX Raspberry Pi - Face Processor
Face detection, encoding, and recognition using face_recognition library
"""

import face_recognition
import numpy as np
import cv2
import time
import logging
import threading

logger = logging.getLogger("FaceLogX.Face")


class FaceProcessor:
    """Handles face detection and recognition for a single camera"""

    def __init__(self, camera_id, config, api_client, lcd_display):
        self.camera_id = camera_id
        self.config = config
        self.api = api_client
        self.lcd = lcd_display

        # Recognition settings
        self.model = config.get("model", "hog")
        self.tolerance = config.get("tolerance", 0.5)
        self.num_jitters = config.get("num_jitters", 1)
        self.scale_factor = config.get("scale_factor", 0.5)
        self.recognition_cooldown = config.get("recognition_cooldown", 30)
        self.unknown_cooldown = config.get("unknown_cooldown", 5)

        # Known faces database (refreshed from server periodically)
        self.known_encodings = []  # List of numpy arrays
        self.known_ids = []        # List of student IDs
        self.known_names = []      # List of student names
        self.lock = threading.Lock()

        # Cooldown tracking (prevent duplicate recognitions)
        self._last_recognized = {}  # student_id -> timestamp
        self._last_unknown = 0

        # Stats
        self.total_scans = 0
        self.total_recognized = 0
        self.total_unknown = 0

    def load_known_faces(self, encodings_data):
        """Load known face encodings from server data"""
        with self.lock:
            self.known_encodings = []
            self.known_ids = []
            self.known_names = []

            for entry in encodings_data:
                try:
                    encoding = np.array(entry["encoding"], dtype=np.float64)
                    if encoding.shape == (128,):
                        self.known_encodings.append(encoding)
                        self.known_ids.append(entry["student_id"])
                        self.known_names.append(entry["name"])
                except (ValueError, KeyError) as e:
                    logger.warning(f"Invalid encoding for {entry.get('student_id', '?')}: {e}")

            logger.info(
                f"[Camera {self.camera_id}] Loaded {len(self.known_encodings)} known faces"
            )

    def process_frame(self, frame, active_sessions):
        """
        Process a single video frame:
        1. Detect faces
        2. Encode detected faces
        3. Compare against known faces
        4. Report results to server and LCD

        Returns list of recognition results
        """
        if frame is None:
            return []

        self.total_scans += 1
        results = []

        # Resize frame for faster processing
        small_frame = cv2.resize(
            frame, (0, 0),
            fx=self.scale_factor,
            fy=self.scale_factor
        )

        # Convert BGR (OpenCV) to RGB (face_recognition)
        rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        # Detect face locations
        face_locations = face_recognition.face_locations(rgb_frame, model=self.model)

        if not face_locations:
            return []

        # Encode detected faces
        face_encodings = face_recognition.face_encodings(
            rgb_frame,
            face_locations,
            num_jitters=self.num_jitters
        )

        now = time.time()

        with self.lock:
            for face_encoding, face_location in zip(face_encodings, face_locations):
                # Compare against known faces
                if len(self.known_encodings) == 0:
                    self._handle_unknown(now)
                    results.append({"recognized": False, "location": face_location})
                    continue

                # Calculate face distances
                face_distances = face_recognition.face_distance(
                    self.known_encodings, face_encoding
                )

                best_match_index = np.argmin(face_distances)
                best_distance = face_distances[best_match_index]
                confidence = 1.0 - best_distance

                if best_distance <= self.tolerance:
                    # RECOGNIZED
                    student_id = self.known_ids[best_match_index]
                    student_name = self.known_names[best_match_index]

                    result = {
                        "recognized": True,
                        "student_id": student_id,
                        "student_name": student_name,
                        "confidence": confidence,
                        "location": face_location,
                    }

                    # Check cooldown
                    last_time = self._last_recognized.get(student_id, 0)
                    if now - last_time >= self.recognition_cooldown:
                        self._last_recognized[student_id] = now
                        self.total_recognized += 1

                        # Report to server
                        server_response = self.api.report_recognition(
                            student_id, self.camera_id, confidence
                        )

                        # Update LCD
                        if server_response and server_response.get("attendance_recorded"):
                            sessions = server_response.get("sessions", [])
                            session_str = "/".join(sessions)
                            self.lcd.show_attendance_marked(student_name, session_str)
                        else:
                            self.lcd.show_recognized(student_name, student_id)

                        logger.info(
                            f"[Camera {self.camera_id}] Recognized: {student_name} "
                            f"(confidence: {confidence:.2%})"
                        )

                        result["attendance_recorded"] = (
                            server_response.get("attendance_recorded", False)
                            if server_response else False
                        )
                    else:
                        result["cooldown"] = True

                    results.append(result)
                else:
                    # UNKNOWN FACE
                    self._handle_unknown(now)
                    results.append({
                        "recognized": False,
                        "confidence": confidence,
                        "location": face_location,
                    })

        return results

    def _handle_unknown(self, now):
        """Handle unrecognized face with cooldown"""
        if now - self._last_unknown >= self.unknown_cooldown:
            self._last_unknown = now
            self.total_unknown += 1
            self.api.report_unknown(self.camera_id)
            self.lcd.show_unknown()
            logger.info(f"[Camera {self.camera_id}] Unknown face detected")

    def get_stats(self):
        """Return processing stats"""
        return {
            "camera_id": self.camera_id,
            "total_scans": self.total_scans,
            "total_recognized": self.total_recognized,
            "total_unknown": self.total_unknown,
            "known_faces": len(self.known_encodings),
        }


class FaceEnroller:
    """
    Standalone face enrollment: captures face from camera and registers encoding on server.
    Used for Pi-side face registration (more accurate than browser).
    """

    def __init__(self, api_client, num_jitters=10):
        self.api = api_client
        self.num_jitters = num_jitters  # More jitters = better encoding for registration

    def enroll_from_camera(self, device_index, student_id):
        """
        Capture face from camera and register encoding on server.
        Returns True on success.
        """
        logger.info(f"Starting enrollment for student {student_id} on camera {device_index}")

        cap = cv2.VideoCapture(device_index)
        if not cap.isOpened():
            logger.error(f"Cannot open camera {device_index}")
            return False

        try:
            # Wait for camera to warm up
            for _ in range(10):
                cap.read()

            # Capture multiple frames and pick the best face
            best_encoding = None
            best_size = 0

            print(f"Capturing face for student {student_id}...")
            print("Look directly at the camera. Capturing in 3 seconds...")
            time.sleep(3)

            for i in range(5):
                ret, frame = cap.read()
                if not ret:
                    continue

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb_frame, model="hog")

                if len(face_locations) == 1:
                    top, right, bottom, left = face_locations[0]
                    face_size = (bottom - top) * (right - left)

                    if face_size > best_size:
                        encodings = face_recognition.face_encodings(
                            rgb_frame,
                            face_locations,
                            num_jitters=self.num_jitters
                        )
                        if encodings:
                            best_encoding = encodings[0]
                            best_size = face_size
                            print(f"  Frame {i+1}: Face captured (size: {face_size})")
                elif len(face_locations) == 0:
                    print(f"  Frame {i+1}: No face detected")
                else:
                    print(f"  Frame {i+1}: Multiple faces detected ({len(face_locations)}), skipping")

                time.sleep(0.5)

            if best_encoding is None:
                logger.error("No clear face detected during enrollment")
                print("ERROR: Could not detect a clear face. Please try again.")
                return False

            # Upload to server
            encoding_list = best_encoding.tolist()
            success = self.api.upload_encoding(student_id, encoding_list)

            if success:
                print(f"SUCCESS: Face registered for student {student_id}")
                logger.info(f"Enrollment complete for student {student_id}")
                return True
            else:
                print("ERROR: Failed to upload encoding to server")
                return False

        finally:
            cap.release()

    def enroll_from_image(self, image_path, student_id):
        """Register face from an image file"""
        logger.info(f"Enrolling from image: {image_path}")

        image = face_recognition.load_image_file(image_path)
        face_locations = face_recognition.face_locations(image)

        if len(face_locations) == 0:
            print("ERROR: No face detected in image")
            return False
        if len(face_locations) > 1:
            print("WARNING: Multiple faces detected, using the first one")

        encodings = face_recognition.face_encodings(
            image,
            [face_locations[0]],
            num_jitters=self.num_jitters
        )

        if not encodings:
            print("ERROR: Could not encode face")
            return False

        encoding_list = encodings[0].tolist()
        success = self.api.upload_encoding(student_id, encoding_list)

        if success:
            print(f"SUCCESS: Face registered for student {student_id}")
            return True
        else:
            print("ERROR: Failed to upload encoding")
            return False
