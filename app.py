# app.py
from flask import Flask, Response, render_template, request
import cv2
import numpy as np
import time
import threading
import os
import webbrowser
import smtplib
from email.mime.text import MIMEText
from twilio.rest import Client
import shutil

# ---------------- CONFIG ----------------
# Twilio (SMS) - set your real credentials
TWILIO_SID =  ""
TWILIO_AUTH = ""
TWILIO_PHONE = "+"
ADMIN_PHONE = ""

# Email (Gmail) - fallback (use App Password)
EMAIL_SENDER = ""
EMAIL_PASS = ""
EMAIL_RECEIVER = ""


# Screenshots password
SCREENSHOT_PASSWORD = "bms 123"

# Behavior settings
RESTRICT_TOP_LEFT = (0, 0)
RESTRICT_BOTTOM_RIGHT = (250,480)
LOITER_THRESHOLD = 30        # seconds before first loiter alert
RE_ALERT_INTERVAL = 15       # seconds between repeated alerts for same person/event
MIN_CONFIDENCE = 0.5

# Storage limits
KEEP_LAST_N = 50  # keep last N images per folder

# YOLO config files
YOLO_CFG = "yolov3.cfg"
YOLO_WEIGHTS = "yolov3.weights"
COCO_NAMES = "coco.names"

# Paths
SCREENSHOT_DIR = os.path.join("static", "screenshots")
RESTRICT_DIR = os.path.join(SCREENSHOT_DIR, "restricted")
LOITER_DIR = os.path.join(SCREENSHOT_DIR, "loitering")

# Flask
app = Flask(__name__)
app.secret_key = "bms_session_secret_key_v2"

# ---------------- PREPARE FOLDERS (safe) ----------------
def ensure_dir(path):
    if os.path.exists(path) and not os.path.isdir(path):
        # if a file with same name exists, remove it
        try:
            os.remove(path)
        except Exception:
            pass
    os.makedirs(path, exist_ok=True)

ensure_dir(SCREENSHOT_DIR)
ensure_dir(RESTRICT_DIR)
ensure_dir(LOITER_DIR)

# ---------------- TWILIO & EMAIL HELPERS ----------------
twilio_client = None
def send_sms(message):
    global twilio_client
    try:
        if twilio_client is None:
            twilio_client = Client(TWILIO_SID, TWILIO_AUTH)
        twilio_client.messages.create(body=message, from_=TWILIO_PHONE, to=ADMIN_PHONE)
        print("SMS SENT:", message)
        return True
    except Exception as e:
        print("SMS FAILED:", e)
        return False

def send_email(message):
    try:
        msg = MIMEText(message)
        msg["Subject"] = "BMS Alert"
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print("EMAIL SENT:", message)
        return True
    except Exception as e:
        print("EMAIL FAILED:", e)
        return False

def send_alert_with_fallback(message):
    sms_ok = send_sms(message)
    if not sms_ok:
        send_email(message)

# ---------------- LOAD YOLO ----------------
net = cv2.dnn.readNet(YOLO_WEIGHTS, YOLO_CFG)
with open(COCO_NAMES, "r") as f:
    CLASS_NAMES = [c.strip() for c in f.readlines()]
layer_names = net.getLayerNames()
output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]

# ---------------- CAMERA ----------------
cap = cv2.VideoCapture(0)
time.sleep(1.0)
camera_fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
if camera_fps == 0:
    camera_fps = 20.0

# ---------------- TRACKING / TIMERS ----------------
next_person_id = 0
tracked_centroids = {}         # person_id -> (cx, cy)
tracked_first_seen = {}        # person_id -> timestamp (for loiter)
tracked_last_seen = {}         # person_id -> timestamp (last seen frame time)
last_alert_time = {}           # (person_id, event) -> timestamp (cooldown)
alerted_restricted = set()     # person_ids that already had restricted screenshot recently
alerted_loiter = set()         # person_ids that already had loiter screenshot recently

last_frame_time = time.time()
camera_offline_alert_sent = False

# cleanup timeout: if person not seen for this long, remove from alerted sets so they can be alerted again later
SEEN_RESET_TIMEOUT = 120  # seconds

