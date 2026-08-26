import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from ml.evaluation.importance import calculate_permutation_importance


def test_permutation_importance_returns_all_feature_names():
    features = pd.DataFrame({"signal": [0, 0, 1, 1, 0, 1], "noise": [1, 0, 1, 0, 1, 0]})
    target = pd.Series([0, 0, 1, 1, 0, 1])
    model = LogisticRegression().fit(features, target)
    result = calculate_permutation_importance(model, features, target, scoring="roc_auc")
    assert {entry["feature"] for entry in result} == {"signal", "noise"}
    assert np.isfinite([entry["importance_mean"] for entry in result]).all()
