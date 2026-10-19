
import json
from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FILE = PROJECT_ROOT / "data" / "raw" / "transactions.csv"
FEATURE_FILE = (
    PROJECT_ROOT / "data" / "features" / "customer_features.parquet"
)
REPORT_FILE = (
    PROJECT_ROOT / "data" / "reports" / "feature_quality_report.json"
)

REQUIRED_COLUMNS = {
    "nameOrig",
    "step",
    "amount",
    "customer_transaction_count",
    "customer_prior_active_steps",
    "customer_avg_transactions_per_active_step",
    "customer_avg_amount",
    "has_customer_history",
    "amount_vs_avg",
}


def validate_feature_dataset() -> None:
    if not RAW_FILE.exists():
        raise FileNotFoundError(f"Raw dataset not found: {RAW_FILE}")

    if not FEATURE_FILE.exists():
        raise FileNotFoundError(
            f"Feature dataset not found: {FEATURE_FILE}. "
            "Run build_features.py first."
        )

    con = duckdb.connect(database=":memory:")

    try:
        raw_path = str(RAW_FILE).replace("\\", "/").replace("'", "''")
        feature_path = (
            str(FEATURE_FILE).replace("\\", "/").replace("'", "''")
        )

        con.execute(f"""
            CREATE VIEW raw_data AS
            SELECT * FROM read_csv_auto('{raw_path}')
        """)

        con.execute(f"""
            CREATE VIEW features AS
            SELECT * FROM read_parquet('{feature_path}')
        """)

        columns = {
            row[0]
            for row in con.execute(
                "DESCRIBE features"
            ).fetchall()
        }

        missing_columns = sorted(REQUIRED_COLUMNS - columns)

        if missing_columns:
            raise AssertionError(
                f"Missing required columns: {missing_columns}"
            )

        result = con.execute("""
            SELECT
                (SELECT COUNT(*) FROM raw_data) AS raw_rows,
                COUNT(*) AS feature_rows,

                COUNT(*) FILTER (
                    WHERE nameOrig IS NULL
                ) AS null_customer_ids,

                COUNT(*) FILTER (
                    WHERE step IS NULL
                ) AS null_steps,

                COUNT(*) FILTER (
                    WHERE customer_transaction_count IS NULL
                       OR customer_prior_active_steps IS NULL
                       OR has_customer_history IS NULL
                ) AS null_required_features,

                COUNT(*) FILTER (
                    WHERE customer_transaction_count < 0
                       OR customer_prior_active_steps < 0
                ) AS negative_history_rows,

                COUNT(*) FILTER (
                    WHERE has_customer_history NOT IN (0, 1)
                ) AS invalid_history_flags,

                COUNT(*) FILTER (
                    WHERE has_customer_history <>
                        CASE
                            WHEN customer_transaction_count > 0
                            THEN 1
                            ELSE 0
                        END
                ) AS inconsistent_history_flags,

                COUNT(*) FILTER (
                    WHERE customer_transaction_count = 0
                      AND customer_avg_amount IS NOT NULL
                ) AS unexpected_avg_amount,

                COUNT(*) FILTER (
                    WHERE customer_prior_active_steps = 0
                      AND customer_avg_transactions_per_active_step
                          IS NOT NULL
                ) AS unexpected_active_step_average,

                COUNT(*) FILTER (
                    WHERE customer_transaction_count > 0
                      AND customer_avg_amount IS NULL
                ) AS missing_historical_amount_average,

                COUNT(*) FILTER (
                    WHERE customer_avg_transactions_per_active_step < 0
                ) AS negative_active_step_average,

                COUNT(*) FILTER (
                    WHERE amount_vs_avg IS NOT NULL
                      AND (
                          amount_vs_avg < 0
                          OR NOT isfinite(amount_vs_avg)
                      )
                ) AS invalid_amount_ratios

            FROM features
        """).fetchone()

        names = [
            "raw_rows",
            "feature_rows",
            "null_customer_ids",
            "null_steps",
            "null_required_features",
            "negative_history_rows",
            "invalid_history_flags",
            "inconsistent_history_flags",
            "unexpected_avg_amount",
            "unexpected_active_step_average",
            "missing_historical_amount_average",
            "negative_active_step_average",
            "invalid_amount_ratios",
        ]

        metrics = dict(zip(names, result))

        checks = {
            "required_columns_present": len(missing_columns) == 0,
            "row_count_matches_raw": (
                metrics["raw_rows"] == metrics["feature_rows"]
            ),
            "customer_ids_present": metrics["null_customer_ids"] == 0,
            "steps_present": metrics["null_steps"] == 0,
            "required_features_present": (
                metrics["null_required_features"] == 0
            ),
            "historical_counts_nonnegative": (
                metrics["negative_history_rows"] == 0
            ),
            "history_flags_valid": (
                metrics["invalid_history_flags"] == 0
            ),
            "history_flags_consistent": (
                metrics["inconsistent_history_flags"] == 0
            ),
            "average_null_rules_valid": (
                metrics["unexpected_avg_amount"] == 0
                and metrics["unexpected_active_step_average"] == 0
            ),
            "historical_amount_average_present": (
                metrics["missing_historical_amount_average"] == 0
            ),
            "active_step_average_nonnegative": (
                metrics["negative_active_step_average"] == 0
            ),
            "amount_ratios_valid": (
                metrics["invalid_amount_ratios"] == 0
            ),
        }

        report = {
            "project": "Customer Risk Feature Store",
            "checks_passed": sum(checks.values()),
            "checks_total": len(checks),
            "status": (
                "PASS" if all(checks.values()) else "FAIL"
            ),
            "checks": checks,
            "metrics": metrics,
        }

        REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        REPORT_FILE.write_text(
            json.dumps(report, indent=4),
            encoding="utf-8",
        )

        print("\n=== FEATURE DATASET QUALITY REPORT ===")
        print(f"Status: {report['status']}")
        print(
            f"Checks passed: "
            f"{report['checks_passed']}/{report['checks_total']}"
        )
        print(f"Raw rows: {metrics['raw_rows']:,}")
        print(f"Feature rows: {metrics['feature_rows']:,}")

        for name, passed in checks.items():
            print(f"[{'PASS' if passed else 'FAIL'}] {name}")

        print(f"\nReport saved to: {REPORT_FILE}")

        if not all(checks.values()):
            raise AssertionError(
                "Feature dataset quality validation failed. "
                "Review the report for details."
            )

    finally:
        con.close()


if __name__ == "__main__":
    validate_feature_dataset()
