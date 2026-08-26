"""Faz 4 model karşılaştırmasını ve açıklanabilirlik raporunu üretir."""

from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ml.training.train_advanced import train_advanced_models


if __name__ == "__main__":
    result = train_advanced_models(
        database_path=PROJECT_ROOT / "data" / "process_risk.db",
        artifact_dir=PROJECT_ROOT / "ml" / "artifacts",
        report_path=PROJECT_ROOT / "reports" / "generated" / "advanced_model_report.json",
        verbose=True,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
