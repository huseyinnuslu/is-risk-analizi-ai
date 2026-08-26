# Model Kartı — advanced-v1

## 1. Amaç ve kullanım sınırı

Bu model, devam eden bir işin gecikme olasılığını ve tahmini kalan süresini üretir. Çıktı yalnızca erken uyarı ve önceliklendirme desteğidir; otomatik karar, çalışan performans değerlendirmesi, hukuki veya İK kararı olarak kullanılamaz.

## 2. Eğitim verisi

- Kaynak: Yerel olarak üretilmiş sentetik süreç kayıtları
- Tamamlanmış eğitim kaydı: 30.000
- Kronolojik ayrım: eğitim 18.000, doğrulama 6.000, test 6.000
- Ayrım anahtarı: `as_of_date`; geleceğin kaydı geçmişe sızdırılmaz.

Bu metrikler gerçek kurum performansını temsil etmez. Gerçek veri geldiğinde veri kalitesi, sınıf dağılımı, eşikler ve segment performansı yeniden değerlendirilmelidir.

## 3. Hedefler

- Sınıflandırma hedefi: `is_delayed` — iş son tarihten sonra tamamlandıysa `1`
- Regresyon hedefi: `remaining_days` — tahmin anından tamamlanmaya kalan gün

## 4. Kullanılan özellikler

Süreç türü, mevcut aşama, sorumlu ekip, öncelik; revizyon, eksik belge, aşama değişimi, aşamada geçen gün, tarihsel aşama ortalaması, ekip kapasite kullanımı ve bu alanlardan türetilen yaş/süre oranları kullanılır.

`completed_at`, `is_delayed`, `total_duration_days` ve `remaining_days` feature değildir. Bunlar yalnız hedef üretimi ve değerlendirme için kullanılır.

## 5. Seçilen modeller ve seçim yöntemi

| Problem | Adaylar | Seçilen model | Seçim kuralı |
|---|---|---|---|
| Gecikme sınıflandırması | Logistic Regression, Random Forest, HistGradientBoosting | HistGradientBoosting | En yüksek doğrulama ROC-AUC, eşitlikte recall |
| Kalan süre regresyonu | Linear Regression, Random Forest, HistGradientBoosting | Linear Regression | En düşük doğrulama MAE, eşitlikte RMSE |

HistGradientBoosting sınıflandırıcı: `learning_rate=0.08`, `max_iter=220`, `max_leaf_nodes=20`, `l2_regularization=1.0`, `random_state=42`.

## 6. Test metrikleri

| Sınıflandırma | Değer |
|---|---:|
| Accuracy | 0,7093 |
| Recall | 0,6814 |
| Precision | 0,7534 |
| F1 | 0,7156 |
| ROC-AUC | 0,7806 |
| PR-AUC | 0,8249 |

Test confusion matrix: `[[2062, 718], [1026, 2194]]`. Satırlar gerçek sonucu; sütunlar model tahminini ifade eder.

| Regresyon | Değer |
|---|---:|
| MAE | 6,722 gün |
| RMSE | 8,1737 gün |
| MedAE | 5,9551 gün |
| R² | 0,4907 |

## 7. Risk eşiği

Risk puanı sınıflandırıcının gecikme olasılığı × 100 değeridir. Başlangıç operasyon eşiği: 0–39 düşük, 40–69 orta, 70–100 yüksek. Bu eşikler başlangıç önerisidir; gerçek veride yanlış alarm maliyeti ve kaçırılan gecikme maliyetiyle yeniden ayarlanmalıdır.

## 8. Açıklanabilirlik

Küresel açıklama için permutation importance; tek iş ekranında ise alanlar tek tek iyileştirilerek karşı-senaryo duyarlılığı kullanılır. Bu açıklamalar model davranışını gösterir, nedensel kanıt değildir.

## 9. Sınırlamalar ve izleme

- Sentetik verideki ilişkiler gerçek operasyonu temsil etmeyebilir.
- Son tarihi geçmiş işler erken uyarı değil, kesin takvim ihlalidir.
- Kullanıcı geri bildirimi yerel SQLite içinde saklanır; model otomatik güncellenmez.
- Gerçek sonuçlar biriktikçe precision, recall ve MAE yeniden ölçülmelidir.

## 10. Sürüm bilgisi

- Sürüm: `advanced-v1`
- Eğitim zamanı: 2026-08-07 UTC
- Sınıflandırma artefact: `ml/artifacts/delay_classifier_advanced_v1.joblib`
- Regresyon artefact: `ml/artifacts/duration_regressor_advanced_v1.joblib`
- Ayrıntılı rapor: `reports/generated/advanced_model_report.json` (yalnız yerel)
