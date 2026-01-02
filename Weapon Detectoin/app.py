import customtkinter as ctk
from tkinter import filedialog
import cv2
from PIL import Image, ImageTk
from detector import WeaponDetector
from notifier import AlertManager
from evidence import EvidenceLocker
import threading
import time
import os
import sys

# Configuration
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class WeaponDetectionApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Sentinel Eye - Advanced Weapon Detection System")
        self.geometry("1200x800")
        
        # Force window to top and focus
        self.lift()
        self.attributes('-topmost',True)
        self.after_idle(self.attributes,'-topmost',False)

        # Initialize Logic
        self.detector = WeaponDetector()
        self.alerter = AlertManager()
        self.evidence_locker = EvidenceLocker()
        self.cap = None
        self.is_running = False
        self.audio_enabled = True
        
        # State
        self.current_threat_level = 0.0
        self.threat_persistence = {} # Label -> frames
        self.escalated = False
        
        # Incident Capture State
        self.incident_capture_active = False
        self.incident_frames_left = 0
        self.current_incident_id = None
        
        # Performance
        self.frame_count = 0
        self.skip_frames = 0
        self.last_detections = []
        self.last_persons = []
        
        # Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._create_sidebar()
        self._create_main_view()
        self._create_right_panel()

    def _create_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar, text="SENTINEL EYE", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.start_btn = ctk.CTkButton(self.sidebar, text="START CAMERA", command=self.toggle_camera, fg_color="green")
        self.start_btn.grid(row=1, column=0, padx=20, pady=10)
        
        # Threat Level Indicator
        self.threat_frame = ctk.CTkFrame(self.sidebar)
        self.threat_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkLabel(self.threat_frame, text="THREAT LEVEL").pack()
        self.threat_bar = ctk.CTkProgressBar(self.threat_frame, orientation="horizontal")
        self.threat_bar.set(0)
        self.threat_bar.pack(pady=5)
        
        self.ack_btn = ctk.CTkButton(self.sidebar, text="ACKNOWLEDGE ALERT", command=self.acknowledge_alert, fg_color="gray", state="disabled")
        self.ack_btn.grid(row=3, column=0, padx=20, pady=10)

        # Model Config
        self.model_frame = ctk.CTkFrame(self.sidebar)
        self.model_frame.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(self.model_frame, text="Model Config").pack(pady=2)
        
        self.model_option = ctk.CTkOptionMenu(self.model_frame, values=["YOLOv8 Nano", "YOLOv8 Medium"], command=self.change_model)
        self.model_option.set("YOLOv8 Medium")
        self.model_option.pack(pady=5)
        
        self.custom_model_btn = ctk.CTkButton(self.model_frame, text="Load Custom Weights", command=self.load_custom_model, height=25)
        self.custom_model_btn.pack(pady=5)

        self.high_res_switch = ctk.CTkSwitch(self.model_frame, text="High-Res (1280px)", command=self.toggle_high_res)
        self.high_res_switch.pack(pady=5)
        
        self.skip_label = ctk.CTkLabel(self.model_frame, text="Skip Frames: 0")
        self.skip_label.pack(pady=(5,0))
        self.skip_slider = ctk.CTkSlider(self.model_frame, from_=0, to=10, number_of_steps=10, command=self.update_skip)
        self.skip_slider.set(0)
        self.skip_slider.pack(pady=5)

        self.conf_label = ctk.CTkLabel(self.sidebar, text="Sensitivity: 50%", anchor="w")
        self.conf_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        self.conf_slider = ctk.CTkSlider(self.sidebar, from_=0, to=1, number_of_steps=100, command=self.update_conf)
        self.conf_slider.set(0.5)
        self.conf_slider.grid(row=6, column=0, padx=20, pady=10)

        self.audio_switch = ctk.CTkSwitch(self.sidebar, text="Audio Alarm", command=self.toggle_audio)
        self.audio_switch.select()
        self.audio_switch.grid(row=7, column=0, padx=20, pady=10)

        self.privacy_switch = ctk.CTkSwitch(self.sidebar, text="Privacy Shield", command=self.toggle_privacy)
        self.privacy_switch.select()
        self.privacy_switch.grid(row=8, column=0, padx=20, pady=10)

        self.sms_switch = ctk.CTkSwitch(self.sidebar, text="SMS Alerts", command=self.toggle_sms)
        self.sms_switch.grid(row=9, column=0, padx=20, pady=10)
        
        # Twilio Config Inputs
        self.twilio_frame = ctk.CTkFrame(self.sidebar)
        self.twilio_frame.grid(row=10, column=0, padx=10, pady=10)
        ctk.CTkLabel(self.twilio_frame, text="Twilio Config (Optional)").pack()
        self.entry_sid = ctk.CTkEntry(self.twilio_frame, placeholder_text="Account SID")
        self.entry_sid.pack(pady=5)
        self.entry_token = ctk.CTkEntry(self.twilio_frame, placeholder_text="Auth Token", show="*")
        self.entry_token.pack(pady=5)
        self.entry_to = ctk.CTkEntry(self.twilio_frame, placeholder_text="To Phone (+1...)")
        self.entry_to.pack(pady=5)
        ctk.CTkButton(self.twilio_frame, text="Save Config", command=self.save_twilio, height=25).pack(pady=5)

        self.status_label = ctk.CTkLabel(self.sidebar, text="Status: Ready", text_color="gray")
        self.status_label.grid(row=11, column=0, padx=20, pady=20)

    def _create_main_view(self):
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.video_label = ctk.CTkLabel(self.main_frame, text="", corner_radius=10)
        self.video_label.pack(expand=True, fill="both")

    def _create_right_panel(self):
        self.right_panel = ctk.CTkScrollableFrame(self, width=250, label_text="Detection Log")
        self.right_panel.grid(row=0, column=2, sticky="nsew", padx=(0, 20), pady=20)

    def change_model(self, choice):
        model_map = {
            "YOLOv8 Nano": "yolov8n.pt",
            "YOLOv8 Medium": "yolov8m.pt"
        }
        path = model_map.get(choice, "yolov8m.pt")
        # Run in thread to avoid freezing UI
        threading.Thread(target=self._load_model_thread, args=(path, choice)).start()

    def _load_model_thread(self, path, name):
        self.status_label.configure(text=f"Loading {name}...", text_color="orange")
        success = self.detector.load_model(path)
        if success:
            self.status_label.configure(text=f"Loaded {name}", text_color="green")
        else:
            self.status_label.configure(text=f"Failed to load {name}", text_color="red")

    def load_custom_model(self):
        file_path = filedialog.askopenfilename(filetypes=[("YOLO Weights", "*.pt")])
        if file_path:
            threading.Thread(target=self._load_model_thread, args=(file_path, "Custom Model")).start()
            self.model_option.set("Custom")

    def toggle_high_res(self):
        enabled = self.high_res_switch.get()
        self.detector.set_high_res_mode(enabled)
        mode = "High-Res" if enabled else "Standard"
        self.status_label.configure(text=f"Mode: {mode}", text_color="blue")

    def update_skip(self, value):
        self.skip_frames = int(value)
        self.skip_label.configure(text=f"Skip Frames: {self.skip_frames}")

    def toggle_camera(self):
        if self.is_running:
            self.is_running = False
            self.start_btn.configure(text="START CAMERA", fg_color="green")
            if self.cap:
                self.cap.release()
            self.video_label.configure(image=None)
            self.status_label.configure(text="Status: Stopped", text_color="red")
        else:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                self.status_label.configure(text="Error: No Camera", text_color="red")
                return
            self.is_running = True
            self.start_btn.configure(text="STOP CAMERA", fg_color="red")
            self.status_label.configure(text="Status: Monitoring...", text_color="#00ff00")
            self.update_frame()

    def update_conf(self, value):
        self.detector.set_confidence(value)
        self.conf_label.configure(text=f"Sensitivity: {int(value*100)}%")

    def toggle_audio(self):
        self.audio_enabled = self.audio_switch.get()

    def toggle_privacy(self):
        self.detector.set_privacy(self.privacy_switch.get())

    def toggle_sms(self):
        self.alerter.toggle_sms(self.sms_switch.get())
        
    def acknowledge_alert(self):
        self.escalated = False
        self.ack_btn.configure(state="disabled", fg_color="gray")
        self.threat_persistence.clear()
        self.threat_bar.set(0)
        self.status_label.configure(text="Status: Monitoring...", text_color="#00ff00")

    def save_twilio(self):
        sid = self.entry_sid.get()
        token = self.entry_token.get()
        to_num = self.entry_to.get()
        # Default from number for demo
        success = self.alerter.set_twilio_config(sid, token, "+1234567890", to_num)
        if success:
            self.status_label.configure(text="Twilio Connected", text_color="green")
        else:
            self.status_label.configure(text="Twilio Failed", text_color="red")

    def play_alarm(self):
        if self.audio_enabled and not self.escalated:
            # macOS native sound with Max Volume
            if sys.platform == 'darwin':
                try:
                    # Set system volume to 100% (User requested "too loud")
                    os.system("osascript -e 'set volume output volume 100'")
                    os.system('afplay assets/alarm.wav&')
                except Exception as e:
                    print(f"Alarm error: {e}")
            else:
                # Linux/Windows fallback (assuming aplayer or similar, or just print)
                print("BEEP! (LOUD)") 

    def log_detection(self, label, hash_entry=None):
        timestamp = time.strftime("%H:%M:%S")
        text = f"[{timestamp}] {label}"
        if hash_entry:
            text += " (Secured)"
        log_entry = ctk.CTkLabel(self.right_panel, text=text, text_color="red", anchor="w")
        log_entry.pack(fill="x", padx=5, pady=2)

    def update_frame(self):
        if not self.is_running:
            return

        ret, frame = self.cap.read()
        if ret:
            self.frame_count += 1
            
            # Force inference during incident capture to ensure we get bounding boxes for all 5 shots
            should_infer = (self.skip_frames == 0) or \
                           (self.frame_count % (self.skip_frames + 1) == 0) or \
                           self.incident_capture_active

            if should_infer:
                # Detection
                self.last_detections, self.last_persons = self.detector.detect(frame)
                detections = self.last_detections
            else:
                detections = self.last_detections
                self.detector.apply_privacy_blur(frame, self.last_persons)
            
            # Threat Logic
            if detections:
                self.current_threat_level = min(1.0, self.current_threat_level + 0.1)
                for det in detections:
                    label = det['label']
                    self.threat_persistence[label] = self.threat_persistence.get(label, 0) + 1
            else:
                self.current_threat_level = max(0.0, self.current_threat_level - 0.05)
                # Decay persistence
                for k in list(self.threat_persistence.keys()):
                    self.threat_persistence[k] = max(0, self.threat_persistence[k] - 1)
                    if self.threat_persistence[k] == 0:
                        del self.threat_persistence[k]

            self.threat_bar.set(self.current_threat_level)

            # Annotate & Alert
            detected_threats = []
            
            for det in detections:
                x1, y1, x2, y2 = det['box']
                label = f"{det['label']} {det['confidence']:.2f}"
                color = (0, 0, 255) # Red for weapon
                
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
                # Check Persistence for Alert Escalation
                # Alert if seen for > 5 frames
                if self.threat_persistence.get(det['label'], 0) > 5:
                    detected_threats.append(det)

            # --- ESCALATION LOGIC ---
            if detected_threats and not self.escalated:
                self.escalated = True
                self.ack_btn.configure(state="normal", fg_color="red")
                self.status_label.configure(text="Status: THREAT DETECTED", text_color="red")
                
                # Start Incident Capture (5 shots)
                label = detected_threats[0]['label']
                self.incident_capture_active = True
                self.incident_frames_left = 5
                self.current_incident_id = self.evidence_locker.create_incident_id(label)
                
                # Trigger Alert (Notification)
                self.alerter.trigger_alert(frame, label, detected_threats)
                self.play_alarm()
                
                # Log to UI (Initial)
                self.log_detection(label, hash_entry=True)

            # --- INCIDENT CAPTURE (BURST) ---
            if self.incident_capture_active and self.incident_frames_left > 0:
                # Capture current frame as evidence
                shot_idx = 5 - self.incident_frames_left
                self.evidence_locker.secure_evidence(
                    frame, 
                    detections, # Use all current detections
                    incident_id=self.current_incident_id,
                    shot_index=shot_idx
                )
                self.incident_frames_left -= 1
                
                if self.incident_frames_left == 0:
                    self.incident_capture_active = False
                    self.status_label.configure(text="Evidence Secured", text_color="orange")

            # Convert to PIL for Tkinter
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            
            # Resize to fit (maintain aspect ratio)
            display_w = self.video_label.winfo_width()
            display_h = self.video_label.winfo_height()
            
            if display_w > 10 and display_h > 10:
                img.thumbnail((display_w, display_h))
                
            imgtk = ImageTk.PhotoImage(image=img)
            self.video_label.imgtk = imgtk
            self.video_label.configure(image=imgtk)

        self.after(10, self.update_frame)

    def on_closing(self):
        if self.cap:
            self.cap.release()
        self.destroy()

if __name__ == "__main__":
    print("Starting app...")
    try:
        app = WeaponDetectionApp()
        print("App initialized, starting mainloop...")
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.mainloop()
    except Exception as e:
        print(f"Error starting app: {e}")
        import traceback
        traceback.print_exc()
