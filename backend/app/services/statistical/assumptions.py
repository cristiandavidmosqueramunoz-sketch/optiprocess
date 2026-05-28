"""
OptiProcess - Validación de supuestos estadísticos: normalidad, independencia, estabilidad.
"""
import numpy as np
from scipy import stats
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field


@dataclass
class TestResult:
    nombre: str
    estadistico: float
    p_valor: float
    rechaza_h0: bool
    conclusion: str
    interpretacion: str
    nivel_significancia: float


@dataclass
class AssumptionsResult:
    n: int
    media: float
    std: float
    # Pruebas de normalidad
    shapiro_wilk: Optional[TestResult]
    anderson_darling: Optional[TestResult]
    kolmogorov_smirnov: TestResult
    # Independencia
    runs_test: TestResult
    durbin_watson: Optional[Dict[str, Any]]
    autocorrelacion_lag1: float
    # Conclusión global
    normalidad_ok: bool
    independencia_ok: bool
    apto_fase1: bool
    apto_fase2: bool
    diagnostico_global: str
    recomendaciones: List[str]
    # Datos para QQ-plot
    qq_data: Dict[str, Any]
    histograma: Dict[str, Any]


def validate_assumptions(data: np.ndarray, alpha: float = 0.05) -> AssumptionsResult:
    """Ejecuta batería completa de pruebas de supuestos estadísticos."""
    data = data[~np.isnan(data)]
    n = len(data)
    media = float(np.mean(data))
    std = float(np.std(data, ddof=1))

    # ── Shapiro-Wilk (mejor para n < 5000) ────────────────────────────────
    shapiro = None
    if n >= 3 and n <= 5000:
        stat, p = stats.shapiro(data)
        shapiro = TestResult(
            nombre="Shapiro-Wilk",
            estadistico=round(float(stat), 6),
            p_valor=round(float(p), 6),
            rechaza_h0=p < alpha,
            conclusion="No normal" if p < alpha else "Normal",
            interpretacion=(
                f"Con W = {stat:.4f} y p = {p:.4f}, "
                + ("se rechaza H₀ de normalidad. Los datos NO siguen distribución normal."
                   if p < alpha else
                   "no se rechaza H₀. Los datos son COMPATIBLES con distribución normal.")
            ),
            nivel_significancia=alpha,
        )

    # ── Anderson-Darling ───────────────────────────────────────────────────
    ad_result = stats.anderson(data, dist='norm')
    # Obtener valor crítico para alpha más cercano
    sig_levels = [0.15, 0.10, 0.05, 0.025, 0.01]
    idx_alpha = min(range(len(sig_levels)), key=lambda i: abs(sig_levels[i] - alpha))
    critical_val = ad_result.critical_values[idx_alpha]
    ad_test = TestResult(
        nombre="Anderson-Darling",
        estadistico=round(float(ad_result.statistic), 6),
        p_valor=float(sig_levels[idx_alpha]),
        rechaza_h0=bool(ad_result.statistic > critical_val),
        conclusion="No normal" if ad_result.statistic > critical_val else "Normal",
        interpretacion=(
            f"Con A² = {ad_result.statistic:.4f} (valor crítico = {critical_val:.3f}), "
            + ("se rechaza H₀. Los datos presentan desviaciones significativas de normalidad."
               if ad_result.statistic > critical_val else
               "no se rechaza H₀. Los datos son compatibles con la distribución normal.")
        ),
        nivel_significancia=alpha,
    )

    # ── Kolmogorov-Smirnov ─────────────────────────────────────────────────
    data_std = (data - media) / std if std > 0 else data
    ks_stat, ks_p = stats.kstest(data_std, 'norm')
    ks_test = TestResult(
        nombre="Kolmogorov-Smirnov",
        estadistico=round(float(ks_stat), 6),
        p_valor=round(float(ks_p), 6),
        rechaza_h0=ks_p < alpha,
        conclusion="No normal" if ks_p < alpha else "Normal",
        interpretacion=(
            f"Con D = {ks_stat:.4f} y p = {ks_p:.4f}, "
            + ("se rechaza H₀ de normalidad."
               if ks_p < alpha else
               "no se rechaza H₀. Los datos son compatibles con normalidad.")
        ),
        nivel_significancia=alpha,
    )

    # ── Prueba de Rachas (Independencia) ───────────────────────────────────
    runs_result = _runs_test(data, media, alpha)

    # ── Autocorrelación Lag-1 ─────────────────────────────────────────────
    ac_lag1 = float(np.corrcoef(data[:-1], data[1:])[0, 1]) if n > 2 else 0.0

    # ── Durbin-Watson ─────────────────────────────────────────────────────
    dw = _durbin_watson(data)

    # ── Conclusiones globales ─────────────────────────────────────────────
    normalidad_votes = sum([
        1 if (shapiro and not shapiro.rechaza_h0) else 0,
        1 if not ad_test.rechaza_h0 else 0,
        1 if not ks_test.rechaza_h0 else 0,
    ])
    normalidad_ok = normalidad_votes >= 2  # Mayoría de pruebas

    independencia_ok = not runs_result.rechaza_h0 and abs(ac_lag1) < 0.3

    apto_fase1 = n >= 20
    apto_fase2 = normalidad_ok and independencia_ok and n >= 15

    diagnostico, recomendaciones = _global_diagnostics(
        normalidad_ok, independencia_ok, n, ac_lag1
    )

    # ── QQ-Plot data ──────────────────────────────────────────────────────
    sorted_data = np.sort(data)
    theoretical_q = stats.norm.ppf(np.linspace(0.01, 0.99, len(sorted_data)))
    qq_data = {
        "theoretical": theoretical_q.tolist(),
        "sample": sorted_data.tolist(),
        "line_x": [float(theoretical_q[0]), float(theoretical_q[-1])],
        "line_y": [float(np.percentile(data, 25) + theoretical_q[0] * std),
                   float(np.percentile(data, 75) + theoretical_q[-1] * std)],
    }

    # ── Histograma ────────────────────────────────────────────────────────
    n_bins = max(10, int(np.sqrt(n)))
    counts, bin_edges = np.histogram(data, bins=n_bins)
    x_normal = np.linspace(media - 4*std, media + 4*std, 200)
    histograma = {
        "counts": counts.tolist(),
        "bin_edges": bin_edges.tolist(),
        "normal_x": x_normal.tolist(),
        "normal_y": stats.norm.pdf(x_normal, media, std).tolist(),
        "media": media, "std": std,
        "curtosis": float(stats.kurtosis(data)),
        "asimetria": float(stats.skew(data)),
    }

    return AssumptionsResult(
        n=n, media=media, std=std,
        shapiro_wilk=shapiro,
        anderson_darling=ad_test,
        kolmogorov_smirnov=ks_test,
        runs_test=runs_result,
        durbin_watson=dw,
        autocorrelacion_lag1=round(ac_lag1, 4),
        normalidad_ok=normalidad_ok,
        independencia_ok=independencia_ok,
        apto_fase1=apto_fase1,
        apto_fase2=apto_fase2,
        diagnostico_global=diagnostico,
        recomendaciones=recomendaciones,
        qq_data=qq_data,
        histograma=histograma,
    )


