"""
OptiProcess - Motor de Fase II: Monitoreo continuo usando límites establecidos en Fase I.
Detecta desviaciones, aplica reglas de sensibilidad y genera alertas operacionales.
"""
import numpy as np
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from app.services.statistical.rules_engine import apply_western_electric_rules, RuleViolation
import logging

logger = logging.getLogger(__name__)


@dataclass
class Phase2Alert:
    """Alerta generada durante monitoreo Fase II."""
    tipo: str  # fuera_de_control, tendencia, racha, advertencia
    severidad: str  # critica, alta, media, baja
    punto_indice: int
    valor: float
    reglas_violadas: List[int]
    mensaje: str
    accion_recomendada: str
    timestamp: str = ""


@dataclass
class Phase2Result:
    """Resultado del monitoreo Fase II."""
    tipo_grafico: str
    # Datos monitoreados
    values_chart1: List[float]
    values_chart2: List[Optional[float]]
    # Límites fijos de Fase I (no modificables)
    cl_chart1: float
    ucl_chart1: float
    lcl_chart1: float
    cl_chart2: float
    ucl_chart2: float
    lcl_chart2: float
    # Estado
    puntos_en_control: int
    puntos_fuera_control: int
    ooc_chart1: List[int]
    ooc_chart2: List[int]
    alertas: List[Phase2Alert]
    proceso_bajo_control: bool
    # ARL estimado
    arl_estimado: float
    # Diagnóstico
    estado_proceso: str  # bajo_control, fuera_control, advertencia
    diagnostico: str
    recomendaciones: List[str]
    violaciones_detalle: List[Dict[str, Any]]


