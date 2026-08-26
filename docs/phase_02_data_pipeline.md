# Faz 2 - Sentetik Veri ve SQLite Pipeline

Bu fazda veri kaynağı tamamen sentetiktir. `scripts/generate_synthetic_data.py`, 40.000 süreç düzeyi kayıt üretir: 30.000 tamamlanmış kayıt eğitim için, 10.000 açık kayıt ise uygulama demosu için kullanılır.

## Neden süreç düzeyi CSV?

Uygulamanın tahmin girdisi tek bir işin o anki durumudur. Bu nedenle her CSV satırı bir süreç kaydını temsil eder; olay günlüğü (event log) değil. `as_of_date`, satırdaki verinin hangi tahmin anına ait olduğunu belirtir.

## Çalıştırma

Proje kökünde, aktif `.venv` ile:

```powershell
python scripts/generate_synthetic_data.py --rows 40000
python scripts/init_db.py
python scripts/import_process_data.py
pytest
```

Üretilen dosyalar:

- `data/raw/synthetic_process_records.csv`: ham sentetik kaynak
- `data/process_risk.db`: SQLite veritabanı
- `reports/generated/data_quality_report.json`: kalite/aktarım özeti

Bu dosyalar `.gitignore` ile yerel kalacak şekilde ayarlanmıştır.

## Güvenlik ve leakage

`completed_at`, `is_delayed` ve `total_duration_days` import aşamasında yalnızca eğitim hedefi olarak üretilir. Faz 3'te kurulacak feature pipeline bu üç alanı model girdisi olarak kabul etmeyecektir.
