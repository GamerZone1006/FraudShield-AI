"""Train and evaluate the FraudShield AI Random Forest pipeline."""
from pathlib import Path
import json
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score,
    average_precision_score, accuracy_score, precision_score,
    recall_score, f1_score,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "transactions_sample.csv"
MODEL_PATH = BASE_DIR / "fraud_detector.joblib"

if not DATA_PATH.exists():
    raise FileNotFoundError("Dataset missing. Run python generate_demo_data.py first.")

data = pd.read_csv(DATA_PATH)
required = {"step", "type", "amount", "isFraud"}
missing = required - set(data.columns)
if missing:
    raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")

X = data[["step", "type", "amount"]]
y = data["isFraud"].astype(int)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42, stratify=y
)

preprocessor = ColumnTransformer(
    transformers=[
        ("transaction_type", OneHotEncoder(handle_unknown="ignore"), ["type"])
    ],
    remainder="passthrough",
)
model = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        ("classifier", RandomForestClassifier(
            n_estimators=100,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        )),
    ]
)

print("Training Random Forest pipeline...")
model.fit(X_train, y_train)
predictions = model.predict(X_test)
probabilities = model.predict_proba(X_test)[:, 1]

print("\nClassification report:")
print(classification_report(
    y_test, predictions, labels=[0, 1],
    target_names=["Legitimate", "Fraud"], zero_division=0
))
cm = confusion_matrix(y_test, predictions, labels=[0, 1])
print("Confusion matrix:\n", cm)
tn, fp, fn, tp = cm.ravel()

metrics = {
    "test_samples": int(len(y_test)),
    "accuracy": float(accuracy_score(y_test, predictions)),
    "precision": float(precision_score(y_test, predictions, zero_division=0)),
    "recall": float(recall_score(y_test, predictions, zero_division=0)),
    "f1_score": float(f1_score(y_test, predictions, zero_division=0)),
    "roc_auc": float(roc_auc_score(y_test, probabilities)),
    "average_precision": float(average_precision_score(y_test, probabilities)),
    "true_negatives": int(tn),
    "false_positives": int(fp),
    "false_negatives": int(fn),
    "true_positives": int(tp),
}
with (BASE_DIR / "evaluation_metrics.json").open("w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2)

preprocessor_fitted = model.named_steps["preprocessor"]
classifier = model.named_steps["classifier"]
feature_names = preprocessor_fitted.get_feature_names_out()
importance_data = pd.DataFrame({
    "feature": feature_names,
    "importance": classifier.feature_importances_,
}).sort_values("importance", ascending=False)
importance_data.to_csv(BASE_DIR / "feature_importance.csv", index=False)

joblib.dump(model, MODEL_PATH)
print(f"\nSaved model: {MODEL_PATH}")
print("Saved evaluation_metrics.json and feature_importance.csv")
