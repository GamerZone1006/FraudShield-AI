"""FastAPI application for FraudShield AI."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "fraud_detector.joblib"
DATABASE_PATH = BASE_DIR / "transactions.db"

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        "Trained model not found. From backend, run: python generate_demo_data.py && python train_model.py"
    )
model = joblib.load(MODEL_PATH)

app = FastAPI(
    title="FraudShield AI",
    description="ML-powered transaction fraud screening prototype",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TransactionType = Literal["PAYMENT", "TRANSFER", "CASH_OUT", "DEBIT", "CASH_IN"]


class TransactionRequest(BaseModel):
    step: int = Field(ge=1)
    type: TransactionType
    amount: float = Field(gt=0, le=1_000_000_000)


@contextmanager
def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                step INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                amount REAL NOT NULL,
                fraud_probability REAL NOT NULL,
                risk_level TEXT NOT NULL,
                decision TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


initialize_database()


@app.get("/")
def home():
    return {
        "message": "Welcome to FraudShield AI",
        "status": "running",
        "model_loaded": True,
        "database": "SQLite",
    }


@app.post("/api/predict")
def predict_fraud(transaction: TransactionRequest):
    input_data = pd.DataFrame([{
        "step": transaction.step,
        "type": transaction.type,
        "amount": transaction.amount,
    }])

    try:
        fraud_probability = float(model.predict_proba(input_data)[0][1])
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="The model could not process this transaction.",
        )

    if fraud_probability >= 0.50:
        risk_level, decision = "HIGH", "REVIEW"
    elif fraud_probability >= 0.20:
        risk_level, decision = "MEDIUM", "REVIEW"
    else:
        risk_level, decision = "LOW", "APPROVE"

    created_at = datetime.now(timezone.utc).isoformat()
    try:
        with get_connection() as connection:
            cursor = connection.execute("""
                INSERT INTO transactions (
                    step, transaction_type, amount, fraud_probability,
                    risk_level, decision, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                transaction.step, transaction.type, transaction.amount,
                fraud_probability, risk_level, decision, created_at,
            ))
            transaction_id = cursor.lastrowid
    except sqlite3.Error:
        raise HTTPException(status_code=500, detail="Could not save the transaction.")

    return {
        "id": transaction_id,
        "step": transaction.step,
        "transaction_type": transaction.type,
        "amount": transaction.amount,
        "fraud_probability": round(fraud_probability, 4),
        "fraud_probability_percent": round(fraud_probability * 100, 2),
        "risk_level": risk_level,
        "decision": decision,
        "created_at": created_at,
        "model": "Random Forest",
    }


@app.get("/api/transactions")
def get_transactions(limit: int = Query(default=100, ge=1, le=500)):
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM transactions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/stats")
def get_stats():
    with get_connection() as connection:
        row = connection.execute("""
            SELECT
                COUNT(*) AS total_transactions,
                SUM(CASE WHEN decision = 'REVIEW' THEN 1 ELSE 0 END) AS flagged_transactions,
                SUM(CASE WHEN decision = 'APPROVE' THEN 1 ELSE 0 END) AS approved_transactions,
                SUM(CASE WHEN decision = 'REVIEW' THEN amount ELSE 0 END) AS flagged_amount,
                AVG(fraud_probability) AS average_risk
            FROM transactions
        """).fetchone()

    return {
        "total_transactions": row["total_transactions"] or 0,
        "flagged_transactions": row["flagged_transactions"] or 0,
        "approved_transactions": row["approved_transactions"] or 0,
        "flagged_amount": round(row["flagged_amount"] or 0, 2),
        "average_risk": round(row["average_risk"] or 0, 4),
    }


@app.get("/api/model-metrics")
def get_model_metrics():
    path = BASE_DIR / "evaluation_metrics.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evaluation metrics not found. Train the model first.")
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=500, detail="Could not read evaluation metrics.")


@app.get("/api/feature-importance")
def get_feature_importance():
    path = BASE_DIR / "feature_importance.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Feature importance not found. Train the model first.")
    try:
        data = pd.read_csv(path)
        return [
            {"feature": str(row["feature"]), "importance": round(float(row["importance"]), 6)}
            for _, row in data.iterrows()
        ]
    except (OSError, ValueError, KeyError):
        raise HTTPException(status_code=500, detail="Could not read feature importance.")
