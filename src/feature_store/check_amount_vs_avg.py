
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "data" / "features" / "customer_features.parquet"


def main():
    con = duckdb.connect()

    try:
        parquet_path = FEATURES.as_posix().replace("'", "''")

        con.execute(
            f"CREATE VIEW features AS SELECT * FROM read_parquet('{parquet_path}')"
        )

        result = con.execute("""
            SELECT
                COUNT(*) AS total_rows,

                COUNT(amount_vs_avg) AS rows_with_ratio,

                COUNT(*) FILTER (
                    WHERE amount_vs_avg IS NULL
                ) AS rows_without_ratio,

                COUNT(*) FILTER (
                    WHERE amount_vs_avg < 0
                ) AS negative_ratios,

                COUNT(*) FILTER (
                    WHERE customer_avg_amount > 0
                      AND amount_vs_avg IS NULL
                ) AS missing_expected_ratios,

                COUNT(*) FILTER (
                    WHERE customer_avg_amount IS NULL
                      AND amount_vs_avg IS NOT NULL
                ) AS unexpected_ratios

            FROM features
        """).fetchone()

        labels = [
            "Total rows",
            "Rows with ratio",
            "Rows without ratio",
            "Negative ratios",
            "Missing expected ratios",
            "Unexpected ratios",
        ]

        print("=== AMOUNT VS AVERAGE VALIDATION ===")

        for label, value in zip(labels, result):
            print(f"{label:30} {value:,}")

        assert result[0] == 6_362_620
        assert result[3] == 0
        assert result[4] == 0
        assert result[5] == 0

        print("\nBasic validation: PASS")

        print("\n=== SAMPLE RESULTS ===")

        print(con.execute("""
            SELECT
                nameOrig,
                step,
                amount,
                customer_avg_amount,
                amount_vs_avg
            FROM features
            WHERE amount_vs_avg IS NOT NULL
            LIMIT 10
        """).df().to_string(index=False))

    finally:
        con.close()


if __name__ == "__main__":
    main()
