"""Yerel demo ve eğitim için açıklanabilir sentetik süreç verisi üretir."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import TEAM_CAPACITY


PROCESS_TYPES = {
    "Ödeme Başvurusu": 22,
    "Belge İnceleme": 16,
    "Sözleşme Onayı": 28,
    "Teşvik Başvurusu": 35,
    "Tedarik Talebi": 20,
}
STAGES = ["Ön Kontrol", "Belge İnceleme", "Uzman İnceleme", "Onay", "Tamamlama"]
TEAMS = ["Operasyon", "Finans", "Hukuk", "Teşvik"]
PRIORITIES = ["Düşük", "Orta", "Yüksek"]
STAGE_NORMS = {
    "Ön Kontrol": 3.0,
    "Belge İnceleme": 5.0,
    "Uzman İnceleme": 8.0,
    "Onay": 4.0,
    "Tamamlama": 2.0,
}


def generate_dataset(record_count: int, seed: int = 42) -> pd.DataFrame:
    """Tahmin anında bilinen alanlar ile sonuç alanlarını ayrı üreten veri seti.

    `completed_at`, önce gecikme mekanizmasının sonucu olarak oluşturulur. Bu
    alan daha sonra modele girmeyecek; yalnız hedef etiketi üretmek içindir.
    """

    if record_count < 100:
        raise ValueError("Anlamlı dağılım için en az 100 kayıt üretin.")

    rng = np.random.default_rng(seed)
    reference_date = date(2026, 8, 7)
    completed_count = int(record_count * 0.75)
    rows: list[dict] = []

    for index in range(record_count):
        process_type = rng.choice(list(PROCESS_TYPES))
        team = rng.choice(TEAMS, p=[0.36, 0.23, 0.19, 0.22])
        priority = rng.choice(PRIORITIES, p=[0.22, 0.54, 0.24])
        stage = rng.choice(STAGES, p=[0.18, 0.28, 0.27, 0.17, 0.10])
        base_duration = PROCESS_TYPES[process_type]
        is_completed = index < completed_count

        if is_completed:
            created_at = reference_date - timedelta(days=int(rng.integers(70, 730)))
            process_age = int(rng.integers(3, max(5, base_duration)))
            as_of_date = created_at + timedelta(days=process_age)
        else:
            # Açık işler, demo tarihinde geçmişe yığılmasın diye ayrı planlanır.
            # %15'i bilinçli olarak gecikmiş, %85'i henüz son tarihine ulaşmamıştır.
            process_age = int(rng.integers(12, 91))
            created_at = reference_date - timedelta(days=process_age)
            as_of_date = reference_date

        revision_count = int(rng.poisson(1.8))
        missing_document_count = int(rng.binomial(4, 0.20))
        stage_change_count = max(1, int(rng.poisson(3.0)))
        historical_avg_stage_days = round(
            max(1.0, STAGE_NORMS[stage] * (base_duration / 22) * rng.normal(1.0, 0.08)), 1
        )
        days_in_current_stage = min(
            process_age,
            max(1, int(rng.gamma(shape=2.0, scale=historical_avg_stage_days / 2))),
        )

        planned_days = int(np.clip(rng.normal(base_duration, 4), 8, 70))
        if is_completed:
            deadline = created_at + timedelta(days=planned_days)
        elif rng.random() < 0.15:
            deadline = reference_date - timedelta(days=int(rng.integers(1, 11)))
        else:
            deadline = reference_date + timedelta(days=int(rng.integers(1, 46)))

        # Gecikme olasılığı neden-sonuç mantığı taşır; tek bir alan belirleyici değildir.
        risk_logit = -2.0
        risk_logit += 0.42 * revision_count
        risk_logit += 0.72 * missing_document_count
        risk_logit += 0.08 * days_in_current_stage
        risk_logit += 0.16 * max(stage_change_count - 3, 0)
        risk_logit += 0.45 if stage == "Uzman İnceleme" else 0.0
        risk_logit += 0.28 if process_type == "Teşvik Başvurusu" else 0.0
        risk_logit -= 0.32 if priority == "Yüksek" else 0.0
        delay_probability = 1 / (1 + np.exp(-risk_logit))
        delayed = bool(rng.random() < delay_probability)

        if is_completed:
            if delayed:
                completion_offset = planned_days + int(rng.integers(1, 24))
            else:
                completion_offset = max(process_age + 1, planned_days - int(rng.integers(0, 8)))
            completed_at = created_at + timedelta(days=completion_offset)
            # Tahmin anı, tamamlanmadan öncedir; böylece remaining_days anlamlıdır.
            if as_of_date >= completed_at:
                as_of_date = completed_at - timedelta(days=1)
        else:
            completed_at = None

        rows.append(
            {
                "external_id": f"SYN-{index + 1:06d}",
                "process_type": process_type,
                "current_stage": stage,
                "responsible_team": team,
                "priority": priority,
                "created_at": created_at.isoformat(),
                "as_of_date": as_of_date.isoformat(),
                "deadline": deadline.isoformat(),
                "revision_count": revision_count,
                "missing_document_count": missing_document_count,
                "stage_change_count": stage_change_count,
                "days_in_current_stage": days_in_current_stage,
                # Bu alan süreç tamamlandıktan sonra değil, tahmin anında
                # bilinen operasyonel aşama normundan gelir.
                "historical_avg_stage_days": historical_avg_stage_days,
                "status": "completed" if is_completed else "open",
                "completed_at": completed_at.isoformat() if completed_at else None,
            }
        )

    data = pd.DataFrame(rows)
    return _add_team_workload(data, reference_date)


def _add_team_workload(data: pd.DataFrame, reference_date: date) -> pd.DataFrame:
    """Her tahmin tarihinde ekipteki eşzamanlı açık iş sayısını hesaplar."""

    result = data.copy()
    start = pd.to_datetime(result["created_at"]).dt.normalize()
    final_day = pd.Timestamp(reference_date) + pd.Timedelta(days=1)
    end = pd.to_datetime(result["completed_at"], errors="coerce").fillna(final_day).dt.normalize()
    end = end.where(end <= final_day, final_day)
    all_days = pd.date_range(start.min(), final_day, freq="D")
    day_index = pd.Series(range(len(all_days)), index=all_days)
    workload = pd.Series(0, index=result.index, dtype="int64")

    for team, indexes in result.groupby("responsible_team").groups.items():
        team_indexes = list(indexes)
        changes = np.zeros(len(all_days) + 1, dtype=int)
        start_positions = day_index.loc[start.loc[team_indexes]].to_numpy()
        end_positions = day_index.loc[end.loc[team_indexes]].to_numpy()
        np.add.at(changes, start_positions, 1)
        np.add.at(changes, end_positions, -1)
        active_count = np.cumsum(changes[:-1])
        as_of_positions = day_index.loc[pd.to_datetime(result.loc[team_indexes, "as_of_date"]).dt.normalize()].to_numpy()
        workload.loc[team_indexes] = active_count[as_of_positions] - 1

    result["team_workload"] = (
        (workload.clip(lower=0) / TEAM_CAPACITY * 100).round().clip(upper=100).astype(int)
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Sentetik süreç verisi üretir.")
    parser.add_argument("--rows", type=int, default=40_000, help="Üretilecek kayıt sayısı")
    parser.add_argument("--seed", type=int, default=42, help="Tekrarlanabilirlik tohumu")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "synthetic_process_records.csv",
        help="CSV çıktı yolu",
    )
    args = parser.parse_args()

    data = generate_dataset(args.rows, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"{len(data):,} sentetik kayıt oluşturuldu: {args.output}")
    print(data["status"].value_counts().to_string())


if __name__ == "__main__":
    main()
