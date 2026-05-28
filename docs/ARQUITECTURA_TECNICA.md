# OptiProcess — Documentación Técnica de Arquitectura

## 1. Decisiones de Diseño

### Por qué FastAPI + React?
- **FastAPI**: Máximo rendimiento Python, tipado estático, OpenAPI automático, async nativo
- **React + TypeScript**: UI profesional, ecosistema maduro, tipado fuerte, componentes reutilizables
- Esta arquitectura desacopla el motor estadístico del frontend, permite escalar cada capa independientemente

### Por qué SQLite?
- Cero configuración, ideal para despliegue inmediato
- Fácilmente upgradeable a PostgreSQL cambiando solo `DATABASE_URL`
- WAL mode habilitado para mejor rendimiento concurrente

### Separación de Responsabilidades
```
API Layer        → Validación de entrada, autorización, respuestas HTTP
Service Layer    → Lógica de negocio, coordinación
Statistical Layer → Cálculos estadísticos puros (numpy, scipy)
Data Layer       → Persistencia, consultas SQL
```

## 2. Motor Estadístico

### Phase1Engine
- Análisis iterativo hasta `MAX_ITERATIONS = 10`
- No excluye más del `MAX_EXCLUSION_RATIO = 25%` de los datos
- Registro de trazabilidad completa de exclusiones
- Criterio de parada: sin puntos OOC o límite alcanzado

### Phase2Engine
- Límites de control inmutables (bloqueados)
- No admite recálculo de límites
- ARL₀ teórico = 370 para ±3σ con distribución normal

### Reglas Western Electric (8 reglas)
| Regla | Descripción | Señal |
|-------|-------------|-------|
| 1 | 1 punto > ±3σ | Causa especial inmediata |
| 2 | 9 puntos mismo lado CL | Desplazamiento de media |
| 3 | 6 puntos en tendencia | Desgaste/deriva |
| 4 | 14 alternando | Mezcla/oscilación |
| 5 | 2/3 fuera de ±2σ | Cambio moderado |
| 6 | 4/5 fuera de ±1σ | Desplazamiento leve |
| 7 | 15 en zona C | Estratificación |
| 8 | 8 fuera de zona C | Mezcla de causas |

### Constantes Estadísticas
Tablas d₂, D₃, D₄, A₂, A₃, B₃, B₄ según ISO 8258 para n = 2 a 25.
Interpolación lineal para tamaños intermedios no tabulados.

## 3. Seguridad

### Autenticación JWT
- Access token: 8 horas de validez
- Refresh token: 7 días de validez
- Algoritmo: HS256
- Contraseñas: bcrypt con salt automático

### Roles y Permisos
```python
ROLES = {
  "administrador":    nivel=5, permisos=["*"]
  "ingeniero_calidad": nivel=4, permisos=[...todos los módulos]
  "supervisor":       nivel=3, permisos=[datos, graficos, capacidad, reportes, fase2]
  "analista":         nivel=2, permisos=[datos, graficos, supuestos, fase1, fase2]
  "usuario":          nivel=1, permisos=[datos, graficos]
}
```

## 4. Modelos de Datos

### Dataset
- Almacena datos como JSON en columna `datos`
- `columnas_info`: metadata de columnas (tipo, stats básicos)
- `estadisticos`: descriptivos por columna numérica
- Soft delete con campo `activo`

### Analysis
- `tipo`: tipo de carta o análisis
- `fase`: "I" o "II"
- `resultados`: JSON con todos los resultados
- `limites_control`: JSON con CL, UCL, LCL
- `puntos_excluidos`: historial de exclusiones Fase I
- `interpretacion`: diagnóstico textual automático

## 5. Escalabilidad

### Para producción empresarial:
1. Cambiar `DATABASE_URL` a PostgreSQL
2. Agregar Redis para cache de análisis pesados
3. Usar Celery para análisis asíncronos en background
4. Agregar nginx como reverse proxy
5. Contenedorizar con Docker Compose
6. Agregar exportación PDF real con ReportLab
7. Implementar WebSockets para monitoreo real-time

### Migraciones de base de datos
```bash
cd backend
alembic init alembic
alembic revision --autogenerate -m "descripcion"
alembic upgrade head
```
