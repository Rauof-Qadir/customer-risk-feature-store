
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]
RAW_FILE = ROOT / "data" / "raw" / "transactions.csv"


def main():
    con = duckdb.connect()

    try:
        raw_path = RAW_FILE.resolve().as_posix().replace("'", "''")

        con.execute(f"""
            CREATE VIEW transactions AS
            SELECT nameOrig, step
            FROM read_csv_auto('{raw_path}')
        """)

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
                    ) AS historical_transactions,

                    COUNT(*) OVER (
                        PARTITION BY customer_id
                        ORDER BY step
                        ROWS BETWEEN UNBOUNDED PRECEDING
                                 AND 1 PRECEDING
                    ) AS prior_active_steps

                FROM step_counts
            )
            SELECT
                COUNT(*) FILTER (
                    WHERE prior_active_steps > 0
                ) AS records_with_history,

                COUNT(*) FILTER (
                    WHERE historical_transactions > prior_active_steps
                ) AS nontrivial_average_cases,

                MAX(historical_transactions) AS max_historical_transactions,

                MAX(prior_active_steps) AS max_prior_active_steps

            FROM history
        """).fetchone()

        print("=== CUSTOMER HISTORY PATTERN ANALYSIS ===")
        print(f"Records with history: {result[0]:,}")
        print(f"Non-trivial average cases: {result[1]:,}")
        print(f"Maximum historical transactions: {result[2]}")
        print(f"Maximum prior active steps: {result[3]}")

    finally:
        con.close()


if __name__ == "__main__":
    main()
