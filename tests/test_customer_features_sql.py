
from pathlib import Path

import duckdb
import pytest


ROOT = Path(__file__).resolve().parents[1]
SQL_FILE = ROOT / "sql" / "customer_features.sql"


def test_production_sql_calculates_nontrivial_average():
    """Production SQL should calculate 1.5 for controlled history."""
    assert SQL_FILE.exists(), f"SQL file not found: {SQL_FILE}"

    sql = SQL_FILE.read_text(encoding="utf-8").strip().rstrip(";")
    con = duckdb.connect(database=":memory:")

    try:
        con.execute("""
            CREATE TABLE transactions (
                step INTEGER,
                type VARCHAR,
                amount DOUBLE,
                nameOrig VARCHAR,
                oldbalanceOrg DOUBLE,
                newbalanceOrig DOUBLE,
                nameDest VARCHAR,
                oldbalanceDest DOUBLE,
                newbalanceDest DOUBLE,
                isFraud INTEGER,
                isFlaggedFraud INTEGER
            )
        """)

        # Customer C001:
        # Step 1: two transactions
        # Step 2: one transaction
        # Step 3: three transactions
        rows = [
            (1, "TRANSFER", 10.0, "C001", 100.0, 90.0, "D1", 0.0, 10.0, 0, 0),
            (1, "PAYMENT", 20.0, "C001", 90.0, 70.0, "D2", 0.0, 20.0, 0, 0),
            (2, "TRANSFER", 30.0, "C001", 70.0, 40.0, "D3", 0.0, 30.0, 0, 0),
            (3, "CASH_OUT", 40.0, "C001", 40.0, 0.0, "D4", 0.0, 40.0, 0, 0),
            (3, "PAYMENT", 50.0, "C001", 0.0, 0.0, "D5", 0.0, 50.0, 0, 0),
            (3, "TRANSFER", 60.0, "C001", 0.0, 0.0, "D6", 0.0, 60.0, 0, 0),
        ]

        con.executemany(
            """
            INSERT INTO transactions VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            rows,
        )

        # Execute the exact SQL file used by the production pipeline.
        con.execute(f"CREATE VIEW generated_features AS {sql}")

        results = con.execute("""
            SELECT DISTINCT
                step,
                customer_transaction_count,
                customer_prior_active_steps,
                customer_avg_transactions_per_active_step
            FROM generated_features
            WHERE nameOrig = 'C001'
              AND step = 3
        """).fetchall()

        assert len(results) == 1

        (
            step,
            historical_count,
            prior_active_steps,
            average,
        ) = results[0]

        assert step == 3
        assert historical_count == 3
        assert prior_active_steps == 2
        assert average == pytest.approx(1.5)

    finally:
        con.close()


def test_first_transaction_has_no_history():
    sql = SQL_FILE.read_text(encoding="utf-8").strip().rstrip(";")
    con = duckdb.connect(database=":memory:")

    try:
        con.execute("""
            CREATE TABLE transactions (
                step INTEGER,
                type VARCHAR,
                amount DOUBLE,
                nameOrig VARCHAR,
                oldbalanceOrg DOUBLE,
                newbalanceOrig DOUBLE,
                nameDest VARCHAR,
                oldbalanceDest DOUBLE,
                newbalanceDest DOUBLE,
                isFraud INTEGER,
                isFlaggedFraud INTEGER
            )
        """)

        con.execute("""
            INSERT INTO transactions VALUES
            (1, 'PAYMENT', 100, 'C001', 100, 0, 'D1', 0, 100, 0, 0)
        """)

        con.execute(f"CREATE VIEW generated_features AS {sql}")

        result = con.execute("""
            SELECT
                customer_transaction_count,
                customer_prior_active_steps,
                customer_avg_transactions_per_active_step,
                customer_avg_amount,
                has_customer_history,
                amount_vs_avg
            FROM generated_features
            WHERE nameOrig = 'C001'
        """).fetchone()

        assert result[0] == 0
        assert result[1] == 0
        assert result[2] is None
        assert result[3] is None
        assert result[4] == 0
        assert result[5] is None

    finally:
        con.close()


def test_same_step_transactions_do_not_leak_into_history():
    sql = SQL_FILE.read_text(encoding="utf-8").strip().rstrip(";")
    con = duckdb.connect(database=":memory:")

    try:
        con.execute("""
            CREATE TABLE transactions (
                step INTEGER,
                type VARCHAR,
                amount DOUBLE,
                nameOrig VARCHAR,
                oldbalanceOrg DOUBLE,
                newbalanceOrig DOUBLE,
                nameDest VARCHAR,
                oldbalanceDest DOUBLE,
                newbalanceDest DOUBLE,
                isFraud INTEGER,
                isFlaggedFraud INTEGER
            )
        """)

        con.execute("""
            INSERT INTO transactions VALUES
            (1, 'PAYMENT', 100, 'C001', 200, 100, 'D1', 0, 100, 0, 0),
            (1, 'TRANSFER', 200, 'C001', 100, 0, 'D2', 0, 200, 0, 0),
            (2, 'PAYMENT', 50, 'C001', 0, 0, 'D3', 0, 50, 0, 0)
        """)

        con.execute(f"CREATE VIEW generated_features AS {sql}")

        results = con.execute("""
            SELECT DISTINCT
                step,
                customer_transaction_count,
                customer_prior_active_steps,
                customer_avg_transactions_per_active_step
            FROM generated_features
            WHERE nameOrig = 'C001'
            ORDER BY step
        """).fetchall()

        assert len(results) == 2

        # Both step-1 transactions have zero prior history.
        assert results[0] == (1, 0, 0, None)

        # Step 2 sees both step-1 transactions and one prior active step.
        assert results[1] == (2, 2, 1, 2.0)

    finally:
        con.close()




def test_current_step_amounts_do_not_leak_into_historical_average():
    sql = SQL_FILE.read_text(encoding="utf-8").strip().rstrip(";")
    con = duckdb.connect(database=":memory:")

    try:
        con.execute("""
            CREATE TABLE transactions (
                step INTEGER,
                type VARCHAR,
                amount DOUBLE,
                nameOrig VARCHAR,
                oldbalanceOrg DOUBLE,
                newbalanceOrig DOUBLE,
                nameDest VARCHAR,
                oldbalanceDest DOUBLE,
                newbalanceDest DOUBLE,
                isFraud INTEGER,
                isFlaggedFraud INTEGER
            )
        """)

        con.execute("""
            INSERT INTO transactions VALUES
            (1, 'PAYMENT', 10, 'C001', 100, 90, 'D1', 0, 10, 0, 0),
            (1, 'PAYMENT', 20, 'C001', 90, 70, 'D2', 0, 20, 0, 0),
            (2, 'TRANSFER', 30, 'C001', 70, 40, 'D3', 0, 30, 0, 0),
            (2, 'CASH_OUT', 1000, 'C001', 40, 0, 'D4', 0, 1000, 0, 0)
        """)

        con.execute(
            f"CREATE VIEW generated_features AS {sql}"
        )

        results = con.execute("""
            SELECT
                amount,
                customer_transaction_count,
                customer_avg_amount,
                amount_vs_avg
            FROM generated_features
            WHERE nameOrig = 'C001'
              AND step = 2
            ORDER BY amount
        """).fetchall()

        assert len(results) == 2

        for amount, count, avg_amount, ratio in results:
            assert count == 2
            assert avg_amount == pytest.approx(15.0)
            assert ratio == pytest.approx(amount / 15.0)

    finally:
        con.close()





def test_feature_generation_preserves_transaction_row_count():
    sql = SQL_FILE.read_text(encoding="utf-8").strip().rstrip(";")
    con = duckdb.connect(database=":memory:")

    try:
        con.execute("""
            CREATE TABLE transactions (
                step INTEGER,
                type VARCHAR,
                amount DOUBLE,
                nameOrig VARCHAR,
                oldbalanceOrg DOUBLE,
                newbalanceOrig DOUBLE,
                nameDest VARCHAR,
                oldbalanceDest DOUBLE,
                newbalanceDest DOUBLE,
                isFraud INTEGER,
                isFlaggedFraud INTEGER
            )
        """)

        con.execute("""
            INSERT INTO transactions VALUES
            (1, 'PAYMENT', 10, 'C001', 100, 90, 'D1', 0, 10, 0, 0),
            (1, 'TRANSFER', 20, 'C001', 90, 70, 'D2', 0, 20, 0, 0),
            (2, 'PAYMENT', 30, 'C001', 70, 40, 'D3', 0, 30, 0, 0),
            (2, 'CASH_OUT', 40, 'C001', 40, 0, 'D4', 0, 40, 0, 0)
        """)

        con.execute(
            f"CREATE VIEW generated_features AS {sql}"
        )

        raw_count = con.execute("""
            SELECT COUNT(*) FROM transactions
        """).fetchone()[0]

        feature_count = con.execute("""
            SELECT COUNT(*) FROM generated_features
        """).fetchone()[0]

        assert raw_count == 4
        assert feature_count == raw_count

    finally:
        con.close()


