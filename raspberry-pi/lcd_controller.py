"""
FaceLogX Raspberry Pi - LCD Controller
Controls 3x 16x2 I2C LCD displays (one per camera)
"""

import threading
import time
import logging

logger = logging.getLogger("FaceLogX.LCD")

try:
    from RPLCD.i2c import CharLCD
    LCD_AVAILABLE = True
except ImportError:
    LCD_AVAILABLE = False
    logger.warning("RPLCD not installed. LCD displays will be simulated in console.")


class LCDDisplay:
    """Single LCD display controller"""

    def __init__(self, address, camera_name, port=1, cols=16, rows=2, expander="PCF8574"):
        self.address = address
        self.camera_name = camera_name
        self.cols = cols
        self.rows = rows
        self.lcd = None
        self.lock = threading.Lock()
        self._current_lines = ["", ""]

        if LCD_AVAILABLE:
            try:
                self.lcd = CharLCD(
                    i2c_expander=expander,
                    address=address,
                    port=port,
                    cols=cols,
                    rows=rows,
                    backlight_enabled=True,
                )
                self.lcd.clear()
                logger.info(f"LCD initialized at 0x{address:02X} for {camera_name}")
            except Exception as e:
                logger.error(f"LCD init failed at 0x{address:02X}: {e}")
                self.lcd = None
        else:
            logger.info(f"[SIM LCD 0x{address:02X}] {camera_name}")

    def write(self, line1, line2=""):
        """Write two lines to LCD"""
        with self.lock:
            # Truncate or pad to LCD width
            l1 = line1[:self.cols].ljust(self.cols)
            l2 = line2[:self.cols].ljust(self.cols)

            self._current_lines = [l1, l2]

            if self.lcd:
                try:
                    self.lcd.clear()
                    self.lcd.write_string(l1)
                    self.lcd.cursor_pos = (1, 0)
                    self.lcd.write_string(l2)
                except Exception as e:
                    logger.error(f"LCD write error 0x{self.address:02X}: {e}")
            else:
                # Console simulation
                logger.debug(f"[LCD 0x{self.address:02X}] {l1.strip()} | {l2.strip()}")

    def show_recognized(self, student_name, student_id):
        """Display recognized student"""
        # Truncate name if needed
        name = student_name[:self.cols]
        id_str = student_id[:self.cols]
        self.write(name, id_str)

    def show_unknown(self):
        """Display unknown face detected"""
        self.write("Unknown Face", "Not Registered")

    def show_scanning(self):
        """Display scanning status"""
        self.write("FaceLogX Ready", "Scanning...")

    def show_error(self, msg=""):
        """Display error message"""
        self.write("ERROR", msg[:self.cols] if msg else "Camera Offline")

    def show_no_session(self):
        """Display when no attendance session is active"""
        self.write("No Session", "Waiting...")

    def show_attendance_marked(self, name, session_type):
        """Display attendance confirmation"""
        self.write(f"Present!", f"{session_type.upper()[:3]}: {name[:10]}")

    def clear(self):
        """Clear LCD display"""
        with self.lock:
            self._current_lines = ["", ""]
            if self.lcd:
                try:
                    self.lcd.clear()
                except Exception as e:
                    logger.error(f"LCD clear error: {e}")

    def backlight(self, on=True):
        """Toggle backlight"""
        if self.lcd:
            try:
                self.lcd.backlight_enabled = on
            except Exception:
                pass


class LCDManager:
    """Manages all LCD displays"""

    def __init__(self, camera_configs, lcd_config):
        self.displays = {}
        for cam in camera_configs:
            lcd = LCDDisplay(
                address=cam["lcd_address"],
                camera_name=cam["name"],
                port=lcd_config["i2c_port"],
                cols=lcd_config["cols"],
                rows=lcd_config["rows"],
                expander=lcd_config["expander"],
            )
            self.displays[cam["id"]] = lcd

    def get_display(self, camera_id):
        """Get LCD display for a camera"""
        return self.displays.get(camera_id)

    def show_all_scanning(self):
        """Set all LCDs to scanning mode"""
        for lcd in self.displays.values():
            lcd.show_scanning()

    def show_all_no_session(self):
        """Set all LCDs to no-session mode"""
        for lcd in self.displays.values():
            lcd.show_no_session()

    def clear_all(self):
        """Clear all LCDs"""
        for lcd in self.displays.values():
            lcd.clear()

    def show_startup(self):
        """Display startup message on all LCDs"""
        for lcd in self.displays.values():
            lcd.write("FaceLogX v1.0", "Starting up...")

    def show_shutdown(self):
        """Display shutdown message"""
        for lcd in self.displays.values():
            lcd.write("FaceLogX", "Shutting down...")
            time.sleep(0.5)
            lcd.clear()
            lcd.backlight(False)
