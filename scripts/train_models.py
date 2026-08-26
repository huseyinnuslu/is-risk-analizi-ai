"""Faz 3 baseline modellerini çalıştırır."""

from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ml.training.train_baselines import train_baselines


if __name__ == "__main__":
    result = train_baselines(
        database_path=PROJECT_ROOT / "data" / "process_risk.db",
        artifact_dir=PROJECT_ROOT / "ml" / "artifacts",
        report_path=PROJECT_ROOT / "reports" / "generated" / "baseline_metrics.json",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
