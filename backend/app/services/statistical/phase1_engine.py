"""
OptiProcess - Motor de Fase I: Análisis histórico, estabilización y construcción de límites.
Implementa el proceso iterativo de depuración de causas especiales.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from app.services.statistical.control_charts import (
    calculate_xbar_r, calculate_xbar_s, calculate_imr,
    calculate_p_chart, calculate_np_chart, calculate_c_chart, calculate_u_chart,
    ControlChartResult,
)
from app.services.statistical.rules_engine import apply_western_electric_rules
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExclusionRecord:
    """Registro de exclusión de un punto en Fase I."""
    punto_indice: int
    iteracion: int
    razon: str
    reglas_violadas: List[int]
    valor: float


@dataclass
class Phase1Result:
    """Resultado completo del análisis Fase I."""
    tipo_grafico: str
    iteraciones: int
    proceso_estable: bool
    resultado_final: ControlChartResult
    historial_iteraciones: List[Dict[str, Any]]
    exclusiones: List[ExclusionRecord]
    limites_establecidos: Dict[str, float]
    sigma_proceso: float
    media_proceso: float
    n_puntos_originales: int
    n_puntos_excluidos: int
    porcentaje_excluido: float
    apto_para_fase2: bool
    diagnostico: str
    recomendaciones: List[str]
    advertencias: List[str]


class Phase1Engine:
    """
    Motor de análisis Fase I para Control Estadístico de Procesos.
    Realiza análisis iterativo para identificar y eliminar causas especiales,
    hasta alcanzar estabilidad estadística o hasta el máximo de iteraciones.
    """

    MAX_ITERATIONS = 10
    MAX_EXCLUSION_RATIO = 0.25  # No excluir más del 25% de los datos

    def __init__(self):
        self.exclusion_history: List[ExclusionRecord] = []

    def analyze(
        self,
        data: np.ndarray,
        chart_type: str,
        subgroup_size: int = 1,
        manual_exclusions: List[int] = None,
        rules: List[int] = None,
        subgroup_column: np.ndarray = None,
        sample_sizes: np.ndarray = None,
        iterative: bool = True,
    ) -> Phase1Result:
        """
        Realiza análisis completo de Fase I con depuración iterativa.
        """
        rules = rules or [1, 2, 3, 4, 5, 6, 7, 8]
        manual_exclusions = manual_exclusions or []
        excluded = list(set(manual_exclusions))
        n_original = len(data)

        historial = []
        self.exclusion_history = []
        iteracion = 0

        while iteracion < self.MAX_ITERATIONS:
            iteracion += 1

            # Calcular gráfico con puntos excluidos actuales
            result = self._calculate_chart(
                data, chart_type, subgroup_size, excluded, sample_sizes
            )

            # Aplicar reglas Western Electric
            violations, ooc_indices = apply_western_electric_rules(
                np.array(result.values_chart1),
                result.cl_chart1,
                result.ucl_chart1,
                result.lcl_chart1,
                rules,
            )

            result.ooc_chart1 = ooc_indices

            # También verificar carta secundaria
            chart2_vals = [v for v in result.values_chart2 if v is not None]
            if chart2_vals:
                violations2, ooc2 = apply_western_electric_rules(
                    np.array(chart2_vals),
                    result.cl_chart2,
                    result.ucl_chart2,
                    result.lcl_chart2,
                    [1],  # Solo regla 1 para carta secundaria
                )
                result.ooc_chart2 = ooc2

            historial.append({
                "iteracion": iteracion,
                "n_excluidos": len(excluded),
                "puntos_excluidos": list(excluded),
                "cl_chart1": result.cl_chart1,
                "ucl_chart1": result.ucl_chart1,
                "lcl_chart1": result.lcl_chart1,
                "cl_chart2": result.cl_chart2,
                "ucl_chart2": result.ucl_chart2,
                "lcl_chart2": result.lcl_chart2,
                "ooc_count": len(ooc_indices),
                "sigma": result.sigma_proceso,
                "media": result.media_proceso,
                "violaciones": [
                    {"regla": v.regla, "nombre": v.nombre, "puntos": v.puntos_afectados}
                    for v in violations
                ],
            })

            # Sin causas especiales: proceso estable
            if not ooc_indices and not ooc2 if chart2_vals else not ooc_indices:
                logger.info(f"Fase I: Proceso estabilizado en iteración {iteracion}")
                break

            # Solo excluir en modo iterativo
            if not iterative:
                break

            # Verificar límite de exclusión
            nuevos_exc = [i for i in ooc_indices if i not in excluded]
            if not nuevos_exc:
                break

            ratio_exc = (len(excluded) + len(nuevos_exc)) / n_original
            if ratio_exc > self.MAX_EXCLUSION_RATIO:
                logger.warning(
                    f"Fase I: Límite de exclusión alcanzado ({ratio_exc:.1%}). Deteniendo."
                )
                break

            # Registrar exclusiones con sus razones
            for idx in nuevos_exc:
                reglas_v = [v.regla for v in violations if idx in v.puntos_afectados]
                val = result.values_chart1[idx] if idx < len(result.values_chart1) else 0
                record = ExclusionRecord(
                    punto_indice=idx,
                    iteracion=iteracion,
                    razon=self._generate_exclusion_reason(reglas_v, val, result.cl_chart1),
                    reglas_violadas=reglas_v,
                    valor=val,
                )
                self.exclusion_history.append(record)
                excluded.append(idx)

        # Resultado final
        result_final = self._calculate_chart(data, chart_type, subgroup_size, excluded, sample_sizes)
        violations_final, ooc_final = apply_western_electric_rules(
            np.array(result_final.values_chart1),
            result_final.cl_chart1,
            result_final.ucl_chart1,
            result_final.lcl_chart1,
        )
        result_final.ooc_chart1 = ooc_final
        result_final.fase = "I"

        proceso_estable = len(ooc_final) == 0
        n_excluidos = len(set(excluded) - set(manual_exclusions))
        pct_excluido = n_excluidos / n_original if n_original > 0 else 0

        limites = {
            "cl_x": result_final.cl_chart1,
            "ucl_x": result_final.ucl_chart1,
            "lcl_x": result_final.lcl_chart1,
            "cl_r_s_mr": result_final.cl_chart2,
            "ucl_r_s_mr": result_final.ucl_chart2,
            "lcl_r_s_mr": result_final.lcl_chart2,
            "sigma": result_final.sigma_proceso,
            "media": result_final.media_proceso,
        }

        diagnostico, recomendaciones, advertencias = self._generate_diagnostics(
            proceso_estable, pct_excluido, n_original, n_excluidos,
            result_final.sigma_proceso, result_final.media_proceso, violations_final
        )

        return Phase1Result(
            tipo_grafico=chart_type,
            iteraciones=iteracion,
            proceso_estable=proceso_estable,
            resultado_final=result_final,
            historial_iteraciones=historial,
            exclusiones=self.exclusion_history,
            limites_establecidos=limites,
            sigma_proceso=result_final.sigma_proceso,
            media_proceso=result_final.media_proceso,
            n_puntos_originales=n_original,
            n_puntos_excluidos=n_excluidos,
            porcentaje_excluido=pct_excluido,
            apto_para_fase2=proceso_estable and pct_excluido <= 0.20,
            diagnostico=diagnostico,
            recomendaciones=recomendaciones,
            advertencias=advertencias,
        )

    def _calculate_chart(
        self, data, chart_type, subgroup_size, excluded, sample_sizes
    ) -> ControlChartResult:
        if chart_type == "xbar_r":
            return calculate_xbar_r(data, subgroup_size, excluded)
        elif chart_type == "xbar_s":
            return calculate_xbar_s(data, subgroup_size, excluded)
        elif chart_type == "imr":
            return calculate_imr(data, excluded)
        elif chart_type == "p":
            ns = sample_sizes if sample_sizes is not None else np.full(len(data), subgroup_size)
            return calculate_p_chart(data, ns, excluded)
        elif chart_type == "np":
            return calculate_np_chart(data, subgroup_size, excluded)
        elif chart_type == "c":
            return calculate_c_chart(data, excluded)
        elif chart_type == "u":
            ns = sample_sizes if sample_sizes is not None else np.ones(len(data))
            return calculate_u_chart(data, ns, excluded)
        else:
            raise ValueError(f"Tipo de gráfico no soportado: {chart_type}")

    def _generate_exclusion_reason(
        self, rules_violated: List[int], value: float, center_line: float
    ) -> str:
        if not rules_violated:
            return "Exclusión manual del usuario"
        rule_names = {
            1: "punto fuera de ±3σ",
            2: "racha de 9 puntos",
            3: "tendencia de 6 puntos",
            4: "oscilación sistemática",
            5: "2 de 3 puntos fuera de ±2σ",
            6: "4 de 5 puntos fuera de ±1σ",
            7: "estratificación (hugging)",
            8: "mezcla de causas",
        }
        reasons = [rule_names.get(r, f"Regla {r}") for r in rules_violated]
        direction = "sobre UCL" if value > center_line else "bajo LCL"
        return f"Causa especial detectada: {', '.join(reasons)} ({direction})"

    def _generate_diagnostics(
        self, stable, pct_exc, n_orig, n_exc, sigma, media, violations
    ) -> Tuple[str, List[str], List[str]]:
        recomendaciones = []
        advertencias = []

        if stable:
            diagnostico = (
                f"✅ El proceso muestra estabilidad estadística en Fase I. "
                f"Se excluyeron {n_exc} de {n_orig} observaciones ({pct_exc:.1%}). "
                f"El proceso está LISTO para pasar a monitoreo Fase II."
            )
            recomendaciones.append("Proceder con el cálculo de capacidad del proceso.")
            recomendaciones.append("Documentar los límites de control establecidos para Fase II.")
            recomendaciones.append("Investigar y eliminar las causas raíz de los puntos excluidos.")
        else:
            diagnostico = (
                f"⚠️ El proceso NO alcanzó estabilidad estadística en Fase I. "
                f"Se detectaron causas especiales que no pudieron eliminarse completamente. "
                f"Se requiere investigación adicional antes de proceder a Fase II."
            )
            recomendaciones.append("Investigar las causas especiales identificadas.")
            recomendaciones.append("Revisar el sistema de medición (R&R de sistema de medición).")
            recomendaciones.append("Verificar condiciones operativas del proceso.")

        if pct_exc > 0.15:
            advertencias.append(
                f"⚠️ Se excluyó el {pct_exc:.1%} de las observaciones. "
                "Un porcentaje alto indica posibles problemas sistémicos en el proceso."
            )

        if n_orig < 25:
            advertencias.append(
                f"⚠️ La muestra ({n_orig} obs.) es pequeña para Fase I. "
                "Se recomiendan al menos 25 subgrupos o 100 observaciones individuales."
            )

        return diagnostico, recomendaciones, advertencias
