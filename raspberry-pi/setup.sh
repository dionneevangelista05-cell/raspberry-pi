#!/bin/bash
# ============================================
# FaceLogX Raspberry Pi Setup Script
# Run this on a fresh Raspberry Pi OS installation
# ============================================

set -e

echo "============================================"
echo "FaceLogX Raspberry Pi Setup"
echo "============================================"
echo ""

# Update system
echo "[1/7] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Enable I2C
echo "[2/7] Enabling I2C interface..."
sudo raspi-config nonint do_i2c 0
echo "I2C enabled."

# Install system dependencies
echo "[3/7] Installing system dependencies..."
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-smbus \
    i2c-tools \
    cmake \
    build-essential \
    libatlas-base-dev \
    libopenblas-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libffi-dev

# Verify I2C devices
echo "[4/7] Scanning I2C bus..."
echo "I2C devices found:"
sudo i2cdetect -y 1 || echo "No I2C devices detected. Check LCD wiring."

# Verify cameras
echo "[5/7] Checking connected cameras..."
echo "Video devices:"
ls /dev/video* 2>/dev/null || echo "No video devices found. Check USB cameras."

# Create virtual environment and install Python packages
echo "[6/7] Installing Python dependencies..."
cd "$(dirname "$0")"

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

deactivate
echo "Python dependencies installed in virtual environment."

# Create systemd service for auto-start
echo "[7/7] Creating systemd service..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

sudo tee /etc/systemd/system/facelogx.service > /dev/null <<EOF
[Unit]
Description=FaceLogX Face Recognition System
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/venv/bin/python3 $SCRIPT_DIR/main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
echo "Systemd service created (not enabled yet)."

echo ""
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo ""
echo "Next Steps:"
echo ""
echo "  1. Edit config.py:"
echo "     - Set SERVER_URL to your FaceLogX server IP"
echo "     - Verify camera device_index values"
echo "     - Verify LCD I2C addresses"
echo ""
echo "  2. Register this Pi with the server:"
echo "     source venv/bin/activate"
echo "     python3 register_pi.py"
echo ""
echo "  3. Test hardware:"
echo "     python3 main.py --test-lcd"
echo "     python3 main.py --test-cameras"
echo ""
echo "  4. Start the system:"
echo "     python3 main.py"
echo ""
echo "  5. (Optional) Enable auto-start on boot:"
echo "     sudo systemctl enable facelogx"
echo "     sudo systemctl start facelogx"
echo ""
echo "  6. Enroll student faces:"
echo "     python3 enroll_face.py <student_id>"
echo ""
