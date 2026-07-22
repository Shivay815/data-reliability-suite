"""Append Project B's current model metrics to the reliability history —
over time this becomes the model-quality trend the dashboard plots."""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

METRICS_URL = (
    "https://raw.githubusercontent.com/Shivay815/churn-insights-app/main/"
    "artifacts/metrics.json"
)
HISTORY = Path(__file__).resolve().parents[1] / "history" / "model_runs.parquet"

if __name__ == "__main__":
    with urllib.request.urlopen(METRICS_URL, timeout=30) as resp:
        metrics = json.loads(resp.read())
    row = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "roc_auc": metrics["roc_auc"],
        "pr_auc": metrics["pr_auc"],
        "lift_at_top_decile": metrics["lift_at_top_decile"],
        "brier": metrics["brier"],
        "n_customers": metrics.get("n_customers"),
    }
    HISTORY.parent.mkdir(exist_ok=True)
    new = pd.DataFrame([row])
    if HISTORY.exists():
        new = pd.concat([pd.read_parquet(HISTORY), new], ignore_index=True)
    new.to_parquet(HISTORY, index=False)
    print(f"✓ model health appended: AUC {row['roc_auc']}, Brier {row['brier']}")
