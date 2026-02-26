"""
Train and evaluate the fire risk prediction model.
Run:  python ml/train_model.py

Outputs:
  backend/models/fire_risk_model.pkl
  backend/models/scaler.pkl
  ml/evaluation_report.txt
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (classification_report, confusion_matrix,
                              accuracy_score, ConfusionMatrixDisplay)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── Paths ─────────────────────────────────────────
DATA_PATH   = os.path.join(os.path.dirname(__file__), "..", "data", "sensor_data.csv")
MODEL_DIR   = os.path.join(os.path.dirname(__file__), "..", "backend", "models")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "evaluation_report.txt")
os.makedirs(MODEL_DIR, exist_ok=True)

# ── Load Data ─────────────────────────────────────
print("Loading data...")
df = pd.read_csv(DATA_PATH)

FEATURES = ["temperature", "smoke", "gas"]
TARGET   = "risk_label"

X = df[FEATURES].values
y = df[TARGET].values

# ── Encode labels ─────────────────────────────────
le = LabelEncoder()
y_enc = le.fit_transform(y)
print("Classes:", le.classes_)

# ── Train/Test Split ──────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y_enc, test_size=0.2, random_state=42, stratify=y_enc
)

# ── Feature Scaling ───────────────────────────────
scaler = StandardScaler()
X_train_sc = scaler.fit_transform(X_train)
X_test_sc  = scaler.transform(X_test)

# ── Model Candidates ──────────────────────────────
candidates = {
    "RandomForest":        RandomForestClassifier(n_estimators=100, random_state=42),
    "GradientBoosting":    GradientBoostingClassifier(n_estimators=100, random_state=42),
    "LogisticRegression":  LogisticRegression(max_iter=500, random_state=42),
}

best_model, best_score, best_name = None, 0, ""
cv_results = {}

for name, clf in candidates.items():
    x_tr = X_train_sc if name == "LogisticRegression" else X_train
    cv = cross_val_score(clf, x_tr, y_train, cv=5, scoring="accuracy")
    cv_results[name] = cv
    print(f"{name}  CV Acc: {cv.mean():.4f} ± {cv.std():.4f}")
    if cv.mean() > best_score:
        best_score = cv.mean()
        best_model = clf
        best_name  = name

# ── Train Best Model ──────────────────────────────
print(f"\nBest model: {best_name}")
use_scaled = (best_name == "LogisticRegression")
best_model.fit(X_train_sc if use_scaled else X_train,  y_train)
y_pred = best_model.predict(X_test_sc if use_scaled else X_test)

acc = accuracy_score(y_test, y_pred)
print(f"Test Accuracy: {acc:.4f}")

# ── Save ──────────────────────────────────────────
joblib.dump(best_model, os.path.join(MODEL_DIR, "fire_risk_model.pkl"))
joblib.dump(scaler,     os.path.join(MODEL_DIR, "scaler.pkl"))
joblib.dump(le,         os.path.join(MODEL_DIR, "label_encoder.pkl"))
meta = {
    "model_name":   best_name,
    "features":     FEATURES,
    "classes":      le.classes_.tolist(),
    "test_accuracy": round(acc, 4),
    "use_scaled":   use_scaled,
}
with open(os.path.join(MODEL_DIR, "model_meta.json"), "w") as f:
    json.dump(meta, f, indent=2)
print("Models saved to backend/models/")

# ── Report ────────────────────────────────────────
report = classification_report(y_test, y_pred, target_names=le.classes_)
with open(REPORT_PATH, "w") as f:
    f.write(f"Best Model: {best_name}\n")
    f.write(f"Test Accuracy: {acc:.4f}\n\n")
    f.write(report)
    f.write("\nCV Results:\n")
    for n, cv in cv_results.items():
        f.write(f"  {n}: {cv.mean():.4f} ± {cv.std():.4f}\n")
print(f"Evaluation report → {REPORT_PATH}")
print(report)

# ── Confusion Matrix Plot ─────────────────────────
cm = confusion_matrix(y_test, y_pred)
disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=le.classes_)
fig, ax = plt.subplots(figsize=(6, 5))
disp.plot(ax=ax, colorbar=False)
plt.title(f"Confusion Matrix — {best_name}")
plt.tight_layout()
plt.savefig(os.path.join(os.path.dirname(__file__), "confusion_matrix.png"))
print("Confusion matrix plot saved.")

# ── Feature Importance (if RF/GB) ─────────────────
if hasattr(best_model, "feature_importances_"):
    fi = best_model.feature_importances_
    plt.figure(figsize=(5, 3))
    plt.bar(FEATURES, fi, color=["#e74c3c", "#f39c12", "#3498db"])
    plt.title("Feature Importance")
    plt.ylabel("Importance")
    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(__file__), "feature_importance.png"))
    print("Feature importance plot saved.")
