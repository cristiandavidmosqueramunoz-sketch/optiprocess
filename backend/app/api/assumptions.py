"""
OptiProcess - Endpoints de validación de supuestos estadísticos
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import pandas as pd
from app.database import get_db
from app.models.user import User
from app.models.dataset import Dataset
from app.schemas.analysis import AssumptionsRequest
from app.services.auth_service import get_current_user
from app.services.statistical.assumptions import validate_assumptions
import logging

router = APIRouter(prefix="/assumptions", tags=["Validación de Supuestos"])
logger = logging.getLogger(__name__)


@router.post("/validate")
def validate_statistical_assumptions(
    request: AssumptionsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Validación completa de supuestos: normalidad, independencia, estabilidad."""
    dataset = db.query(Dataset).filter(
        Dataset.id == request.dataset_id, Dataset.usuario_id == current_user.id
    ).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset no encontrado")

    df = pd.DataFrame(dataset.datos or [])
    if request.columna not in df.columns:
        raise HTTPException(status_code=400, detail=f"Columna '{request.columna}' no encontrada")

    import numpy as np
    values = pd.to_numeric(df[request.columna], errors="coerce").dropna().values

    if len(values) < 8:
        raise HTTPException(status_code=400, detail="Se requieren al menos 8 observaciones para validar supuestos")

    try:
        result = validate_assumptions(values, alpha=request.nivel_significancia)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en validación: {str(e)}")

    def test_to_dict(t):
        if t is None:
            return None
        return {
            "nombre": t.nombre, "estadistico": t.estadistico,
            "p_valor": t.p_valor, "rechaza_h0": t.rechaza_h0,
            "conclusion": t.conclusion, "interpretacion": t.interpretacion,
            "nivel_significancia": t.nivel_significancia,
        }

    return {
        "n": result.n, "media": result.media, "std": result.std,
        "normalidad": {
            "shapiro_wilk": test_to_dict(result.shapiro_wilk),
            "anderson_darling": test_to_dict(result.anderson_darling),
            "kolmogorov_smirnov": test_to_dict(result.kolmogorov_smirnov),
            "normalidad_ok": result.normalidad_ok,
        },
        "independencia": {
            "runs_test": test_to_dict(result.runs_test),
            "durbin_watson": result.durbin_watson,
            "autocorrelacion_lag1": result.autocorrelacion_lag1,
            "independencia_ok": result.independencia_ok,
        },
        "aptitud": {
            "apto_fase1": result.apto_fase1,
            "apto_fase2": result.apto_fase2,
        },
        "diagnostico_global": result.diagnostico_global,
        "recomendaciones": result.recomendaciones,
        "graficos": {
            "qq_data": result.qq_data,
            "histograma": result.histograma,
        },
    }
