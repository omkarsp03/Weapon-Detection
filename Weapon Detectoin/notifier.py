import os
import time
from twilio.rest import Client
import cv2
from datetime import datetime
from threading import Thread

class AlertManager:
    def __init__(self, sms_sid=None, sms_auth=None, sms_from=None, sms_to=None):
        self.last_alert_time = 0
        self.alert_cooldown = 10  # seconds
        self.sms_enabled = False
        self.whatsapp_enabled = False
        self.save_enabled = True
        
        # Twilio Config (Placeholders)
        self.account_sid = sms_sid or "AC_YOUR_ACCOUNT_SID"
        self.auth_token = sms_auth or "YOUR_AUTH_TOKEN"
        self.from_number = sms_from or "+1234567890"
        self.to_number = sms_to or "+0987654321"
        
        try:
            if self.account_sid != "AC_YOUR_ACCOUNT_SID":
                self.client = Client(self.account_sid, self.auth_token)
                self.sms_enabled = True
        except:
            print("Twilio client init failed. SMS disabled.")
            self.sms_enabled = False

    def trigger_alert(self, frame, detection_label, detections):
        current_time = time.time()
        if current_time - self.last_alert_time < self.alert_cooldown:
            return False

        self.last_alert_time = current_time
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"snapshots/alert_{timestamp}_{detection_label.replace(' ', '_')}.jpg"
        
        # Draw boxes on the frame for the alert image
        alert_frame = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det['box']
            label = f"{det['label']} {det['confidence']:.2f}"
            cv2.rectangle(alert_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(alert_frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        
        # Save image
        if self.save_enabled:
            cv2.imwrite(filename, alert_frame)
            print(f"Alert saved: {filename}")

        # Send SMS/WhatsApp (Threaded to not block UI)
        if self.sms_enabled:
            Thread(target=self._send_twilio, args=(detection_label,)).start()
            
        return True

    def _send_twilio(self, label):
        try:
            message = self.client.messages.create(
                body=f"SECURITY ALERT: {label} detected!",
                from_=self.from_number,
                to=self.to_number
            )
            print(f"SMS sent: {message.sid}")
        except Exception as e:
            print(f"Failed to send SMS: {e}")

    def toggle_sms(self, state):
        self.sms_enabled = state

    def set_twilio_config(self, sid, token, from_num, to_num):
        self.account_sid = sid
        self.auth_token = token
        self.from_number = from_num
        self.to_number = to_num
        try:
            self.client = Client(sid, token)
            self.sms_enabled = True
            return True
        except:
            self.sms_enabled = False
            return False
