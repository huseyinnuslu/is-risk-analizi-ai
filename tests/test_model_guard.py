import pytest

from ml.evaluation.model_guard import ModelRegressionError, assert_not_regressed


BASELINE = {
    "classification": {"roc_auc": 0.72},
    "regression": {"mae": 6.8},
}


def test_model_guard_accepts_a_non_regressing_candidate():
    result = assert_not_regressed(
        {"classification": {"roc_auc": 0.78}, "regression": {"mae": 6.7}},
        BASELINE,
    )
    assert result == {"roc_auc_delta": 0.06, "mae_delta_days": -0.1}


@pytest.mark.parametrize(
    "candidate",
    [
        {"classification": {"roc_auc": 0.71}, "regression": {"mae": 6.7}},
        {"classification": {"roc_auc": 0.78}, "regression": {"mae": 6.9}},
    ],
)
def test_model_guard_rejects_a_regressing_candidate(candidate):
    with pytest.raises(ModelRegressionError):
        assert_not_regressed(candidate, BASELINE)
