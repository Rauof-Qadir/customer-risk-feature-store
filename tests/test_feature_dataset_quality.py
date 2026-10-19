
import duckdb
import pytest


def test_feature_quality_rules_detect_invalid_history():
    con = duckdb.connect(database=":memory:")

    try:
        con.execute("""
            CREATE TABLE features (
                customer_transaction_count BIGINT,
                customer_prior_active_steps BIGINT,
                has_customer_history INTEGER,
                customer_avg_amount DOUBLE,
                customer_avg_transactions_per_active_step DOUBLE,
                amount_vs_avg DOUBLE
            )
        """)

        # Valid first transaction: no historical information.
        con.execute("""
            INSERT INTO features VALUES
            (0, 0, 0, NULL, NULL, NULL)
        """)

        valid_result = con.execute("""
            SELECT COUNT(*)
            FROM features
            WHERE customer_transaction_count < 0
               OR customer_prior_active_steps < 0
               OR has_customer_history NOT IN (0, 1)
               OR (
                   customer_transaction_count = 0
                   AND customer_avg_amount IS NOT NULL
               )
               OR (
                   customer_prior_active_steps = 0
                   AND customer_avg_transactions_per_active_step
                       IS NOT NULL
               )
        """).fetchone()[0]

        assert valid_result == 0

        # Inject an invalid negative historical count.
        con.execute("""
            INSERT INTO features VALUES
            (-1, 0, 0, NULL, NULL, NULL)
        """)

        invalid_result = con.execute("""
            SELECT COUNT(*)
            FROM features
            WHERE customer_transaction_count < 0
               OR customer_prior_active_steps < 0
               OR has_customer_history NOT IN (0, 1)
               OR (
                   customer_transaction_count = 0
                   AND customer_avg_amount IS NOT NULL
               )
               OR (
                   customer_prior_active_steps = 0
                   AND customer_avg_transactions_per_active_step
                       IS NOT NULL
               )
        """).fetchone()[0]

        assert invalid_result == 1

    finally:
        con.close()


def test_history_flag_must_match_historical_count():
    con = duckdb.connect(database=":memory:")

    try:
        con.execute("""
            CREATE TABLE features (
                customer_transaction_count BIGINT,
                has_customer_history INTEGER
            )
        """)

        con.execute("""
            INSERT INTO features VALUES
            (0, 0),
            (3, 1),
            (3, 0)
        """)

        mismatches = con.execute("""
            SELECT COUNT(*)
            FROM features
            WHERE has_customer_history <>
                CASE
                    WHEN customer_transaction_count > 0 THEN 1
                    ELSE 0
                END
        """).fetchone()[0]

        assert mismatches == 1

    finally:
        con.close()
