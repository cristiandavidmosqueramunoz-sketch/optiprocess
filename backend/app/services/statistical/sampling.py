"""
OptiProcess - Diseño de planes de muestreo de aceptación.
Calcula planes simples, dobles, curvas OC, AOQ, ATI para niveles AQL/LTPD.
"""
import numpy as np
from scipy import stats
from scipy.stats import binom, hypergeom
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import math


@dataclass
class SingleSamplingPlan:
    """Plan de muestreo simple."""
    N: int       # Tamaño del lote
    n: int       # Tamaño de muestra
    c: int       # Número de aceptación
    r: int       # Número de rechazo
    aql: float
    ltpd: Optional[float]
    alpha: float  # Riesgo del productor
    beta: float   # Riesgo del consumidor
    # Curva OC
    oc_curve: Dict[str, List[float]]
    # AOQ y ATI
    aoq_curve: Dict[str, List[float]]
    ati_curve: Dict[str, List[float]]
    aoq_max: float   # AOQL
    # Interpretación
    interpretacion: str
    descripcion_plan: str


def design_single_sampling_plan(
    N: int,
    aql: float,
    ltpd: Optional[float] = None,
    alpha: float = 0.05,
    beta: float = 0.10,
    nivel_inspeccion: str = "II",
) -> SingleSamplingPlan:
    """
    Diseña un plan de muestreo simple óptimo para los parámetros dados.
    Usa distribución binomial para lotes grandes.
    """
    p1 = aql / 100.0 if aql > 1 else aql
    p2 = ltpd / 100.0 if ltpd and ltpd > 1 else (ltpd or p1 * 5)

    # Búsqueda del plan óptimo
    best_n, best_c = _find_single_plan(p1, p2, alpha, beta)

    # Si no se encontró, usar heurística
    if best_n is None:
        best_n = max(10, int(np.log(beta) / np.log(1 - p2)))
        best_c = max(0, int(best_n * p1))

    # Ajustar n al tamaño del lote
    n = min(best_n, N)
    c = best_c
    r = c + 1

    # Calcular curvas
    p_range = np.linspace(0, min(0.5, p2 * 3), 100)
    oc_pa = [float(binom.cdf(c, n, p)) for p in p_range]

    # AOQ = P(aceptar) * p * (N - n) / N
    aoq_vals = [pa * p * (N - n) / N for pa, p in zip(oc_pa, p_range)]
    aoq_max = float(max(aoq_vals))
    aoq_max_p = float(p_range[np.argmax(aoq_vals)])

    # ATI = n + (1 - Pa) * (N - n)
    ati_vals = [n + (1 - pa) * (N - n) for pa in oc_pa]

    oc_curve = {"p": p_range.tolist(), "pa": oc_pa}
    aoq_curve = {"p": p_range.tolist(), "aoq": aoq_vals, "aoq_max": aoq_max, "p_aoql": aoq_max_p}
    ati_curve = {"p": p_range.tolist(), "ati": ati_vals}

    # Verificar riesgos
    pa_at_aql = float(binom.cdf(c, n, p1))
    pa_at_ltpd = float(binom.cdf(c, n, p2))
    alpha_actual = 1 - pa_at_aql
    beta_actual = pa_at_ltpd

    interpretacion = (
        f"Plan de muestreo simple: n = {n}, c = {c}. "
        f"Riesgo del productor α = {alpha_actual:.3f} en AQL = {p1*100:.1f}%. "
        f"Riesgo del consumidor β = {beta_actual:.3f} en LTPD = {p2*100:.1f}%. "
        f"AOQL = {aoq_max*100:.3f}% (en p = {aoq_max_p*100:.2f}%)."
    )

    descripcion = (
        f"Inspeccionar {n} unidades del lote de {N}. "
        f"Aceptar si defectuosos ≤ {c}. Rechazar si defectuosos ≥ {r}."
    )

    return SingleSamplingPlan(
        N=N, n=n, c=c, r=r,
        aql=p1, ltpd=p2, alpha=alpha, beta=beta,
        oc_curve=oc_curve, aoq_curve=aoq_curve, ati_curve=ati_curve,
        aoq_max=aoq_max,
        interpretacion=interpretacion,
        descripcion_plan=descripcion,
    )


def _find_single_plan(p1: float, p2: float, alpha: float, beta: float) -> Tuple[Optional[int], Optional[int]]:
    """Búsqueda iterativa del plan n, c que cumple los riesgos especificados."""
    for c in range(0, 20):
        for n in range(c + 1, 2000):
            pa1 = float(binom.cdf(c, n, p1))
            pa2 = float(binom.cdf(c, n, p2))
            if pa1 >= (1 - alpha) and pa2 <= beta:
                return n, c
    return None, None


def design_double_sampling_plan(
    N: int,
    aql: float,
    alpha: float = 0.05,
    beta: float = 0.10,
) -> Dict[str, Any]:
    """
    Diseña un plan de muestreo doble.
    Incluye primera y segunda muestra con sus números de aceptación/rechazo.
    """
    p1 = aql / 100.0 if aql > 1 else aql

    # Regla aproximada: n2 = 2*n1
    n1 = max(10, int(np.log(beta) / np.log(1 - max(p1 * 5, 0.01))))
    n1 = min(n1, N // 2)
    n2 = min(n1 * 2, N - n1)

    c1 = max(0, int(n1 * p1 * 0.5))
    c2 = max(c1 + 1, int((n1 + n2) * p1 * 1.5))
    r1 = c2 + 1
    r2 = c2 + 1

    # Curva OC doble
    p_range = np.linspace(0, min(0.5, p1 * 15), 100)
    oc_pa = []
    for p in p_range:
        # P(aceptar en 1ª muestra)
        pa1 = binom.cdf(c1, n1, p)
        # P(continuar a 2ª muestra) = P(c1 < D1 < r1)
        if r1 > c1 + 1:
            p_2nd = binom.cdf(r1-1, n1, p) - binom.cdf(c1, n1, p)
        else:
            p_2nd = 0
        # P(aceptar en 2ª muestra | continuar)
        pa2 = 0
        for d1 in range(c1+1, r1):
            p_d1 = float(binom.pmf(d1, n1, p))
            pa_2nd = float(binom.cdf(c2 - d1, n2, p)) if c2 - d1 >= 0 else 0
            pa2 += p_d1 * pa_2nd
        oc_pa.append(float(pa1 + pa2))

    return {
        "tipo": "doble",
        "N": N, "n1": n1, "n2": n2,
        "c1": c1, "c2": c2, "r1": r1, "r2": r2,
        "aql": p1,
        "oc_curve": {"p": p_range.tolist(), "pa": oc_pa},
        "interpretacion": (
            f"Plan doble: 1ª muestra n₁={n1} (aceptar si d≤{c1}, rechazar si d≥{r1}). "
            f"2ª muestra n₂={n2} si d está entre {c1+1} y {r1-1} "
            f"(aceptar si d₁+d₂≤{c2}, rechazar si d₁+d₂>{c2})."
        ),
        "descripcion_plan": (
            f"Primera muestra: {n1} unidades. "
            f"Si ≤{c1} defectuosos → ACEPTAR. Si ≥{r1} → RECHAZAR. "
            f"Si entre {c1+1} y {r1-1} → Segunda muestra: {n2} unidades. "
            f"Aceptar si total ≤{c2}."
        ),
    }