# ---------------- UTILITIES ----------------
def save_screenshots_to_folder(frame, bbox, event, person_id, folder):
    """
    Save full-frame screenshot and cropped-person image into 'folder'.
    Also prune old files keeping only last KEEP_LAST_N
    Returns tuple (full_path, crop_path)
    """
    ts = time.strftime("%Y%m%d_%H%M%S")
    full_name = f"{event}_id{person_id}_{ts}.jpg"
    crop_name = f"{event}_id{person_id}_{ts}_crop.jpg"
    full_path = os.path.join(folder, full_name)
    crop_path = os.path.join(folder, crop_name)
    try:
        cv2.imwrite(full_path, frame)
        x, y, w, h = bbox
        h_frame, w_frame = frame.shape[:2]
        x1 = max(0, x); y1 = max(0, y)
        x2 = min(w_frame, x + w); y2 = min(h_frame, y + h)
        crop = frame[y1:y2, x1:x2]
        if crop.size != 0:
            cv2.imwrite(crop_path, crop)
        else:
            cv2.imwrite(crop_path, frame)
        print("Saved screenshots:", full_path, crop_path)
    except Exception as e:
        print("Failed to save screenshots:", e)
    # maintain folder size
    maintain_limit(folder, KEEP_LAST_N)
    return full_path, crop_path

def maintain_limit(folder, keep_last):
    try:
        files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(('.jpg','.png','.jpeg'))]
        if len(files) <= keep_last:
            return
        files_sorted = sorted(files, key=os.path.getmtime)  # oldest first
        remove_count = len(files_sorted) - keep_last
        for i in range(remove_count):
            try:
                os.remove(files_sorted[i])
            except Exception as e:
                print("Failed to remove old file:", files_sorted[i], e)
    except Exception as e:
        print("maintain_limit error:", e)

def can_send_event(person_id, event):
    key = (person_id, event)
    now = time.time()
    last = last_alert_time.get(key, 0)
    if now - last >= RE_ALERT_INTERVAL:
        last_alert_time[key] = now
        return True
    return False

# ---------------- BACKGROUND TASKS ----------------
def camera_health_monitor():
    global camera_offline_alert_sent
    while True:
        if time.time() - last_frame_time > 10 and not camera_offline_alert_sent:
            threading.Thread(target=send_alert_with_fallback, args=("⚠ ALERT: Camera Offline! No video feed detected.",), daemon=True).start()
            camera_offline_alert_sent = True
        time.sleep(5)

def cleanup_unseen_ids():
    """
    Periodically remove person IDs from alerted sets if they haven't been seen for SEEN_RESET_TIMEOUT.
    This allows re-alerting if same person returns after a while.
    """
    while True:
        now = time.time()
        remove = []
        for pid, last_seen in list(tracked_last_seen.items()):
            if now - last_seen > SEEN_RESET_TIMEOUT:
                # evict from tracked structures and alerted sets
                alerted_restricted.discard(pid)
                alerted_loiter.discard(pid)
                tracked_centroids.pop(pid, None)
                tracked_first_seen.pop(pid, None)
                tracked_last_seen.pop(pid, None)
        time.sleep(10)

threading.Thread(target=camera_health_monitor, daemon=True).start()
threading.Thread(target=cleanup_unseen_ids, daemon=True).start()

