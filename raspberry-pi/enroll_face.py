#!/usr/bin/env python3
"""
FaceLogX - Register a Student's Face from Pi Camera
Captures face encoding using the Pi camera and uploads to server.
Much more accurate than browser-based registration.

Usage:
    python3 enroll_face.py <student_id> [camera_index]

Examples:
    python3 enroll_face.py 2024-00001
    python3 enroll_face.py 2024-00001 2
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SERVER_URL, API_KEY, CAMERAS
from api_client import FaceLogXAPI
from face_processor import FaceEnroller


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 enroll_face.py <student_id> [camera_index]")
        print("Example: python3 enroll_face.py 2024-00001")
        sys.exit(1)

    student_id = sys.argv[1]
    device_index = int(sys.argv[2]) if len(sys.argv) > 2 else CAMERAS[0]["device_index"]

    if not API_KEY:
        print("ERROR: No API key configured. Run register_pi.py first.")
        sys.exit(1)

    print(f"FaceLogX Face Enrollment")
    print(f"Student ID: {student_id}")
    print(f"Camera: /dev/video{device_index}")
    print()

    api = FaceLogXAPI(SERVER_URL, API_KEY)

    if not api.test_connection():
        print("ERROR: Cannot connect to server")
        sys.exit(1)

    enroller = FaceEnroller(api, num_jitters=10)
    success = enroller.enroll_from_camera(device_index, student_id)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
