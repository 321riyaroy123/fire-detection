"""
Smart Fire Detection — Flask Backend API
Run: python backend/app.py

Dependencies: flask, scikit-learn, numpy, joblib (all stdlib sqlite3 — no SQLAlchemy needed)
"""
import os, json, logging, sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, render_template, g
import joblib
import numpy as np

# ── App Setup ─────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.join(BASE_DIR, "..")
MODEL_DIR  = os.path.join(BASE_DIR, "models")
STATIC_DIR = os.path.join(ROOT_DIR, "dashboard", "static")
TMPL_DIR   = os.path.join(ROOT_DIR, "dashboard", "templates")
DB_PATH    = os.path.join(BASE_DIR, "fire_detection.db")

app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TMPL_DIR)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("fire-detect")

# ── CORS helper ───────────────────────────────────
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

app.after_request(add_cors)

@app.route("/api/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    return jsonify({}), 200

# ── SQLite helpers ────────────────────────────────
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db: db.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id   TEXT    NOT NULL,
            timestamp   TEXT    NOT NULL,
            temperature REAL    NOT NULL,
            smoke       INTEGER NOT NULL,
            gas         INTEGER NOT NULL,
            risk_level  TEXT    NOT NULL,
            risk_code   INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    log.info(f"Database ready → {DB_PATH}")

def row_to_dict(row):
    return {
        "id":          row["id"],
        "device_id":   row["device_id"],
        "timestamp":   row["timestamp"],
        "temperature": row["temperature"],
        "smoke":       row["smoke"],
        "gas":         row["gas"],
        "risk_level":  row["risk_level"],
        "risk_code":   row["risk_code"],
    }

# ── ML Model ──────────────────────────────────────
predictor  = None
scaler     = None
label_enc  = None
model_meta = {}

def load_model():
    global predictor, scaler, label_enc, model_meta
    meta_path = os.path.join(MODEL_DIR, "model_meta.json")
    if not os.path.exists(meta_path):
        log.warning("ML model not found — using rule-based fallback. Run: python ml/train_model.py")
        return
    with open(meta_path) as f:
        model_meta = json.load(f)
    predictor = joblib.load(os.path.join(MODEL_DIR, "fire_risk_model.pkl"))
    scaler     = joblib.load(os.path.join(MODEL_DIR, "scaler.pkl"))
    label_enc  = joblib.load(os.path.join(MODEL_DIR, "label_encoder.pkl"))
    log.info(f"Model loaded: {model_meta['model_name']} (acc={model_meta['test_accuracy']})")

def rule_predict(temperature, smoke, gas):
    """Simple rule-based fallback."""
    score = 0
    if temperature >= 60:   score += 2
    elif temperature >= 45: score += 1
    if smoke >= 500:         score += 2
    elif smoke >= 300:       score += 1
    if gas >= 700:           score += 2
    elif gas >= 400:         score += 1
    if score <= 1:   return "LOW",    0, None
    if score <= 3:   return "MEDIUM", 1, None
    return "HIGH", 2, None

def ml_predict(temperature, smoke, gas):
    if predictor is None:
        return rule_predict(temperature, smoke, gas)
    feat = np.array([[temperature, smoke, gas]], dtype=float)
    feat_sc = scaler.transform(feat) if model_meta.get("use_scaled") else feat
    enc_code = int(predictor.predict(feat_sc)[0])
    proba    = predictor.predict_proba(feat_sc)[0].tolist()
    label    = label_enc.inverse_transform([enc_code])[0]
    RISK_CODES = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    code = RISK_CODES.get(label, 0)
    return label, code, proba

# ── Routes ────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/sensor-data", methods=["POST"])
def receive_sensor_data():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No JSON body"}), 400
    for field in ["device_id", "temperature", "smoke", "gas"]:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    temp  = float(data["temperature"])
    smoke = int(data["smoke"])
    gas   = int(data["gas"])

    label, code, proba = ml_predict(temp, smoke, gas)
    ts = datetime.utcnow().isoformat()

    db = get_db()
    db.execute(
        "INSERT INTO sensor_readings (device_id, timestamp, temperature, smoke, gas, risk_level, risk_code) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (data["device_id"], ts, temp, smoke, gas, label, code)
    )
    db.commit()

    if code >= 1:
        log.warning(f"⚠️  {label} RISK — device={data['device_id']} T={temp}°C S={smoke}ppm G={gas}ppm")

    resp = {"status": "ok", "risk_level": label, "risk_code": code}
    if proba and label_enc is not None:
        resp["probabilities"] = {lbl: round(p, 4) for lbl, p in zip(label_enc.classes_, proba)}
    return jsonify(resp), 200

@app.route("/api/latest", methods=["GET"])
def get_latest():
    device = request.args.get("device_id")
    limit  = int(request.args.get("limit", 50))
    db = get_db()
    if device:
        rows = db.execute(
            "SELECT * FROM sensor_readings WHERE device_id=? ORDER BY id DESC LIMIT ?",
            (device, limit)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM sensor_readings ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])

@app.route("/api/stats", methods=["GET"])
def get_stats():
    db    = get_db()
    total  = db.execute("SELECT COUNT(*) FROM sensor_readings").fetchone()[0]
    high   = db.execute("SELECT COUNT(*) FROM sensor_readings WHERE risk_level='HIGH'").fetchone()[0]
    medium = db.execute("SELECT COUNT(*) FROM sensor_readings WHERE risk_level='MEDIUM'").fetchone()[0]
    low    = db.execute("SELECT COUNT(*) FROM sensor_readings WHERE risk_level='LOW'").fetchone()[0]

    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    recent = db.execute(
        "SELECT temperature, smoke, gas FROM sensor_readings WHERE timestamp >= ?", (cutoff,)
    ).fetchall()

    if recent:
        avg_temp  = round(sum(r[0] for r in recent) / len(recent), 2)
        avg_smoke = round(sum(r[1] for r in recent) / len(recent), 2)
        avg_gas   = round(sum(r[2] for r in recent) / len(recent), 2)
        max_temp  = round(max(r[0] for r in recent), 2)
    else:
        avg_temp = avg_smoke = avg_gas = max_temp = 0

    return jsonify({
        "total_readings": total,
        "risk_distribution": {"LOW": low, "MEDIUM": medium, "HIGH": high},
        "last_24h": {
            "count":     len(recent),
            "avg_temp":  avg_temp,
            "avg_smoke": avg_smoke,
            "avg_gas":   avg_gas,
            "max_temp":  max_temp,
        },
        "model": model_meta or "rule-based",
    })

@app.route("/api/devices", methods=["GET"])
def get_devices():
    db   = get_db()
    rows = db.execute("SELECT DISTINCT device_id FROM sensor_readings").fetchall()
    return jsonify([r[0] for r in rows])

@app.route("/api/predict", methods=["POST"])
def manual_predict():
    data  = request.get_json(force=True)
    temp  = float(data.get("temperature", 30))
    smoke = int(data.get("smoke",         100))
    gas   = int(data.get("gas",           150))
    label, code, proba = ml_predict(temp, smoke, gas)
    resp = {"risk_level": label, "risk_code": code}
    if proba and label_enc is not None:
        resp["probabilities"] = {lbl: round(p, 4) for lbl, p in zip(label_enc.classes_, proba)}
    return jsonify(resp)

# ── Entry Point ───────────────────────────────────
if __name__ == "__main__":
    init_db()
    load_model()
    app.run(host="0.0.0.0", port=5000, debug=True)
