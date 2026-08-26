# AI Destekli İş Süreci Tahmin ve Gecikme Risk Sistemi

Yerel ortamda çalışacak, geçmiş süreçlerden gecikme riski ve tamamlanma süresi tahmin eden açıklanabilir karar destek sistemi.

## Durum

Çalışan yerel full stack uygulama: veri içe aktarma, eğitim, tahmin, açıklama, what-if, model izleme ve geri bildirim ekranları hazırdır. Toplu tahmin arka planda izlenebilir ve durdurulabilir; API girdileri ve model kalite eşiği testlerle korunur.

Bu aşamada gerçek veri kullanılmaz. Tamamen sentetik veri üretilir, kalite kurallarıyla doğrulanır ve SQLite'a tekrarlanabilir biçimde aktarılır.

## Yerel kurulum (Windows / VS Code terminali)

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

> Bu çalışma alanının klasör adında `İ` karakteri olduğu için Windows, `.venv` başlatıcısında yol kodlama hatası verebilir. Bu durumda sanal ortamı ASCII karakterli komşu bir klasörde oluşturun ve VS Code'da bu yorumlayıcıyı seçin:

```powershell
python -m venv C:\venvs\istrisk_venv
C:\venvs\istrisk_venv\Scripts\Activate.ps1
cd "<proje-klasorunun-tam-yolu>"
pip install -r requirements.txt
```

PowerShell, script çalıştırmayı engellerse yalnızca açık terminal oturumu için şunu çalıştırabilirsin:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Gizlilik

- Gerçek CSV/Excel, SQLite veritabanı, eğitim çıktıları ve modeller sürüm kontrolüne eklenmez.
- `completed_at`, gerçek toplam süre ve gerçekleşmiş gecikme sonucu tahmin özellikleri değildir; yalnız hedef etiketi/eğitim değerlendirmesi için kullanılır.
- Model çıktısı erken uyarıdır; kesin operasyonel karar değildir.

## Faz 1 çıktıları

- [Veri sözlüğü](docs/phase_01_data_dictionary.md)
- [Veri kalitesi ve leakage planı](docs/phase_01_quality_and_leakage_plan.md)
- [Faz 2 pipeline kılavuzu](docs/phase_02_data_pipeline.md)
- [Faz 3 baseline model kılavuzu](docs/phase_03_baseline_models.md)
- [Faz 4 model karşılaştırma kılavuzu](docs/phase_04_advanced_models.md)
- [Faz 5 backend API kılavuzu](docs/phase_05_backend_api.md)
- [Final teknik rapor](docs/final_technical_report.md)
- [Kısa kullanım kılavuzu](docs/user_guide.md)

## Yerel çalıştırma sırası

```powershell
python scripts/generate_synthetic_data.py
python scripts/import_process_data.py
python scripts/train_advanced_models.py
python scripts/evaluate_models.py
python scripts/score_open_processes.py
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Tarayıcı: `http://127.0.0.1:8001/`  
API dokümantasyonu: `http://127.0.0.1:8001/docs`

## Günlük açık iş değerlendirmesi

Dashboard'daki **Açık işleri değerlendir** düğmesi, açık kayıtlar için bugünün tahminini arka planda üretir ve tahmin geçmişine kaydeder. Kaynak süreç verisini değiştirmez. Çubukta işlenen kayıt sayısı görünür; gerekirse **İşlemi durdur** ile sonraki kayıtların üretilmesi kesilir. O ana kadar oluşmuş tahminler korunur.

## Model kartı

[advanced-v1 model kartı](reports/model_card_advanced_v1.md), modelin amaçlarını, eğitim ayrımını, metriklerini, eşiklerini, veri sızıntısı önlemlerini ve sınırlamalarını açıklar.
