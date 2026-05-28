# OptiProcess
### Sistema Profesional de Control Estadístico de Procesos (CEP/SPC)

> Plataforma empresarial para análisis estadístico industrial, monitoreo de procesos manufactureros y gestión de calidad.

---

## Características Principales

### Módulos Estadísticos
| Módulo | Descripción | Técnicas |
|--------|-------------|----------|
| **Gestión de Datos** | Carga, limpieza y exploración | CSV, Excel, ingreso manual |
| **Gráficos Fase I** | Análisis histórico iterativo | X̄-R, X̄-S, I-MR, p, np, c, u |
| **Monitoreo Fase II** | Vigilancia operacional | Límites fijos, alertas en tiempo real |
| **Supuestos** | Validación estadística | Shapiro-Wilk, Anderson-Darling, KS, Rachas |
| **Capacidad** | Índices de proceso | Cp, Cpk, Cpl, Cpu, Pp, Ppk, PPM |
| **Muestreo** | Planes de aceptación | Simple, doble, curvas OC, AOQ, ATI |
| **Reportes** | Generación automática | PDF ejecutivo, Excel |

### Características Técnicas
- **Reglas Western Electric / Nelson**: 8 reglas de detección de causas especiales
- **Fase I iterativa**: Depuración automática con trazabilidad completa
- **Fase II**: Monitoreo con límites bloqueados de Fase I
- **Interpretaciones automáticas**: Diagnósticos y recomendaciones inteligentes
- **Constantes estadísticas**: Tablas ISO 8258 para n = 2 a 25
- **Gráficos interactivos**: Plotly.js con zoom, exportación PNG/PDF

### Sistema Empresarial
- Autenticación JWT segura
- 5 roles de usuario (Administrador, Ing. Calidad, Supervisor, Analista, Usuario)
- Modo oscuro / modo claro
- Interfaz responsive y moderna
- API REST documentada (OpenAPI / Swagger)

---

## Arquitectura

```
OptiProcess/
├── backend/                 # API FastAPI (Python)
│   ├── app/
│   │   ├── api/             # Endpoints REST
│   │   ├── core/            # Seguridad, logging, excepciones
│   │   ├── models/          # Modelos SQLAlchemy
│   │   ├── schemas/         # Validación Pydantic
│   │   └── services/
│   │       └── statistical/ # Motor estadístico
│   │           ├── phase1_engine.py   # Análisis Fase I
│   │           ├── phase2_engine.py   # Monitoreo Fase II
│   │           ├── control_charts.py  # Cálculos de cartas
│   │           ├── capability.py      # Cp, Cpk, Pp, Ppk
│   │           ├── assumptions.py     # Pruebas normalidad/independencia
│   │           ├── sampling.py        # Planes de muestreo
│   │           └── rules_engine.py    # Reglas Western Electric
│   └── requirements.txt
│
├── frontend/                # Aplicación React + TypeScript
│   └── src/
│       ├── api/             # Cliente HTTP
│       ├── components/      # Componentes reutilizables
│       ├── pages/           # Vistas por módulo
│       ├── store/           # Estado global (Zustand)
│       └── types/           # Tipos TypeScript
│
├── data/sample_data/        # Datasets de demostración
├── scripts/                 # Scripts de instalación y ejecución
└── docs/                    # Documentación técnica
```

---

## Instalación Rápida (Windows)

### Prerrequisitos
- Python 3.11 o superior
- Node.js 18 o superior
- npm 9+

### Pasos

```bash
# 1. Instalar todo el sistema
scripts\install.bat

# 2. Iniciar el sistema
scripts\run.bat
```

El sistema se abrirá automáticamente en: **http://localhost:5173**

### Credenciales de Demo
| Campo | Valor |
|-------|-------|
| Email | admin@optiprocess.com |
| Contraseña | Admin2024! |

---

## Instalación Manual

### Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate      # Linux/Mac
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Datos de Ejemplo
```bash
python data/sample_data/generate_samples.py
```

---

## Uso del Sistema

### 1. Carga de Datos
- Navegar a **Gestión de Datos**
- Arrastrar un archivo CSV/Excel o usar datos de muestra en `data/sample_data/`
- Revisar estadísticos descriptivos y calidad del dataset

### 2. Análisis Fase I
- Ir a **Fase I — Análisis**
- Seleccionar dataset y tipo de gráfico (X̄-R, X̄-S, I-MR, etc.)
- Ejecutar análisis iterativo automático
- Revisar iteraciones, exclusiones y límites establecidos
- Guardar límites para Fase II

### 3. Monitoreo Fase II
- Ir a **Fase II — Monitor**
- Seleccionar análisis de Fase I como base
- Seleccionar nuevos datos a monitorear
- Revisar alertas y estado del proceso

### 4. Capacidad del Proceso
- Ir a **Capacidad del Proceso**
- Ingresar especificaciones (LSL, USL, objetivo)
- Interpretar Cp, Cpk, Pp, Ppk con semáforos visuales

---

## API REST

La documentación completa de la API está disponible en:
- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

### Endpoints principales
```
POST /api/auth/login/json           Autenticación
POST /api/datasets/upload           Cargar dataset
POST /api/charts/phase1/analyze     Análisis Fase I
POST /api/charts/phase2/monitor     Monitoreo Fase II
POST /api/capability/calculate      Capacidad del proceso
POST /api/assumptions/validate      Validar supuestos
POST /api/sampling/design           Diseñar plan de muestreo
GET  /api/dashboard/summary         Dashboard ejecutivo
```

---

## Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| Backend | Python 3.11 + FastAPI |
| Base de datos | SQLite (upgradeable a PostgreSQL) |
| ORM | SQLAlchemy 2.0 |
| Autenticación | JWT (python-jose) + bcrypt |
| Estadística | NumPy, SciPy, pandas, statsmodels |
| Frontend | React 18 + TypeScript + Vite |
| Estilos | Tailwind CSS 3 |
| Gráficos | Plotly.js + Recharts |
| Estado | Zustand |

---

## Metodología SPC Implementada

### Fase I — Análisis Histórico
1. Carga de datos históricos del proceso
2. Verificación de supuestos (normalidad, independencia)
3. Cálculo inicial de límites de control (±3σ)
4. Aplicación de las 8 reglas Western Electric
5. Identificación y exclusión de causas especiales
6. Recálculo iterativo de límites (hasta 10 iteraciones)
7. Verificación de estabilidad estadística
8. Establecimiento de límites para Fase II

### Fase II — Monitoreo Operacional
1. Carga de límites establecidos en Fase I (fijos)
2. Monitoreo de nuevas observaciones
3. Aplicación continua de reglas de control
4. Generación automática de alertas
5. Diagnóstico del estado del proceso
6. Recomendaciones de acción correctiva

### Índices de Capacidad
- **Cp**: Capacidad potencial (sin descentramiento)
- **Cpk**: Capacidad real (con descentramiento)
- **Cpl/Cpu**: Capacidad unilateral inferior/superior
- **Pp/Ppk**: Desempeño largo plazo (sigma global)
- **PPM**: Fracción no conforme estimada

---

## Contribuciones y Soporte

Para soporte técnico o contribuciones:
- Revisar la documentación en `/docs`
- Revisar los logs en `backend/logs/optiprocess.log`
- API docs en http://localhost:8000/api/docs

---

*OptiProcess v1.0.0 — Sistema Empresarial de CEP/SPC*
