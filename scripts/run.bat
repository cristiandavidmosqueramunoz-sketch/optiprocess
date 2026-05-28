@echo off
echo.
echo ============================================================
echo   OPTIPROCESS - Iniciando Sistema
echo ============================================================
echo.

cd /d "%~dp0.."

:: Iniciar Backend
echo [Backend] Iniciando API en http://localhost:8000 ...
start "OptiProcess Backend" cmd /k "call backend\.venv\Scripts\activate.bat && cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

:: Esperar un momento
timeout /t 3 /nobreak > nul

:: Iniciar Frontend
echo [Frontend] Iniciando UI en http://localhost:5173 ...
start "OptiProcess Frontend" cmd /k "cd frontend && npm run dev"

:: Esperar y abrir navegador
timeout /t 4 /nobreak > nul
start "" "http://localhost:5173"

echo.
echo ============================================================
echo   Sistema iniciado:
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000
echo   API Docs: http://localhost:8000/api/docs
echo.
echo   Login: admin@optiprocess.com / Admin2024!
echo ============================================================
echo.
