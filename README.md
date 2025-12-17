# 🛡️ Behavior Monitoring System (BMS)

Behavior Monitoring System (BMS) is a real-time computer vision–based security application developed using Python.  
It detects people through a live camera feed and monitors their behavior to identify **restricted area entry** and **loitering**.  
When a violation occurs, the system captures screenshots and sends instant alerts via Email and SMS.

---

## 🎯 Project Objective

- Automatically monitor people using a camera
- Detect unauthorized entry into restricted areas
- Detect loitering based on time spent
- Send real-time alerts
- Store evidence screenshots securely

---

## 🧠 Technologies Used

- Python 3
- OpenCV
- YOLO / MobileNet-SSD
- Flask
- HTML & CSS
- SMTP (Email)
- Twilio API (SMS)

---

## 📁 Project Structure

Behavior-Monitoring-System/
├── app.py  
├── README.md  
├── requirements.txt  
├── templates/  
│   ├── index.html  
│   ├── screenshots_login.html  
│   └── gallery.html  
├── static/  
│   └── screenshots/  
│       ├── restricted/  
│       └── loitering/  

---

## ⚙️ How to Run the Project

### Step 1: Clone Repository
```bash
git clone https://github.com/iamvishwa-codes/Behavior-Monitoring-System.git
cd Behavior-Monitoring-System

## 🔄 Working Process

- Camera captures live video  
- Person is detected using a deep learning model  
- Each person is tracked with a unique ID  
- System continuously checks:
  - Restricted area entry  
  - Loitering duration  
- On violation:
  - Screenshot is captured  
  - Email or SMS alert is sent  
  - Incident is stored for review  

---

## ✨ Key Features

- Real-time monitoring  
- Accurate person detection  
- Loitering detection using time threshold  
- Password-protected evidence gallery  
- Smart storage (avoids duplicate screenshots)  
- Instant alert system  

---

## 👤 Author

**Vishwa K**  
GitHub: https://github.com/iamvishwa-codes


