"""
OptiProcess - Análisis de Capacidad del Proceso: Cp, Cpk, Pp, Ppk y fracción no conforme.
"""
import numpy as np
from scipy import stats
from typing import Dict, Optional, List, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class CapabilityResult:
    """Resultado completo del análisis de capacidad."""
    # Parámetros de entrada
    usl: Optional[float]
    lsl: Optional[float]
    target: Optional[float]
    media: float
    std_within: float
    std_overall: float
    n: int
    # Índices de capacidad potencial
    cp: Optional[float]
    cpl: Optional[float]
    cpu: Optional[float]
    cpk: Optional[float]
    # Índices de desempeño (largo plazo)
    pp: Optional[float]
    ppl: Optional[float]
    ppu: Optional[float]
    ppk: Optional[float]
    # Fracción no conforme estimada (ppm)
    ppm_total_within: float
    ppm_abajo_within: float
    ppm_arriba_within: float
    ppm_total_overall: float
    # Semáforos y calificaciones
    calificacion_cpk: str
    calificacion_ppk: str
    color_cpk: str
    color_ppk: str
    # Interpretación
    interpretacion: str
    diagnostico: str
    recomendaciones: List[str]
    # Datos para histograma
    datos: List[float]
    curva_normal: Dict[str, Any]


def _semaforo(valor: Optional[float]) -> Tuple[str, str]:
    """Retorna (calificación, color) para un índice de capacidad."""
    if valor is None:
        return "N/A", "gray"
    if valor >= 1.67:
        return "Excelente (6σ)", "green"
    elif valor >= 1.33:
        return "Adecuado (4σ)", "blue"
    elif valor >= 1.00:
        return "Marginal (3σ)", "yellow"
    else:
        return "Inadecuado (<3σ)", "red"


def calculate_capability(
    data: np.ndarray,
    usl: Optional[float] = None,
    lsl: Optional[float] = None,
    target: Optional[float] = None,
    subgroup_size: Optional[int] = None,
    subgroup_column: Optional[np.ndarray] = None,
) -> CapabilityResult:
    """
    Calcula índices de capacidad Cp, Cpk, Pp, Ppk y fracción no conforme.
    """
    data = data[~np.isnan(data)]
    n = len(data)
    media = float(np.mean(data))
    std_overall = float(np.std(data, ddof=1))

    # Sigma dentro del subgrupo (corto plazo)
    if subgroup_size and subgroup_size > 1:
        n_sg = n // subgroup_size
        sgs = data[:n_sg * subgroup_size].reshape(n_sg, subgroup_size)
        ranges = np.ptp(sgs, axis=1)
        # Tabla d2 simplificada
        d2_map = {2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326, 6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970, 10: 3.078}
        d2 = d2_map.get(subgroup_size, 2.326)
        std_within = float(np.mean(ranges) / d2)
    else:
        # I-MR: sigma estimada por rangos móviles
        mr = np.abs(np.diff(data))
        std_within = float(np.mean(mr) / 1.128) if len(mr) > 0 else std_overall

    if std_within <= 0:
        std_within = std_overall

    # ── Índices de capacidad (corto plazo, sigma dentro) ──────────────────
    cp = cpl = cpu = cpk = None

    if usl is not None and lsl is not None:
        cp = (usl - lsl) / (6 * std_within)
    if lsl is not None:
        cpl = (media - lsl) / (3 * std_within)
    if usl is not None:
        cpu = (usl - media) / (3 * std_within)
    if cpl is not None and cpu is not None:
        cpk = min(cpl, cpu)
    elif cpl is not None:
        cpk = cpl
    elif cpu is not None:
        cpk = cpu

    # ── Índices de desempeño (largo plazo, sigma global) ──────────────────
    pp = ppl = ppu = ppk = None

    if usl is not None and lsl is not None:
        pp = (usl - lsl) / (6 * std_overall)
    if lsl is not None:
        ppl = (media - lsl) / (3 * std_overall)
    if usl is not None:
        ppu = (usl - media) / (3 * std_overall)
    if ppl is not None and ppu is not None:
        ppk = min(ppl, ppu)
    elif ppl is not None:
        ppk = ppl
    elif ppu is not None:
        ppk = ppu

    # ── Fracción no conforme (PPM) ─────────────────────────────────────────
    ppm_abajo = ppm_arriba = ppm_total = 0.0
    ppm_total_overall = 0.0

    if std_within > 0:
        if lsl is not None:
            z_bajo = (media - lsl) / std_within
            ppm_abajo = stats.norm.sf(z_bajo) * 1_000_000
        if usl is not None:
            z_alto = (usl - media) / std_within
            ppm_arriba = stats.norm.sf(z_alto) * 1_000_000
        ppm_total = ppm_abajo + ppm_arriba

    if std_overall > 0:
        ppm_abajo_overall = stats.norm.sf((media - lsl) / std_overall) * 1_000_000 if lsl else 0
        ppm_arriba_overall = stats.norm.sf((usl - media) / std_overall) * 1_000_000 if usl else 0
        ppm_total_overall = ppm_abajo_overall + ppm_arriba_overall

    # ── Semáforos visuales ────────────────────────────────────────────────
    cal_cpk, color_cpk = _semaforo(cpk)
    cal_ppk, color_ppk = _semaforo(ppk)

    # ── Curva normal para histograma ──────────────────────────────────────
    x_range = np.linspace(media - 4 * std_overall, media + 4 * std_overall, 200)
    curva_normal = {
        "x": x_range.tolist(),
        "y_within": stats.norm.pdf(x_range, media, std_within).tolist(),
        "y_overall": stats.norm.pdf(x_range, media, std_overall).tolist(),
        "media": media,
        "usl": usl,
        "lsl": lsl,
        "target": target,
    }

    interpretacion = _generate_interpretation(cpk, ppk, cp, pp, ppm_total)
    diagnostico = _generate_diagnostico(cpk, ppk, ppm_total)
    recomendaciones = _generate_recommendations(cpk, ppk, cp, pp, media, usl, lsl)

    return CapabilityResult(
        usl=usl, lsl=lsl, target=target,
        media=media, std_within=std_within, std_overall=std_overall, n=n,
        cp=cp, cpl=cpl, cpu=cpu, cpk=cpk,
        pp=pp, ppl=ppl, ppu=ppu, ppk=ppk,
        ppm_total_within=round(ppm_total, 2),
        ppm_abajo_within=round(ppm_abajo, 2),
        ppm_arriba_within=round(ppm_arriba, 2),
        ppm_total_overall=round(ppm_total_overall, 2),
        calificacion_cpk=cal_cpk, calificacion_ppk=cal_ppk,
        color_cpk=color_cpk, color_ppk=color_ppk,
        interpretacion=interpretacion,
        diagnostico=diagnostico,
        recomendaciones=recomendaciones,
        datos=data.tolist(),
        curva_normal=curva_normal,
    )


