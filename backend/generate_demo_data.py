"""Generate a small synthetic dataset so the project can run without a download."""
from pathlib import Path
import numpy as np
import pandas as pd

OUTPUT = Path(__file__).resolve().parent / "transactions_sample.csv"
rng = np.random.default_rng(42)
n = 12000

steps = rng.integers(1, 744, size=n)
types = rng.choice(
    ["PAYMENT", "TRANSFER", "CASH_OUT", "DEBIT", "CASH_IN"],
    size=n,
    p=[0.40, 0.18, 0.17, 0.10, 0.15],
)
amounts = np.round(rng.lognormal(mean=7.2, sigma=1.25, size=n), 2)
amounts = np.clip(amounts, 1, 1_000_000_000)

# Synthetic labels are generated from simple rules plus noise.
risk = (
    (np.isin(types, ["TRANSFER", "CASH_OUT"]) * 1.1)
    + (amounts > 100_000) * 1.0
    + (amounts > 300_000) * 0.8
    + (steps < 10) * 0.2
    + rng.normal(0, 0.8, size=n)
)
threshold = np.quantile(risk, 0.91)
fraud = (risk > threshold).astype(int)

data = pd.DataFrame({
    "step": steps,
    "type": types,
    "amount": amounts,
    "isFraud": fraud,
})
data.to_csv(OUTPUT, index=False)
print(f"Generated {len(data):,} synthetic rows at {OUTPUT}")
print("Class distribution:")
print(data["isFraud"].value_counts())
print("NOTE: This data is synthetic and is for software demonstration only.")
