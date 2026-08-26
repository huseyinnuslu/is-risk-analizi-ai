"""Yeni modelin yerleşik temel modele göre gerilemesini engeller."""

from __future__ import annotations


class ModelRegressionError(RuntimeError):
    """Aday model, temel modelin test başarımını koruyamadığında yükseltilir."""


def assert_not_regressed(candidate: dict, baseline: dict) -> dict[str, float]:
    """Sınıflandırmada ROC-AUC, süre tahmininde MAE karşılaştırması yapar.

    ROC-AUC yükselmelidir; MAE ise düşmelidir. Böylece yeni modelin yalnızca
    doğrulama kümesinde iyi görünmesiyle aktif modele dönüşmesi önlenir.
    """

    candidate_auc = float(candidate["classification"]["roc_auc"])
    baseline_auc = float(baseline["classification"]["roc_auc"])
    candidate_mae = float(candidate["regression"]["mae"])
    baseline_mae = float(baseline["regression"]["mae"])

    if candidate_auc < baseline_auc:
        raise ModelRegressionError(
            f"ROC-AUC geriledi: aday={candidate_auc:.4f}, temel={baseline_auc:.4f}"
        )
    if candidate_mae > baseline_mae:
        raise ModelRegressionError(
            f"MAE geriledi: aday={candidate_mae:.4f}, temel={baseline_mae:.4f}"
        )

    return {
        "roc_auc_delta": round(candidate_auc - baseline_auc, 4),
        "mae_delta_days": round(candidate_mae - baseline_mae, 4),
    }
