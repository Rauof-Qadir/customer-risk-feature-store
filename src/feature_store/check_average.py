
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "data" / "features" / "customer_features.parquet"


def main():
    con = duckdb.connect()

    try:
        
        feature_path = FEATURES.as_posix().replace("'", "''")

        con.execute(
            f"""
            CREATE VIEW features AS
            SELECT * FROM read_parquet('{feature_path}')
            """
        )


        print("=== AVERAGE FEATURE VALIDATION ===")

        result = con.execute("""
            SELECT
                COUNT(*) AS total_rows,
                COUNT(customer_avg_amount) AS rows_with_average,
                COUNT(*) FILTER (
                    WHERE customer_avg_amount IS NULL
                ) AS rows_without_average,
                COUNT(*) FILTER (
                    WHERE customer_avg_amount < 0
                ) AS negative_averages,
                COUNT(*) FILTER (
                    WHERE has_customer_history = 0
                      AND customer_avg_amount IS NOT NULL
                ) AS inconsistent_rows,
                MIN(customer_avg_amount) AS minimum_average,
                MAX(customer_avg_amount) AS maximum_average
            FROM features
        """).fetchone()

        labels = [
            "Total rows",
            "Rows with average",
            "Rows without average",
            "Negative averages",
            "Inconsistent history flags",
            "Minimum average",
            "Maximum average",
        ]

        for label, value in zip(labels, result):
            print(f"{label:30} {value}")

        assert result[0] == 6_362_620
        assert result[3] == 0
        assert result[4] == 0

        print("\nBasic validation: PASS")

        print("\n=== SAMPLE FEATURES ===")
        print(con.execute("""
            SELECT
                nameOrig,
                step,
                amount,
                customer_transaction_count,
                customer_avg_amount,
                has_customer_history
            FROM features
            WHERE has_customer_history = 1
            LIMIT 10
        """).df().to_string(index=False))

    finally:
        con.close()


if __name__ == "__main__":
    main()
