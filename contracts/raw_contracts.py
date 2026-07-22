"""Great Expectations ingestion contracts for the Olist raw layer.

These validate raw data BEFORE dbt transformation — a different layer than
Project A's dbt-expectations tests (which validate transformation logic).
Contracts at ingestion, logic tests at transformation.
"""

from __future__ import annotations

import itertools
import os

os.environ.setdefault("TQDM_DISABLE", "1")  # GX metric progress bars off in CI logs

import great_expectations as gx
from great_expectations.core import ExpectationSuite

E = gx.expectations

# GX 1.x requires an active data context before suites can be constructed.
_CONTEXT = gx.get_context(mode="ephemeral")
_SOURCE = _CONTEXT.data_sources.add_pandas("raw")
_ASSET_IDS = itertools.count()


def _suite(name: str, expectations: list) -> ExpectationSuite:
    suite = ExpectationSuite(name=name)
    for exp in expectations:
        suite.add_expectation(exp)
    return suite


SUITES: dict[str, ExpectationSuite] = {
    "orders": _suite(
        "orders",
        [
            E.ExpectTableRowCountToBeBetween(min_value=95_000, max_value=110_000),
            E.ExpectColumnValuesToNotBeNull(column="order_id"),
            E.ExpectColumnValuesToBeUnique(column="order_id"),
            E.ExpectColumnValuesToNotBeNull(column="customer_id"),
            E.ExpectColumnValuesToBeInSet(
                column="order_status",
                value_set=[
                    "created", "approved", "invoiced", "processing",
                    "shipped", "delivered", "canceled", "unavailable",
                ],
            ),
            E.ExpectColumnValuesToNotBeNull(column="order_purchase_timestamp"),
        ],
    ),
    "order_items": _suite(
        "order_items",
        [
            E.ExpectTableRowCountToBeBetween(min_value=110_000, max_value=125_000),
            E.ExpectColumnValuesToNotBeNull(column="order_id"),
            E.ExpectColumnValuesToNotBeNull(column="product_id"),
            E.ExpectColumnValuesToBeBetween(column="price", min_value=0, max_value=10_000),
            E.ExpectColumnValuesToBeBetween(
                column="freight_value", min_value=0, max_value=1_000
            ),
        ],
    ),
    "order_payments": _suite(
        "order_payments",
        [
            E.ExpectColumnValuesToNotBeNull(column="order_id"),
            E.ExpectColumnValuesToBeBetween(
                column="payment_value", min_value=0, max_value=20_000
            ),
            E.ExpectColumnValuesToBeInSet(
                column="payment_type",
                value_set=["credit_card", "boleto", "voucher", "debit_card", "not_defined"],
            ),
        ],
    ),
    "order_reviews": _suite(
        "order_reviews",
        [
            E.ExpectColumnValuesToNotBeNull(column="review_id"),
            E.ExpectColumnValuesToBeBetween(column="review_score", min_value=1, max_value=5),
        ],
    ),
    "customers": _suite(
        "customers",
        [
            E.ExpectColumnValuesToNotBeNull(column="customer_id"),
            E.ExpectColumnValuesToBeUnique(column="customer_id"),
            E.ExpectColumnValuesToNotBeNull(column="customer_unique_id"),
            E.ExpectColumnValueLengthsToEqual(column="customer_state", value=2),
        ],
    ),
    "products": _suite(
        "products",
        [
            E.ExpectColumnValuesToNotBeNull(column="product_id"),
            E.ExpectColumnValuesToBeUnique(column="product_id"),
        ],
    ),
    "sellers": _suite(
        "sellers",
        [
            E.ExpectColumnValuesToNotBeNull(column="seller_id"),
            E.ExpectColumnValuesToBeUnique(column="seller_id"),
        ],
    ),
}

# file name on disk -> suite key
FILES = {
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "olist_customers_dataset.csv": "customers",
    "olist_products_dataset.csv": "products",
    "olist_sellers_dataset.csv": "sellers",
}


def validate_dataframe(df, suite: ExpectationSuite):
    """Validate a pandas DataFrame against a suite; returns the GX result."""
    asset = _SOURCE.add_dataframe_asset(f"asset_{next(_ASSET_IDS)}")
    batch_def = asset.add_batch_definition_whole_dataframe("batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})
    return batch.validate(suite)
