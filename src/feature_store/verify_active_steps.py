
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
        features_path = (
            str(FEATURES_FILE).replace("\\", "/").replace("'", "''")
        )

        con.execute(f"""
            CREATE VIEW raw AS
            SELECT * FROM read_csv_auto('{raw_path}')
        """)

        con.execute(f"""
            CREATE VIEW features AS
            SELECT * FROM read_parquet('{features_path}')
        """)

        # Pick customers with at least three distinct observed steps.
        samples = con.execute("""
            WITH customer_steps AS (
                SELECT DISTINCT nameOrig, step
                FROM raw
            ),
            ranked AS (
                SELECT
                    nameOrig,
                    step,
                    ROW_NUMBER() OVER (
                        PARTITION BY nameOrig
                        ORDER BY step
                    ) AS step_rank
                FROM customer_steps
            )
            SELECT nameOrig, step
            FROM ranked
            WHERE step_rank >= 2
            LIMIT 20
        """).fetchall()

        if not samples:
            raise RuntimeError(
                "No customers with prior active steps found."
            )

        failures = 0
        print("=== ACTIVE-STEP VERIFICATION ===")

        for customer_id, current_step in samples:
            actual = con.execute("""
                SELECT COUNT(DISTINCT step)
                FROM raw
                WHERE nameOrig = ?
                  AND step < ?
            """, [customer_id, current_step]).fetchone()[0]

            stored = con.execute("""
                SELECT customer_prior_active_steps
                FROM features
                WHERE nameOrig = ?
                  AND step = ?
                LIMIT 1
            """, [customer_id, current_step]).fetchone()

            passed = stored is not None and stored[0] == actual

            print(
                f"{'PASS' if passed else 'FAIL'} | "
                f"{customer_id} | step={current_step} | "
                f"stored={stored[0] if stored else None} | "
                f"actual={actual}"
            )

            if not passed:
                failures += 1

        print(f"\nSamples checked: {len(samples)}")
        print(f"Failures: {failures}")

        if failures:
            raise AssertionError(
                "Active-step verification failed."
            )

        print("Independent verification: PASS")

    finally:
        con.close()


if __name__ == "__main__":
    main()
