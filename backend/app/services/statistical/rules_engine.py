"""
OptiProcess - Motor de Reglas Western Electric / Nelson
Implementación completa de las 8 reglas de detección de causas especiales.
"""
import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class RuleViolation:
    regla: int
    nombre: str
    descripcion: str
    puntos_afectados: List[int]
    interpretacion: str
    severidad: str  # alta, media, baja


RULES_DESCRIPTIONS = {
    1: {
        "nombre": "Regla 1 - Punto fuera de 3σ",
        "descripcion": "Un punto fuera de los límites de control (±3σ)",
        "interpretacion": "Cambio brusco en el proceso — causa especial inmediata",
        "severidad": "alta",
    },
    2: {
        "nombre": "Regla 2 - Racha de 9 puntos",
        "descripcion": "9 puntos consecutivos en el mismo lado de la línea central",
        "interpretacion": "Desplazamiento sostenido del proceso — ajuste de media",
        "severidad": "alta",
    },
    3: {
        "nombre": "Regla 3 - Tendencia de 6 puntos",
        "descripcion": "6 puntos consecutivos en tendencia ascendente o descendente",
        "interpretacion": "Tendencia sistemática — desgaste, fatiga o degradación gradual",
        "severidad": "media",
    },
    4: {
        "nombre": "Regla 4 - Oscilación de 14 puntos",
        "descripcion": "14 puntos alternando arriba/abajo consecutivamente",
        "interpretacion": "Variabilidad sistemática — mezcla de dos procesos o fuentes",
        "severidad": "media",
    },
    5: {
        "nombre": "Regla 5 - Zona B: 2 de 3 puntos",
        "descripcion": "2 de 3 puntos consecutivos más allá de ±2σ del mismo lado",
        "interpretacion": "Proceso con posible cambio moderado en la media",
        "severidad": "media",
    },
    6: {
        "nombre": "Regla 6 - Zona C: 4 de 5 puntos",
        "descripcion": "4 de 5 puntos consecutivos más allá de ±1σ del mismo lado",
        "interpretacion": "Desplazamiento moderado sostenido de la media del proceso",
        "severidad": "baja",
    },
    7: {
        "nombre": "Regla 7 - Hugging: 15 puntos en zona C",
        "descripcion": "15 puntos consecutivos dentro de ±1σ (zona C) de la línea central",
        "interpretacion": "Estratificación — datos provienen de múltiples fuentes mezcladas",
        "severidad": "media",
    },
    8: {
        "nombre": "Regla 8 - 8 puntos fuera de zona C",
        "descripcion": "8 puntos consecutivos fuera de ±1σ de ambos lados",
        "interpretacion": "Mezcla de causas — posible multimodalidad del proceso",
        "severidad": "baja",
    },
}


