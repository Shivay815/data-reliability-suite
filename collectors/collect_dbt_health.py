"""Parse dbt artifacts (run_results.json + sources.json) from Project A's
build and append per-run health rows to the reliability history.

Run AFTER `dbt build` and `dbt source freshness` in the platform repo.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = REPO_ROOT.parent / "ecom-analytics-platform" / "dbt" / "target"
HISTORY_DIR = REPO_ROOT / "history"


def append(path: Path, rows: list[dict]) -> None:
    HISTORY_DIR.mkdir(exist_ok=True)
    new = pd.DataFrame(rows)
    if path.exists():
        new = pd.concat([pd.read_parquet(path), new], ignore_index=True)
    new.to_parquet(path, index=False)


def collect_run_results(target: Path, run_at: str) -> dict:
    data = json.loads((target / "run_results.json").read_text())
    results = data["results"]
    by_type: dict[str, dict[str, int]] = {}
    for r in results:
        kind = "test" if r["unique_id"].startswith("test.") else "model"
        bucket = by_type.setdefault(kind, {"total": 0, "pass": 0, "fail": 0})
        bucket["total"] += 1
        if r["status"] in ("success", "pass"):
            bucket["pass"] += 1
        else:
            bucket["fail"] += 1
    tests = by_type.get("test", {"total": 0, "pass": 0, "fail": 0})
    models = by_type.get("model", {"total": 0, "pass": 0, "fail": 0})
    return {
        "run_at": run_at,
        "elapsed_seconds": round(data.get("elapsed_time", 0), 1),
        "models_total": models["total"],
        "models_failed": models["fail"],
        "tests_total": tests["total"],
        "tests_failed": tests["fail"],
        "pass_rate": round(100 * tests["pass"] / max(tests["total"], 1), 2),
    }


def collect_freshness(target: Path, run_at: str) -> list[dict]:
    path = target / "sources.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    rows = []
    for r in data.get("results", []):
        rows.append(
            {
                "run_at": run_at,
                "source_name": r["unique_id"].split(".")[-1],
                "status": r["status"],  # pass / warn / error
                "max_loaded_at": r.get("max_loaded_at"),
                "age_seconds": (r.get("max_loaded_at_time_ago_in_s") or 0),
            }
        )
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-dir", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args()
    run_at = datetime.now(timezone.utc).isoformat()

    run_row = collect_run_results(args.target_dir, run_at)
    append(HISTORY_DIR / "dbt_runs.parquet", [run_row])
    print(f"✓ dbt run: {run_row['tests_total']} tests, "
          f"{run_row['tests_failed']} failed, pass rate {run_row['pass_rate']}%")

    fresh = collect_freshness(args.target_dir, run_at)
    if fresh:
        append(HISTORY_DIR / "freshness.parquet", fresh)
        print(f"✓ freshness: {len(fresh)} sources, "
              f"statuses {[r['status'] for r in fresh]}")
