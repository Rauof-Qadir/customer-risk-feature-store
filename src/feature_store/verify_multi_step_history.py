
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]

RAW_FILE = ROOT / "data" / "raw" / "transactions.csv"
FEATURE_FILE = ROOT / "data" / "features" / "customer_features.parquet"

TOLERANCE = 0.000001


def main():
    con = duckdb.connect()

    try:
        raw_path = RAW_FILE.resolve().as_posix().replace("'", "''")
        feature_path = (
            FEATURE_FILE.resolve().as_posix().replace("'", "''")
        )

        con.execute(f"""
            CREATE VIEW raw_transactions AS
            SELECT *
            FROM read_csv_auto('{raw_path}')
        """)

        con.execute(f"""
            CREATE VIEW features AS
            SELECT *
            FROM read_parquet('{feature_path}')
        """)

        results = con.execute("""
            WITH raw_step_counts AS (
                SELECT
                    nameOrig AS customer_id,
                    step,
                    COUNT(*) AS transactions_in_step
                FROM raw_transactions
                GROUP BY nameOrig, step
            ),
            expected AS (
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
                    ) AS expected_count,

                    COUNT(*) OVER (
                        PARTITION BY customer_id
                        ORDER BY step
                        ROWS BETWEEN UNBOUNDED PRECEDING
                                 AND 1 PRECEDING
                    ) AS expected_active_steps

                FROM raw_step_counts
            ),
            stored AS (
                SELECT DISTINCT
                    nameOrig AS customer_id,
                    step,
                    customer_transaction_count,
                    customer_prior_active_steps,
                    customer_avg_transactions_per_active_step
                FROM features
            )
            SELECT
                e.customer_id,
                e.step,
                e.expected_count,
                s.customer_transaction_count,
                e.expected_active_steps,
                s.customer_prior_active_steps,
                CAST(e.expected_count AS DOUBLE)
                    / e.expected_active_steps AS expected_average,
                s.customer_avg_transactions_per_active_step
                    AS stored_average
            FROM expected e
            JOIN stored s
              ON s.customer_id = e.customer_id
             AND s.step = e.step
            WHERE e.expected_active_steps > 0
                AND e.expected_count > e.expected_active_steps
            ORDER BY e.customer_id, e.step
            LIMIT 100
        """).fetchall()

        if not results:
            print("No eligible historical cases found.")
            return

        failures = []

        print("=== FEATURE #5 INDEPENDENT VERIFICATION ===")

        for row in results:
            (
                customer_id,
                step,
                expected_count,
                stored_count,
                expected_steps,
                stored_steps,
                expected_average,
                stored_average,
            ) = row

            count_ok = abs(
                float(expected_count) - float(stored_count)
            ) <= TOLERANCE

            steps_ok = expected_steps == stored_steps

            average_ok = (
                stored_average is not None
                and abs(
                    float(expected_average) - float(stored_average)
                ) <= TOLERANCE
            )

            if not (count_ok and steps_ok and average_ok):
                failures.append(row)

        for row in results[:10]:
            print(
                f"Customer={row[0]}, step={row[1]}, "
                f"expected_count={row[2]}, stored_count={row[3]}, "
                f"expected_steps={row[4]}, stored_steps={row[5]}, "
                f"expected_average={row[6]}, stored_average={row[7]}"
            )

        print(f"\nCases checked: {len(results)}")
        print(f"Cases with mismatches: {len(failures)}")

        if failures:
            raise AssertionError(
                "Independent feature verification failed."
            )

        print("Independent verification: PASS")

    finally:
        con.close()


if __name__ == "__main__":
    main()
