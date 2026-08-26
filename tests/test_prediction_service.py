from app.services.prediction_service import risk_level


def test_risk_level_thresholds():
    assert risk_level(0) == "Düşük"
    assert risk_level(39) == "Düşük"
    assert risk_level(40) == "Orta"
    assert risk_level(69) == "Orta"
    assert risk_level(70) == "Yüksek"
