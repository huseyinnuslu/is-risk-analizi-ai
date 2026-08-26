"""FastAPI uygulamasının başlangıç noktası."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import router
from app.core.config import APP_NAME, DATABASE_PATH
from app.core.logging_config import configure_local_logging
from app.database.schema import initialise_database
from app.services.system_health_service import start_monitor, stop_monitor
from app.web.router import PROJECT_ROOT, router as web_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialise_database(DATABASE_PATH)
    configure_local_logging().info("application_started local_only=true")
    start_monitor(DATABASE_PATH)
    yield
    stop_monitor()


app = FastAPI(
    title=APP_NAME,
    version="0.1.0",
    description="Yerel çalışan, açıklanabilir gecikme riski karar destek API'si.",
    lifespan=lifespan,
)
app.include_router(router)
app.include_router(web_router)
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "app" / "static")), name="static")


@app.get("/health", tags=["health"])
def health_check():
    # Yerel dosya sisteminin mutlak yolunu API yanıtında ifşa etmeyiz.
    return {"status": "ok", "storage": "local_sqlite"}
