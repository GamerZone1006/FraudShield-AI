"""Prepare a sampled PaySim CSV for model training."""
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
SOURCE_FILE = BASE_DIR / "PS_20174392719_1491204439457_log.csv"
OUTPUT_FILE = BASE_DIR / "transactions_sample.csv"

if not SOURCE_FILE.exists():
    raise FileNotFoundError(
        f"Missing {SOURCE_FILE.name}. Download the PaySim dataset and place it in {BASE_DIR}."
    )

chunks = []
print("Reading PaySim in chunks...")
for chunk_number, chunk in enumerate(pd.read_csv(SOURCE_FILE, chunksize=100_000)):
    fraud = chunk[chunk["isFraud"] == 1]
    legitimate = chunk[chunk["isFraud"] == 0]
    sample = legitimate.sample(frac=0.03, random_state=42 + chunk_number)
    chunks.append(pd.concat([fraud, sample], ignore_index=True))
    print(f"Processed chunk {chunk_number + 1}")

data = pd.concat(chunks, ignore_index=True)
data = data[["step", "type", "amount", "isFraud"]].dropna()
data.to_csv(OUTPUT_FILE, index=False)
print(f"Saved {len(data):,} rows to {OUTPUT_FILE}")
print(data["isFraud"].value_counts())
print(f"Fraud prevalence in sample: {data['isFraud'].mean() * 100:.2f}%")
