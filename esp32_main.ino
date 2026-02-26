/*
 * Smart Fire Detection and Risk Prediction System
 * ESP32 Firmware - Main Controller
 *
 * Hardware:
 *   - ESP32 Dev Module
 *   - LM35 / DHT11 Temperature Sensor  (GPIO34)
 *   - MQ-2  Smoke Sensor                (GPIO35)
 *   - MQ-5  Gas Sensor                  (GPIO32)
 *   - LCD 16x2 via I2C                  (SDA=GPIO21, SCL=GPIO22)
 *   - Buzzer                            (GPIO25)
 *   - LED Red                           (GPIO26)
 *   - LED Green                         (GPIO27)
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>
#include <ArduinoJson.h>

// ──────────────────────────────────────────────────
// CONFIGURATION — Edit before flashing
// ──────────────────────────────────────────────────
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* SERVER_URL    = "http://YOUR_SERVER_IP:5000/api/sensor-data";
const char* DEVICE_ID     = "SENSOR_NODE_01";

// ──────────────────────────────────────────────────
// PIN DEFINITIONS
// ──────────────────────────────────────────────────
#define DHT_PIN       34
#define DHT_TYPE      DHT11
#define SMOKE_PIN     35
#define GAS_PIN       32
#define BUZZER_PIN    25
#define LED_RED_PIN   26
#define LED_GREEN_PIN 27

// ──────────────────────────────────────────────────
// THRESHOLD VALUES
// ──────────────────────────────────────────────────
#define TEMP_WARN     45.0f   // °C
#define TEMP_RISK     60.0f   // °C
#define SMOKE_WARN    300     // ppm
#define SMOKE_RISK    500     // ppm
#define GAS_WARN      400     // ppm
#define GAS_RISK      700     // ppm

// ──────────────────────────────────────────────────
// INTERVALS
// ──────────────────────────────────────────────────
#define READ_INTERVAL   2000   // ms between sensor reads
#define UPLOAD_INTERVAL 10000  // ms between cloud uploads

// ──────────────────────────────────────────────────
// GLOBALS
// ──────────────────────────────────────────────────
LiquidCrystal_I2C lcd(0x27, 16, 2);
DHT dht(DHT_PIN, DHT_TYPE);

float temperature  = 0.0;
int   smokeLevel   = 0;
int   gasLevel     = 0;
int   riskLevel    = 0;   // 0=LOW 1=MEDIUM 2=HIGH
String riskLabel   = "LOW";

unsigned long lastRead   = 0;
unsigned long lastUpload = 0;

// ──────────────────────────────────────────────────
// SETUP
// ──────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);

  pinMode(BUZZER_PIN,    OUTPUT);
  pinMode(LED_RED_PIN,   OUTPUT);
  pinMode(LED_GREEN_PIN, OUTPUT);

  digitalWrite(LED_GREEN_PIN, HIGH);

  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0); lcd.print("Smart Fire");
  lcd.setCursor(0, 1); lcd.print("Detect System");
  delay(2000);
  lcd.clear();

  dht.begin();

  connectWiFi();

  lcd.setCursor(0, 0); lcd.print("System Ready");
  delay(1000);
  lcd.clear();
}

// ──────────────────────────────────────────────────
// MAIN LOOP
// ──────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  if (now - lastRead >= READ_INTERVAL) {
    lastRead = now;
    readSensors();
    evaluateRisk();
    updateLCD();
    triggerAlarms();
    printSerial();
  }

  if (now - lastUpload >= UPLOAD_INTERVAL) {
    lastUpload = now;
    uploadData();
  }

  // Reconnect Wi-Fi if dropped
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }
}

// ──────────────────────────────────────────────────
// SENSOR READING
// ──────────────────────────────────────────────────
void readSensors() {
  float t = dht.readTemperature();
  if (!isnan(t)) temperature = t;

  // Map ADC 0-4095 to ppm range (calibration values)
  smokeLevel = map(analogRead(SMOKE_PIN), 0, 4095, 0, 1000);
  gasLevel   = map(analogRead(GAS_PIN),   0, 4095, 0, 1000);
}

// ──────────────────────────────────────────────────
// RISK EVALUATION
// ──────────────────────────────────────────────────
void evaluateRisk() {
  int score = 0;

  if (temperature >= TEMP_RISK)    score += 2;
  else if (temperature >= TEMP_WARN) score += 1;

  if (smokeLevel >= SMOKE_RISK)    score += 2;
  else if (smokeLevel >= SMOKE_WARN) score += 1;

  if (gasLevel >= GAS_RISK)        score += 2;
  else if (gasLevel >= GAS_WARN)   score += 1;

  if (score <= 1)      { riskLevel = 0; riskLabel = "LOW"; }
  else if (score <= 3) { riskLevel = 1; riskLabel = "MEDIUM"; }
  else                 { riskLevel = 2; riskLabel = "HIGH"; }
}

// ──────────────────────────────────────────────────
// LCD DISPLAY
// ──────────────────────────────────────────────────
void updateLCD() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("T:"); lcd.print(temperature, 1); lcd.print("C ");
  lcd.print("S:"); lcd.print(smokeLevel);

  lcd.setCursor(0, 1);
  lcd.print("G:"); lcd.print(gasLevel); lcd.print("  ");
  lcd.print("R:"); lcd.print(riskLabel);
}

// ──────────────────────────────────────────────────
// ALARMS
// ──────────────────────────────────────────────────
void triggerAlarms() {
  if (riskLevel == 2) {
    // HIGH — continuous buzzer + red LED
    digitalWrite(LED_RED_PIN,   HIGH);
    digitalWrite(LED_GREEN_PIN, LOW);
    tone(BUZZER_PIN, 1000);
  } else if (riskLevel == 1) {
    // MEDIUM — intermittent beep
    digitalWrite(LED_RED_PIN,   HIGH);
    digitalWrite(LED_GREEN_PIN, LOW);
    tone(BUZZER_PIN, 500); delay(200); noTone(BUZZER_PIN);
  } else {
    // LOW — all clear
    noTone(BUZZER_PIN);
    digitalWrite(LED_RED_PIN,   LOW);
    digitalWrite(LED_GREEN_PIN, HIGH);
  }
}

// ──────────────────────────────────────────────────
// CLOUD UPLOAD
// ──────────────────────────────────────────────────
void uploadData() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<256> doc;
  doc["device_id"]   = DEVICE_ID;
  doc["temperature"] = temperature;
  doc["smoke"]       = smokeLevel;
  doc["gas"]         = gasLevel;
  doc["risk_level"]  = riskLabel;

  String payload;
  serializeJson(doc, payload);

  int httpCode = http.POST(payload);
  if (httpCode == 200) {
    Serial.println("[UPLOAD] OK");
  } else {
    Serial.printf("[UPLOAD] Failed: %d\n", httpCode);
  }
  http.end();
}

// ──────────────────────────────────────────────────
// WIFI CONNECTION
// ──────────────────────────────────────────────────
void connectWiFi() {
  lcd.clear();
  lcd.print("Connecting WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500); Serial.print("."); attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected: " + WiFi.localIP().toString());
    lcd.clear(); lcd.print("WiFi Connected");
  } else {
    Serial.println("\n[WiFi] Failed — running offline");
    lcd.clear(); lcd.print("WiFi Failed");
    lcd.setCursor(0,1); lcd.print("Offline Mode");
  }
  delay(1000);
}

// ──────────────────────────────────────────────────
// SERIAL DEBUG
// ──────────────────────────────────────────────────
void printSerial() {
  Serial.printf("Temp: %.1f°C | Smoke: %d ppm | Gas: %d ppm | Risk: %s\n",
                temperature, smokeLevel, gasLevel, riskLabel.c_str());
}
