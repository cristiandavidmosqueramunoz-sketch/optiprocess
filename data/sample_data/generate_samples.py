"""
OptiProcess - Generador de datos de muestra para demostración.
Genera datasets realistas de manufactura para probar todos los módulos.
"""
import numpy as np
import pandas as pd
from pathlib import Path

np.random.seed(42)
OUTPUT_DIR = Path(__file__).parent

def generate_xbar_r_data():
    """Dataset para carta X̄-R: diámetro de tornillos (mm)"""
    n_subgroups = 30
    subgroup_size = 5
    true_mean = 10.0
    true_sigma = 0.05

    data = []
    for sg in range(1, n_subgroups + 1):
        # Introducir causas especiales en subgrupos 8, 15, 22
        shift = 0
        if sg == 8:
            shift = 0.20  # Cambio de herramienta
        elif sg == 15:
            shift = -0.15  # Desgaste
        elif sg == 22:
            shift = 0.25

        for obs in range(1, subgroup_size + 1):
            val = np.random.normal(true_mean + shift, true_sigma)
            data.append({
                "subgrupo": sg,
                "observacion": obs,
                "diametro_mm": round(val, 4),
            })

    df = pd.DataFrame(data)
    df.to_csv(OUTPUT_DIR / "tornillos_xbar_r.csv", index=False)
    print(f"✓ tornillos_xbar_r.csv ({len(df)} filas, {n_subgroups} subgrupos × {subgroup_size})")
    return df


def generate_imr_data():
    """Dataset para I-MR: temperatura de horno (°C)"""
    n = 50
    temps = []
    for i in range(n):
        if i < 20:
            t = np.random.normal(850, 3)
        elif i < 30:
            t = np.random.normal(855, 3)  # Desplazamiento
        else:
            t = np.random.normal(850, 3)
        temps.append(round(t, 2))

    df = pd.DataFrame({
        "muestra": range(1, n + 1),
        "temperatura_C": temps,
        "turno": ["A" if i < 17 else "B" if i < 34 else "C" for i in range(n)],
        "operador": [f"OP{(i % 3) + 1}" for i in range(n)],
    })
    df.to_csv(OUTPUT_DIR / "temperatura_horno_imr.csv", index=False)
    print(f"✓ temperatura_horno_imr.csv ({n} observaciones)")
    return df


def generate_capability_data():
    """Dataset para análisis de capacidad: peso de tabletas (mg)"""
    n = 200
    # Proceso bien centrado
    pesos = np.random.normal(500.0, 2.5, n)

    df = pd.DataFrame({
        "muestra": range(1, n + 1),
        "peso_mg": np.round(pesos, 3),
        "lote": [f"L{(i // 50) + 1:02d}" for i in range(n)],
    })
    df.to_csv(OUTPUT_DIR / "tabletas_capacidad.csv", index=False)
    print(f"✓ tabletas_capacidad.csv ({n} obs) — Target=500mg, USL=506, LSL=494")
    return df


def generate_attributes_data():
    """Dataset para gráficos de atributos: defectos en pintura automotriz"""
    n_subgroups = 25
    data = []
    for i in range(1, n_subgroups + 1):
        n = 100
        p_real = 0.03 if i not in [6, 12, 19] else 0.12
        defectos = int(np.random.binomial(n, p_real))
        data.append({
            "subgrupo": i,
            "n_inspeccionados": n,
            "n_defectuosos": defectos,
            "proporcion_defectuosa": round(defectos / n, 4),
        })

    df = pd.DataFrame(data)
    df.to_csv(OUTPUT_DIR / "pintura_carta_p.csv", index=False)
    print(f"✓ pintura_carta_p.csv ({n_subgroups} subgrupos)")
    return df


def generate_xbar_s_large():
    """Dataset para X̄-S: resistencia de materiales (MPa), n=10"""
    n_subgroups = 25
    subgroup_size = 10
    data = []
    for sg in range(1, n_subgroups + 1):
        shift = 5 if sg == 18 else 0
        for obs in range(1, subgroup_size + 1):
            val = np.random.normal(320 + shift, 8)
            data.append({
                "subgrupo": sg,
                "obs": obs,
                "resistencia_MPa": round(val, 2),
            })
    df = pd.DataFrame(data)
    df.to_csv(OUTPUT_DIR / "resistencia_xbar_s.csv", index=False)
    print(f"✓ resistencia_xbar_s.csv ({len(df)} obs, {n_subgroups} subgrupos × {subgroup_size})")
    return df


if __name__ == "__main__":
    print("Generando datos de muestra para OptiProcess...\n")
    generate_xbar_r_data()
    generate_imr_data()
    generate_capability_data()
    generate_attributes_data()
    generate_xbar_s_large()
    print("\n✅ Todos los datasets generados correctamente en:", OUTPUT_DIR)
