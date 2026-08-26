from datetime import date

from app.services.prediction_service import prepare_live_prediction_input


def test_live_input_uses_prediction_date_without_mutating_source_record():
    source = {
        "as_of_date": "2026-08-07",
        "days_in_current_stage": 5,
        "team_workload": 10,
    }
    live = prepare_live_prediction_input(source, date(2026, 8, 12), current_team_workload=13)
    assert source["as_of_date"] == "2026-08-07"
    assert live["as_of_date"] == "2026-08-12"
    assert live["days_in_current_stage"] == 10
    assert live["team_workload"] == 13