class Phase2Engine:
    """
    Motor de Fase II para monitoreo operacional continuo.
    Los límites de control están bloqueados (establecidos en Fase I).
    """

    def monitor(
        self,
        new_data: np.ndarray,
        phase1_limits: Dict[str, float],
        chart_type: str,
        rules: List[int] = None,
        sample_sizes: np.ndarray = None,
        subgroup_size: int = 1,
    ) -> Phase2Result:
        """
        Monitorea nuevos datos contra límites establecidos en Fase I.
        """
        rules = rules or [1, 2, 3, 4, 5, 6, 7, 8]

        # Usar límites bloqueados de Fase I
        cl_x = phase1_limits["cl_x"]
        ucl_x = phase1_limits["ucl_x"]
        lcl_x = phase1_limits["lcl_x"]
        cl_sec = phase1_limits.get("cl_r_s_mr", 0)
        ucl_sec = phase1_limits.get("ucl_r_s_mr", 0)
        lcl_sec = phase1_limits.get("lcl_r_s_mr", 0)

        # Calcular estadísticos de las nuevas observaciones
        values_chart1, values_chart2 = self._compute_chart_values(
            new_data, chart_type, subgroup_size, sample_sizes
        )

        # Aplicar reglas WE sobre carta principal
        violations, ooc1 = apply_western_electric_rules(
            np.array(values_chart1), cl_x, ucl_x, lcl_x, rules
        )

        # Aplicar regla 1 sobre carta secundaria
        ooc2 = []
        if values_chart2:
            vals2 = [v for v in values_chart2 if v is not None]
            if vals2 and ucl_sec > 0:
                _, ooc2 = apply_western_electric_rules(
                    np.array(vals2), cl_sec, ucl_sec, lcl_sec, [1]
                )

        # Generar alertas
        alertas = self._generate_alerts(violations, ooc1, ooc2, values_chart1, cl_x)

        # Estado del proceso
        n_total = len(values_chart1)
        n_ooc = len(set(ooc1 + ooc2))
        proceso_bajo_control = n_ooc == 0

        estado = "bajo_control" if proceso_bajo_control else (
            "critico" if n_ooc > n_total * 0.1 else "advertencia"
        )

        # ARL estimado (simplificado para display)
        p_falsa_alarma = 0.0027  # Para 3σ con una regla
        arl = 1.0 / p_falsa_alarma if p_falsa_alarma > 0 else 370

        diagnostico, recomendaciones = self._generate_diagnostics(
            proceso_bajo_control, n_ooc, n_total, violations, alertas
        )

        return Phase2Result(
            tipo_grafico=chart_type,
            values_chart1=values_chart1,
            values_chart2=values_chart2,
            cl_chart1=cl_x,
            ucl_chart1=ucl_x,
            lcl_chart1=lcl_x,
            cl_chart2=cl_sec,
            ucl_chart2=ucl_sec,
            lcl_chart2=lcl_sec,
            puntos_en_control=n_total - n_ooc,
            puntos_fuera_control=n_ooc,
            ooc_chart1=ooc1,
            ooc_chart2=ooc2,
            alertas=alertas,
            proceso_bajo_control=proceso_bajo_control,
            arl_estimado=arl,
            estado_proceso=estado,
            diagnostico=diagnostico,
            recomendaciones=recomendaciones,
            violaciones_detalle=[
                {
                    "regla": v.regla,
                    "nombre": v.nombre,
                    "descripcion": v.descripcion,
                    "puntos": v.puntos_afectados,
                    "interpretacion": v.interpretacion,
                    "severidad": v.severidad,
                }
                for v in violations
            ],
        )

    def _compute_chart_values(self, data, chart_type, subgroup_size, sample_sizes):
        n = len(data)
        if chart_type in ("xbar_r", "xbar_s") and subgroup_size > 1:
            n_sg = n // subgroup_size
            sgs = data[:n_sg * subgroup_size].reshape(n_sg, subgroup_size)
            chart1 = np.mean(sgs, axis=1).tolist()
            if chart_type == "xbar_r":
                chart2 = np.ptp(sgs, axis=1).tolist()
            else:
                chart2 = np.std(sgs, axis=1, ddof=1).tolist()
        elif chart_type == "imr":
            chart1 = data.tolist()
            mr = np.abs(np.diff(data))
            chart2 = [None] + mr.tolist()
        elif chart_type == "p":
            ns = sample_sizes if sample_sizes is not None else np.full(n, subgroup_size)
            chart1 = (data / ns).tolist()
            chart2 = ns.tolist()
        elif chart_type in ("c", "np"):
            chart1 = data.tolist()
            chart2 = [1.0] * n
        elif chart_type == "u":
            ns = sample_sizes if sample_sizes is not None else np.ones(n)
            chart1 = (data / ns).tolist()
            chart2 = ns.tolist()
        else:
            chart1 = data.tolist()
            chart2 = []
        return chart1, chart2

    def _generate_alerts(
        self, violations: List[RuleViolation], ooc1: List[int],
        ooc2: List[int], values: List[float], cl: float
    ) -> List[Phase2Alert]:
        alerts = []
        severity_map = {"alta": "critica", "media": "alta", "baja": "media"}

        for v in violations:
            for pt in v.puntos_afectados[:3]:  # Limitar alertas por regla
                val = values[pt] if pt < len(values) else 0
                alerts.append(Phase2Alert(
                    tipo="fuera_de_control" if v.regla == 1 else "patron_no_aleatorio",
                    severidad=severity_map.get(v.severidad, "media"),
                    punto_indice=pt,
                    valor=val,
                    reglas_violadas=[v.regla],
                    mensaje=f"{v.nombre}: {v.descripcion}",
                    accion_recomendada=f"Investigar causa especial. {v.interpretacion}",
                ))

        return alerts

    def _generate_diagnostics(self, bajo_control, n_ooc, n_total, violations, alerts):
        recomendaciones = []

        if bajo_control:
            diagnostico = (
                f"✅ PROCESO BAJO CONTROL ESTADÍSTICO. "
                f"Las {n_total} observaciones monitoreadas están dentro de los límites de Fase I. "
                "No se detectaron causas especiales."
            )
            recomendaciones.append("Continuar el monitoreo regular del proceso.")
            recomendaciones.append("Mantener las condiciones operativas actuales.")
        else:
            pct = n_ooc / n_total if n_total > 0 else 0
            diagnostico = (
                f"🚨 PROCESO FUERA DE CONTROL ESTADÍSTICO. "
                f"Se detectaron {n_ooc} de {n_total} puntos fuera de control ({pct:.1%}). "
                "Se requiere acción correctiva inmediata."
            )
            if any(v.regla == 1 for v in violations):
                recomendaciones.append("⚠️ ACCIÓN INMEDIATA: Detener el proceso e investigar causas especiales.")
            if any(v.regla in (2, 3) for v in violations):
                recomendaciones.append("Investigar cambio de media — revisar configuración de máquina.")
            recomendaciones.append("Documentar las condiciones del proceso al momento de la señal.")
            recomendaciones.append("Implementar acciones correctivas y verificar su efectividad.")

        return diagnostico, recomendaciones
