
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]
RAW_FILE = ROOT / "data" / "raw" / "transactions.csv"
FEATURES_FILE = (
    ROOT / "data" / "features" / "customer_features.parquet"
)


def main():
    con = duckdb.connect()

    try:
        
        raw_path = str(RAW_FILE).replace("\\", "/").replace("'", "''")
        features_path = str(FEATURES_FILE).replace("\\", "/").replace("'", "''")

        con.execute(f"""
            CREATE VIEW raw AS
            SELECT * FROM read_csv_auto('{raw_path}')
        """)

        con.execute(f"""
            CREATE VIEW features AS
            SELECT * FROM read_parquet('{features_path}')
        """)


        # Select customers who have transactions at multiple steps.
        samples = con.execute("""
            SELECT
                nameOrig,
                step
            FROM raw
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY nameOrig
                ORDER BY step
            ) = 2
            LIMIT 20
        """).fetchall()

        if not samples:
            raise RuntimeError("No suitable customer samples found.")

        print("=== INDEPENDENT HISTORY VERIFICATION ===")

        failures = 0

        for customer_id, current_step in samples:
            actual = con.execute("""
                SELECT
                    COUNT(*) AS historical_count,
                    AVG(amount) AS historical_average
                FROM raw
                WHERE nameOrig = ?
                  AND step < ?
            """, [customer_id, current_step]).fetchone()

            stored = con.execute("""
                SELECT
                    customer_transaction_count,
                    customer_avg_amount
                FROM features
                WHERE nameOrig = ?
                  AND step = ?
                LIMIT 1
            """, [customer_id, current_step]).fetchone()

            if stored is None:
                print(
                    f"FAIL | {customer_id} | "
                    f"step={current_step} | feature row missing"
                )
                failures += 1
                continue

            actual_count, actual_average = actual
            stored_count, stored_average = stored

            count_ok = stored_count == actual_count

            if actual_average is None:
                average_ok = stored_average is None
            else:
                average_ok = (
                    stored_average is not None
                    and abs(stored_average - actual_average) < 0.01
                )

            passed = count_ok and average_ok

            print(
                f"{'PASS' if passed else 'FAIL'} | "
                f"{customer_id} | step={current_step} | "
                f"count={stored_count}/{actual_count} | "
                f"average={stored_average}/{actual_average}"
            )

            if not passed:
                failures += 1

        print(f"\nSamples checked: {len(samples)}")
        print(f"Failures: {failures}")

        if failures:
            raise AssertionError(
                "Independent historical verification failed."
            )

        print("Independent verification: PASS")

    finally:
        con.close()


if __name__ == "__main__":
    main()
