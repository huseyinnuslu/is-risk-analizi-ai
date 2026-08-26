"""Aktif modelleri kullanarak açıklanabilir tahmin üretir."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from datetime import date, timedelta

import joblib
import pandas as pd

from app.core.config import REPORT_DIR
from ml.features.build_features import build_features


SIMULATABLE_FIELDS = {
    "priority", "revision_count", "missing_document_count",
    "stage_change_count", "days_in_current_stage", "current_stage",
}
FACTOR_LABELS = {
    "missing_document_count": "Eksik belge sayısı",
    "revision_count": "Revizyon sayısı",
    "days_in_current_stage": "Mevcut aşamada geçirilen gün",
    "stage_change_count": "Aşama değişim sayısı",
    "priority": "İş önceliği",
}


@lru_cache(maxsize=4)
def _load_model(path: str):
    return joblib.load(path)


def risk_level(score: int) -> str:
    if score >= 70:
        return "Yüksek"
    if score >= 40:
        return "Orta"
    return "Düşük"


def prepare_live_prediction_input(
    record: dict,
    prediction_date: date | None = None,
    current_team_workload: int | None = None,
) -> dict:
    """Açık işin feature'larını tahmin gününe taşır, kaynağı değiştirmez.

    `days_in_current_stage` için mevcut aşamanın değişmediği varsayılır. Gerçek
    sistemde aşama değiştiğinde kaynak kayıttaki değer de güncellenmelidir.
    """

    today = prediction_date or date.today()
    snapshot_date = date.fromisoformat(record["as_of_date"])
    elapsed_days = max(0, (today - snapshot_date).days)
    live_record = record | {
        "as_of_date": today.isoformat(),
        "days_in_current_stage": float(record["days_in_current_stage"]) + elapsed_days,
    }
    if current_team_workload is not None:
        live_record["team_workload"] = current_team_workload
    return live_record


def _risk_explanation(record: dict, classifier, original_probability: float) -> dict:
    """Aynı modelde daha iyi karşı-senaryolar deneyerek yerel etkiyi ölçer."""

    factors = []
    as_of_date = date.fromisoformat(record["as_of_date"])
    deadline = date.fromisoformat(record["deadline"])
    if deadline <= as_of_date:
        # Son tarih tahmin anında bilinen bir alan ve modelde doğrudan kullanılıyor.
        overdue_days = (as_of_date - deadline).days
        safer_deadline = (as_of_date + timedelta(days=7)).isoformat()
        scenario_probability = float(
            classifier.predict_proba(
                build_features(pd.DataFrame([record | {"deadline": safer_deadline}]))
            )[:, 1][0]
        )
        factors.append({
            "feature": "deadline_remaining_days",
            "label": "Son tarih durumu",
            "current_value": f"{overdue_days} gün geçti",
            "improved_value": "7 gün kalan senaryo",
            "risk_impact_points": round(max(0, original_probability - scenario_probability) * 100, 1),
            "message": f"Son tarih tahmin anında {overdue_days} gün geçmiş. Model son tarihe kalan günü risk girdisi olarak kullanır.",
        })
    improvements = {
        "missing_document_count": 0,
        "revision_count": 0,
        "days_in_current_stage": max(0, float(record["days_in_current_stage"]) * 0.5),
        "stage_change_count": max(0, int(record["stage_change_count"]) - 1),
    }
    for feature, better_value in improvements.items():
        current_value = record[feature]
        if current_value == better_value:
            continue
        scenario = record | {feature: better_value}
        scenario_probability = float(classifier.predict_proba(build_features(pd.DataFrame([scenario])))[:, 1][0])
        impact = original_probability - scenario_probability
        if impact > 0.003:
            factors.append({
                "feature": feature,
                "label": FACTOR_LABELS[feature],
                "current_value": current_value,
                "improved_value": better_value,
                "risk_impact_points": round(impact * 100, 1),
                "message": f"{FACTOR_LABELS[feature]} azaltıldığında model riski düşürüyor.",
            })

    factors.sort(key=lambda item: item["risk_impact_points"], reverse=True)
    return {
        "method": "model_karşı_senaryo_duyarlılığı",
        "note": "Etkiler, aynı eğitilmiş modelde alan tek tek iyileştirildiğinde olasılıktaki değişimdir; nedensel kanıt değildir.",
        "context_note": (
            "Son tarih bugün veya geçmişte. Takvim baskısı model olasılığını tavana yaklaştırdığı için, "
            "tek tek alanlardaki küçük iyileşmeler 0–100 puanında görünmeyebilir."
            if deadline <= as_of_date else None
        ),
        "top_risk_factors": factors[:3],
        "recommended_actions": recommended_actions(record),
    }


def recommended_actions(record: dict) -> list[dict[str, str]]:
    """Risk girdilerinden türetilen, kesin karar olmayan işlem önerileri."""

    actions: list[dict[str, str]] = []
    deadline_remaining = (date.fromisoformat(record["deadline"]) - date.fromisoformat(record["as_of_date"])).days
    if deadline_remaining <= 3:
        actions.append({
            "title": "Teslim planını bugün kontrol edin",
            "reason": f"Son tarihe {max(0, deadline_remaining)} gün kaldı; takvim aciliyeti model skorundan bağımsız izlenmelidir.",
        })
    if int(record["missing_document_count"]) > 0:
        actions.append({
            "title": "Eksik belgeleri tamamlatın",
            "reason": f"Bekleyen {record['missing_document_count']} belge kaydı bulunuyor.",
        })
    if int(record["revision_count"]) >= 2:
        actions.append({
            "title": "Revizyon nedenini netleştirin",
            "reason": f"{record['revision_count']} revizyon, tekrar işleme olasılığına işaret edebilir.",
        })
    if float(record["days_in_current_stage"]) > float(record["historical_avg_stage_days"]):
        actions.append({
            "title": "Aşama beklemesini gözden geçirin",
            "reason": "Bu aşamadaki süre, benzer işlerin tarihsel ortalamasını aştı.",
        })
    if int(record["team_workload"]) >= 80:
        actions.append({
            "title": "Ekip kapasitesini kontrol edin",
            "reason": f"Tahmin anındaki ekip kapasite kullanımı %{record['team_workload']}.",
        })
    return actions[:3]


def predict(
    record: dict,
    classifier_artifact: Path,
    regressor_artifact: Path,
    model_version: str,
    regression_mae: float | None = None,
) -> dict:
    classifier = _load_model(str(classifier_artifact))
    regressor = _load_model(str(regressor_artifact))
    features = build_features(pd.DataFrame([record]))
    probability = float(classifier.predict_proba(features)[:, 1][0])
    score = round(probability * 100)
    # Açık iş henüz tamamlanmadığı için kullanıcıya 0 gün göstermek yanıltıcıdır.
    remaining_days = max(1.0, float(regressor.predict(features)[0]))
    remaining_days = round(remaining_days, 1)
    # Bu istatistiksel bir güven aralığı değildir. Test MAE'sini görünür kılarak
    # sürenin tek ve kesin bir sayı gibi yorumlanmasını önler.
    uncertainty = None
    if regression_mae is not None:
        margin = round(float(regression_mae), 1)
        uncertainty = {
            "lower_days": round(max(1.0, remaining_days - margin), 1),
            "upper_days": round(remaining_days + margin, 1),
            "mae_days": margin,
            "note": "Aralık, aktif süre modelinin test MAE değerinden türetilen yaklaşık hata payıdır; güven aralığı değildir.",
        }
    return {
        "model_version": model_version,
        "delay_probability": round(probability, 4),
        "risk_score": score,
        "risk_level": risk_level(score),
        "predicted_remaining_days": remaining_days,
        "remaining_days_uncertainty": uncertainty,
        "explanation": _risk_explanation(record, classifier, probability),
    }


def active_artifact_paths(active_models: list[dict]) -> tuple[Path, Path, str]:
    by_type = {item["model_type"]: item for item in active_models}
    if "classification" not in by_type or "regression" not in by_type:
        raise RuntimeError("Aktif sınıflandırma ve regresyon modeli bulunamadı.")
    return (
        Path(by_type["classification"]["artifact_path"]),
        Path(by_type["regression"]["artifact_path"]),
        by_type["classification"]["model_version"],
    )
