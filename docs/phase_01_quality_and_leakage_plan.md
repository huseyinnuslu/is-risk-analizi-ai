# Faz 1 - Veri Kalitesi ve Veri Sızıntısı Planı

## Veri kaynağı kararı

Senior tarafından veri sağlanmadığı için Faz 2'de bu sözlüğe uygun, tamamen sentetik ve tekrarlanabilir bir süreç veri seti üretilecektir. Sentetik kayıtlar gerçek kişi, firma veya kurum süreci içermeyecektir.

İleride kamuya açık bir veri seti değerlendirilirse indirilen dosya yalnız `data/raw/` altında yerelde tutulur; lisans, alan eşlemesi ve kişisel veri riski incelenmeden projeye dahil edilmez.

## Veri kalite kontrolleri

| Kontrol | Kural | Hatalıysa davranış |
|---|---|---|
| Şema | Zorunlu kolonlar mevcut olmalı. | İçe aktarma durur, eksik kolonlar raporlanır. |
| Kimlik | `external_id` boş veya tekrar edemez. | Tekrarlar raporlanır; otomatik birleştirilmez. |
| Tarih | `created_at <= as_of_date`; tamamlanmışta `completed_at >= created_at`. | Kayıt reddedilir/kalite raporuna yazılır. |
| Son tarih | `deadline` varsa `deadline >= created_at`. | Kayıt işaretlenir; hedef üretiminden dışlanabilir. |
| Sayımlar | Revizyon, eksik belge ve aşama değişimi negatif olamaz. | Kayıt reddedilir. |
| Süreler | `days_in_current_stage >= 0`; eğitim hedefi `remaining_days >= 0`. | Kayıt reddedilir. |
| Kategoriler | Süreç türü, aşama, ekip ve öncelik izinli değerlerden olmalı. | Bilinmeyen değer raporlanır; kontrollü `Diğer` dönüşümü uygulanabilir. |
| Aykırı değer | Süre ve sayımlarda IQR/iş kuralı kontrolü yapılır. | Silinmez; raporda işaretlenir ve incelenir. |

Uygulamadaki IQR kontrolü `revision_count`, `missing_document_count`, `stage_change_count`, `days_in_current_stage`, `historical_avg_stage_days` ve 0–100 aralığındaki `team_workload` (ekip kapasite kullanımı) için aykırı kayıt sayısını verir. Aykırı değer otomatik hata değildir; import devam eder ve kayıt kalite raporunda görünür.

## Veri sızıntısı kontrol listesi

Aşağıdaki alanlar hiçbir eğitim/prediction feature setine eklenmez:

| Yasak alan | Neden |
|---|---|
| `completed_at` | Tahmin sırasında gelecekte gerçekleşecek bilgidir. |
| `is_delayed` | Sınıflandırma hedefidir. |
| `total_duration_days` | Sonuçtan türetilir; hedefi doğrudan ele verir. |
| Gerçek tamamlanma sonrasındaki not, revizyon veya aşama değişimi | Tahmin zamanından sonradır. |
| Test/future veriyle hesaplanan grup ortalamaları | Eğitim-test bilgisini karıştırır. |

Ek önlemler:

1. Eğitim/validasyon/test bölünmesi `as_of_date` sırasına göre kronolojik yapılır.
2. Ölçekleme, eksik değer doldurma, one-hot encoding ve grup ortalamaları yalnız eğitim kısmına `fit` edilir; doğrulama/testte yalnız `transform` uygulanır.
3. Benzer iş araması yalnız geçmişte tamamlanmış ve tahmin tarihinden önceki kayıtları kullanır.
4. Açık bir iş son tarihi geçmişse arayüz bunu “mevcut durum” olarak belirtir; model olasılığı ile karıştırmaz.

## Başlangıç model ve metrik planı

| Hedef | Baseline | Sonraki karşılaştırmalar | Ana metrik |
|---|---|---|---|
| Gecikme riski | Logistic Regression | Random Forest, HistGradientBoosting | Recall, Precision, F1, PR-AUC, ROC-AUC |
| Kalan süre | Median/Linear Regression | Random Forest Regressor, Gradient Boosting | MAE, RMSE, MedAE, R² |

Risk puanı, seçilen sınıflandırıcının gecikme olasılığının `round(probability * 100)` dönüşümüdür. Başlangıç seviyeleri: 0-39 Düşük, 40-69 Orta, 70-100 Yüksek. Faz 3'te eşikler doğrulama verisi üzerinde gerekçelendirilir.

## Faz 1 kabul ölçütleri

- Veri alanları, tipleri ve tahmin anında erişilebilirlikleri belgelendi.
- Gecikme ve kalan süre hedefleri açık formülle tanımlandı.
- Yasak feature'lar ve leakage önlemleri yazılı hale getirildi.
- Faz 2 sentetik veri üretimi için şema ve kalite kontrolleri hazırlandı.
