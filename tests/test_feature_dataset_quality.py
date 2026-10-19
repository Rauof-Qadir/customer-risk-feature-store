
import pytest

from src.feature_store.validate_feature_dataset import (
    build_quality_checks,
)


@pytest.fixture
def valid_metrics():
    return {
        "raw_rows": 100,
        "feature_rows": 100,
        "null_customer_ids": 0,
        "null_steps": 0,
        "null_required_features": 0,
        "negative_history_rows": 0,
        "invalid_history_flags": 0,
        "inconsistent_history_flags": 0,
        "unexpected_avg_amount": 0,
        "unexpected_active_step_average": 0,
        "missing_historical_amount_average": 0,
        "negative_active_step_average": 0,
        "invalid_amount_ratios": 0,
    }


def test_valid_metrics_pass_all_quality_checks(valid_metrics):
    checks = build_quality_checks(valid_metrics, [])

    assert len(checks) == 13
    assert all(checks.values())


def test_missing_required_column_fails(valid_metrics):
    checks = build_quality_checks(
        valid_metrics,
        ["customer_avg_amount"],
    )

    assert checks["required_columns_present"] is False
    assert sum(checks.values()) == 12


@pytest.mark.parametrize(
    ("metric", "check_name"),
    [
        ("raw_rows", "row_count_matches_raw"),
        ("null_customer_ids", "customer_ids_present"),
        ("null_steps", "steps_present"),
        ("null_required_features", "required_features_present"),
        ("negative_history_rows", "historical_counts_nonnegative"),
        ("invalid_history_flags", "history_flags_valid"),
        ("inconsistent_history_flags", "history_flags_consistent"),
        ("unexpected_avg_amount", "average_null_rules_valid"),
        (
            "unexpected_active_step_average",
            "average_null_rules_valid",
        ),
        (
            "missing_historical_amount_average",
            "historical_amount_average_present",
        ),
        (
            "negative_active_step_average",
            "active_step_average_nonnegative",
        ),
        ("invalid_amount_ratios", "amount_ratios_valid"),
    ],
)
def test_invalid_metrics_fail_their_quality_check(
    valid_metrics,
    metric,
    check_name,
):
    valid_metrics[metric] = (
        99 if metric == "raw_rows" else 1
    )

    checks = build_quality_checks(valid_metrics, [])

    assert checks[check_name] is False


def test_wrong_feature_type_fails_schema_check(valid_metrics):
    checks = build_quality_checks(
        valid_metrics,
        [],
        ["customer_transaction_count"],
    )

    assert checks["feature_types_valid"] is False