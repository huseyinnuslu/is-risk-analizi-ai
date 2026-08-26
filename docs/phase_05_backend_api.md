# Faz 5 - FastAPI Backend

Bu faz, eğitimde üretilen joblib modellerini SQLite'daki aktif model kaydı üzerinden çağırır. API yalnızca yerelde çalışır; hiçbir süreç verisi dış servise gönderilmez.

## Başlatma

```powershell
uvicorn app.main:app --reload
```

Tarayıcıdan API dokümantasyonu: `http://127.0.0.1:8000/docs`

## Temel uçlar

| Metot | Uç | Amaç |
|---|---|---|
| GET | `/health` | Yerel uygulama durumu |
| GET | `/api/dashboard` | Dashboard özeti |
| GET | `/api/processes` | Açık/tamamlanmış süreç listesi |
| GET | `/api/processes/{id}` | Süreç ve tahmin geçmişi |
| POST | `/api/predictions/{id}/run` | Tek açık süreç için tahmin |
| POST | `/api/predictions/batch` | Toplu tahmin |
| POST | `/api/predictions/batch/start` | Arka plan toplu tahmin işi başlatır (202) |
| GET | `/api/predictions/batch/{job_id}/status` | Toplu işin ilerleme ve durumunu döndürür |
| POST | `/api/predictions/batch/{job_id}/cancel` | Devam eden toplu işi durdurma isteği gönderir |
| POST | `/api/simulate` | Kaydetmeden what-if simülasyonu |
| GET | `/api/models/active` | Aktif model ve metrikler |
| POST | `/api/feedback` | Kullanıcı geri bildirimi |

## Tahmin açıklaması

Tek kayıt açıklaması, seçilen model üzerinde karşı-senaryo duyarlılığı ile üretilir. Örneğin mevcut eksik belge sayısı sıfıra indirildiğinde model olasılığı düşüyorsa, bu alan risk faktörü olarak listelenir. Bu açıklama nedensel karar değildir; model davranışının yerel açıklamasıdır.

## Dinamik tahmin tarihi

Açık iş için tahmin çalıştığında `as_of_date` o günün tarihiyle geçici olarak güncellenir. Böylece `days_since_created` ve `deadline_remaining_days` güncel hesaplanır; ayrıca ekipteki açık iş sayısından türetilen 0–100 ekip kapasite kullanımı yeniden hesaplanır. Kaynak süreç kaydı simülasyon veya tahmin sırasında değiştirilmez.

## Toplu tahmin iş akışı

Dashboard, `POST /api/predictions/batch/start` ile uzun süren işi HTTP yanıtından ayırır. Arayüz durum ucunu düzenli olarak sorgular; `queued`, `running`, `completed`, `cancelled` veya `failed` durumunu ve işlenen kayıt sayısını gösterir. Durdurma isteği, çalışmakta olan kaydı geri almaz; yalnızca sonraki tahminlerin üretilmesini engeller. Kaynak `process_records` verisi bu akışta değişmez, yalnızca `predictions` tablosuna yeni tahmin anları yazılır.

## Girdi ve yerel yol güvenliği

Karşı-senaryo girdi şeması kapalıdır: yalnızca `missing_document_count` (0–50), `revision_count` (0–50) ve `days_in_current_stage` (0–3650) kabul edilir. Bilinmeyen alanlar ve geçersiz aralıklar `422` ile reddedilir. Sağlık ucu, makinedeki veritabanının mutlak yolunu döndürmez; uygulamanın SQLite depolamayı yerelde kullandığını bildirir.
