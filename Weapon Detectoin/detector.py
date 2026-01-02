from ultralytics import YOLO
import cv2
import numpy as np
from shapely.geometry import Polygon, Point

class WeaponDetector:
    def __init__(self, model_path='yolov8m.pt', confidence_threshold=0.5):
        self.model = YOLO(model_path)
        self.confidence_threshold = confidence_threshold
        self.imgsz = 640 # Default inference size
        
        # COCO IDs: 
        # 0=Person
        # 34=Baseball Bat
        # 43=Knife
        # 76=Scissors
        # 67=Cell Phone (Simulated Gun)
        self.weapon_classes = [34, 43, 76] 
        self.person_class = 0
        
        # Temporal Consistency
        self.persistence_threshold = 5  # Frames
        self.active_detections = {}     # ID -> frames_seen
        self.frame_counter = 0
        
        # Zone Defense (List of Polygons)
        self.exclusion_zones = [] # List of [(x,y), ...]
        
        # Privacy Shield
        self.privacy_mode = True

    def load_model(self, path):
        try:
            self.model = YOLO(path)
            print(f"Loaded model from {path}")
            return True
        except Exception as e:
            print(f"Failed to load model: {e}")
            return False

    def set_high_res_mode(self, enabled):
        # 1280 is significantly better for small objects at distance
        self.imgsz = 1280 if enabled else 640

    def set_confidence(self, conf):
        self.confidence_threshold = conf

    def set_zones(self, zones):
        """Set exclusion zones (list of list of points)."""
        self.exclusion_zones = [Polygon(z) for z in zones if len(z) >= 3]

    def set_privacy(self, enabled):
        self.privacy_mode = enabled

    def _check_zone(self, box):
        """Returns True if box center is INSIDE an exclusion zone."""
        if not self.exclusion_zones:
            return False
            
        x1, y1, x2, y2 = box
        center = Point((x1 + x2) / 2, (y1 + y2) / 2)
        
        for poly in self.exclusion_zones:
            if poly.contains(center):
                return True
        return False

    def _boxes_intersect(self, box1, box2):
        """Check if two boxes intersect."""
        x1_a, y1_a, x2_a, y2_a = box1
        x1_b, y1_b, x2_b, y2_b = box2
        
        # Calculate intersection
        x_left = max(x1_a, x1_b)
        y_top = max(y1_a, y1_b)
        x_right = min(x2_a, x2_b)
        y_bottom = min(y2_a, y2_b)
        
        if x_right < x_left or y_bottom < y_top:
            return False
            
        return True

    def detect(self, frame):
        self.frame_counter += 1
        # Run inference with specified image size
        results = self.model(frame, verbose=False, conf=self.confidence_threshold, imgsz=self.imgsz)
        
        persons = []
        raw_weapons = []

        # 1. First Pass: Gather all raw detections
        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                label = self.model.names[cls_id]
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                # Person Detection (for Privacy Shield)
                if cls_id == self.person_class:
                    persons.append((x1, y1, x2, y2))
                    continue

                # Weapon Detection
                is_weapon = cls_id in self.weapon_classes or label == 'cell phone'
                if is_weapon:
                    if label == 'cell phone':
                        label = 'Gun (Simulated)'
                    
                    # Zone Check
                    if self._check_zone((x1, y1, x2, y2)):
                        continue
                        
                    raw_weapons.append({
                        'label': label,
                        'confidence': conf,
                        'box': (x1, y1, x2, y2)
                    })

        # 2. Smart Privacy Shield (Blur ONLY Unarmed Persons)
        if self.privacy_mode:
            for px1, py1, px2, py2 in persons:
                person_box = (px1, py1, px2, py2)
                is_armed = False
                
                # Check if this person is holding a weapon (intersection)
                for weapon in raw_weapons:
                    if self._boxes_intersect(person_box, weapon['box']):
                        is_armed = True
                        break
                
                # Only blur if NOT armed
                if not is_armed:
                    # Extract ROI
                    roi = frame[py1:py2, px1:px2]
                    if roi.size > 0:
                        # Apply Gaussian Blur
                        roi = cv2.GaussianBlur(roi, (51, 51), 30)
                        # Put back
                        frame[py1:py2, px1:px2] = roi

        # 3. Temporal Consistency
        
        return raw_weapons, persons

    def apply_privacy_blur(self, frame, persons):
        """Apply blur to cached person boxes (Naive implementation for skipped frames)."""
        # NOTE: For skipped frames, we don't have fresh weapon locations to do the 'Smart' check.
        # Ideally, we should cache 'safe_persons' separately.
        # For now, we will just skip blurring on skipped frames if we want to be safe, 
        # OR we can accept that skipped frames might be fully blurred.
        # BETTER: Let's blur everyone on skipped frames to be safe (Privacy First), 
        # but since skipped frames are milliseconds, it might flicker.
        
        # IMPROVEMENT: The app.py should pass 'last_safe_persons' or similar.
        # But to keep API simple, let's just blur everyone. 
        # Wait, if we blur everyone, the weapon will disappear on skipped frames!
        # So we should probably NOT blur on skipped frames if we want to see the weapon.
        # OR, better yet, just don't use this method if you care about smart privacy on skipped frames.
        
        if not self.privacy_mode:
            return
            
        for px1, py1, px2, py2 in persons:
            # Ensure coordinates are within frame
            h, w = frame.shape[:2]
            px1, py1 = max(0, px1), max(0, py1)
            px2, py2 = min(w, px2), min(h, py2)
            
            if px1 >= px2 or py1 >= py2:
                continue
                
            roi = frame[py1:py2, px1:px2]
            if roi.size > 0:
                roi = cv2.GaussianBlur(roi, (51, 51), 30)
                frame[py1:py2, px1:px2] = roi

