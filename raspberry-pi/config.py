"""
FaceLogX Raspberry Pi - Configuration
All settings for the face recognition system
"""

# ============================================
# SERVER CONNECTION
# ============================================
SERVER_URL = "http://192.168.1.100:5000/api"  # Change to your FaceLogX server IP
API_KEY = ""  # Set after running: python3 register_pi.py

# ============================================
# CAMERA CONFIGURATION
# ============================================
CAMERAS = [
    {
        "id": 1,               # Database camera ID
        "name": "Camera 1",
        "device_index": 0,     # /dev/video0
        "resolution": (640, 480),
        "fps": 15,
        "lcd_address": 0x27,   # I2C address for this camera's LCD
    },
    {
        "id": 2,
        "name": "Camera 2",
        "device_index": 2,     # /dev/video2 (USB cameras often skip indices)
        "resolution": (640, 480),
        "fps": 15,
        "lcd_address": 0x26,
    },
    {
        "id": 3,
        "name": "Camera 3",
        "device_index": 4,     # /dev/video4
        "resolution": (640, 480),
        "fps": 15,
        "lcd_address": 0x25,
    },
]

# ============================================
# FACE RECOGNITION SETTINGS
# ============================================
FACE_RECOGNITION = {
    "model": "hog",               # "hog" (faster, CPU) or "cnn" (more accurate, GPU)
    "tolerance": 0.5,             # Lower = stricter matching (0.4-0.6 recommended)
    "num_jitters": 1,             # More jitters = more accurate but slower (1-10)
    "scale_factor": 0.5,          # Downscale frame for faster detection (0.25-1.0)
    "min_face_size": 40,          # Minimum face size in pixels
    "recognition_cooldown": 30,   # Seconds before same student can be recognized again
    "unknown_cooldown": 5,        # Seconds before logging unknown face again
}

# ============================================
# LCD DISPLAY SETTINGS
# ============================================
LCD = {
    "i2c_port": 1,                # I2C bus (1 for Pi 4)
    "cols": 16,                   # LCD columns
    "rows": 2,                    # LCD rows
    "expander": "PCF8574",        # I2C expander type
    "scroll_speed": 0.3,          # Seconds between scroll steps for long names
    "display_duration": 3,        # Seconds to show recognition result
    "idle_message_line1": "FaceLogX Ready",
    "idle_message_line2": "Scanning...",
}

# ============================================
# SYSTEM SETTINGS
# ============================================
SYSTEM = {
    "encoding_refresh_interval": 300,  # Seconds between refreshing known faces from server (5 min)
    "heartbeat_interval": 30,          # Seconds between heartbeat pings to server
    "log_level": "INFO",               # DEBUG, INFO, WARNING, ERROR
    "max_threads": 3,                  # One thread per camera
    "save_unknown_faces": False,       # Save images of unknown faces for review
    "unknown_faces_dir": "./unknown_faces",
}