def _generate_interpretation(cpk, ppk, cp, pp, ppm):
    lineas = []
    if cpk is not None:
        if cpk >= 1.67:
            lineas.append(f"Cpk = {cpk:.3f} — Proceso capaz con excelente margen (nivel 6σ).")
        elif cpk >= 1.33:
            lineas.append(f"Cpk = {cpk:.3f} — Proceso adecuadamente capaz (nivel 4σ).")
        elif cpk >= 1.00:
            lineas.append(f"Cpk = {cpk:.3f} — Proceso marginalmente capaz. Mejora recomendada.")
        else:
            lineas.append(f"Cpk = {cpk:.3f} — Proceso NO capaz. Acción correctiva necesaria.")

    if ppm > 0:
        lineas.append(f"Fracción no conforme estimada: {ppm:,.0f} PPM ({ppm/10000:.4f}%).")

    if cp is not None and cpk is not None:
        diff = cp - cpk
        if diff > 0.1:
            lineas.append(
                f"Cp = {cp:.3f} vs Cpk = {cpk:.3f}: El proceso tiene potencial pero está descentrado. "
                "Centrar el proceso en el objetivo mejoraría significativamente la capacidad."
            )
    return " ".join(lineas)


def _generate_diagnostico(cpk, ppk, ppm):
    if cpk is None:
        return "⚠️ Sin especificaciones definidas — no se puede calcular capacidad."
    if cpk >= 1.67:
        return "✅ Proceso ALTAMENTE CAPAZ — cumple estándares industriales de clase mundial."
    elif cpk >= 1.33:
        return "✅ Proceso CAPAZ — cumple los requisitos de capacidad de la mayoría de industrias."
    elif cpk >= 1.00:
        return "⚠️ Proceso MARGINALMENTE CAPAZ — requiere monitoreo estrecho y mejora continua."
    else:
        return f"🚨 Proceso NO CAPAZ — se producen aproximadamente {ppm:,.0f} PPM fuera de especificación."


def _generate_recommendations(cpk, ppk, cp, pp, media, usl, lsl):
    recs = []
    if cpk is None:
        recs.append("Definir límites de especificación (LSL/USL) con el área de ingeniería.")
        return recs

    if cpk < 1.00:
        recs.append("PRIORIDAD ALTA: Reducir la variabilidad del proceso (causas comunes).")
        recs.append("Revisar el sistema de medición (estudio MSA/R&R).")
        recs.append("Identificar y eliminar las principales fuentes de variación.")

    if cp is not None and cpk is not None and (cp - cpk) > 0.1:
        if usl is not None and lsl is not None:
            target_center = (usl + lsl) / 2
            recs.append(
                f"Centrar el proceso: la media actual ({media:.3f}) dista del objetivo "
                f"({target_center:.3f}). Ajustar parámetros de proceso."
            )

    if ppk is not None and cpk is not None and (cpk - ppk) > 0.15:
        recs.append(
            "Alta variación largo plazo detectada (Ppk << Cpk). "
            "Investigar causas de variación entre turnos, lotes o periodos."
        )

    if cpk >= 1.33:
        recs.append("Mantener las condiciones actuales del proceso.")
        recs.append("Considerar reducción de frecuencia de inspección.")

    return recs
