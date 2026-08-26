"""Modelden bağımsız permutation importance hesaplaması."""

from __future__ import annotations

import pandas as pd
from sklearn.inspection import permutation_importance


def calculate_permutation_importance(model, features: pd.DataFrame, target, scoring: str) -> list[dict]:
    """Bir özelliğin karıştırılması başarıyı ne kadar düşürüyor, onu ölçer.

    Bu yöntem seçilen algoritmadan bağımsızdır. Importance değeri büyükse
    özelliğin model kararlarına küresel (genel) etkisi daha yüksektir.
    """

    sample = features.sample(n=min(len(features), 1_500), random_state=42)
    sampled_target = target.loc[sample.index]
    result = permutation_importance(
        model,
        sample,
        sampled_target,
        n_repeats=5,
        random_state=42,
        scoring=scoring,
        # Yerel/öğrenci bilgisayarlarında gereksiz thread patlamasını önler.
        n_jobs=1,
    )
    importance = pd.DataFrame({
        "feature": features.columns,
        "importance_mean": result.importances_mean,
        "importance_std": result.importances_std,
    }).sort_values("importance_mean", ascending=False)
    return [
        {
            "feature": row.feature,
            "importance_mean": round(float(row.importance_mean), 5),
            "importance_std": round(float(row.importance_std), 5),
        }
        for row in importance.itertuples(index=False)
    ]
