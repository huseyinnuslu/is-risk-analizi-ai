"""Kronolojik bölmeyle başlangıç sınıflandırma ve regresyon modellerini eğitir."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    median_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.features.build_features import (
    CATEGORICAL_FEATURES,
    MODEL_FEATURES,
    NUMERIC_FEATURES,
    build_features,
    build_remaining_days,
)


MODEL_VERSION = "baseline-v1"


def chronological_split(records: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Geçmişle eğitip geleceği test etmek için zaman sıralı 60/20/20 bölme."""

    ordered = records.sort_values(["as_of_date", "id"], kind="stable").reset_index(drop=True)
    train_end = int(len(ordered) * 0.60)
    validation_end = int(len(ordered) * 0.80)
    train, validation, test = (
        ordered.iloc[:train_end].copy(),
        ordered.iloc[train_end:validation_end].copy(),
        ordered.iloc[validation_end:].copy(),
    )
    if min(len(train), len(validation), len(test)) == 0:
        raise ValueError("Kronolojik bölme için yeterli tamamlanmış kayıt yok.")
    return train, validation, test


def build_preprocessor() -> ColumnTransformer:
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("one_hot", OneHotEncoder(handle_unknown="ignore")),
    ])
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    return ColumnTransformer([
        ("categorical", categorical_pipeline, CATEGORICAL_FEATURES),
        ("numeric", numeric_pipeline, NUMERIC_FEATURES),
    ])


def classification_metrics(y_true: pd.Series, probabilities) -> dict:
    predictions = (probabilities >= 0.5).astype(int)
    return {
        "accuracy": round(float(accuracy_score(y_true, predictions)), 4),
        "recall": round(float(recall_score(y_true, predictions, zero_division=0)), 4),
        "precision": round(float(precision_score(y_true, predictions, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, predictions, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, probabilities)), 4),
        "pr_auc": round(float(average_precision_score(y_true, probabilities)), 4),
        "confusion_matrix": confusion_matrix(y_true, predictions).tolist(),
    }


def regression_metrics(y_true: pd.Series, predictions) -> dict:
    mse = mean_squared_error(y_true, predictions)
    return {
        "mae": round(float(mean_absolute_error(y_true, predictions)), 4),
        "rmse": round(float(mse ** 0.5), 4),
        "medae": round(float(median_absolute_error(y_true, predictions)), 4),
        "r2": round(float(r2_score(y_true, predictions)), 4),
        "mape": round(float(mean_absolute_percentage_error(y_true, predictions)), 4),
    }


def _read_completed_records(database_path: Path) -> pd.DataFrame:
    with sqlite3.connect(database_path) as connection:
        records = pd.read_sql_query(
            "SELECT * FROM process_records WHERE status = 'completed' AND is_delayed IS NOT NULL",
            connection,
        )
    if records.empty:
        raise ValueError("Eğitim için tamamlanmış ve etiketlenmiş kayıt bulunamadı.")
    return records


def _register_models(database_path: Path, metrics: dict, artifact_dir: Path) -> None:
    trained_at = datetime.now(timezone.utc).isoformat()
    entries = [
        (
            f"{MODEL_VERSION}-classifier", "classification",
            str(artifact_dir / "delay_classifier_baseline_v1.joblib"),
            json.dumps(metrics["classification"], ensure_ascii=False),
        ),
        (
            f"{MODEL_VERSION}-regressor", "regression",
            str(artifact_dir / "duration_regressor_baseline_v1.joblib"),
            json.dumps(metrics["regression"], ensure_ascii=False),
        ),
    ]
    with sqlite3.connect(database_path) as connection:
        for version, model_type, artifact_path, model_metrics in entries:
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
                (version, model_type, artifact_path, model_metrics, json.dumps(MODEL_FEATURES), trained_at),
            )


def train_baselines(database_path: Path, artifact_dir: Path, report_path: Path) -> dict:
    """Baseline'ları eğitir, artifact/rapor üretir ve modeli SQLite'a kaydeder."""

    records = _read_completed_records(database_path)
    train, validation, test = chronological_split(records)
    x_train, x_validation, x_test = map(build_features, (train, validation, test))
    y_train = train["is_delayed"].astype(int)
    y_validation = validation["is_delayed"].astype(int)
    y_test = test["is_delayed"].astype(int)
    duration_train = build_remaining_days(train)
    duration_validation = build_remaining_days(validation)
    duration_test = build_remaining_days(test)

    classifier = Pipeline([
        ("preprocessor", build_preprocessor()),
        ("model", LogisticRegression(max_iter=1_000, random_state=42)),
    ])
    classifier.fit(x_train, y_train)
    classifier_baseline = DummyClassifier(strategy="prior", random_state=42).fit(x_train, y_train)

    regressor = Pipeline([
        ("preprocessor", build_preprocessor()),
        ("model", LinearRegression()),
    ])
    regressor.fit(x_train, duration_train)
    regressor_baseline = DummyRegressor(strategy="median").fit(x_train, duration_train)

    classification_report = {
        "baseline_validation": classification_metrics(
            y_validation, classifier_baseline.predict_proba(x_validation)[:, 1]
        ),
        "logistic_regression_validation": classification_metrics(
            y_validation, classifier.predict_proba(x_validation)[:, 1]
        ),
        "logistic_regression_test": classification_metrics(
            y_test, classifier.predict_proba(x_test)[:, 1]
        ),
    }
    regression_report = {
        "baseline_validation": regression_metrics(
            duration_validation, regressor_baseline.predict(x_validation)
        ),
        "linear_regression_validation": regression_metrics(
            duration_validation, regressor.predict(x_validation)
        ),
        "linear_regression_test": regression_metrics(duration_test, regressor.predict(x_test)),
    }
    report = {
        "model_version": MODEL_VERSION,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "split": {"train": len(train), "validation": len(validation), "test": len(test)},
        "feature_list": MODEL_FEATURES,
        "excluded_leakage_columns": ["completed_at", "is_delayed", "total_duration_days"],
        "classification": classification_report,
        "regression": regression_report,
    }

    artifact_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(classifier, artifact_dir / "delay_classifier_baseline_v1.joblib")
    joblib.dump(regressor, artifact_dir / "duration_regressor_baseline_v1.joblib")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _register_models(database_path, report, artifact_dir)
    return report
