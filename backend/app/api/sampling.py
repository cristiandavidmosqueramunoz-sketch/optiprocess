"""
OptiProcess - Endpoints de muestreo de aceptación
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.analysis import SamplingRequest
from app.services.auth_service import get_current_user
from app.services.statistical.sampling import design_single_sampling_plan, design_double_sampling_plan
import logging
from dataclasses import asdict

router = APIRouter(prefix="/sampling", tags=["Muestreo de Aceptación"])
logger = logging.getLogger(__name__)


@router.post("/design")
def design_sampling_plan(
    request: SamplingRequest,
    current_user: User = Depends(get_current_user),
):
    """Diseña plan de muestreo de aceptación según parámetros AQL/LTPD."""
    try:
        if request.tipo == "simple":
            result = design_single_sampling_plan(
                N=request.n_lote,
                aql=request.aql,
                ltpd=request.ltpd,
                alpha=request.alpha,
                beta=request.beta,
                nivel_inspeccion=request.nivel_inspeccion,
            )
            return {
                "tipo": "simple",
                "plan": asdict(result),
            }
        elif request.tipo == "doble":
            result = design_double_sampling_plan(
                N=request.n_lote,
                aql=request.aql,
                alpha=request.alpha,
                beta=request.beta,
            )
            return {"tipo": "doble", "plan": result}
        else:
            raise HTTPException(status_code=400, detail="Tipo 'multiple' en desarrollo. Use 'simple' o 'doble'.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en diseño del plan: {str(e)}")


@router.get("/tables")
def get_standard_tables(current_user: User = Depends(get_current_user)):
    """Retorna tablas estándar AQL ISO 2859 / MIL-STD-1916."""
    # Niveles AQL estándar
    aql_levels = [0.065, 0.10, 0.15, 0.25, 0.40, 0.65, 1.0, 1.5, 2.5, 4.0, 6.5, 10.0]
    return {
        "aql_estandar": aql_levels,
        "niveles_inspeccion": ["I", "II", "III"],
        "tipos_muestreo": ["simple", "doble", "multiple"],
        "referencia": "ISO 2859-1 / ANSI/ASQ Z1.4",
        "descripcion": (
            "AQL (Acceptable Quality Level): nivel máximo de defectos considerado aceptable. "
            "LTPD (Lot Tolerance Percent Defective): nivel de calidad rechazable. "
            "α: riesgo del productor (rechazar lote bueno). "
            "β: riesgo del consumidor (aceptar lote malo)."
        ),
    }
