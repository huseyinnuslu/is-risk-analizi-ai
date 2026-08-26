# Faz 1 - Veri Sözlüğü

## Amaç ve kayıt birimi

Her satır, belirli bir **tahmin anındaki** tek bir iş sürecini temsil eder. Eğitim verisindeki tamamlanmış işler için bu an, `as_of_date` alanıyla açıkça belirtilir. Açık işler için `as_of_date`, tahminin çalıştırıldığı gün olur.

Bu zaman sabitlemesi kritiktir: model, yalnızca o tarihte bilinebilecek bilgileri kullanır.

## Kaynak alanlar

| Alan | Tip | Zorunlu | Tahmin anında bilinir mi? | Kullanım |
|---|---|---:|---:|---|
| `external_id` | metin | Evet | Evet | Benzersiz kayıt kimliği; modele girmez. |
| `process_type` | kategorik | Evet | Evet | Süreç türü; özellik adayı. |
| `current_stage` | kategorik | Evet | Evet | Tahmin anındaki aşama; özellik adayı. |
| `responsible_team` | kategorik | Evet | Evet | Ekip seviyesi iş yükü analizi için; kişi adı içermez. |
| `priority` | kategorik | Evet | Evet | Düşük/Orta/Yüksek; özellik adayı. |
| `created_at` | tarih | Evet | Evet | Süreç yaşı türetmek için kullanılır. |
| `as_of_date` | tarih | Evet | Evet | Özelliklerin hangi anda gözlemlendiğini sabitler; doğrudan modele girmez. |
| `deadline` | tarih | Koşullu | Evet | Son tarih kalan günü üretmek için kullanılır. |
| `revision_count` | tamsayı | Evet | Evet | Tahmin anına kadarki revizyon sayısı; özellik adayı. |
| `missing_document_count` | tamsayı | Evet | Evet | Tahmin anındaki eksik belge sayısı; özellik adayı. |
| `stage_change_count` | tamsayı | Evet | Evet | Tahmin anına kadarki aşama değişimi; özellik adayı. |
| `days_in_current_stage` | sayı | Evet | Evet | Mevcut aşamada geçen gün; özellik adayı. |
| `historical_avg_stage_days` | sayı | Evet | Evet | Süreç türü/aşama için önceden bilinen normal süre; özellik adayı. |
| `team_workload` | yüzde tamsayı (0–100) | Evet | Evet | Tahmin tarihinde ekipteki açık iş sayısının yerel kapasite sınırına oranı; ekip kapasite kullanımı özelliği. |
| `completed_at` | tarih | Tamamlanmış kayıtta | **Hayır** | Sadece hedef üretimi ve değerlendirme. |

## Türetilmiş özellikler

| Özellik | Formül | Leakage notu |
|---|---|---|
| `days_since_created` | `as_of_date - created_at` | Tahmin tarihinde hesaplanır. |
| `deadline_remaining_days` | `deadline - as_of_date` | Son tarih yoksa eksiklik göstergesiyle birlikte işlenir. |
| `stage_delay_ratio` | `days_in_current_stage / historical_avg_stage_days` | Referans ortalama yalnız eğitim bölümünden/fold içinden hesaplanır. |
| `revision_intensity` | `revision_count / max(days_since_created, 1)` | Gelecek revizyonları içermez. |
| `missing_doc_flag` | `missing_document_count > 0` | Tahmin anındaki sayımdan üretilir. |
| `stage_change_rate` | `stage_change_count / max(days_since_created, 1)` | Gelecek aşama hareketleri içermez. |
| `team_workload` | `açık iş sayısı / TEAM_CAPACITY × 100` | Aynı günün görünür açık kayıtlarından hesaplanır; 0–100 aralığında sınırlandırılır. |

`historical_avg_stage_days` kaynak veride tutulmak yerine eğitim pipeline'ında üretilecektir. Böylece test satırları veya gelecekteki kayıtlar ortalamaya sızmaz.

## Hedef değişkenler

### Sınıflandırma: `is_delayed`

Tamamlanmış bir eğitim kaydı için tanım:

```text
is_delayed = 1, completed_at > deadline ise
is_delayed = 0, completed_at <= deadline ise
```

`deadline` veya `completed_at` yoksa etiket üretilemez; bu satır sınıflandırma eğitimi dışında bırakılır ve kalite raporunda sayılır.

### Regresyon: `remaining_days`

Tamamlanmış eğitim kayıtlarında:

```text
remaining_days = completed_at - as_of_date
```

Eğitim için `remaining_days` negatif olamaz. Açık işte model bu değeri tahmin eder; `completed_at` bilinmediği için girdide asla kullanılmaz.

## İlk özellik listesi

`process_type`, `current_stage`, `responsible_team`, `priority`, `days_since_created`, `deadline_remaining_days`, `revision_count`, `missing_document_count`, `stage_change_count`, `days_in_current_stage`, `historical_avg_stage_days`, `stage_delay_ratio`, `revision_intensity`, `missing_doc_flag`, `stage_change_rate`, `team_workload`.

Kişi adı, firma adı veya serbest metin ilk sürümde kullanılmayacaktır. Bu seçim hem gizliliği hem de açıklanabilirliği iyileştirir.
