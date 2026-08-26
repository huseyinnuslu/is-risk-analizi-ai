import pandas as pd

from ml.training.train_baselines import chronological_split


def test_chronological_split_preserves_time_order():
    records = pd.DataFrame({
        "id": range(10),
        "as_of_date": pd.date_range("2026-01-01", periods=10, freq="D").astype(str),
    })
    train, validation, test = chronological_split(records)
    assert len(train) == 6
    assert len(validation) == 2
    assert len(test) == 2
    assert train["as_of_date"].max() <= validation["as_of_date"].min()
    assert validation["as_of_date"].max() <= test["as_of_date"].min()
