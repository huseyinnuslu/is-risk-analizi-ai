"""Yerel karar destek API uçları."""

from __future__ import annotations

import io
import json
import logging
from datetime import date
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.core.config import DATABASE_PATH, REPORT_DIR
from app.models.schemas import BatchPredictionRequest, FeedbackRequest, SimulationRequest
from app.repositories import process_repository as repository
from app.services.prediction_service import (
    SIMULATABLE_FIELDS,
    active_artifact_paths,
    prepare_live_prediction_input,
    predict,
    recommended_actions,
)
from app.services.import_service import import_dataframe
from app.services.drift_service import drift_report
from app.services.system_health_service import check_and_record
from app.repositories import system_health_repository


router = APIRouter(prefix="/api", tags=["process-risk"])
logger = logging.getLogger("istrisk")
BATCH_JOBS: dict[str, dict] = {}
ACTION_REQUIRED_FIELDS = {
    "as_of_date", "deadline", "responsible_team", "missing_document_count",
    "revision_count", "days_in_current_stage", "historical_avg_stage_days",
}


def _attach_remaining_days_uncertainty(prediction: dict, active_models: list[dict]) -> dict:
    """Eski tahmin kayıtlarını aktif modelin hata payı açıklamasıyla zenginleştirir."""

    if prediction.get("remaining_days_uncertainty") is not None:
        return prediction
    regressor = next((item for item in active_models if item["model_type"] == "regression"), None)
    mae = regressor and regressor["metrics"].get("mae")
    if mae is None or prediction.get("predicted_remaining_days") is None:
        return prediction
    remaining = float(prediction["predicted_remaining_days"])
    margin = round(float(mae), 1)
    prediction["remaining_days_uncertainty"] = {
        "lower_days": round(max(1.0, remaining - margin), 1),
        "upper_days": round(remaining + margin, 1),
        "mae_days": margin,
        "note": "Aralık, aktif süre modelinin test MAE değerinden türetilen yaklaşık hata payıdır; güven aralığı değildir.",
    }
    return prediction


def _deadline_context(process: dict, reference_date: date | None = None) -> dict:
    """Model tahmininden bağımsız, kesin takvim durumunu hesaplar."""
    today = reference_date or date.today()
    remaining_days = (date.fromisoformat(process["deadline"]) - today).days
    if remaining_days < 0:
        return {"status": "overdue", "days": abs(remaining_days), "label": "Gecikmiş"}
    if remaining_days <= 1:
        return {"status": "urgent", "days": remaining_days, "label": "Acil"}
    return {"status": "within_deadline", "days": remaining_days, "label": "Plan dahilinde"}


def _predict_for_process(process: dict, persist: bool) -> dict:
    active_models = repository.get_active_models(DATABASE_PATH)
    classifier_path, regressor_path, version = active_artifact_paths(active_models)
    if not classifier_path.exists() or not regressor_path.exists():
        raise HTTPException(status_code=503, detail="Model dosyası bulunamadı. Modeli yeniden eğitin.")
    today = date.today()
    live_input = prepare_live_prediction_input(
        process,
        prediction_date=today,
        current_team_workload=repository.get_current_team_workload(
            DATABASE_PATH, process["responsible_team"], today.isoformat()
        ),
    )
    regressor_metrics = next(item["metrics"] for item in active_models if item["model_type"] == "regression")
    prediction = predict(
        live_input, classifier_path, regressor_path, version,
        regression_mae=regressor_metrics.get("mae"),
    )
    _attach_remaining_days_uncertainty(prediction, active_models)
    prediction["prediction_as_of_date"] = live_input["as_of_date"]
    prediction["explanation"]["prediction_as_of_date"] = live_input["as_of_date"]
    prediction["deadline_context"] = _deadline_context(process)
    if persist:
        prediction["prediction_id"] = repository.save_prediction(DATABASE_PATH, process["id"], prediction)
        logger.info("prediction_saved model_version=%s", version)
    return prediction


