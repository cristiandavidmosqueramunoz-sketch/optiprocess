"""
OptiProcess - Schemas de Análisis (Pydantic)
"""
from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class ControlChartRequest(BaseModel):
    dataset_id: int
    tipo_grafico: str  # xbar_r, xbar_s, imr, p, np, c, u
    columna_variable: str
    columna_subgrupo: Optional[str] = None
    tamano_subgrupo: Optional[int] = None
    fase: str = "I"
    nombre: Optional[str] = None
    # Para Fase II: usar límites previos
    usar_limites_fase1: Optional[bool] = False
    analisis_fase1_id: Optional[int] = None
    # Configuración avanzada
    sigma_multiplicador: float = 3.0
    reglas_we: List[int] = [1, 2, 3, 4, 5, 6, 7, 8]
    puntos_excluidos: List[int] = []

    @validator("tipo_grafico")
    def tipo_valido(cls, v):
        tipos = ["xbar_r", "xbar_s", "imr", "p", "np", "c", "u"]
        if v not in tipos:
            raise ValueError(f"Tipo de gráfico debe ser uno de: {tipos}")
        return v

    @validator("fase")
    def fase_valida(cls, v):
        if v not in ("I", "II"):
            raise ValueError("La fase debe ser I o II")
        return v


class CapabilityRequest(BaseModel):
    dataset_id: int
    columna: str
    lsl: Optional[float] = None   # Límite inferior de especificación
    usl: Optional[float] = None   # Límite superior de especificación
    target: Optional[float] = None
    tamano_subgrupo: Optional[int] = None
    columna_subgrupo: Optional[str] = None


class AssumptionsRequest(BaseModel):
    dataset_id: int
    columna: str
    nivel_significancia: float = 0.05

    @validator("nivel_significancia")
    def alpha_valido(cls, v):
        if not 0.01 <= v <= 0.10:
            raise ValueError("Nivel de significancia debe estar entre 0.01 y 0.10")
        return v


class SamplingRequest(BaseModel):
    tipo: str  # simple, doble, multiple
    n_lote: int
    aql: float
    ltpd: Optional[float] = None
    alpha: float = 0.05
    beta: float = 0.10
    nivel_inspeccion: str = "II"

    @validator("tipo")
    def tipo_valido(cls, v):
        if v not in ("simple", "doble", "multiple"):
            raise ValueError("Tipo debe ser: simple, doble o multiple")
        return v


class PointExclusionRequest(BaseModel):
    analisis_id: int
    punto_indice: int
    razon: str


class Phase2MonitorRequest(BaseModel):
    dataset_id: int
    analisis_fase1_id: int
    columna_variable: str
    columna_subgrupo: Optional[str] = None
    tamano_subgrupo: Optional[int] = None
    nuevos_datos: Optional[List[Dict[str, Any]]] = None


class ReportRequest(BaseModel):
    titulo: str
    empresa: Optional[str] = None
    autor: Optional[str] = None
    analisis_ids: List[int]
    formato: str = "pdf"  # pdf, excel
    incluir_graficos: bool = True
    incluir_interpretaciones: bool = True
    incluir_recomendaciones: bool = True


class AnalysisResponse(BaseModel):
    id: int
    dataset_id: int
    tipo: str
    fase: str
    nombre: Optional[str]
    resultados: Optional[Dict[str, Any]]
    limites_control: Optional[Dict[str, Any]]
    interpretacion: Optional[str]
    estado: str
    created_at: datetime

    class Config:
        from_attributes = True
