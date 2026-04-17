#!/usr/bin/env python3
"""
FaceLogX - Register Raspberry Pi with the Server
Run this ONCE to register your Pi and get an API key.

Usage:
    python3 register_pi.py
"""

import requests
import json
import socket
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import SERVER_URL


def get_local_ip():
    """Get the Pi's local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "unknown"


def main():
    print("=" * 50)
    print("FaceLogX - Raspberry Pi Registration")
    print("=" * 50)
    print()

    # Test server connection
    print(f"Server URL: {SERVER_URL}")
    try:
        resp = requests.get(f"{SERVER_URL}/health", timeout=5)
        if resp.status_code != 200:
            print(f"ERROR: Server returned status {resp.status_code}")
            sys.exit(1)
        print("Server connection: OK")
    except requests.ConnectionError:
        print(f"ERROR: Cannot connect to server at {SERVER_URL}")
        print("Make sure the FaceLogX server is running and the URL in config.py is correct.")
        sys.exit(1)

    print()

    # Get device info
    hostname = socket.gethostname()
    ip = get_local_ip()

    device_name = input(f"Device name [{hostname}]: ").strip() or hostname
    ip_address = input(f"IP address [{ip}]: ").strip() or ip

    print()
    print(f"Registering Pi: {device_name} ({ip_address})")

    try:
        resp = requests.post(
            f"{SERVER_URL}/face-recognition/register-pi",
            json={"device_name": device_name, "ip_address": ip_address},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        if resp.status_code == 201:
            data = resp.json()
            api_key = data["api_key"]

            print()
            print("SUCCESS! Pi registered.")
            print()
            print("Your API Key:")
            print(f"  {api_key}")
            print()

            # Update config.py automatically
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
            try:
                with open(config_path, "r") as f:
                    config_content = f.read()

                config_content = config_content.replace(
                    'API_KEY = ""',
                    f'API_KEY = "{api_key}"'
                )

                with open(config_path, "w") as f:
                    f.write(config_content)

                print("config.py has been updated automatically with your API key.")
            except Exception as e:
                print(f"Could not update config.py automatically: {e}")
                print(f"Please manually set API_KEY in config.py to: {api_key}")

            print()
            print("Next steps:")
            print("  1. Verify config.py settings (SERVER_URL, camera indices, LCD addresses)")
            print("  2. Test LCDs:     python3 main.py --test-lcd")
            print("  3. Test cameras:  python3 main.py --test-cameras")
            print("  4. Start system:  python3 main.py")
        else:
            print(f"ERROR: Registration failed ({resp.status_code})")
            print(resp.text)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
