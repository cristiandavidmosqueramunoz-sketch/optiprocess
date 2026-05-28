"""
OptiProcess - Motor de cálculo para gráficos de control por variables y atributos.
Implementación de X̄-R, X̄-S, I-MR, p, np, c, u con constantes estadísticas.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

# ─── Constantes para gráficos de control (ISO 8258 / Montgomery) ────────────
CONTROL_CHART_CONSTANTS = {
    2:  {"A2": 1.880, "A3": 2.659, "B3": 0.000, "B4": 3.267, "d2": 1.128, "d3": 0.853, "D3": 0.000, "D4": 3.267},
    3:  {"A2": 1.023, "A3": 1.954, "B3": 0.000, "B4": 2.568, "d2": 1.693, "d3": 0.888, "D3": 0.000, "D4": 2.574},
    4:  {"A2": 0.729, "A3": 1.628, "B3": 0.000, "B4": 2.266, "d2": 2.059, "d3": 0.880, "D3": 0.000, "D4": 2.282},
    5:  {"A2": 0.577, "A3": 1.427, "B3": 0.000, "B4": 2.089, "d2": 2.326, "d3": 0.864, "D3": 0.000, "D4": 2.114},
    6:  {"A2": 0.483, "A3": 1.287, "B3": 0.030, "B4": 1.970, "d2": 2.534, "d3": 0.848, "D3": 0.000, "D4": 2.004},
    7:  {"A2": 0.419, "A3": 1.182, "B3": 0.118, "B4": 1.882, "d2": 2.704, "d3": 0.833, "D3": 0.076, "D4": 1.924},
    8:  {"A2": 0.373, "A3": 1.099, "B3": 0.185, "B4": 1.815, "d2": 2.847, "d3": 0.820, "D3": 0.136, "D4": 1.864},
    9:  {"A2": 0.337, "A3": 1.032, "B3": 0.239, "B4": 1.761, "d2": 2.970, "d3": 0.808, "D3": 0.184, "D4": 1.816},
    10: {"A2": 0.308, "A3": 0.975, "B3": 0.284, "B4": 1.716, "d2": 3.078, "d3": 0.797, "D3": 0.223, "D4": 1.777},
    15: {"A2": 0.223, "A3": 0.789, "B3": 0.428, "B4": 1.572, "d2": 3.472, "d3": 0.756, "D3": 0.347, "D4": 1.653},
    20: {"A2": 0.180, "A3": 0.680, "B3": 0.510, "B4": 1.490, "d2": 3.735, "d3": 0.729, "D3": 0.415, "D4": 1.585},
    25: {"A2": 0.153, "A3": 0.606, "B3": 0.565, "B4": 1.435, "d2": 3.931, "d3": 0.708, "D3": 0.459, "D4": 1.541},
}


def get_constants(n: int) -> Dict[str, float]:
    """Obtener constantes para tamaño de subgrupo n (interpolación si es necesario)."""
    sizes = sorted(CONTROL_CHART_CONSTANTS.keys())
    if n in CONTROL_CHART_CONSTANTS:
        return CONTROL_CHART_CONSTANTS[n]
    # Interpolación lineal para tamaños no tabulados
    for i in range(len(sizes)-1):
        if sizes[i] < n < sizes[i+1]:
            k = (n - sizes[i]) / (sizes[i+1] - sizes[i])
            c1 = CONTROL_CHART_CONSTANTS[sizes[i]]
            c2 = CONTROL_CHART_CONSTANTS[sizes[i+1]]
            return {key: c1[key] + k * (c2[key] - c1[key]) for key in c1}
    return CONTROL_CHART_CONSTANTS[sizes[-1]]


@dataclass
class ChartLimits:
    cl: float
    ucl: float
    lcl: float
    sigma: float


@dataclass
class ControlChartResult:
    tipo: str
    fase: str
    # Carta principal (X̄ o Individuales)
    values_chart1: List[float]
    cl_chart1: float
    ucl_chart1: float
    lcl_chart1: float
    # Carta secundaria (R, S, o MR)
    values_chart2: List[float]
    cl_chart2: float
    ucl_chart2: float
    lcl_chart2: float = 0.0
    # Metadatos
    subgrupos: List[int] = field(default_factory=list)
    tamano_subgrupo: int = 1
    n_subgrupos: int = 0
    # Control
    ooc_chart1: List[int] = field(default_factory=list)
    ooc_chart2: List[int] = field(default_factory=list)
    process_stable: bool = True
    # Estimaciones
    sigma_proceso: float = 0.0
    media_proceso: float = 0.0
    # Interpretación
    interpretacion: str = ""
    recomendaciones: List[str] = field(default_factory=list)


def calculate_xbar_r(data: np.ndarray, subgroup_size: int, excluded: List[int] = None) -> ControlChartResult:
    """Calcula carta X̄-R para subgrupos de tamaño fijo."""
    excluded = excluded or []
    constants = get_constants(subgroup_size)
    n_subgroups = len(data) // subgroup_size

    subgroups = data[:n_subgroups * subgroup_size].reshape(n_subgroups, subgroup_size)
    subgroup_indices = list(range(n_subgroups))

    # Calcular medias y rangos
    xbars = np.mean(subgroups, axis=1)
    ranges = np.ptp(subgroups, axis=1)

    # Filtrar excluidos para estimación de límites
    mask = np.ones(n_subgroups, dtype=bool)
    for idx in excluded:
        if 0 <= idx < n_subgroups:
            mask[idx] = False

    xbars_clean = xbars[mask]
    ranges_clean = ranges[mask]

    # Límites carta R
    R_bar = np.mean(ranges_clean)
    cl_r = R_bar
    ucl_r = constants["D4"] * R_bar
    lcl_r = constants["D3"] * R_bar

    # Límites carta X̄
    X_bar_bar = np.mean(xbars_clean)
    cl_x = X_bar_bar
    ucl_x = X_bar_bar + constants["A2"] * R_bar
    lcl_x = X_bar_bar - constants["A2"] * R_bar

    # Estimación de sigma del proceso
    d2 = constants["d2"]
    sigma_estimado = R_bar / d2

    return ControlChartResult(
        tipo="xbar_r",
        fase="I",
        values_chart1=xbars.tolist(),
        cl_chart1=cl_x,
        ucl_chart1=ucl_x,
        lcl_chart1=lcl_x,
        values_chart2=ranges.tolist(),
        cl_chart2=cl_r,
        ucl_chart2=ucl_r,
        lcl_chart2=max(0, lcl_r),
        subgrupos=subgroup_indices,
        tamano_subgrupo=subgroup_size,
        n_subgrupos=n_subgroups,
        sigma_proceso=sigma_estimado,
        media_proceso=X_bar_bar,
    )


def calculate_xbar_s(data: np.ndarray, subgroup_size: int, excluded: List[int] = None) -> ControlChartResult:
    """Calcula carta X̄-S para subgrupos (preferido para n >= 10)."""
    excluded = excluded or []
    constants = get_constants(subgroup_size)
    n_subgroups = len(data) // subgroup_size

    subgroups = data[:n_subgroups * subgroup_size].reshape(n_subgroups, subgroup_size)
    xbars = np.mean(subgroups, axis=1)
    stds = np.std(subgroups, axis=1, ddof=1)

    mask = np.ones(n_subgroups, dtype=bool)
    for idx in excluded:
        if 0 <= idx < n_subgroups:
            mask[idx] = False

    xbars_clean = xbars[mask]
    stds_clean = stds[mask]

    S_bar = np.mean(stds_clean)
    X_bar_bar = np.mean(xbars_clean)

    # Límites carta S
    cl_s = S_bar
    ucl_s = constants["B4"] * S_bar
    lcl_s = constants["B3"] * S_bar

    # Límites carta X̄
    cl_x = X_bar_bar
    ucl_x = X_bar_bar + constants["A3"] * S_bar
    lcl_x = X_bar_bar - constants["A3"] * S_bar

    # c4 para estimación de sigma
    c4 = 1 - 1/(4*(subgroup_size-1)) if subgroup_size > 1 else 1
    sigma_estimado = S_bar / c4

    return ControlChartResult(
        tipo="xbar_s",
        fase="I",
        values_chart1=xbars.tolist(),
        cl_chart1=cl_x,
        ucl_chart1=ucl_x,
        lcl_chart1=lcl_x,
        values_chart2=stds.tolist(),
        cl_chart2=cl_s,
        ucl_chart2=ucl_s,
        lcl_chart2=max(0, lcl_s),
        subgrupos=list(range(n_subgroups)),
        tamano_subgrupo=subgroup_size,
        n_subgroups=n_subgroups,
        sigma_proceso=sigma_estimado,
        media_proceso=X_bar_bar,
    )


def calculate_imr(data: np.ndarray, excluded: List[int] = None) -> ControlChartResult:
    """Calcula carta Individuales - Rango Móvil (I-MR)."""
    excluded = excluded or []
    n = len(data)

    # Rangos móviles
    mr = np.abs(np.diff(data))
    mr_full = np.concatenate([[np.nan], mr])

    mask = np.ones(n, dtype=bool)
    for idx in excluded:
        if 0 <= idx < n:
            mask[idx] = False

    data_clean = data[mask]
    mr_clean = mr[mask[1:] & mask[:-1]]

    # Constantes para n=2 (rango móvil)
    d2 = 1.128
    D3 = 0.000
    D4 = 3.267

    MR_bar = np.mean(mr_clean)
    X_bar = np.mean(data_clean)
    sigma_estimado = MR_bar / d2

    # Carta de Individuales
    cl_i = X_bar
    ucl_i = X_bar + 3 * sigma_estimado
    lcl_i = X_bar - 3 * sigma_estimado

    # Carta MR
    cl_mr = MR_bar
    ucl_mr = D4 * MR_bar
    lcl_mr = D3 * MR_bar

    return ControlChartResult(
        tipo="imr",
        fase="I",
        values_chart1=data.tolist(),
        cl_chart1=cl_i,
        ucl_chart1=ucl_i,
        lcl_chart1=lcl_i,
        values_chart2=[v if not np.isnan(v) else None for v in mr_full.tolist()],
        cl_chart2=cl_mr,
        ucl_chart2=ucl_mr,
        lcl_chart2=lcl_mr,
        subgrupos=list(range(n)),
        tamano_subgrupo=1,
        n_subgrupos=n,
        sigma_proceso=sigma_estimado,
        media_proceso=X_bar,
    )


def calculate_p_chart(
    n_defectives: np.ndarray,
    sample_sizes: np.ndarray,
    excluded: List[int] = None,
) -> ControlChartResult:
    """Calcula carta p (proporción de no conformidades). Soporta n variable."""
    excluded = excluded or []
    k = len(n_defectives)

    mask = np.ones(k, dtype=bool)
    for idx in excluded:
        if 0 <= idx < k:
            mask[idx] = False

    p_i = n_defectives / sample_sizes
    p_bar = np.sum(n_defectives[mask]) / np.sum(sample_sizes[mask])

    # Límites individuales por subgrupo (n variable)
    ucl_i = p_bar + 3 * np.sqrt(p_bar * (1 - p_bar) / sample_sizes)
    lcl_i = np.maximum(0, p_bar - 3 * np.sqrt(p_bar * (1 - p_bar) / sample_sizes))

    # Para visualización, usar n promedio para las líneas centrales
    n_promedio = np.mean(sample_sizes[mask])
    sigma_p = np.sqrt(p_bar * (1 - p_bar) / n_promedio)
    ucl_p = p_bar + 3 * sigma_p
    lcl_p = max(0, p_bar - 3 * sigma_p)

    return ControlChartResult(
        tipo="p",
        fase="I",
        values_chart1=p_i.tolist(),
        cl_chart1=p_bar,
        ucl_chart1=ucl_p,
        lcl_chart1=lcl_p,
        values_chart2=sample_sizes.tolist(),
        cl_chart2=n_promedio,
        ucl_chart2=n_promedio * 1.5,
        lcl_chart2=max(1, n_promedio * 0.5),
        subgrupos=list(range(k)),
        tamano_subgrupo=int(n_promedio),
        n_subgrupos=k,
        sigma_proceso=sigma_p,
        media_proceso=p_bar,
    )


def calculate_np_chart(
    n_defectives: np.ndarray,
    n: int,
    excluded: List[int] = None,
) -> ControlChartResult:
    """Calcula carta np (número de no conformidades, tamaño fijo)."""
    excluded = excluded or []
    k = len(n_defectives)

    mask = np.ones(k, dtype=bool)
    for idx in excluded:
        if 0 <= idx < k:
            mask[idx] = False

    np_bar = np.mean(n_defectives[mask])
    p_bar = np_bar / n
    sigma_np = np.sqrt(n * p_bar * (1 - p_bar))

    cl = np_bar
    ucl = np_bar + 3 * sigma_np
    lcl = max(0, np_bar - 3 * sigma_np)

    return ControlChartResult(
        tipo="np",
        fase="I",
        values_chart1=n_defectives.tolist(),
        cl_chart1=cl,
        ucl_chart1=ucl,
        lcl_chart1=lcl,
        values_chart2=[n] * k,
        cl_chart2=float(n),
        ucl_chart2=float(n),
        lcl_chart2=float(n),
        subgrupos=list(range(k)),
        tamano_subgrupo=n,
        n_subgrupos=k,
        sigma_proceso=sigma_np,
        media_proceso=np_bar,
    )


def calculate_c_chart(
    defects_per_unit: np.ndarray,
    excluded: List[int] = None,
) -> ControlChartResult:
    """Calcula carta c (defectos por unidad, área de oportunidad fija)."""
    excluded = excluded or []
    k = len(defects_per_unit)

    mask = np.ones(k, dtype=bool)
    for idx in excluded:
        if 0 <= idx < k:
            mask[idx] = False

    c_bar = np.mean(defects_per_unit[mask])
    sigma_c = np.sqrt(c_bar)

    cl = c_bar
    ucl = c_bar + 3 * sigma_c
    lcl = max(0, c_bar - 3 * sigma_c)

    return ControlChartResult(
        tipo="c",
        fase="I",
        values_chart1=defects_per_unit.tolist(),
        cl_chart1=cl,
        ucl_chart1=ucl,
        lcl_chart1=lcl,
        values_chart2=[1.0] * k,
        cl_chart2=1.0,
        ucl_chart2=1.0,
        lcl_chart2=1.0,
        subgrupos=list(range(k)),
        tamano_subgrupo=1,
        n_subgrupos=k,
        sigma_proceso=sigma_c,
        media_proceso=c_bar,
    )


def calculate_u_chart(
    defects: np.ndarray,
    units: np.ndarray,
    excluded: List[int] = None,
) -> ControlChartResult:
    """Calcula carta u (defectos por unidad, área variable)."""
    excluded = excluded or []
    k = len(defects)

    mask = np.ones(k, dtype=bool)
    for idx in excluded:
        if 0 <= idx < k:
            mask[idx] = False

    u_i = defects / units
    u_bar = np.sum(defects[mask]) / np.sum(units[mask])

    n_prom = np.mean(units[mask])
    sigma_u = np.sqrt(u_bar / n_prom)

    cl = u_bar
    ucl = u_bar + 3 * sigma_u
    lcl = max(0, u_bar - 3 * sigma_u)

    return ControlChartResult(
        tipo="u",
        fase="I",
        values_chart1=u_i.tolist(),
        cl_chart1=cl,
        ucl_chart1=ucl,
        lcl_chart1=lcl,
        values_chart2=units.tolist(),
        cl_chart2=n_prom,
        ucl_chart2=n_prom * 1.5,
        lcl_chart2=max(1, n_prom * 0.5),
        subgrupos=list(range(k)),
        tamano_subgrupo=int(n_prom),
        n_subgrupos=k,
        sigma_proceso=sigma_u,
        media_proceso=u_bar,
    )
