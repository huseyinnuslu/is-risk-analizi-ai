# Final Teknik Rapor

## Proje özeti

AI Destekli İş Süreci Tahmin ve Gecikme Risk Sistemi; geçmiş süreç kayıtlarından açık işlerin gecikme olasılığını ve tahmini kalan süresini hesaplayan, açıklanabilir ve tamamen yerel çalışan bir karar destek uygulamasıdır.

## Mimari

`CSV/XLSX → doğrulama → SQLite → feature pipeline → scikit-learn modelleri → FastAPI → Jinja2 arayüz`

- Backend: Python, FastAPI
- Veri katmanı: SQLite
- Veri işleme: pandas, NumPy
- Makine öğrenmesi: scikit-learn, joblib
- Arayüz: HTML, CSS, JavaScript, Jinja2
- Test: pytest

## Veri ve gizlilik

Uygulama yerel bilgisayarda çalışır. Gerçek CSV/Excel, SQLite veritabanı, model dosyaları ve loglar harici ortama gönderilmez. Sunum için kullanılan kayıtlar sentetiktir.

Tahmin anında bilinmeyen `completed_at`, `is_delayed`, `total_duration_days` ve `remaining_days` model feature'ı değildir. Bu alanlar yalnız hedef üretimi ve değerlendirme için kullanılır.

## Modelleme

Sınıflandırma hedefi `is_delayed`; regresyon hedefi `remaining_days` alanıdır. Bölme `as_of_date` ile kronolojik olarak yapılır: %60 eğitim, %20 doğrulama, %20 test.

Sınıflandırmada Logistic Regression, Random Forest ve HistGradientBoosting; regresyonda Linear Regression, Random Forest ve HistGradientBoosting karşılaştırılmıştır. Seçilen sınıflandırıcı HistGradientBoosting, seçilen regresyon modeli Linear Regression'dır.

Test sonuçları:

| Model | Temel metrik |
|---|---:|
| Gecikme sınıflandırması | ROC-AUC 0,7806 |
| Gecikme sınıflandırması | Recall 0,6814 |
| Kalan süre regresyonu | MAE 6,722 gün |
| Kalan süre regresyonu | R² 0,4907 |

## Açıklanabilirlik

Global değerlendirmede permutation importance kullanılır. İş detayında eksik belge, revizyon ve aşamada geçen gün gibi alanlar tek tek iyileştirilerek karşı-senaryo duyarlılığı gösterilir. Açıklamalar nedensel kanıt değildir; model davranışını açıklar.

## Uygulama fonksiyonları

- CSV/XLSX yerel içe aktarma ve kalite raporu
- Açık işleri takvim durumu ve model riskine göre önceliklendirme
- Süreç türü, aşama, ekip, model riski ve takvim filtresi
- Tek iş tahmini, tahmini bitiş, benzer tamamlanmış işler ve tahmin geçmişi
- What-if senaryosu
- Model sürümü, metrikler, confusion matrix ve saha performansı izleme
- Tahmin geri bildirimi
- Yerel, hassas veri içermeyen döngülü uygulama logları

## Bilinen sınırlamalar

- Mevcut eğitim verisi sentetiktir; gerçek kurum verisi performansını temsil etmez.
- Tahmin, kesin karar değildir; insan incelemesi gerekir.
- Son tarihi geçmiş iş, erken uyarı değil kesin takvim ihlalidir.
- Gerçek sonuç sayısı azsa saha metriği ile model sürümü değiştirilmez.

## Doğrulama

Test paketi 21 otomatik test içerir. Veri doğrulama, leakage önlemi, özellik üretimi, model ayrımı, API hata durumları, tahmin tekrarının engellenmesi ve arayüz endpointleri kontrol edilir.

Aktif modelleri eğitimi değiştirmeden son kronolojik test diliminde tekrar ölçmek için `python scripts/evaluate_models.py` çalıştırılır. Çıktı yalnız yerel `reports/generated/active_model_evaluation.json` dosyasına yazılır.
