"""
OptiProcess - Endpoints de capacidad del proceso
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import numpy as np
import pandas as pd
from app.database import get_db
from app.models.user import User
from app.models.dataset import Dataset
from app.models.analysis import Analysis
from app.schemas.analysis import CapabilityRequest
from app.services.auth_service import get_current_user
from app.services.statistical.capability import calculate_capability
import logging

router = APIRouter(prefix="/capability", tags=["Capacidad del Proceso"])
logger = logging.getLogger(__name__)


@router.post("/calculate")
def calculate_process_capability(
    request: CapabilityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Calcula índices de capacidad Cp, Cpk, Pp, Ppk con semáforos y diagnóstico."""
    dataset = db.query(Dataset).filter(
        Dataset.id == request.dataset_id, Dataset.usuario_id == current_user.id
    ).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset no encontrado")

    df = pd.DataFrame(dataset.datos or [])
    if request.columna not in df.columns:
        raise HTTPException(status_code=400, detail=f"Columna '{request.columna}' no encontrada")

    values = pd.to_numeric(df[request.columna], errors="coerce").dropna().values

    if len(values) < 10:
        raise HTTPException(status_code=400, detail="Se requieren al menos 10 observaciones")

    if request.usl is None and request.lsl is None:
        raise HTTPException(status_code=400, detail="Debe especificar al menos un límite de especificación (USL o LSL)")

    try:
        result = calculate_capability(
            data=values,
            usl=request.usl,
            lsl=request.lsl,
            target=request.target,
            subgroup_size=request.tamano_subgrupo,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en cálculo de capacidad: {str(e)}")

    # Guardar análisis
    result_dict = {
        "n": result.n, "media": result.media,
        "std_within": result.std_within, "std_overall": result.std_overall,
        "cp": result.cp, "cpl": result.cpl, "cpu": result.cpu, "cpk": result.cpk,
        "pp": result.pp, "ppl": result.ppl, "ppu": result.ppu, "ppk": result.ppk,
        "ppm_total_within": result.ppm_total_within,
        "ppm_abajo_within": result.ppm_abajo_within,
        "ppm_arriba_within": result.ppm_arriba_within,
        "ppm_total_overall": result.ppm_total_overall,
        "calificacion_cpk": result.calificacion_cpk,
        "calificacion_ppk": result.calificacion_ppk,
        "color_cpk": result.color_cpk, "color_ppk": result.color_ppk,
        "interpretacion": result.interpretacion,
        "diagnostico": result.diagnostico,
        "recomendaciones": result.recomendaciones,
        "datos": result.datos[:500],  # Muestra para histograma
        "curva_normal": result.curva_normal,
        "usl": result.usl, "lsl": result.lsl, "target": result.target,
    }

    analysis = Analysis(
        dataset_id=request.dataset_id,
        usuario_id=current_user.id,
        tipo="capability",
        fase="I",
        nombre=f"Capacidad - {request.columna}",
        columna_variable=request.columna,
        tamano_subgrupo=request.tamano_subgrupo,
        parametros={"usl": request.usl, "lsl": request.lsl, "target": request.target},
        resultados=result_dict,
        interpretacion=result.diagnostico,
        estado="completado",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    result_dict["analisis_id"] = analysis.id
    return result_dict
