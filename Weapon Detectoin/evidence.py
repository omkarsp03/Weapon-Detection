import hashlib
import json
import os
from datetime import datetime
import cv2

class EvidenceLocker:
    def __init__(self, evidence_dir="snapshots"):
        self.evidence_dir = evidence_dir
        self.chain_file = os.path.join(evidence_dir, "chain_log.json")
        self.last_hash = "0" * 64
        
        if not os.path.exists(evidence_dir):
            os.makedirs(evidence_dir)
            
        self._load_chain()

    def _load_chain(self):
        """Load the last hash from the chain log if it exists."""
        if os.path.exists(self.chain_file):
            try:
                with open(self.chain_file, 'r') as f:
                    chain = json.load(f)
                    if chain:
                        self.last_hash = chain[-1]['current_hash']
            except (json.JSONDecodeError, IndexError):
                pass

    def create_incident_id(self, label):
        """Generates a unique folder name for the incident."""
        safe_label = label.replace(" ", "_")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{timestamp}_{safe_label}"

    def secure_evidence(self, frame, detection_meta, incident_id=None, shot_index=0):
        """
        Saves frame and metadata with cryptographic chaining.
        If incident_id is provided, saves to a subfolder.
        Also saves zoomed crops of threats.
        """
        timestamp = datetime.now().isoformat()
        
        # Determine folder
        if incident_id:
            save_dir = os.path.join(self.evidence_dir, incident_id)
        else:
            # Fallback if no incident ID provided (single shot)
            save_dir = self.evidence_dir
            
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        # Filename logic
        base_name = f"evidence_{shot_index}"
        filename = f"{base_name}.jpg"
        filepath = os.path.join(save_dir, filename)
        
        # Save Full Frame
        cv2.imwrite(filepath, frame)
        
        # Save Zoomed Crops
        for i, det in enumerate(detection_meta):
            x1, y1, x2, y2 = det['box']
            h, w = frame.shape[:2]
            
            # Add padding (zoom context)
            pad_x = int((x2 - x1) * 0.5)
            pad_y = int((y2 - y1) * 0.5)
            
            crop_x1 = max(0, x1 - pad_x)
            crop_y1 = max(0, y1 - pad_y)
            crop_x2 = min(w, x2 + pad_x)
            crop_y2 = min(h, y2 + pad_y)
            
            crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]
            crop_filename = f"{base_name}_zoom_{i}_{det['label']}.jpg"
            cv2.imwrite(os.path.join(save_dir, crop_filename), crop)
        
        # Read back bytes for hashing (ensure identical bytes)
        with open(filepath, 'rb') as f:
            image_bytes = f.read()
            
        # Create Data Block
        data_block = {
            "timestamp": timestamp,
            "filename": os.path.join(os.path.basename(save_dir), filename) if incident_id else filename,
            "incident_id": incident_id,
            "meta": detection_meta,
            "previous_hash": self.last_hash
        }
        
        # Calculate Hash
        hasher = hashlib.sha256()
        hasher.update(image_bytes)
        hasher.update(json.dumps(data_block, sort_keys=True).encode('utf-8'))
        current_hash = hasher.hexdigest()
        
        # Update Chain
        entry = {
            "index": self._get_next_index(),
            "timestamp": timestamp,
            "data": data_block,
            "current_hash": current_hash
        }
        
        self._append_to_log(entry)
        self.last_hash = current_hash
        
        return entry

    def _get_next_index(self):
        if os.path.exists(self.chain_file):
            try:
                with open(self.chain_file, 'r') as f:
                    chain = json.load(f)
                    return len(chain)
            except:
                return 0
        return 0

    def _append_to_log(self, entry):
        chain = []
        if os.path.exists(self.chain_file):
            try:
                with open(self.chain_file, 'r') as f:
                    chain = json.load(f)
            except:
                pass
        
        chain.append(entry)
        
        with open(self.chain_file, 'w') as f:
            json.dump(chain, f, indent=4)
            
    def verify_integrity(self):
        """Re-calculates all hashes to verify chain integrity."""
        if not os.path.exists(self.chain_file):
            return True, "No chain file found."
            
        with open(self.chain_file, 'r') as f:
            chain = json.load(f)
            
        prev_hash = "0" * 64
        for i, entry in enumerate(chain):
            # Verify Linkage
            if entry['data']['previous_hash'] != prev_hash:
                return False, f"Broken chain at index {i}: Previous hash mismatch."
            
            # Verify Content
            filepath = os.path.join(self.evidence_dir, entry['data']['filename'])
            if not os.path.exists(filepath):
                return False, f"Missing evidence file at index {i}: {filepath}"
                
            with open(filepath, 'rb') as img_f:
                image_bytes = img_f.read()
                
            hasher = hashlib.sha256()
            hasher.update(image_bytes)
            hasher.update(json.dumps(entry['data'], sort_keys=True).encode('utf-8'))
            calculated_hash = hasher.hexdigest()
            
            if calculated_hash != entry['current_hash']:
                return False, f"Data corruption at index {i}: Hash mismatch."
                
            prev_hash = entry['current_hash']
            
        return True, "Chain integrity verified."
