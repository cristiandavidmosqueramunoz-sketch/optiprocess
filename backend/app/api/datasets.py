"""
OptiProcess - Endpoints de gestión de datasets
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import json
from pydantic import BaseModel
from app.database import get_db
from app.models.user import User
from app.models.dataset import Dataset
from app.schemas.dataset import DatasetCreate, DatasetResponse, DataPreview
from app.services.auth_service import get_current_user
from app.services.data_service import DataService
import logging

router = APIRouter(prefix="/datasets", tags=["Datos"])
logger = logging.getLogger(__name__)
data_service = DataService()


@router.post("/upload", response_model=DatasetResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    nombre: str = Form(...),
    descripcion: str = Form(default=""),
    proceso: str = Form(default=""),
    fase: str = Form(default="I"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cargar dataset desde archivo CSV o Excel."""
    content = await file.read()
    try:
        analisis = data_service.process_file(content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    dataset = Dataset(
        nombre=nombre,
        descripcion=descripcion,
        proceso=proceso,
        fase=fase,
        usuario_id=current_user.id,
        archivo_origen=file.filename,
        tipo_archivo=file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "desconocido",
        n_filas=analisis["n_filas"],
        n_columnas=analisis["n_columnas"],
        columnas_info=analisis["columnas_info"],
        estadisticos=analisis["estadisticos"],
        datos=analisis["datos"],
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    logger.info(f"Dataset cargado: {nombre} ({analisis['n_filas']} filas) por {current_user.email}")
    return dataset


class ManualDatasetRequest(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    proceso: Optional[str] = None
    fase: str = "I"
    columnas: List[str]
    datos: List[dict]

    class Config:
        from_attributes = True


@router.post("/manual", response_model=DatasetResponse, status_code=201)
def create_manual(
    body: ManualDatasetRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crear dataset con datos ingresados manualmente desde la tabla editor."""
    if not body.columnas:
        raise HTTPException(status_code=400, detail="Debes definir al menos una columna")
    if not body.datos:
        raise HTTPException(status_code=400, detail="La tabla no tiene datos")
    try:
        analisis = data_service.process_manual_data(body.datos, body.columnas)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    dataset_data = body  # reusar campos nombre, descripcion, etc.

    dataset = Dataset(
        nombre=dataset_data.nombre,
        descripcion=dataset_data.descripcion,
        proceso=dataset_data.proceso,
        fase=dataset_data.fase,
        usuario_id=current_user.id,
        tipo_archivo="manual",
        n_filas=analisis["n_filas"],
        n_columnas=analisis["n_columnas"],
        columnas_info=analisis["columnas_info"],
        estadisticos=analisis["estadisticos"],
        datos=analisis["datos"],
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


@router.get("", response_model=List[DatasetResponse])
def list_datasets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar todos los datasets del usuario."""
    return db.query(Dataset).filter(
        Dataset.usuario_id == current_user.id,
        Dataset.activo == True
    ).order_by(Dataset.created_at.desc()).all()


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtener dataset por ID."""
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.usuario_id == current_user.id,
    ).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset no encontrado")
    return dataset


@router.get("/{dataset_id}/preview")
def preview_dataset(
    dataset_id: int,
    page: int = 1,
    page_size: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Vista previa del dataset con paginación."""
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id, Dataset.usuario_id == current_user.id
    ).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset no encontrado")

    datos = dataset.datos or []
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "columnas": [c["nombre"] for c in (dataset.columnas_info or [])],
        "datos": datos[start:end],
        "total_filas": dataset.n_filas,
        "pagina": page,
        "total_paginas": max(1, (dataset.n_filas + page_size - 1) // page_size),
        "estadisticos": dataset.estadisticos,
    }


@router.get("/{dataset_id}/outliers")
def detect_outliers(
    dataset_id: int,
    columna: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Detectar outliers en una columna específica."""
    import numpy as np
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id, Dataset.usuario_id == current_user.id
    ).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset no encontrado")

    import pandas as pd
    df = pd.DataFrame(dataset.datos or [])
    if columna not in df.columns:
        raise HTTPException(status_code=400, detail=f"Columna '{columna}' no encontrada")

    values = pd.to_numeric(df[columna], errors="coerce").dropna().values
    return data_service.detect_outliers_iqr(values)


@router.delete("/{dataset_id}")
def delete_dataset(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Eliminar dataset (soft delete)."""
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id, Dataset.usuario_id == current_user.id
    ).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset no encontrado")
    dataset.activo = False
    db.commit()
    return {"mensaje": "Dataset eliminado correctamente"}
