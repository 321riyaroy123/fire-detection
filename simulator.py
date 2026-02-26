"""
Sensor Data Simulator — mimics ESP32 posting to the Flask API.
Run:  python scripts/simulator.py

Options:
  --url     Server URL  (default: http://localhost:5000/api/sensor-data)
  --device  Device ID   (default: SIMULATOR_01)
  --mode    normal | escalating | random  (default: random)
  --interval Seconds between posts (default: 2)
"""
import argparse, time, random, math, requests, json
from datetime import datetime

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--url",      default="http://localhost:5000/api/sensor-data")
    p.add_argument("--device",   default="SIMULATOR_01")
    p.add_argument("--mode",     default="random", choices=["normal","escalating","random"])
    p.add_argument("--interval", type=float, default=2.0)
    return p.parse_args()

def normal_reading():
    return {
        "temperature": round(random.uniform(25, 42), 2),
        "smoke":       random.randint(50, 280),
        "gas":         random.randint(80, 380),
    }

def escalating_reading(step):
    """Simulate a fire developing over time."""
    t = 30 + step * 1.2 + random.uniform(-2, 2)
    s = 100 + step * 15  + random.uniform(-20, 20)
    g = 150 + step * 12  + random.uniform(-20, 20)
    return {
        "temperature": round(min(t, 130), 2),
        "smoke":       int(min(s, 1200)),
        "gas":         int(min(g, 1200)),
    }

def random_reading(step):
    if random.random() < 0.15:
        return escalating_reading(random.randint(10, 40))
    return normal_reading()

def post(url, device, payload):
    body = {"device_id": device, **payload}
    try:
        r = requests.post(url, json=body, timeout=5)
        resp = r.json()
        risk  = resp.get("risk_level", "?")
        proba = resp.get("probabilities", {})
        ts    = datetime.now().strftime("%H:%M:%S")
        color = {"LOW": "\033[92m", "MEDIUM": "\033[93m", "HIGH": "\033[91m"}.get(risk, "")
        reset = "\033[0m"
        prob_str = " | ".join(f"{k}:{v:.2f}" for k, v in proba.items()) if proba else ""
        print(f"[{ts}] T={payload['temperature']:6.1f}°C  "
              f"S={payload['smoke']:4d}ppm  G={payload['gas']:4d}ppm  "
              f"→ Risk: {color}{risk}{reset}  {prob_str}")
    except requests.exceptions.ConnectionError:
        print(f"[ERROR] Cannot connect to {url} — is the server running?")
    except Exception as e:
        print(f"[ERROR] {e}")

def main():
    args = parse_args()
    print(f"Simulator starting → {args.url}  mode={args.mode}  device={args.device}")
    print("Press Ctrl+C to stop.\n")

    step = 0
    try:
        while True:
            if args.mode == "normal":
                payload = normal_reading()
            elif args.mode == "escalating":
                payload = escalating_reading(step)
            else:
                payload = random_reading(step)

            post(args.url, args.device, payload)
            time.sleep(args.interval)
            step += 1
    except KeyboardInterrupt:
        print("\nSimulator stopped.")

if __name__ == "__main__":
    main()
