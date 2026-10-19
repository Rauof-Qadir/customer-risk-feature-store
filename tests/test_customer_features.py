
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]

FEATURES_FILE = (
    ROOT / "data" / "features" / "customer_features.parquet"
)

EXPECTED_ROWS = 6_362_620


def load_features():
    """Load the generated feature dataset into DuckDB."""
    assert FEATURES_FILE.exists(), (
        f"Feature dataset not found: {FEATURES_FILE}"
    )

    con = duckdb.connect()

    # Safely quote the file path as a SQL string literal.
    file_path = FEATURES_FILE.resolve().as_posix()
    escaped_path = file_path.replace("'", "''")

    con.execute(
        f"CREATE VIEW features AS "
        f"SELECT * FROM read_parquet('{escaped_path}')"
    )

    return con


def test_feature_dataset_exists():
    """The feature pipeline must generate its output file."""
    assert FEATURES_FILE.exists()


def test_expected_row_count():
    """Feature generation must preserve all transaction rows."""
    con = load_features()

    try:
        rows = con.execute(
            "SELECT COUNT(*) FROM features"
        ).fetchone()[0]

        assert rows == EXPECTED_ROWS
    finally:
        con.close()


def test_required_features_exist():
    """All three customer behavior features must be present."""
    con = load_features()

    try:
        columns = {
            row[0]
            for row in con.execute(
                "DESCRIBE features"
            ).fetchall()
        }

        required = {
            "customer_transaction_count",
            "customer_avg_amount",
            "has_customer_history",
            "amount_vs_avg",
            "customer_prior_active_steps",
            "customer_avg_transactions_per_active_step",
        }

        assert required.issubset(columns)
    finally:
        con.close()


def test_transaction_counts_are_non_negative():
    """Historical transaction counts cannot be negative."""
    con = load_features()

    try:
        invalid_rows = con.execute("""
            SELECT COUNT(*)
            FROM features
            WHERE customer_transaction_count < 0
               OR customer_transaction_count IS NULL
        """).fetchone()[0]

        assert invalid_rows == 0
    finally:
        con.close()


def test_history_flag_matches_transaction_count():
    """History flag must agree with historical transaction count."""
    con = load_features()

    try:
        invalid_rows = con.execute("""
            SELECT COUNT(*)
            FROM features
            WHERE (
                customer_transaction_count = 0
                AND has_customer_history <> 0
            )
            OR (
                customer_transaction_count > 0
                AND has_customer_history <> 1
            )
            OR has_customer_history IS NULL
        """).fetchone()[0]

        assert invalid_rows == 0
    finally:
        con.close()


def test_average_and_ratio_are_consistent():
    """Ratio must equal amount divided by historical average."""
    con = load_features()

    try:
        invalid_rows = con.execute("""
            SELECT COUNT(*)
            FROM features
            WHERE (
                customer_avg_amount > 0
                AND (
                    amount_vs_avg IS NULL
                    OR ABS(
                        amount_vs_avg
                        - amount / customer_avg_amount
                    ) > 0.000001
                )
            )
            OR (
                (
                    customer_avg_amount IS NULL
                    OR customer_avg_amount <= 0
                )
                AND amount_vs_avg IS NOT NULL
            )
        """).fetchone()[0]

        assert invalid_rows == 0
    finally:
        con.close()


def test_history_features_exclude_current_transaction():
    """A transaction must not contribute to its own historical features."""
    con = load_features()

    try:
        invalid_rows = con.execute("""
            SELECT COUNT(*)
            FROM features
            WHERE customer_transaction_count = 0
              AND (
                  customer_avg_amount IS NOT NULL
                  OR has_customer_history <> 0
                  OR amount_vs_avg IS NOT NULL
              )
        """).fetchone()[0]

        assert invalid_rows == 0
    finally:
        con.close()


def test_prior_active_steps_are_non_negative():
    """Prior active steps must be present and non-negative."""
    con = load_features()

    try:
        invalid_rows = con.execute("""
            SELECT COUNT(*)
            FROM features
            WHERE customer_prior_active_steps IS NULL
               OR customer_prior_active_steps < 0
        """).fetchone()[0]

        assert invalid_rows == 0
    finally:
        con.close()


def test_prior_active_steps_match_history_count():
    """Distinct previous steps cannot exceed prior transactions."""
    con = load_features()

    try:
        invalid_rows = con.execute("""
            SELECT COUNT(*)
            FROM features
            WHERE customer_prior_active_steps
                  > customer_transaction_count
        """).fetchone()[0]

        assert invalid_rows == 0
    finally:
        con.close()



def test_avg_transactions_per_active_step_is_consistent():
    """Average transactions per prior active step must be correct."""
    con = load_features()

    try:
        invalid_rows = con.execute("""
            SELECT COUNT(*)
            FROM features
            WHERE (
                customer_prior_active_steps > 0
                AND (
                    customer_avg_transactions_per_active_step IS NULL
                    OR ABS(
                        customer_avg_transactions_per_active_step
                        - CAST(customer_transaction_count AS DOUBLE)
                          / customer_prior_active_steps
                    ) > 0.000001
                )
            )
            OR (
                customer_prior_active_steps = 0
                AND customer_avg_transactions_per_active_step IS NOT NULL
            )
            OR (
                customer_avg_transactions_per_active_step < 0
            )
        """).fetchone()[0]

        assert invalid_rows == 0
    finally:
        con.close()



