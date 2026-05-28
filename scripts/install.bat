@echo off
echo.
echo ============================================================
echo   OPTIPROCESS - Instalacion del Sistema
echo   Sistema Profesional de Control Estadistico de Procesos
echo ============================================================
echo.

:: Verificar Python
python --version 2>nul
if errorlevel 1 (
    echo [ERROR] Python no encontrado. Instala Python 3.11+ desde python.org
    pause
    exit /b 1
)

:: Verificar Node.js
node --version 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js no encontrado. Instala Node.js 18+ desde nodejs.org
    pause
    exit /b 1
)

echo [1/5] Creando entorno virtual Python...
cd /d "%~dp0.."
python -m venv backend\.venv
call backend\.venv\Scripts\activate.bat

echo [2/5] Instalando dependencias del backend...
pip install -r backend\requirements.txt --quiet

echo [3/5] Instalando dependencias del frontend...
cd frontend
npm install --silent
cd ..

echo [4/5] Generando datos de ejemplo...
call backend\.venv\Scripts\python.exe data\sample_data\generate_samples.py

echo [5/5] Configuracion inicial...
if not exist backend\.env (
    echo SECRET_KEY=optiprocess-dev-secret-2024 > backend\.env
    echo DATABASE_URL=sqlite:///./optiprocess.db >> backend\.env
    echo DEBUG=false >> backend\.env
)

echo.
echo ============================================================
echo   INSTALACION COMPLETADA
echo.
echo   Para iniciar el sistema, ejecuta:  scripts\run.bat
echo   Usuario admin: admin@optiprocess.com
echo   Contrasena:    Admin2024!
echo ============================================================
echo.
pause
