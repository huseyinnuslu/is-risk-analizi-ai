"""Açık işleri yerel modelle toplu skorlar; web sunucusunu meşgul etmez."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import DATABASE_PATH
from app.repositories import process_repository as repository
from app.services.prediction_service import active_artifact_paths, prepare_live_prediction_input, predict


def main() -> None:
    processes = repository.list_processes(DATABASE_PATH, status="open", limit=10_000)
    active_models = repository.get_active_models(DATABASE_PATH)
    classifier_path, regressor_path, version = active_artifact_paths(active_models)
    today = date.today()
    workloads = {
        team: repository.get_current_team_workload(DATABASE_PATH, team, today.isoformat())
        for team in {process["responsible_team"] for process in processes}
    }
    results: list[tuple[int, dict]] = []
    saved = 0
    for index, process in enumerate(processes, start=1):
        live_input = prepare_live_prediction_input(
            process, prediction_date=today, current_team_workload=workloads[process["responsible_team"]]
        )
        prediction = predict(live_input, classifier_path, regressor_path, version)
        results.append((process["id"], prediction))
        if index % 250 == 0:
            saved += repository.save_predictions_batch(DATABASE_PATH, results)
            results.clear()
            print(f"{index} / {len(processes)} tahmin kaydedildi", flush=True)
    if results:
        saved += repository.save_predictions_batch(DATABASE_PATH, results)
    print(f"{saved} açık iş için tahmin kaydedildi.")


if __name__ == "__main__":
    main()
