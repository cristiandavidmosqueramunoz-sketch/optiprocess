"""
OptiProcess - Endpoints de gráficos de control Fase I y Fase II
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import numpy as np
import pandas as pd
from typing import Optional, List
from pydantic import BaseModel
from app.database import get_db
from app.models.user import User
from app.models.dataset import Dataset
from app.models.analysis import Analysis
from app.schemas.analysis import ControlChartRequest, Phase2MonitorRequest
from app.services.auth_service import get_current_user
from app.services.statistical.phase1_engine import Phase1Engine
from app.services.statistical.phase2_engine import Phase2Engine
from app.services.statistical.control_charts import get_constants
from app.services.statistical.rules_engine import apply_western_electric_rules
from dataclasses import asdict
import logging

router = APIRouter(prefix="/charts", tags=["Gráficos de Control"])
logger = logging.getLogger(__name__)
phase1_engine = Phase1Engine()
phase2_engine = Phase2Engine()


def _get_dataset_data(dataset_id: int, user_id: int, db: Session):
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id, Dataset.usuario_id == user_id
    ).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset no encontrado")
    return dataset


def _extract_values(dataset, columna: str, subgrupo_col: Optional[str] = None):
    """Extrae valores numéricos del dataset."""
    df = pd.DataFrame(dataset.datos or [])
    if columna not in df.columns:
        raise HTTPException(status_code=400, detail=f"Columna '{columna}' no encontrada")
    values = pd.to_numeric(df[columna], errors="coerce").dropna().values
    sample_sizes = None
    if subgrupo_col and subgrupo_col in df.columns:
        sample_sizes = pd.to_numeric(df[subgrupo_col], errors="coerce").dropna().values
    return values, sample_sizes


@router.post("/phase1/analyze")
def analyze_phase1(
    request: ControlChartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Análisis completo de Fase I con depuración iterativa de causas especiales."""
    dataset = _get_dataset_data(request.dataset_id, current_user.id, db)
    values, sample_sizes = _extract_values(dataset, request.columna_variable, request.columna_subgrupo)

    if len(values) < 10:
        raise HTTPException(status_code=400, detail="Se requieren al menos 10 observaciones para el análisis")

    subgroup_size = request.tamano_subgrupo or 1

    try:
        result = phase1_engine.analyze(
            data=values,
            chart_type=request.tipo_grafico,
            subgroup_size=subgroup_size,
            manual_exclusions=request.puntos_excluidos,
            rules=request.reglas_we,
            sample_sizes=sample_sizes,
            iterative=True,
        )
    except Exception as e:
        logger.error(f"Error en análisis Fase I: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error en análisis estadístico: {str(e)}")

    # Serializar resultado
    result_dict = _serialize_phase1_result(result)

    # Guardar en base de datos
    analysis = Analysis(
        dataset_id=request.dataset_id,
        usuario_id=current_user.id,
        tipo=request.tipo_grafico,
        fase="I",
        nombre=request.nombre or f"Fase I - {request.tipo_grafico.upper()}",
        columna_variable=request.columna_variable,
        columna_subgrupo=request.columna_subgrupo,
        tamano_subgrupo=subgroup_size,
        parametros=request.dict(),
        resultados=result_dict,
        limites_control=result.limites_establecidos,
        puntos_excluidos=[asdict(e) for e in result.exclusiones],
        interpretacion=result.diagnostico,
        estado="completado",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    result_dict["analisis_id"] = analysis.id
    return result_dict


@router.post("/phase2/monitor")
def monitor_phase2(
    request: Phase2MonitorRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Monitoreo Fase II usando límites establecidos en Fase I."""
    # Obtener análisis Fase I
    analysis_fase1 = db.query(Analysis).filter(
        Analysis.id == request.analisis_fase1_id,
        Analysis.usuario_id == current_user.id,
        Analysis.fase == "I",
    ).first()
    if not analysis_fase1:
        raise HTTPException(status_code=404, detail="Análisis de Fase I no encontrado")

    limits = analysis_fase1.limites_control
    if not limits:
        raise HTTPException(status_code=400, detail="El análisis Fase I no tiene límites establecidos")

    # Obtener datos
    dataset = _get_dataset_data(request.dataset_id, current_user.id, db)
    values, sample_sizes = _extract_values(dataset, request.columna_variable, request.columna_subgrupo)

    chart_type = analysis_fase1.tipo
    subgroup_size = analysis_fase1.tamano_subgrupo or 1

    try:
        result = phase2_engine.monitor(
            new_data=values,
            phase1_limits=limits,
            chart_type=chart_type,
            subgroup_size=subgroup_size,
            sample_sizes=sample_sizes,
        )
    except Exception as e:
        logger.error(f"Error en monitoreo Fase II: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error en monitoreo: {str(e)}")

    # Serializar alertas
    alertas = []
    for a in result.alertas:
        alertas.append({
            "tipo": a.tipo, "severidad": a.severidad,
            "punto_indice": a.punto_indice, "valor": a.valor,
            "reglas_violadas": a.reglas_violadas,
            "mensaje": a.mensaje, "accion_recomendada": a.accion_recomendada,
        })

    # Guardar análisis
    analysis = Analysis(
        dataset_id=request.dataset_id,
        usuario_id=current_user.id,
        tipo=chart_type,
        fase="II",
        nombre=f"Fase II - Monitoreo",
        columna_variable=request.columna_variable,
        columna_subgrupo=request.columna_subgrupo,
        tamano_subgrupo=subgroup_size,
        resultados={
            "values_chart1": result.values_chart1,
            "values_chart2": result.values_chart2,
            "ooc_chart1": result.ooc_chart1,
            "ooc_chart2": result.ooc_chart2,
            "proceso_bajo_control": result.proceso_bajo_control,
            "puntos_en_control": result.puntos_en_control,
            "puntos_fuera_control": result.puntos_fuera_control,
            "estado_proceso": result.estado_proceso,
            "alertas": alertas,
            "violaciones_detalle": result.violaciones_detalle,
        },
        limites_control=limits,
        interpretacion=result.diagnostico,
        estado="completado",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    return {
        "analisis_id": analysis.id,
        "tipo_grafico": result.tipo_grafico,
        "fase": "II",
        "limites": {
            "cl_chart1": result.cl_chart1, "ucl_chart1": result.ucl_chart1, "lcl_chart1": result.lcl_chart1,
            "cl_chart2": result.cl_chart2, "ucl_chart2": result.ucl_chart2, "lcl_chart2": result.lcl_chart2,
        },
        "datos": {
            "values_chart1": result.values_chart1,
            "values_chart2": result.values_chart2,
            "ooc_chart1": result.ooc_chart1,
            "ooc_chart2": result.ooc_chart2,
        },
        "estado": {
            "proceso_bajo_control": result.proceso_bajo_control,
            "estado_proceso": result.estado_proceso,
            "puntos_en_control": result.puntos_en_control,
            "puntos_fuera_control": result.puntos_fuera_control,
        },
        "alertas": alertas,
        "violaciones": result.violaciones_detalle,
        "diagnostico": result.diagnostico,
        "recomendaciones": result.recomendaciones,
    }


@router.get("/analyses")
def list_analyses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar todos los análisis del usuario."""
    analyses = db.query(Analysis).filter(
        Analysis.usuario_id == current_user.id
    ).order_by(Analysis.created_at.desc()).limit(50).all()

    return [
        {
            "id": a.id, "tipo": a.tipo, "fase": a.fase,
            "nombre": a.nombre, "dataset_id": a.dataset_id,
            "estado": a.estado, "created_at": a.created_at.isoformat(),
        }
        for a in analyses
    ]


@router.get("/analyses/{analysis_id}")
def get_analysis(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtener análisis completo por ID."""
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id, Analysis.usuario_id == current_user.id
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")
    return {
        "id": analysis.id, "tipo": analysis.tipo, "fase": analysis.fase,
        "nombre": analysis.nombre, "columna_variable": analysis.columna_variable,
        "tamano_subgrupo": analysis.tamano_subgrupo,
        "resultados": analysis.resultados,
        "limites_control": analysis.limites_control,
        "puntos_excluidos": analysis.puntos_excluidos,
        "interpretacion": analysis.interpretacion,
        "estado": analysis.estado,
        "created_at": analysis.created_at.isoformat(),
    }


class VariablesChartRequest(BaseModel):
    dataset_id: int
    tipo: str                     # "xbar_r", "xbar_s", "imr"
    columnas: List[str]           # para X̄-R / X̄-S: varias columnas (n por subgrupo)
                                  # para I-MR: una sola columna
    nombre: Optional[str] = None
    puntos_excluidos: List[int] = []
    reglas_we: List[int] = [1, 2, 3, 4, 5, 6, 7, 8]


# Mantener alias para compatibilidad
class XBarRRequest(VariablesChartRequest):
    pass


@router.post("/variables")
def analyze_variables_chart(
    request: VariablesChartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Endpoint unificado para X̄-R, X̄-S e I-MR con subgrupos reales.
    - X̄-R / X̄-S: cada columna seleccionada = una observación del subgrupo. Cada fila = un subgrupo.
    - I-MR: una columna, cada fila = observación individual.
    """
    if request.tipo not in ("xbar_r", "xbar_s", "imr"):
        raise HTTPException(400, detail="tipo debe ser xbar_r, xbar_s o imr")

    dataset = _get_dataset_data(request.dataset_id, current_user.id, db)
    df = pd.DataFrame(dataset.datos or [])

    missing = [c for c in request.columnas if c not in df.columns]
    if missing:
        raise HTTPException(400, detail=f"Columnas no encontradas: {missing}")

    if request.tipo == "imr":
        return _analyze_imr(request, df, current_user.id, db)
    else:
        return _analyze_xbar_subgroups(request, df, current_user.id, db)


def _analyze_xbar_subgroups(request: VariablesChartRequest, df: pd.DataFrame, user_id: int, db):
    """Lógica compartida para X̄-R y X̄-S."""
    tipo = request.tipo
    if len(request.columnas) < 2:
        raise HTTPException(400, detail=f"{tipo.upper()}: se necesitan ≥ 2 columnas (n ≥ 2)")

    sub_df = df[request.columnas].apply(pd.to_numeric, errors="coerce").dropna(how="all")
    if len(sub_df) < 3:
        raise HTTPException(400, detail="Se necesitan al menos 3 subgrupos con datos válidos")

    n = len(request.columnas)
    k = len(sub_df)
    excluidos = set(request.puntos_excluidos)
    mask = [i for i in range(k) if i not in excluidos]

    subgroup_data = []
    xbars, dispersiones = [], []

    for idx, (_, row) in enumerate(sub_df.iterrows()):
        vals = row.dropna().values
        if len(vals) == 0:
            continue
        xi_bar = float(np.mean(vals))
        if tipo == "xbar_r":
            disp = float(np.max(vals) - np.min(vals))        # rango
        else:
            disp = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0  # desviación

        subgroup_data.append({
            "subgrupo": idx + 1,
            "observaciones": [round(float(v), 4) for v in vals],
            "media": round(xi_bar, 4),
            "dispersion": round(disp, 4),
            "ooc_xbar": False, "ooc_disp": False, "excluido": idx in excluidos,
        })
        xbars.append(xi_bar)
        dispersiones.append(disp)

    xbars = np.array(xbars)
    dispersiones = np.array(dispersiones)
    xbars_c = xbars[mask]
    disp_c = dispersiones[mask]

    consts = get_constants(n)
    x_bar_bar = float(np.mean(xbars_c))
    disp_bar = float(np.mean(disp_c))

    if tipo == "xbar_r":
        d2 = consts["d2"]
        sigma_est = disp_bar / d2
        ucl_x = x_bar_bar + consts["A2"] * disp_bar
        lcl_x = x_bar_bar - consts["A2"] * disp_bar
        ucl_d = consts["D4"] * disp_bar
        lcl_d = consts["D3"] * disp_bar
        label_disp, label_ucl_d, label_lcl_d = "R̄", "UCL_R", "LCL_R"
        formula_disp = f"D₄·R̄ = {consts['D4']:.4f}×{disp_bar:.4f}"
        formulas = {
            "ucl_x": f"x̄̄ + A₂·R̄ = {x_bar_bar:.4f} + {consts['A2']:.4f}×{disp_bar:.4f}",
            "lcl_x": f"x̄̄ − A₂·R̄ = {x_bar_bar:.4f} − {consts['A2']:.4f}×{disp_bar:.4f}",
            "sigma": f"R̄/d₂ = {disp_bar:.4f}/{d2:.4f}",
            "constantes": {"A2": consts["A2"], "d2": d2, "D3": consts["D3"], "D4": consts["D4"]},
        }
    else:  # xbar_s
        # c4 aproximado para estimación de sigma
        c4 = 1 - 1/(4*(n-1)) if n > 1 else 1.0
        sigma_est = disp_bar / c4
        ucl_x = x_bar_bar + consts["A3"] * disp_bar
        lcl_x = x_bar_bar - consts["A3"] * disp_bar
        ucl_d = consts["B4"] * disp_bar
        lcl_d = consts["B3"] * disp_bar
        label_disp, label_ucl_d, label_lcl_d = "S̄", "UCL_S", "LCL_S"
        formula_disp = f"B₄·S̄ = {consts['B4']:.4f}×{disp_bar:.4f}"
        formulas = {
            "ucl_x": f"x̄̄ + A₃·S̄ = {x_bar_bar:.4f} + {consts['A3']:.4f}×{disp_bar:.4f}",
            "lcl_x": f"x̄̄ − A₃·S̄ = {x_bar_bar:.4f} − {consts['A3']:.4f}×{disp_bar:.4f}",
            "sigma": f"S̄/c₄ = {disp_bar:.4f}/{c4:.4f}",
            "constantes": {"A3": consts["A3"], "c4": round(c4, 4), "B3": consts["B3"], "B4": consts["B4"]},
        }

    vx, ooc_x = apply_western_electric_rules(xbars, x_bar_bar, ucl_x, lcl_x, request.reglas_we)
    vd, ooc_d = apply_western_electric_rules(dispersiones, disp_bar, ucl_d, max(lcl_d, 0), [1])

    for i, sg in enumerate(subgroup_data):
        sg["ooc_xbar"] = i in ooc_x
        sg["ooc_disp"] = i in ooc_d

    proceso_estable = len(ooc_x) == 0 and len(ooc_d) == 0
    nombre_tipo = "X̄-R" if tipo == "xbar_r" else "X̄-S"

    interpretacion = (
        f"Proceso {'ESTABLE' if proceso_estable else 'INESTABLE'}. "
        f"x̄̄ = {x_bar_bar:.4f} | {label_disp} = {disp_bar:.4f} | σ̂ = {sigma_est:.4f}. "
        + (f"Se detectaron {len(set(ooc_x+ooc_d))} subgrupos con causas especiales." if not proceso_estable
           else "Sin causas especiales detectadas. Proceso apto para Fase II.")
    )

    limites = {
        "cl_x": x_bar_bar, "ucl_x": ucl_x, "lcl_x": lcl_x,
        "cl_disp": disp_bar, "ucl_disp": ucl_d, "lcl_disp": max(lcl_d, 0),
        "sigma": sigma_est, "media": x_bar_bar,
        "cl_chart1": x_bar_bar, "ucl_chart1": ucl_x, "lcl_chart1": lcl_x,
        "cl_r_s_mr": disp_bar, "ucl_r_s_mr": ucl_d, "lcl_r_s_mr": max(lcl_d, 0),
    }

    analysis = Analysis(
        dataset_id=request.dataset_id, usuario_id=user_id,
        tipo=tipo, fase="I",
        nombre=request.nombre or f"{nombre_tipo} — {k} subgrupos × n={n}",
        tamano_subgrupo=n,
        parametros={"columnas": request.columnas, "n": n, "k": k, "tipo": tipo},
        resultados={"subgrupos": subgroup_data, "xbars": xbars.tolist(),
                    "dispersiones": dispersiones.tolist(), "ooc_xbar": ooc_x, "ooc_disp": ooc_d,
                    "proceso_estable": proceso_estable},
        limites_control=limites, interpretacion=interpretacion,
        puntos_excluidos=list(excluidos), estado="completado",
    )
    db.add(analysis); db.commit(); db.refresh(analysis)

    return {
        "analisis_id": analysis.id, "tipo": tipo, "nombre_tipo": nombre_tipo,
        "n": n, "k": k, "k_usados": len(mask), "columnas": request.columnas,
        "resumen": {
            "x_bar_bar": round(x_bar_bar, 6), "disp_bar": round(disp_bar, 6),
            "sigma_estimado": round(sigma_est, 6), "label_disp": label_disp,
        },
        "limites_xbar": {"cl": round(x_bar_bar,6), "ucl": round(ucl_x,6), "lcl": round(lcl_x,6)},
        "limites_disp": {"cl": round(disp_bar,6), "ucl": round(ucl_d,6), "lcl": round(max(lcl_d,0),6),
                         "label": label_disp, "label_ucl": label_ucl_d, "label_lcl": label_lcl_d},
        "subgrupos": subgroup_data,
        "ooc_xbar": ooc_x, "ooc_disp": ooc_d,
        "violaciones_xbar": [{"regla": v.regla, "nombre": v.nombre, "puntos": v.puntos_afectados,
                               "interpretacion": v.interpretacion, "severidad": v.severidad} for v in vx],
        "violaciones_disp": [{"regla": v.regla, "nombre": v.nombre, "puntos": v.puntos_afectados} for v in vd],
        "proceso_estable": proceso_estable,
        "apto_para_fase2": proceso_estable,
        "interpretacion": interpretacion,
        "formulas": formulas, "limites_fase2": limites,
    }


def _analyze_imr(request: VariablesChartRequest, df: pd.DataFrame, user_id: int, db):
    """Carta de Individuales y Rango Móvil (I-MR)."""
    if len(request.columnas) != 1:
        raise HTTPException(400, detail="I-MR requiere exactamente 1 columna (observaciones individuales)")

    col = request.columnas[0]
    series = pd.to_numeric(df[col], errors="coerce").dropna()
    if len(series) < 5:
        raise HTTPException(400, detail="I-MR necesita al menos 5 observaciones individuales")

    vals = series.values
    n_obs = len(vals)
    excluidos = set(request.puntos_excluidos)
    mask = [i for i in range(n_obs) if i not in excluidos]

    # Rangos móviles (span 2)
    mr = np.abs(np.diff(vals))
    mr_full = np.concatenate([[np.nan], mr])  # MR₁ = N/A

    vals_clean = vals[mask]
    mr_clean = mr[[i for i in range(n_obs-1) if i+1 in mask and i in mask]]

    d2 = 1.128   # constante para span = 2
    D4 = 3.267   # D₄ para n=2
    D3 = 0.000

    x_bar = float(np.mean(vals_clean))
    mr_bar = float(np.mean(mr_clean)) if len(mr_clean) > 0 else float(np.mean(mr))
    sigma_est = mr_bar / d2

    ucl_i = x_bar + 3 * sigma_est
    lcl_i = x_bar - 3 * sigma_est
    ucl_mr = D4 * mr_bar
    lcl_mr = 0.0

    vi, ooc_i   = apply_western_electric_rules(vals, x_bar, ucl_i, lcl_i, request.reglas_we)
    _, ooc_mr = apply_western_electric_rules(
        np.array([v for v in mr_full if not np.isnan(v)]), mr_bar, ucl_mr, lcl_mr, [1]
    )

    obs_data = []
    for i, v in enumerate(vals):
        mr_val = float(mr_full[i]) if not np.isnan(mr_full[i]) else None
        obs_data.append({
            "observacion": i + 1, "valor": round(float(v), 4),
            "rango_movil": round(mr_val, 4) if mr_val is not None else None,
            "ooc_i": i in ooc_i, "ooc_mr": (i-1) in ooc_mr if i > 0 else False,
            "excluido": i in excluidos,
        })

    proceso_estable = len(ooc_i) == 0 and len(ooc_mr) == 0
    interpretacion = (
        f"I-MR: proceso {'ESTABLE' if proceso_estable else 'INESTABLE'}. "
        f"X̄ = {x_bar:.4f} | MR̄ = {mr_bar:.4f} | σ̂ = R̄/d₂ = {sigma_est:.4f}."
    )

    limites = {
        "cl_x": x_bar, "ucl_x": ucl_i, "lcl_x": lcl_i,
        "cl_mr": mr_bar, "ucl_mr": ucl_mr, "lcl_mr": lcl_mr,
        "sigma": sigma_est, "media": x_bar,
        "cl_chart1": x_bar, "ucl_chart1": ucl_i, "lcl_chart1": lcl_i,
        "cl_r_s_mr": mr_bar, "ucl_r_s_mr": ucl_mr, "lcl_r_s_mr": lcl_mr,
    }

    analysis = Analysis(
        dataset_id=request.dataset_id, usuario_id=user_id,
        tipo="imr", fase="I",
        nombre=request.nombre or f"I-MR — {col} ({n_obs} obs.)",
        tamano_subgrupo=1,
        parametros={"columna": col, "n": n_obs, "tipo": "imr"},
        resultados={"observaciones": obs_data, "valores": vals.tolist(),
                    "rangos_moviles": [float(v) if not np.isnan(v) else None for v in mr_full],
                    "ooc_i": ooc_i, "ooc_mr": ooc_mr, "proceso_estable": proceso_estable},
        limites_control=limites, interpretacion=interpretacion,
        puntos_excluidos=list(excluidos), estado="completado",
    )
    db.add(analysis); db.commit(); db.refresh(analysis)

    return {
        "analisis_id": analysis.id, "tipo": "imr", "nombre_tipo": "I-MR",
        "n": 1, "k": n_obs, "k_usados": len(mask), "columnas": request.columnas,
        "resumen": {
            "x_bar": round(x_bar, 6), "mr_bar": round(mr_bar, 6),
            "sigma_estimado": round(sigma_est, 6),
            "d2": d2, "D3": D3, "D4": D4,
        },
        "limites_xbar": {"cl": round(x_bar,6), "ucl": round(ucl_i,6), "lcl": round(lcl_i,6)},
        "limites_disp": {"cl": round(mr_bar,6), "ucl": round(ucl_mr,6), "lcl": 0.0,
                         "label": "MR̄", "label_ucl": "UCL_MR", "label_lcl": "LCL_MR"},
        "subgrupos": obs_data,
        "ooc_xbar": ooc_i, "ooc_disp": ooc_mr,
        "violaciones_xbar": [{"regla": v.regla, "nombre": v.nombre, "puntos": v.puntos_afectados,
                               "interpretacion": v.interpretacion, "severidad": v.severidad} for v in vi],
        "violaciones_disp": [],
        "proceso_estable": proceso_estable,
        "apto_para_fase2": proceso_estable,
        "interpretacion": interpretacion,
        "formulas": {
            "ucl_x": f"X̄ + 3·MR̄/d₂ = {x_bar:.4f} + 3×{sigma_est:.4f}",
            "lcl_x": f"X̄ − 3·MR̄/d₂ = {x_bar:.4f} − 3×{sigma_est:.4f}",
            "sigma": f"MR̄/d₂ = {mr_bar:.4f}/{d2}",
            "ucl_mr": f"D₄·MR̄ = {D4}×{mr_bar:.4f}",
            "constantes": {"d2": d2, "D3": D3, "D4": D4},
        },
        "limites_fase2": limites,
    }


@router.post("/xbar-r-subgroups")
def analyze_xbar_r_subgroups(
    request: XBarRRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Análisis X̄-R a partir de un dataset donde cada fila es un subgrupo
    y cada columna seleccionada es una observación dentro del subgrupo.
    Devuelve estadísticos por subgrupo + límites de control + violaciones WE.
    """
    dataset = _get_dataset_data(request.dataset_id, current_user.id, db)
    df = pd.DataFrame(dataset.datos or [])

    # Validar columnas
    missing = [c for c in request.columnas if c not in df.columns]
    if missing:
        raise HTTPException(400, detail=f"Columnas no encontradas: {missing}")
    if len(request.columnas) < 2:
        raise HTTPException(400, detail="Se necesitan al menos 2 columnas (tamaño de subgrupo n ≥ 2)")

    # Convertir a numérico y limpiar
    sub_df = df[request.columnas].apply(pd.to_numeric, errors="coerce")
    sub_df = sub_df.dropna(how="all")
    if len(sub_df) < 3:
        raise HTTPException(400, detail="Se necesitan al menos 3 subgrupos con datos válidos")

    n = len(request.columnas)       # tamaño del subgrupo
    k_total = len(sub_df)           # número total de subgrupos

    # ── Estadísticos por subgrupo ──────────────────────────────────────────
    subgroup_data = []
    for idx, (row_idx, row) in enumerate(sub_df.iterrows()):
        vals = row.dropna().values
        if len(vals) == 0:
            continue
        xi_bar = float(np.mean(vals))
        ri = float(np.max(vals) - np.min(vals))
        subgroup_data.append({
            "subgrupo": idx + 1,
            "observaciones": [round(float(v), 4) for v in vals],
            "media": round(xi_bar, 4),
            "rango": round(ri, 4),
        })

    k = len(subgroup_data)
    if k < 3:
        raise HTTPException(400, detail="Datos insuficientes para el análisis")

    excluidos = set(request.puntos_excluidos)
    mask = [i for i in range(k) if i not in excluidos]

    xbars = np.array([sg["media"] for sg in subgroup_data])
    ranges = np.array([sg["rango"] for sg in subgroup_data])

    xbars_clean = xbars[mask]
    ranges_clean = ranges[mask]

    # ── Constantes y límites ───────────────────────────────────────────────
    consts = get_constants(n)
    d2 = consts["d2"]
    A2 = consts["A2"]
    D3 = consts["D3"]
    D4 = consts["D4"]

    x_bar_bar = float(np.mean(xbars_clean))   # media de las medias (x̄̄)
    R_bar = float(np.mean(ranges_clean))       # media de los rangos (R̄)
    sigma_estimado = R_bar / d2                # estimación de sigma del proceso

    # Carta X̄
    ucl_x = x_bar_bar + A2 * R_bar
    lcl_x = x_bar_bar - A2 * R_bar

    # Carta R
    ucl_r = D4 * R_bar
    lcl_r = D3 * R_bar                        # 0 para n < 7

    # ── Detección de causas especiales ────────────────────────────────────
    violations_x, ooc_x = apply_western_electric_rules(
        xbars, x_bar_bar, ucl_x, lcl_x, request.reglas_we
    )
    violations_r, ooc_r = apply_western_electric_rules(
        ranges, R_bar, ucl_r, max(lcl_r, 0), [1]
    )

    proceso_estable = len(ooc_x) == 0 and len(ooc_r) == 0

    # ── Añadir estado OOC a cada subgrupo ─────────────────────────────────
    for i, sg in enumerate(subgroup_data):
        sg["ooc_xbar"] = i in ooc_x
        sg["ooc_rango"] = i in ooc_r
        sg["excluido"] = i in excluidos

    # ── Interpretación automática ─────────────────────────────────────────
    pct_exc = len(excluidos) / k if k > 0 else 0
    if proceso_estable:
        interpretacion = (
            f"El proceso muestra estabilidad estadística. "
            f"x̄̄ = {x_bar_bar:.4f} | R̄ = {R_bar:.4f} | σ estimada = {sigma_estimado:.4f}. "
            f"Ningún subgrupo viola las reglas de control. Proceso apto para Fase II."
        )
    else:
        n_ooc = len(set(ooc_x + ooc_r))
        interpretacion = (
            f"Se detectaron {n_ooc} subgrupos con causas especiales. "
            f"x̄̄ = {x_bar_bar:.4f} | R̄ = {R_bar:.4f} | σ estimada = {sigma_estimado:.4f}. "
            f"Investigar y eliminar causas especiales antes de proceder a Fase II."
        )

    # ── Guardar análisis ───────────────────────────────────────────────────
    limites = {
        "cl_x": x_bar_bar, "ucl_x": ucl_x, "lcl_x": lcl_x,
        "cl_r": R_bar, "ucl_r": ucl_r, "lcl_r": lcl_r,
        "sigma": sigma_estimado, "media": x_bar_bar,
        # Alias para compatibilidad con Fase II
        "cl_chart1": x_bar_bar, "ucl_chart1": ucl_x, "lcl_chart1": lcl_x,
        "cl_r_s_mr": R_bar, "ucl_r_s_mr": ucl_r, "lcl_r_s_mr": lcl_r,
    }

    analysis = Analysis(
        dataset_id=request.dataset_id,
        usuario_id=current_user.id,
        tipo="xbar_r",
        fase="I",
        nombre=request.nombre or f"X̄-R — {k} subgrupos × n={n}",
        tamano_subgrupo=n,
        parametros={"columnas": request.columnas, "n": n, "k": k},
        resultados={
            "subgrupos": subgroup_data,
            "xbars": xbars.tolist(),
            "rangos": ranges.tolist(),
            "ooc_xbar": ooc_x,
            "ooc_rango": ooc_r,
            "proceso_estable": proceso_estable,
        },
        limites_control=limites,
        interpretacion=interpretacion,
        puntos_excluidos=list(excluidos),
        estado="completado",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    return {
        "analisis_id": analysis.id,
        "n": n,
        "k": k,
        "k_usados": len(mask),
        "columnas": request.columnas,
        # Estadísticos globales
        "resumen": {
            "x_bar_bar": round(x_bar_bar, 6),
            "R_bar": round(R_bar, 6),
            "sigma_estimado": round(sigma_estimado, 6),
            "d2": d2, "A2": A2, "D3": D3, "D4": D4,
        },
        # Límites
        "limites_xbar": {"cl": round(x_bar_bar, 6), "ucl": round(ucl_x, 6), "lcl": round(lcl_x, 6)},
        "limites_rango": {"cl": round(R_bar, 6), "ucl": round(ucl_r, 6), "lcl": round(max(lcl_r, 0), 6)},
        # Datos por subgrupo (para tabla y gráfico)
        "subgrupos": subgroup_data,
        # Puntos fuera de control
        "ooc_xbar": ooc_x,
        "ooc_rango": ooc_r,
        "violaciones_xbar": [
            {"regla": v.regla, "nombre": v.nombre, "puntos": v.puntos_afectados,
             "interpretacion": v.interpretacion, "severidad": v.severidad}
            for v in violations_x
        ],
        "violaciones_rango": [
            {"regla": v.regla, "nombre": v.nombre, "puntos": v.puntos_afectados}
            for v in violations_r
        ],
        "proceso_estable": proceso_estable,
        "apto_para_fase2": proceso_estable and pct_exc <= 0.20,
        "interpretacion": interpretacion,
        "limites_fase2": limites,  # para pasar directamente a Fase II
    }


def _serialize_phase1_result(result) -> dict:
    """Serializa el resultado de Fase I para JSON."""
    final = result.resultado_final
    return {
        "tipo_grafico": result.tipo_grafico,
        "fase": "I",
        "iteraciones": result.iteraciones,
        "proceso_estable": result.proceso_estable,
        "apto_para_fase2": result.apto_para_fase2,
        "limites": {
            "cl_chart1": final.cl_chart1, "ucl_chart1": final.ucl_chart1,
            "lcl_chart1": final.lcl_chart1, "cl_chart2": final.cl_chart2,
            "ucl_chart2": final.ucl_chart2, "lcl_chart2": final.lcl_chart2,
        },
        "datos": {
            "values_chart1": final.values_chart1,
            "values_chart2": [v for v in (final.values_chart2 or [])],
            "ooc_chart1": final.ooc_chart1,
            "ooc_chart2": final.ooc_chart2,
            "subgrupos": final.subgrupos,
            "tamano_subgrupo": final.tamano_subgrupo,
            "n_subgrupos": final.n_subgrupos,
        },
        "estadisticos": {
            "sigma_proceso": result.sigma_proceso,
            "media_proceso": result.media_proceso,
            "n_puntos_originales": result.n_puntos_originales,
            "n_puntos_excluidos": result.n_puntos_excluidos,
            "porcentaje_excluido": result.porcentaje_excluido,
        },
        "exclusiones": [
            {
                "punto_indice": e.punto_indice, "iteracion": e.iteracion,
                "razon": e.razon, "reglas_violadas": e.reglas_violadas, "valor": e.valor,
            }
            for e in result.exclusiones
        ],
        "historial_iteraciones": result.historial_iteraciones,
        "diagnostico": result.diagnostico,
        "recomendaciones": result.recomendaciones,
        "advertencias": result.advertencias,
        "limites_establecidos": result.limites_establecidos,
    }
