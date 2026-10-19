
import duckdb

from src.feature_store.validate_feature_dataset import (
    audit_transaction_integrity,
)


def create_test_tables(con, raw_rows, feature_rows):
    columns = """
        step, type, amount, nameOrig,
        oldbalanceOrg, newbalanceOrig, nameDest,
        oldbalanceDest, newbalanceDest, isFraud, isFlaggedFraud
    """

    for table_name, rows in [
        ("raw_data", raw_rows),
        ("features", feature_rows),
    ]:
        values = ", ".join(
            "(" + ", ".join(
                "NULL" if value is None else
                "'" + value.replace("'", "''") + "'"
                if isinstance(value, str) else str(value)
                for value in row
            ) + ")"
            for row in rows
        )

        con.execute(
            f"CREATE TABLE {table_name} AS "
            f"SELECT * FROM (VALUES {values}) AS t({columns})"
        )


def test_identical_transactions_pass_integrity_audit():
    row = (
        1, "PAYMENT", 100.0, "C1", 500.0, 400.0,
        "M1", 0.0, 100.0, 0, 0,
    )

    con = duckdb.connect(":memory:")
    try:
        create_test_tables(con, [row, row], [row, row])

        result = audit_transaction_integrity(con)

        assert result["passed"] is True
        assert result["missing_transactions"] == 0
        assert result["extra_or_altered_transactions"] == 0
    finally:
        con.close()


def test_missing_transaction_fails_integrity_audit():
    row1 = (
        1, "PAYMENT", 100.0, "C1", 500.0, 400.0,
        "M1", 0.0, 100.0, 0, 0,
    )
    row2 = (
        2, "CASH_OUT", 200.0, "C2", 300.0, 100.0,
        "M2", 0.0, 200.0, 1, 0,
    )

    con = duckdb.connect(":memory:")
    try:
        create_test_tables(con, [row1, row2], [row1])

        result = audit_transaction_integrity(con)

        assert result["passed"] is False
        assert result["missing_transactions"] == 1
        assert result["extra_or_altered_transactions"] == 0
    finally:
        con.close()
