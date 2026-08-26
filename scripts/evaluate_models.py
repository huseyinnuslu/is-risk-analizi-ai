"""Aktif modelleri son kronolojik test dilimi üzerinde yeniden değerlendirir."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

import joblib

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import DATABASE_PATH, MODEL_ARTIFACT_DIR, REPORT_DIR
from app.repositories import process_repository as repository
from app.services.prediction_service import active_artifact_paths
from ml.features.build_features import build_features, build_remaining_days
from ml.training.train_baselines import (
    _read_completed_records,
    chronological_split,
    classification_metrics,
    regression_metrics,
)


def evaluate_active_models(database_path: Path, report_path: Path) -> dict:
    """Aktif joblib modellerini eğitime dokunmadan tekrar ölçer."""
    active_models = repository.get_active_models(database_path)
    classifier_path, regressor_path, version = active_artifact_paths(active_models)
    if not classifier_path.exists() or not regressor_path.exists():
        raise FileNotFoundError("Aktif model dosyası bulunamadı. Önce modeli eğitin.")

    records = _read_completed_records(database_path)
    _, _, test = chronological_split(records)
    features = build_features(test)
    classifier = joblib.load(classifier_path)
    regressor = joblib.load(regressor_path)

    report = {
        "model_version": version,
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_method": "completed records üzerinde son kronolojik %20 test dilimi",
        "test_record_count": len(test),
        "classification": classification_metrics(
            test["is_delayed"].astype(int), classifier.predict_proba(features)[:, 1]
        ),
        "regression": regression_metrics(
            build_remaining_days(test), regressor.predict(features)
        ),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Aktif modelleri kronolojik test diliminde değerlendirir.")
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_DIR / "active_model_evaluation.json")
    args = parser.parse_args()
    result = evaluate_active_models(args.database, args.report)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
