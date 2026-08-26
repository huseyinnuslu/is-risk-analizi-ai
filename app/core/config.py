"""Yerel uygulama ayarları."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

APP_NAME = os.getenv("APP_NAME", "AI Destekli İş Süreci Tahmin ve Gecikme Risk Sistemi")
DATABASE_PATH = PROJECT_ROOT / os.getenv("DATABASE_PATH", "data/process_risk.db")
MODEL_ARTIFACT_DIR = PROJECT_ROOT / os.getenv("MODEL_ARTIFACT_DIR", "ml/artifacts")
REPORT_DIR = PROJECT_ROOT / "reports" / "generated"
LOG_DIR = PROJECT_ROOT / "logs"
TEAM_CAPACITY = int(os.getenv("TEAM_CAPACITY", "4000"))
SYSTEM_MONITOR_ENABLED = os.getenv("SYSTEM_MONITOR_ENABLED", "true").lower() == "true"
SYSTEM_MONITOR_INTERVAL_SECONDS = int(os.getenv("SYSTEM_MONITOR_INTERVAL_SECONDS", "60"))
SYSTEM_CPU_WARNING_PERCENT = float(os.getenv("SYSTEM_CPU_WARNING_PERCENT", "80"))
SYSTEM_CPU_CRITICAL_PERCENT = float(os.getenv("SYSTEM_CPU_CRITICAL_PERCENT", "95"))
SYSTEM_MEMORY_WARNING_PERCENT = float(os.getenv("SYSTEM_MEMORY_WARNING_PERCENT", "80"))
SYSTEM_MEMORY_CRITICAL_PERCENT = float(os.getenv("SYSTEM_MEMORY_CRITICAL_PERCENT", "90"))
SYSTEM_DISK_WARNING_PERCENT = float(os.getenv("SYSTEM_DISK_WARNING_PERCENT", "85"))
SYSTEM_DISK_CRITICAL_PERCENT = float(os.getenv("SYSTEM_DISK_CRITICAL_PERCENT", "95"))
