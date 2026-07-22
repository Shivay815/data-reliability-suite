"""Run all ingestion contracts against the raw Olist CSVs and append the
outcome to the reliability history.

Exit code is non-zero on any contract failure — CI turns that into an alert.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from contracts.raw_contracts import FILES, SUITES, validate_dataframe

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_RAW = REPO_ROOT.parent / "ecom-analytics-platform" / "data" / "raw"
HISTORY = REPO_ROOT / "history" / "contract_runs.parquet"


def append_history(rows: list[dict]) -> None:
    HISTORY.parent.mkdir(exist_ok=True)
    new = pd.DataFrame(rows)
    if HISTORY.exists():
        new = pd.concat([pd.read_parquet(HISTORY), new], ignore_index=True)
    new.to_parquet(HISTORY, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    args = parser.parse_args()
    if not args.raw_dir.exists():
        sys.exit(f"raw dir not found: {args.raw_dir} — run `make data` first")

    run_at = datetime.now(timezone.utc).isoformat()
    rows, failed = [], []
    for filename, key in FILES.items():
        df = pd.read_csv(args.raw_dir / filename)
        started = time.perf_counter()
        result = validate_dataframe(df, SUITES[key])
        n_pass = sum(1 for r in result.results if r.success)
        rows.append(
            {
                "run_at": run_at,
                "table_name": key,
                "expectations": len(result.results),
                "passed": n_pass,
                "failed": len(result.results) - n_pass,
                "success": bool(result.success),
                "rows_validated": len(df),
                "seconds": round(time.perf_counter() - started, 2),
            }
        )
        status = "✓" if result.success else "✗"
        print(f"{status} {key:<16} {n_pass}/{len(result.results)} expectations, {len(df):,} rows")
        if not result.success:
            failed.append(key)

    append_history(rows)
    print(f"✓ history appended → {HISTORY}")
    if failed:
        sys.exit(f"✗ CONTRACT VIOLATIONS in: {failed}")


if __name__ == "__main__":
    main()
