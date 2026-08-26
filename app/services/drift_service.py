"""Eğitim bağlamı ile açık işler arasındaki basit veri dağılımı karşılaştırması."""

from __future__ import annotations

import math


NUMERIC_FIELDS = ("revision_count", "missing_document_count", "days_in_current_stage", "team_workload")
CATEGORICAL_FIELDS = ("process_type", "current_stage", "responsible_team", "priority")


def _distribution(values: list, categories: list) -> list[float]:
    total = len(values) or 1
    return [sum(value == category for value in values) / total for category in categories]


def population_stability_index(reference: list[float], current: list[float], bins: int = 5) -> float:
    """Sayısal alanlarda PSI hesaplar; 0.10/0.25 eşikleri yaygın izleme eşikleridir."""

    if not reference or not current:
        return 0.0
    ordered = sorted(float(value) for value in reference)
    edges = sorted({ordered[round((len(ordered) - 1) * index / bins)] for index in range(1, bins)})
    boundaries = [-math.inf, *edges, math.inf]
    score = 0.0
    for lower, upper in zip(boundaries, boundaries[1:]):
        reference_ratio = sum(lower < float(value) <= upper for value in reference) / len(reference)
        current_ratio = sum(lower < float(value) <= upper for value in current) / len(current)
        reference_ratio = max(reference_ratio, 0.0001)
        current_ratio = max(current_ratio, 0.0001)
        score += (current_ratio - reference_ratio) * math.log(current_ratio / reference_ratio)
    return round(score, 4)


def categorical_drift(reference: list[str], current: list[str]) -> float:
    """Kategorik alanlarda toplam değişim oranı (TV distance) hesaplar."""

    categories = sorted(set(reference) | set(current))
    reference_distribution = _distribution(reference, categories)
    current_distribution = _distribution(current, categories)
    return round(sum(abs(left - right) for left, right in zip(reference_distribution, current_distribution)) / 2, 4)


def drift_report(reference_rows: list[dict], current_rows: list[dict]) -> dict:
    fields: list[dict] = []
    for field in NUMERIC_FIELDS:
        score = population_stability_index(
            [float(row[field]) for row in reference_rows], [float(row[field]) for row in current_rows]
        )
        level = "yüksek" if score >= 0.25 else "izle" if score >= 0.10 else "normal"
        fields.append({"field": field, "method": "PSI", "score": score, "level": level})
    for field in CATEGORICAL_FIELDS:
        score = categorical_drift(
            [str(row[field]) for row in reference_rows], [str(row[field]) for row in current_rows]
        )
        level = "yüksek" if score >= 0.25 else "izle" if score >= 0.10 else "normal"
        fields.append({"field": field, "method": "Toplam değişim", "score": score, "level": level})
    severity = "yüksek" if any(item["level"] == "yüksek" for item in fields) else "izle" if any(item["level"] == "izle" for item in fields) else "normal"
    return {
        "reference_count": len(reference_rows),
        "current_count": len(current_rows),
        "severity": severity,
        "note": "Bu bir veri dağılımı uyarısıdır; modelin hatalı olduğu veya yeniden eğitim gerektiği tek başına anlamına gelmez.",
        "fields": sorted(fields, key=lambda item: item["score"], reverse=True),
    }
