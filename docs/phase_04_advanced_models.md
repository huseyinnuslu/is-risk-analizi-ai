# Faz 4 - Gelişmiş Modeller ve Açıklanabilirlik

Bu fazda Logistic/Linear Regression modelleri, Random Forest ve HistGradientBoosting adaylarıyla karşılaştırılır.

## Seçim kuralları

- Gecikme sınıflandırması: validation ROC-AUC en yüksek model seçilir; eşitlikte recall kullanılır.
- Kalan süre regresyonu: validation MAE en düşük model seçilir; eşitlikte RMSE kullanılır.

Test verisi model seçimi için kullanılmaz; yalnız seçilen modelin son, tarafsız raporu için bir kez kullanılır.

## Açıklama yöntemi

Permutation importance, bir feature'ın değerlerini karıştırınca model başarısındaki düşüşü ölçer. Böylece modelin hangi alanlara genel olarak daha çok dayandığını, algoritmadan bağımsız şekilde görürüz.

## Çalıştırma

```powershell
python scripts/train_advanced_models.py
```

Çıktılar `ml/artifacts/` altında joblib modelleri, `reports/generated/advanced_model_report.json` içinde kıyaslama/importance raporu ve SQLite `model_registry` tablosunda aktif model kaydıdır.
