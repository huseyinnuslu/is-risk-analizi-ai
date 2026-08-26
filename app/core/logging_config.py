"""Yerel uygulama olaylarını hassas süreç verisi yazmadan kaydeder."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.core.config import LOG_DIR


def configure_local_logging() -> logging.Logger:
    """En fazla 3 adet 1 MB yerel log dosyası tutar; kayıt/kişi bilgisi loglanmaz."""
    logger = logging.getLogger("istrisk")
    if logger.handlers:
        return logger
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        LOG_DIR / "app.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    return logger
