"""
OptiProcess - Servicio de gestión y procesamiento de datos
"""
import pandas as pd
import numpy as np
import json
from typing import Dict, List, Optional, Any, Tuple
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


class DataService:
    """Servicio para carga, validación y procesamiento de datasets."""

    SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
    MAX_ROWS = 100_000

    def process_file(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Procesa un archivo CSV o Excel y retorna datos limpios con estadísticos."""
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Formato no soportado. Use: {', '.join(self.SUPPORTED_EXTENSIONS)}")

        try:
            if ext == ".csv":
                df = self._read_csv(file_content)
            else:
                df = self._read_excel(file_content)
        except Exception as e:
            raise ValueError(f"Error al leer el archivo: {str(e)}")

        if len(df) > self.MAX_ROWS:
            df = df.head(self.MAX_ROWS)
            logger.warning(f"Dataset truncado a {self.MAX_ROWS} filas")

        return self._analyze_dataframe(df)

    def process_manual_data(self, data: List[Dict], column_names: List[str]) -> Dict[str, Any]:
        """Procesa datos ingresados manualmente."""
        df = pd.DataFrame(data, columns=column_names)
        # Convertir columnas numéricas
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return self._analyze_dataframe(df)

    def _read_csv(self, content: bytes) -> pd.DataFrame:
        for sep in [",", ";", "\t", "|"]:
            try:
                df = pd.read_csv(BytesIO(content), sep=sep, decimal=".", encoding="utf-8-sig")
                if len(df.columns) > 1:
                    return df
            except Exception:
                continue
        return pd.read_csv(BytesIO(content), encoding="latin-1")

    def _read_excel(self, content: bytes) -> pd.DataFrame:
        return pd.read_excel(BytesIO(content), engine="openpyxl")

    def _analyze_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Genera análisis completo del dataframe."""
        # Limpiar nombres de columnas
        df.columns = [str(c).strip().replace(" ", "_") for c in df.columns]

        n_rows, n_cols = df.shape
        columnas_info = []
        estadisticos = {}

        for col in df.columns:
            series = df[col]
            n_nulos = int(series.isna().sum())
            n_unicos = int(series.nunique())
            is_numeric = pd.api.types.is_numeric_dtype(series)

            col_info = {
                "nombre": col,
                "tipo": "numerico" if is_numeric else "categorico",
                "n_nulos": n_nulos,
                "n_unicos": n_unicos,
                "porcentaje_nulos": round(n_nulos / n_rows * 100, 2) if n_rows > 0 else 0,
            }

            if is_numeric:
                clean_series = series.dropna()
                if len(clean_series) > 0:
                    col_info.update({
                        "min": round(float(clean_series.min()), 6),
                        "max": round(float(clean_series.max()), 6),
                        "media": round(float(clean_series.mean()), 6),
                        "mediana": round(float(clean_series.median()), 6),
                        "std": round(float(clean_series.std()), 6),
                        "q1": round(float(clean_series.quantile(0.25)), 6),
                        "q3": round(float(clean_series.quantile(0.75)), 6),
                        "curtosis": round(float(clean_series.kurtosis()), 4),
                        "asimetria": round(float(clean_series.skew()), 4),
                        "n_outliers": int(self._count_outliers(clean_series)),
                    })
                    estadisticos[col] = col_info.copy()

            columnas_info.append(col_info)

        # Calidad general del dataset
        total_celdas = n_rows * n_cols
        total_nulos = int(df.isna().sum().sum())
        calidad = {
            "porcentaje_completitud": round((1 - total_nulos / total_celdas) * 100, 2) if total_celdas > 0 else 100,
            "total_nulos": total_nulos,
            "filas_con_nulos": int(df.isna().any(axis=1).sum()),
            "columnas_numericas": sum(1 for c in columnas_info if c["tipo"] == "numerico"),
            "columnas_categoricas": sum(1 for c in columnas_info if c["tipo"] == "categorico"),
        }

        # Datos como lista de dicts (para JSON)
        datos = df.where(pd.notnull(df), None).to_dict(orient="records")

        return {
            "n_filas": n_rows,
            "n_columnas": n_cols,
            "columnas": list(df.columns),
            "columnas_info": columnas_info,
            "estadisticos": estadisticos,
            "calidad": calidad,
            "datos": datos,
        }

    def _count_outliers(self, series: pd.Series) -> int:
        """Detecta outliers usando IQR."""
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            return 0
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        return int(((series < lower) | (series > upper)).sum())

    def prepare_chart_data(
        self, data: Dict[str, Any], column: str, subgroup_size: int = None,
        subgroup_col: str = None
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Prepara datos para análisis de gráficos de control."""
        df = pd.DataFrame(data["datos"])

        if column not in df.columns:
            raise ValueError(f"Columna '{column}' no encontrada")

        values = pd.to_numeric(df[column], errors="coerce").dropna().values

        subgroup_indices = None
        if subgroup_col and subgroup_col in df.columns:
            subgroup_indices = df[subgroup_col].values[:len(values)]

        return values, subgroup_indices

    def detect_outliers_iqr(self, values: np.ndarray) -> Dict[str, Any]:
        """Detecta outliers con método IQR y Z-score."""
        q1, q3 = np.percentile(values, [25, 75])
        iqr = q3 - q1
        lower_iqr = q1 - 1.5 * iqr
        upper_iqr = q3 + 1.5 * iqr

        z_scores = np.abs((values - np.mean(values)) / np.std(values)) if np.std(values) > 0 else np.zeros(len(values))

        outliers_iqr = np.where((values < lower_iqr) | (values > upper_iqr))[0].tolist()
        outliers_zscore = np.where(z_scores > 3)[0].tolist()

        return {
            "outliers_iqr": outliers_iqr,
            "outliers_zscore": outliers_zscore,
            "lower_bound_iqr": float(lower_iqr),
            "upper_bound_iqr": float(upper_iqr),
            "q1": float(q1), "q3": float(q3), "iqr": float(iqr),
        }
