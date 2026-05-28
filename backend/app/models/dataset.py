"""
OptiProcess - Modelo de Dataset y columnas de datos
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(255), nullable=False)
    descripcion = Column(Text, nullable=True)
    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    archivo_origen = Column(String(500), nullable=True)
    tipo_archivo = Column(String(20), nullable=True)  # csv, excel, manual
    n_filas = Column(Integer, default=0)
    n_columnas = Column(Integer, default=0)
    columnas_info = Column(JSON, nullable=True)  # metadata de columnas
    estadisticos = Column(JSON, nullable=True)    # estadísticos descriptivos
    datos = Column(JSON, nullable=True)           # datos en formato JSON
    fase = Column(String(10), default="I")         # I o II
    proceso = Column(String(255), nullable=True)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    usuario = relationship("User", backref="datasets")
    analisis = relationship("Analysis", back_populates="dataset", cascade="all, delete-orphan")
