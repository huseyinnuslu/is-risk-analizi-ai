"""Yerel makinenin CPU, RAM, disk ve varsa GPU durumunu izler."""

from __future__ import annotations

import logging
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.core import config
from app.repositories import system_health_repository as repository


logger = logging.getLogger("istrisk")
_stop_event = threading.Event()
_monitor_thread: threading.Thread | None = None


def _gpu_snapshot() -> dict:
    """NVIDIA sürücüsü yoksa hata vermek yerine GPU bilgisini kullanılabilir değil yapar."""

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3, check=True,
        )
        name, percent, used, total = [value.strip() for value in result.stdout.splitlines()[0].split(",")]
        return {
            "available": True, "scope": "NVIDIA ayrık GPU", "name": name,
            "percent": float(percent), "memory_used_mb": float(used), "memory_total_mb": float(total),
        }
    except (FileNotFoundError, subprocess.SubprocessError, IndexError, ValueError):
        return {"available": False, "scope": "NVIDIA ayrık GPU", "message": "NVIDIA GPU verisi bulunamadı."}


def evaluate_status(cpu: float, memory: float, disk: float) -> tuple[str, list[str]]:
    """Kaynak yüzdelerini işletimsel eşiklerle yorumlar."""

    critical, warnings = [], []
    checks = (
        ("CPU", cpu, config.SYSTEM_CPU_WARNING_PERCENT, config.SYSTEM_CPU_CRITICAL_PERCENT),
        ("RAM", memory, config.SYSTEM_MEMORY_WARNING_PERCENT, config.SYSTEM_MEMORY_CRITICAL_PERCENT),
        ("Disk", disk, config.SYSTEM_DISK_WARNING_PERCENT, config.SYSTEM_DISK_CRITICAL_PERCENT),
    )
    for name, value, warning_threshold, critical_threshold in checks:
        if value >= critical_threshold:
            critical.append(f"{name} %{value:.1f} ile kritik eşikte")
        elif value >= warning_threshold:
            warnings.append(f"{name} %{value:.1f} ile izleme eşiğinde")
    if critical:
        return "critical", critical + warnings
    if warnings:
        return "warning", warnings
    return "healthy", []


def collect_health_snapshot() -> dict:
    """Ölçümü yalnızca yerel makineden alır; dış sistemden veri çekmez."""

    try:
        import psutil
    except ImportError:
        return {
            "status": "unavailable", "alert_summary": "psutil bağımlılığı kurulu değil.",
            "measured_at": datetime.now(timezone.utc).isoformat(),
            "cpu": {}, "memory": {}, "disk": {}, "gpu": _gpu_snapshot(),
        }

    cpu_percent = float(psutil.cpu_percent(interval=0.2))
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(Path.cwd().anchor)
    status, messages = evaluate_status(cpu_percent, float(memory.percent), float(disk.percent))
    return {
        "status": status,
        "alert_summary": " · ".join(messages) if messages else None,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "cpu": {"percent": cpu_percent, "core_count": psutil.cpu_count(logical=True)},
        "memory": {"percent": float(memory.percent), "used_gb": round(memory.used / 1024**3, 2), "total_gb": round(memory.total / 1024**3, 2)},
        "disk": {"percent": float(disk.percent), "used_gb": round(disk.used / 1024**3, 2), "total_gb": round(disk.total / 1024**3, 2)},
        "gpu": _gpu_snapshot(),
    }


def check_and_record(database_path: Path) -> dict:
    snapshot = collect_health_snapshot()
    snapshot["event_id"] = repository.save_health_event(database_path, snapshot)
    return snapshot


def start_monitor(database_path: Path) -> None:
    """FastAPI yanında çalışan, daemon nitelikli ücretsiz yerel izleyici."""

    global _monitor_thread
    if not config.SYSTEM_MONITOR_ENABLED or (_monitor_thread and _monitor_thread.is_alive()):
        return
    _stop_event.clear()

    def run() -> None:
        while not _stop_event.is_set():
            try:
                check_and_record(database_path)
            except Exception:
                logger.exception("system_health_monitor_failed")
            _stop_event.wait(max(10, config.SYSTEM_MONITOR_INTERVAL_SECONDS))

    _monitor_thread = threading.Thread(target=run, name="system-health-monitor", daemon=True)
    _monitor_thread.start()


def stop_monitor() -> None:
    _stop_event.set()
