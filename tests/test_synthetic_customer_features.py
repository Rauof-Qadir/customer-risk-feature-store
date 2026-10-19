
import duckdb
import pytest


@pytest.mark.parametrize(
    "transactions_per_step, expected_average",
    [
        ([2, 1], 2.0),   # At step 2: 2 historical transactions / 1 step
        ([2, 1, 3], 1.5),  # At step 3: 3 historical transactions / 2 steps
        ([1, 1, 1], 1.0),
    ],
)
def test_average_transactions_per_active_step(
    transactions_per_step,
    expected_average,
):
    con = duckdb.connect()

    try:
        rows = []

        for step, count in enumerate(transactions_per_step, start=1):
            for _ in range(count):
                rows.append(("C001", step, 100.0))

        con.execute("""
            CREATE TABLE transactions (
                nameOrig VARCHAR,
                step INTEGER,
                amount DOUBLE
            )
        """)

        con.executemany(
            "INSERT INTO transactions VALUES (?, ?, ?)",
            rows,
        )

        result = con.execute("""
            WITH step_counts AS (
                SELECT
                    nameOrig AS customer_id,
                    step,
                    COUNT(*) AS transactions_in_step
                FROM transactions
                GROUP BY nameOrig, step
            ),
            history AS (
                SELECT
                    customer_id,
                    step,
                    COALESCE(
                        SUM(transactions_in_step) OVER (
                            PARTITION BY customer_id
                            ORDER BY step
                            ROWS BETWEEN UNBOUNDED PRECEDING
                                     AND 1 PRECEDING
                        ),
                        0
                    ) AS historical_count,
                    COUNT(*) OVER (
                        PARTITION BY customer_id
                        ORDER BY step
                        ROWS BETWEEN UNBOUNDED PRECEDING
                                 AND 1 PRECEDING
                    ) AS prior_active_steps
                FROM step_counts
            )
            SELECT
                CASE
                    WHEN prior_active_steps > 0
                    THEN CAST(historical_count AS DOUBLE)
                         / prior_active_steps
                    ELSE NULL
                END AS average_transactions
            FROM history
            WHERE step = ?
        """, [len(transactions_per_step)]).fetchone()

        assert result is not None
        assert result[0] == pytest.approx(expected_average)

    finally:
        con.close()
