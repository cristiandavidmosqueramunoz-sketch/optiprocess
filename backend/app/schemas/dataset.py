"""
OptiProcess - Schemas de Dataset (Pydantic)
"""
from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class DatasetCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    proceso: Optional[str] = None
    fase: str = "I"

    @validator("fase")
    def fase_valida(cls, v):
        if v not in ("I", "II"):
            raise ValueError("La fase debe ser I o II")
        return v


class DatasetUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    proceso: Optional[str] = None
    fase: Optional[str] = None


class ColumnInfo(BaseModel):
    nombre: str
    tipo: str  # numerico, categorico, fecha
    n_nulos: int
    n_unicos: int
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    media: Optional[float] = None
    std: Optional[float] = None


class DatasetResponse(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str]
    usuario_id: int
    archivo_origen: Optional[str]
    tipo_archivo: Optional[str]
    n_filas: int
    n_columnas: int
    columnas_info: Optional[List[Dict[str, Any]]]
    estadisticos: Optional[Dict[str, Any]]
    fase: str
    proceso: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class DataPreview(BaseModel):
    columnas: List[str]
    datos: List[Dict[str, Any]]
    total_filas: int
    estadisticos: Dict[str, Any]
    calidad: Dict[str, Any]  # info sobre nulos, outliers, etc.


class SubgroupConfig(BaseModel):
    columna_variable: str
    columna_subgrupo: Optional[str] = None
    tamano_subgrupo: Optional[int] = None
    metodo: str = "consecutivo"  # consecutivo, por_columna, por_variable
