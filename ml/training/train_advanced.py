"""Gelişmiş model adaylarını kıyaslar, seçer ve açıklama raporu üretir."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import joblib
import pandas as pd
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.pipeline import Pipeline

from ml.evaluation.importance import calculate_permutation_importance
from ml.evaluation.model_guard import assert_not_regressed
from ml.features.build_features import MODEL_FEATURES, build_features, build_remaining_days
from ml.training.train_baselines import (
    _read_completed_records,
    build_preprocessor,
    chronological_split,
    classification_metrics,
    regression_metrics,
)


MODEL_VERSION = "advanced-v1"


def _classifier_candidates() -> dict[str, Pipeline]:
    return {
        "logistic_regression": Pipeline([
            ("preprocessor", build_preprocessor()),
            ("model", LogisticRegression(max_iter=1_000, random_state=42)),
        ]),
        "random_forest": Pipeline([
            ("preprocessor", build_preprocessor()),
            ("model", RandomForestClassifier(
                n_estimators=150, min_samples_leaf=6, class_weight="balanced",
                random_state=42, n_jobs=1,
            )),
        ]),
        "hist_gradient_boosting": Pipeline([
            ("preprocessor", build_preprocessor()),
            ("model", HistGradientBoostingClassifier(
                learning_rate=0.08, max_iter=220, max_leaf_nodes=20,
                l2_regularization=1.0, random_state=42,
            )),
        ]),
    }


def _regressor_candidates() -> dict[str, Pipeline]:
    return {
        "linear_regression": Pipeline([
            ("preprocessor", build_preprocessor()),
            ("model", LinearRegression()),
        ]),
        "random_forest": Pipeline([
            ("preprocessor", build_preprocessor()),
            ("model", RandomForestRegressor(
                n_estimators=150, min_samples_leaf=5, random_state=42, n_jobs=1,
            )),
        ]),
        "hist_gradient_boosting": Pipeline([
            ("preprocessor", build_preprocessor()),
            ("model", HistGradientBoostingRegressor(
                learning_rate=0.07, max_iter=250, max_leaf_nodes=20,
                l2_regularization=1.0, random_state=42,
            )),
        ]),
    }


def _register_selected_models(database_path: Path, report: dict, artifact_dir: Path) -> None:
    now = datetime.now(timezone.utc).isoformat()
    selected = [
        (
            f"{MODEL_VERSION}-classifier", "classification",
            artifact_dir / "delay_classifier_advanced_v1.joblib",
            report["classification"]["selected"],
        ),
        (
            f"{MODEL_VERSION}-regressor", "regression",
            artifact_dir / "duration_regressor_advanced_v1.joblib",
            report["regression"]["selected"],
        ),
    ]
    with sqlite3.connect(database_path) as connection:
        for version, model_type, artifact, selected_metrics in selected:
            connection.execute("UPDATE model_registry SET is_active = 0 WHERE model_type = ?", (model_type,))
            connection.execute(
                """
                INSERT INTO model_registry
                    (model_version, model_type, artifact_path, metrics_json, feature_list_json, trained_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(model_version) DO UPDATE SET
                    artifact_path=excluded.artifact_path,
                    metrics_json=excluded.metrics_json,
                    feature_list_json=excluded.feature_list_json,
                    trained_at=excluded.trained_at,
                    is_active=1
                """,
                (
                    version, model_type, str(artifact),
                    json.dumps(selected_metrics, ensure_ascii=False),
                    json.dumps(MODEL_FEATURES), now,
                ),
            )


def train_advanced_models(
    database_path: Path,
    artifact_dir: Path,
    report_path: Path,
    verbose: bool = False,
) -> dict:
    """Adayları validation üzerinde seçer, testte bir kez raporlar."""

    log = print if verbose else lambda _message: None
    log("[1/6] SQLite'tan tamamlanmış kayıtlar okunuyor...")
    records = _read_completed_records(database_path)
    train, validation, test = chronological_split(records)
    log(
        f"[2/6] Kronolojik bölme tamamlandı: "
        f"eğitim={len(train)}, doğrulama={len(validation)}, test={len(test)}"
    )
    x_train, x_validation, x_test = map(build_features, (train, validation, test))
    y_train = train["is_delayed"].astype(int)
    y_validation = validation["is_delayed"].astype(int)
    y_test = test["is_delayed"].astype(int)
    duration_train = build_remaining_days(train)
    duration_validation = build_remaining_days(validation)
    duration_test = build_remaining_days(test)

    classifier_scores: dict[str, dict] = {}
    fitted_classifiers: dict[str, Pipeline] = {}
    for name, model in _classifier_candidates().items():
        log(f"[3/6] Gecikme modeli eğitiliyor: {name}")
        model.fit(x_train, y_train)
        classifier_scores[name] = classification_metrics(
            y_validation, model.predict_proba(x_validation)[:, 1]
        )
        log(
            f"       validation ROC-AUC={classifier_scores[name]['roc_auc']}, "
            f"recall={classifier_scores[name]['recall']}"
        )
        fitted_classifiers[name] = model

    # Ana seçim metriği ROC-AUC; eşitlikte yüksek riskli işi kaçırmamak için recall.
    selected_classifier_name = max(
        classifier_scores,
        key=lambda name: (classifier_scores[name]["roc_auc"], classifier_scores[name]["recall"]),
    )
    selected_classifier = fitted_classifiers[selected_classifier_name]
    classifier_test_metrics = classification_metrics(
        y_test, selected_classifier.predict_proba(x_test)[:, 1]
    )
    log(f"       Seçilen gecikme modeli: {selected_classifier_name}")

    regressor_scores: dict[str, dict] = {}
    fitted_regressors: dict[str, Pipeline] = {}
    for name, model in _regressor_candidates().items():
        log(f"[4/6] Süre modeli eğitiliyor: {name}")
        model.fit(x_train, duration_train)
        regressor_scores[name] = regression_metrics(duration_validation, model.predict(x_validation))
        log(f"       validation MAE={regressor_scores[name]['mae']} gün")
        fitted_regressors[name] = model

    # Süre tahmininde en küçük MAE seçilir; eşitlikte daha küçük RMSE tercih edilir.
    selected_regressor_name = min(
        regressor_scores,
        key=lambda name: (regressor_scores[name]["mae"], regressor_scores[name]["rmse"]),
    )
    selected_regressor = fitted_regressors[selected_regressor_name]
    regressor_test_metrics = regression_metrics(duration_test, selected_regressor.predict(x_test))
    log(f"       Seçilen süre modeli: {selected_regressor_name}")
    log("[5/6] Permutation importance ile açıklanabilirlik hesaplanıyor...")

    report = {
        "model_version": MODEL_VERSION,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "split": {"train": len(train), "validation": len(validation), "test": len(test)},
        "feature_list": MODEL_FEATURES,
        "excluded_leakage_columns": ["completed_at", "is_delayed", "total_duration_days"],
        "classification": {
            "selection_metric": "En yüksek validation ROC-AUC; eşitlikte recall",
            "validation_candidates": classifier_scores,
            "selected_model": selected_classifier_name,
            "selected": classifier_test_metrics,
            "permutation_importance": calculate_permutation_importance(
                selected_classifier, x_validation, y_validation, scoring="roc_auc"
            ),
        },
        "regression": {
            "selection_metric": "En düşük validation MAE; eşitlikte RMSE",
            "validation_candidates": regressor_scores,
            "selected_model": selected_regressor_name,
            "selected": regressor_test_metrics,
            "permutation_importance": calculate_permutation_importance(
                selected_regressor, x_validation, duration_validation,
                scoring="neg_mean_absolute_error",
            ),
        },
    }

    # İlk eğitimde temel rapor henüz olmayabilir. Varsa, test kümesinde daha
    # kötüleşen bir modeli artefakt olarak kaydetmeyiz.
    baseline_report_path = report_path.parent / "baseline_metrics.json"
    if baseline_report_path.exists():
        baseline_report = json.loads(baseline_report_path.read_text(encoding="utf-8"))
        report["baseline_comparison"] = assert_not_regressed(
            {
                "classification": report["classification"]["selected"],
                "regression": report["regression"]["selected"],
            },
            {
                "classification": baseline_report["classification"]["logistic_regression_test"],
                "regression": baseline_report["regression"]["linear_regression_test"],
            },
        )

    artifact_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(selected_classifier, artifact_dir / "delay_classifier_advanced_v1.joblib")
    joblib.dump(selected_regressor, artifact_dir / "duration_regressor_advanced_v1.joblib")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _register_selected_models(database_path, report, artifact_dir)
    log("[6/6] Modeller, rapor ve SQLite model kaydı oluşturuldu.")
    return report
