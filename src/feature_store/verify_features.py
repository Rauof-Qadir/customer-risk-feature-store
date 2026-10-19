
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "transactions.csv"
FEATURES = ROOT / "data" / "features" / "customer_features.parquet"


def main():
    con = duckdb.connect()

    try:
        
        raw_path = str(RAW).replace("\\", "/").replace("'", "''")
        features_path = str(FEATURES).replace("\\", "/").replace("'", "''")

        con.execute(f"""
            CREATE VIEW raw_transactions AS
            SELECT * FROM read_csv_auto('{raw_path}')
        """)

        con.execute(f"""
            CREATE VIEW features AS
            SELECT * FROM read_parquet('{features_path}')
        """)


        # Check the output row count and feature distribution.
        print("=== FEATURE DISTRIBUTION ===")
        print(con.execute("""
            SELECT
                customer_transaction_count,
                COUNT(*) AS transaction_rows
            FROM features
            GROUP BY customer_transaction_count
            ORDER BY customer_transaction_count
        """).df().to_string(index=False))

        # Independently verify historical counts for selected rows.
        print("\n=== SAMPLE VERIFICATION ===")

        samples = con.execute("""
            SELECT nameOrig, step, customer_transaction_count
            FROM features
            WHERE customer_transaction_count > 0
            LIMIT 10
        """).fetchall()

        all_passed = True

        for customer_id, step, stored_count in samples:
            actual_count = con.execute("""
                SELECT COUNT(*)
                FROM raw_transactions
                WHERE nameOrig = ?
                  AND step < ?
            """, [customer_id, step]).fetchone()[0]

            passed = stored_count == actual_count
            all_passed = all_passed and passed

            print(
                f"Customer={customer_id}, step={step}, "
                f"stored={stored_count}, actual={actual_count}, "
                f"PASS={passed}"
            )

        if not samples:
            print("No rows with historical transactions found.")

        print("\nVerification:", "PASS" if all_passed and samples else "CHECK FAILED")

        assert all_passed and samples, (
            "Feature verification failed. Inspect the output above."
        )

    finally:
        con.close()


if __name__ == "__main__":
    main()
