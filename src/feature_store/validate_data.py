
import json
import sys
from pathlib import Path

import duckdb


def validate_dataset(csv_path: str) -> None:
    path = Path(csv_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    con = duckdb.connect(database=":memory:")

    try:
        
        con.execute(
            "CREATE VIEW transactions AS "
            f"SELECT * FROM read_csv_auto('{str(path).replace(chr(39), chr(39) * 2)}')"
        )


        # Count rows that violate basic data rules.
        checks = {
            "negative_amount": "amount < 0",
            "zero_amount": "amount = 0",
            "invalid_step": "step <= 0",
            "negative_sender_balance": (
                "oldbalanceOrg < 0 OR newbalanceOrig < 0"
            ),
            "negative_receiver_balance": (
                "oldbalanceDest < 0 OR newbalanceDest < 0"
            ),
            "invalid_fraud_label": "isFraud NOT IN (0, 1)",
            "invalid_flag_label": "isFlaggedFraud NOT IN (0, 1)",
            "unknown_transaction_type": (
                "type IS NULL OR type NOT IN "
                "('PAYMENT', 'TRANSFER', 'CASH_OUT', "
                "'CASH_IN', 'DEBIT')"
            ),
            "missing_customer_id": (
                "nameOrig IS NULL OR TRIM(nameOrig) = ''"
            ),
            "missing_destination_id": (
                "nameDest IS NULL OR TRIM(nameDest) = ''"
            ),
        }

        results = {}

        total_rows = con.execute(
            "SELECT COUNT(*) FROM transactions"
        ).fetchone()[0]

        print(f"\nTotal rows: {total_rows:,}")
        print("\n=== DATA QUALITY CHECKS ===")

        for name, condition in checks.items():
            count = con.execute(
                f"SELECT COUNT(*) FROM transactions WHERE {condition}"
            ).fetchone()[0]

            results[name] = count
            print(f"{name:30} {count:,}")

        # Count extra rows belonging to exact duplicate groups.
        
        duplicate_result = con.execute("""
    SELECT
        COUNT(*) AS duplicate_groups,
        COALESCE(SUM(n), 0) AS rows_in_duplicate_groups,
        COALESCE(SUM(n - 1), 0) AS extra_duplicate_rows
    FROM (
        SELECT COUNT(*) AS n
        FROM transactions
        GROUP BY
            step,
            type,
            amount,
            nameOrig,
            oldbalanceOrg,
            newbalanceOrig,
            nameDest,
            oldbalanceDest,
            newbalanceDest,
            isFraud,
            isFlaggedFraud
               HAVING COUNT(*) > 1
           ) AS duplicate_groups
        """).fetchone()

        duplicate_groups, duplicate_rows, duplicate_count = duplicate_result

        results["exact_duplicate_groups"] = duplicate_groups
        results["rows_in_duplicate_groups"] = duplicate_rows

        print(f"{'exact_duplicate_groups':30} {duplicate_groups:,}")
        print(f"{'rows_in_duplicate_groups':30} {duplicate_rows:,}")

        results["exact_duplicate_extra_rows"] = duplicate_count

        print(f"{'exact_duplicate_extra_rows':30} {duplicate_count:,}")

        # Useful summaries for understanding the dataset.
        print("\n=== TRANSACTION SUMMARY ===")

        summary = con.execute("""
            SELECT
                COUNT(DISTINCT type) AS transaction_types,
                COUNT(DISTINCT nameOrig) AS unique_senders,
                COUNT(DISTINCT nameDest) AS unique_destinations,
                SUM(isFraud) AS fraud_transactions,
                MIN(amount) AS minimum_amount,
                MAX(amount) AS maximum_amount
            FROM transactions
        """).fetchone()

        summary_data = {
            "transaction_types": summary[0],
            "unique_senders": summary[1],
            "unique_destinations": summary[2],
            "fraud_transactions": summary[3],
            "minimum_amount": summary[4],
            "maximum_amount": summary[5],
        }

        for key, value in summary_data.items():
            print(f"{key:30} {value}")

        report = {
            "dataset": path.name,
            "total_rows": total_rows,
            "validation_checks": results,
            "summary": summary_data,
        }

        report_dir = Path("data/reports")
        report_dir.mkdir(parents=True, exist_ok=True)

        report_path = report_dir / "validation_report.json"
        report_path.write_text(
            json.dumps(report, indent=2, default=str),
            encoding="utf-8",
        )

        print(f"\nReport saved to: {report_path}")

    finally:
        con.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            'Usage: python src/feature_store/validate_data.py '
            '"path/to/transactions.csv"'
        )
        sys.exit(1)

    validate_dataset(sys.argv[1])
