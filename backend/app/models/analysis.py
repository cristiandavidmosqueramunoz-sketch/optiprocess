"""
OptiProcess - Modelo de Análisis estadístico
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tipo = Column(String(50), nullable=False)  # xbar_r, xbar_s, imr, p, np, c, u, capability, etc.
    fase = Column(String(10), default="I")      # I o II
    nombre = Column(String(255), nullable=True)
    columna_variable = Column(String(255), nullable=True)
    columna_subgrupo = Column(String(255), nullable=True)
    tamano_subgrupo = Column(Integer, nullable=True)
    parametros = Column(JSON, nullable=True)     # parámetros de configuración
    resultados = Column(JSON, nullable=True)     # resultados del análisis
    limites_control = Column(JSON, nullable=True) # UCL, LCL, CL para cada carta
    puntos_excluidos = Column(JSON, nullable=True) # historial de exclusiones Fase I
    interpretacion = Column(Text, nullable=True)  # interpretación automática
    estado = Column(String(50), default="completado")  # completado, error, en_proceso
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    dataset = relationship("Dataset", back_populates="analisis")
    usuario = relationship("User", backref="analisis")