def apply_western_electric_rules(
    values: np.ndarray,
    center_line: float,
    ucl: float,
    lcl: float,
    rules: List[int] = None,
) -> Tuple[List[RuleViolation], List[int]]:
    """
    Aplica las reglas Western Electric/Nelson a una serie de datos.
    Retorna lista de violaciones y lista de índices de puntos fuera de control.
    """
    if rules is None:
        rules = [1, 2, 3, 4, 5, 6, 7, 8]

    n = len(values)
    sigma = (ucl - center_line) / 3.0
    if sigma <= 0:
        sigma = (center_line - lcl) / 3.0
    if sigma <= 0:
        return [], []

    # Zonas: A = ±3σ, B = ±2σ, C = ±1σ
    ucl_1s = center_line + sigma
    lcl_1s = center_line - sigma
    ucl_2s = center_line + 2 * sigma
    lcl_2s = center_line - 2 * sigma

    violations = []
    all_ooc_indices = set()

    # Regla 1: Un punto fuera de ±3σ
    if 1 in rules:
        ooc = [i for i in range(n) if values[i] > ucl or values[i] < lcl]
        if ooc:
            all_ooc_indices.update(ooc)
            violations.append(RuleViolation(
                regla=1,
                nombre=RULES_DESCRIPTIONS[1]["nombre"],
                descripcion=RULES_DESCRIPTIONS[1]["descripcion"],
                puntos_afectados=ooc,
                interpretacion=RULES_DESCRIPTIONS[1]["interpretacion"],
                severidad=RULES_DESCRIPTIONS[1]["severidad"],
            ))

    # Regla 2: 9 puntos consecutivos en el mismo lado de CL
    if 2 in rules:
        ooc = []
        for i in range(8, n):
            window = values[i-8:i+1]
            if all(v > center_line for v in window) or all(v < center_line for v in window):
                ooc.extend(range(i-8, i+1))
        ooc = list(set(ooc))
        if ooc:
            all_ooc_indices.update(ooc)
            violations.append(RuleViolation(
                regla=2,
                nombre=RULES_DESCRIPTIONS[2]["nombre"],
                descripcion=RULES_DESCRIPTIONS[2]["descripcion"],
                puntos_afectados=sorted(ooc),
                interpretacion=RULES_DESCRIPTIONS[2]["interpretacion"],
                severidad=RULES_DESCRIPTIONS[2]["severidad"],
            ))

    # Regla 3: 6 puntos consecutivos en tendencia
    if 3 in rules:
        ooc = []
        for i in range(5, n):
            window = values[i-5:i+1]
            diffs = np.diff(window)
            if all(d > 0 for d in diffs) or all(d < 0 for d in diffs):
                ooc.extend(range(i-5, i+1))
        ooc = list(set(ooc))
        if ooc:
            all_ooc_indices.update(ooc)
            violations.append(RuleViolation(
                regla=3,
                nombre=RULES_DESCRIPTIONS[3]["nombre"],
                descripcion=RULES_DESCRIPTIONS[3]["descripcion"],
                puntos_afectados=sorted(ooc),
                interpretacion=RULES_DESCRIPTIONS[3]["interpretacion"],
                severidad=RULES_DESCRIPTIONS[3]["severidad"],
            ))

    # Regla 4: 14 puntos alternando arriba/abajo
    if 4 in rules:
        ooc = []
        for i in range(13, n):
            window = values[i-13:i+1]
            alternating = all(
                (window[j] > window[j-1]) != (window[j+1] > window[j])
                for j in range(1, len(window)-1)
            )
            if alternating:
                ooc.extend(range(i-13, i+1))
        ooc = list(set(ooc))
        if ooc:
            all_ooc_indices.update(ooc)
            violations.append(RuleViolation(
                regla=4,
                nombre=RULES_DESCRIPTIONS[4]["nombre"],
                descripcion=RULES_DESCRIPTIONS[4]["descripcion"],
                puntos_afectados=sorted(ooc),
                interpretacion=RULES_DESCRIPTIONS[4]["interpretacion"],
                severidad=RULES_DESCRIPTIONS[4]["severidad"],
            ))

    # Regla 5: 2 de 3 puntos más allá de ±2σ en el mismo lado
    if 5 in rules:
        ooc = []
        for i in range(2, n):
            window = values[i-2:i+1]
            above = sum(1 for v in window if v > ucl_2s)
            below = sum(1 for v in window if v < lcl_2s)
            if above >= 2 or below >= 2:
                ooc.extend(range(i-2, i+1))
        ooc = list(set(ooc))
        if ooc:
            all_ooc_indices.update(ooc)
            violations.append(RuleViolation(
                regla=5,
                nombre=RULES_DESCRIPTIONS[5]["nombre"],
                descripcion=RULES_DESCRIPTIONS[5]["descripcion"],
                puntos_afectados=sorted(ooc),
                interpretacion=RULES_DESCRIPTIONS[5]["interpretacion"],
                severidad=RULES_DESCRIPTIONS[5]["severidad"],
            ))

    # Regla 6: 4 de 5 puntos más allá de ±1σ en el mismo lado
    if 6 in rules:
        ooc = []
        for i in range(4, n):
            window = values[i-4:i+1]
            above = sum(1 for v in window if v > ucl_1s)
            below = sum(1 for v in window if v < lcl_1s)
            if above >= 4 or below >= 4:
                ooc.extend(range(i-4, i+1))
        ooc = list(set(ooc))
        if ooc:
            all_ooc_indices.update(ooc)
            violations.append(RuleViolation(
                regla=6,
                nombre=RULES_DESCRIPTIONS[6]["nombre"],
                descripcion=RULES_DESCRIPTIONS[6]["descripcion"],
                puntos_afectados=sorted(ooc),
                interpretacion=RULES_DESCRIPTIONS[6]["interpretacion"],
                severidad=RULES_DESCRIPTIONS[6]["severidad"],
            ))

    # Regla 7: 15 puntos consecutivos dentro de ±1σ (hugging)
    if 7 in rules:
        ooc = []
        for i in range(14, n):
            window = values[i-14:i+1]
            if all(lcl_1s < v < ucl_1s for v in window):
                ooc.extend(range(i-14, i+1))
        ooc = list(set(ooc))
        if ooc:
            all_ooc_indices.update(ooc)
            violations.append(RuleViolation(
                regla=7,
                nombre=RULES_DESCRIPTIONS[7]["nombre"],
                descripcion=RULES_DESCRIPTIONS[7]["descripcion"],
                puntos_afectados=sorted(ooc),
                interpretacion=RULES_DESCRIPTIONS[7]["interpretacion"],
                severidad=RULES_DESCRIPTIONS[7]["severidad"],
            ))

    # Regla 8: 8 puntos consecutivos fuera de ±1σ (ambos lados)
    if 8 in rules:
        ooc = []
        for i in range(7, n):
            window = values[i-7:i+1]
            if all(v > ucl_1s or v < lcl_1s for v in window):
                ooc.extend(range(i-7, i+1))
        ooc = list(set(ooc))
        if ooc:
            all_ooc_indices.update(ooc)
            violations.append(RuleViolation(
                regla=8,
                nombre=RULES_DESCRIPTIONS[8]["nombre"],
                descripcion=RULES_DESCRIPTIONS[8]["descripcion"],
                puntos_afectados=sorted(ooc),
                interpretacion=RULES_DESCRIPTIONS[8]["interpretacion"],
                severidad=RULES_DESCRIPTIONS[8]["severidad"],
            ))

    return violations, sorted(list(all_ooc_indices))