def _run_batch_prediction_job(job_id: str, process_ids: list[int] | None, limit: int) -> None:
    """Uzun toplu skorlama işini HTTP yanıtından sonra yerelde yürütür."""
    job = BATCH_JOBS[job_id]
    try:
        if process_ids:
            processes = [repository.get_process(DATABASE_PATH, process_id) for process_id in process_ids]
            processes = [process for process in processes if process and process["status"] == "open"]
        else:
            processes = repository.list_processes(DATABASE_PATH, status="open", limit=limit)
        job.update({"status": "running", "total": len(processes), "processed": 0})
        for index, process in enumerate(processes, start=1):
            if job.get("cancel_requested"):
                job["status"] = "cancelled"
                logger.info("batch_prediction_cancelled count=%s", job["processed"])
                return
            _predict_for_process(process, persist=True)
            job["processed"] = index
        job["status"] = "completed"
        logger.info("batch_prediction_completed count=%s", job["processed"])
    except Exception as error:
        job.update({"status": "failed", "error": type(error).__name__})
        logger.exception("batch_prediction_failed error_type=%s", type(error).__name__)


@router.get("/dashboard")
def get_dashboard():
    return repository.dashboard_summary(DATABASE_PATH)


@router.get("/processes")
def get_processes(
    status: str | None = Query(default="open", pattern="^(open|completed)$"),
    risk_level: str | None = Query(default=None, pattern="^(Düşük|Orta|Yüksek)$"),
    deadline_status: str | None = Query(default=None, pattern="^(actionable|overdue|urgent|within_deadline)$"),
    process_type: str | None = None,
    current_stage: str | None = None,
    responsible_team: str | None = None,
    limit: int = Query(default=100, ge=1, le=1_000),
    offset: int = Query(default=0, ge=0),
):
    return {"items": repository.list_processes(
        DATABASE_PATH, status, risk_level, deadline_status, limit, offset,
        process_type, current_stage, responsible_team,
    )}


@router.get("/processes/export.csv")
def export_processes_csv(
    status: str = Query(default="open", pattern="^(open|completed)$"),
    risk_level: str | None = Query(default=None, pattern="^(Düşük|Orta|Yüksek)$"),
    deadline_status: str | None = Query(default=None, pattern="^(actionable|overdue|urgent|within_deadline)$"),
    process_type: str | None = None,
    current_stage: str | None = None,
    responsible_team: str | None = None,
):
    """Filtrelenmiş iş öncelik listesini yalnızca kullanıcı indirdiğinde CSV olarak üretir."""

    rows = repository.list_processes(
        DATABASE_PATH, status, risk_level, deadline_status, 10_000, 0,
        process_type, current_stage, responsible_team,
    )
    columns = {
        "external_id": "İş ID", "process_type": "Süreç türü", "current_stage": "Aşama",
        "responsible_team": "Ekip", "priority": "Öncelik", "deadline": "Son tarih",
        "predicted_completion_date": "Tahmini bitiş", "deadline_status": "Takvim durumu",
        "risk_score": "Risk puanı", "risk_level": "Model riski",
        "predicted_remaining_days": "Tahmini kalan gün",
    }
    dataframe = pd.DataFrame(rows).reindex(columns=columns.keys()).rename(columns=columns)
    content = dataframe.to_csv(index=False, encoding="utf-8-sig")
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=istrisk_is_oncelik_listesi.csv"},
    )