def _runs_test(data: np.ndarray, mediana: float, alpha: float) -> TestResult:
    """Prueba de rachas para independencia."""
    n = len(data)
    signs = [1 if x >= mediana else 0 for x in data]
    n1 = sum(signs)
    n2 = n - n1

    if n1 == 0 or n2 == 0:
        return TestResult(
            nombre="Prueba de Rachas",
            estadistico=0.0, p_valor=1.0, rechaza_h0=False,
            conclusion="No aplicable", interpretacion="Todos los valores están en el mismo lado de la mediana.",
            nivel_significancia=alpha,
        )

    # Contar rachas
    rachas = 1
    for i in range(1, n):
        if signs[i] != signs[i-1]:
            rachas += 1

    # Media y varianza esperadas
    mu_r = (2 * n1 * n2) / (n1 + n2) + 1
    sigma_r = np.sqrt(2 * n1 * n2 * (2*n1*n2 - n1 - n2) / ((n1+n2)**2 * (n1+n2-1))) if n > 2 else 1

    if sigma_r > 0:
        z = (rachas - mu_r) / sigma_r
        p_valor = 2 * (1 - stats.norm.cdf(abs(z)))
    else:
        z, p_valor = 0.0, 1.0

    rechaza = p_valor < alpha
    return TestResult(
        nombre="Prueba de Rachas",
        estadistico=round(float(z), 4),
        p_valor=round(float(p_valor), 6),
        rechaza_h0=rechaza,
        conclusion="Dependiente" if rechaza else "Independiente",
        interpretacion=(
            f"Rachas observadas: {rachas}, esperadas: {mu_r:.1f}. Z = {z:.3f}, p = {p_valor:.4f}. "
            + ("Existe evidencia de AUTOCORRELACIÓN o patrón no aleatorio en los datos."
               if rechaza else
               "Los datos son INDEPENDIENTES — no se detectan patrones sistemáticos.")
        ),
        nivel_significancia=alpha,
    )


def _durbin_watson(data: np.ndarray) -> Dict[str, Any]:
    """Estadístico Durbin-Watson para autocorrelación."""
    n = len(data)
    if n < 3:
        return None
    residuals = data - np.mean(data)
    dw_stat = np.sum(np.diff(residuals)**2) / np.sum(residuals**2)
    # DW ~ 2 indica sin autocorrelación; < 2 positiva; > 2 negativa
    interpretacion = (
        "Sin autocorrelación" if 1.5 < dw_stat < 2.5 else
        "Autocorrelación positiva" if dw_stat <= 1.5 else
        "Autocorrelación negativa"
    )
    return {"estadistico": round(float(dw_stat), 4), "interpretacion": interpretacion}


def _global_diagnostics(normalidad_ok, independencia_ok, n, ac_lag1):
    recs = []
    partes = []

    if normalidad_ok:
        partes.append("✅ Normalidad confirmada.")
    else:
        partes.append("⚠️ Los datos NO siguen distribución normal.")
        recs.append("Considerar transformaciones de datos (Log, Box-Cox) o gráficos de control robustos.")
        recs.append("Evaluar el uso de cartas de control no paramétricas si la no normalidad es severa.")

    if independencia_ok:
        partes.append("✅ Independencia de observaciones confirmada.")
    else:
        partes.append("⚠️ Se detecta dependencia entre observaciones.")
        recs.append("Revisar el proceso de muestreo — asegurar que las muestras sean independientes.")
        if abs(ac_lag1) >= 0.3:
            recs.append(f"Autocorrelación lag-1 = {ac_lag1:.3f} — considerar modelos de series de tiempo.")

    if n < 30:
        recs.append(f"Muestra pequeña (n={n}). Los resultados estadísticos son menos confiables con pocos datos.")

    diagnostico = " ".join(partes)
    return diagnostico, recs
