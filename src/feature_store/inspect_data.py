
import sys
from pathlib import Path

import duckdb


def inspect_dataset(csv_path: str) -> None:
    path = Path(csv_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    con = duckdb.connect(database=":memory:")

    try:
        # Read the CSV without loading the entire dataset into pandas.
        relation = con.read_csv(str(path), auto_detect=True)

        print("\n=== DATASET INSPECTION ===")
        print(f"File: {path}")
        print(f"Rows: {relation.count('*').fetchone()[0]:,}")
        print(f"Columns: {len(relation.columns)}")

        print("\n=== COLUMN NAMES AND DATA TYPES ===")
        schema = con.execute(
            "DESCRIBE SELECT * FROM read_csv_auto(?)",
            [str(path)],
        ).fetchall()

        for column in schema:
            print(f"{column[0]:25} {column[1]}")

        print("\n=== FIRST 5 ROWS ===")
        print(relation.limit(5).df().to_string(index=False))

        print("\n=== NULL COUNTS ===")
        null_query = ", ".join(
            f'COUNT(*) FILTER (WHERE "{col}" IS NULL) AS "{col}"'
            for col in relation.columns
        )

        null_counts = con.execute(
            f"SELECT {null_query} FROM read_csv_auto(?)",
            [str(path)],
        ).fetchone()

        for column, count in zip(relation.columns, null_counts):
            print(f"{column:25} {count:,}")

    finally:
        con.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            'Usage: python src/feature_store/inspect_data.py '
            '"path/to/transactions.csv"'
        )
        sys.exit(1)

    inspect_dataset(sys.argv[1])
