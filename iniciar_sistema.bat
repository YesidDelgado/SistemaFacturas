@echo off
rem Configura la consola y trabaja desde la carpeta del proyecto.
setlocal
title Sistema de Facturacion
color 0B

cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"

echo.
echo ==========================================
echo       SISTEMA DE FACTURACION
echo ==========================================
echo.

if not exist "%PYTHON%" (
    rem Detiene el arranque si no existe el entorno virtual.
    echo ERROR: No se encuentra el entorno virtual.
    echo Verifica la carpeta .venv.
    pause
    exit /b 1
)

if not exist "backend\requirements.txt" (
    rem Detiene el arranque si falta el manifiesto de dependencias.
    echo ERROR: No se encuentra backend\requirements.txt.
    pause
    exit /b 1
)

if not exist ".env" (
    echo AVISO: No se encuentra el archivo .env en la raiz.
    echo La integracion con Gemini podria no funcionar.
    echo.
)

rem Comprueba e instala dependencias únicamente si faltan.
echo [1/3] Verificando dependencias...

"%PYTHON%" -c "import fastapi, uvicorn, dotenv, PIL, reportlab, multipart, openpyxl; from google import genai"

if errorlevel 1 (
    echo.
    echo ERROR: Faltan dependencias del proyecto.
    echo Instalando dependencias necesarias...
    "%PYTHON%" -m pip install -r "backend\requirements.txt"

    if errorlevel 1 (
        echo ERROR: No se pudieron instalar las dependencias.
        pause
        exit /b 1
    )
)

echo.
rem Informa si la configuración opcional de Gemini está disponible.
echo [2/3] Verificando configuracion de Gemini...

"%PYTHON%" -c "from pathlib import Path; from dotenv import load_dotenv; import os; load_dotenv(Path.cwd() / '.env'); print('Archivo .env encontrado.' if (Path.cwd() / '.env').is_file() else 'Archivo .env no encontrado.'); print('GEMINI_API_KEY configurada.' if os.getenv('GEMINI_API_KEY') else 'GEMINI_API_KEY NO configurada.')"

echo.
rem Inicia Uvicorn apuntando al módulo principal del backend.
echo [3/3] Iniciando la API...
cd /d "%~dp0backend"

echo.
echo API: http://127.0.0.1:8000
echo Documentacion: http://127.0.0.1:8000/docs
echo Para detener la API, presiona CTRL+C.
echo.

"%PYTHON%" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

echo.
echo La API se ha detenido.
pause
