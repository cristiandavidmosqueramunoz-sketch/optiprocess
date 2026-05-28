"""
OptiProcess - Endpoints del Dashboard principal
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.database import get_db
from app.models.user import User
from app.models.dataset import Dataset
from app.models.analysis import Analysis
from app.services.auth_service import get_current_user
import logging

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
logger = logging.getLogger(__name__)


@router.get("/summary")
def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resumen ejecutivo para el dashboard principal."""
    # KPIs
    total_datasets = db.query(Dataset).filter(
        Dataset.usuario_id == current_user.id, Dataset.activo == True
    ).count()

    total_analyses = db.query(Analysis).filter(
        Analysis.usuario_id == current_user.id
    ).count()

    analyses_fase1 = db.query(Analysis).filter(
        Analysis.usuario_id == current_user.id, Analysis.fase == "I"
    ).count()

    analyses_fase2 = db.query(Analysis).filter(
        Analysis.usuario_id == current_user.id, Analysis.fase == "II"
    ).count()

    # Análisis recientes
    recent_analyses = db.query(Analysis).filter(
        Analysis.usuario_id == current_user.id
    ).order_by(Analysis.created_at.desc()).limit(5).all()

    # Alertas activas (análisis Fase II con problemas)
    alertas_activas = []
    fase2_analyses = db.query(Analysis).filter(
        Analysis.usuario_id == current_user.id,
        Analysis.fase == "II",
    ).order_by(Analysis.created_at.desc()).limit(10).all()

    for a in fase2_analyses:
        if a.resultados and not a.resultados.get("proceso_bajo_control", True):
            alertas_activas.append({
                "analisis_id": a.id,
                "nombre": a.nombre,
                "tipo": a.tipo,
                "estado": a.resultados.get("estado_proceso", "advertencia"),
                "puntos_ooc": a.resultados.get("puntos_fuera_control", 0),
                "fecha": a.created_at.isoformat(),
            })

    # Actividad reciente
    actividad = [
        {
            "id": a.id,
            "tipo": a.tipo,
            "fase": a.fase,
            "nombre": a.nombre or f"Análisis {a.tipo.upper()}",
            "estado": a.estado,
            "fecha": a.created_at.isoformat(),
        }
        for a in recent_analyses
    ]

    # Datasets recientes
    recent_datasets = db.query(Dataset).filter(
        Dataset.usuario_id == current_user.id, Dataset.activo == True
    ).order_by(Dataset.created_at.desc()).limit(5).all()

    return {
        "usuario": {
            "nombre_completo": f"{current_user.nombre} {current_user.apellido}",
            "rol": current_user.rol,
            "empresa": current_user.empresa,
            "primer_login": current_user.primer_login,
        },
        "kpis": {
            "total_datasets": total_datasets,
            "total_analisis": total_analyses,
            "analisis_fase1": analyses_fase1,
            "analisis_fase2": analyses_fase2,
            "alertas_activas": len(alertas_activas),
        },
        "alertas_activas": alertas_activas[:5],
        "actividad_reciente": actividad,
        "datasets_recientes": [
            {
                "id": d.id, "nombre": d.nombre, "proceso": d.proceso,
                "n_filas": d.n_filas, "fase": d.fase,
                "fecha": d.created_at.isoformat(),
            }
            for d in recent_datasets
        ],
    }


@router.get("/stats")
def get_process_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Estadísticas globales de los procesos analizados."""
    # Capacidades calculadas
    capabilities = db.query(Analysis).filter(
        Analysis.usuario_id == current_user.id,
        Analysis.tipo == "capability",
    ).all()

    cap_stats = {"total": len(capabilities), "capaces": 0, "marginales": 0, "no_capaces": 0}
    for c in capabilities:
        if c.resultados:
            cpk = c.resultados.get("cpk")
            if cpk:
                if cpk >= 1.33:
                    cap_stats["capaces"] += 1
                elif cpk >= 1.00:
                    cap_stats["marginales"] += 1
                else:
                    cap_stats["no_capaces"] += 1

    return {
        "capacidad": cap_stats,
        "modulos_utilizados": {
            "fase1": db.query(Analysis).filter(Analysis.usuario_id == current_user.id, Analysis.fase == "I", Analysis.tipo != "capability").count(),
            "fase2": db.query(Analysis).filter(Analysis.usuario_id == current_user.id, Analysis.fase == "II").count(),
            "capacidad": len(capabilities),
        },
    }
