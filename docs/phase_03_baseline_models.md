# Faz 3 - Baseline Modeller

Bu faz, gelişmiş modellere geçmeden önce ölçülebilir bir başlangıç noktası oluşturur.

## Modeller

| Hedef | Basit baseline | İlk model |
|---|---|---|
| Gecikme riski | Sınıf önceliği (`DummyClassifier`) | Logistic Regression |
| Kalan gün | Eğitim medyanı (`DummyRegressor`) | Linear Regression |

Kayıtlar `as_of_date` tarihine göre %60 eğitim, %20 doğrulama ve %20 test olarak ayrılır. Böylece model geçmişle eğitilir ve geleceğe ait kayıtlarla ölçülür.

## Leakage önlemi

`completed_at`, `is_delayed`, `total_duration_days` ve regresyon hedefi `remaining_days`, feature tablosuna alınmaz. Tarih tabanlı özellikler yalnız tahmin anı olan `as_of_date` ile hesaplanır.

## Çalıştırma

```powershell
python scripts/train_models.py
```

Çıktılar:

- `ml/artifacts/delay_classifier_baseline_v1.joblib`
- `ml/artifacts/duration_regressor_baseline_v1.joblib`
- `reports/generated/baseline_metrics.json`
- `model_registry` SQLite tablosundaki aktif model kayıtları
