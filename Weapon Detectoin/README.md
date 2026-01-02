# Sentinel Eye - Advanced Weapon Detection System

## Overview
Sentinel Eye is a high-performance, real-time weapon detection software designed for CCTV systems. It leverages state-of-the-art Deep Learning (YOLOv8) to detect weapons like guns and knives with high accuracy. The system features a modern, dark-mode user interface, multi-channel alerting (SMS, Local Storage, Audio), and smooth camera performance.

## Unique Features
1.  **Real-Time AI Detection**: Uses YOLOv8 for millisecond-level detection latency.
2.  **Smart Alert Throttling**: Prevents spamming by enforcing cooldowns between alerts.
3.  **Dual-Mode Alerting**: Sends SMS (via Twilio) and saves visual evidence to a local secure vault (`snapshots/`).
4.  **Interactive Sensitivity Control**: Adjust detection confidence threshold in real-time without restarting.
5.  **Audit Log**: Visual sidebar log of all detection events with timestamps.
6.  **Audio Alarm Integration**: Plays an audible alarm immediately upon detection.

## Technologies Used
- **Python 3.9+**: Core language.
- **YOLOv8 (Ultralytics)**: Object detection engine.
- **OpenCV**: Video processing and image manipulation.
- **CustomTkinter**: Modern, high-DPI aware GUI framework.
- **Twilio**: SMS/WhatsApp API gateway.
- **Pillow**: Image processing for UI.

## Installation

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: Ensure you have a working webcam connected.*

2.  **Run the Software**:
    ```bash
    python app.py
    ```

## Configuration
- **Twilio (SMS)**: 
    - Enter your Account SID, Auth Token, and Target Phone Number in the sidebar configuration panel.
    - Click "Save Config" to enable SMS alerts.
- **Audio**: Toggle the "Audio Alarm" switch in the sidebar.
- **Sensitivity**: Use the slider to filter out false positives.

## Testing
For demonstration purposes, the system is configured to treat **Cell Phones** as "Simulated Guns" to allow for safe testing without real weapons. It also detects **Knives** and **Scissors**.

## Directory Structure
- `app.py`: Main application entry point.
- `detector.py`: AI model logic.
- `notifier.py`: Alert management system.
- `assets/`: Sound files and icons.
- `snapshots/`: Saved evidence images.

---
**Disclaimer**: This software is for educational and safety demonstration purposes. Always verify detections manually before taking action.
