"""
OptiProcess - Aplicación principal FastAPI
Sistema Profesional de Control Estadístico de Procesos
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
import os
import logging

from app.config import settings
from app.database import create_tables, SessionLocal
from app.core.logging_config import setup_logging
from app.core.exceptions import (
    OptiProcessException,
    optiprocess_exception_handler,
    validation_exception_handler,
    http_exception_handler,
)
from app.api import auth, datasets, control_charts, capability, assumptions, sampling, dashboard

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="OptiProcess API",
        description="Sistema Profesional de Control Estadístico de Procesos (CEP/SPC)",
        version=settings.APP_VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        redirect_slashes=False,   # evita redirect 307 que borra el header Authorization
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception Handlers ────────────────────────────────────────────────
    app.add_exception_handler(OptiProcessException, optiprocess_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    # ── Routers ───────────────────────────────────────────────────────────
    prefix = "/api"
    app.include_router(auth.router, prefix=prefix)
    app.include_router(datasets.router, prefix=prefix)
    app.include_router(control_charts.router, prefix=prefix)
    app.include_router(capability.router, prefix=prefix)
    app.include_router(assumptions.router, prefix=prefix)
    app.include_router(sampling.router, prefix=prefix)
    app.include_router(dashboard.router, prefix=prefix)

    # ── Startup ───────────────────────────────────────────────────────────
    @app.on_event("startup")
    async def startup():
        create_tables()
        # Crear usuario admin por defecto
        db = SessionLocal()
        try:
            from app.services.auth_service import auth_service
            auth_service.create_default_admin(db)
        finally:
            db.close()

        # Crear directorios necesarios
        for d in [settings.UPLOAD_DIR, settings.REPORTS_DIR, "logs"]:
            os.makedirs(d, exist_ok=True)

        logger.info(f"🚀 OptiProcess {settings.APP_VERSION} iniciado correctamente")
        logger.info(f"   Docs: http://localhost:{settings.PORT}/api/docs")

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