# ---------------- PROCESS FRAME ----------------
def process_frame_actions(frame):
    """
    Detect persons, check restricted zone & loitering,
    save screenshots and send alerts when needed.
    Return annotated frame.
    """
    global next_person_id

    h, w = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(frame, 1/255.0, (416,416), swapRB=True, crop=False)
    net.setInput(blob)
    outs = net.forward(output_layers)

    boxes = []
    confidences = []
    centers = []

    for out in outs:
        for det in out:
            scores = det[5:]
            if len(scores) == 0:
                continue
            class_id = int(np.argmax(scores))
            conf = float(scores[class_id])
            if class_id == 0 and conf >= MIN_CONFIDENCE:  # person class
                cx = int(det[0] * w)
                cy = int(det[1] * h)
                bw = int(det[2] * w)
                bh = int(det[3] * h)
                x = int(cx - bw/2)
                y = int(cy - bh/2)
                boxes.append([x, y, bw, bh])
                confidences.append(conf)
                centers.append((cx, cy))

    # NMS safe handling
    idxs = cv2.dnn.NMSBoxes(boxes, confidences, MIN_CONFIDENCE, 0.4)
    if len(idxs) > 0:
        try:
            idxs = idxs.flatten()
        except:
            idxs = [i[0] for i in idxs]
    else:
        idxs = []

    # Assign IDs (simple centroid-based matching)
    assigned = {}  # detection index -> person_id
    for i, (x,y,bw,bh) in enumerate(boxes):
        if i not in idxs:
            continue
        cx, cy = centers[i]
        matched = None
        min_dist = 1e9
        for pid, (tx,ty) in tracked_centroids.items():
            d = np.hypot(tx - cx, ty - cy)
            if d < min_dist and d < 80:
                min_dist = d
                matched = pid
        if matched is None:
            matched = next_person_id
            next_person_id += 1
        assigned[i] = matched
        tracked_centroids[matched] = (cx, cy)
        tracked_last_seen[matched] = time.time()
        if matched not in tracked_first_seen:
            tracked_first_seen[matched] = time.time()

    # Process assigned detections
    for i, (x,y,bw,bh) in enumerate(boxes):
        if i not in assigned:
            continue
        pid = assigned[i]
        cx, cy = centers[i]

        # draw bbox & id
        cv2.rectangle(frame, (x, y), (x+bw, y+bh), (0,255,0), 2)
        cv2.putText(frame, f"ID:{pid}", (x, y-8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

        # Restricted zone check
        rx1, ry1 = RESTRICT_TOP_LEFT
        rx2, ry2 = RESTRICT_BOTTOM_RIGHT
        in_zone = (rx1 < cx < rx2 and ry1 < cy < ry2)
        if in_zone:
            # if not already alerted for this person recently OR cooldown allows
            if pid not in alerted_restricted:
                if can_send_event(pid, "restricted"):
                    # save screenshot into restricted folder
                    save_screenshots_to_folder(frame, (x,y,bw,bh), "restricted", pid, RESTRICT_DIR)
                    threading.Thread(target=send_alert_with_fallback,
                                     args=(f"⚠ RESTRICTED ZONE ENTRY: Person ID {pid} at {time.strftime('%Y-%m-%d %H:%M:%S')}",),
                                     daemon=True).start()
                    alerted_restricted.add(pid)
            else:
                # Already alerted for this person; but still allow re-alerts after cooldown
                if can_send_event(pid, "restricted"):
                    # send alert only (no screenshot to avoid duplicate storage)
                    threading.Thread(target=send_alert_with_fallback,
                                     args=(f"⚠ RESTRICTED ZONE (repeat): Person ID {pid} at {time.strftime('%Y-%m-%d %H:%M:%S')}",),
                                     daemon=True).start()

        # Loitering detection: if person hardly moves from their centroid and time>LOITER_THRESHOLD
        prev = tracked_centroids.get(pid, (cx, cy))
        moved = np.hypot(prev[0] - cx, prev[1] - cy)
        if moved < 30:
            elapsed = time.time() - tracked_first_seen.get(pid, time.time())
            if elapsed >= LOITER_THRESHOLD:
                if pid not in alerted_loiter:
                    if can_send_event(pid, "loiter"):
                        save_screenshots_to_folder(frame, (x,y,bw,bh), "loitering", pid, LOITER_DIR)
                        threading.Thread(target=send_alert_with_fallback,
                                         args=(f"⚠ LOITERING: Person ID {pid} dwell {int(elapsed)}s at {time.strftime('%Y-%m-%d %H:%M:%S')}",),
                                         daemon=True).start()
                        alerted_loiter.add(pid)
                else:
                    if can_send_event(pid, "loiter"):
                        threading.Thread(target=send_alert_with_fallback,
                                         args=(f"⚠ LOITERING (repeat): Person ID {pid} at {time.strftime('%Y-%m-%d %H:%M:%S')}",),
                                         daemon=True).start()
        else:
            # person moved, reset timer
            tracked_first_seen[pid] = time.time()

    # draw restricted zone for UI
    cv2.rectangle(frame, RESTRICT_TOP_LEFT, RESTRICT_BOTTOM_RIGHT, (0,0,255), 2)
    return frame

# ---------------- MJPEG STREAM GENERATOR ----------------
def generate_frames():
    global last_frame_time
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue
        last_frame_time = time.time()
        annotated = process_frame_actions(frame.copy())
        ret2, buf = cv2.imencode(".jpg", annotated)
        if not ret2:
            continue
        frame_bytes = buf.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(max(0, 1.0/camera_fps))

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/video_feed")
def video_feed():
    return Response(generate_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/screenshots", methods=["GET", "POST"])
def screenshots_login():
    if request.method == "POST":
        pwd = request.form.get("password", "")
        if pwd == SCREENSHOT_PASSWORD:
            # gather images from both folders
            imgs = []
            for folder in (RESTRICT_DIR, LOITER_DIR):
                try:
                    files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg','.png','.jpeg'))]
                    for f in files:
                        # prefix with subfolder name so gallery can show src path correctly
                        imgs.append((os.path.basename(folder), f))
                except Exception:
                    pass
            # sort by filename descending (timestamp in name) or by mtime
            imgs_sorted = sorted(imgs, key=lambda x: os.path.getmtime(os.path.join(SCREENSHOT_DIR, x[0], x[1])), reverse=True)
            # prepare list of url paths like 'screenshots/restricted/xxx.jpg' (relative to /static)
            images = [f"screenshots/{sub}/{fname}" for sub, fname in imgs_sorted]
            return render_template("gallery.html", images=images)
        else:
            return render_template("screenshots_login.html", error="Wrong password")
    return render_template("screenshots_login.html", error=None)

# ---------------- OPEN BROWSER ----------------
def open_browser():
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:5000")

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
