# 🔥 Smart Fire Detection & Risk Prediction System

An end-to-end **IoT + Machine Learning** system for industrial fire hazard monitoring.  
Real-time sensor data from an ESP32 node is processed by a Flask API, predicted by a Random Forest classifier, and visualised on a live web dashboard.

---

## 📸 System Overview

```
[ESP32 + Sensors]  ──HTTP──▶  [Flask API + SQLite]  ──▶  [ML Risk Predictor]
      │                              │
   LCD + Buzzer               REST JSON API
                                     │
                          [Web Dashboard (Chart.js)]
```

---

## 🗂 Project Structure

```
smart-fire-detection/
├── firmware/
│   ├── esp32_main/
│   │   └── esp32_main.ino       # ESP32 firmware (Arduino IDE)
│   └── libraries.txt            # Required Arduino libraries
│
├── backend/
│   ├── app.py                   # Flask REST API + dashboard server
│   ├── requirements.txt         # Python dependencies
│   ├── models/                  # Trained ML model files (auto-generated)
│   └── fire_detection.db        # SQLite database (auto-generated)
│
├── dashboard/
│   ├── templates/index.html     # Real-time web dashboard
│   └── static/
│       ├── css/style.css
│       └── js/dashboard.js
│
├── data/
│   ├── generate_data.py         # Synthetic data generator
│   └── sensor_data.csv          # Training dataset (auto-generated)
│
├── ml/
│   ├── train_model.py           # Model training + evaluation
│   ├── evaluation_report.txt    # Metrics (auto-generated)
│   └── confusion_matrix.png     # Confusion matrix plot
│
├── scripts/
│   └── simulator.py             # Hardware-free sensor simulator
│
├── start.sh                     # One-command local launcher
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## ⚡ Quick Start (Local — No Hardware Required)

### Prerequisites
- Python 3.9+
- pip

### 1. Clone & setup

```bash
git clone https://github.com/YOUR_USERNAME/smart-fire-detection.git
cd smart-fire-detection
```

### 2. One-command startup

```bash
chmod +x start.sh
./start.sh
```

This will:
1. Create a Python virtual environment
2. Install all dependencies
3. Generate synthetic sensor training data
4. Train the Random Forest classifier
5. Start the Flask API server
6. Start the sensor simulator (sends live data to the API)

### 3. Open the dashboard

```
http://localhost:5000
```

---

## 🐳 Docker Quick Start

```bash
docker-compose up --build
```

Open `http://localhost:5000`

---

## 🔧 Manual Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Generate training data
python data/generate_data.py

# Train the ML model
python ml/train_model.py

# Start the server
python backend/app.py
```

In a separate terminal:

```bash
source .venv/bin/activate

# Run simulator (picks random/escalating scenarios)
python scripts/simulator.py --mode random --interval 2

# Simulate a developing fire
python scripts/simulator.py --mode escalating --interval 1

# Simulate normal conditions
python scripts/simulator.py --mode normal
```

---

## 🔌 Hardware Wiring (ESP32)

| Component       | ESP32 Pin | Notes                          |
|-----------------|-----------|--------------------------------|
| DHT11 (Temp)    | GPIO 34   | DATA pin; 10kΩ pull-up to 3.3V |
| MQ-2 (Smoke)    | GPIO 35   | AO (analog) output             |
| MQ-5 (Gas)      | GPIO 32   | AO (analog) output             |
| LCD SDA (I2C)   | GPIO 21   | 16×2 with I2C backpack (0x27)  |
| LCD SCL (I2C)   | GPIO 22   |                                |
| Buzzer          | GPIO 25   | Active buzzer                  |
| LED Red         | GPIO 26   | 220Ω series resistor           |
| LED Green       | GPIO 27   | 220Ω series resistor           |

### Flashing the firmware

1. Open `firmware/esp32_main/esp32_main.ino` in Arduino IDE
2. Edit the configuration block at the top:
   ```cpp
   const char* WIFI_SSID     = "YOUR_WIFI_SSID";
   const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
   const char* SERVER_URL    = "http://YOUR_SERVER_IP:5000/api/sensor-data";
   ```
3. Install libraries listed in `firmware/libraries.txt`
4. Select **Tools → Board → ESP32 Dev Module**
5. Upload

---

## 📡 REST API Reference

| Method | Endpoint               | Description                    |
|--------|------------------------|--------------------------------|
| POST   | `/api/sensor-data`     | Ingest sensor reading + predict|
| GET    | `/api/latest`          | Retrieve recent readings       |
| GET    | `/api/stats`           | Summary stats & risk breakdown |
| GET    | `/api/devices`         | List connected device IDs      |
| POST   | `/api/predict`         | Manual risk prediction         |

### POST `/api/sensor-data`

```json
{
  "device_id":   "SENSOR_NODE_01",
  "temperature": 58.4,
  "smoke":       420,
  "gas":         610
}
```

Response:

```json
{
  "status": "ok",
  "risk_level": "MEDIUM",
  "risk_code": 1,
  "probabilities": { "HIGH": 0.12, "LOW": 0.21, "MEDIUM": 0.67 }
}
```

---

## 🧠 Machine Learning Model

| Parameter      | Value                      |
|----------------|----------------------------|
| Algorithm      | Random Forest Classifier   |
| Features       | temperature, smoke, gas    |
| Classes        | LOW / MEDIUM / HIGH        |
| Typical Accuracy | ~97%+ on test set        |
| Fallback       | Rule-based scoring         |

### Risk Thresholds

| Parameter   | Safe       | Warning     | Risk        |
|-------------|------------|-------------|-------------|
| Temperature | < 45 °C    | 45–60 °C    | > 60 °C     |
| Smoke       | < 300 ppm  | 300–500 ppm | > 500 ppm   |
| Gas         | < 400 ppm  | 400–700 ppm | > 700 ppm   |

---

## 🚨 Multi-Level Alert Escalation

| Level | Condition     | Action                            |
|-------|---------------|-----------------------------------|
| 0     | LOW risk      | Green LED, no alarm               |
| 1     | MEDIUM risk   | Red LED, intermittent buzzer, dashboard warning |
| 2     | HIGH risk     | Red LED, continuous buzzer, dashboard alarm, log alert |

---

## 🔮 Future Enhancements

- [ ] Email / SMS alert integration (Twilio / SendGrid)
- [ ] MQTT broker (Mosquitto) for low-latency messaging
- [ ] AI deep learning model (LSTM for time-series prediction)
- [ ] Mobile app (React Native)
- [ ] CCTV + CV smoke/flame detection
- [ ] Automatic sprinkler relay control
- [ ] SCADA integration via Modbus

---

## 📄 License

MIT License — see [LICENSE](LICENSE)
