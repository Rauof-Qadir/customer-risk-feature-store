
from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FILE = PROJECT_ROOT / "data" / "raw" / "transactions.csv"
SQL_FILE = PROJECT_ROOT / "sql" / "customer_features.sql"
OUTPUT_FILE = (
    PROJECT_ROOT / "data" / "features"
    / "customer_features.parquet"
)


def build_features() -> None:
    if not RAW_FILE.exists():
        raise FileNotFoundError(f"Dataset not found: {RAW_FILE}")

    if not SQL_FILE.exists():
        raise FileNotFoundError(f"SQL file not found: {SQL_FILE}")

    # Read SQL BEFORE using the variable.
    sql = SQL_FILE.read_text(encoding="utf-8").strip().rstrip(";")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(database=":memory:")

    try:
        # Register the raw transaction CSV as a SQL view.
        
       
        raw_path = str(RAW_FILE).replace("\\", "/")
        escaped_raw_path = raw_path.replace("'", "''")

        con.execute(
            f"""
            CREATE VIEW transactions AS
            SELECT *
            FROM read_csv_auto('{escaped_raw_path}')
            """
        )


        # Escape the output path for SQL string syntax.
        output_path = str(OUTPUT_FILE).replace("\\", "/")
        escaped_path = output_path.replace("'", "''")

        # Execute feature SQL and write the result to Parquet.
        export_query = (
            f"COPY ({sql}) "
            f"TO '{escaped_path}' (FORMAT PARQUET)"
        )
        con.execute(export_query)

        print("Feature engineering completed!")
        print(f"Output: {OUTPUT_FILE}")

        # Validate the generated dataset.
        result = con.execute(
            """
            SELECT
                COUNT(*) AS total_rows,
                COUNT(DISTINCT nameOrig) AS unique_customers,
                MIN(customer_transaction_count) AS min_history,
                MAX(customer_transaction_count) AS max_history,
                COUNT(*) FILTER (
                    WHERE customer_transaction_count < 0
                ) AS negative_history_rows
            FROM read_parquet(?)
            """,
            [str(OUTPUT_FILE)],
        ).fetchone()

        print(f"Rows: {result[0]:,}")
        print(f"Unique customers: {result[1]:,}")
        print(f"Minimum historical count: {result[2]}")
        print(f"Maximum historical count: {result[3]}")
        print(f"Negative history rows: {result[4]}")

        assert result[0] == 6_362_620, "Output row count mismatch"
        assert result[2] == 0, "Unexpected minimum historical count"
        assert result[4] == 0, "Negative historical counts found"

        print("\nAll basic feature checks passed.")

    finally:
        con.close()


if __name__ == "__main__":
    build_features()
