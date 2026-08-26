from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import DATABASE_PATH
from app.repositories import process_repository as repository

PROJECT_ROOT = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "app" / "templates"))
router = APIRouter(include_in_schema=False)


def render(request: Request, template_name: str, **context) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={"current_page": template_name.replace(".html", ""), **context},
    )


@router.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request):
    dashboard = repository.dashboard_summary(DATABASE_PATH)
    type_max = max((item["count"] for item in dashboard["process_type_distribution"]), default=1)
    risk_max = max((item["count"] for item in dashboard["risk_distribution"]), default=1)
    for item in dashboard["process_type_distribution"]:
        item["percent"] = round(item["count"] / type_max * 100)
    for item in dashboard["risk_distribution"]:
        item["percent"] = round(item["count"] / risk_max * 100)
    return render(
        request, "dashboard.html", title="Dashboard",
        dashboard=dashboard,
        priority_processes=repository.list_processes(DATABASE_PATH, status="open", limit=8),
    )


@router.get("/processes", response_class=HTMLResponse)
def processes_page(request: Request):
    risk_level = request.query_params.get("risk_level") or None
    deadline_status = request.query_params.get("deadline_status") or "actionable"
    process_type = request.query_params.get("process_type") or None
    current_stage = request.query_params.get("current_stage") or None
    responsible_team = request.query_params.get("responsible_team") or None
    if risk_level not in {"Düşük", "Orta", "Yüksek"}:
        risk_level = None
    if deadline_status not in {"actionable", "overdue", "urgent", "within_deadline", "all"}:
        deadline_status = "actionable"
    if deadline_status == "all":
        deadline_status = None
    return render(
        request, "processes.html", title="İş Öncelik Listesi",
        processes=repository.list_processes(
            DATABASE_PATH, status="open", risk_level=risk_level,
            deadline_status=deadline_status, limit=1_000,
            process_type=process_type, current_stage=current_stage,
            responsible_team=responsible_team,
        ),
        selected_risk=risk_level or "", selected_deadline=deadline_status or "all",
        selected_process_type=process_type or "", selected_stage=current_stage or "",
        selected_team=responsible_team or "",
        filter_options=repository.get_open_process_filter_options(DATABASE_PATH),
    )


@router.get("/processes/{process_id}", response_class=HTMLResponse)
def process_detail_page(request: Request, process_id: int):
    return render(request, "process_detail.html", title="İş Detayı", process_id=process_id)


@router.get("/models", response_class=HTMLResponse)
def models_page(request: Request):
    return render(request, "models.html", title="Model Performansı")


@router.get("/data-quality", response_class=HTMLResponse)
def data_quality_page(request: Request):
    return render(request, "data_quality.html", title="Veri Kalitesi")


@router.get("/imports", response_class=HTMLResponse)
def imports_page(request: Request):
    return render(request, "imports.html", title="Veri İçe Aktarma")


@router.get("/system-health", response_class=HTMLResponse)
def system_health_page(request: Request):
    return render(request, "system_health.html", title="Sistem Sağlığı")
