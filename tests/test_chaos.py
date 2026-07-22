"""Chaos drills: inject realistic data breaks and assert the contracts refuse
every one of them. This is the measured basis for the claim "catches N/N
injected break classes" — if a new break class slips through, this suite
fails and the claim is revoked automatically.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts.raw_contracts import SUITES, validate_dataframe


@pytest.fixture(scope="module")
def clean_orders() -> pd.DataFrame:
    n = 96_000
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "order_id": [f"o{i:07d}" for i in range(n)],
            "customer_id": [f"c{i:07d}" for i in range(n)],
            "order_status": rng.choice(["delivered", "shipped", "canceled"], n),
            "order_purchase_timestamp": "2018-01-01 10:00:00",
        }
    )


@pytest.fixture(scope="module")
def clean_items() -> pd.DataFrame:
    n = 115_000
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "order_id": [f"o{i:07d}" for i in range(n)],
            "product_id": [f"p{i:05d}" for i in range(n)],
            "price": rng.uniform(10, 500, n).round(2),
            "freight_value": rng.uniform(0, 60, n).round(2),
        }
    )


def test_clean_data_passes(clean_orders):
    assert validate_dataframe(clean_orders, SUITES["orders"]).success


# ── the drills ──────────────────────────────────────────────────────

def test_catches_null_primary_key(clean_orders):
    broken = clean_orders.copy()
    broken.loc[broken.index[:50], "order_id"] = None
    assert not validate_dataframe(broken, SUITES["orders"]).success


def test_catches_duplicate_primary_key(clean_orders):
    broken = pd.concat([clean_orders, clean_orders.head(100)], ignore_index=True)
    assert not validate_dataframe(broken, SUITES["orders"]).success


def test_catches_unknown_enum_value(clean_orders):
    broken = clean_orders.copy()
    broken.loc[broken.index[:10], "order_status"] = "teleported"
    assert not validate_dataframe(broken, SUITES["orders"]).success


def test_catches_row_count_collapse(clean_orders):
    # e.g. an upstream extract silently truncated
    assert not validate_dataframe(clean_orders.head(5_000), SUITES["orders"]).success


def test_catches_negative_prices(clean_items):
    broken = clean_items.copy()
    broken.loc[broken.index[:20], "price"] = -9.99
    assert not validate_dataframe(broken, SUITES["order_items"]).success


def test_catches_absurd_price_outliers(clean_items):
    broken = clean_items.copy()
    broken.loc[broken.index[:5], "price"] = 9_999_999.0  # currency-unit bug
    assert not validate_dataframe(broken, SUITES["order_items"]).success
