import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_synthetic_data import generate_dataset
from app.core.validation import validate_process_dataframe


def test_generated_dataset_has_requested_size_and_valid_rows():
    data = generate_dataset(record_count=200, seed=7)
    result = validate_process_dataframe(data)
    assert len(data) == 200
    assert len(result.valid_data) == 200
    assert data["external_id"].is_unique
    assert set(data["status"]) == {"open", "completed"}


def test_completed_records_can_produce_delay_label():
    data = generate_dataset(record_count=1_000, seed=11)
    completed = data.loc[data["status"].eq("completed")].copy()
    completed["completed_at"] = pd.to_datetime(completed["completed_at"])
    completed["deadline"] = pd.to_datetime(completed["deadline"])
    assert (completed["completed_at"] > completed["deadline"]).any()
