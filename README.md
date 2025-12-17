# 🚨 Behavior Monitoring System (BMS)

A real-time **Computer Vision–based security system** that detects **restricted area entry** and **loitering behavior** using deep learning and sends **instant alerts via SMS or Email**.

---

## 📌 Project Overview

The Behavior Monitoring System (BMS) is designed to automate surveillance by analyzing live camera feeds.  
Instead of relying on manual CCTV monitoring, this system intelligently detects people, tracks their movement, identifies suspicious behavior, and alerts authorities in real time.

---

## 🎯 Objectives

- Detect people in live video streams  
- Monitor restricted zones automatically  
- Identify loitering behavior using time thresholds  
- Capture evidence screenshots  
- Send instant Email/SMS alerts  
- Store incidents securely for review  

---

## 🔄 Working Process

- Camera captures live video  
- Person is detected using a deep learning model (YOLO / MobileNet-SSD)  
- Each person is tracked with a unique ID  
- System continuously checks:
  - Restricted area entry  
  - Loitering duration  
- On violation:
  - Screenshot is captured  
  - Email or SMS alert is sent  
  - Incident is stored for review  

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

----

## ✨ Key Features

- Real-time monitoring  
- Accurate person detection  
- Loitering detection using time threshold  
- Restricted area monitoring  
- Password-protected screenshot gallery  
- Smart storage (avoids duplicate screenshots)  
- Instant Email & SMS alert system  
- Low latency and efficient processing  

---

## 🛠️ Technologies Used

- **Python 3.x**
- **OpenCV** – Video processing & DNN
- **YOLO / MobileNet-SSD** – Person detection
- **NumPy** – Numerical operations
- **Flask** – Web interface
- **Twilio API** – SMS alerts
- **SMTP (Gmail)** – Email alerts

---

## 🖥️ System Requirements

### Hardware
- Webcam or CCTV camera  
- Minimum 8GB RAM  
- Dual-core or higher CPU  

### Software
- Python 3.8+
- OpenCV
- Flask
- NumPy
- Twilio library

---

## 🚀 How to Run the Project

1. Clone the repository  
   ```bash
   git clone https://github.com/iamvishwa-codes/Behavior-Monitoring-System.git