@router.get("/processes/{process_id}")
def get_process_detail(process_id: int):
    process = repository.get_process(DATABASE_PATH, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Süreç bulunamadı.")
    active_models = repository.get_active_models(DATABASE_PATH)
    history = repository.get_prediction_history(DATABASE_PATH, process_id)
    live_input = None
    if ACTION_REQUIRED_FIELDS.issubset(process):
        live_input = prepare_live_prediction_input(
            process,
            prediction_date=date.today(),
            current_team_workload=repository.get_current_team_workload(
                DATABASE_PATH, process["responsible_team"], date.today().isoformat()
            ),
        )
    for item in history:
        _attach_remaining_days_uncertainty(item, active_models)
        if live_input:
            item["explanation"].setdefault("recommended_actions", recommended_actions(live_input))
    return {
        "process": process,
        "prediction_history": history,
        "similar_completed_processes": repository.get_similar_completed_processes(DATABASE_PATH, process),
        "deadline_context": _deadline_context(process),
    }


@router.post("/predictions/{process_id}/run")
def run_prediction(process_id: int):
    process = repository.get_process(DATABASE_PATH, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Süreç bulunamadı.")
    if process["status"] != "open":
        raise HTTPException(status_code=400, detail="Tahmin yalnız açık süreçler için üretilebilir.")
    # Aynı iş için aynı gün ve aynı model sürümüyle yinelenen kayıtlar, tahmin
    # geçmişini gereksiz kopyalarla doldurur. Kaydedilmiş anlık görüntüyü döndürürüz.
    latest_history = repository.get_prediction_history(DATABASE_PATH, process_id)
    active_models = repository.get_active_models(DATABASE_PATH)
    _, _, active_version = active_artifact_paths(active_models)
    if latest_history:
        latest = latest_history[0]
        if (
            latest["model_version"] == active_version
            and str(latest["predicted_at"]).startswith(date.today().isoformat())
        ):
            latest["prediction_id"] = latest["id"]
            latest["deadline_context"] = _deadline_context(process)
            _attach_remaining_days_uncertainty(latest, active_models)
            if ACTION_REQUIRED_FIELDS.issubset(process):
                live_input = prepare_live_prediction_input(
                    process,
                    prediction_date=date.today(),
                    current_team_workload=repository.get_current_team_workload(
                        DATABASE_PATH, process["responsible_team"], date.today().isoformat()
                    ),
                )
                latest["explanation"].setdefault("recommended_actions", recommended_actions(live_input))
            latest["reused_existing_prediction"] = True
            logger.info("prediction_reused model_version=%s", active_version)
            return latest
    return _predict_for_process(process, persist=True)


@router.post("/predictions/batch")
def run_batch_prediction(request: BatchPredictionRequest):
    if request.process_ids:
        processes = [repository.get_process(DATABASE_PATH, process_id) for process_id in request.process_ids]
        processes = [process for process in processes if process and process["status"] == "open"]
    else:
        processes = repository.list_processes(DATABASE_PATH, status="open", limit=request.limit)
    predictions = [_predict_for_process(process, persist=True) for process in processes]
    logger.info("batch_prediction_completed count=%s", len(predictions))
    return {"predicted_count": len(predictions), "items": predictions}


@router.post("/predictions/batch/start", status_code=202)
def start_batch_prediction(request: BatchPredictionRequest, background_tasks: BackgroundTasks):
    """Toplu tahmini arka plana alır; arayüz ilerlemeyi ayrı uçtan izler."""
    job_id = uuid4().hex
    BATCH_JOBS[job_id] = {
        "status": "queued", "total": 0, "processed": 0,
        "error": None, "cancel_requested": False,
    }
    background_tasks.add_task(_run_batch_prediction_job, job_id, request.process_ids, request.limit)
    return {"job_id": job_id, **BATCH_JOBS[job_id]}


@router.get("/predictions/batch/{job_id}/status")
def get_batch_prediction_status(job_id: str):
    job = BATCH_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Toplu tahmin işi bulunamadı.")
    percent = round((job["processed"] / job["total"]) * 100, 1) if job["total"] else 0
    return {"job_id": job_id, **job, "percent": percent}


@router.post("/predictions/batch/{job_id}/cancel")
def cancel_batch_prediction(job_id: str):
    """Devam eden yerel toplu tahmin işinin yeni kayıt üretmesini durdurur."""
    job = BATCH_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Toplu tahmin işi bulunamadı.")
    if job["status"] in {"completed", "failed", "cancelled"}:
        return {"job_id": job_id, **job}
    job["cancel_requested"] = True
    return {"job_id": job_id, **job}


@router.post("/simulate")
def simulate(request: SimulationRequest):
    process = repository.get_process(DATABASE_PATH, request.process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Süreç bulunamadı.")
    overrides = request.overrides.model_dump(exclude_none=True)
    if not overrides:
        raise HTTPException(status_code=422, detail="Simülasyon için en az bir alan girilmelidir.")
    invalid_fields = set(overrides).difference(SIMULATABLE_FIELDS)
    if invalid_fields:
        raise HTTPException(status_code=422, detail="Geçersiz simülasyon alanı gönderildi.")
    # Karşılaştırma aynı tahmin anında yapılmalıdır. Ekrandaki son tahmin önceki
    # bir güne ait olabilir; onu bugünkü senaryoyla kıyaslamak yanlış fark üretir.
    baseline = _predict_for_process(process, persist=False)
    simulated = process | overrides
    result = _predict_for_process(simulated, persist=False)
    return {
        "original_process_id": process["id"],
        "overrides": overrides,
        "deadline_context": result["deadline_context"],
        "baseline": baseline,
        "simulation": result,
    }


@router.get("/models/active")
def get_active_models():
    return {"items": repository.get_active_models(DATABASE_PATH)}


@router.get("/models/monitoring")
def get_model_monitoring():
    return repository.get_feedback_summary(DATABASE_PATH)


@router.get("/models/data-drift")
def get_data_drift():
    reference_rows, current_rows = repository.get_drift_samples(DATABASE_PATH)
    return drift_report(reference_rows, current_rows)


@router.get("/data-quality")
def get_data_quality():
    report_path = REPORT_DIR / "data_quality_report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Veri kalite raporu bulunamadı.")
    return json.loads(report_path.read_text(encoding="utf-8"))


@router.get("/system-health")
def get_system_health():
    """Son yerel ölçümü ve kısa geçmişini verir; ölçüm geçmişi yoksa yeni ölçüm üretir."""

    latest = system_health_repository.latest_health_event(DATABASE_PATH)
    if latest is None:
        latest = check_and_record(DATABASE_PATH)
    return {"latest": latest, "history": system_health_repository.list_health_events(DATABASE_PATH, limit=20)}


@router.post("/system-health/check")
def run_system_health_check():
    """Kullanıcının ekrandan istediği anlık yerel sağlık kontrolü."""

    return check_and_record(DATABASE_PATH)


@router.post("/feedback", status_code=201)
def create_feedback(feedback: FeedbackRequest):
    try:
        feedback_id = repository.save_feedback(DATABASE_PATH, feedback.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    logger.info("feedback_saved type=%s", feedback.feedback_type)
    return {"feedback_id": feedback_id, "message": "Geri bildirim kaydedildi."}


@router.post("/imports/processes")
async def import_process_file(file: UploadFile = File(...)):
    """Yerel CSV/XLSX dosyasını doğrulayıp geçerli satırlarını SQLite'a yazar."""
    filename = file.filename or ""
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in {"csv", "xlsx"}:
        raise HTTPException(status_code=415, detail="Yalnızca .csv veya .xlsx dosyası yüklenebilir.")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Yüklenen dosya boş.")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Dosya 10 MB sınırını aşıyor.")
    try:
        buffer = io.BytesIO(content)
        dataframe = pd.read_csv(buffer, low_memory=False) if suffix == "csv" else pd.read_excel(buffer)
        report = import_dataframe(dataframe, DATABASE_PATH, REPORT_DIR / "data_quality_report.json")
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        logger.warning("import_failed error_type=%s", type(error).__name__)
        raise HTTPException(status_code=400, detail=f"Dosya okunamadı: {error}") from error
    logger.info("import_completed imported_rows=%s rejected_rows=%s", report["imported_rows"], report["rejected_rows"])
    return {"filename": filename, "report": report, "message": "Geçerli satırlar yerel veritabanına aktarıldı."}
